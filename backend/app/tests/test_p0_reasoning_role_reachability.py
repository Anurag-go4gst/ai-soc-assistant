"""P0 — reasoning-role reachability audit (investigation_planner allowlist)."""

from __future__ import annotations

from typing import Any

import pytest

from app.chat.guided_investigation_plan_llm import INVESTIGATION_PLAN_ROLE
from app.chat.investigation_plan_delta_reasoner import PLAN_DELTA_ROLE
from app.config import settings
from app.llm.mitre_risk_rationale import MITRE_REASONER_ROLE, RISK_RATIONALE_ROLE
from app.llm.registry_settings import ROLE_DEFAULTS
from app.llm.sidecar_clients import _REASONING_ALLOWED_ROLES, build_failover_client_for_role
from app.llm.sidecar_governance import REASONING_REJECTION_MATCHING, resolve_sidecar_role_status

AUDIT_ROLES = (
    MITRE_REASONER_ROLE,
    "missing_evidence_reasoner",
    RISK_RATIONALE_ROLE,
    PLAN_DELTA_ROLE,
    INVESTIGATION_PLAN_ROLE,
)


def _preferred_model(role: str) -> str | None:
    entry = next((item for item in ROLE_DEFAULTS if item.get("role") == role), None)
    return str(entry.get("preferred_model") or "").strip() or None if entry else None


def _reachability(role: str) -> dict[str, Any]:
    allowed = role in _REASONING_ALLOWED_ROLES
    status = resolve_sidecar_role_status(
        role,
        reasoning_rejection_reason=REASONING_REJECTION_MATCHING,
        allow_reasoning=allowed,
    )
    client = build_failover_client_for_role(role)
    if allowed and status.enabled:
        posture = "reachable_when_llm_enabled"
    elif status.rejected_reason == REASONING_REJECTION_MATCHING:
        posture = "blocked_by_reasoning_allowlist"
    elif not settings.ai_soc_llm_enabled or settings.ai_soc_llm_mode.strip().lower() == "disabled":
        posture = "flag_off_or_llm_disabled"
    elif status.llm_assist_skipped_reason:
        posture = status.llm_assist_skipped_reason
    else:
        posture = "instruct_path_or_role_disabled"
    return {
        "role": role,
        "preferred_model": _preferred_model(role),
        "reasoning_allowlisted": allowed,
        "enabled": status.enabled,
        "rejected_reason": status.rejected_reason,
        "client_built": client is not None,
        "posture": posture,
    }


@pytest.fixture
def role_matrix(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    return [_reachability(role) for role in AUDIT_ROLES]


def test_investigation_planner_is_only_reasoning_allowlist_member() -> None:
    assert _REASONING_ALLOWED_ROLES == frozenset({INVESTIGATION_PLAN_ROLE})


def test_role_reachability_matrix_documents_current_posture(role_matrix: list[dict[str, Any]]) -> None:
    by_role = {row["role"]: row for row in role_matrix}
    planner = by_role[INVESTIGATION_PLAN_ROLE]
    assert planner["reasoning_allowlisted"] is True
    assert planner["preferred_model"]
    # Audit-only: allowlist permits reasoning; live reachability still needs a configured provider.
    assert planner["posture"] in {
        "reachable_when_llm_enabled",
        "no_provider_configured",
        "role_not_enabled",
        "flag_off_or_llm_disabled",
    }
    assert planner["rejected_reason"] is None

    for blocked_role in (MITRE_REASONER_ROLE, "missing_evidence_reasoner", RISK_RATIONALE_ROLE, PLAN_DELTA_ROLE):
        row = by_role[blocked_role]
        assert row["reasoning_allowlisted"] is False
        assert row["posture"] == "blocked_by_reasoning_allowlist"
        assert row["rejected_reason"] == REASONING_REJECTION_MATCHING
        assert row["client_built"] is False
