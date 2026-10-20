"""Deterministic constraint checks applied to every candidate action (independent of any prompt)."""

from __future__ import annotations

import re

from smartcity import settings
from smartcity.contracts import AdvisoryResponse, CandidateAction, ConstraintResult

FORBIDDEN_TEXT = [
    r"\b(bypass|ignore|override|disable)\b.{0,40}\b(constraint|safety|clearance|pedestrian|rule|validator)",
    r"\b[rgyGrRyYoOsu]{6,}\b",  # raw SUMO signal-state strings
    r"\b(already|has|have)\s+(improved|reduced|cut|lowered)\b",
    r"\b(real|actual)\s+(controller|infrastructure|signal hardware)\b.{0,30}\b(send|apply|push|deploy)",
    r"\bapproved for (real )?deployment\b",
]


def check_candidate(c: CandidateAction, ctx: dict) -> ConstraintResult:
    """ctx keys: network (tls -> {phases: [{index, duration, green: bool, minDur, maxDur}]}),
    mapping_valid, known_evidence_ids, data_fresh, forecast_reliable, retrieval_supported,
    pedestrian_modelled, side_road_measured."""
    sim = settings.load("simulation")["simulation"]
    acts = settings.load("agents")["actions"]
    checks: dict[str, str] = {}
    reasons: list[str] = []

    def setc(name, ok, why=""):
        checks[name] = "PASS" if ok is True else ("NOT_EVALUATED" if ok is None else "FAIL")
        if ok is False:
            reasons.append(f"{name}: {why}")

    setc("network_mapping_valid", bool(ctx.get("mapping_valid")), "no reviewed DOT->SUMO mapping")
    setc("action_type_allowed", c.action_type in acts["allowed"], f"{c.action_type} not allowed")
    tls = ctx.get("network", {})
    needs_signal = c.action_type in ("bounded_green_extension", "select_prevalidated_program")
    if needs_signal:
        setc("signal_exists", c.traffic_light_id in tls, f"unknown traffic light {c.traffic_light_id}")
    else:
        setc("signal_exists", True)
    phases = tls.get(c.traffic_light_id, {}).get("phases", []) if needs_signal else []
    if c.action_type == "bounded_green_extension":
        ph = next((p for p in phases if p["index"] == c.phase_index), None)
        setc("phase_exists", ph is not None, f"phase {c.phase_index} not in program")
        is_green = bool(ph and ph.get("green"))
        if ph is not None and not is_green:
            setc("phase_exists", False, f"phase {c.phase_index} is not a green phase (clearance phases cannot be extended)")
        ext = c.extension_seconds
        b = acts["green_extension_s"]
        setc("parameter_in_bounds", ext is not None and b["min"] <= ext <= b["max"],
             f"extension {ext} outside [{b['min']}, {b['max']}] s")
        if ph is not None and ext is not None:
            new = ph["duration"] + ext
            setc("minimum_green_preserved", new >= sim["min_green_s"], f"{new}s < min green")
            setc("maximum_green_preserved", new <= sim["max_green_s"], f"{new}s > max green {sim['max_green_s']}")
        else:
            setc("minimum_green_preserved", False, "cannot verify without phase")
            setc("maximum_green_preserved", False, "cannot verify without phase")
        setc("clearance_preserved", is_green, "only green phases may change; yellow/all-red untouched")
    elif c.action_type == "select_prevalidated_program":
        progs = tls.get(c.traffic_light_id, {}).get("programs", [])
        setc("phase_exists", c.program_id in progs, f"program {c.program_id} not prevalidated")
        setc("parameter_in_bounds", True)
        setc("minimum_green_preserved", True)
        setc("maximum_green_preserved", True)
        setc("clearance_preserved", True)
    else:  # monitor_only
        for k in ("phase_exists", "parameter_in_bounds", "minimum_green_preserved", "maximum_green_preserved",
                  "clearance_preserved"):
            setc(k, True)
    setc("pedestrian_protection_available", True if ctx.get("pedestrian_modelled") else None)
    setc("side_road_protection_available", bool(ctx.get("side_road_measured")) if needs_signal else True,
         "side-road delay is not measured")
    setc("source_freshness_acceptable", bool(ctx.get("data_fresh")), "stale source data")
    setc("forecast_reliability_acceptable", bool(ctx.get("forecast_reliable")), "uncertainty gate failed")
    known = set(ctx.get("known_evidence_ids", []))
    missing = [e for e in c.evidence_ids if e not in known]
    setc("retrieval_support_acceptable", bool(ctx.get("retrieval_supported")) and not missing and bool(c.evidence_ids),
         f"evidence ids not in retrieved set: {missing}" if missing else "no supporting evidence")
    for pat in FORBIDDEN_TEXT:
        if re.search(pat, c.rationale, flags=re.I):
            checks["rationale_policy"] = "FAIL"
            reasons.append(f"rationale_policy: matched forbidden pattern {pat!r}")
            break
    else:
        checks["rationale_policy"] = "PASS"
    passed = all(v != "FAIL" for v in checks.values())
    return ConstraintResult(candidate_id=c.candidate_id, checks=checks, passed=passed, reasons=reasons)


def check_response(resp: AdvisoryResponse, ctx: dict) -> tuple[list[ConstraintResult], list[str]]:
    errs = []
    if resp.forecast_run_id != ctx.get("forecast_run_id"):
        errs.append(f"unknown forecast_run_id {resp.forecast_run_id}")
    if resp.target_network_id != ctx.get("network_id"):
        errs.append(f"unknown target_network_id {resp.target_network_id}")
    text = " ".join([resp.uncertainty_note, *resp.limitations])
    for pat in FORBIDDEN_TEXT:
        if re.search(pat, text, flags=re.I):
            errs.append(f"response text matched forbidden pattern {pat!r}")
    return [check_candidate(c, ctx) for c in resp.candidates], errs
