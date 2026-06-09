from __future__ import annotations

from app.chat.guidance_templates import (
    build_conceptual_mitre_guidance,
    build_unsafe_action_guidance,
    is_conceptual_mitre_confirm_query,
)
from app.threat.mitre_decision import resolve_mitre_decision
from app.threat.mitre_evidence_preconditions import (
    cap_mitre_status_for_evidence_tier,
    resolve_evidence_tier,
)
from app.threat.mitre_registry_schema import MitreRegistryMetadata


def _metadata() -> MitreRegistryMetadata:
    return MitreRegistryMetadata(
        mitre_permitted=["T1110", "T1110.001"],
        mitre_candidate=["T1110.003"],
        mitre_blocked=[],
        mitre_requires_evidence=True,
        mitre_requires_alert_context=False,
        mapping_rationale="test",
    )


def test_signal_only_tier_caps_evidence_supported() -> None:
    tier = resolve_evidence_tier(
        source_evidence=[{"source_type": "manual", "collection_status": "skipped"}],
        execution={"status": "skipped"},
    )
    assert tier != "source_grounded"
    assert cap_mitre_status_for_evidence_tier("evidence_supported", tier) in {"candidate", "requires_validation"}


def test_executed_mcp_yields_source_grounded_tier() -> None:
    tier = resolve_evidence_tier(
        source_evidence=[
            {
                "source_type": "splunk_mcp",
                "collection_status": "collected",
                "warnings": [],
            }
        ],
        execution={"status": "executed"},
    )
    assert tier == "source_grounded"
    assert cap_mitre_status_for_evidence_tier("evidence_supported", tier) == "evidence_supported"


def test_failed_login_spike_query_signals_do_not_upgrade_without_execution() -> None:
    decision = resolve_mitre_decision(
        registry_metadata=_metadata(),
        use_case_id="auth_failed_login_spike",
        intent_classification={
            "intent_family": "hybrid_alert_review",
            "answer_goal": ["mitre_mapping"],
            "requires_clarification": False,
        },
        evidence_plan={"answer_mode": "hybrid"},
        negative_evidence={"present_evidence": ["failed_login_pattern"]},
        execution={"status": "skipped"},
        source_evidence=[{"source_type": "manual", "collection_status": "skipped"}],
    )
    statuses = {item["technique_id"]: item["status"] for item in decision.techniques}
    assert "evidence_supported" not in set(statuses.values())


def test_conceptual_mitre_guidance_direct_negation() -> None:
    text = build_conceptual_mitre_guidance(
        "Is unusual DNS traffic alone enough to confirm command and control?"
    )
    assert "not enough to confirm" in text.lower()
    assert is_conceptual_mitre_confirm_query(
        "Is unusual DNS traffic alone enough to confirm command and control?"
    )


def test_unsafe_action_guidance_blocks_execution() -> None:
    text = build_unsafe_action_guidance().lower()
    assert "was performed" in text or "not executed" in text
    assert "hil" in text or "approval" in text
    assert "blocked" in text or "not authorized" in text
