"""Audit of the SUMO testbed itself (not a controller comparison): route choice and corridor signal capacity.

1. Route choice. The routine_peak demand at the 2026-10-20 declared levels (1,200 veh/h per direction, 150 per side
   approach) is run twice with plain SUMO (no TraCI, fixed-time programs, seed 1): once as bare from/to flows (SUMO
   routes those at insertion on current travel times) and once with one fixed free-flow route per flow. Reported:
   teleports, route replacements by the rerouting device, and the share of mainline vehicles whose route leaves
   West Street.
2. Signal capacity. For every signal on each mainline route, the green time of the movements that route makes, in the netconvert
   program and a rough capacity estimate lanes * saturation_flow * g/C (saturation flow is a nominal assumption).

Outputs: reports/experiments/simulation_testbed_audit.json, reports/experiments/simulation_signal_capacity.csv.
Run from the repository root after `simulation prepare`:  python scripts/sim_testbed_audit.py
"""

from __future__ import annotations

import csv
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from smartcity import settings
from smartcity.simulation import pipeline as p
from smartcity.simulation import sumo_runner as sr
from smartcity.utils import read_json, utcnow_iso, write_json

SATURATION_VPHPL = 1800  # nominal saturation flow per lane (assumption for the estimate, not a measured value)
DECLARED = {"main_veh_per_hour_per_direction": 1200, "side_veh_per_hour_per_approach": 150}


def route_choice_audit(meta: dict, tmp: Path) -> dict:
    cfg = settings.load("simulation")["simulation"]
    net = settings.ROOT / meta["network"]["static"]
    corridor = set(meta["corridor"]["northbound"]) | set(meta["corridor"]["southbound"])
    out = {}
    for mode in ("dynamic_insertion", "fixed_free_flow"):
        m = {**meta, "demand": {k: v for k, v in meta["demand"].items()
                                if k not in ("main_veh_per_hour_by_direction", "side_demand_scale")}}
        m["demand"].update(DECLARED, route_choice=mode)
        scen = {**next(s for s in p.scenarios(m) if s["name"] == "routine_peak"), "name": f"audit_routes_{mode}"}
        routes = p.build_routes(m, scen)
        vr, stats = tmp / f"{mode}.vehroutes.xml", tmp / f"{mode}.stats.xml"
        cmd = [sr.binary(), "-n", str(net), "-r", routes, "--seed", "1", "--end", str(cfg["warmup_s"] + cfg["evaluation_s"] + 1800),
               "--time-to-teleport", "300", "--max-depart-delay", "900", "--no-step-log", "true", "--no-warnings", "true",
               "--vehroute-output", str(vr), "--vehroute-output.write-unfinished", "true", "--statistic-output", str(stats)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"sumo failed ({mode}): {r.stderr[-1000:]}")
        reasons, main, main_off = Counter(), 0, 0
        for v in ET.parse(vr).getroot().iter("vehicle"):
            dist = v.find("routeDistribution")
            routes_v = dist.findall("route") if dist is not None else [v.find("route")]
            for rt in routes_v:
                if rt.get("reason"):
                    reasons[rt.get("reason")] += 1
            if v.get("id").startswith("main_"):
                main += 1
                main_off += any(e not in corridor and not e.startswith(":") for e in routes_v[-1].get("edges").split())
        st = ET.parse(stats).getroot()
        tp, veh = st.find("teleports").attrib, st.find("vehicles").attrib
        out[mode] = {"route_file_sha16": sr.file_hash(Path(routes)), "loaded": int(veh["loaded"]), "inserted": int(veh["inserted"]),
                     "teleports": {k: int(v) for k, v in tp.items()}, "route_replacements": dict(reasons),
                     "mainline_vehicles": main, "mainline_routes_leaving_west_street": main_off}
    return out


def capacity_audit(meta: dict, add_file: str | None = None, label: str = "netconvert_guess") -> list[dict]:
    import sumolib

    net = sumolib.net.readNet(str(settings.ROOT / meta["network"]["static"]), withPrograms=True)
    retimed = {}
    if add_file:  # same phase states, re-timed durations (checked by pipeline.retimed_inventory)
        retimed = {t: [float(ph["duration"]) for ph in v["phases"]] for t, v in p.retimed_inventory(meta, add_file).items()}
    rows = []
    c = meta["corridor"]
    for tag, ins, outs in (("northbound", c["nb_entries"], c["nb_exits"]), ("southbound", c["sb_entries"], c["sb_exits"])):
        # only movements the mainline flow actually makes: consecutive edges of its fixed route (entry -> exit)
        path, _ = net.getFastestPath(net.getEdge(ins[0]), net.getEdge(outs[-1]), vClass="passenger")
        steps = {(a.getID(), b.getID()) for a, b in zip(path, path[1:])}
        for tl in net.getTrafficLights():
            through = [(a, i) for a, b, i in tl.getConnections() if (a.getEdge().getID(), b.getEdge().getID()) in steps]
            if not through:
                continue
            phases = next(iter(tl.getPrograms().values())).getPhases()
            dur = retimed.get(tl.getID()) or [ph.duration for ph in phases]
            cycle = sum(dur)
            green = sum(d for ph, d in zip(phases, dur) if any(ph.state[i] in "Gg" for _, i in through))
            lanes = len({a.getID() for a, _ in through})
            rows.append({"program": label, "direction": tag, "tls_id": tl.getID(), "through_lanes": lanes, "cycle_s": cycle,
                         "corridor_green_s": green, "g_over_c": round(green / cycle, 3),
                         "est_capacity_vph": round(lanes * SATURATION_VPHPL * green / cycle)})
    return sorted(rows, key=lambda r: (r["program"], r["direction"], r["est_capacity_vph"]))


def direction_breakdown(scale: float = 0.0, timing: str = "netconvert_guess") -> list[dict]:
    """Mainline completed trips and mean time loss per direction in the demand-selection runs at one side scale
    (read from the runs' tripinfo.xml; trips departing after warm-up, as in the run metrics)."""
    sel = read_json(p.SIM / "scenarios" / f"demand_selection_{timing}.json")
    warmup = settings.load("simulation")["simulation"]["warmup_s"]
    rows = []
    for entry in sel["per_scale"]:
        if entry["side_demand_scale"] != scale:
            continue
        for run_id in entry["run_ids"]:
            trip = p.SIM / "outputs" / run_id / "tripinfo.xml"
            if not trip.exists():
                continue
            tl: dict = {}
            for t in ET.parse(trip).getroot().iter("tripinfo"):
                if float(t.get("depart")) >= warmup and t.get("id").startswith("main_"):
                    tl.setdefault(t.get("id").split(".")[0], []).append(float(t.get("timeLoss")))
            for flow, v in sorted(tl.items()):
                rows.append({"signal_timing": timing, "run_id": run_id, "flow": flow, "completed": len(v), "mean_time_loss_s": round(sum(v) / len(v), 1)})
    return rows


def main() -> None:
    meta = read_json(p.SIM / "scenarios" / "prepared.json")
    with tempfile.TemporaryDirectory() as d:
        routing = route_choice_audit(meta, Path(d))
    cap = capacity_audit(meta)
    sel_w = p.SIM / "scenarios" / "demand_selection_webster_retimed.json"
    plan0 = read_json(sel_w)["retimed_programs"].get("0.0", {}).get("tls_additional") if sel_w.exists() else None
    if plan0:  # the plan re-timed for the zero-side-demand routine peak (the least loaded level tested)
        cap += capacity_audit(meta, plan0, "webster_retimed_side0")
    exp = settings.ROOT / "reports" / "experiments"
    with open(exp / "simulation_signal_capacity.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cap[0].keys()))
        w.writeheader()
        w.writerows(cap)
    demand = meta["demand"]
    rep = {"generated_at": utcnow_iso(), "mode": "SIMULATION (testbed audit, not a controller comparison)",
           "sumo_version": sr.sumo_version(), "network_static_content_sha256": meta["network"].get("static_content_sha256"),
           "osm_sha256": meta["network"]["osm_sha256"], "route_choice_audit": {"demand": DECLARED, "seed": 1, **routing},
           "signal_capacity": {"saturation_flow_vphpl_assumed": SATURATION_VPHPL,
                               "observed_main_vph": demand["main_veh_per_hour_per_direction"],
                               "min_est_capacity_vph": {f"{g}:{t}": min(r["est_capacity_vph"] for r in cap
                                                                       if r["direction"] == t and r["program"] == g)
                                                        for g in sorted({r["program"] for r in cap})
                                                        for t in ("northbound", "southbound")},
                               "signals_below_observed_demand": [r for r in cap if r["est_capacity_vph"]
                                                                 < demand["main_veh_per_hour_per_direction"]]},
           "mainline_by_direction_side_scale_0": direction_breakdown(0.0) + (
               direction_breakdown(0.0, "webster_retimed") if sel_w.exists() else [])}
    write_json(exp / "simulation_testbed_audit.json", rep)
    print(rep["route_choice_audit"])
    print(rep["signal_capacity"])


if __name__ == "__main__":
    main()
