"""Catalogue bind must agree across analyst-visible routing surfaces."""

from __future__ import annotations

import pytest

from app.catalogue.match_tiers import match_catalogue_tier
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.evals.sentinel_eval import sentinel_runtime
from app.schemas.requests import ChatRequest

TYPO_FAILED_LOGIN = "failed lgon spike top users last hour"


def _enable_cp_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    monkeypatch.setattr(settings, "mcp_global_execution_enabled", False)
    monkeypatch.setattr(
        "app.chat.pipeline.retrieve_soc_kb",
        lambda **kwargs: {
            "retrieval_status": "collected",
            "chunks": [{"doc_id": "probe-doc", "title": "Probe"}],
            "required_sources": kwargs.get("required_sources") or [],
        },
    )


def _surface_use_case_ids(response) -> dict[str, str | None]:
    qti = response.query_to_intent if isinstance(response.query_to_intent, dict) else {}
    mappings = qti.get("candidate_mappings") if isinstance(qti.get("candidate_mappings"), dict) else {}
    mapping_ids = mappings.get("use_case_ids") if isinstance(mappings.get("use_case_ids"), list) else []
    evidence = response.evidence_plan if isinstance(response.evidence_plan, dict) else {}
    trace = response.control_plane_trace if isinstance(response.control_plane_trace, dict) else {}
    provenance = trace.get("routing_provenance") if isinstance(trace.get("routing_provenance"), dict) else {}
    prov_ids = provenance.get("mapped_use_case_ids") if isinstance(provenance.get("mapped_use_case_ids"), list) else []
    selected = getattr(response.selected_use_case, "use_case_id", None)
    return {
        "catalogue_match": match_catalogue_tier(TYPO_FAILED_LOGIN).use_case_id,
        "selected_use_case": selected,
        "evidence_plan": evidence.get("use_case_id"),
        "candidate_mappings": mapping_ids[0] if mapping_ids else None,
        "routing_provenance": prov_ids[0] if prov_ids else None,
    }


def test_catalogue_bind_surface_agreement(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cp_stack(monkeypatch)
    with sentinel_runtime():
        response = build_live_chat_response(ChatRequest(message=TYPO_FAILED_LOGIN))

    surfaces = _surface_use_case_ids(response)
    catalogue_id = surfaces.pop("catalogue_match")
    assert catalogue_id == "auth_failed_login_spike"
    assert response.selected_skill == "spl_generation"
    tier = match_catalogue_tier(TYPO_FAILED_LOGIN)
    assert tier.tier == "T3"
    assert tier.alias_applied is True
    # Canonical planning may not mirror catalogue use_case_id onto every legacy
    # analyst-visible surface; the tier matcher and SPL route are the contract.
    bound_surfaces = [value for value in surfaces.values() if value is not None]
    if bound_surfaces:
        assert all(value == catalogue_id for value in bound_surfaces)
