"""Plan 8 E0A — minimal EvidenceState is a derived view, not a duplicate store."""

from __future__ import annotations

from app.evidence.minimal_evidence_state import derive_minimal_evidence_state


def test_view_is_derived_from_existing_governed_state() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            {
                "evidence_id": "ev_mcp",
                "source_type": "splunk_mcp",
                "source_name": "splunk_soc",
                "collection_status": "collected",
                "fields_returned": ["user", "src"],
                "preview_rows": [{"user": "admin", "password": "should-not-copy"}],
                "created_at": "2026-08-16T00:00:00Z",
                "provenance": "mcp_search",
                "time_range": "-15m",
            }
        ],
        structured_context={"missing_evidence": ["host"]},
        evidence_plan={"required_evidence_keys": ["user", "src", "host"], "needs_mcp": True, "mcp_allowed": True},
        resolved_query_contract={
            "evidence_requirements": ["user"],
            "required_capabilities": ["mcp"],
            "time_scope": "-15m",
            "entities": {"user": "admin"},
        },
        canonical_facts={"facts": [{"kind": "entity", "provenance": {"node": "spine", "evidence_class": "mcp_search"}}]},
        final_evidence_gate={"collected_evidence_refs": ["ev_mcp"], "suppressed_claims": []},
    )
    assert state.schema_version == "minimal_evidence_state_v2"
    assert "user" in state.required
    assert "host" in state.required
    assert "user" in state.obtained
    assert "src" in state.obtained
    assert "mcp" in state.obtained
    assert "entity" not in state.obtained
    assert "entity" in state.diagnostic
    assert next(item for item in state.items if item.key == "entity").status == "diagnostic"
    assert "host" in state.missing
    assert state.provenance["derived_from"] == [
        "source_evidence",
        "structured_context",
        "evidence_plan",
        "resolved_query_contract",
        "canonical_facts",
        "final_evidence_gate",
    ]
    assert state.provenance["raw_evidence_duplicated"] is False
    dumped = state.model_dump_view()
    assert "preview_rows" not in dumped
    assert "should-not-copy" not in str(dumped)
    user_item = next(item for item in state.items if item.key == "user")
    assert user_item.trust_class == "untrusted_evidence"
    assert user_item.provenance == "mcp_search"
    assert user_item.scope["time_range"] == "-15m"
    assert user_item.observed_at == "2026-08-16T00:00:00Z"
    assert state.scope["time_scope"] == "-15m"


def test_blocked_and_stale_and_invalidated_are_not_usable() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            {
                "evidence_id": "ev_old",
                "source_type": "splunk_mcp",
                "source_name": "splunk_soc",
                "collection_status": "collected",
                "warnings": ["stale_result"],
                "fields_returned": ["user"],
            },
            {
                "evidence_id": "ev_fail",
                "source_type": "rag",
                "source_name": "soc_kb",
                "collection_status": "failed",
            },
            {
                "evidence_id": "ev_block",
                "source_type": "cve_snapshot",
                "source_name": "cisa_kev",
                "collection_status": "blocked",
            },
        ],
        evidence_plan={"required_evidence_keys": ["user", "rag", "cve_snapshot"], "needs_mcp": True, "mcp_allowed": False},
        final_evidence_gate={"suppressed_claims": ["allow_vulnerability_confirmed"]},
    )
    assert "mcp" in state.blocked
    assert "rag" in state.invalidated
    assert "cve_snapshot" in state.blocked
    assert "user" in state.stale or "mcp" in state.stale
    assert "allow_vulnerability_confirmed" in state.invalidated
    assert "user" in state.missing
    assert "rag" in state.missing


def test_execution_status_without_source_evidence_is_diagnostic_only() -> None:
    state = derive_minimal_evidence_state(
        evidence_plan={"needs_spl": True, "needs_mcp": True, "mcp_allowed": True},
        execution={"status": "executed"},
    )
    assert state.obtained == []
    assert set(state.missing) == {"spl", "mcp"}
    assert "execution_status" in state.diagnostic
    execution_item = next(item for item in state.items if item.key == "execution_status")
    assert execution_item.status == "diagnostic"
    assert execution_item.scope == {"status": "executed"}


def test_generated_candidate_spl_is_non_authoritative() -> None:
    state = derive_minimal_evidence_state(
        source_evidence=[
            {
                "evidence_id": "ev_saia",
                "source_type": "splunk_mcp_saia",
                "source_name": "splunk_ai_assistant",
                "collection_status": "collected",
                "output_type": "candidate_spl",
            }
        ]
    )
    item = next(item for item in state.items if item.key == "candidate_spl")
    assert item.trust_class == "non_authoritative_generated"
    assert item.status == "diagnostic"
    assert "candidate_spl" not in state.obtained
