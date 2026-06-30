"""Tenant-portable token SPL builder (no hardcoded index/sourcetype/fields).

Per the dynamic-environment requirement, detection SPL is authored against
PLACEHOLDER TOKENS rather than a specific tenant's schema. Resolution order is
owned by the existing chain (``graph_node_spl_source_resolve``):

    user query -> Environment Knowledge (COE ``AI_SOC_SOURCE_PROFILE_MAP``)
              -> MCP discovery (``pipeline_dispatch.runtime_context.mcp_discovery_context``)
              -> unresolved: an explicit analyst-guiding placeholder is left in place

Fields are wrapped in ``coalesce`` over the platform's normalized variable plus
common vendor aliases so a tenant whose Environment KB has not mapped an alias
yet still gets a runnable shape (graceful field drift). All output is review-only
(placeholders + no execution authority) until the source profile fully resolves.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenSplDefinition:
    detection_family: str
    # Placeholder stems resolved by source_profile_resolver (<stem>). The fallback
    # name is what the analyst sees when nothing in the chain mapped the slot.
    index_token: str = "<index>"
    sourcetype_token: str = "<enter_your_sourcetype>"


def _coalesce(normalized_token: str, *aliases: str) -> str:
    """coalesce(<normalized_field_token>, alias1, alias2, "unknown") for drift tolerance."""
    parts = [normalized_token, *aliases, '"unknown"']
    return "coalesce(" + ", ".join(parts) + ")"


def build_scada_threshold_token_spl() -> str:
    """SCADA performance threshold-anomaly hunt, fully tokenized."""
    rtu = _coalesce("<rtu_id_field>", "rtu_id", "asset_id", "device_id")
    metric = _coalesce("<scada_metric_field>", "transmission_error_count", "error_count", "latency")
    return (
        "search index=<index> sourcetype=<enter_your_scada_sourcetype> earliest=-24h latest=now "
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
    """Cisco firewall denies / IOC-by-source hunt, fully tokenized."""
    src = _coalesce("<src_ip_field>", "src_ip", "src", "saddr")
    dest = _coalesce("<dest_ip_field>", "dest_ip", "dst_ip", "daddr")
    action = _coalesce("<action_field>", "action", "fw_action")
    return (
        "search index=<index> sourcetype=<enter_your_firewall_sourcetype> earliest=-24h latest=now "
        f"| eval src=lower({src}), dest=lower({dest}), fw_action=lower({action}) "
        "| stats count as event_count sum(coalesce(<bytes_field>, bytes, 0)) as total_bytes "
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
