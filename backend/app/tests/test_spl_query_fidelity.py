from __future__ import annotations

import pytest

from app.chat.contracts.llm_intent_advisory import LLMIntentAdvisory
from app.spl.draft_preview import _family_by_id
from app.spl.draft_preview_customization import customize_draft_preview_for_query
from app.chat.analyst_response_builder import build_analyst_response_for_live
from app.schemas.responses import CandidateSplEnvelope, SplDraftPreviewEnvelope
from app.spl.spl_slot_binding_validator import extract_natural_language_slots
from app.spl.template_compatibility import check_template_compatibility
from app.spl.template_query_bindings import customize_template_spl, validate_template_slots_for_render
from app.spl.user_constraint_bindings import build_user_constraint_bindings


MODBUS_QUERY = (
    "Write and execute an SPL query to search the ot_logs index for any Modbus "
    "function code 5 or 15 write commands to unexpected IPs."
)
WINEVENT_QUERY = (
    "Search wineventlog for Event ID 4624 for user jsmith from substation subnets over the last 7 days."
)
FIREWALL_QUERY = (
    "Look across syslog and cisco_asa for permits from IT VLAN to OT DMZ on port 445."
)
FAILED_LOGIN_QUERY = "Show failed logins for account jsmith on SRV-DC-01 over last 24 hours."
LOOKUP_QUERY = "Correlate ot_assets.csv against latest OT network traffic to find unmanaged devices."
THRESHOLD_QUERY = "Find users with more than 10 failed logins in 30 minutes."
DIRECTION_QUERY = "Find connections from 10.1.2.3 to 10.2.3.4."
SMB_QUERY = "Show SMB traffic from IT to OT."


@pytest.fixture(autouse=True)
def _expanded_indexes(monkeypatch):
    monkeypatch.setenv(
        "SPL_ALLOWED_INDEXES",
        "pgcil_soc,ot_logs,wineventlog,syslog,cisco_asa,ot_soc",
    )
    monkeypatch.setenv(
        "SPL_ALLOWED_SOURCETYPES",
        "pgcil:auth,ot:modbus,WinEventLog:Security,cisco:asa",
    )


def test_modbus_function_code_query_preserves_constraints() -> None:
    bindings = build_user_constraint_bindings(MODBUS_QUERY)
    assert bindings.explicit_indexes == ["ot_logs"] or bindings.normalized_slots.get("index") == "ot_logs"
    assert "modbus" in [p.lower() for p in bindings.explicit_protocols] or bindings.normalized_slots.get("protocol") == "modbus"
    assert "5" in str(bindings.explicit_function_codes or bindings.normalized_slots.get("function_code"))
    compatibility = check_template_compatibility(None, bindings, family_id="scada_dnp3_modbus_write")
    assert compatibility.compatible is False
    family = _family_by_id("scada_dnp3_modbus_write")
    spl, _, meta = customize_draft_preview_for_query(
        MODBUS_QUERY,
        family_id="scada_dnp3_modbus_write",
        draft_spl=family.draft_spl,
        assumptions=family.assumptions,
    )
    assert "index=ot_logs" in spl
    assert "dnp3" not in spl.lower()
    assert "function_code=\"5\"" in spl or 'function_code="5"' in spl
    assert bindings.explicit_directionality.get("unexpected_ip_direction") == "destination" or (
        bindings.normalized_slots.get("unexpected_ip_direction") == "destination"
    )
    assert meta.get("used_user_bound_skeleton") or "approved_ot_destination_allowlist" in spl


def test_llm_slots_do_not_override_user_explicit_index() -> None:
    advisory = LLMIntentAdvisory(
        entity_slots_candidate={"index": ["wrong_index"], "protocol": ["dnp3"]},
    )
    bindings = build_user_constraint_bindings(MODBUS_QUERY, llm_intent_advisory=advisory)
    assert bindings.normalized_slots.get("index") == "ot_logs"
    assert bindings.slot_sources["index"] == "user_explicit"
    assert bindings.normalized_slots.get("protocol") in {"modbus", None} or bindings.explicit_protocols[0] == "modbus"
    assert any(
        item.get("slot") == "index"
        and item.get("kept_source") == "user_explicit"
        and item.get("dropped_source") == "llm"
        for item in bindings.unbound_constraints
    )


def test_extra_slots_are_not_labeled_user_explicit() -> None:
    bindings = build_user_constraint_bindings(
        MODBUS_QUERY,
        extra_slots={"index": "wrong_index", "sourcetype": "ot:modbus"},
    )
    assert bindings.normalized_slots.get("index") == "ot_logs"
    assert bindings.slot_sources["index"] == "user_explicit"
    assert bindings.slot_sources["sourcetype"] == "source_profile"


def test_pipeline_llm_slots_do_not_poison_user_explicit_bucket() -> None:
    from app.chat.pipeline import _spl_user_constraint_bindings

    advisory = LLMIntentAdvisory(entity_slots_candidate={"index": "wrong_index"})
    bindings = _spl_user_constraint_bindings(MODBUS_QUERY, llm_intent_advisory=advisory)
    assert bindings.normalized_slots.get("index") == "ot_logs"
    assert bindings.slot_sources["index"] == "user_explicit"


def test_wineventlog_event_code_user_host_time() -> None:
    slots = extract_natural_language_slots(WINEVENT_QUERY)
    assert slots.get("index") == "wineventlog" or "wineventlog" in str(slots.get("indexes", ""))
    assert slots.get("event_code") == "4624"
    assert slots.get("user") == "jsmith"
    assert slots.get("time_window") == "earliest=-7d latest=now"


def test_event_code_does_not_force_skeleton_for_template_without_event_slot() -> None:
    bindings = build_user_constraint_bindings(WINEVENT_QUERY)
    compatibility = check_template_compatibility(
        "auth_success_after_failure",
        bindings,
    )
    assert compatibility.compatible is True
    assert compatibility.use_user_bound_skeleton is False


def test_template_validation_uses_passed_bindings() -> None:
    query = "Search pgcil_soc index for Modbus function code 5."
    bindings = build_user_constraint_bindings(
        query,
        llm_intent_advisory=LLMIntentAdvisory(entity_slots_candidate={"index": "wrong_index"}),
    )
    outcome = validate_template_slots_for_render(
        "scada_dnp3_modbus_write",
        query,
        extra_slots={"index": "wrong_index"},
        slot_source="llm",
        user_constraint_bindings=bindings,
    )
    assert outcome.normalized_slots.get("index") == "pgcil_soc"
    assert "wrong_index" not in str(outcome.normalized_slots)


def test_policy_rejected_user_sourcetype_is_preserved_for_review() -> None:
    query = "Search index=pgcil_soc sourcetype=bad:source for failed logins."
    bindings = build_user_constraint_bindings(
        query,
        allowed_indexes=("pgcil_soc",),
        allowed_sourcetypes=("pgcil:auth",),
    )
    assert "bad:source" in bindings.explicit_sourcetypes
    assert bindings.normalized_slots.get("sourcetype") != "bad:source"
    assert any(
        item.get("slot") == "sourcetype" and item.get("reason")
        for item in bindings.unbound_constraints
    )


def test_response_envelopes_preserve_binding_visibility_fields() -> None:
    candidate = CandidateSplEnvelope(
        trace_id="t",
        skill="spl_generation",
        user_query="query",
        candidate_spl="search index=main earliest=-15m latest=now",
        generation_mode="deterministic_template_render",
        confidence=0.9,
        assumptions=[],
        warnings=[],
        user_constraint_bindings={"unbound_constraints": [{"slot": "sourcetype"}]},
        spl_binding_trace={"unbound_constraints": [{"slot": "host"}]},
    )
    assert candidate.user_constraint_bindings == {"unbound_constraints": [{"slot": "sourcetype"}]}
    assert candidate.spl_binding_trace == {"unbound_constraints": [{"slot": "host"}]}

    preview = SplDraftPreviewEnvelope(
        draft_spl="search index=<vpn_index> earliest=-15m latest=now",
        draft_status="review_only",
        draft_source="deterministic_pattern",
        detection_family="vpn_login_anomaly",
        assumptions=[],
        required_source_fields=[],
        source_profile_missing=True,
        governed_template_missing=False,
        validator_status="blocked",
        review_required=True,
        execution_enabled=False,
        warning="review only",
        not_catalog_approved_notice="not catalog-approved",
        unbound_constraints=[{"slot": "vpn_index", "reason": "missing_source_profile"}],
        source_profile_bindings=[{"slot": "vpn_sourcetype", "value": "cisco:asa:vpn"}],
    )
    assert preview.unbound_constraints == [{"slot": "vpn_index", "reason": "missing_source_profile"}]
    assert preview.source_profile_bindings == [{"slot": "vpn_sourcetype", "value": "cisco:asa:vpn"}]


def test_analyst_response_surfaces_governed_candidate_unbound_constraints() -> None:
    envelope = build_analyst_response_for_live(
        user_query="Search index=pgcil_soc sourcetype=bad:source for failed logins.",
        message="Candidate SPL generated.",
        analyst_summary=None,
        source_evidence=[],
        mitre_mappings=[],
        severity_label=None,
        synthesis_draft=None,
        human_review={"required": True, "review_type": "spl_revision"},
        candidate_spl={
            "candidate_spl": "search index=pgcil_soc earliest=-15m latest=now",
            "generation_mode": "deterministic_template_render",
            "user_constraint_bindings": {
                "unbound_constraints": [
                    {
                        "slot": "sourcetype",
                        "value": "bad:source",
                        "reason": "slot_sourcetype_not_allowlisted",
                        "source": "user_explicit",
                    }
                ]
            },
        },
        spl_validation={"approved": False},
        execution={"status": "skipped"},
        intent_classification={"intent_family": "spl_generation_only"},
        evidence_plan={"answer_mode": "spl_review"},
    )

    assert envelope is not None
    assert envelope.spl_unbound_constraints == [
        {
            "slot": "sourcetype",
            "value": "bad:source",
            "reason": "slot_sourcetype_not_allowlisted",
            "source": "user_explicit",
        }
    ]


def test_firewall_permit_zones_and_port() -> None:
    slots = extract_natural_language_slots(FIREWALL_QUERY)
    assert slots.get("port") == "445"
    assert slots.get("action_semantic") == "permit"
    assert slots.get("src_zone") == "IT VLAN"
    assert slots.get("dest_zone") == "OT DMZ"


def test_failed_login_user_host_time() -> None:
    slots = extract_natural_language_slots(FAILED_LOGIN_QUERY)
    assert slots.get("user") == "jsmith"
    assert slots.get("host") == "SRV-DC-01"
    assert slots.get("time_window") == "earliest=-24h latest=now"
    assert slots.get("action_semantic") == "failed_login"


def test_lookup_correlation_preserves_csv() -> None:
    slots = extract_natural_language_slots(LOOKUP_QUERY)
    assert slots.get("lookup") == "ot_assets.csv"


def test_threshold_count_and_window() -> None:
    slots = extract_natural_language_slots(THRESHOLD_QUERY)
    assert slots.get("threshold") == "10"
    assert slots.get("threshold_comparison") == "greater_than"
    assert slots.get("time_window") == "earliest=-30m latest=now"


def test_directionality_src_dest_ips() -> None:
    slots = extract_natural_language_slots(DIRECTION_QUERY)
    assert slots.get("src_ip") == "10.1.2.3"
    assert slots.get("dest_ip") == "10.2.3.4"


def test_smb_service_binding() -> None:
    slots = extract_natural_language_slots(SMB_QUERY)
    assert slots.get("service") == "smb"


def test_auth_success_template_binds_host() -> None:
    query = "Generate SPL for successful login after failures on host=APP-01"
    spl = customize_template_spl("auth_success_after_failure", _BASE_AUTH_TEMPLATE, query)
    assert 'host="APP-01"' in spl
    assert "index=pgcil_soc" in spl


_BASE_AUTH_TEMPLATE = (
    "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now "
    "(action=failure OR action=success) | stats count by user | head 100"
)
