"""Governed Phase-10 communication draft; never a send authorization."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.chat.contracts.resolved_query import ALLOWED_RECIPIENT_ROLES

SCHEMA_VERSION = "governed_email_draft_v1"


class GovernedEmailDraft(BaseModel):
    """Evidence-bound draft content with unresolved role-only recipients."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["governed_email_draft_v1"] = SCHEMA_VERSION
    status: Literal["draft_ready"] = "draft_ready"
    recipient_roles: list[str] = Field(default_factory=list, max_length=8)
    recipient_resolution_required: Literal[True] = True
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=6000)
    findings: list[str] = Field(default_factory=list, max_length=16)
    evidence_refs: list[str] = Field(default_factory=list, min_length=1, max_length=32)
    generation_source: Literal["deterministic_governed"] = "deterministic_governed"
    llm_attempted: Literal[False] = False
    llm_status: Literal["not_attempted_no_governed_email_role"] = (
        "not_attempted_no_governed_email_role"
    )
    send_authorized: Literal[False] = False
    sent: Literal[False] = False

    @field_validator("recipient_roles", mode="before")
    @classmethod
    def _governed_roles_only(cls, value: object) -> list[str]:
        if not isinstance(value, (list, tuple, set, frozenset)):
            return []
        roles: list[str] = []
        for raw in value:
            role = str(raw or "").strip().lower()
            if role in ALLOWED_RECIPIENT_ROLES and role not in roles:
                roles.append(role)
        return roles

    @field_validator("subject", mode="before")
    @classmethod
    def _single_line_subject(cls, value: object) -> str:
        return " ".join(str(value or "").split())[:240]
