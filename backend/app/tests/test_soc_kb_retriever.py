from __future__ import annotations

from app.api.routes_chat import _attach_hil_soc_kb_guidance
from app.evidence.context_structurer import structure_context
from app.evidence.source_evidence import build_source_evidence
from app.knowledge.soc_kb_retriever import load_soc_kb_store, retrieve_soc_kb, soc_kb_status_summary
from app.orchestration.human_review import human_review


APPROVED_VALIDATION = {
    "approved": True,
    "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
    "reject_reasons": [],
    "warnings": [],
    "enforced_limits": {"max_result_limit": 100},
    "policy_version": "spl-policy-v1",
}

EXECUTION = {
    "status": "requires_human_review",
    "execution_intent": "spl_search",
    "selected_mcp_server": "splunk_soc",
    "selected_mcp_tool": "run_splunk_query",
    "tool_selection_status": "selected",
    "tool_selection_reason": "allowlisted_spl_search_tool_selected",
    "executed_spl": None,
    "result_count": 0,
    "results_preview": [],
    "block_reason": "mcp_global_execution_disabled",
    "duration_ms": 0,
}

WORKFLOW = {
    "trace_id": "trace-rag",
    "skill": "attack_discovery",
    "tool_plan": ["route_only", "attack_discovery"],
    "status": "not_started",
    "execution_enabled": False,
    "steps": [],
    "required_connectors": ["mcp", "rag"],
    "safety_gates": ["approved_chunks_only"],
    "required_sources": ["mcp:splunk", "rag:sop"],
    "available_sources": [],
    "missing_sources": ["mcp:splunk", "rag:sop"],
    "message": "Workflow plan created.",
}


def _enable(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", True)


def test_store_loads_multiple_collections_documents_and_entries() -> None:
    store = load_soc_kb_store()
    assert len(store.collections) >= 5
    assert len({doc["collection_id"] for doc in store.documents}) >= 4
    assert sum(1 for entry in store.entries if entry["doc_id"] == "coe-auth-sop-v1") >= 5

    summary = soc_kb_status_summary(store)
    assert summary["collections_configured_count"] >= 5
    assert summary["documents_total_count"] >= 9
    assert summary["eligible_current_approved_document_count"] >= 5
    assert summary["draft_count"] >= 1
    assert summary["retired_rejected_count"] >= 1
    assert summary["superseded_count"] >= 1
    assert summary["direct_to_llm"] is False
    assert summary["llm_selection_enabled"] is False
    assert summary["hybrid_placeholder_enabled"] is True
    assert summary["graph_placeholder_enabled"] is True


def test_current_approved_runtime_filters_exclude_bad_lifecycle_docs(monkeypatch) -> None:
    _enable(monkeypatch)
    result = retrieve_soc_kb(
        query="draft runtime should not retrieve superseded runtime should not retrieve expired rejected",
        selected_skill="attack_discovery",
        allowed_use=["hil_guidance"],
        collection_ids=["soc_sop"],
    )

    ids = {entry["doc_id"] for entry in result["retrieved_entries"]}
    assert "draft-auth-sop-v2" not in ids
    assert "old-auth-sop-v0" not in ids
    assert "expired-auth-note-v1" not in ids
    assert "rejected-auth-note-v1" not in ids
    assert result["excluded_counts"]["draft"] >= 1
    assert result["excluded_counts"]["superseded"] >= 1
    assert result["excluded_counts"]["expired"] >= 1
    assert result["excluded_counts"]["rejected"] >= 1


def test_environment_allowed_use_and_skill_filters(monkeypatch) -> None:
    _enable(monkeypatch)
    wrong_env = retrieve_soc_kb(query="failed login spike", selected_skill="attack_discovery", environment="pgcil_prod")
    assert not any(entry["environment"] == "coe" for entry in wrong_env["retrieved_entries"])
    assert wrong_env["excluded_counts"]["wrong_environment"] >= 1

    wrong_use = retrieve_soc_kb(query="failed login spike", selected_skill="attack_discovery", allowed_use=["tool_selection"])
    assert all("tool_selection" in entry["allowed_use"] for entry in wrong_use["retrieved_entries"])

    wrong_skill = retrieve_soc_kb(query="failed login spike", selected_skill="knowledge_recall", collection_ids=["splunk_context"])
    assert wrong_skill["retrieval_status"] in {"no_match", "retrieved"}
    assert not any(entry["entry_id"] == "coe-splunk-auth-context" for entry in wrong_skill["retrieved_entries"])


def test_typo_synonym_query_retrieves_expected_entry(monkeypatch) -> None:
    _enable(monkeypatch)
    result = retrieve_soc_kb(query="faild logins bruteforce against admin", selected_skill="attack_discovery", allowed_use=["hil_guidance"])

    assert result["retrieval_status"] == "retrieved"
    assert result["retrieved_entries"][0]["entry_id"] == "coe-auth-bruteforce"
    assert result["confidence"] >= 0.35
    assert "retrieval_hint_match" in result["reasons"] or "synonyms_match" in result["reasons"]


def test_negative_examples_prevent_contamination(monkeypatch) -> None:
    _enable(monkeypatch)
    result = retrieve_soc_kb(query="malware download dns beacon firewall denied traffic", selected_skill="attack_discovery", allowed_use=["hil_guidance"])

    assert not any(entry["entry_id"] == "coe-auth-bruteforce" for entry in result["retrieved_entries"])


def test_ambiguous_no_match_max_results_and_stable_confidence(monkeypatch) -> None:
    _enable(monkeypatch)
    ambiguous = retrieve_soc_kb(query="auth failed login brute force T1110", selected_skill="attack_discovery", max_results=2)
    assert ambiguous["retrieval_status"] in {"retrieved", "ambiguous"}
    assert len(ambiguous["retrieved_entries"]) <= 2
    assert ambiguous["confidence"] == retrieve_soc_kb(query="auth failed login brute force T1110", selected_skill="attack_discovery", max_results=2)["confidence"]

    no_match = retrieve_soc_kb(query="printer toner inventory procurement", selected_skill="attack_discovery")
    assert no_match["retrieval_status"] == "no_match"
    assert no_match["retrieved_entries"] == []


def test_retrieved_entries_become_source_evidence_and_preserve_citations(monkeypatch) -> None:
    _enable(monkeypatch)
    retrieval = retrieve_soc_kb(query="brute force failed login spike", selected_skill="attack_discovery", allowed_use=["hil_guidance"])
    evidence = build_source_evidence(
        trace_id="trace-rag-evidence",
        query="brute force failed login spike",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTION,
        soc_kb_retrieval=retrieval,
    )

    rag = evidence[0]
    row = rag["preview_rows"][0]
    assert rag["source_type"] == "rag"
    assert rag["tool_name"] == "governed_soc_kb_retrieval"
    assert rag["collection_status"] == "collected"
    assert row["doc_id"] == "coe-auth-sop-v1"
    assert row["doc_version"] == "1.0"
    assert row["entry_id"] == "coe-auth-bruteforce"
    assert row["citation"] == "COE Sample Auth Investigation SOP v1.0 AUTH-001"


def test_structured_context_receives_rag_policy_constraints_and_refs(monkeypatch) -> None:
    _enable(monkeypatch)
    retrieval = retrieve_soc_kb(query="successful login after failures T1078 pgcil:auth", selected_skill="attack_discovery")
    evidence = build_source_evidence(
        trace_id="trace-rag-context",
        query="successful login after failures T1078 pgcil:auth",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTION,
        soc_kb_retrieval=retrieval,
    )
    context = structure_context(
        query="successful login after failures T1078 pgcil:auth",
        trace_id="trace-rag-context",
        selected_skill="attack_discovery",
        workflow_plan=WORKFLOW,
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTION,
        source_evidence=evidence,
    )

    assert context["policy_context_refs"]
    assert any("Do not call the account compromised" in item for item in context["answer_constraints"])
    assert any("account takeover confirmed" in item for item in context["prohibited_conclusions"])
    assert context["mitre_grounding_refs"] or context["mitre_candidates"]
    assert context["splunk_context_refs"]
    assert context["synthesis_allowed"] is False


def test_hil_receives_sop_fields_and_missing_sop_safe_message(monkeypatch) -> None:
    _enable(monkeypatch)
    review = human_review(
        "execution_approval",
        "mcp_global_execution_disabled",
        "analyst",
        ["approve_mock_execution"],
        "Human review required.",
    )
    retrieval = retrieve_soc_kb(query="brute force failed login spike", selected_skill="attack_discovery", allowed_use=["hil_guidance"])
    evidence = build_source_evidence(
        trace_id="trace-rag-hil",
        query="brute force failed login spike",
        selected_skill="attack_discovery",
        spl_validation=APPROVED_VALIDATION,
        execution=EXECUTION,
        soc_kb_retrieval=retrieval,
    )
    enriched = _attach_hil_soc_kb_guidance(review, evidence)
    assert enriched["sop_reference"] == "COE Sample Auth Investigation SOP v1.0 AUTH-001"
    assert enriched["sop_excerpt"]
    assert enriched["sop_action_hint"]
    assert enriched["reviewer_role"] == "tier2_soc_analyst"

    missing = _attach_hil_soc_kb_guidance(review, [])
    assert missing["safe_message_for_user"] == "Approved SOP guidance is unavailable for this scenario."


def test_disabled_retrieval_and_llm_safety_flags(monkeypatch) -> None:
    monkeypatch.setattr("app.knowledge.soc_kb_retriever.settings.soc_kb_retrieval_enabled", False)
    result = retrieve_soc_kb(query="brute force", selected_skill="attack_discovery")
    assert result["retrieval_status"] == "disabled"
    assert result["retrieved_entries"] == []
    assert result["direct_to_llm"] is False
    assert result["llm_selection_enabled"] is False
