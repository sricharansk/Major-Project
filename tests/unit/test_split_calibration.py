"""Signal-split calibration: pure functions (no SUMO run, no project data)."""

import xml.etree.ElementTree as ET

import pytest

from smartcity.simulation import calibrate

ADD = """<additional>
<tlLogic id="corr" type="static" programID="w" offset="0">
  <phase duration="30" state="GGrr" minDur="30" maxDur="30"/>
  <phase duration="3" state="yyrr"/>
  <phase duration="2" state="rrrr"/>
  <phase duration="25" state="rrGG"/>
  <phase duration="3" state="rryy"/>
  <phase duration="2" state="rrrr"/>
</tlLogic>
<tlLogic id="other" type="static" programID="w" offset="0">
  <phase duration="40" state="GG"/>
  <phase duration="3" state="yy"/>
</tlLogic>
</additional>
"""


def _durations(path, tls):
    tl = next(t for t in ET.parse(path).getroot().iter("tlLogic") if t.get("id") == tls)
    return [float(p.get("duration")) for p in tl.findall("phase")], [p.get("state") for p in tl.findall("phase")]


def test_cycle_is_kept_while_the_other_green_has_slack(tmp_path):
    src = tmp_path / "w.add.xml"
    src.write_text(ADD)
    out = tmp_path / "c.add.xml"
    rep = calibrate.rescale_corridor_green(src, out, {"corr": 0}, 1.5, 7.0, 120.0, 90.0)
    d, states = _durations(out, "corr")
    assert d[0] == 45.0 and d[3] == 10.0 and sum(d) == 65.0  # corridor +15 s, side -15 s, cycle unchanged
    assert states == ["GGrr", "yyrr", "rrrr", "rrGG", "rryy", "rrrr"]
    assert _durations(out, "other")[0] == [40.0, 3.0]  # not a corridor signal: untouched
    assert rep["per_tls"]["corr"]["cycle_after_s"] == 65.0 and not rep["per_tls"]["corr"]["capped"]
    tl = next(t for t in ET.parse(out).getroot().iter("tlLogic") if t.get("id") == "corr")
    assert tl.findall("phase")[0].get("minDur") == "45.0"


def test_cycle_grows_only_when_the_slack_is_exhausted(tmp_path):
    src = tmp_path / "w.add.xml"
    src.write_text(ADD)
    out = tmp_path / "c.add.xml"
    calibrate.rescale_corridor_green(src, out, {"corr": 0}, 2.0, 7.0, 120.0, 90.0)
    d, _ = _durations(out, "corr")
    assert d[0] == 60.0 and d[3] == 7.0 and sum(d) == 77.0  # side green at the minimum, cycle +12 s


def test_corridor_green_is_capped_by_max_green_and_max_cycle(tmp_path):
    src = tmp_path / "w.add.xml"
    src.write_text(ADD)
    out = tmp_path / "c.add.xml"
    rep = calibrate.rescale_corridor_green(src, out, {"corr": 0}, 4.0, 7.0, 80.0, 90.0)
    d, _ = _durations(out, "corr")
    assert sum(d) == 80.0 and d[0] == 63.0 and rep["per_tls"]["corr"]["capped"]
    rep = calibrate.rescale_corridor_green(src, out, {"corr": 0}, 4.0, 7.0, 200.0, 50.0)
    d, _ = _durations(out, "corr")
    assert d[0] == 50.0 and rep["per_tls"]["corr"]["capped"]


def test_corridor_phase_must_be_green(tmp_path):
    src = tmp_path / "w.add.xml"
    src.write_text(ADD)
    with pytest.raises(RuntimeError):
        calibrate.rescale_corridor_green(src, tmp_path / "c.add.xml", {"corr": 1}, 1.5, 7.0, 120.0, 90.0)


def test_space_mean_speed_is_length_weighted():
    v = calibrate.space_mean_speed_mph({"a": 100.0, "b": 100.0}, {"a": 10.0, "b": 2.5})  # 10 s + 40 s for 200 m
    assert v == round(4.0 * calibrate.MPH_PER_MPS, 2)
    assert calibrate.space_mean_speed_mph({"a": 100.0}, {}) is None


def _f(factor, admissible, speed):
    return {"green_factor": factor, "admissible": admissible, "speed_mean_mph": speed}


def test_choose_factor_takes_the_closest_admissible_within_tolerance():
    per = [_f(1.0, False, 5.8), _f(1.2, True, 8.1), _f(1.4, True, 10.2), _f(1.6, True, 12.4)]
    c = calibrate.choose_factor(per, 10.95, 1.5)
    assert c["selected_green_factor"] == 1.4 and c["speed_gap_mph"] == -0.75


def test_choose_factor_refuses_outside_tolerance_or_without_admissible_runs():
    assert calibrate.choose_factor([_f(1.0, False, 5.8), _f(1.2, False, 8.0)], 10.95, 1.5)["selected_green_factor"] is None
    c = calibrate.choose_factor([_f(1.0, True, 5.8), _f(2.5, True, 14.0)], 10.95, 1.5)
    assert c["selected_green_factor"] is None and "beyond" in c["reason"]
    assert calibrate.choose_factor([_f(1.2, True, 10.0), _f(1.0, True, 10.0)], 10.95, 1.5)["selected_green_factor"] == 1.0


# ---- protocol v6: common cycle, progression offsets, grid and tie-break (pure functions) ----

def _add(tmp_path):
    src = tmp_path / "in.add.xml"
    src.write_text(ADD)
    return src


def test_common_cycle_scales_greens_and_keeps_clearance(tmp_path):
    # corr: greens 30 + 25, clearance 10 -> at a 90 s cycle the greens share 80 s in the same proportion
    rep = calibrate.set_common_cycle(_add(tmp_path), tmp_path / "c.add.xml", ["corr"], 90.0, 7.0)
    durs, states = _durations(tmp_path / "c.add.xml", "corr")
    assert states == ["GGrr", "yyrr", "rrrr", "rrGG", "rryy", "rrrr"]
    assert durs[1:3] == [3.0, 2.0] and durs[4:] == [3.0, 2.0]
    assert sum(durs) == pytest.approx(90.0, abs=1e-6)
    assert durs[0] == pytest.approx(80 * 30 / 55, abs=0.1) and durs[3] == pytest.approx(80 * 25 / 55, abs=0.1)
    assert rep["per_tls"]["corr"]["cycle_after_s"] == 90.0 and "other" not in rep["per_tls"]
    assert _durations(tmp_path / "c.add.xml", "other")[0] == [40.0, 3.0]   # non-corridor signal untouched


def test_common_cycle_floors_greens_at_min_green(tmp_path):
    # 20 s cycle: 10 s clearance leaves 10 s for two greens of at least 7 s -> impossible
    with pytest.raises(RuntimeError):
        calibrate.set_common_cycle(_add(tmp_path), tmp_path / "c.add.xml", ["corr"], 20.0, 7.0)
    # 26 s cycle: 16 s of green; proportional 8.7/7.3 keeps both above 7 s; 24 s: 14 s -> 7.6/6.4 so the short green
    # is floored at 7 and the long one takes the rest
    calibrate.set_common_cycle(_add(tmp_path), tmp_path / "c.add.xml", ["corr"], 24.0, 7.0)
    durs, _ = _durations(tmp_path / "c.add.xml", "corr")
    assert durs[3] == 7.0 and durs[0] == pytest.approx(7.0, abs=1e-6) and sum(durs) == pytest.approx(24.0, abs=1e-6)


def test_green_factor_within_a_common_cycle_keeps_the_cycle(tmp_path):
    calibrate.set_common_cycle(_add(tmp_path), tmp_path / "c.add.xml", ["corr"], 90.0, 7.0)
    rep = calibrate.rescale_corridor_green(tmp_path / "c.add.xml", tmp_path / "f.add.xml", {"corr": 0}, 3.0, 7.0, 90.0, 90.0)
    durs, _ = _durations(tmp_path / "f.add.xml", "corr")
    assert sum(durs) == pytest.approx(90.0, abs=0.11)        # cycle preserved (0.1 s rounding)
    assert durs[3] == pytest.approx(7.0, abs=0.11)            # the other green is at the floor
    assert durs[0] == pytest.approx(73.0, abs=0.11) and rep["per_tls"]["corr"]["capped"]   # 3 x 43.6 would exceed the slack


def test_progression_offsets_follow_distance_over_speed():
    positions = [{"tls": "a", "distance_m": 100.0}, {"tls": "b", "distance_m": 100.0 + 11.176 * 40}, {"tls": "c", "distance_m": 100.0 + 11.176 * 130}]
    programs = {"a": ([30, 3, 2, 25, 3, 2], 0), "b": ([25, 3, 2, 30, 3, 2], 3), "c": ([30, 3, 2, 25, 3, 2], 0)}
    offs = calibrate.progression_offsets(positions, programs, 25.0, 90.0)
    assert offs["a"] == 0.0                                   # the first signal's green starts at program time 0
    assert offs["b"] == pytest.approx(40 - 30, abs=0.1)       # arrives after 40 s; its corridor green starts at 30 s
    assert offs["c"] == pytest.approx(130 % 90, abs=0.1)      # wraps modulo the cycle
    assert calibrate.progression_offsets(positions, programs, 0.0, 90.0) == {}


def test_apply_offsets_writes_only_the_offset_attribute(tmp_path):
    rep = calibrate.apply_offsets(_add(tmp_path), tmp_path / "o.add.xml", {"corr": 12.3})
    tls = {t.get("id"): t for t in ET.parse(tmp_path / "o.add.xml").getroot().iter("tlLogic")}
    assert tls["corr"].get("offset") == "12.3" and tls["other"].get("offset") == "0"
    assert _durations(tmp_path / "o.add.xml", "corr") == _durations(_add(tmp_path), "corr")
    assert rep["offsets_s"] == {"corr": 12.3}
    assert calibrate.program_durations(tmp_path / "o.add.xml", {"corr": 3}) == {"corr": ([30, 3, 2, 25, 3, 2], 3)}


def test_grid_cells_skip_offsets_without_a_common_cycle():
    cal = {"grid": {"common_cycles_s": [None, 90, 120], "green_factors": [1.0, 2.0], "progression_speeds_mph": [0, 25]}}
    cells = calibrate.grid_cells(cal)
    assert len(cells) == 2 + 2 * 2 * 2
    assert all(c["progression_speed_mph"] == 0 for c in cells if c["common_cycle_s"] is None)
    assert calibrate.grid_cells({"green_factors": [1.0, 1.2]}) == [
        {"common_cycle_s": None, "green_factor": 1.0, "progression_speed_mph": 0.0},
        {"common_cycle_s": None, "green_factor": 1.2, "progression_speed_mph": 0.0}]   # the v5 shape


def test_choose_factor_tie_break_prefers_the_least_intervention():
    same = {"admissible": True, "speed_mean_mph": 10.5}
    cells = [{**same, "green_factor": 2.0, "common_cycle_s": 120.0, "progression_speed_mph": 25.0},
             {**same, "green_factor": 2.0, "common_cycle_s": 90.0, "progression_speed_mph": 0.0},
             {**same, "green_factor": 2.0, "common_cycle_s": None, "progression_speed_mph": 0.0},
             {**same, "green_factor": 1.5, "common_cycle_s": 120.0, "progression_speed_mph": 25.0},
             {"admissible": False, "speed_mean_mph": 10.95, "green_factor": 1.0, "common_cycle_s": None, "progression_speed_mph": 0.0}]
    c = calibrate.choose_factor(cells, 10.95, 1.5)
    assert c["selected_cell"] == {"green_factor": 1.5, "common_cycle_s": 120.0, "progression_speed_mph": 25.0}
    c = calibrate.choose_factor(cells[:3], 10.95, 1.5)
    assert c["selected_cell"]["common_cycle_s"] is None and c["selected_green_factor"] == 2.0
    far = calibrate.choose_factor([{**same, "speed_mean_mph": 8.1, "green_factor": 3.0, "common_cycle_s": 120.0,
                                    "progression_speed_mph": 25.0}], 10.95, 1.5)
    assert far["selected_cell"] is None and "120 s common cycle, 25.0 mph offsets" in far["reason"]
