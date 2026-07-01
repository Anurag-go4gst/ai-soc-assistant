"""S6b — P3–P7 pilot enrichment wiring."""

from __future__ import annotations

from app.use_cases.content_enrichment import get_content_enrichment


PILOTS = (
    "email_phishing_header_review",
    "edr_powershell_suspicious_command",
    "dns_beaconing_candidate",
    "critical_notable_mitre_review",
    "endpoint_ransomware_impact_review",
)


def test_pilot_enrichment_blocks_present() -> None:
    for use_case_id in PILOTS:
        record = get_content_enrichment(use_case_id)
        assert record is not None, use_case_id
        assert record.get("evidence_requirements")
        assert record.get("limitations")
        assert record.get("answer_rules")


def test_pilot_enrichment_has_no_offensive_scripts() -> None:
    for use_case_id in PILOTS:
        record = get_content_enrichment(use_case_id) or {}
        blob = str(record).lower()
        for forbidden in ("execute malware", "run exploit", "dropper payload"):
            assert forbidden not in blob


def test_pilot_mitre_are_candidates_only() -> None:
    for use_case_id in PILOTS:
        record = get_content_enrichment(use_case_id) or {}
        assert "confirmed_mitre" not in str(record.get("answer_rules") or []).lower()


def test_github_refs_are_provenance_only() -> None:
    record = get_content_enrichment("email_phishing_header_review") or {}
    refs = record.get("github_reference_skills") or []
    assert refs
    for ref in refs:
        assert isinstance(ref, dict)
        assert ref.get("decision") == "accepted"
        assert "SKILL.md" in str(ref.get("path") or "")
