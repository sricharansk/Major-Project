"""Signal-split calibration of the SUMO testbed: a calibrated scenario testbed, not a digital twin.

NYC DOT publishes no phase timings for the West Street signals, and the Webster programs re-timed for the declared
demand leave the corridor far slower than observed (5.8 mph simulated against 10.95 mph measured on DOT link 4456494
in the weekday PM peak, protocol v4). The protocol here is fixed in ``configs/simulation.yaml`` (``split_calibration``)
before any run and does not touch the preregistered admissibility rule:

1. Start from the Webster programs re-timed for the routine peak with no side-street demand (the same base the v4
   speed validation used).
2. Multiply the corridor green of every corridor signal by a factor from the grid; keep the cycle by shortening the
   other green phases down to ``min_green_s``, let the cycle grow up to ``max_cycle_s`` only when that is not enough,
   and never let a corridor green exceed ``max_green_s``. Phase order and states never change.
3. Run every factor under the fixed-time baseline on the development seeds. A factor is admissible only when every
   seed passes the preregistered rule (``demand_selection.max_teleports`` and ``max_unfinished_frac``).
4. Among admissible factors select the one whose seed-mean space-mean speed on the mapped DOT link is closest to the
   observed PM-peak speed, provided the gap is within ``tolerance_mph``; otherwise nothing is selected and the
   comparison stays NOT RUN.

The selected program replaces the Webster plan as the fixed-time baseline (and the plan the forecast rule and
candidates act on); the side-demand level is then re-selected under it by the preregistered rule.
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from smartcity import settings
from smartcity.simulation import pipeline as p
from smartcity.simulation import sumo_runner as sr
from smartcity.utils import read_json, utcnow_iso, write_json

MPH_PER_MPS = 2.236936


def _is_green(state: str) -> bool:
    return "y" not in state and ("G" in state or "g" in state)


def rescale_corridor_green(src: Path, dst: Path, corridor_phase: dict, factor: float, min_green: float,
                           max_cycle: float, max_green: float) -> dict:
    """Multiply the corridor green phase of every corridor signal in a tlLogic additional file by ``factor``.

    The cycle is kept by shortening the other green phases proportionally to their slack above ``min_green``; when
    the slack is not enough the cycle grows up to ``max_cycle`` and the corridor green is capped so that neither
    ``max_cycle`` nor ``max_green`` is exceeded. Clearance phases (yellow, all-red) and phase states are untouched;
    signals that are not corridor signals are copied unchanged."""
    tree = ET.parse(src)
    per_tls = {}
    for tl in tree.getroot().iter("tlLogic"):
        tid = tl.get("id")
        if tid not in corridor_phase:
            continue
        phases = tl.findall("phase")
        ci = int(corridor_phase[tid])
        durs = [float(ph.get("duration")) for ph in phases]
        if not (0 <= ci < len(phases)) or not _is_green(phases[ci].get("state")):
            raise RuntimeError(f"{tid}: corridor phase {ci} is not a green phase of the program")
        cycle0, dc = sum(durs), durs[ci]
        others = [i for i, ph in enumerate(phases) if i != ci and _is_green(ph.get("state"))]
        slack = {i: max(durs[i] - min_green, 0.0) for i in others}
        reducible = sum(slack.values())
        new_c = min(dc * factor, max_green, dc + reducible + max(max_cycle - cycle0, 0.0))
        new_c = max(new_c, dc)
        cut = min(new_c - dc, reducible)
        new = list(durs)
        new[ci] = new_c
        for i in others:
            new[i] = durs[i] - (cut * slack[i] / reducible if reducible > 0 else 0.0)
        for ph, d in zip(phases, new):
            ph.set("duration", f"{d:.1f}")
            for k in ("minDur", "maxDur"):
                if ph.get(k) is not None:
                    ph.set(k, f"{d:.1f}")
        per_tls[tid] = {"cycle_before_s": round(cycle0, 1), "cycle_after_s": round(sum(new), 1),
                        "corridor_green_before_s": round(dc, 1), "corridor_green_after_s": round(new_c, 1),
                        "capped": bool(new_c + 1e-9 < dc * factor)}
    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    rel = str(dst.relative_to(settings.ROOT)) if dst.is_relative_to(settings.ROOT) else str(dst)
    return {"method": "calibrated_splits", "green_factor": factor, "tls_additional": rel, "sha16": sr.file_hash(dst),
            "min_green_s": min_green, "max_green_s": max_green, "max_cycle_s": max_cycle, "per_tls": per_tls}


def space_mean_speed_mph(lengths: dict[str, float], edge_speeds: dict[str, float]) -> float | None:
    """Length-weighted space-mean speed over a chain of edges from per-edge mean speeds (m/s); None if no edge has
    data."""
    have = [e for e in lengths if e in edge_speeds]
    if not have:
        return None
    length = sum(lengths[e] for e in have)
    ttime = sum(lengths[e] / max(float(edge_speeds[e]), 0.01) for e in have)
    return round(length / ttime * MPH_PER_MPS, 2)


def link_speed_from_edgedata(net_file: Path, edgedata_xml: Path, edges: list[str]) -> dict:
    """Space-mean speed of a mapped DOT link in the evaluation window from a SUMO edgeData output."""
    import sumolib

    net = sumolib.net.readNet(str(net_file))
    lengths = {e: net.getEdge(e).getLength() for e in edges}
    if not edgedata_xml.exists():
        return {"space_mean_speed_mph": None, "edges_with_data": 0, "length_m": round(sum(lengths.values()), 1)}
    ed = {e.get("id"): float(e.get("speed")) for e in ET.parse(edgedata_xml).getroot().iter("edge") if e.get("speed")}
    return {"space_mean_speed_mph": space_mean_speed_mph(lengths, ed), "edges_with_data": sum(e in ed for e in edges),
            "length_m": round(sum(lengths.values()), 1)}


def choose_factor(per_factor: list[dict], target_mph: float, tolerance_mph: float) -> dict:
    """Preregistered choice: the admissible factor whose seed-mean speed is closest to the target (smallest factor on
    a tie), provided the gap is within tolerance; otherwise nothing is selected."""
    ok = [f for f in per_factor if f.get("admissible") and f.get("speed_mean_mph") is not None]
    if not ok:
        return {"selected_green_factor": None, "selected_speed_mph": None, "speed_gap_mph": None,
                "reason": "no green factor passes the preregistered admissibility rule on every seed"}
    best = min(ok, key=lambda f: (abs(f["speed_mean_mph"] - target_mph), f["green_factor"]))
    gap = round(best["speed_mean_mph"] - target_mph, 2)
    if abs(gap) > tolerance_mph:
        return {"selected_green_factor": None, "selected_speed_mph": best["speed_mean_mph"], "speed_gap_mph": gap,
                "reason": f"closest admissible factor {best['green_factor']} gives {best['speed_mean_mph']} mph, "
                          f"{gap:+.2f} mph from the target, beyond the {tolerance_mph} mph tolerance"}
    return {"selected_green_factor": best["green_factor"], "selected_speed_mph": best["speed_mean_mph"],
            "speed_gap_mph": gap, "reason": "closest admissible factor within tolerance"}


def mapped_edges(link_id: str) -> list[str]:
    with open(settings.ROOT / "simulation" / "mappings" / "dot_to_sumo.csv") as fh:
        for r in csv.DictReader(fh):
            if r["dot_link_id"] == link_id and r["mapping_confidence"] == "high":
                return r["sumo_edge_id"].split(";")
    raise SystemExit(f"NOT_RUN: DOT link {link_id} has no high-confidence SUMO mapping")


def calibrate_splits() -> dict:
    scfg = settings.load("simulation")
    cal = scfg.get("split_calibration")
    if not cal:
        raise SystemExit("NOT_RUN: configs/simulation.yaml has no split_calibration block")
    if not scfg.get("demand_selection"):
        raise SystemExit("NOT_RUN: configs/simulation.yaml has no demand_selection block (the preregistered rule)")
    rule, sim = scfg["demand_selection"], scfg["simulation"]
    prep = p.SIM / "scenarios" / "prepared.json"
    meta = read_json(prep)
    label = cal["protocol_id"]
    edges = mapped_edges(str(cal["dot_link_id"]))
    net = settings.ROOT / meta["network"]["static"]
    routine = next(s for s in p.scenarios(meta) if s["name"] == "routine_peak")
    scen = {**routine, "name": "calib_side000", "side_demand_scale": float(cal.get("side_demand_scale", 0.0)),
            "description": "SPLIT CALIBRATION: routine peak, fixed-time baseline only, side demand as configured"}
    scen.pop("tls_additional", None)
    scen["demand"] = p.flow_demand(meta, scen)
    routes = p.build_routes(meta, scen)
    base = p.retime_signals(meta, routes, scen["name"], label)
    plans, jobs, outs = {}, [], []
    for f in cal["green_factors"]:
        f = float(f)
        out = p.SIM / "networks" / f"{p.CFG_NAME}.{label}.f{f:.2f}.add.xml"
        plans[f] = rescale_corridor_green(settings.ROOT / base["tls_additional"], out, meta["corridor_phase"], f,
                                          float(sim["min_green_s"]), float(cal.get("max_cycle_s", 120)),
                                          float(sim["max_green_s"]))
        for s in cal["seeds"]:
            ed_add = p.SIM / "demand" / f"{label}.f{f:.2f}.s{s}.edgedata.add.xml"
            ed_out = (p.SIM / "outputs" / f"{label}-edgedata-f{f:.2f}-s{s}.xml").resolve()
            t0, t1 = sim["warmup_s"], sim["warmup_s"] + sim["evaluation_s"]
            ed_add.write_text(f'<additional><edgeData id="ed" file="{ed_out}" begin="{t0}" end="{t1}" '
                              'excludeEmpty="true"/></additional>')
            sc = {**scen, "name": f"calib_f{round(100 * f):03d}", "tls_additional": plans[f]["tls_additional"],
                  "signal_timing_kind": "calibrated_splits", "green_factor": f,
                  "extra_additionals": [str(ed_add.relative_to(settings.ROOT))]}
            jobs.append((net, routes, sc, "fixed_time", s))
            outs.append((f, s, ed_out))
    rows = p.run_many(jobs)
    per_factor = []
    for f in plans:
        idx = [i for i, (ff, _, _) in enumerate(outs) if ff == f]
        rs = [rows[i] for i in idx]
        sp = [link_speed_from_edgedata(net, outs[i][2], edges) for i in idx]
        speeds = [x["space_mean_speed_mph"] for x in sp]
        valid = [v for v in speeds if v is not None]
        per_factor.append({"green_factor": f, "program": plans[f], "admissible": all(p.run_admissible(r, rule) for r in rs),
                           "run_ids": [r["run_id"] for r in rs], "status": [r["status"] for r in rs],
                           "teleports": [r["metrics"].get("teleports") for r in rs],
                           "unfinished_trips": [r["metrics"].get("unfinished_trips") for r in rs],
                           "loaded": [r["metrics"].get("loaded") for r in rs],
                           "completed_trips": [r["metrics"].get("completed_trips") for r in rs],
                           "speeds_mph": speeds, "speed_mean_mph": round(float(np.mean(valid)), 2) if valid else None})
    choice = choose_factor(per_factor, float(cal["target_speed_mph"]), float(cal["tolerance_mph"]))
    rep = {"generated_at": utcnow_iso(), "protocol_id": label,
           "mode": "SIMULATION (testbed split calibration, not a controller comparison)",
           "sumo_version": sr.sumo_version(), "rule": {**cal, "max_teleports": rule["max_teleports"],
                                                      "max_unfinished_frac": rule["max_unfinished_frac"]},
           "base_program": base, "dot_link_id": str(cal["dot_link_id"]), "sumo_edges": edges,
           "network_static_content_sha256": meta["network"].get("static_content_sha256"),
           "demand_source": meta["demand"].get("source"), "demand": scen["demand"], "per_factor": per_factor, **choice,
           "note": "a calibrated scenario testbed (corridor green share tuned to the observed speed), not NYC DOT timing"}
    write_json(p.SIM / "scenarios" / f"split_calibration_{label}.json", rep)
    p.export_sim_rows(rows, settings.ROOT / "reports" / "experiments" / f"simulation_split_calibration_{label}.csv")
    f = choice["selected_green_factor"]
    if f is not None:
        meta["signal_timing"] = {**plans[f], "base_program": base,
                                 "calibration": f"simulation/scenarios/split_calibration_{label}.json",
                                 "note": "calibrated scenario testbed, not NYC DOT timing plans"}
        meta["tls_inventory_active"] = p.retimed_inventory(meta, plans[f]["tls_additional"])
        for k in ("side_demand_scale", "side_demand_selection"):  # must be re-selected under the new program
            meta["demand"].pop(k, None)
    elif (meta.get("signal_timing") or {}).get("method") == "calibrated_splits":
        # a program calibrated by an earlier run must not survive a run that selects nothing
        meta.pop("signal_timing", None)
        meta.pop("tls_inventory_active", None)
        for k in ("side_demand_scale", "side_demand_selection"):
            meta["demand"].pop(k, None)
    write_json(prep, meta)
    return rep
