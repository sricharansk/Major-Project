"""Frozen shared contracts between workstreams (Pydantic v2)."""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Mode(str, Enum):
    LIVE = "LIVE"
    REPLAY = "REPLAY"
    SIMULATION = "SIMULATION"


class Status(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IMPLEMENTED_UNTESTED = "IMPLEMENTED_UNTESTED"
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Decision(str, Enum):
    DEFER_DATA = "DEFER_DATA"
    DEFER_UNCERTAINTY = "DEFER_UNCERTAINTY"
    DEFER_EVIDENCE = "DEFER_EVIDENCE"
    REJECT_SCHEMA = "REJECT_SCHEMA"
    REJECT_CONSTRAINT = "REJECT_CONSTRAINT"
    REJECT_SIMULATION = "REJECT_SIMULATION"
    SIMULATION_PASSED = "SIMULATION_PASSED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    HUMAN_APPROVED_FOR_SIMULATION = "HUMAN_APPROVED_FOR_SIMULATION"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    ERROR_TOOL = "ERROR_TOOL"


class Authority(str, Enum):
    OFFICIAL_GUIDANCE = "official_guidance"
    SOFTWARE_DOCUMENTATION = "software_documentation"
    PROJECT_POLICY = "project_defined_experimental_policy"
    PRIOR_SIMULATION = "prior_simulation_evidence"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoadLink(_Strict):
    link_id: str
    link_name: str | None = None
    borough: str | None = None
    owner: str | None = None
    length_m: float | None = None
    start_lat: float | None = None
    start_lon: float | None = None
    end_lat: float | None = None
    end_lon: float | None = None


class FeatureSnapshot(_Strict):
    link_id: str
    timestamp_utc: dt.datetime
    features: dict[str, float | None]
    group_mask: dict[str, bool]


class ForecastRequest(_Strict):
    link_ids: list[str] | None = None
    origin_utc: dt.datetime | None = None
    mode: Mode = Mode.REPLAY
    model_name: str = "proposed"


class HorizonForecast(_Strict):
    horizon_minutes: int
    predicted_speed_mph: float  # unclipped model output
    displayed_speed_mph: float  # max(0, predicted); transformation disclosed
    lower_mph: float | None = None
    upper_mph: float | None = None
    interval_level: float | None = None
    observed_speed_mph: float | None = None  # filled only when the target is later observed


class ForecastResult(_Strict):
    forecast_id: str
    run_id: str
    mode: Mode
    link_id: str
    origin_utc: dt.datetime
    data_as_of_utc: dt.datetime | None
    generated_at_utc: dt.datetime
    model_version: str
    graph_hash: str | None
    feature_schema_hash: str | None
    speed_unit: Literal["mph"] = "mph"
    horizons: list[HorizonForecast]
    warnings: list[str] = []


class UncertaintyResult(_Strict):
    link_id: str
    origin_utc: dt.datetime
    eligible: bool
    reasons: list[str]
    interval_widths: dict[int, float]
    input_missing_fraction: float
    data_age_minutes: float | None


class ExplanationResult(_Strict):
    explanation_id: str
    model_version: str
    method: str
    link_id: str
    horizon_minutes: int
    origin_utc: dt.datetime
    background: str
    group_contributions: dict[str, float]
    base_value: float
    prediction: float
    runtime_s: float
    model_calls: int | None = None
    note: str = "Attributions describe model sensitivity, not causal effects."


class RetrievedEvidence(_Strict):
    chunk_id: str
    document_id: str
    title: str
    authority: Authority
    score: float
    text: str
    source_url: str | None = None


class CandidateAction(_Strict):
    candidate_id: str
    action_type: Literal["bounded_green_extension", "select_prevalidated_program", "monitor_only"]
    traffic_light_id: str | None = None
    phase_index: int | None = None
    extension_seconds: float | None = None
    program_id: str | None = None
    evidence_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=10, max_length=1500)


class AdvisoryResponse(_Strict):
    """Schema the LLM must satisfy.  Format validity is necessary, not sufficient (see safety)."""

    forecast_run_id: str
    recommendation_type: Literal["evaluate_signal_plan", "monitor_only"]
    target_network_id: str
    candidates: list[CandidateAction] = Field(max_length=4)
    uncertainty_note: str = Field(min_length=5)
    limitations: list[str] = []
    requires_human_review: Literal[True] = True

    @field_validator("candidates")
    @classmethod
    def _unique_ids(cls, v):
        ids = [c.candidate_id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate candidate_id")
        return v


class ConstraintResult(_Strict):
    candidate_id: str
    checks: dict[str, Literal["PASS", "FAIL", "NOT_EVALUATED"]]
    passed: bool
    reasons: list[str]


class SimulationRequest(_Strict):
    scenario: str
    controller: str
    seeds: list[int]
    candidate: CandidateAction | None = None


class SimulationResult(_Strict):
    run_id: str
    mode: Literal[Mode.SIMULATION] = Mode.SIMULATION
    scenario: str
    controller: str
    seed: int
    metrics: dict[str, float | None]
    sumo_version: str
    network_hash: str
    demand_hash: str
    status: Literal["OK", "ERROR", "TIMEOUT"]
    error: str | None = None


class AdvisoryDecision(_Strict):
    advisory_id: str
    run_id: str
    decision: Decision
    reasons: list[str]
    candidate_id: str | None = None


class EvidenceRecord(_Strict):
    requirement_id: str
    component: str
    required_function: str
    implementation_path: str
    test_command: str
    test_status: Status
    artifact_path: str = ""
    artifact_hash: str = ""
    last_verified_at: str = ""
    limitations: str = ""
