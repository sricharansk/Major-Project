"""Graph construction rules on synthetic link geometries (software checks, not project evidence)."""

from smartcity.graph.build import build_graph, corridor_key, endpoint_labels

CFG = {"endpoint_join_m": 150, "max_heading_change_deg": 100, "reject_if_reverse_direction": True,
       "corridor_join_m": 2000, "corridor_max_heading_change_deg": 100, "named_join_m": 6000}


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


def test_named_rule_joins_truncated_polylines_but_not_opposite_or_generic():
    # 1 "63rd - 25th" geometry stops ~1.5 km short of 2's start (as the real DOT polylines do); corridor rule alone
    # would still join them, so disable it here to isolate the named rule.  3 is the opposite carriageway starting
    # at the same named point; 4/5 share only the generic label "Toll Plaza"; 6 is a matching name 8 km away.
    links = [_link("1", "FDR S 63rd - 25th St", 40.760, northbound=False),      # ends at 40.750
             _link("2", "FDR S 25th St - Catherine Slip", 40.736, northbound=False),  # starts ~1.55 km south of 1's end
             _link("3", "FDR N 25th - 63rd St", 40.736),                         # starts at 40.736 heading north
             _link("4", "QMT E Manhattan Side - Toll Plaza", 40.700, lon=-73.99),
             _link("5", "BBT W Toll Plaza - Manhattan Portal", 40.700, lon=-73.95),
             _link("6", "FDR S Catherine Slip - BKN Bridge Manhattan Side", 40.660, northbound=False)]
    res = build_graph(links, dict(CFG, corridor_join_m=0))
    g = res["graph"]
    pairs = set(zip(*g["edge_index"]))
    assert (0, 1) in pairs and g["n_edges_named_rule"] == 1
    assert (0, 2) not in pairs and (1, 2) not in pairs   # S -> N never joined by name
    assert (3, 4) not in pairs and (4, 3) not in pairs   # generic labels carry no evidence
    assert (1, 5) not in pairs                           # beyond named_join_m
    row = next(r for r in res["audit"] if r["src"] == "1" and r["dst"] == "2")
    assert row["accepted"] and row["rationale"].startswith("named-endpoint continuity") and "'25'" in row["rationale"]
    assert g["n_edges"] == 1
