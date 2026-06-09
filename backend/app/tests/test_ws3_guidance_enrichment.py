from __future__ import annotations

from app.use_cases.content_enrichment import get_guidance_only_enrichment_projection


def test_guidance_projection_scrubs_evidence_supported_phrasing() -> None:
    projection = get_guidance_only_enrichment_projection("dns_beaconing_candidate")
    assert projection is not None
    joined = " ".join(projection.get("investigation_workflow") or [])
    assert "evidence-supported" not in joined.lower()
    assert "source-grounded" in joined.lower()


def test_guidance_only_projection_strips_spl_approval_fields() -> None:
    projection = get_guidance_only_enrichment_projection("auth_failed_login_spike")
    assert projection is not None
    assert projection.get("guidance_only") is True
    assert projection.get("allowed_spl_templates") == []
    assert projection.get("spl_template_status") == "unavailable"
    assert projection.get("analyst_checklist")


def test_guidance_projection_has_no_runtime_active_claim() -> None:
    projection = get_guidance_only_enrichment_projection("auth_success_after_failure")
    assert projection is not None
    assert projection.get("activation_lifecycle_stage") == "guidance_only_projection"
