"""Completeness floor: in-catalog under-routes escalate to investigation.

guided_investigation only rescues out-of-catalog hunts; this floor is the safety
net for an investigation-shaped query that maps to an investigation-capable
in-catalog use case but was thin-routed (rag_only/knowledge).
"""
from __future__ import annotations

from app.chat.planning_decision import _apply_completeness_floor


class _CC:
    def __init__(self, status: str, mitre: list[str]):
        self.spl_template_status = status
        self.mitre_candidates = mitre


class _QU:
    def __init__(self, *, shaped: bool = False, alerts: list[str] | None = None):
        self.soc_investigation_shaped = shaped
        self.alert_id = alerts or []


_CAPABLE = _CC("active", ["T1078"])


def test_escalates_investigation_shaped_capable_under_route():
    assert _apply_completeness_floor(
        "rag_only", {"intent_family": "mitre_mapping"}, _CAPABLE, _QU(shaped=True)
    ) == ("hybrid_investigation", True)


def test_escalates_on_concrete_alert_id():
    assert _apply_completeness_floor(
        "generic_soc_guidance", {"intent_family": "mitre_mapping"}, _CAPABLE, _QU(alerts=["NOTABLE-1"])
    ) == ("hybrid_investigation", True)


def test_does_not_escalate_knowledge_or_explanation_families():
    for fam in ("mitre_explanation", "policy_knowledge", "sop_or_playbook", "knowledge_definition"):
        assert _apply_completeness_floor(
            "rag_only", {"intent_family": fam}, _CAPABLE, _QU(shaped=True)
        ) == ("rag_only", False)


def test_does_not_escalate_when_not_investigation_shaped():
    assert _apply_completeness_floor(
        "rag_only", {"intent_family": "mitre_mapping"}, _CAPABLE, _QU()
    ) == ("rag_only", False)


def test_does_not_escalate_without_active_template_or_mitre():
    assert _apply_completeness_floor(
        "rag_only", {"intent_family": "mitre_mapping"}, _CC("planned", ["T1078"]), _QU(shaped=True)
    ) == ("rag_only", False)
    assert _apply_completeness_floor(
        "rag_only", {"intent_family": "mitre_mapping"}, _CC("active", []), _QU(shaped=True)
    ) == ("rag_only", False)


def test_does_not_escalate_clarification_or_nonthin_paths():
    assert _apply_completeness_floor(
        "rag_only", {"intent_family": "mitre_mapping", "requires_clarification": True}, _CAPABLE, _QU(shaped=True)
    ) == ("rag_only", False)
    # non-thin path untouched
    assert _apply_completeness_floor(
        "hybrid_investigation", {"intent_family": "mitre_mapping"}, _CAPABLE, _QU(shaped=True)
    )[1] is False
