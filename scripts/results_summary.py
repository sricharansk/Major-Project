"""Print a compact, factual summary of every result artifact that exists (nothing is computed or extrapolated).

Used to write the paper's results narrative from the real artifacts.  Missing files are reported as MISSING.

    python scripts/results_summary.py
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "reports" / "experiments"


def rows(path: Path) -> list[dict]:
    if not path.exists():
        print(f"MISSING {path.relative_to(ROOT)}")
        return []
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def forecast(track: str) -> None:
    rs = [r for r in rows(EXP / "forecast_metrics.csv") if r["track"] == track]
    if not rs:
        return
    latest = {(r["model"], int(r["horizon_min"])): r for r in rs}  # last row per (model, horizon) wins
    hs = sorted({int(r["horizon_min"]) for r in rs})
    print(f"\n== forecast_metrics ({track}) period {rs[0]['evaluation_period_utc']}")
    print("model".ljust(24) + "".join(f"{h:>3}m MAE/RMSE/sMAPE/R2        " for h in hs))
    for m in dict.fromkeys(r["model"] for r in rs):
        cells = []
        for h in hs:
            r = latest.get((m, h))
            cells.append(f"{float(r['mae_mph']):6.3f}/{float(r['rmse_mph']):6.3f}/{float(r['smape_pct']):5.1f}/{float(r['r2']):5.2f}   "
                         if r else " " * 29)
        print(m.ljust(24) + "".join(cells))
    n = {h: latest[(rs[0]["model"], h)]["n_valid_targets"] for h in hs}
    print(f"n valid targets per horizon: {n}")


def ablation() -> None:
    rs = rows(EXP / "ablation_metrics.csv")
    if rs:
        print("\n== ablation_metrics (mean MAE over horizons; delta vs proposed, day-block bootstrap 95% CI)")
        for r in rs:
            print(f"{r['variant']:28s} MAE={r['mae_mean_mph']:>8} delta={r['delta_vs_proposed_mph']:>8} "
                  f"CI=[{r['ci95_low']}, {r['ci95_high']}] days={r['n_days']} {r['status']}")


def uncertainty() -> None:
    rs = rows(EXP / "uncertainty_metrics.csv")
    if rs:
        print("\n== uncertainty_metrics")
        for r in rs:
            print(f"{r['model']:10s} h={r['horizon_min']:>3} group={r['group']:12s} n={r['n']:>7} nominal={r['nominal_coverage']} "
                  f"empirical={r['empirical_coverage']} width={r['mean_width_mph']}")


def link_support() -> None:
    for track in ("operational", "retrospective"):
        rs = rows(EXP / f"link_test_support_{track}.csv")
        if rs:
            ne = [r["link_id"] for r in rs if r["status"] != "EVALUATED"]
            print(f"\n== link_test_support ({track}): {len(rs)} links, NOT_EVALUATED: {ne or 'none'}")


def retrieval() -> None:
    p = ROOT / "artifacts" / "retrieval" / "retrieval_eval.json"
    if not p.exists():
        print(f"MISSING {p.relative_to(ROOT)}")
        return
    s = json.loads(p.read_text())["summary"]
    print("\n== retrieval_eval summary")
    for k, v in s.items():
        print(f"  {k}: {v}")


def simulation() -> None:
    rs = rows(EXP / "simulation_metrics.csv")
    if not rs:
        return
    print("\n== simulation_metrics (mean over completed seeds)")
    agg: dict = defaultdict(list)
    for r in rs:
        agg[(r["scenario"], r["controller"], r["status"])].append(r)
    metric_keys = [k for k in rs[0] if k not in ("run_id", "mode", "scenario", "controller", "seed", "status", "error",
                                                 "sumo_version", "network_hash", "demand_hash", "warmup_s",
                                                 "evaluation_s", "pedestrian_protection")]
    for (sc, ctl, st), group in sorted(agg.items()):
        means = {}
        for k in metric_keys:
            vals = [float(g[k]) for g in group if g.get(k) not in ("", None, "None")]
            if vals:
                means[k] = round(sum(vals) / len(vals), 3)
        print(f"{sc:18s} {ctl:16s} {st:8s} seeds={len(group)} {means}")


def advisory() -> None:
    rs = rows(EXP / "advisory_metrics.csv")
    if rs:
        print("\n== advisory_metrics")
        for r in rs:
            print(f"{r['policy']:14s} {r['case']:28s} decision={r.get('decision')} llm={r.get('llm_status')} "
                  f"attempts={r.get('llm_attempts')} cand={r.get('n_candidates')} invalid_cit={r.get('n_invalid_citations')} "
                  f"viol={r.get('constraint_violations')}/{r.get('candidates_checked')} sim={r.get('sim_delay_improvement_pct')} "
                  f"lat={r.get('latency_s')}s mode={r.get('mode')}")


def explanations() -> None:
    for p in sorted((ROOT / "artifacts").glob("**/explanations_summary.json")):
        s = json.loads(p.read_text())
        print(f"\n== explanations {p.relative_to(ROOT)}: {s.get('explained_model')} run {s.get('model_run_id')}")
        print(f"  global mean |SHAP| by group (mph): {s.get('global_grouped_mean_abs_shap_mph')}")
        print(f"  local alerts explained: {len(s.get('local_alerts', []))}; neighbour-removal rows: {len(s.get('neighbour_removal', []))}; "
              f"temporal-window rows: {len(s.get('temporal_window', []))}")


def runs() -> None:
    print("\n== run_info (deep models)")
    for p in sorted((ROOT / "artifacts").glob("**/run_info.json")):
        i = json.loads(p.read_text())
        if "epochs_run" in i:
            print(f"{i['model']:28s} epochs={i['epochs_run']:>2} best_ep={i['best_epoch']:>2} best_val_mae={i['best_val_mae']:.3f} "
                  f"train={i['train_time_s'] / 60:.1f}min dev={i.get('train_device')} stop={i.get('stopped_reason')} "
                  f"params={i['n_params']} lat={i.get('infer_latency_ms_per_origin')}")


def stages() -> None:
    p = ROOT / "reports" / "verification" / "stage_log.jsonl"
    if not p.exists():
        print(f"MISSING {p.relative_to(ROOT)}")
        return
    print("\n== stage_log (last record per stage)")
    last = {}
    for line in p.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            last[e["stage"]] = e
    for st, e in last.items():
        print(f"rc={e['returncode']} {e['wall_s']:>8.1f}s  {st}")


if __name__ == "__main__":
    for t in ("operational", "retrospective"):
        forecast(t)
    ablation()
    uncertainty()
    link_support()
    retrieval()
    simulation()
    advisory()
    explanations()
    runs()
    stages()
