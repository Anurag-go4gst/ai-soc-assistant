"""S3 — flag-gated runtime content enrichment loader."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.use_cases.content_enrichment import (
    UseCaseContentEnrichment,
    get_content_enrichment,
    load_skill_enrichment,
    runtime_enrichment_activation_allowed,
)


def test_runtime_enrichment_flag_off_blocks_loader(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_runtime_enrichment_enabled", False)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", False)
    assert runtime_enrichment_activation_allowed("auth_failed_login_spike") is False
    assert load_skill_enrichment("auth_failed_login_spike") is None


def test_runtime_enrichment_alias_flag_loads_p1(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_runtime_enrichment_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_curated_enrichment_activation_enabled", False)
    ctx = load_skill_enrichment("auth_failed_login_spike")
    assert ctx is not None
    assert isinstance(ctx, UseCaseContentEnrichment)
    assert ctx.use_case_id == "auth_failed_login_spike"
    assert ctx.evidence_requirements


def test_runtime_enrichment_loads_p2_dns_beaconing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_runtime_enrichment_enabled", True)
    ctx = load_skill_enrichment("dns_beaconing_candidate")
    assert ctx is not None
    assert "T1071" in ctx.mitre_candidates


def test_missing_enrichment_does_not_break_loader() -> None:
    assert load_skill_enrichment("nonexistent_use_case_xyz") is None


def test_github_markdown_never_loaded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_runtime_enrichment_enabled", True)
    record = get_content_enrichment("email_phishing_header_review")
    assert record is not None
    assert "SKILL.md" in str(record.get("github_reference_skills") or "")
    ctx = load_skill_enrichment("email_phishing_header_review")
    if ctx is not None:
        dumped = ctx.model_dump_json()
        assert "SKILL.md" not in dumped
        assert "Anthropic-Cybersecurity-Skills" not in dumped


def test_provenance_refs_are_ids_not_markdown(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_runtime_enrichment_enabled", True)
    from app.use_cases.content_enrichment import llm_facing_curated_enrichment_projection

    ctx = load_skill_enrichment("edr_powershell_suspicious_command")
    if ctx is not None:
        projection = llm_facing_curated_enrichment_projection(ctx)
        assert projection is not None
        blob = str(projection)
        assert "SKILL.md" not in blob
        assert "Anthropic-Cybersecurity-Skills" not in blob
