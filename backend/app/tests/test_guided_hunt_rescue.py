"""WS-F guided-hunt grounding wire + CVE A4 evidence adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.chat.guided_hunt_grounding import (
    build_guided_hunt_grounding,
    detection_families_for_question,
    guided_hunt_grounding_trace,
    skill_refs_for_question,
    soc_kb_refs_from_retrieval,
)
from app.cve.evidence_adapter import (
    append_cve_snapshot_source_evidence,
    resolve_vulnerability_source_status,
    vulnerability_source_from_evidence,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cve"


def test_soc_kb_refs_are_refs_only() -> None:
    refs = soc_kb_refs_from_retrieval(
        {
            "retrieved_entries": [
                {"entry_id": "kb-001", "title": "DNS beaconing checklist"},
            ]
        }
    )
    assert refs == ["kb-001:DNS beaconing checklist"]


def test_skill_refs_match_register_metadata() -> None:
    refs = skill_refs_for_question("investigate cobalt strike beaconing on endpoints")
    assert any(ref.startswith("github_skill:") for ref in refs)


def test_detection_families_from_question() -> None:
    families = detection_families_for_question("suspicious dns beacon to rare domain")
    assert "dns_beaconing_candidate" in families


def test_build_guided_hunt_grounding_carries_unverified_banner() -> None:
    block = build_guided_hunt_grounding(
        query="hunt prompt injection against our llm endpoint",
    )
    trace = guided_hunt_grounding_trace(block)
    assert trace["advisory_only"] is True
    assert "unverified" in trace["unverified_banner"].lower()
    assert any("unverified" in item.lower() for item in block.limitations)
    assert block.ai_threat_signal is True


def test_cve_adapter_not_onboarded_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.cve.evidence_adapter.settings.ai_soc_cve_snapshot_dir", "", raising=False)
    status = resolve_vulnerability_source_status(
        evidence_plan={"missing_evidence": ["vulnerability_source"]},
    )
    assert status is not None
    assert status["status"] == "not_onboarded"


def test_cve_adapter_appends_source_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.cve.evidence_adapter.settings.ai_soc_cve_snapshot_dir", "", raising=False)
    evidence = append_cve_snapshot_source_evidence(
        [],
        trace_id="trace-1",
        evidence_plan={"missing_evidence": ["cve_correlation"]},
    )
    assert len(evidence) == 1
    assert evidence[0]["source_name"] == "vulnerability_source"
    assert evidence[0]["collection_status"] == "blocked"
    assert vulnerability_source_from_evidence(evidence)["status"] == "not_onboarded"


def test_cve_adapter_onboarded_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.cve.evidence_adapter.settings.ai_soc_cve_snapshot_dir",
        str(FIXTURE_DIR),
        raising=False,
    )
    monkeypatch.setattr(
        "app.cve.evidence_adapter.settings.ai_soc_cve_snapshot_stale_after_days",
        100000,
        raising=False,
    )
    evidence = append_cve_snapshot_source_evidence(
        [],
        trace_id="trace-2",
        evidence_plan={"required_produces": ["unpatched_cve_correlation"]},
    )
    payload = vulnerability_source_from_evidence(evidence)
    assert payload is not None
    assert payload["status"] == "onboarded_snapshot"
    assert evidence[0]["collection_status"] == "collected"
