"""The simulation gate is deterministic code: a lower per-trip delay must not pass when fewer vehicles complete."""

from smartcity.agents.workflow import candidate_passes

ACC = {"min_delay_improvement_pct": 1.0, "max_side_road_delay_increase_pct": 10.0, "max_teleports": 0,
       "max_completed_trips_decrease_pct": 0.0}


def test_passes_when_delay_improves_and_throughput_is_kept():
    r = {"delay_improvement_pct": 4.0, "side_road_delay_change_pct": 2.0, "teleports_candidate": 0,
         "completed_trips_change_pct": 0.5}
    ok, why = candidate_passes(r, ACC)
    assert ok and "completed trips 0.5%" in why


def test_survivorship_lower_delay_with_fewer_completed_trips_fails():
    r = {"delay_improvement_pct": 10.3, "side_road_delay_change_pct": -4.0, "teleports_candidate": 0,
         "completed_trips_change_pct": -3.5}
    ok, _ = candidate_passes(r, ACC)
    assert not ok


def test_teleports_and_side_road_limits_still_apply():
    base = {"delay_improvement_pct": 5.0, "side_road_delay_change_pct": 0.0, "teleports_candidate": 0,
            "completed_trips_change_pct": 0.0}
    assert candidate_passes(base, ACC)[0]
    assert not candidate_passes(dict(base, teleports_candidate=1), ACC)[0]
    assert not candidate_passes(dict(base, side_road_delay_change_pct=10.1), ACC)[0]
    assert not candidate_passes(dict(base, delay_improvement_pct=0.9), ACC)[0]


def test_older_results_without_completed_field_are_judged_on_the_other_criteria_and_say_so():
    r = {"delay_improvement_pct": 5.0, "side_road_delay_change_pct": 0.0, "teleports_candidate": 0}
    ok, why = candidate_passes(r, ACC)
    assert ok and "not recorded" in why
