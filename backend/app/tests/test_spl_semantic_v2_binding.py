"""S2 — Final RQC and governed source mappings bind into the existing SPL spec."""

from __future__ import annotations

from types import SimpleNamespace

from app.spl.request_authority import (
    build_deterministic_request_contract,
    check_template_semantic_fidelity,
)
from app.spl.source_profile_bindings import source_mappings_for_query
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.user_constraint_bindings import build_user_constraint_bindings
from app.spl.utility_spl_authoring import _build_authoring_intent_spec, _build_utility_llm_context


def test_auth_source_profile_fills_blank_index(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.spl.source_profile_bindings.load_persisted_source_profile_document",
        lambda: {
            "values": {"auth_index": "coe_auth", "auth_sourcetype": "winevent:security"},
            "field_sources": {"auth_index": "coe_ui", "auth_sourcetype": "coe_ui"},
        },
    )
    mappings = source_mappings_for_query("hourly failed-login trend over the last 24 hours")
    assert mappings["index"] == "coe_auth"
    assert mappings["sourcetype"] == "winevent:security"
    spec = _build_authoring_intent_spec("hourly failed-login trend over the last 24 hours")
    assert spec["source_constraints"]["index"] == "coe_auth"
    assert spec["field_provenance"]["source_constraints.index"] == "source_mapping"


def test_explicit_user_index_wins_over_source_profile(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.spl.source_profile_bindings.load_persisted_source_profile_document",
        lambda: {
            "values": {"auth_index": "coe_auth", "auth_sourcetype": "winevent:security"},
            "field_sources": {},
        },
    )
    spec = _build_authoring_intent_spec(
        "hourly failed-login trend over the last 24 hours index=user_named_index"
    )
    assert spec["source_constraints"]["index"] == "user_named_index"
    assert spec["source_constraints"]["sourcetype"] == "winevent:security"


def test_final_rqc_binds_into_authoring_context() -> None:
    rqc = {
        "normalized_goal": "hourly failed authentication trend",
        "time_scope": "last 6 hours",
        "locked_fields": {"time_scope": "last 6 hours"},
        "entities": {"source_ip": ["198.51.100.10"]},
    }
    spec = _build_authoring_intent_spec(
        "hourly failed-login trend over the last 24 hours",
        resolved_query_contract=rqc,
    )
    assert spec["search_horizon"] == "earliest=-6h latest=now"
    assert spec["objective"] == "hourly failed authentication trend"
    ctx = _build_utility_llm_context(
        "hourly failed-login trend over the last 24 hours",
        family="lab_draft",
        resolved_query_contract=rqc,
        intent_spec=spec,
    )
    assert ctx["deterministic_source_bindings"]["time_window"] == "earliest=-6h latest=now"
    assert ctx["resolved_query_contract"] is rqc
    assert "search_horizon: earliest=-6h latest=now" in ctx["semantic_analyst_intent_text"]


def test_raw_query_cannot_override_locked_rqc_horizon() -> None:
    spec = build_spl_intent_spec(
        "show failed logins last 24 hours",
        resolved_query_contract={
            "time_scope": "last 2 hours",
            "locked_fields": {"time_scope": "last 2 hours"},
        },
    )
    assert spec["search_horizon"] == "earliest=-2h latest=now"


def test_analytical_shape_rejects_alert_template_bias() -> None:
    spec = build_spl_intent_spec("hourly failed-login trend over the last 24 hours")
    bindings = build_user_constraint_bindings(
        "hourly failed-login trend over the last 24 hours",
        allowed_indexes=("wineventlog",),
        allowed_sourcetypes=("WinEventLog:Security",),
    )
    contract = build_deterministic_request_contract(
        query_understanding=None,
        query_signals={"explicit_spl_authoring": True, "review_only_spl": True},
        bindings=bindings,
    )
    template = SimpleNamespace(
        spl_text="search index=wineventlog EventCode=4740 | stats count by user | head 100"
    )
    decision = check_template_semantic_fidelity(
        contract=contract,
        template=template,
        intent_spec=spec,
    )
    assert decision.compatible is False
    assert "alert_template_bias" in decision.rejected_reasons
