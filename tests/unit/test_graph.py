"""Graph construction rules on synthetic link geometries (software checks, not project evidence)."""

from smartcity.graph.build import build_graph, corridor_key, direction_tokens, endpoint_labels

CFG = {"endpoint_join_m": 150, "max_heading_change_deg": 100, "reject_if_reverse_direction": True,
       "corridor_join_m": 2000, "corridor_max_heading_change_deg": 100, "named_join_m": 12000}


def _link(lid, name, lat0, n=6, step=0.002, lon=-74.0, northbound=True):
    lats = [lat0 + step * i for i in range(n)]
    if not northbound:
        lats = lats[::-1]
    return {"link_id": lid, "link_name": name, "borough": "Manhattan", "owner": "t",
            "link_points": " ".join(f"{la:.5f},{lon:.5f}" for la in lats), "encoded_poly_line": ""}


def test_corridor_key_parses_direction_token():
    assert corridor_key("FDR N 25th - 42nd") == ("fdr", "N")
    assert corridor_key("West Side Hwy S 42nd - Houston") == ("west side hwy", "S")
    assert corridor_key("12th ave n ganservoort - 12th ave @ 40th st") == ("12th ave", "N")
    assert corridor_key("MANHATTAN BRIDGE") is None
    assert corridor_key("") is None


def test_endpoint_rule_joins_contiguous_segments():
    links = [_link("1", "FDR N a - b", 40.70), _link("2", "FDR N b - c", 40.71)]
    g = build_graph(links, CFG)["graph"]
    assert g["n_edges"] == 1 and g["n_edges_endpoint_rule"] == 1 and g["edge_index"] == [[0], [1]]


def test_corridor_rule_bridges_unmonitored_gap_one_successor_only():
    # 1 -> gap of ~1.1 km -> 2 -> gap -> 3, all "FDR N"; without the corridor rule they would be isolated
    links = [_link("1", "FDR N a - b", 40.70), _link("2", "FDR N b - c", 40.72), _link("3", "FDR N c - d", 40.74)]
    g = build_graph(links, dict(CFG, corridor_join_m=0, named_join_m=0))["graph"]
    assert g["n_edges"] == 0
    res = build_graph(links, dict(CFG, named_join_m=0))
    g = res["graph"]
    assert g["n_edges"] == 2 and g["n_edges_corridor_rule"] == 2
    assert sorted(zip(*g["edge_index"])) == [(0, 1), (1, 2)]  # nearest successor only, no 1 -> 3 skip edge
    assert any(r["accepted"] and r["rationale"].startswith("corridor continuity") for r in res["audit"])


def test_corridor_rule_never_joins_opposite_direction_or_upstream():
    links = [_link("1", "FDR N a - b", 40.70), _link("2", "FDR S b - a", 40.70, northbound=False),
             _link("3", "FDR N z - a", 40.68)]  # 3 lies upstream (south) of 1's end
    g = build_graph(links, CFG)["graph"]
    pairs = set(zip(*g["edge_index"]))
    assert (0, 1) not in pairs and (1, 0) not in pairs
    assert (0, 2) not in pairs and (2, 0) in pairs  # 3 -> 1 is a legitimate downstream join


def test_endpoint_labels_parse_real_dot_name_shapes():
    assert endpoint_labels("FDR S 63rd - 25th St") == ({"63"}, {"25"})
    assert endpoint_labels("FDR N Catherine Slip - 25th St") == ({"catherine", "slip"}, {"25"})
    assert endpoint_labels("12th ave @ 45th - 11 ave ganservoort st") == ({"12", "45"}, {"11", "ganservoort"})
    assert endpoint_labels("FDR N - TBB E 116TH STREET - MANHATTAN TRUSS") == ({"tbb", "116"}, {"truss"})
    assert endpoint_labels("BBT E Manhattan Portal - Toll Plaza") == ({"bbt"}, set())  # generic 'Toll Plaza' never matches
    assert endpoint_labels("LINCOLN TUNNEL E SOUTH TUBE - NJ - NY") == (set(), set())
    assert endpoint_labels("MANHATTAN BRIDGE") == (set(), set())


def test_direction_tokens_entry_and_exit():
    assert direction_tokens("FDR N 25th - 63rd St") == ("N", "N")
    assert direction_tokens("TBB W - FDR S MANHATTAN TRUSS - E116TH STREET") == ("W", "S")
    assert direction_tokens("FDR N - TBB E 116TH STREET - MANHATTAN TRUSS") == ("N", "E")
    assert direction_tokens("BKN Bridge Manhattan Side - FDR N Catherine Slip") == ("N", "N")
    assert direction_tokens("12th ave @ 45th - 11 ave ganservoort st") == (None, None)


def test_named_rule_joins_truncated_polylines_but_not_opposite_or_generic():
    # 1 "63rd - 25th" geometry stops ~1.5 km short of 2's start (as the real DOT polylines do); corridor rule alone
    # would still join them, so disable it here to isolate the named rule.  3 is the opposite carriageway starting
    # at the same named point; 4/5 share only the generic label "Toll Plaza"; 6 is a matching name 15 km away.
    links = [_link("1", "FDR S 63rd - 25th St", 40.760, northbound=False),      # ends at 40.750
             _link("2", "FDR S 25th St - Catherine Slip", 40.736, northbound=False),  # starts ~1.55 km south of 1's end
             _link("3", "FDR N 25th - 63rd St", 40.736),                         # starts at 40.736 heading north
             _link("4", "QMT E Manhattan Side - Toll Plaza", 40.700, lon=-73.99),
             _link("5", "BBT W Toll Plaza - Manhattan Portal", 40.700, lon=-73.95),
             _link("6", "FDR S Catherine Slip - BKN Bridge Manhattan Side", 40.600, northbound=False)]
    res = build_graph(links, dict(CFG, corridor_join_m=0))
    g = res["graph"]
    pairs = set(zip(*g["edge_index"]))
    assert (0, 1) in pairs and g["n_edges_named_rule"] == 1
    assert (0, 2) not in pairs and (1, 2) not in pairs   # S -> N never joined by name
    assert (3, 4) not in pairs and (4, 3) not in pairs   # generic labels carry no evidence
    assert (1, 5) not in pairs                           # beyond named_join_m (start to start)
    row = next(r for r in res["audit"] if r["src"] == "1" and r["dst"] == "2")
    assert row["accepted"] and row["rationale"].startswith("named-endpoint continuity") and "'25'" in row["rationale"]
    assert g["n_edges"] == 1


def test_named_rule_handles_ramps_and_names_without_direction_tokens():
    # a: Triborough westbound ramp exiting onto FDR S at 116th; b: FDR N on-ramp to Triborough eastbound from 116th.
    # They share the label "116" but a exits S and b enters N: a U-turn, never joined.
    # c: a southbound avenue link whose name has no direction token (direction inferred from geometry) feeding
    # d (southbound, accepted) but not e (northbound at the same named point, rejected).
    links = [_link("a", "TBB W - FDR S MANHATTAN TRUSS - E116TH STREET", 40.800, northbound=False),
             _link("b", "FDR N - TBB E 116TH STREET - MANHATTAN TRUSS", 40.790),
             _link("c", "12th ave @ 45th - 11 ave ganservoort st", 40.760, northbound=False),
             _link("d", "11th ave s ganservoort - west st @ spring st", 40.745, northbound=False),
             _link("e", "11th ave n ganservoort - 12th ave @ 40th st", 40.745)]
    res = build_graph(links, dict(CFG, corridor_join_m=0))
    pairs = set(zip(*res["graph"]["edge_index"]))
    assert (0, 1) not in pairs
    assert (2, 3) in pairs and (2, 4) not in pairs
    nodes = {n["link_id"]: n for n in res["graph"]["nodes"]}
    assert nodes["c"]["direction_inferred"] and nodes["c"]["exit_dir"] == "S"
    assert not nodes["a"]["direction_inferred"] and (nodes["a"]["entry_dir"], nodes["a"]["exit_dir"]) == ("W", "S")


def test_temporal_signal_falls_back_when_the_package_init_raises_oserror(monkeypatch):
    """A blocked compiled extension (Windows Application Control, WinError 4551) raises OSError, not ImportError,
    from the package __init__; the signal module must still load through the direct-module route."""
    import importlib.abc
    import importlib.machinery
    import sys

    from smartcity.graph import temporal

    class _Blocked(importlib.abc.Loader):
        def create_module(self, spec):
            return None

        def exec_module(self, module):
            raise OSError(4551, "An Application Control policy has blocked this file")

    class _Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name == "torch_geometric_temporal.signal":
                return importlib.machinery.ModuleSpec(name, _Blocked())
            return None

    for k in [k for k in sys.modules if k.startswith("torch_geometric_temporal")]:
        monkeypatch.delitem(sys.modules, k)
    monkeypatch.setattr(sys, "meta_path", [_Finder(), *sys.meta_path])
    monkeypatch.setattr(temporal, "IMPORT_ROUTE", "unresolved")
    cls = temporal._signal_class()
    assert cls.__name__ == "StaticGraphTemporalSignal"
    assert temporal.IMPORT_ROUTE.startswith("direct-module")
