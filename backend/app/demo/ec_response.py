"""Experience Center envelope — /demo only. Not a production /chat schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProvenanceKind = Literal[
    "experience_center_fixture",
    "ec_scenario_policy",
    "production_validator_read_only",
    "simulated_mcp",
    "simulated_rag",
    "simulated_llm",
    "simulated_phase10_action",
    "ec_fixture_selected",
]


class EcProvenanceStamp(BaseModel):
    kind: ProvenanceKind
    detail: str | None = None


class EcProjectionView(BaseModel):
    title: str
    summary: str
    items: list[str] = Field(default_factory=list)
    provenance: EcProvenanceStamp


class EcProjection(BaseModel):
    """Architecture-shaped views for Layer 2. Not production InvestigationOutcome."""

    understanding: EcProjectionView
    resource_plan: EcProjectionView
    phase_contract: EcProjectionView
    evidence_state: EcProjectionView
    investigation_outcome: EcProjectionView
    provenance: EcProvenanceStamp


class EcFollowUpChip(BaseModel):
    follow_up_id: str
    label: str
    advances_state: bool = True


class EcSessionState(BaseModel):
    session_id: str | None = None
    family: str
    scenario_id: str
    turn: int = 0
    pending_action_id: str | None = None
    awaiting_external: bool = False
    applied_follow_up_ids: list[str] = Field(default_factory=list)


class EcActionRecord(BaseModel):
    action_id: str
    kind: str
    label: str
    state: str
    provenance: Literal["simulated_phase10_action"] = "simulated_phase10_action"
    production_side_effect: bool = False
    receipt: dict[str, Any] | None = None
    verify_result: dict[str, Any] | None = None


class ExperienceCenterResponse(BaseModel):
    """EC-owned /demo envelope. Extra keys may pass through for the frozen picker client."""

    model_config = ConfigDict(extra="allow")

    scenario_id: str
    trace_id: str
    message: str
    note: str | None = None
    demo_mode: bool = True
    analyst_summary: str | None = None
    analyst: dict[str, Any] | None = None
    analyst_response: dict[str, Any] | None = None
    selected_skill: str | None = None
    route_source: str = "ec_fixture_selected"
    candidate_spl: dict[str, Any] | None = None
    spl_validation: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    human_review: dict[str, Any] | None = None
    source_evidence: list[Any] = Field(default_factory=list)
    ec_stage_latencies: list[Any] | None = None
    ec_projection: EcProjection
    ec_actions: list[EcActionRecord] = Field(default_factory=list)
    ec_followups: list[EcFollowUpChip] = Field(default_factory=list)
    ec_session_state: EcSessionState
    ec_provenance: dict[str, Any]
