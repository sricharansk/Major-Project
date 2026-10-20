"""Graph construction rules on synthetic link geometries (software checks, not project evidence)."""

from smartcity.graph.build import build_graph, corridor_key

CFG = {"endpoint_join_m": 150, "max_heading_change_deg": 100, "reject_if_reverse_direction": True,
       "corridor_join_m": 2000, "corridor_max_heading_change_deg": 100}


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
    g = build_graph(links, dict(CFG, corridor_join_m=0))["graph"]
    assert g["n_edges"] == 0
    res = build_graph(links, CFG)
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
