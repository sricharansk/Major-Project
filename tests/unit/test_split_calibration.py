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
