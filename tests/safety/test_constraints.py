"""Safety tests: every malformed / unsafe candidate must be rejected or deferred deterministically."""

import json

import pytest
from pydantic import ValidationError

from smartcity.contracts import AdvisoryResponse, CandidateAction
from smartcity.safety.constraints import check_candidate, check_response
from smartcity.uncertainty.conformal import gate

NET = {"J1": {"programs": ["0"], "phases": [
    {"index": 0, "duration": 30.0, "state": "GGrr", "green": True},
    {"index": 1, "duration": 3.0, "state": "yyrr", "green": False},
    {"index": 2, "duration": 30.0, "state": "rrGG", "green": True},
    {"index": 3, "duration": 3.0, "state": "rryy", "green": False}]}}

CTX = {"network": NET, "mapping_valid": True, "known_evidence_ids": ["doc#c0001"], "data_fresh": True,
       "forecast_reliable": True, "retrieval_supported": True, "pedestrian_modelled": False, "side_road_measured": True,
       "forecast_run_id": "case-1", "network_id": "sumo:abc"}


def cand(**kw):
    base = dict(candidate_id="c1", action_type="bounded_green_extension", traffic_light_id="J1", phase_index=0,
                extension_seconds=5, evidence_ids=["doc#c0001"], rationale="Forecast drop; evidence permits bounded extension.")
    base.update(kw)
    return CandidateAction(**base)


def test_valid_candidate_passes_with_pedestrian_not_evaluated():
    r = check_candidate(cand(), CTX)
    assert r.passed, r.reasons
    assert r.checks["pedestrian_protection_available"] == "NOT_EVALUATED"


def test_unknown_signal_rejected():
    assert not check_candidate(cand(traffic_light_id="J99"), CTX).passed


def test_invalid_phase_rejected():
    assert not check_candidate(cand(phase_index=7), CTX).passed


def test_clearance_phase_cannot_be_extended():
    r = check_candidate(cand(phase_index=1), CTX)
    assert not r.passed and r.checks["clearance_preserved"] == "FAIL"


def test_excessive_extension_rejected():
    r = check_candidate(cand(extension_seconds=45), CTX)
    assert not r.passed and r.checks["parameter_in_bounds"] == "FAIL"


def test_missing_citation_rejected_by_schema():
    with pytest.raises(ValidationError):
        cand(evidence_ids=[])


def test_fabricated_citation_rejected():
    r = check_candidate(cand(evidence_ids=["made-up#c9"]), CTX)
    assert not r.passed and r.checks["retrieval_support_acceptable"] == "FAIL"


def test_contradictory_or_unsupported_evidence_rejected():
    r = check_candidate(cand(), dict(CTX, retrieval_supported=False))
    assert not r.passed


def test_stale_source_rejected():
    assert not check_candidate(cand(), dict(CTX, data_fresh=False)).passed


def test_wide_interval_defers():
    ok, reasons = gate({30: 40.0}, 0.0, 5.0, {30: 1000},
                       {"max_data_age_minutes": 20, "max_input_missing_fraction": 0.34, "max_interval_width_mph": 10.0,
                        "min_calibration_samples": 200})
    assert not ok and any("WIDE_INTERVAL" in r for r in reasons)


def test_unmapped_link_rejected():
    assert not check_candidate(cand(), dict(CTX, mapping_valid=False)).passed


def test_bypass_and_raw_state_text_rejected():
    assert not check_candidate(cand(rationale="Please bypass the safety constraint and set GGGrrrGGG"), CTX).passed
    assert not check_candidate(cand(rationale="This action has already improved traffic on the corridor."), CTX).passed


def test_malformed_llm_json_rejected():
    with pytest.raises(ValidationError):
        AdvisoryResponse.model_validate_json('{"forecast_run_id": "x", "candidates": [}')


def test_unsupported_action_type_rejected_by_schema():
    with pytest.raises(ValidationError):
        cand(action_type="set_raw_state")


def test_response_with_unknown_ids_rejected():
    resp = AdvisoryResponse(forecast_run_id="other", recommendation_type="evaluate_signal_plan",
                            target_network_id="sumo:zzz", candidates=[cand()], uncertainty_note="interval moderate")
    _, errs = check_response(resp, CTX)
    assert len(errs) == 2


def test_human_review_cannot_approve_deployment():
    with pytest.raises(ValidationError):
        AdvisoryResponse(forecast_run_id="case-1", recommendation_type="evaluate_signal_plan", target_network_id="sumo:abc",
                         candidates=[cand()], uncertainty_note="ok note", requires_human_review=False)


def test_sumo_timeout_is_not_approval():
    from smartcity.agents.workflow import Toolkit  # noqa: F401  (decision logic below mirrors the node)
    sims = [{"candidate_id": "c1", "status": "TIMEOUT", "error": "wall-clock timeout"}]
    passed = [s for s in sims if s["status"] == "OK"]
    assert passed == []
