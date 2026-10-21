"""Multi-seed study of the deep forecasters (single-seed results cannot separate models 0.01-0.05 mph apart).

    python scripts/multi_seed_study.py train --variant proposed --seed 1     # one run; repeat per variant and seed
    python scripts/multi_seed_study.py analyze                               # metrics, seed spread, paired bootstrap

Runs go through runner.train_deep (same data, budget, early stopping and device rules as the main run) into their own
artifact folders and are listed in artifacts/models/multi_seed_runs.json; the per-track registry that calibration,
explanations and agents read is not touched. `analyze` evaluates every listed run on one shared valid-target mask and
writes reports/experiments/multi_seed_metrics.csv (per run and horizon) and multi_seed_summary.csv (per model:
mean and spread over seeds; paired day-block bootstrap of the seed-averaged MAE difference against the proposed model).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np

from smartcity import settings
from smartcity.training import metrics as M
from smartcity.training import runner
from smartcity.training.data import load_data
from smartcity.utils import new_run_id, read_json, write_json

MANIFEST = settings.ROOT / "artifacts" / "models" / "multi_seed_runs.json"
EXP = settings.ROOT / "reports" / "experiments"


def _manifest() -> dict:
    return read_json(MANIFEST) if MANIFEST.exists() else {"runs": []}


def train(variant: str, seed: int, track: str) -> None:
    data = load_data(track)
    res = runner.train_deep(variant, data, run_id=new_run_id(f"ms-{variant}-s{seed}"), seed=seed)
    man = _manifest()  # one process at a time appends (runs are started sequentially by the caller)
    man["runs"].append({"variant": variant, "seed": seed, "track": track, **{k: res["info"][k] for k in (
        "run_id", "artifact_dir", "best_epoch", "epochs_run", "best_val_mae", "train_time_s", "train_device",
        "stopped_reason", "model_sha256")}})
    write_json(MANIFEST, man)
    print(json.dumps(man["runs"][-1]))


def analyze(track: str, n_boot: int, reference: str) -> None:
    data = load_data(track)
    o = data.origins["test"]
    Y = data.Y[o]
    runs = [r for r in _manifest()["runs"] if r["track"] == track]
    preds = {}
    for r in runs:
        z = np.load(Path(r["artifact_dir"]) / "predictions_test.npz")
        if not np.array_equal(z["origins"], o):
            raise RuntimeError(f"{r['run_id']}: test origins differ from the current data")
        preds[r["run_id"]] = z["pred_mph"]
    mask = np.isfinite(Y)
    for P in preds.values():
        mask &= np.isfinite(P)
    period = f"{data.meta['split_times_utc']['test'][0]} .. {data.meta['split_times_utc']['test'][1]}"
    rows = []
    for r in runs:
        for hm, v in M.by_horizon(Y, preds[r["run_id"]], data.horizon_minutes, mask).items():
            rows.append({"run_id": r["run_id"], "model": r["variant"], "seed": r["seed"], "track": track,
                         "evaluation_period_utc": period, "horizon_min": hm, "n_valid_targets": v["n"],
                         "mae_mph": round(v["mae"], 4), "rmse_mph": round(v["rmse"], 4), "r2": round(v["r2"], 4),
                         "best_epoch": r["best_epoch"], "epochs_run": r["epochs_run"],
                         "train_time_s": round(r["train_time_s"], 1), "train_device": r["train_device"],
                         "graph_hash": data.meta["graph_hash"], "feature_schema_hash": data.meta["feature_schema_hash"]})
    _write(EXP / "multi_seed_metrics.csv", rows)
    # seed-averaged absolute error per target, per model; paired day-block bootstrap of the difference vs reference
    day = np.asarray(data.times[o]).astype("datetime64[s]").astype("datetime64[D]").astype("int64")
    day_idx = np.broadcast_to(day[:, None, None], Y.shape)
    models = sorted({r["variant"] for r in runs})
    seeds_of = {m: sorted(r["seed"] for r in runs if r["variant"] == m) for m in models}
    # mean prediction error is averaged over seeds through |error|: P_eff is chosen so that |P_eff - Y| equals the
    # seed-mean absolute error, which lets the existing paired bootstrap run unchanged on seed-averaged MAE
    abs_err = {m: np.mean([np.abs(preds[r["run_id"]] - Y) for r in runs if r["variant"] == m], axis=0) for m in models}
    eff = {m: Y + abs_err[m] for m in models}
    summary = []
    for m in models:
        per_h = {}
        for k, hm in enumerate(data.horizon_minutes):
            vals = [x["mae_mph"] for x in rows if x["model"] == m and x["horizon_min"] == hm]
            per_h[hm] = (float(np.mean(vals)), float(np.std(vals, ddof=1)) if len(vals) > 1 else None, min(vals), max(vals))
        line = {"model": m, "track": track, "n_seeds": len(seeds_of[m]), "seeds": ";".join(map(str, seeds_of[m])),
                "evaluation_period_utc": period, "n_valid_targets_60m": int(mask[:, -1].sum())}
        for hm, (mu, sd, lo, hi) in per_h.items():
            line.update({f"mae_{hm}m_mean": round(mu, 4), f"mae_{hm}m_sd": None if sd is None else round(sd, 4),
                         f"mae_{hm}m_min": round(lo, 4), f"mae_{hm}m_max": round(hi, 4)})
        if m != reference and reference in models:
            for k, hm in enumerate(data.horizon_minutes):
                d = M.day_block_bootstrap_mae_diff(Y[:, k][mask[:, k]], eff[m][:, k][mask[:, k]],
                                                   eff[reference][:, k][mask[:, k]], day_idx[:, k][mask[:, k]], n_boot=n_boot)
                line.update({f"diff_vs_{reference}_{hm}m": round(d["mae_diff"], 4),
                             f"diff_vs_{reference}_{hm}m_ci95": f"[{d['ci95'][0]:.4f}, {d['ci95'][1]:.4f}]",
                             "n_days": d["n_days"]})
        summary.append(line)
    _write(EXP / "multi_seed_summary.csv", summary)
    for line in summary:
        print(line)


def _write(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--variant", required=True, choices=["gru", "temporal_transformer", "proposed"])
    t.add_argument("--seed", type=int, required=True)
    t.add_argument("--track", default="operational")
    a = sub.add_parser("analyze")
    a.add_argument("--track", default="operational")
    a.add_argument("--n-boot", type=int, default=1000)
    a.add_argument("--reference", default="proposed")
    args = ap.parse_args()
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    if args.cmd == "train":
        train(args.variant, args.seed, args.track)
    else:
        analyze(args.track, args.n_boot, args.reference)


if __name__ == "__main__":
    main()
