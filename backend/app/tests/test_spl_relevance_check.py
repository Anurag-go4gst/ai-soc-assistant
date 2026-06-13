"""Unit tests for the structural SPL relevance gate (R5).

Seeded asked-X-got-Y pairs, including the five Phase-B-deferred refs. No LLM.
"""
from __future__ import annotations

from app.query_understanding.models import (
    OutputTemplate,
    QueryEntities,
    QueryUnderstandingResult,
    RequestedOutputType,
)
from app.spl.spl_relevance_check import check_spl_relevance


def _understanding(**entity_kwargs) -> QueryUnderstandingResult:
    return QueryUnderstandingResult(
        raw_query="q",
        normalized_query="q",
        primary_intent="spl_generation",
        requested_output_type=RequestedOutputType.SPL,
        output_template=OutputTemplate.SPL_RESPONSE,
        entities=QueryEntities(**entity_kwargs),
        confidence=0.9,
    )

# Minimal SPL fixtures by data source.
NETWORK_TOP_TALKERS = (
    "search index=<network_index> sourcetype=<network_traffic_sourcetype> (dest_port=* OR bytes=*) "
    "| eval src_ip_norm=coalesce(src_ip, src) | stats sum(bytes) as total by src_ip_norm | sort - total | head 100"
)
DNS_BY_HOST = (
    "search index=<dns_index> sourcetype=<dns_sourcetype> (query=*) "
    "| eval src_host_norm=coalesce(src_host, src_ip) | eval domain_norm=lower(query) "
    "| stats count as dns_query_count dc(domain_norm) as distinct_domains by src_host_norm | sort - dns_query_count | head 100"
)
POWERSHELL_EVENTS = (
    "search index=<endpoint_index> sourcetype=<endpoint_process_sourcetype> (powershell OR pwsh) "
    "| eval host_norm=coalesce(Computer, host) | table host_norm command_line_norm | head 100"
)
POWERSHELL_ROLLUP = (
    "search index=<endpoint_index> sourcetype=<endpoint_process_sourcetype> (powershell OR pwsh) "
    "| eval host_norm=coalesce(Computer, host) | stats count as suspicious_events by host_norm | sort - suspicious_events | head 100"
)
AUTH_BY_USER = (
    "search index=<auth_index> sourcetype=<auth_sourcetype> (action=failure) "
    "| eval user_norm=coalesce(user, src_user) | stats count as failures by user_norm | sort - failures | head 100"
)


def test_dns_question_with_network_spl_is_irrelevant():
    # q0.q017 class: asked DNS, got network bytes.
    r = check_spl_relevance("Which hosts generated the most DNS queries?", NETWORK_TOP_TALKERS)
    assert r.relevant is False
    assert any(m.startswith("data_source_missing:dns") for m in r.mismatches)


def test_dns_question_with_dns_spl_is_relevant():
    r = check_spl_relevance("Which hosts generated the most DNS queries?", DNS_BY_HOST)
    assert r.relevant is True
    assert r.mismatches == []


def test_powershell_which_hosts_without_aggregation_flags_metric():
    r = check_spl_relevance("Which hosts ran suspicious PowerShell?", POWERSHELL_EVENTS)
    assert r.relevant is False
    assert "aggregation_missing" in r.mismatches


def test_powershell_which_hosts_with_rollup_is_relevant():
    r = check_spl_relevance("Which hosts ran suspicious PowerShell?", POWERSHELL_ROLLUP)
    assert r.relevant is True


def test_auth_question_with_network_spl_flags_source():
    # q0.q070 class: auth (password) question mis-routed to network data.
    r = check_spl_relevance("Which users changed their password multiple times?", NETWORK_TOP_TALKERS)
    assert r.relevant is False
    assert any("auth" in m for m in r.mismatches)


def test_auth_question_with_auth_spl_is_relevant():
    r = check_spl_relevance("Which users changed their password multiple times?", AUTH_BY_USER)
    assert r.relevant is True


def test_missing_spl_is_never_relevant():
    r = check_spl_relevance("Which hosts generated the most DNS queries?", None)
    assert r.relevant is False
    assert r.mismatches == ["no_spl_generated"]


def test_entity_missing_when_asked_user_absent_from_spl():
    spl = (
        "search index=<network_index> sourcetype=<network_traffic_sourcetype> (dest_port=*) "
        "| stats count by dest_port | sort - count | head 100"
    )
    r = check_spl_relevance("Which users had large outbound transfers?", spl)
    assert r.relevant is False
    assert "entity_missing" in r.mismatches


def test_query_understanding_entities_tighten_entity_check():
    understanding = _understanding(user=["alice"])
    # SPL has no user field -> entity_missing even if the prose were vague.
    spl = (
        "search index=<network_index> sourcetype=<network_traffic_sourcetype> (dest_port=*) "
        "| stats count by dest_port | head 100"
    )
    r = check_spl_relevance("show outbound activity", spl, understanding=understanding)
    assert "entity_missing" in r.mismatches


def test_to_dict_round_trips():
    r = check_spl_relevance("Which hosts generated the most DNS queries?", DNS_BY_HOST)
    d = r.to_dict()
    assert d["relevant"] is True
    assert set(d) == {"relevant", "mismatches", "checks", "trace"}


import pytest  # noqa: E402

# Phase D.2: every catalogue use case mapped to a lab family must produce a draft
# whose SPL passes the structural relevance gate for that detection.
_USE_CASE_QUERY = {
    "net_firewall_deny_spike": "Investigate firewall deny spike",
    "net_vpn_login_anomaly": "Investigate VPN login anomaly",
    "edr_suspicious_process": "Investigate suspicious process execution",
    "auth_after_hours_critical_asset": "Investigate after-hours login to critical asset",
    "edr_credential_dumping_signal": "Investigate credential dumping signal",
    "auth_impossible_travel": "Investigate impossible travel",
    "net_blocked_region_connection": "Check connection to blocked country",
    "auth_service_account_abnormal_login": "Investigate service account abnormal login",
    "auth_disabled_account_login": "Check login from disabled account",
}


@pytest.mark.parametrize("use_case_id,query", list(_USE_CASE_QUERY.items()))
def test_phase_d2_catalogue_family_draft_is_relevant(monkeypatch, use_case_id, query):
    import app.chat  # noqa: F401  warm package to resolve draft_preview import cycle
    from app.spl.draft_preview import build_draft_preview

    from app.config import settings as _settings
    monkeypatch.setattr(_settings, "ai_soc_spl_draft_preview_enabled", True)
    preview = build_draft_preview(query, use_case_id=use_case_id)
    assert preview is not None, f"{use_case_id} produced no draft"
    result = check_spl_relevance(query, preview["draft_spl"])
    assert result.relevant, f"{use_case_id} draft not relevant: {result.mismatches}"
