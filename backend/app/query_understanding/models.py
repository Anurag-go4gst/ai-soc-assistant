from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RequestedOutputType(str, Enum):
    INVESTIGATION = "investigation"
    SPL = "spl"
    SOP = "sop"
    MITRE_MAPPING = "mitre_mapping"
    SUMMARY = "summary"
    NOTE = "note"
    ACTION_PLAN = "action_plan"
    CLARIFICATION = "clarification"


class OutputTemplate(str, Enum):
    INVESTIGATION_ANSWER = "investigation_answer"
    SPL_RESPONSE = "spl_response"
    SOP_RESPONSE = "sop_response"
    MITRE_MAPPING_RESPONSE = "mitre_mapping_response"
    CLARIFICATION_RESPONSE = "clarification_response"
    NOTE_RESPONSE = "note_response"


class QueryEntities(BaseModel):
    asset: list[str] = Field(default_factory=list)
    host: list[str] = Field(default_factory=list)
    user: list[str] = Field(default_factory=list)
    source_ip: list[str] = Field(default_factory=list)
    destination_ip: list[str] = Field(default_factory=list)
    time_window: str | None = None
    index: list[str] = Field(default_factory=list)
    sourcetype: list[str] = Field(default_factory=list)
    alert_id: list[str] = Field(default_factory=list)
    event_type: list[str] = Field(default_factory=list)


class QueryUnderstandingResult(BaseModel):
    raw_query: str
    normalized_query: str
    primary_intent: str
    secondary_intents: list[str] = Field(default_factory=list)
    requested_output_type: RequestedOutputType
    output_template: OutputTemplate
    entities: QueryEntities
    ambiguity_flags: list[str] = Field(default_factory=list)
    confidence: float
    clarification_needed: bool = False
    clarification_question: str | None = None
    mapped_use_case_ids: list[str] = Field(default_factory=list)
