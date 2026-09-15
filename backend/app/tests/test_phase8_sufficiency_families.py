"""Generic evidence-sufficiency families: catalogue leftovers cannot block completion."""

from __future__ import annotations

from app.chat.contracts.staged_sufficiency import from_evidence_state
from app.evidence.minimal_evidence_state import derive_minimal_evidence_state


def _mcp_record(*, fields: list[str], rows: list[dict]) -> dict:
    return {
        "evidence_id": "ev_env",
        "source_type": "splunk_mcp",
        "source_name": "splunk_soc",
        "collection_status": "collected",
        "fields_returned": fields,
        "preview_rows": rows,
    }


def test_auth_family_completes_without_rag_or_spl_keys() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            _mcp_record(
                fields=["user", "src_ip", "host", "action", "eventcode", "_time"],
                rows=[
                    {"user": "jdoe", "src_ip": "10.0.0.8", "host": "vpn-1", "action": "failure", "eventcode": "4625"},
                    {"user": "jdoe", "src_ip": "10.0.0.8", "host": "vpn-1", "action": "success", "eventcode": "4624"},
                ],
            )
        ],
        evidence_plan={
            "required_evidence_keys": ["auth", "identity", "rag", "spl"],
            "needs_rag": True,
            "needs_spl": True,
            "needs_mcp": True,
            "mcp_allowed": True,
            "answer_mode": "live_investigation",
            "checklist": [
                "Authentication failure events (including MFA/VPN/SSH) for the reported source, user, and window.",
                "Authentication success events after those failures for the same source/account.",
            ],
        },
        resolved_query_contract={"intent_family": "live_investigation", "evidence_requirements": []},
    )
    staged = from_evidence_state(state.model_dump_view())
    assert "auth" in state.obtained
    assert staged.status == "SUFFICIENT"
    assert "rag" not in staged.missing
    assert "spl" not in staged.missing


def test_endpoint_family_completes_despite_leftover_auth_and_rag() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            _mcp_record(
                fields=["host", "user", "action", "task_exec", "dest", "_time"],
                rows=[
                    {"host": "WS-14", "user": "jdoe", "action": "scheduled_task_created", "task_exec": "powershell.exe"},
                    {"host": "WS-14", "user": "jdoe", "dest": "198.51.100.88", "dest_port": 443},
                ],
            )
        ],
        evidence_plan={
            "required_evidence_keys": ["endpoint", "auth", "process_execution", "rag", "spl"],
            "needs_rag": True,
            "needs_spl": True,
            "needs_mcp": True,
            "mcp_allowed": True,
            "answer_mode": "live_investigation",
            "checklist": [
                "Endpoint/process execution telemetry for the reported host, including parent/child process.",
                "Correlate the collected legs on host,user within 8h.",
            ],
        },
        structured_context={"missing_evidence": ["approved_sop_guidance", "rag:sop"]},
    )
    staged = from_evidence_state(state.model_dump_view())
    assert "endpoint" in state.obtained
    assert "process_execution" in state.obtained
    assert staged.status == "SUFFICIENT"
    assert "auth" not in staged.missing
    assert "rag" not in staged.missing


def test_network_family_completes_without_auth_or_rag() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            _mcp_record(
                fields=["host", "query", "answer", "dest", "dest_port", "action", "_time"],
                rows=[
                    {"host": "ws-2", "query": "rare.example", "answer": "198.51.100.10"},
                    {"host": "ws-2", "dest": "198.51.100.10", "dest_port": 443, "action": "allowed"},
                ],
            )
        ],
        evidence_plan={
            "required_evidence_keys": ["dns", "firewall_sessions", "auth", "rag"],
            "needs_rag": True,
            "needs_mcp": True,
            "mcp_allowed": True,
            "answer_mode": "live_investigation",
            "checklist": [
                "DNS query telemetry for the same host and time window.",
                "Firewall / network session telemetry for the same host and time window.",
            ],
        },
    )
    staged = from_evidence_state(state.model_dump_view())
    assert "dns" in state.obtained
    assert "firewall_sessions" in state.obtained
    assert staged.status == "SUFFICIENT"
    assert "auth" not in staged.missing
    assert "rag" not in staged.missing
