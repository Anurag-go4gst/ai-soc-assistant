"""Plan 8 O1A — prior evidence is reusable only when it matches the new final RQC."""

from __future__ import annotations

from types import SimpleNamespace

from app.chat.contracts.staged_sufficiency import from_evidence_state
from app.chat.session_store import SessionPins
from app.evidence.evidence_sufficiency import attach_evidence_sufficiency
from app.evidence.minimal_evidence_state import derive_minimal_evidence_state
from app.evidence.session_evidence_applicability import apply_session_evidence_applicability


def test_admin_evidence_is_out_of_scope_for_service_account_rqc() -> None:
    new_rqc = {
        "intent_family": "live_investigation",
        "required_capabilities": ["mcp"],
        "evidence_requirements": ["mcp"],
        "entities": {"account_type": "service_account", "geo": "Germany"},
        "time_scope": "-24h",
    }
    current = derive_minimal_evidence_state(
        evidence_plan={"required_evidence_keys": ["mcp"], "needs_mcp": True, "mcp_allowed": True},
        resolved_query_contract=new_rqc,
    )
    applied = apply_session_evidence_applicability(
        current,
        resolved_query_contract=new_rqc,
        prior_scope={
            "intent_family": "live_investigation",
            "entities": {"user": "admin", "geo": "Germany"},
            "time_scope": "-24h",
        },
        prior_refs=["mcp"],
    )
    mcp_item = next(item for item in applied.items if item.key == "mcp")
    assert mcp_item.applicability == "OUT_OF_SCOPE"
    assert "mcp" in applied.out_of_scope
    assert "mcp" not in applied.obtained
    assert "mcp" in applied.missing
    assert applied.provenance["applicability_evaluated"] is True
    sufficiency = from_evidence_state(applied, resolved_query_contract=new_rqc)
    assert sufficiency.status == "INSUFFICIENT"
    assert "evidence_out_of_scope" in sufficiency.reason_codes
    assert "mcp" not in sufficiency.available


def test_matching_geo_and_time_remain_reusable_without_account_conflict() -> None:
    evidence = derive_minimal_evidence_state(
        source_evidence=[
            {
                "evidence_id": "ev_vpn",
                "source_type": "splunk_mcp",
                "collection_status": "collected",
            }
        ],
        evidence_plan={"needs_mcp": True, "mcp_allowed": True, "required_evidence_keys": ["mcp"]},
        resolved_query_contract={
            "required_capabilities": ["mcp"],
            "entities": {"geo": "Germany"},
            "time_scope": "-24h",
        },
    )
    applied = apply_session_evidence_applicability(
        evidence,
        resolved_query_contract={
            "required_capabilities": ["mcp"],
            "entities": {"geo": "Germany"},
            "time_scope": "-24h",
        },
        prior_scope={"entities": {"geo": "Germany"}, "time_scope": "-24h"},
        prior_refs=[],
    )
    mcp_item = next(item for item in applied.items if item.key == "mcp")
    assert mcp_item.applicability == "REUSABLE"
    assert "mcp" in applied.obtained
    assert applied.out_of_scope == []


def test_attach_sufficiency_uses_session_pins_for_admin_to_service_accounts() -> None:
    new_rqc = {
        "intent_family": "live_investigation",
        "required_capabilities": ["mcp"],
        "evidence_requirements": ["mcp"],
        "entities": {"account_type": "service_account", "geo": "Germany"},
        "time_scope": "-24h",
    }
    pins = SessionPins(
        session_id="sess-o1a",
        last_rqc_redacted={"intent_family": "live_investigation", "entities": {"user": "admin"}},
        last_evidence_scope={"entities": {"user": "admin", "geo": "Germany"}, "time_scope": "-24h"},
        last_evidence_refs=["mcp"],
    )

    updated = attach_evidence_sufficiency(
        {
            "resolved_query_contract": new_rqc,
            "evidence_plan": {"needs_mcp": True, "mcp_allowed": True, "required_evidence_keys": ["mcp"]},
            "session_context_resolution": SimpleNamespace(follow_up_kind="scope_delta", pins=pins),
            "session_pins": pins,
        }
    )
    evidence = updated["evidence_state"]
    assert "mcp" in evidence.get("out_of_scope", [])
    assert "mcp" in evidence.get("missing", [])
    assert updated["evidence_sufficiency"]["status"] == "INSUFFICIENT"
