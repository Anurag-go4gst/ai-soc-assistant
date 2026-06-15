"""Multi-call MCP orchestration envelope (O5a — contract only).

The singular `execution` object stays the wire summary for existing clients;
`McpOrchestration` is the authoritative multi-call record for lineage and the
future scheduler/reconcile loop (plan A.6). This module defines the models and
the deterministic HIL-approval gate. It performs no I/O and is not wired into
the live pipeline yet (that is O5b/O5c, behind
`MCP_MULTI_CALL_ORCHESTRATION_ENABLED`, default off).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.planner.recipe_registry import RecipeCall

OrchestrationStatus = Literal[
    "planned",
    "awaiting_approval",
    "running",
    "complete",
    "partial",
    "blocked",
    "failed",
    "budget_exhausted",
]

# Classified outcome of one logical call (plan A.10). Empty != failed.
CallOutcome = Literal[
    "ok",
    "empty",
    "failed",
    "timeout",
    "denied",
    "schema_mismatch",
    "partial",
    "blocked",
]

# A search call may execute only when approval is "approved" or, for calls that
# never required HIL, "not_required". "pending"/"rejected" block execution.
ApprovalState = Literal["not_required", "pending", "approved", "rejected"]


class CallBudget(BaseModel):
    max_calls: int = 1
    calls_planned: int = 0
    calls_started: int = 0
    calls_completed: int = 0
    max_wall_time_ms: int | None = None

    def has_call_capacity(self) -> bool:
        return self.calls_started < self.max_calls


class McpCallSpec(BaseModel):
    """A concrete, materialized call awaiting (or cleared for) execution."""

    call_id: str
    sequence: int
    depends_on: list[str] = Field(default_factory=list)
    purpose: str
    call_class: str
    server: str | None = None
    tool: str | None = None
    args_template: dict[str, Any] = Field(default_factory=dict)
    normalized_spl_hash: str | None = None
    required_policy_checks: list[str] = Field(default_factory=list)
    requires_hil: bool = True
    approval_state: ApprovalState = "pending"


class McpCallRecord(BaseModel):
    """The recorded outcome of one logical investigation call.

    Async submit + several polls is ONE record (plan A.3): poll count is bounded
    by the connector lifecycle policy, not counted as new investigation calls.
    """

    call_id: str
    sequence: int
    outcome: CallOutcome
    started_at: float | None = None
    completed_at: float | None = None
    redacted_arguments: dict[str, Any] = Field(default_factory=dict)
    result_envelope_ref: str | None = None
    result_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    error_type: str | None = None


class McpOrchestration(BaseModel):
    schema_version: str = "1"
    orchestration_id: str
    recipe_id: str
    status: OrchestrationStatus = "planned"
    call_budget: CallBudget = Field(default_factory=CallBudget)
    unresolved_evidence_keys: list[str] = Field(default_factory=list)
    calls: list[McpCallRecord] = Field(default_factory=list)
    next_call: McpCallSpec | None = None
    stop_reason: str | None = None


def build_call_spec(
    recipe_call: RecipeCall,
    *,
    sequence: int,
    server: str | None = None,
    tool: str | None = None,
    args_template: dict[str, Any] | None = None,
    normalized_spl_hash: str | None = None,
) -> McpCallSpec:
    """Materialize a recipe call into a concrete spec.

    A call that requires HIL starts `pending` and cannot execute until an
    analyst approves it; a call that never required HIL starts `not_required`.
    """
    return McpCallSpec(
        call_id=recipe_call.call_id,
        sequence=sequence,
        depends_on=list(recipe_call.depends_on),
        purpose=recipe_call.purpose,
        call_class=recipe_call.call_class,
        server=server,
        tool=tool,
        args_template=dict(args_template or {}),
        normalized_spl_hash=normalized_spl_hash,
        required_policy_checks=list(recipe_call.validation_chain),
        requires_hil=recipe_call.requires_hil,
        approval_state="pending" if recipe_call.requires_hil else "not_required",
    )


def can_execute_call(spec: McpCallSpec) -> tuple[bool, str | None]:
    """Deterministic execution gate: a call runs only when cleared.

    Returns (allowed, block_reason). A search-class call additionally requires a
    bound normalized-SPL hash so an approval can never be reused after the SPL
    or arguments change (plan A.7 — scope change invalidates approval).
    """
    if spec.requires_hil and spec.approval_state != "approved":
        return False, f"hil_approval_{spec.approval_state}"
    if spec.approval_state == "rejected":
        return False, "hil_rejected"
    if spec.call_class in ("evidence_search", "investigation_pivot") and not spec.normalized_spl_hash:
        return False, "missing_normalized_spl_hash"
    return True, None


def approve_call(spec: McpCallSpec, *, normalized_spl_hash: str | None = None) -> McpCallSpec:
    """Record analyst approval. If HIL approves, the call may execute.

    Any change to the bound SPL hash after approval re-opens the gate: the new
    spec carries the new hash and the caller must re-approve.
    """
    updated = spec.model_copy(
        update={
            "approval_state": "approved",
            "normalized_spl_hash": normalized_spl_hash or spec.normalized_spl_hash,
        }
    )
    return updated


def reject_call(spec: McpCallSpec) -> McpCallSpec:
    return spec.model_copy(update={"approval_state": "rejected"})
