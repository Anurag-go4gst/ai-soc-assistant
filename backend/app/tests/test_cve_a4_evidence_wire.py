"""Plan §3 A4: CVE snapshot store wired into the evidence-loop trace.

Asserts the deterministic resolver: None when no CVE requirement, fail-closed
not_onboarded by default, onboarded_snapshot when an operator package is configured.
Routing is unchanged (CVE stays a capability gap); this only enriches provenance.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.chat import pipeline
from app.chat.evidence_loop import cve_requirements_present

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cve"


def test_predicate_detects_cve_class_requirements():
    assert cve_requirements_present(["vulnerability_source"]) is True
    assert cve_requirements_present(["cve_correlation", "failed_logins"]) is True
    assert cve_requirements_present(["failed_logins", "src"]) is False
    assert cve_requirements_present([]) is False
    assert cve_requirements_present(None) is False


def test_resolver_none_without_cve_requirement():
    state = {"mcp_required_produces": ["failed_logins", "src"]}
    assert pipeline._resolve_vulnerability_source_status(state) is None


def test_resolver_not_onboarded_by_default(monkeypatch):
    # Default posture: no package configured -> fail-closed not_onboarded.
    monkeypatch.setattr("app.cve.evidence_adapter.settings.ai_soc_cve_snapshot_dir", "", raising=False)
    state = {"mcp_required_produces": ["vulnerability_source"]}
    result = pipeline._resolve_vulnerability_source_status(state)
    assert result is not None
    assert result["status"] == "not_onboarded"
    assert result["limitation"]


def test_resolver_onboarded_when_package_configured(monkeypatch):
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
    state = {"mcp_required_produces": ["unpatched_cve_correlation"]}
    result = pipeline._resolve_vulnerability_source_status(state)
    assert result is not None
    assert result["status"] == "onboarded_snapshot"
    assert result["snapshot_id"] == "cve-fixture-2026-06-16"
    assert result["provenance"]["signer_id"] == "fixture-signer"


def test_resolver_uses_evidence_plan_when_loop_state_absent(monkeypatch):
    monkeypatch.setattr("app.cve.evidence_adapter.settings.ai_soc_cve_snapshot_dir", "", raising=False)
    state = {"evidence_plan": {"missing_evidence": ["vulnerability_source"]}}
    result = pipeline._resolve_vulnerability_source_status(state)
    assert result is not None
    assert result["status"] == "not_onboarded"


def test_vulnerability_context_line_surfaces_status():
    """A4b: CVE status renders as an advisory analyst-card line (not a confirmed claim)."""
    from app.cve.evidence_adapter import vulnerability_context_line

    onboarded = vulnerability_context_line(
        {"status": "onboarded_snapshot", "snapshot_id": "cve-x", "snapshot_age_days": 2}
    )
    assert onboarded and "onboarded" in onboarded
    assert "join keys" in onboarded  # never a confirmed unpatched-CVE claim
    assert "stale" in vulnerability_context_line({"status": "stale", "snapshot_id": "cve-x"})
    assert "not onboarded" in vulnerability_context_line({"status": "not_onboarded"})
    assert vulnerability_context_line(None) is None
    assert vulnerability_context_line({}) is None


def test_cve_evidence_item_satisfies_source_evidence_envelope():
    """Regression: the appended CVE item must validate against SourceEvidenceEnvelope,
    else a CVE-triggering /chat turn fails response validation (caught in live smoke)."""
    from app.cve.evidence_adapter import append_cve_snapshot_source_evidence
    from app.schemas.responses import SourceEvidenceEnvelope

    items = append_cve_snapshot_source_evidence(
        [], trace_id="trace-x", evidence_plan={"optional_evidence_keys": ["vulnerability_source"]}
    )
    assert len(items) == 1
    # Must not raise — all required envelope fields present.
    env = SourceEvidenceEnvelope(**items[0])
    assert env.source_name == "vulnerability_source"
    assert env.trace_id == "trace-x"
