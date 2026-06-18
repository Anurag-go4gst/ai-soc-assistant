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


def test_kev_findings_for_query_flags_only_known_exploited():
    """KEV enrichment: referenced CVE IDs that resolve AND carry kev=True are returned."""
    from app.cve.evidence_adapter import kev_findings_for_query

    class _StubStore:
        _rows = {
            "CVE-2024-1111": {"cve_id": "CVE-2024-1111", "kev": True, "kev_date_added": "2024-03-01", "severity": "CRITICAL"},
            "CVE-2024-2222": {"cve_id": "CVE-2024-2222", "kev": False, "severity": "HIGH"},
        }

        def lookup_cve(self, cve_id: str):
            return self._rows.get(cve_id.upper())

    store = _StubStore()
    q = "Investigate the alert citing CVE-2024-1111 and cve-2024-2222 on the EMS host."
    findings = kev_findings_for_query(store, q)
    assert [f["cve_id"] for f in findings] == ["CVE-2024-1111"]  # only the KEV one, normalized
    assert findings[0]["kev_date_added"] == "2024-03-01"
    # Degrades cleanly: no query / no CVE IDs / unknown CVE -> empty.
    assert kev_findings_for_query(store, "") == []
    assert kev_findings_for_query(store, "no cve mentioned") == []
    assert kev_findings_for_query(store, "CVE-2030-9999") == []  # not in snapshot


def test_vulnerability_context_line_surfaces_kev_warning():
    from app.cve.evidence_adapter import vulnerability_context_line

    line = vulnerability_context_line(
        {
            "status": "onboarded_snapshot",
            "snapshot_id": "cve-x",
            "snapshot_age_days": 1,
            "kev_findings": [{"cve_id": "CVE-2024-1111", "kev_date_added": "2024-03-01"}],
        }
    )
    assert "KEV" in line and "CVE-2024-1111" in line and "prioritize" in line.lower()
    # No KEV findings -> base advisory line only, no KEV warning.
    base = vulnerability_context_line(
        {"status": "onboarded_snapshot", "snapshot_id": "cve-x", "kev_findings": []}
    )
    assert "onboarded" in base and "KEV" not in base
