"""Sensitivity of the SUMO testbed to netconvert's --osm.turn-lanes (a testbed check, not a controller comparison).

Both networks are built from the same OSM extract; on each, the routine peak with the 2014 ATR mainline count
(1,389 veh/h per direction) and no side-street demand is re-timed with Webster's method and run with plain SUMO on
the development seeds. Output: reports/experiments/simulation_turnlane_check.json.
Run from the repository root after `simulation prepare`:  python scripts/sim_turnlane_check.py
"""

from __future__ import annotations

import copy
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from smartcity import settings
from smartcity.simulation import pipeline as p
from smartcity.simulation import sumo_runner as sr
from smartcity.utils import read_json, utcnow_iso, write_json

DEMAND_2014 = {"main_veh_per_hour_per_direction": 1389.0, "side_veh_per_hour_per_approach": 150,
               "route_choice": "fixed_free_flow", "side_demand_scale": 0.0}


def run_case(meta: dict, osm: Path, turn_lanes: bool, seeds: list[int], tmp: Path) -> dict:
    cfg = settings.load("simulation")["simulation"]
    net = sr.netconvert(osm, tmp / f"turnlanes_{turn_lanes}.net.xml", "static", turn_lanes)
    m = copy.deepcopy(meta)
    m["network"]["static"] = str(net)
    m["demand"] = dict(DEMAND_2014)
    name = f"turnlane_check_{'with' if turn_lanes else 'without'}"
    scen = {**next(s for s in p.scenarios(m) if s["name"] == "routine_peak"), "name": name, "side_demand_scale": 0.0}
    routes = p.build_routes(m, scen)
    plan = p.retime_signals(m, routes, name, "turnlane_check")
    runs = []
    for seed in seeds:
        trip, stats = tmp / f"{name}_{seed}.trip.xml", tmp / f"{name}_{seed}.stats.xml"
        cmd = [sr.binary(), "-n", str(net), "-r", routes, "-a", str(settings.ROOT / plan["tls_additional"]), "--seed", str(seed),
               "--end", str(cfg["warmup_s"] + cfg["evaluation_s"] + 1800), "--time-to-teleport", "300",
               "--max-depart-delay", "900", "--no-step-log", "true", "--no-warnings", "true",
               "--tripinfo-output", str(trip), "--statistic-output", str(stats)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"sumo failed: {r.stderr[-800:]}")
        veh = ET.parse(stats).getroot().find("vehicles").attrib
        tl: dict = {}
        for t in ET.parse(trip).getroot().iter("tripinfo"):
            if float(t.get("depart")) >= cfg["warmup_s"]:
                tl.setdefault(t.get("id").split(".")[0], []).append(float(t.get("timeLoss")))
        runs.append({"seed": seed, "loaded": int(veh["loaded"]), "running_at_end": int(veh["running"]),
                     "teleports": int(ET.parse(stats).getroot().find("teleports").get("total")),
                     "by_flow": {k: {"completed": len(v), "mean_time_loss_s": round(sum(v) / len(v), 1)} for k, v in sorted(tl.items())}})
    return {"osm_turn_lanes": turn_lanes, "network_content_sha256": p.net_content_hash(net),
            "dead_end_corridor_lanes": p.dead_lanes(p._net(m), set(m["corridor"]["northbound"]) | set(m["corridor"]["southbound"])),
            "retimed_programs_sha16": plan["sha16"], "runs": runs}


def main() -> None:
    meta = read_json(p.SIM / "scenarios" / "prepared.json")
    osm = settings.ROOT / meta["network"]["osm_file"]
    seeds = settings.load("simulation")["demand_selection"]["seeds"]
    with tempfile.TemporaryDirectory() as d:
        cases = [run_case(meta, osm, flag, seeds, Path(d)) for flag in (True, False)]
    rep = {"generated_at": utcnow_iso(), "mode": "SIMULATION (testbed check, not a controller comparison)",
           "sumo_version": sr.sumo_version(), "osm_sha256": meta["network"]["osm_sha256"], "demand": DEMAND_2014,
           "seeds": seeds, "cases": cases}
    write_json(settings.ROOT / "reports" / "experiments" / "simulation_turnlane_check.json", rep)
    for c in cases:
        print(c["osm_turn_lanes"], c["network_content_sha256"][:12], [(r["seed"], r["running_at_end"], r["by_flow"]) for r in c["runs"]])


if __name__ == "__main__":
    main()
