"""Side-demand selection rule and network content hash (pure functions; no SUMO run, no project data)."""

import pytest

from smartcity.simulation.pipeline import apply_selection_rule, net_content_hash, paired_candidate_eval

CFG = {"side_scales": [1.0, 0.5, 0.0], "seeds": [101, 102], "max_teleports": 0, "max_unfinished_frac": 0.01}


def _run(scale, teleports=0, unfinished=0, loaded=1000, status="OK"):
    return {"run_id": f"r{scale}-{teleports}-{unfinished}", "status": status, "demand": {"side_demand_scale": scale},
            "metrics": {"teleports": teleports, "unfinished_trips": unfinished, "loaded": loaded}}


def test_largest_admissible_scale_is_selected():
    rows = [_run(1.0, teleports=5), _run(1.0), _run(0.5), _run(0.5, unfinished=10), _run(0.0), _run(0.0)]
    sel = apply_selection_rule(rows, CFG)
    assert [p["admissible"] for p in sel["per_scale"]] == [False, True, True]
    assert sel["selected_side_demand_scale"] == 0.5  # 10 unfinished of 1000 is exactly the 1 % bound


def test_one_bad_seed_disqualifies_a_scale():
    rows = [_run(1.0), _run(1.0, unfinished=11), _run(0.5), _run(0.5), _run(0.0), _run(0.0)]
    assert apply_selection_rule(rows, CFG)["selected_side_demand_scale"] == 0.5


def test_no_admissible_scale_selects_nothing():
    rows = [_run(s, teleports=1) for s in CFG["side_scales"] for _ in CFG["seeds"]]
    assert apply_selection_rule(rows, CFG)["selected_side_demand_scale"] is None


def test_failed_or_missing_runs_are_not_admissible():
    rows = [_run(1.0, status="TIMEOUT"), _run(1.0), _run(0.0), _run(0.0)]  # scale 0.5 has no runs at all
    sel = apply_selection_rule(rows, CFG)
    assert [p["admissible"] for p in sel["per_scale"]] == [False, False, True]
    assert sel["selected_side_demand_scale"] == 0.0


def test_net_content_hash_ignores_the_netconvert_header(tmp_path):
    body = '<net version="1.20"><edge id="a"/></net>\n'
    a, b = tmp_path / "a.net.xml", tmp_path / "b.net.xml"
    a.write_text('<?xml version="1.0"?>\n<!-- generated on 2026-10-21T01:00:00 by netconvert\n --input /x -->\n' + body)
    b.write_text('<?xml version="1.0"?>\n<!-- generated on 2026-10-21T02:00:00 by netconvert\n --input /y -->\n' + body)
    assert net_content_hash(a) == net_content_hash(b)
    b.write_text(b.read_text().replace('id="a"', 'id="b"'))
    assert net_content_hash(a) != net_content_hash(b)


def test_candidate_is_not_judged_on_a_testbed_without_admissible_demand():
    meta = {"network": {"static": "unused.net.xml"}, "demand": {"main_veh_per_hour_per_direction": 1389,
                                                                 "side_veh_per_hour_per_approach": 150}}
    with pytest.raises(RuntimeError, match="NOT_EVALUATED"):
        paired_candidate_eval(meta, {"name": "event_surge"}, {"candidate_id": "c1"}, [1])


def _counts_frame(rows):
    import polars as pl

    hour_cols = {16: "_4_00_5_00pm", 17: "_5_00_6_00pm", 18: "_6_00_7_00pm"}
    out = []
    for name, direction, date, cls, vph in rows:
        out.append({"roadway_name": name, "from": "Spring St", "to": "W Houston St", "direction": direction, "date": date,
                    "veh_class_type": cls, **{c: str(vph) for c in hour_cols.values()}})
    return pl.DataFrame(out)


def test_recent_two_direction_counts_takes_the_latest_year_with_both_directions(monkeypatch):
    from smartcity.preprocessing import raw
    from smartcity.simulation import pipeline

    data = {
        "classification": _counts_frame([
            ("West St NB", "NB", "2025-04-29T00:00:00.000", "Autos", 2000), ("West St NB", "NB", "2025-04-29T00:00:00.000", "Taxi", 500),
            ("West St SB", "SB", "2025-04-29T00:00:00.000", "Autos", 2400),
            ("West St NB", "NB", "2026-01-06T00:00:00.000", "Autos", 9999),           # newer, but one direction only
            ("West St SB", "SB", "2025-04-26T00:00:00.000", "Autos", 7777),           # a Saturday: excluded
            ("Joe DiMaggio Hwy/West Side Hwy", "SB", "2025-04-29T00:00:00.000", "Autos", 5555)]),  # other street
        "volume_hist": _counts_frame([("West Street", "NB", "2019-10-08T00:00:00.000", "", 1500),
                                      ("West Street", "SB", "2019-10-08T00:00:00.000", "", 1600)]),
    }
    monkeypatch.setattr(raw, "read_socrata", lambda src, prefix=None: data[src])
    rec = pipeline.recent_two_direction_counts({"count_sources": ["classification", "volume_hist"],
                                                "count_street_regex": "^(WEST ST|WEST STREET)( NB| SB)?$"})
    assert rec["count_source"] == "classification" and rec["count_year"] == 2025
    assert rec["vph"] == {"nb": 2500.0, "sb": 2400.0}  # classes summed per hour; weekend and other street ignored


def test_no_two_direction_year_returns_none(monkeypatch):
    from smartcity.preprocessing import raw
    from smartcity.simulation import pipeline

    one = _counts_frame([("West St NB", "NB", "2025-04-29T00:00:00.000", "Autos", 2000)])
    monkeypatch.setattr(raw, "read_socrata", lambda src, prefix=None: one)
    assert pipeline.recent_two_direction_counts({"count_sources": ["classification"],
                                                 "count_street_regex": "^(WEST ST)( NB| SB)?$"}) is None
