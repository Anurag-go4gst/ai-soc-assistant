"""Tenant-portable token SPL builder (no hardcoded index/sourcetype/fields).

Detection SPL is authored against ABSTRACT COE placeholder stems
(``<scada_index>``, ``<cisco_firewall_sourcetype>``, …) — never a specific
tenant's schema. The application resolves them at chat time via the existing
chain in ``graph_node_spl_source_resolve`` / ``resolve_spl_source_profile``:

    Environment Knowledge (COE ``AI_SOC_SOURCE_PROFILE_MAP`` / persisted store)
        -- COE/admin values are AUTHORITATIVE --
    -> MCP discovery / asset registry (fills blanks only, never overrides COE)
    -> still unmapped: the pipeline HALTS and raises an Analyst Review
       (HIL ``spl_source_profile_clarification``) so the analyst binds the slot.
       No placeholder is ever executed and nothing is hardcoded.

Index/sourcetype use ``<stem>`` placeholders (COE-resolved, HIL on miss). FIELDS
use ``coalesce`` over the platform's normalized field plus common vendor aliases
(graceful field drift) and are NOT ``<>`` placeholders, so an unmapped field
alias degrades gracefully instead of HIL-blocking the whole query.
"""

from __future__ import annotations


def _coalesce(normalized: str, *aliases: str) -> str:
    """coalesce(normalized_field, alias1, alias2, "unknown") for drift tolerance."""
    parts = [normalized, *aliases, '"unknown"']
    return "coalesce(" + ", ".join(parts) + ")"


def build_scada_threshold_token_spl() -> str:
    """SCADA performance threshold-anomaly hunt — COE-stem index/sourcetype."""
    rtu = _coalesce("rtu_id", "asset_id", "device_id")
    metric = _coalesce("transmission_error_count", "error_count", "latency")
    return (
        "search index=<scada_index> sourcetype=<scada_sourcetype> earliest=-24h latest=now "
        f"| eval rtu=lower({rtu}), metric_value={metric} "
        "| stats max(metric_value) as peak_value avg(metric_value) as avg_value count as samples "
        "earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by rtu "
        "| where peak_value > 0 "
        '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S"), '
        'last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S") '
        "| fields - first_seen_epoch last_seen_epoch "
        "| sort - peak_value | head 100"
    )


def build_cisco_firewall_token_spl() -> str:
    """Cisco firewall denies / IOC-by-source hunt — COE-stem index/sourcetype."""
    src = _coalesce("src_ip", "src", "saddr")
    dest = _coalesce("dest_ip", "dst_ip", "daddr")
    action = _coalesce("action", "fw_action")
    return (
        "search index=<cisco_firewall_index> sourcetype=<cisco_firewall_sourcetype> "
        "earliest=-24h latest=now "
        f"| eval src=lower({src}), dest=lower({dest}), fw_action=lower({action}) "
        "| stats count as event_count sum(coalesce(bytes, 0)) as total_bytes "
        "earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by src, dest, fw_action "
        '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S"), '
        'last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S") '
        "| fields - first_seen_epoch last_seen_epoch "
        "| sort - event_count | head 100"
    )


_TOKEN_BUILDERS = {
    "ot_scada_performance": build_scada_threshold_token_spl,
    "network_firewall": build_cisco_firewall_token_spl,
}


def token_spl_for_validator_profile(validator_profile: str | None) -> str | None:
    """Return tokenized review-only SPL for a runtime validator profile, or None."""
    if not validator_profile:
        return None
    builder = _TOKEN_BUILDERS.get(validator_profile)
    return builder() if builder is not None else None
