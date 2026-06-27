"""Batch D — SPL artifact degrade-chain trace projection (read model only)."""

from __future__ import annotations

from app.spl.spl_artifact_trace_projection import build_spl_artifact_handoff_summary


def test_governed_template_path_projects_cleanly() -> None:
    summary = build_spl_artifact_handoff_summary(
        candidate_spl={
            "generation_mode": "governed_template",
            "selected_candidate_spl_provider": "spl_template",
            "candidate_spl": "search index=auth earliest=-24h | stats count",
            "execution_eligible": False,
        },
        spl_validation={
            "approved": True,
            "normalized_spl": "search index=auth earliest=-24h | stats count",
            "selected_candidate_spl_provider": "spl_template",
            "candidate_provider_reason": "use_case_catalog_default_raw_template",
        },
    )
    assert summary["spl_artifact_status"] == "governed_template_candidate"
    assert summary["governed_template_bound"] is True
    assert summary["review_only"] is True
    assert summary["execution_eligible"] is False
    assert summary["trace_authority"] == "read_model_projection_only"


def test_t2_native_meta_path_projects_cleanly() -> None:
    summary = build_spl_artifact_handoff_summary(
        candidate_spl={
            "generation_mode": "t2_spl_native_review",
            "selected_candidate_spl_provider": "t2_spl_native",
            "candidate_spl": "index=scada_perf earliest=-30d | stats count",
            "execution_eligible": False,
            "t2_spl_native": {"source_profile": "scada_perf"},
        },
        spl_validation={
            "approved": False,
            "review_required_reason": "t2_spl_native_review_only",
            "selected_candidate_spl_provider": "t2_spl_native",
        },
    )
    assert summary["spl_artifact_status"] == "t2_native_review_only"
    assert summary["t2_native_shape"] is True
    assert summary["must_not_execute_reason"] == "t2_spl_native_review_only"


def test_lab_preview_path_projects_cleanly() -> None:
    summary = build_spl_artifact_handoff_summary(
        candidate_spl={
            "generation_mode": "deterministic_lab_draft",
            "execution_eligible": False,
        },
        spl_validation={"approved": False},
        spl_draft_preview={
            "draft_spl": "index=wineventlog earliest=-7d | stats count",
            "generation_mode": "user_bound_skeleton",
        },
    )
    assert summary["spl_artifact_status"] == "lab_preview_review_only"
    assert summary["lab_preview_used"] is True
    assert summary["review_only"] is True


def test_llm_failover_projects_advisory_only() -> None:
    summary = build_spl_artifact_handoff_summary(
        candidate_spl={
            "generation_mode": "llm_fallback",
            "llm_fallback_used": True,
            "execution_eligible": False,
            "candidate_provider_reason": "template_miss_llm_advisory_fallback",
        },
        spl_validation={
            "approved": False,
            "llm_fallback_used": True,
            "llm_fallback_status": "lab_candidate",
        },
    )
    assert summary["spl_artifact_status"] == "llm_failover_advisory"
    assert summary["llm_failover_used"] is True
    assert summary["execution_eligible"] is False
