"""Generate LaTeX tables for the IEEE paper directly from the result CSVs (paper/tables/*.tex)."""

from __future__ import annotations

import csv
import json

from smartcity import settings

R = settings.ROOT
T = R / "paper" / "tables"


def _rows(p):
    p = R / p
    if not p.exists():
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def _f(x, nd=2):
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return "--"


def _esc(s: str) -> str:
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")


def _write(name: str, body: str):
    T.mkdir(parents=True, exist_ok=True)
    (T / name).write_text(body)


def not_run(caption: str, label: str) -> str:
    return (f"\\begin{{table}}[t]\\centering\\caption{{{caption}}}\\label{{{label}}}\n"
            "\\begin{tabular}{c}\\toprule NOT RUN \\\\ \\bottomrule\\end{tabular}\\end{table}\n")


def forecast_table():
    rows = [r for r in _rows("reports/experiments/forecast_metrics.csv") if r["track"] == "operational"]
    cap = "Test-partition forecast error (mph) by model and horizon, operational feature track"
    if not rows:
        return _write("forecast.tex", not_run(cap, "tab:forecast"))
    latest = {}
    for r in rows:
        latest[(r["model"], r["horizon_min"])] = r
    models = list(dict.fromkeys(r["model"] for r in rows))
    hs = sorted({int(r["horizon_min"]) for r in rows})
    lines = [f"\\begin{{table*}}[t]\\centering\\caption{{{cap}. Period {_esc(rows[0]['evaluation_period_utc'])} UTC; "
             f"identical valid-target mask for all models (n per horizon shown).}}\\label{{tab:forecast}}",
             "\\begin{tabular}{l" + "rr" * len(hs) + "}\\toprule",
             "Model & " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{h} min}}" for h in hs) + " \\\\",
             " & " + " & ".join("MAE & RMSE" for _ in hs) + " \\\\ \\midrule"]
    for m in models:
        cells = []
        for h in hs:
            r = latest.get((m, str(h)))
            cells += [_f(r["mae_mph"]) if r else "--", _f(r["rmse_mph"]) if r else "--"]
        lines.append(_esc(m) + " & " + " & ".join(cells) + " \\\\")
    ns = [latest[(models[0], str(h))]["n_valid_targets"] for h in hs]
    lines.append("\\midrule n & " + " & ".join(f"\\multicolumn{{2}}{{c}}{{{n}}}" for n in ns) + " \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table*}\n")
    _write("forecast.tex", "\n".join(lines))


def ablation_table():
    rows = _rows("reports/experiments/ablation_metrics.csv")
    cap = "Ablations of the proposed model (test MAE, mph, mean over horizons)"
    if not rows:
        return _write("ablation.tex", not_run(cap, "tab:ablation"))
    lines = [f"\\begin{{table}}[t]\\centering\\caption{{{cap}}}\\label{{tab:ablation}}",
             "\\begin{tabular}{lrrl}\\toprule Variant & MAE & $\\Delta$ & Status \\\\ \\midrule"]
    for r in rows:
        lines.append(f"{_esc(r['variant'])} & {_f(r.get('mae_mean_mph'))} & {_f(r.get('delta_vs_proposed_mph'))} & "
                     f"{_esc(r.get('status', ''))} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table}\n")
    _write("ablation.tex", "\n".join(lines))


def multi_seed_table():
    rows = _rows("reports/experiments/multi_seed_summary.csv")
    cap = "Deep forecasters over seeds: test MAE (mph), mean $\\pm$ s.d. [min, max] over seeds, and the paired day-block bootstrap of the seed-averaged MAE difference to the proposed model (95\\% interval; positive: proposed lower)"
    if not rows:
        return _write("multi_seed.tex", not_run(cap, "tab:multiseed"))
    hs = [h for h in (15, 30, 60) if f"mae_{h}m_mean" in rows[0]]
    seeds = rows[0]["seeds"].replace(";", ", ")
    lines = [f"\\begin{{table*}}[t]\\centering\\caption{{{cap}. Seeds {seeds}; same GPU, data, budget and code for every run; "
             f"period {_esc(rows[0]['evaluation_period_utc'])} UTC; n = {rows[0]['n_valid_targets_60m']} valid 60-min targets.}}"
             "\\label{tab:multiseed}",
             "\\begin{tabular}{l" + "l" * len(hs) + "}\\toprule",
             "Model & " + " & ".join(f"{h} min" for h in hs) + " \\\\ \\midrule"]
    order = sorted(rows, key=lambda r: (r["model"] != "proposed", r["model"]))
    for r in order:
        cells = [f"{_f(r[f'mae_{h}m_mean'], 3)} $\\pm$ {_f(r.get(f'mae_{h}m_sd'), 3)} "
                 f"[{_f(r[f'mae_{h}m_min'], 3)}, {_f(r[f'mae_{h}m_max'], 3)}]" for h in hs]
        lines.append(f"{_esc(r['model'])} ({r['n_seeds']} seeds) & " + " & ".join(cells) + " \\\\")
        if r.get(f"diff_vs_proposed_{hs[0]}m") not in (None, ""):
            diffs = []
            for h in hs:
                lo_hi = r.get(f"diff_vs_proposed_{h}m_ci95", "").strip("[]").split(",")
                ci = f"[{float(lo_hi[0]):+.3f}, {float(lo_hi[1]):+.3f}]" if len(lo_hi) == 2 else ""
                diffs.append(f"$\\Delta$ {float(r[f'diff_vs_proposed_{h}m']):+.3f} {ci}")
            lines.append("\\quad minus proposed & " + " & ".join(diffs) + " \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table*}\n")
    _write("multi_seed.tex", "\n".join(lines))


def uncertainty_table():
    rows = [r for r in _rows("reports/experiments/uncertainty_metrics.csv") if r["group"] == "all"]
    cap = "Split-conformal intervals: empirical test coverage (nominal 90\\%) and width"
    if not rows:
        return _write("uncertainty.tex", not_run(cap, "tab:unc"))
    lines = [f"\\begin{{table}}[t]\\centering\\caption{{{cap}}}\\label{{tab:unc}}",
             "\\begin{tabular}{rrrr}\\toprule Horizon & n & Coverage & Width (mph) \\\\ \\midrule"]
    for r in rows:
        lines.append(f"{r['horizon_min']} min & {r['n']} & {_f(r['empirical_coverage'], 3)} & {_f(r['mean_width_mph'])} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table}\n")
    _write("uncertainty.tex", "\n".join(lines))


def simulation_table():
    rows = _rows("reports/experiments/simulation_metrics.csv")
    cap = "SUMO testbed (SIMULATION): mean over completed matched seeds"
    if not rows:
        return _write("simulation.tex", not_run(cap, "tab:sim"))
    if "route_choice" not in rows[0]:  # the 2026-10-20 runs predate the route-choice column: bare from/to flows
        cap = ("SUPERSEDED 2026-10-20 controller comparison (SIMULATION), kept as recorded: bare from/to flows that SUMO "
               "routes at insertion on current travel times, the northbound flow inserted on a 0.2\\,m stub edge, declared "
               "demand. The testbed audit (Table~\\ref{tab:simaudit}) shows that this design sent about half of the "
               "mainline off West Street, so the table is not a corridor controller comparison. Mean over matched seeds")
    agg: dict = {}
    for r in rows:
        if r["status"] != "OK":
            continue
        k = (r["scenario"], r["controller"])
        agg.setdefault(k, []).append(r)
    timing = {r["controller"]: r.get("signal_timing", "") for r in rows}
    if any(t.startswith("calibrated_splits") for t in timing.values()):
        uncal = sorted(c for c, t in timing.items() if not t.startswith("calibrated_splits"))
        testbed = ("Calibrated scenario testbed (protocol v6 plan: 90\\,s common cycle, corridor green factor 1.5, 25\\,mph "
                   "southbound offsets, tuned to one observed speed on one link; not NYC DOT timing), OSM geometry, 2025 "
                   "two-direction counts, no side-street demand. The fixed-time and forecast-rule rows share this plan, "
                   "network and seeds and are the matched pair"
                   + (f"; the {', '.join(_esc(c) for c in uncal)} controller runs on netconvert's own actuated programs, not on "
                      "the calibrated plan, and is an uncalibrated reference, not ranked" if uncal else "") + ". ")
    else:
        testbed = "Scenario-based testbed with OSM geometry and declared demand, not a calibrated digital twin. "
    head = ("\\begin{table*}[t]\\centering\\caption{" + cap + ". " + testbed + "Time loss is the mean per \\emph{completed} trip; completed, "
            "unfinished and teleported vehicles are per run, averaged over seeds, so a lower time loss with fewer completed trips is "
            "survivorship, not improvement.}\\label{tab:sim}")
    lines = [head,
             "\\begin{tabular}{llrrrrrrrr}\\toprule Scenario & Controller & Seeds & Loaded & Completed & Unfinished & "
             "Teleports & Time loss (s) & Corridor TL (s) & Side TL (s) \\\\ \\midrule"]

    def mean(rs, k):
        v = [float(x[k]) for x in rs if x.get(k) not in (None, "", "None")]
        return sum(v) / len(v) if v else None
    for (s, c), rs in sorted(agg.items()):
        lines.append(f"{_esc(s)} & {_esc(c)} & {len(rs)} & {_f(mean(rs, 'loaded'), 0)} & {_f(mean(rs, 'completed_trips'), 0)} & "
                     f"{_f(mean(rs, 'unfinished_trips'), 0)} & {_f(mean(rs, 'teleports'), 0)} & "
                     f"{_f(mean(rs, 'mean_time_loss_s'), 1)} & {_f(mean(rs, 'corridor_mean_time_loss_s'), 1)} & "
                     f"{_f(mean(rs, 'side_road_mean_time_loss_s'), 1)} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table*}\n")
    _write("simulation.tex", "\n".join(lines))


def simulation_audit_table():
    """Testbed audit: route choice at the declared demand, and the preregistered side-demand selection per
    signal-timing protocol (netconvert programs; Webster re-timed programs)."""
    cap = "SUMO testbed audit (SIMULATION)"
    audit_p = R / "reports" / "experiments" / "simulation_testbed_audit.json"
    protocols = [("netconvert_guess", "2014 count, netconvert programs"), ("webster_retimed", "2014 count, Webster programs"),
                 ("v4_counts2025_webster_noturnlanes", "2025 counts, no OSM turn-lane restrictions, Webster programs")]
    sweeps = {m: _rows(f"reports/experiments/simulation_demand_selection_{m}.csv") for m, _ in protocols}
    if not any(sweeps.values()) or not audit_p.exists():
        return _write("simulation_audit.tex", not_run(cap, "tab:simaudit"))
    ra = json.loads(audit_p.read_text())["route_choice_audit"]
    chosen = {}
    for m, _ in protocols:
        sp = R / "simulation" / "scenarios" / f"demand_selection_{m}.json"
        chosen[m] = json.loads(sp.read_text()).get("selected_side_demand_scale") if sp.exists() else "NOT RUN"
    picked = "; ".join(f"{lbl}: {'none' if chosen[m] is None else chosen[m]}" for m, lbl in protocols)
    head = ("\\begin{table}[t]\\centering\\caption{" + cap + ". Top: routine peak at the 2026-10-20 declared demand ("
            f"{ra['demand']['main_veh_per_hour_per_direction']}/{ra['demand']['side_veh_per_hour_per_approach']} veh/h "
            "per direction/side approach), netconvert programs, seed 1. Below: preregistered side-demand selection on the "
            "routine peak, fixed-time only, observed mainline demand (2014 ATR count: 1,389 veh/h per direction; 2025 "
            "classification counts: 2,510 NB / 2,444 SB veh/h), three development seeds, mean per run; a level "
            "is admissible only with no teleport and at most 1\\,\\% unfinished in every seed. Selected level: "
            f"{_esc(picked)}." + "}\\label{tab:simaudit}\\small")
    lines = [head, "\\resizebox{\\columnwidth}{!}{%",
             "\\begin{tabular}{lrrrr}\\toprule Route choice & Inserted & Teleports & Re-routed & Main off West St \\\\ \\midrule"]
    for mode in ("dynamic_insertion", "fixed_free_flow"):
        a = ra[mode]
        lines.append(f"{_esc(mode)} & {a['inserted']} & {a['teleports']['total']} & {sum(a['route_replacements'].values())} & "
                     f"{a['mainline_routes_leaving_west_street']}/{a['mainline_vehicles']} \\\\")

    def mean(rs, k):
        v = [float(x[k]) for x in rs if x.get(k) not in (None, "", "None")]
        return sum(v) / len(v) if v else None
    for m, lbl in protocols:
        if not sweeps[m]:
            continue
        lines.append(f"\\midrule \\multicolumn{{5}}{{l}}{{\\emph{{{lbl}}}}} \\\\")
        lines.append("Side (veh/h/approach) & Loaded & Unfinished & Teleports & Time loss (s) \\\\ \\midrule")
        by: dict = {}
        for r in sweeps[m]:
            by.setdefault(float(r["side_vph_per_approach"]), []).append(r)
        for side in sorted(by, reverse=True):
            rs = by[side]
            lines.append(f"{_f(side, 1)} & {_f(mean(rs, 'loaded'), 0)} & {_f(mean(rs, 'unfinished_trips'), 0)} & "
                         f"{_f(mean(rs, 'teleports'), 0)} & {_f(mean(rs, 'mean_time_loss_s'), 1)} \\\\")
    lines.append("\\bottomrule\\end{tabular}}\\end{table}\n")
    _write("simulation_audit.tex", "\n".join(lines))


def split_calibration_table():
    """Protocol v5 signal-split calibration: one row per preregistered green factor (fixed-time baseline, development
    seeds, no side demand), the simulated space-mean speed on the mapped DOT link, admissibility and the selection."""
    cap = "SUMO signal-split calibration, protocol v5 (SIMULATION)"
    rec_p = R / "simulation" / "scenarios" / "split_calibration_v5_counts2025_calibrated_splits.json"
    if not rec_p.exists():
        return _write("split_calibration.tex", not_run(cap, "tab:splitcal"))
    rec = json.loads(rec_p.read_text())
    rule = rec["rule"]
    sel = rec.get("selected_green_factor")
    picked = (f"selected factor {sel}" if sel is not None
              else f"no factor selected: {_esc(rec.get('reason', 'no admissible factor within tolerance'))}")
    head = ("\\begin{table}[t]\\centering\\caption{" + cap + ". Corridor green share of the Webster plan scaled by a "
            "factor from a grid fixed before the run (cycle at most "
            f"{_f(rule.get('max_cycle_s'), 0)}\\,s, phase states unchanged), fixed-time baseline, seeds "
            f"{', '.join(str(x) for x in rule.get('seeds', []))}, no side-street demand, 2025 counts. Speed is the "
            f"seed-mean space-mean speed on the SUMO edges mapped to DOT link {rule['dot_link_id']}; target "
            f"{_f(rule['target_speed_mph'])}\\,mph $\\pm$ {_f(rule['tolerance_mph'], 1)} (observed weekday PM peak). A factor is "
            "admissible with no teleport and at most 1\\,\\% unfinished trips in every seed. Outcome: "
            + picked + ".}\\label{tab:splitcal}\\small")
    lines = [head, "\\begin{tabular}{rrrrrc}\\toprule Green factor & Speed (mph) & Gap (mph) & Unfinished per seed & "
                   "Max cycle (s) & Admissible \\\\ \\midrule"]
    for v in rec["per_factor"]:
        per = v["program"]["per_tls"]
        unf = "/".join(str(int(u)) for u in v["unfinished_trips"])
        gap = v["speed_mean_mph"] - rule["target_speed_mph"]
        lines.append(f"{_f(v['green_factor'], 1)} & {_f(v['speed_mean_mph'])} & {gap:+.2f} & {unf} & "
                     f"{_f(max(x['cycle_after_s'] for x in per.values()), 0)} & {'yes' if v['admissible'] else 'no'} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table}\n")
    _write("split_calibration.tex", "\n".join(lines))


def split_calibration_v6_table():
    """Protocol v6 signal-timing calibration (common cycle x corridor-green factor x 25 mph offsets): one row per grid
    cell, fixed-time baseline, development seeds, no side demand; NOT RUN placeholder until the workstation runs it."""
    cap = "SUMO signal-timing calibration, protocol v6 (SIMULATION)"
    rec_p = R / "simulation" / "scenarios" / "split_calibration_v6_counts2025_cycle_splits_offsets.json"
    if not rec_p.exists():
        return _write("split_calibration_v6.tex", not_run(cap, "tab:splitcal6"))
    rec = json.loads(rec_p.read_text())
    rule = rec["rule"]
    sel = rec.get("selected_cell")
    picked = (f"selected cell: factor {_f(sel['green_factor'], 1)}, "
              + (f"{_f(sel['common_cycle_s'], 0)}\\,s common cycle" if sel.get("common_cycle_s") else "Webster cycles")
              + (f", {_f(sel['progression_speed_mph'], 0)}\\,mph offsets" if sel.get("progression_speed_mph") else "")
              if sel else f"no cell selected: {_esc(rec.get('reason', 'no admissible cell within tolerance'))}")
    head = ("\\begin{table}[t]\\centering\\caption{" + cap + ". Grid fixed before the run: every corridor signal on the "
            "per-signal Webster cycles or on a common cycle, corridor green scaled by a factor within the cycle (phase states "
            "unchanged, greens at least 7\\,s, corridor green at most 90\\,s) and, with a common cycle, offsets for a 25\\,mph "
            f"platoon along the {_esc(rec.get('progression_direction', ''))} chain. Fixed-time baseline, seeds "
            f"{', '.join(str(x) for x in rule.get('seeds', []))}, no side-street demand, 2025 counts. Speed is the seed-mean "
            f"space-mean speed on the SUMO edges mapped to DOT link {rule['dot_link_id']}; target {_f(rule['target_speed_mph'])}\\,mph "
            f"$\\pm$ {_f(rule['tolerance_mph'], 1)}. A cell is admissible with no teleport and at most 1\\,\\% unfinished trips in "
            "every seed. Outcome: " + picked + ".}\\label{tab:splitcal6}\\small")
    lines = [head, "\\begin{tabular}{rrrrrrc}\\toprule Cycle (s) & Green factor & Offsets & Speed (mph) & Gap (mph) & "
                   "Unfinished per seed & Admissible \\\\ \\midrule"]
    for v in rec["per_factor"]:
        unf = "/".join(str(int(u)) for u in v["unfinished_trips"])
        sp = v.get("speed_mean_mph")
        gap = f"{sp - rule['target_speed_mph']:+.2f}" if sp is not None else "--"
        cyc = _f(v["common_cycle_s"], 0) if v.get("common_cycle_s") else "Webster"
        prog = f"{_f(v['progression_speed_mph'], 0)}\\,mph" if v.get("progression_speed_mph") else "none"
        lines.append(f"{cyc} & {_f(v['green_factor'], 1)} & {prog} & {_f(sp)} & {gap} & {unf} & "
                     f"{'yes' if v['admissible'] else 'no'} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table}\n")
    _write("split_calibration_v6.tex", "\n".join(lines))


def live_table():
    """LIVE observational run: per-horizon error, coverage and persistence of forecasts made from records pulled after
    training and scored once their targets were observed; NOT RUN placeholder until the workstation runs it."""
    cap = "Live observational run (LIVE)"
    summ_p = R / "artifacts" / "live" / "live_summary.json"
    rows = _rows("reports/experiments/live_metrics.csv")
    if not summ_p.exists() or not rows:
        return _write("live.tex", not_run(cap, "tab:live"))
    summ = json.loads(summ_p.read_text())
    if not summ.get("n_scored"):
        return _write("live.tex", not_run(cap + " (forecasts saved, no target observed yet)", "tab:live"))
    la = "latest_available" in (summ.get("origin_modes") or [])
    origin_txt = ("the origin of each batch was the newest bin the feed had published, on average "
                  f"{_f(summ.get('mean_origin_lag_minutes'), 0)}\\,min (at most {_f(summ.get('max_origin_lag_minutes'), 0)}\\,min) "
                  "old when the forecast was written (latest-available protocol preregistered on 29 October 2026); every "
                  "forecast was written before its target bin was published and scored only when that bin was first "
                  f"retrieved afterwards ({summ.get('n_published_before_issue', 0)} rows excluded as published before issue; "
                  f"{summ.get('n_scored_target_in_past_at_issue', 0)} scored targets already lay in the past on the wall clock)"
                  if la else
                  "every forecast was written before its target time and scored only after the target bin was observed")
    head = ("\\begin{table}[t]\\centering\\caption{" + cap + ". The frozen model was run on records pulled from the public "
            f"speed feed between {_esc(summ['first_origin_utc'][:16])} and {_esc(summ['last_origin_utc'][:16])} UTC "
            f"({summ['n_batches']} five-minute batches, {summ['n_links']} links); {origin_txt}. Persistence is the last "
            f"observed speed at the origin. Pending targets ({summ.get('n_pending', 0)}) and late forecasts "
            f"({summ.get('n_late', 0)}) are not scored. A short window on one weekday, not a second test set.}}"
            "\\label{tab:live}\\small")
    lines = [head, "\\begin{tabular}{rrrrrr}\\toprule Horizon (min) & Scored & MAE (mph) & Persistence MAE & "
                   "Coverage & Width (mph) \\\\ \\midrule"]
    for r in rows:
        lines.append(f"{r['horizon_minutes']} & {r['n_scored']} & {_f(r['mae_mph'])} & {_f(r['persistence_mae_mph'])} & "
                     f"{_f(r['coverage'], 3)} & {_f(r['mean_interval_width_mph'], 1)} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table}\n")
    _write("live.tex", "\n".join(lines))


def retrieval_table():
    p = R / "artifacts" / "retrieval" / "retrieval_eval.json"
    cap = "Retrieval evaluation on the labelled query set"
    if not p.exists():
        return _write("retrieval.tex", not_run(cap, "tab:ret"))
    s = json.loads(p.read_text())["summary"]
    k = s["k"]
    body = (f"\\begin{{table}}[t]\\centering\\caption{{{cap} (labels drafted by the project; review status: "
            f"{_esc(', '.join(s['label_review_status']))})}}\\label{{tab:ret}}\n\\begin{{tabular}}{{lr}}\\toprule\n"
            f"Queries & {s['n_queries']} \\\\ Recall@{k} & {_f(s.get(f'mean_recall@{k}'), 3)} \\\\ MRR & {_f(s.get('mrr'), 3)} \\\\ "
            f"Support-status accuracy & {_f(s['status_accuracy'], 3)} \\\\ \\bottomrule\\end{{tabular}}\\end{{table}}\n")
    _write("retrieval.tex", body)


def advisory_table():
    rows = _rows("reports/experiments/advisory_metrics.csv")
    cap = "Advisory workflow outcomes by policy (REPLAY cases; simulation-only effects)"
    if not rows:
        return _write("advisory.tex", not_run(cap, "tab:adv"))
    lines = [f"\\begin{{table*}}[t]\\centering\\caption{{{cap}}}\\label{{tab:adv}}",
             "\\begin{tabular}{llllrr}\\toprule Policy & Case & Decision & LLM & Invalid cit. & Constraint viol. \\\\ \\midrule"]
    for r in rows:
        lines.append(f"{_esc(r['policy'])} & {_esc(r['case'])} & {_esc(r.get('decision', ''))} & {_esc(r.get('llm_status') or '--')} & "
                     f"{r.get('n_invalid_citations') or '--'} & {r.get('constraint_violations') or '--'} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table*}\n")
    _write("advisory.tex", "\n".join(lines))


def sources_table():
    rows = _rows("reports/data_audit/source_inventory.csv")
    cap = "Verified public data sources (server-side audit)"
    if not rows:
        return _write("sources.tex", not_run(cap, "tab:sources"))
    lines = [f"\\begin{{table*}}[t]\\centering\\caption{{{cap}}}\\label{{tab:sources}}\\small",
             "\\begin{tabular}{lllrl}\\toprule Source & Dataset & Observed range & Records & Role/limitation \\\\ \\midrule"]
    for r in rows:
        rng = f"{(r.get('observation_min') or '')[:10]} -- {(r.get('observation_max') or '')[:10]}"
        lines.append(f"{_esc(r['source_id'])} & {_esc(r.get('dataset_id') or '')} & {rng} & {r.get('record_count') or '--'} & "
                     f"{_esc((r.get('limitations') or '')[:70])} \\\\")
    lines.append("\\bottomrule\\end{tabular}\\end{table*}\n")
    _write("sources.tex", "\n".join(lines))


def sync() -> str:
    for fn in (forecast_table, multi_seed_table, ablation_table, uncertainty_table, simulation_table, simulation_audit_table,
               split_calibration_table, split_calibration_v6_table, live_table,
               retrieval_table, advisory_table, sources_table):
        fn()
    return "tables: " + ", ".join(sorted(p.name for p in T.glob("*.tex")))
