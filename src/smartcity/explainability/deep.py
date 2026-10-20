"""Explanations of the *actual* proposed graph Transformer (not a surrogate) and of tree baselines.

Proposed model — grouped Kernel SHAP:
  explained scalar   : predicted speed (mph) of target link n at horizon h for forecast origin t
  players            : feature groups split by time range (traffic last 30 min / traffic 30-120 min), each
                       context group, and *neighbour traffic* (traffic features of the target's graph
                       neighbours), so spatial influence is attributed explicitly
  masker             : a player that is "absent" takes its values from training-period background windows
                       (``n_background`` windows sampled from the TRAIN partition, averaged in expectation)
  graph topology     : held fixed
All coalitions (2^P) are evaluated exactly via shap.KernelExplainer with nsamples=2^P.
Outputs are model sensitivities, not causal effects.
"""

from __future__ import annotations

import csv
import time

import numpy as np
import shap
import torch

from smartcity import settings
from smartcity.utils import new_run_id, write_json

RECENT_STEPS = 6  # last 30 minutes at 5-min resolution


def players(data, n: int) -> list[dict]:
    gs = data.meta["group_slices"]
    L = data.L
    ei = data.edge_index
    nbrs = sorted(set(ei[0][ei[1] == n].tolist()) | set(ei[1][ei[0] == n].tolist()))
    ta, tb = gs["traffic"]
    P = [
        {"name": "traffic_target_last30min", "nodes": [n], "feat": (ta, tb), "steps": (L - RECENT_STEPS, L)},
        {"name": "traffic_target_30_120min", "nodes": [n], "feat": (ta, tb), "steps": (0, L - RECENT_STEPS)},
    ]
    if nbrs:
        P.append({"name": "traffic_graph_neighbours", "nodes": nbrs, "feat": (ta, tb), "steps": (0, L)})
    for g in data.meta["groups"]:
        if g == "traffic":
            continue
        P.append({"name": g, "nodes": "all", "feat": tuple(gs[g]), "steps": (0, L), "group": g})
    return P, nbrs


def _background(data, n_bg: int, seed: int) -> tuple[torch.Tensor, torch.Tensor]:
    rng = np.random.default_rng(seed)
    tr = data.origins["train"]
    sel = np.sort(rng.choice(tr, size=min(n_bg, len(tr)), replace=False))
    x, m, _, _ = data.window(sel)
    return x, m


class GroupedModelFn:
    """f(coalitions[K, P]) -> E_bg[ model(x_mixed)[h, n] ]  in mph."""

    def __init__(self, model, data, x, m, bx, bm, pl, n, h_idx, gi_map):
        self.model, self.data, self.x, self.m, self.bx, self.bm = model, data, x, m, bx, bm
        self.pl, self.n, self.h = pl, n, h_idx
        self.gi_map = gi_map
        self.ei = torch.from_numpy(data.edge_index)
        self.calls = 0

    @torch.no_grad()
    def __call__(self, Z: np.ndarray) -> np.ndarray:
        out = []
        nb = self.bx.shape[0]
        for z in Z:
            xs = self.x.repeat(nb, 1, 1, 1).clone()
            ms = self.m.repeat(nb, 1, 1, 1).clone()
            for j, p in enumerate(self.pl):
                if z[j] > 0.5:
                    continue
                s0, s1 = p["steps"]
                f0, f1 = p["feat"]
                nodes = slice(None) if p["nodes"] == "all" else p["nodes"]
                xs[:, s0:s1, nodes, f0:f1] = self.bx[:, s0:s1, nodes, f0:f1]
                gi = self.gi_map.get(p.get("group", "traffic"))
                if gi is not None:
                    ms[:, s0:s1, nodes, gi] = self.bm[:, s0:s1, nodes, gi]
            pred = self.model(xs, ms, self.ei)[:, self.h, self.n]
            self.calls += nb
            out.append(float(pred.mean()) * float(self.data.sd[self.n]) + float(self.data.mu[self.n]))
        return np.array(out)


def explain_alert(model, data, origin: int, n: int, h_idx: int, n_bg: int = 16, seed: int = 42) -> dict:
    model.eval()
    pl, nbrs = players(data, n)
    gi_map = {g: i for i, g in enumerate(data.meta["groups"])}
    x, m, _, _ = data.window(np.array([origin]))
    bx, bm = _background(data, n_bg, seed)
    fn = GroupedModelFn(model, data, x, m, bx, bm, pl, n, h_idx, gi_map)
    P = len(pl)
    t0 = time.time()
    explainer = shap.KernelExplainer(fn, np.zeros((1, P)))
    sv = explainer.shap_values(np.ones((1, P)), nsamples=2**P, silent=True)
    sv = np.asarray(sv).reshape(-1)
    runtime = time.time() - t0
    pred = fn(np.ones((1, P)))[0]
    base = float(np.asarray(explainer.expected_value).reshape(-1)[0])
    return {
        "explanation_id": new_run_id("xai"),
        "method": "grouped KernelSHAP (exact, all coalitions) on the proposed model",
        "link_id": data.meta["link_ids"][n], "link_index": n, "horizon_minutes": data.horizon_minutes[h_idx],
        "origin_index": int(origin), "origin_utc": int(data.times[origin]),
        "background": f"{n_bg} windows sampled from TRAIN partition (seed {seed})",
        "players": [p["name"] for p in pl], "neighbours": [data.meta["link_ids"][k] for k in nbrs],
        "group_contributions": {p["name"]: float(v) for p, v in zip(pl, sv)},
        "base_value": base, "prediction": float(pred), "additivity_gap": float(pred - base - sv.sum()),
        "observed_target_mph": None if not np.isfinite(data.Y[origin, h_idx, n]) else float(data.Y[origin, h_idx, n]),
        "recent_target_steps_observed": int(np.isfinite(data.speed[origin - RECENT_STEPS + 1:origin + 1, n]).sum()),
        "recent_steps": RECENT_STEPS,
        "runtime_s": runtime, "model_calls": fn.calls,
        "note": "Attributions describe model sensitivity, not causal effects.",
    }


@torch.no_grad()
def neighbour_removal(model, data, origins: np.ndarray, from_predict) -> list[dict]:
    """Change in test MAE when graph edges touching each link's neighbours are removed (one link at a time
    for the most connected links) — a model-sensitivity analysis."""
    rows = []
    ei = data.edge_index
    deg = np.bincount(np.concatenate([ei[0], ei[1]]), minlength=data.X.shape[1]) if ei.size else np.zeros(1)
    base = from_predict(model, data, origins)
    Y = data.Y[origins]
    for n in np.argsort(-deg)[:5]:
        if deg[n] == 0:
            continue
        drop = torch.zeros(data.X.shape[1], dtype=torch.bool)
        nb = set(ei[0][ei[1] == n].tolist()) | set(ei[1][ei[0] == n].tolist())
        for k in nb:
            drop[k] = True
        P = from_predict(model, data, origins, node_drop=drop)
        ok = np.isfinite(Y[:, :, n])
        rows.append({"link_id": data.meta["link_ids"][n], "n_neighbours": len(nb),
                     "mae_target_with_graph": float(np.abs(base[:, :, n] - Y[:, :, n])[ok].mean()),
                     "mae_target_neighbour_edges_removed": float(np.abs(P[:, :, n] - Y[:, :, n])[ok].mean()),
                     "mean_abs_prediction_change_mph": float(np.abs(P[:, :, n] - base[:, :, n]).mean()),
                     "n_targets": int(ok.sum())})
    return rows


@torch.no_grad()
def temporal_window_sensitivity(model, data, origins: np.ndarray, from_predict) -> list[dict]:
    """Replace the oldest k input steps with the TRAIN mean feature vector and measure MAE change."""
    tr = data.origins["train"]
    bg = data.X[tr[:: max(1, len(tr) // 2000)]].mean(axis=0)  # [N, F]
    Y = data.Y[origins]
    rows = []
    for keep_recent in (24, 12, 6, 3, 1):
        def tf(x, m, keep=keep_recent):
            x = x.clone()
            cut = data.L - keep
            if cut > 0:
                x[:, :cut] = torch.from_numpy(bg).float()
            return x, m
        P = from_predict(model, data, origins, input_transform=tf)
        ok = np.isfinite(Y)
        rows.append({"recent_steps_kept": keep_recent, "minutes_kept": keep_recent * 5,
                     "mae_mph": float(np.abs(P - Y)[ok].mean()), "n_targets": int(ok.sum())})
    return rows


def tree_shap_global(tree_result: dict, data, max_rows: int = 3000, seed: int = 42) -> dict:
    """TreeExplainer on the LightGBM/XGBoost *baseline* (labelled as such; it does not explain the GNN)."""
    from smartcity.models import trees

    rng = np.random.default_rng(seed)
    o = data.origins["test"]
    o = np.sort(rng.choice(o, size=min(len(o), max(1, max_rows // data.X.shape[1])), replace=False))
    names = data.meta["feature_names"]
    Xs, cols = trees.tabular(data.X, names.index("speed_z"), np.maximum(o, trees.N_LAGS), names)
    out = {"model": tree_result["info"]["model"], "run_id": tree_result["info"]["run_id"], "rows": int(Xs.shape[0]),
           "by_horizon": {}}
    t0 = time.time()
    for k, mdl in enumerate(tree_result["models"]):
        sv = shap.TreeExplainer(mdl).shap_values(Xs)
        imp = np.abs(sv).mean(0)
        grouped: dict = {}
        for c, v in zip(cols, imp):
            g = trees.group_of(c, data.meta["group_slices"], names)
            grouped[g] = grouped.get(g, 0.0) + float(v)
        out["by_horizon"][data.horizon_minutes[k]] = {
            "grouped_mean_abs_shap_z": grouped,
            "top_features": sorted(zip(cols, imp.tolist()), key=lambda t: -t[1])[:10]}
    out["runtime_s"] = time.time() - t0
    out["note"] = "Explains the tree BASELINE only. Values in standardised-speed units. Not causal."
    return out


def eligible_alert_mask(data, test: np.ndarray, h_idx: int, recent_steps: int = RECENT_STEPS) -> np.ndarray:
    """[len(test), N] boolean: (origin, link) pairs that are legitimate alert examples.

    A pair is eligible only if the link's *raw* speed was observed at every one of the last ``recent_steps``
    input steps (no forward-filled or stale inputs) and the target at ``h_idx`` was observed.  Without this
    rule the "largest predicted drop" is dominated by links whose feed went dark, where the model extrapolates
    from stale or missing inputs (a real-data run picked a link with no observations for four weeks)."""
    obs = np.isfinite(data.speed).astype(np.int32)                 # [T, N]
    cs = np.cumsum(obs, axis=0)
    cs = np.vstack([np.zeros((1, obs.shape[1]), np.int32), cs])    # cs[t] = sum over steps < t
    recent = (cs[test + 1] - cs[test + 1 - recent_steps]) == recent_steps
    target_ok = np.isfinite(data.Y[test, h_idx, :])
    return recent & target_ok


def select_alert_points(data, P: np.ndarray, test: np.ndarray, h_idx: int, n_alerts: int, rng) -> tuple[list, dict]:
    """Half of the points are the largest predicted speed drops (relative to the link's train mean, one per
    link) among eligible pairs; the rest are random eligible test pairs, for the global importance average."""
    elig = eligible_alert_mask(data, test, h_idx)
    drop = (data.mu[None, :] - P[:, h_idx, :]) / data.mu[None, :]
    drop = np.where(elig, drop, np.nan)
    flat = np.argsort(-np.nan_to_num(drop, nan=-np.inf).ravel())
    alerts, seen = [], set()
    for f in flat:
        k, n = divmod(int(f), P.shape[2])
        if not np.isfinite(drop[k, n]):
            break
        if n in seen:
            continue
        seen.add(n)
        alerts.append((int(test[k]), n))
        if len(alerts) >= n_alerts // 2:
            break
    cand = np.argwhere(elig)
    for _ in range(min(n_alerts - len(alerts), len(cand))):
        k, n = cand[rng.integers(0, len(cand))]
        alerts.append((int(test[k]), int(n)))
    info = {"rule": f"raw speed observed at all last {RECENT_STEPS} input steps and observed target at the "
                    f"explained horizon; top drops one per link, then random eligible pairs",
            "n_test_pairs": int(elig.size), "n_eligible_pairs": int(elig.sum()),
            "links_with_eligible_pairs": int((elig.sum(axis=0) > 0).sum()),
            "n_top_drop": sum(1 for _ in alerts[: n_alerts // 2]), "n_random": max(0, len(alerts) - n_alerts // 2)}
    return alerts, info


def run(model, data, results: list[dict], predict_fn, cal: dict | None, n_alerts: int = 12, seed: int = 42) -> dict:
    out_dir = settings.ROOT / "artifacts" / "explanations"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    test = data.origins["test"]
    prop = next(r for r in results if r["info"]["model"] == "proposed")
    P = prop["preds"]["test"]
    h_idx = 1 if len(data.horizon_minutes) > 1 else 0
    alerts, sel_info = select_alert_points(data, P, test, h_idx, n_alerts, rng)
    local = [explain_alert(model, data, o, n, h_idx, seed=seed) for o, n in alerts]
    names = local[0]["players"] if local else []
    glob: dict = {}
    for e in local:
        for k2, v in e["group_contributions"].items():
            glob.setdefault(k2, []).append(abs(v))
    global_imp = {k2: float(np.mean(v)) for k2, v in glob.items()}
    sub = test[:: max(1, len(test) // 600)]
    nb_rows = neighbour_removal(model, data, sub, predict_fn)
    tw_rows = temporal_window_sensitivity(model, data, sub, predict_fn)
    trees_out = [tree_shap_global(r, data) for r in results if r["info"]["model"] in ("lightgbm", "xgboost")]
    summary = {"model_run_id": prop["info"]["run_id"], "explained_model": "proposed (context-gated GATv2-Transformer)",
               "local_alerts": local, "global_grouped_mean_abs_shap_mph": global_imp,
               "global_note": f"mean |SHAP| over {len(local)} explained test points (half top-alert, half random)",
               "alert_selection": sel_info,
               "neighbour_removal": nb_rows, "temporal_window": tw_rows, "tree_baseline_shap": trees_out,
               "players": names}
    write_json(out_dir / "explanations_summary.json", summary)
    for name, rows in (("neighbour_removal.csv", nb_rows), ("temporal_window_sensitivity.csv", tw_rows)):
        if rows:
            with open(out_dir / name, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    return summary
