"""Plan 8 SPL1 — final-RQC entities must reach SPL slots and survive normalization."""

from __future__ import annotations

from app.safeguards.spl_validator import validate_spl
from app.spl.rqc_constraint_preservation import (
    apply_rqc_constraint_preservation,
    evaluate_rqc_constraint_preservation,
    rqc_slots_from_contract,
)
from app.spl.user_constraint_bindings import build_user_constraint_bindings


VPN_RQC = {
    "intent_family": "live_investigation",
    "time_scope": "earliest=-1d@d latest=@d",
    "entities": {
        "source_ip": ["203.0.113.24"],
        "user": ["admin"],
        "geo": "Germany",
        "account_type": "administrator",
    },
}


def test_rqc_slots_include_source_ip_time_and_account() -> None:
    slots = rqc_slots_from_contract(VPN_RQC)
    assert slots["src_ip"] == "203.0.113.24"
    assert slots["time_window"] == "earliest=-1d@d latest=@d"
    assert slots["user"] == "admin"
    assert slots["geo"] == "Germany"
    assert slots["account_type"] == "administrator"


def test_bindings_accept_rqc_slots_as_deterministic() -> None:
    slots = rqc_slots_from_contract(VPN_RQC)
    bindings = build_user_constraint_bindings(
        "Check failed VPN admin logins from 203.0.113.24 yesterday.",
        rqc_slots=slots,
    )
    assert "203.0.113.24" in bindings.explicit_src_ips or bindings.normalized_slots.get("src_ip") == "203.0.113.24"


def test_preserved_vpn_spl_keeps_ip_and_yesterday() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth src=203.0.113.24 user=admin "
        "geo_country=Germany earliest=-1d@d latest=@d | stats count by user | head 100"
    )
    result = evaluate_rqc_constraint_preservation(spl, resolved_query_contract=VPN_RQC)
    assert result["dropped"] == []
    assert "src_ip" in result["present"]
    assert "time_window" in result["present"]


def test_silent_source_ip_loss_is_rejected() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-1d@d latest=@d "
        "| stats count by user | head 100"
    )
    validation = validate_spl(spl)
    updated = apply_rqc_constraint_preservation(
        validation,
        spl=spl,
        resolved_query_contract=VPN_RQC,
    )
    assert updated["approved"] is False
    assert updated["normalized_spl"] is None
    assert "rqc_constraint_dropped:src_ip" in updated["reject_reasons"]


def test_silent_time_scope_loss_is_rejected() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth src=203.0.113.24 user=admin "
        "| stats count by user | head 100"
    )
    result = evaluate_rqc_constraint_preservation(spl, resolved_query_contract=VPN_RQC)
    assert "time_window" in result["dropped"]


def test_silent_geo_and_account_type_loss_is_rejected() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth src=203.0.113.24 "
        "earliest=-1d@d latest=@d | stats count by src | head 100"
    )
    result = evaluate_rqc_constraint_preservation(spl, resolved_query_contract=VPN_RQC)
    assert "geo" in result["dropped"]
    assert "account_type" in result["dropped"] or "user" in result["dropped"]


def test_governed_template_without_src_slot_is_non_applicable() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth earliest=-24h latest=now "
        "| stats count by user | head 50"
    )
    rqc = {
        "time_scope": "earliest=-24h latest=now",
        "entities": {"source_ip": ["203.0.113.24"], "host": "fw01"},
    }
    result = evaluate_rqc_constraint_preservation(
        spl,
        resolved_query_contract=rqc,
        template_body="search index=$index$ sourcetype=$sourcetype$ earliest=$earliest$ latest=$latest$ | stats count by user | head $limit$",
    )
    assert "src_ip" not in result["dropped"]
    assert "host" not in result["dropped"]
    assert result["non_applicable"]["src_ip"] == "no_governed_template_slot"
    assert result["non_applicable"]["host"] == "no_governed_template_slot"
    assert "time_window" not in result["dropped"]


def test_empty_governed_template_still_marks_unmapped_slots_non_applicable() -> None:
    spl = "search index=pgcil_soc earliest=-24h latest=now | stats count by user | head 50"
    rqc = {"entities": {"source_ip": ["203.0.113.24"]}}
    result = evaluate_rqc_constraint_preservation(
        spl,
        resolved_query_contract=rqc,
        template_body="",
    )
    assert result["non_applicable"]["src_ip"] == "no_governed_template_slot"
    assert "src_ip" not in result["dropped"]


def test_explicit_non_applicability_does_not_drop() -> None:
    spl = (
        "search index=pgcil_soc sourcetype=pgcil:auth src=203.0.113.24 user=admin "
        "earliest=-1d@d latest=@d | stats count by user | head 100"
    )
    result = evaluate_rqc_constraint_preservation(
        spl,
        resolved_query_contract=VPN_RQC,
        non_applicable={"geo": "geo_field_not_in_source_profile"},
    )
    assert "geo" not in result["dropped"]
    assert result["non_applicable"]["geo"] == "geo_field_not_in_source_profile"
