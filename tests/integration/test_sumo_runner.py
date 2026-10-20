"""SUMO/TraCI software test on a generated toy grid (fixture network, not the study corridor)."""

import subprocess

import pytest

from smartcity.simulation import sumo_runner as sr


@pytest.fixture(scope="module")
def toy(tmp_path_factory):
    d = tmp_path_factory.mktemp("sumo")
    net = d / "grid.net.xml"
    r = subprocess.run([sr.binary("netgenerate"), "--grid", "--grid.number", "3", "--grid.length", "200",
                        "--default-junction-type", "traffic_light", "--tls.yellow.time", "3", "-o", str(net),
                        "--no-turnarounds", "true"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    import sumolib

    n = sumolib.net.readNet(str(net))
    edges = [e.getID() for e in n.getEdges() if not e.getID().startswith(":")]
    flows = [{"id": "main_0", "from": "A0B0", "to": "B0C0", "veh_per_hour": 300},
             {"id": "side_0", "from": "B1B0", "to": "B0A0", "veh_per_hour": 100}]
    flows = [f for f in flows if f["from"] in edges and f["to"] in edges] or \
        [{"id": "main_0", "from": edges[0], "to": edges[1], "veh_per_hour": 200}]
    rou = sr.write_flows(d / "toy.rou.xml", flows, 0, 600)
    return net, rou


def test_run_scenario_and_protected_controller(toy, monkeypatch):
    net, rou = toy
    from smartcity import settings

    cfg = dict(settings.load("simulation"))
    cfg["simulation"] = dict(cfg["simulation"], warmup_s=60, evaluation_s=300)
    monkeypatch.setattr(settings, "load", lambda name, _o=settings.load: cfg if name == "simulation" else _o(name))
    inv = sr.tls_inventory(net)
    tls = next(t for t, v in inv.items() if any(not p['green'] for p in v['phases']))
    green = next(p["index"] for p in inv[tls]["phases"] if p["green"])
    yellow = next(p["index"] for p in inv[tls]["phases"] if not p["green"])
    scen = {"name": "toy", "corridor_edges": [], "side_prefix": "side_", "incident": None}
    base = sr.run_scenario(net, rou, scen, "fixed_time", 1)
    assert base["status"] == "OK" and base["mode"] == "SIMULATION"
    assert base["metrics"]["completed_trips"] > 0
    ok = sr.run_scenario(net, rou, scen, "candidate", 1, candidate={"action_type": "bounded_green_extension",
                         "traffic_light_id": tls, "phase_index": green, "extension_seconds": 5})
    assert ok["control_log"] == [True]
    bad = sr.run_scenario(net, rou, scen, "candidate", 1, candidate={"action_type": "bounded_green_extension",
                          "traffic_light_id": tls, "phase_index": yellow, "extension_seconds": 5})
    assert bad["control_log"] == [False]  # protective wrapper refuses a clearance phase
