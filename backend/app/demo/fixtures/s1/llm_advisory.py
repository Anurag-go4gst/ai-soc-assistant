"""EC-only LLM advisory fixture for S1.

Demonstrates: LLM candidate → validate_spl → normalized SPL → not deployed.
Does not call a live model. LLM output is not evidence.
"""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP

_JUMP = "10.20.1.10"
_ACCOUNT = "svc_jump_ops"


def advisory_label() -> str:
    return "Agent assessment"


def advisory_trace_label() -> str:
    return "LLM interpretation — not evidence"


def novelty_window_spl(*, indicator: str = PRIMARY_ATTACKER_IP) -> str:
    return (
        f"search index=pgcil_soc sourcetype=pgcil:firewall earliest=-60d latest=-30d "
        f"(src={indicator} OR dest={indicator}) "
        "| stats count as event_count count(eval(action=\"deny\")) as deny_count "
        "count(eval(action=\"allow\")) as allow_count min(_time) as first_seen max(_time) as last_seen "
        "dc(dest_port) as distinct_ports values(dest_port) as dest_ports values(action) as actions by src, dest "
        "| sort -event_count | head 100"
    )


def requested_30d_spl(*, indicator: str = PRIMARY_ATTACKER_IP) -> str:
    return novelty_window_spl(indicator=indicator).replace("earliest=-60d latest=-30d", "earliest=-30d latest=now")


def candidate_monitoring_spl(*, indicator: str = PRIMARY_ATTACKER_IP, dest: str = _JUMP) -> str:
    return (
        f"search index=pgcil_soc sourcetype=pgcil:firewall earliest=-14d latest=now "
        f"src={indicator} dest={dest} (dest_port=443 OR dest_port=8443) "
        "| stats count as event_count count(eval(action=\"allow\")) as allow_count "
        "count(eval(action=\"deny\")) as deny_count min(_time) as first_seen max(_time) as last_seen "
        "values(dest_port) as dest_ports values(action) as actions by src, dest, dest_port "
        "| sort -allow_count,-event_count | head 100"
    )


def fourteen_day_auth_spl(*, dest: str = _JUMP, account: str = _ACCOUNT) -> str:
    return (
        f"search index=pgcil_soc sourcetype=pgcil:auth earliest=-14d latest=now "
        f"host={dest} user={account} action=success "
        "| stats count as success_count min(_time) as first_seen max(_time) as last_seen "
        "values(src) as src_ips by host, user, action "
        "| head 100"
    )


def permitted_session_spl(*, indicator: str = PRIMARY_ATTACKER_IP, dest: str = _JUMP) -> str:
    return (
        f"search index=pgcil_soc sourcetype=pgcil:firewall earliest=-30d latest=now "
        f"src={indicator} dest={dest} action=allow "
        "| stats count as allow_count min(_time) as first_seen max(_time) as last_seen "
        "values(dest_port) as dest_ports values(user) as users by src, dest, dest_port "
        "| head 100"
    )


def advisory_payload(
    *,
    allow_count: int = 3,
    deny_count: int = 922,
    dest: str = _JUMP,
) -> dict[str, Any]:
    return {
        "label": advisory_label(),
        "provenance": "llm_advisory_fixture",
        "live_llm_called": False,
        "not_evidence": True,
        "interpretation": (
            f"Firewall aggregation on {dest} shows {allow_count} allowed / {deny_count} denied. "
            "Denied volume must not bury the permitted sessions. A dedicated allow+auth search is required "
            "before concluding expected MCP traffic or preparing a block."
        ),
        "another_search_required": True,
        "added_step_reason": (
            f"Added because three permitted sessions reached high-criticality jump host {dest}. "
            "Denied volume must not hide successful communication."
        ),
        "candidate_detection": {
            "status": "candidate",
            "name": "EC_New_External_IP_Permitted_Session_Watch",
            "reason": (
                "Existing IOC-based notable does not cover this unlisted indicator. "
                "Candidate monitoring SPL is advisory until validated and authorized."
            ),
        },
        "chain": [
            "LLM candidate",
            "deterministic validation",
            "normalized SPL",
            "authorization",
            "Splunk MCP",
            "evidence",
        ],
    }
