from app.connectors.embeddings.mock import MockEmbeddingsConnector
from app.connectors.llm.mock import MockLlmConnector
from app.connectors.mcp.mock import MockMcpConnector
from app.connectors.rag.mock import MockRagConnector


def test_mock_mcp_returns_deterministic_response() -> None:
    connector = MockMcpConnector()
    request = {
        "server_name": "mock",
        "tool_name": "run_splunk_query",
        "normalized_spl": "search index=pgcil_soc sourcetype=pgcil:auth earliest=-15m latest=now | stats count by user | head 100",
        "trace_id": "trace-test",
        "policy_context": {"max_rows": 100},
    }
    first = connector.execute_validated_spl(**request)
    second = connector.execute_validated_spl(**request)
    assert first == second
    assert first["mock"] is True
    assert first["row_count"] == 1


def test_mock_rag_returns_approved_deterministic_chunks() -> None:
    chunks = MockRagConnector().retrieve("failed login triage", {"approved": True})
    assert len(chunks) == 1
    assert chunks[0].approved is True
    assert chunks[0].doc_id == "mock-runbook-auth-001"


def test_mock_llm_returns_valid_structured_output() -> None:
    routing = MockLlmConnector().complete_skill_routing({"query": "Investigate failed logins"})
    synthesis = MockLlmConnector().complete_synthesis({"evidence_refs": ["auth-001:0001"]})
    assert routing.skill == "attack_discovery"
    assert 0 <= routing.confidence <= 1
    assert synthesis.evidence_refs == ["auth-001:0001"]
    assert synthesis.insufficient_evidence is False


def test_mock_embeddings_are_deterministic() -> None:
    connector = MockEmbeddingsConnector()
    assert connector.embed_text("same") == connector.embed_text("same")
    assert len(connector.embed_text("same")) == 8
