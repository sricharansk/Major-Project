"""Train and evaluate all forecasting models on identical chronological splits and valid-target masks.

Artifacts per run: ``artifacts/models/{run_id}/`` with model weights, config.yaml, feature_schema.json,
split_manifest.json, training_history.csv, environment.json and predictions_{val,calib,test}.npz.
Every run is logged to MLflow (failed runs included) and summarised in ``reports/experiments``.
"""

from __future__ import annotations

import csv
import random
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from smartcity import settings
from smartcity.models import baselines, trees
from smartcity.models.deep import ContextGatedGraphTransformer, GRUForecaster, masked_huber
from smartcity.training import metrics as M
from smartcity.training import tracking
from smartcity.training.data import ForecastData, load_data
from smartcity.utils import environment_info, new_run_id, read_json, sha256_file, write_json

ART = settings.ROOT / "artifacts" / "models"
EXP = settings.ROOT / "reports" / "experiments"

DEEP_VARIANTS = {
    "proposed": dict(kind="graph_transformer", use_graph=True, use_gate=True),
    "temporal_transformer": dict(kind="graph_transformer", use_graph=False, use_gate=True),
    "gru": dict(kind="gru"),
    # ablations
    "ablation_no_gate": dict(kind="graph_transformer", use_graph=True, use_gate=False),
    "ablation_no_weather": dict(kind="graph_transformer", use_graph=True, use_gate=True, drop_groups=["weather"]),
    "ablation_no_infrastructure": dict(kind="graph_transformer", use_graph=True, use_gate=True,
                                       drop_groups=["infrastructure"]),
    "ablation_no_events": dict(kind="graph_transformer", use_graph=True, use_gate=True, drop_groups=["events"]),
    "ablation_no_incidents": dict(kind="graph_transformer", use_graph=True, use_gate=True, drop_groups=["incidents"]),
}


def seed_all(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def _run_dir(run_id: str) -> Path:
    d = ART / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _common_artifacts(d: Path, data: ForecastData, cfg: dict):
    (d / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    write_json(d / "feature_schema.json", {k: data.meta[k] for k in
               ["track", "feature_names", "groups", "group_slices", "feature_schema_hash", "speed_unit",
                "lookback_steps", "horizon_steps", "horizon_minutes", "link_ids", "graph_hash"]})
    write_json(d / "split_manifest.json", {"splits": data.meta["splits"], "split_times_utc": data.meta["split_times_utc"],
                                           "features_sha256": data.meta["sha256"]})
    write_json(d / "environment.json", environment_info())


def _save_preds(d: Path, split: str, origins: np.ndarray, P: np.ndarray):
    np.savez_compressed(d / f"predictions_{split}.npz", origins=origins, pred_mph=P.astype(np.float32))


# ------------------------------------------------------------------------------------------------
# deep models
# ------------------------------------------------------------------------------------------------

def make_model(variant: str, data: ForecastData, mcfg: dict):
    spec = DEEP_VARIANTS[variant]
    if spec["kind"] == "gru":
        return GRUForecaster(data.X.shape[-1], len(data.horizon_steps), hidden_dim=mcfg["hidden_dim"],
                             dropout=mcfg["dropout"])
    return ContextGatedGraphTransformer(data.meta["group_slices"], len(data.horizon_steps), data.L,
                                        use_graph=spec["use_graph"], use_gate=spec["use_gate"], **mcfg)


def _group_drop_mask(data: ForecastData, variant: str) -> np.ndarray | None:
    drop = DEEP_VARIANTS[variant].get("drop_groups") or []
    if not drop:
        return None
    present = [g for g in drop if g in data.meta["groups"]]
    if not present:
        return None
    keep = np.ones(len(data.meta["groups"]), bool)
    for g in present:
        keep[data.meta["groups"].index(g)] = False
    return keep


def resolve_device(name: str | None) -> torch.device:
    """`auto` -> CUDA when available, else CPU.  Explicit `cpu` / `cuda` are honoured as given."""
    if not name or name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(name)


def _apply_drop(x, m, data, keep):
    if keep is None:
        return x, m
    m = m & torch.from_numpy(keep).to(m.device)
    x = x.clone()
    for gi, g in enumerate(data.meta["groups"]):
        if not keep[gi]:
            a, b = data.meta["group_slices"][g]
            x[..., a:b] = 0.0
    return x, m


@torch.no_grad()
def predict_deep(model, data: ForecastData, origins: np.ndarray, keep=None, batch: int = 64,
                 node_drop: torch.Tensor | None = None, input_transform=None) -> np.ndarray:
    model.eval()
    dev = next(model.parameters()).device
    ei = torch.from_numpy(data.edge_index).to(dev)
    if node_drop is not None:
        node_drop = node_drop.to(dev)
    outs = []
    for i in range(0, len(origins), batch):
        x, m, _, _ = data.window(origins[i:i + batch])
        x, m = _apply_drop(x, m, data, keep)
        if input_transform is not None:
            x, m = input_transform(x, m)
        outs.append(model(x.to(dev), m.to(dev), ei, node_drop=node_drop).cpu().numpy())
    return data.to_mph(np.concatenate(outs)) if outs else np.zeros((0, len(data.horizon_steps), data.X.shape[1]))


def train_deep(variant: str, data: ForecastData, run_id: str | None = None, max_epochs: int | None = None,
               windows_per_epoch: int | None = None, max_minutes: float | None = None) -> dict:
    tcfg = settings.load("training")["training"]
    mcfg = {k: v for k, v in settings.load("model")["model"].items() if k not in ("name", "lookback_steps", "horizon_steps")}
    seed_all(tcfg["seed"])
    torch.set_num_threads(4)
    run_id = run_id or new_run_id(variant)
    d = _run_dir(run_id)
    max_minutes = max_minutes or tcfg.get("max_minutes_per_model") or None
    cfg = {"variant": variant, "spec": DEEP_VARIANTS[variant], "model": mcfg, "training": tcfg,
           "max_epochs_override": max_epochs, "windows_per_epoch": windows_per_epoch,
           "max_minutes_per_model": max_minutes}
    dev = resolve_device(tcfg.get("device"))
    cfg["resolved_device"] = str(dev)
    # Training the GRU with cuDNN on Windows/CUDA 12.8 (torch 2.11) crashed the process at exit (0xC0000409) after
    # a successful run; the native (non-cuDNN) CUDA RNN kernels do not.  Set per call so other variants keep cuDNN.
    gru_on_cuda = DEEP_VARIANTS[variant]["kind"] == "gru" and dev.type == "cuda"
    torch.backends.cudnn.enabled = not gru_on_cuda
    cfg["cudnn_enabled"] = torch.backends.cudnn.enabled
    _common_artifacts(d, data, cfg)
    model = make_model(variant, data, mcfg).to(dev)
    keep = _group_drop_mask(data, variant)
    opt = torch.optim.AdamW(model.parameters(), lr=tcfg["learning_rate"], weight_decay=tcfg["weight_decay"])
    ei = torch.from_numpy(data.edge_index).to(dev)
    tr, va = data.origins["train"], data.origins["val"]
    va_sub = va[:: max(1, len(va) // 1500)]  # fixed validation subset (same every epoch)
    rng = np.random.default_rng(tcfg["seed"])
    best, best_ep, bad, history, skipped = np.inf, -1, 0, [], 0
    stopped_reason = "max_epochs"
    epochs = max_epochs or tcfg["max_epochs"]
    wpe = windows_per_epoch or tcfg.get("max_train_windows_per_epoch") or len(tr)
    t0 = time.time()
    for ep in range(epochs):
        model.train()
        sel = rng.choice(tr, size=min(wpe, len(tr)), replace=False)
        losses = []
        for i in range(0, len(sel), tcfg["batch_size"]):
            x, m, yz, mask = data.window(sel[i:i + tcfg["batch_size"]])
            x, m = _apply_drop(x, m, data, keep)
            pred = model(x.to(dev), m.to(dev), ei)
            loss = masked_huber(pred, yz.to(dev), mask.to(dev), tcfg["huber_delta"])
            if loss is None:
                skipped += 1  # no observed target in batch: skipped and counted
                continue
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), tcfg["gradient_clip_norm"])
            opt.step()
            losses.append(loss.item())
        P = predict_deep(model, data, va_sub, keep)
        val_mae = M.by_horizon(data.Y[va_sub], P, data.horizon_minutes)
        mean_mae = float(np.mean([v["mae"] for v in val_mae.values()]))
        history.append({"epoch": ep, "train_loss": float(np.mean(losses)) if losses else None,
                        "val_mae_mean_mph": mean_mae, **{f"val_mae_{h}m": v["mae"] for h, v in val_mae.items()},
                        "elapsed_s": round(time.time() - t0, 1)})
        print(f"[{variant}] epoch {ep} loss {history[-1]['train_loss']} val_mae {mean_mae:.3f}", flush=True)
        if mean_mae < best - 1e-4:
            best, best_ep, bad = mean_mae, ep, 0
            torch.save(model.state_dict(), d / "model.pt")
        else:
            bad += 1
            if bad >= tcfg["early_stopping_patience"]:
                stopped_reason = "early_stopping"
                break
        if max_minutes and (time.time() - t0) / 60 >= max_minutes:
            # wall-clock budget (recorded, not hidden): the best epoch so far is kept, nothing is extrapolated
            stopped_reason = f"time_budget_{max_minutes:g}min"
            print(f"[{variant}] time budget of {max_minutes:g} min reached after epoch {ep}", flush=True)
            break
    train_time = time.time() - t0
    with open(d / "training_history.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(history[0].keys()))
        w.writeheader()
        w.writerows(history)
    # Final predictions, latency and every downstream consumer (calibration, explanations, agents) run on CPU.
    model = model.cpu()
    model.load_state_dict(torch.load(d / "model.pt", map_location="cpu"))
    preds, latency = {}, None
    for split in ("val", "calib", "test"):
        o = data.origins[split]
        t1 = time.time()
        preds[split] = predict_deep(model, data, o, keep)
        if split == "test":
            latency = (time.time() - t1) / max(len(o), 1) * 1000
        _save_preds(d, split, o, preds[split])
    info = {"run_id": run_id, "model": variant, "best_epoch": best_ep, "best_val_mae": best,
            "epochs_run": len(history), "train_time_s": train_time, "infer_latency_ms_per_origin": latency,
            "skipped_batches_no_target": skipped, "model_sha256": sha256_file(d / "model.pt"),
            "n_params": sum(p.numel() for p in model.parameters()), "artifact_dir": str(d),
            "train_device": str(dev), "cudnn_enabled": cfg["cudnn_enabled"], "stopped_reason": stopped_reason,
            "max_minutes_per_model": max_minutes}
    write_json(d / "run_info.json", info)
    return {"info": info, "preds": preds}


# ------------------------------------------------------------------------------------------------
# baselines
# ------------------------------------------------------------------------------------------------

def run_simple_baselines(data: ForecastData) -> list[dict]:
    out = []
    a = data.meta["splits"]["bounds"]["train"][1]
    for name in ("persistence", "historical_average"):
        run_id = new_run_id(name)
        d = _run_dir(run_id)
        _common_artifacts(d, data, {"model": name})
        t0 = time.time()
        ha = baselines.HistoricalAverage(data.meta["frequency_minutes"]).fit(data.speed, data.times, a) \
            if name == "historical_average" else None
        train_time = time.time() - t0
        preds, latency = {}, None
        for split in ("val", "calib", "test"):
            o = data.origins[split]
            t1 = time.time()
            if name == "persistence":
                P = baselines.persistence(data.speed, o, data.horizon_steps, data.mu)
            else:
                P = ha.predict(data.times, o, data.horizon_steps)
            if split == "test":
                latency = (time.time() - t1) / max(len(o), 1) * 1000
            preds[split] = P
            _save_preds(d, split, o, P)
        info = {"run_id": run_id, "model": name, "train_time_s": train_time, "infer_latency_ms_per_origin": latency,
                "artifact_dir": str(d)}
        write_json(d / "run_info.json", info)
        out.append({"info": info, "preds": preds})
    return out


def run_tree_baselines(data: ForecastData, max_train_rows: int = 600_000) -> list[dict]:
    tcfg = settings.load("training")["trees"]
    seed = settings.load("training")["training"]["seed"]
    names = data.meta["feature_names"]
    sz = names.index("speed_z")
    tr = data.origins["train"]
    tr = tr[tr >= trees.N_LAGS]
    N = data.X.shape[1]
    stride = max(1, int(np.ceil(len(tr) * N / max_train_rows)))
    tr = tr[::stride]
    va = data.origins["val"][:: max(1, len(data.origins["val"]) // 3000)]
    Xtr, cols = trees.tabular(data.X, sz, tr, names)
    Xva, _ = trees.tabular(data.X, sz, va, names)
    out = []
    for name, fit in (("xgboost", trees.fit_xgb), ("lightgbm", trees.fit_lgbm)):
        run_id = new_run_id(name)
        d = _run_dir(run_id)
        _common_artifacts(d, data, {"model": name, "trees": tcfg, "train_origin_stride": stride,
                                    "tabular_columns": cols})
        models, t0 = [], time.time()
        for k in range(len(data.horizon_steps)):
            yz_tr = ((data.Y[tr, k] - data.mu) / data.sd).reshape(-1)
            yz_va = ((data.Y[va, k] - data.mu) / data.sd).reshape(-1)
            mtr, mva = np.isfinite(yz_tr), np.isfinite(yz_va)
            mdl = fit(Xtr[mtr], yz_tr[mtr], Xva[mva], yz_va[mva], tcfg, seed)
            models.append(mdl)
            ext = "json" if name == "xgboost" else "txt"
            if name == "xgboost":
                mdl.save_model(str(d / f"model_h{data.horizon_minutes[k]}.{ext}"))
            else:
                mdl.booster_.save_model(str(d / f"model_h{data.horizon_minutes[k]}.{ext}"))
        train_time = time.time() - t0
        preds, latency = {}, None
        for split in ("val", "calib", "test"):
            o = data.origins[split]
            o_ok = np.maximum(o, trees.N_LAGS)
            t1 = time.time()
            Xs, _ = trees.tabular(data.X, sz, o_ok, names)
            P = np.stack([m.predict(Xs).reshape(len(o), N) for m in models], axis=1)
            P = data.to_mph(P)
            if split == "test":
                latency = (time.time() - t1) / max(len(o), 1) * 1000
            preds[split] = P
            _save_preds(d, split, o, P)
        info = {"run_id": run_id, "model": name, "train_time_s": train_time, "infer_latency_ms_per_origin": latency,
                "train_rows": int(Xtr.shape[0]), "train_origin_stride": stride, "artifact_dir": str(d)}
        write_json(d / "run_info.json", info)
        out.append({"info": info, "preds": preds, "models": models, "columns": cols})
    return out


# ------------------------------------------------------------------------------------------------
# evaluation / export
# ------------------------------------------------------------------------------------------------

def evaluate_and_export(results: list[dict], data: ForecastData, track: str, file: str = "forecast_metrics.csv"):
    """Metrics on the SAME test origins and the SAME valid-target mask for all models."""
    EXP.mkdir(parents=True, exist_ok=True)
    o = data.origins["test"]
    Y = data.Y[o]
    mask = np.isfinite(Y)
    for r in results:  # common mask: targets every model predicted
        mask &= np.isfinite(r["preds"]["test"])
    period = f"{data.meta['split_times_utc']['test'][0]} .. {data.meta['split_times_utc']['test'][1]}"
    manifest_hash = read_json(settings.ROOT / "data" / "manifests" / "source_manifest.json").get("manifest_hash", "") \
        if (settings.ROOT / "data" / "manifests" / "source_manifest.json").exists() else ""
    rows = []
    for r in results:
        info = r["info"]
        mh = M.by_horizon(Y, r["preds"]["test"], data.horizon_minutes, mask)
        for hm, v in mh.items():
            rows.append({"run_id": info["run_id"], "model": info["model"], "track": track, "split": "test",
                         "evaluation_period_utc": period, "horizon_min": hm, "n_valid_targets": v["n"],
                         "mae_mph": v["mae"], "rmse_mph": v["rmse"], "smape_pct": v["smape"], "r2": v["r2"],
                         "train_time_s": round(info.get("train_time_s") or 0, 2),
                         "infer_latency_ms_per_origin": info.get("infer_latency_ms_per_origin"),
                         "seed": settings.load("training")["training"]["seed"],
                         "graph_hash": data.meta["graph_hash"], "feature_schema_hash": data.meta["feature_schema_hash"],
                         "data_manifest_hash": manifest_hash, "artifact_dir": info["artifact_dir"]})
        tracking.log_forecast_run(info, data, mh, track)
    path = EXP / file
    write_header = not path.exists()
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        if write_header:
            w.writeheader()
        w.writerows(rows)
    # per-link test support: a link whose feed stopped before the test period has no targets there and is reported as
    # NOT_EVALUATED rather than silently contributing nothing to the aggregate rows above
    sup = EXP / f"link_test_support_{track}.csv"
    with open(sup, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["track", "link_id", *[f"n_test_targets_{h}m" for h in data.horizon_minutes], "status"])
        for n, lid in enumerate(data.meta["link_ids"]):
            counts = [int(mask[:, hi, n].sum()) for hi in range(len(data.horizon_minutes))]
            w.writerow([track, lid, *counts, "EVALUATED" if min(counts) > 0 else "NOT_EVALUATED_no_test_targets"])
    return rows


def run_all(track: str = "operational", deep_variants=("gru", "temporal_transformer", "proposed"),
            max_epochs: int | None = None, windows_per_epoch: int | None = None, file="forecast_metrics.csv"):
    data = load_data(track)
    results = run_simple_baselines(data) + run_tree_baselines(data)
    for v in deep_variants:
        results.append(train_deep(v, data, max_epochs=max_epochs, windows_per_epoch=windows_per_epoch))
    rows = evaluate_and_export(results, data, track, file)
    return results, rows
