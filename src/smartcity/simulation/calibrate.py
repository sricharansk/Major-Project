"""Signal-timing calibration of the SUMO testbed: a calibrated scenario testbed, not a digital twin.

NYC DOT publishes no phase timings for the West Street signals, and the Webster programs re-timed for the declared
demand leave the corridor far slower than observed (5.8 mph simulated against 10.95 mph measured on DOT link 4456494
in the weekday PM peak, protocol v4). Two calibration protocols are fixed in ``configs/simulation.yaml``
(``split_calibration``) before their runs; neither touches the preregistered admissibility rule.

Protocol v5 (run 2026-10-23, no program selected): the corridor green of every corridor signal in the Webster plan is
multiplied by a factor from a grid; the cycle is kept by shortening the other greens down to ``min_green_s``, grows up
to ``max_cycle_s`` only when that is not enough, and no corridor green exceeds ``max_green_s``. Speed rose from 5.82
to 8.10 mph at the largest factor, 2.85 mph short of the target, with one signal at the caps from factor 1.4 on.

Protocol v6 (this module, prepared 2026-10-25) keeps that construction and adds the two things an arterial timed for
progression has and the Webster plan lacks: a common cycle at every corridor signal (the Webster cycles range from
21 to 102 s, so no offset pattern can hold a platoon together) and corridor-green offsets for a platoon travelling
at the posted progression speed along the mapped link's direction. The grid is fixed in the configuration:

1. ``common_cycles_s``: ``null`` keeps the per-signal Webster cycles (the v5 base); a number puts every corridor
   signal on that cycle by scaling its green phases together (clearance phases, phase order and states unchanged,
   greens floored at ``min_green_s``).
2. ``green_factors``: the corridor green is then multiplied by the factor as in v5 (within the common cycle when one
   is set, so the cycle never changes; capped at ``max_green_s``).
3. ``progression_speeds_mph``: 0 writes no offsets; a speed sets each corridor signal's ``offset`` so that its
   corridor green starts when a platoon that left the first corridor signal's green start at that speed arrives,
   following the corridor edge chain in the direction of the mapped DOT link (the opposite direction is not
   progressed). Progression needs a common cycle, so it is combined only with the numeric cycles.

Every cell is run under the fixed-time baseline on the development seeds. A cell is admissible only when every seed
passes the preregistered rule (``demand_selection.max_teleports`` and ``max_unfinished_frac``). Among admissible cells
the one whose seed-mean space-mean speed on the mapped DOT link is closest to the observed PM-peak speed is selected,
provided the gap is within ``tolerance_mph``; ties go to the smaller green factor, then the Webster cycles before a
common cycle and the shorter common cycle, then no progression. Otherwise nothing is selected and the comparison
stays NOT RUN. The selected program replaces the Webster plan as the fixed-time baseline (and the plan the forecast
rule and candidates act on); the side-demand level is then re-selected under it by the preregistered rule.
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


def _rel(path: Path) -> str:
    return path.relative_to(settings.ROOT).as_posix() if path.is_relative_to(settings.ROOT) else str(path)


def _set_durations(phases, new: list[float]) -> None:
    for ph, d in zip(phases, new):
        ph.set("duration", f"{d:.1f}")
        for k in ("minDur", "maxDur"):
            if ph.get(k) is not None:
                ph.set(k, f"{d:.1f}")


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
        _set_durations(phases, new)
        per_tls[tid] = {"cycle_before_s": round(cycle0, 1), "cycle_after_s": round(sum(new), 1),
                        "corridor_green_before_s": round(dc, 1), "corridor_green_after_s": round(new_c, 1),
                        "capped": bool(new_c + 1e-9 < dc * factor)}
    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    return {"method": "calibrated_splits", "green_factor": factor, "tls_additional": _rel(dst), "sha16": sr.file_hash(dst),
            "min_green_s": min_green, "max_green_s": max_green, "max_cycle_s": max_cycle, "per_tls": per_tls}


def set_common_cycle(src: Path, dst: Path, corridor_ids, cycle: float, min_green: float) -> dict:
    """Put every corridor signal of a tlLogic additional file on one common ``cycle``.

    Clearance phases (yellow, all-red) keep their durations; the green phases are scaled by one factor so that the
    cycle equals ``cycle``, with every green floored at ``min_green`` (the floor is paid for by the remaining greens).
    Phase order and states never change; other signals are copied unchanged. Raises when the cycle cannot hold the
    clearance plus ``min_green`` for every green phase."""
    tree = ET.parse(src)
    per_tls = {}
    for tl in tree.getroot().iter("tlLogic"):
        tid = tl.get("id")
        if tid not in set(corridor_ids):
            continue
        phases = tl.findall("phase")
        durs = [float(ph.get("duration")) for ph in phases]
        greens = [i for i, ph in enumerate(phases) if _is_green(ph.get("state"))]
        clearance = sum(d for i, d in enumerate(durs) if i not in greens)
        target = cycle - clearance
        if not greens or target < len(greens) * min_green - 1e-9:
            raise RuntimeError(f"{tid}: a {cycle:.0f} s cycle cannot hold {clearance:.0f} s of clearance plus "
                               f"{len(greens)} greens of at least {min_green:.0f} s")
        new, free = list(durs), set(greens)
        for _ in range(len(greens) + 1):
            fixed = [i for i in greens if i not in free]
            remaining = target - len(fixed) * min_green
            tot = sum(durs[i] for i in free)
            for i in free:
                new[i] = durs[i] * remaining / tot
            low = {i for i in free if new[i] < min_green - 1e-9}
            if not low:
                break
            for i in low:
                new[i] = min_green
            free -= low
        new = [round(d, 1) for d in new]
        longest = max(greens, key=lambda i: new[i])
        new[longest] = round(new[longest] + (cycle - sum(new)), 1)   # absorb the rounding residual: cycle exact
        _set_durations(phases, new)
        per_tls[tid] = {"cycle_before_s": round(sum(durs), 1), "cycle_after_s": round(sum(new), 1),
                        "green_scale": round(target / sum(durs[i] for i in greens), 3),
                        "greens_at_min": sorted(i for i in greens if abs(new[i] - min_green) < 1e-9)}
    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    return {"common_cycle_s": cycle, "tls_additional": _rel(dst), "sha16": sr.file_hash(dst), "per_tls": per_tls}


def order_chain(net, edges: list[str], start: str) -> list[str]:
    """The corridor edges of one direction in travel order, walking downstream from ``start`` through the set; at a
    fork inside the set the higher-priority (then lexically first) edge is followed."""
    ids, out, seen = set(edges), [start], {start}
    cur = net.getEdge(start)
    while True:
        nxt = [e for e in cur.getOutgoing() if e.getID() in ids and e.getID() not in seen]
        if not nxt:
            return out
        nxt.sort(key=lambda e: (-e.getPriority(), e.getID()))
        cur = nxt[0]
        out.append(cur.getID())
        seen.add(cur.getID())


def corridor_signal_positions(net_file: Path, chain: list[str], corridor_ids) -> list[dict]:
    """Cumulative distance along an ordered edge chain to each corridor signal, in travel order: a signal is placed at
    the end of the first chain edge it controls (a joined signal is counted once, where the platoon reaches it)."""
    import sumolib

    net = sumolib.net.readNet(str(net_file))
    cum, out, seen, ids = 0.0, [], set(), set(corridor_ids)
    for e in chain:
        edge = net.getEdge(e)
        cum += edge.getLength()
        tls = edge.getTLS()
        if tls is not None and tls.getID() in ids and tls.getID() not in seen:
            seen.add(tls.getID())
            out.append({"tls": tls.getID(), "edge": e, "distance_m": round(cum, 1)})
    return out


def progression_offsets(positions: list[dict], programs: dict, speed_mph: float, cycle: float) -> dict:
    """Offset per corridor signal so that its corridor green starts when a platoon leaving the first signal's green
    start at ``speed_mph`` arrives: ``offset = (distance / speed - green_start) mod cycle``.

    ``programs`` maps a signal id to ``(phase_durations, corridor_phase_index)``; ``green_start`` is the program time
    at which the corridor phase begins. A positive SUMO offset delays the program by that many seconds."""
    v = speed_mph / MPH_PER_MPS
    if v <= 0 or not positions:
        return {}
    d0 = positions[0]["distance_m"]
    out = {}
    for pos in positions:
        durs, ci = programs[pos["tls"]]
        green_start = sum(durs[:int(ci)])
        out[pos["tls"]] = round(((pos["distance_m"] - d0) / v - green_start) % cycle, 1)
    return out


def apply_offsets(src: Path, dst: Path, offsets: dict) -> dict:
    """Write ``offset`` on the listed tlLogic elements (durations and states untouched)."""
    tree = ET.parse(src)
    for tl in tree.getroot().iter("tlLogic"):
        if tl.get("id") in offsets:
            tl.set("offset", f"{offsets[tl.get('id')]:.1f}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    return {"offsets_s": offsets, "tls_additional": _rel(dst), "sha16": sr.file_hash(dst)}


def program_durations(add_file: Path, corridor_phase: dict) -> dict:
    """``{tls_id: (phase_durations, corridor_phase_index)}`` for the corridor signals of a tlLogic additional file."""
    out = {}
    for tl in ET.parse(add_file).getroot().iter("tlLogic"):
        if tl.get("id") in corridor_phase:
            out[tl.get("id")] = ([float(ph.get("duration")) for ph in tl.findall("phase")], int(corridor_phase[tl.get("id")]))
    return out


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


def _cell_key(c: dict) -> tuple:
    cyc = c.get("common_cycle_s")
    return (float(c["green_factor"]), -1.0 if cyc is None else float(cyc), float(c.get("progression_speed_mph") or 0.0))


def choose_factor(per_factor: list[dict], target_mph: float, tolerance_mph: float) -> dict:
    """Preregistered choice: the admissible cell whose seed-mean speed is closest to the target, provided the gap is
    within tolerance; ties go to the smaller green factor, then the Webster cycles before a common cycle and the
    shorter common cycle, then no progression. Otherwise nothing is selected."""
    ok = [f for f in per_factor if f.get("admissible") and f.get("speed_mean_mph") is not None]
    none = {"selected_green_factor": None, "selected_cell": None, "selected_speed_mph": None, "speed_gap_mph": None}
    if not ok:
        return {**none, "reason": "no cell of the grid passes the preregistered admissibility rule on every seed"}
    best = min(ok, key=lambda f: (abs(f["speed_mean_mph"] - target_mph),) + _cell_key(f))
    gap = round(best["speed_mean_mph"] - target_mph, 2)
    cell = {"green_factor": best["green_factor"], "common_cycle_s": best.get("common_cycle_s"),
            "progression_speed_mph": best.get("progression_speed_mph", 0)}
    desc = (f"factor {best['green_factor']}" + (f", {cell['common_cycle_s']:.0f} s common cycle" if cell["common_cycle_s"] else
            ", Webster cycles") + (f", {cell['progression_speed_mph']} mph offsets" if cell["progression_speed_mph"] else ""))
    if abs(gap) > tolerance_mph:
        return {**none, "selected_speed_mph": best["speed_mean_mph"], "speed_gap_mph": gap,
                "reason": f"closest admissible cell ({desc}) gives {best['speed_mean_mph']} mph, {gap:+.2f} mph from the "
                          f"target, beyond the {tolerance_mph} mph tolerance"}
    return {"selected_green_factor": best["green_factor"], "selected_cell": cell, "selected_speed_mph": best["speed_mean_mph"],
            "speed_gap_mph": gap, "reason": f"closest admissible cell within tolerance ({desc})"}


def mapped_edges(link_id: str) -> list[str]:
    with open(settings.ROOT / "simulation" / "mappings" / "dot_to_sumo.csv") as fh:
        for r in csv.DictReader(fh):
            if r["dot_link_id"] == link_id and r["mapping_confidence"] == "high":
                return r["sumo_edge_id"].split(";")
    raise SystemExit(f"NOT_RUN: DOT link {link_id} has no high-confidence SUMO mapping")


def grid_cells(cal: dict) -> list[dict]:
    """The preregistered grid as a list of cells. Without a ``grid`` block (protocol v5) it is the green factors at the
    Webster cycles with no offsets."""
    grid = cal.get("grid") or {"common_cycles_s": [None], "green_factors": cal["green_factors"], "progression_speeds_mph": [0]}
    cells = []
    for cyc in grid.get("common_cycles_s", [None]):
        for f in grid["green_factors"]:
            for v in grid.get("progression_speeds_mph", [0]):
                if cyc is None and v:
                    continue   # offsets without a common cycle cannot form a progression
                cells.append({"common_cycle_s": None if cyc is None else float(cyc), "green_factor": float(f),
                              "progression_speed_mph": float(v or 0)})
    return cells


def _cell_tag(c: dict) -> str:
    cyc = "web" if c["common_cycle_s"] is None else f"{int(c['common_cycle_s'])}"
    return f"c{cyc}.f{c['green_factor']:.2f}.p{int(c['progression_speed_mph']):02d}"


def build_cell_program(base_add: Path, out: Path, cell: dict, meta: dict, net: Path, sim: dict, cal: dict,
                       chain: list[str]) -> dict:
    """The tlLogic additional file of one grid cell: common cycle (optional), corridor-green factor, offsets (optional)."""
    corridor_phase, corridor_ids = meta["corridor_phase"], meta["tls_corridor"]
    plan = {"method": "calibrated_splits", **cell}
    src = base_add
    if cell["common_cycle_s"] is not None:
        cc = set_common_cycle(src, out, corridor_ids, cell["common_cycle_s"], float(sim["min_green_s"]))
        plan["common_cycle"] = cc["per_tls"]
        src = out
    max_cycle = cell["common_cycle_s"] if cell["common_cycle_s"] is not None else float(cal.get("max_cycle_s", 120))
    rs = rescale_corridor_green(src, out, corridor_phase, cell["green_factor"], float(sim["min_green_s"]), max_cycle,
                                float(sim["max_green_s"]))
    plan["per_tls"] = rs["per_tls"]
    plan.update({k: rs[k] for k in ("min_green_s", "max_green_s", "max_cycle_s")})
    if cell["progression_speed_mph"]:
        positions = corridor_signal_positions(net, chain, corridor_ids)
        offs = progression_offsets(positions, program_durations(out, corridor_phase), cell["progression_speed_mph"],
                                   cell["common_cycle_s"])
        apply_offsets(out, out, offs)
        plan["progression"] = {"speed_mph": cell["progression_speed_mph"], "direction": cal.get("progression_direction", "mapped_link"),
                               "chain_start": chain[0], "signals_in_order": positions, "offsets_s": offs}
    plan.update({"tls_additional": _rel(out), "sha16": sr.file_hash(out)})
    return plan


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
    # the progression direction is the mapped link's: the chain of that direction that contains its edges
    import sumolib

    snet = sumolib.net.readNet(str(net))
    c = meta["corridor"]
    direction = "southbound" if set(edges) & set(c["southbound"]) else "northbound"
    chain = order_chain(snet, c[direction], c[f"{direction[:2]}_chain_starts"][0])
    cells = grid_cells(cal)
    plans, jobs, outs = {}, [], []
    for cell in cells:
        tag = _cell_tag(cell)
        out = p.SIM / "networks" / f"{p.CFG_NAME}.{label}.{tag}.add.xml"
        plans[tag] = build_cell_program(settings.ROOT / base["tls_additional"], out, cell, meta, net, sim, cal, chain)
        for s in cal["seeds"]:
            ed_add = p.SIM / "demand" / f"{label}.{tag}.s{s}.edgedata.add.xml"
            ed_out = (p.SIM / "outputs" / f"{label}-edgedata-{tag}-s{s}.xml").resolve()
            t0, t1 = sim["warmup_s"], sim["warmup_s"] + sim["evaluation_s"]
            ed_add.write_text(f'<additional><edgeData id="ed" file="{ed_out}" begin="{t0}" end="{t1}" '
                              'excludeEmpty="true"/></additional>')
            sc = {**scen, "name": f"calib_{tag.replace('.', '_')}", "tls_additional": plans[tag]["tls_additional"],
                  "signal_timing_kind": "calibrated_splits", **cell,
                  "extra_additionals": [ed_add.relative_to(settings.ROOT).as_posix()]}
            jobs.append((net, routes, sc, "fixed_time", s))
            outs.append((tag, s, ed_out))
    rows = p.run_many(jobs)
    per_factor = []
    for tag, cell in zip(plans, cells):
        idx = [i for i, (tt, _, _) in enumerate(outs) if tt == tag]
        rs = [rows[i] for i in idx]
        sp = [link_speed_from_edgedata(net, outs[i][2], edges) for i in idx]
        speeds = [x["space_mean_speed_mph"] for x in sp]
        valid = [v for v in speeds if v is not None]
        per_factor.append({**cell, "program": plans[tag], "admissible": all(p.run_admissible(r, rule) for r in rs),
                           "run_ids": [r["run_id"] for r in rs], "status": [r["status"] for r in rs],
                           "teleports": [r["metrics"].get("teleports") for r in rs],
                           "unfinished_trips": [r["metrics"].get("unfinished_trips") for r in rs],
                           "loaded": [r["metrics"].get("loaded") for r in rs],
                           "completed_trips": [r["metrics"].get("completed_trips") for r in rs],
                           "speeds_mph": speeds, "speed_mean_mph": round(float(np.mean(valid)), 2) if valid else None})
    choice = choose_factor(per_factor, float(cal["target_speed_mph"]), float(cal["tolerance_mph"]))
    rep = {"generated_at": utcnow_iso(), "protocol_id": label,
           "mode": "SIMULATION (testbed signal-timing calibration, not a controller comparison)",
           "sumo_version": sr.sumo_version(), "rule": {**cal, "max_teleports": rule["max_teleports"],
                                                      "max_unfinished_frac": rule["max_unfinished_frac"]},
           "grid_cells": len(cells), "runs": len(jobs), "base_program": base, "dot_link_id": str(cal["dot_link_id"]),
           "sumo_edges": edges, "progression_direction": direction, "progression_chain": chain,
           "network_static_content_sha256": meta["network"].get("static_content_sha256"),
           "demand_source": meta["demand"].get("source"), "demand": scen["demand"], "per_factor": per_factor, **choice,
           "note": "a calibrated scenario testbed (corridor cycle, green share and offsets tuned to one observed speed), "
                   "not NYC DOT timing"}
    write_json(p.SIM / "scenarios" / f"split_calibration_{label}.json", rep)
    p.export_sim_rows(rows, settings.ROOT / "reports" / "experiments" / f"simulation_split_calibration_{label}.csv")
    sel = choice["selected_cell"]
    if sel is not None:
        tag = _cell_tag(sel)
        meta["signal_timing"] = {**plans[tag], "base_program": base,
                                 "calibration": f"simulation/scenarios/split_calibration_{label}.json",
                                 "note": "calibrated scenario testbed, not NYC DOT timing plans"}
        meta["tls_inventory_active"] = p.retimed_inventory(meta, plans[tag]["tls_additional"])
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
