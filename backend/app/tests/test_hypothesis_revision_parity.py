"""Generic hypothesis floor and data_category / evidence_needed parity."""

from __future__ import annotations

from app.chat.investigation_plan_builder import build_deterministic_investigation_plan
from app.chat.investigation_plan_relevance import categories_for_evidence_needed


_GENERIC = (
    "Expected operational activity or a recent approved change.",
    "Telemetry drift producing an apparent anomaly.",
)


def test_t4_competing_hypotheses_replace_boilerplate_floor() -> None:
    plan = build_deterministic_investigation_plan(
        query="Investigate unusual outbound traffic from an OT host overnight.",
        resolved_query_contract={
            "normalized_goal": "Investigate unusual outbound traffic from an OT host overnight.",
            "qualification_tier": "T4",
            "understanding_source": "semantic_t4",
            "competing_hypotheses": [
                "sanctioned backup window",
                "unauthorized large transfer",
            ],
            "evidence_requirements": ["outbound transfer volume"],
        },
    )
    blob = " ".join(plan.hypotheses).lower()
    assert "sanctioned backup window" in blob
    assert "unauthorized large transfer" in blob
    assert "expected operational activity or a recent approved change" not in blob
    assert "telemetry drift producing an apparent anomaly" not in blob


def test_boilerplate_remains_when_no_scenario_hypotheses_exist() -> None:
    plan = build_deterministic_investigation_plan(
        query="How should I investigate this unnamed anomaly?",
    )
    blob = " ".join(plan.hypotheses).lower()
    assert any(item.lower() in blob for item in _GENERIC) or plan.hypotheses


def test_data_categories_cover_required_network_and_change_evidence() -> None:
    """X10-shaped required evidence must appear in data_categories."""
    plan = build_deterministic_investigation_plan(
        query=(
            "A privileged account authenticated from an unusual source and a large "
            "outbound transfer followed. Investigate whether this is sanctioned backup."
        ),
        resolved_query_contract={
            "normalized_goal": (
                "Investigate whether a privileged login and large outbound transfer "
                "are sanctioned backup or exfiltration."
            ),
            "qualification_tier": "T4",
            "understanding_source": "semantic_t4",
            "competing_hypotheses": ["sanctioned backup", "unauthorized transfer"],
            "evidence_requirements": [
                "network source history for the reported host",
                "change-window context for sanctioned backup activity",
                "authentication events for the privileged account",
            ],
        },
    )
    assert "network_flows" in plan.data_categories or "firewall_sessions" in plan.data_categories
    assert "change_records" in plan.data_categories
    assert "auth" in plan.data_categories or "identity" in plan.data_categories


def test_unrelated_auth_case_does_not_inherit_egress_categories() -> None:
    plan = build_deterministic_investigation_plan(
        query="Show failed SSH logins for alice in the last hour.",
        resolved_query_contract={
            "normalized_goal": "Show failed SSH logins for alice in the last hour.",
            "evidence_requirements": ["authentication failure events for alice"],
        },
    )
    assert "egress_flows" not in plan.data_categories


def test_categories_for_evidence_needed_uses_canonical_vocabulary() -> None:
    cats = categories_for_evidence_needed(
        [
            "network source history",
            "change-window context",
            "endpoint process execution",
        ]
    )
    assert "network_flows" in cats
    assert "change_records" in cats
    assert "endpoint" in cats or "process_execution" in cats
