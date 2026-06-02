from __future__ import annotations

from app.api.routes_chat import chat
from app.coverage.question_runtime_map import list_question_runtime_entries
from app.demo.scenarios import run_demo_scenario
from app.query_understanding.parser import understand_query
from app.query_understanding.time_window import normalize_time_window
from app.schemas.requests import ChatRequest
from app.skills.selector import select_skill_chain
from app.skills.registry import build_skill_chain, get_skill, load_skill_registry
from app.use_cases.models import UseCaseSelection
from app.use_cases.registry import load_use_case_catalog, match_use_cases


def test_use_case_catalog_loads_required_soc_use_cases() -> None:
    catalog = load_use_case_catalog()
    ids = {item.use_case_id for item in catalog}

    assert len(catalog) >= 40
    assert "auth_failed_login_spike" in ids
    assert "soc_show_sop" in ids
    assert "soc_map_alert_mitre" in ids
    assert "ot_protocol_anomaly" in ids
    assert all(item.primary_skill for item in catalog)
    assert all(item.output_template for item in catalog)


def test_query_understanding_maps_failed_login_entities_and_time_window() -> None:
    result = understand_query("Investigate failed logins on host=APP-01 from 10.1.2.3 in the last hour")

    assert result.primary_intent == "attack_discovery"
    assert result.requested_output_type == "investigation"
    assert result.output_template == "investigation_answer"
    assert result.entities.host == ["APP-01"]
    assert result.entities.source_ip == ["10.1.2.3"]
    assert result.entities.time_window == "earliest=-60m latest=now"
    assert "auth_failed_login_spike" in result.mapped_use_case_ids
    assert result.clarification_needed is False


def test_query_understanding_mitre_without_context_requires_clarification() -> None:
    result = understand_query("Map this alert to MITRE")

    assert result.requested_output_type == "mitre_mapping"
    assert result.clarification_needed is True
    assert "mitre_mapping_requires_alert_context" in result.ambiguity_flags
    assert result.clarification_question


def test_query_understanding_maps_exact_105_question_registry_rows() -> None:
    entries = list_question_runtime_entries()
    assert len(entries) == 105

    for entry in entries:
        result = understand_query(entry["question"])
        assert result.mapped_question_ref == entry["question_ref"]
        assert result.mapped_question_number == entry["question_number"]
        assert result.mapped_pattern_type == entry["pattern_type"]
        assert result.mapped_primary_skill == entry["proposed_primary_skill"]
        assert result.mapped_operation_type == entry["proposed_operation_type"]
        assert result.mapped_coverage_id == entry["manifest_coverage_id"]
        assert result.question_registry_match_source == "question_runtime_map_105_exact"
        assert result.question_registry_observation_only is True
        assert result.deterministic_match_path in {
            "exact_105_question",
            "exact_105_plus_use_case_catalog",
        }


def test_query_understanding_uses_question_registry_as_intent_fallback() -> None:
    entry = next(item for item in list_question_runtime_entries() if item["question_ref"] == "q0.q001")
    result = understand_query(entry["question"])

    assert result.mapped_use_case_ids == []
    assert result.primary_intent == entry["legacy_router_intent_hint"]
    assert result.confidence == 0.55


def test_query_understanding_near_matches_105_question_paraphrase() -> None:
    result = understand_query("source IPs with the most outbound connections")

    assert result.mapped_question_ref == "q0.q002"
    assert result.mapped_coverage_id == "cov.q002.top_outbound_source_ips"
    assert result.question_registry_match_source == "question_runtime_map_105_near_token"
    assert result.question_registry_match_score is not None
    assert result.deterministic_match_path in {"near_105_question", "use_case_catalog"}
    assert result.llm_advisory_recommended is True


def test_query_understanding_expands_use_case_catalog_with_examples() -> None:
    result = understand_query("Recommend endpoint isolation")

    assert result.mapped_question_ref is None
    assert result.mapped_use_case_ids == ["edr_isolation_recommendation"]
    assert result.primary_intent == "action_planning"
    assert result.use_case_match_source == "expanded_catalog"
    assert result.deterministic_match_path == "use_case_catalog"


def test_query_understanding_recommends_llm_advisory_for_out_of_registry_query() -> None:
    result = understand_query("Can you correlate badge-reader swipes with cafeteria purchases?")

    assert result.primary_intent == "unknown"
    assert result.mapped_question_ref is None
    assert result.mapped_use_case_ids == []
    assert result.deterministic_match_path == "out_of_registry"
    assert result.llm_advisory_recommended is True


def test_query_understanding_exact_105_and_catalog_are_not_contradictory() -> None:
    for entry in list_question_runtime_entries():
        result = understand_query(entry["question"])
        if result.mapped_use_case_ids:
            assert result.registry_consistency == "consistent"
            assert result.registry_warnings == []


def test_query_understanding_records_registry_catalog_conflict_without_clarification(monkeypatch) -> None:
    def fake_match_use_cases(query: str) -> list[UseCaseSelection]:
        return [
            UseCaseSelection(
                use_case_id="fake_conflict",
                display_name="Fake conflict",
                category="test",
                primary_skill="knowledge_recall",
                confidence=0.9,
                matched_patterns=["Which source IPs generated the most outbound connections?"],
                default_spl_template=None,
                output_template="investigation_answer",
                required_sources=[],
                optional_sources=[],
                action_capability_tier=0,
            )
        ]

    monkeypatch.setattr("app.query_understanding.parser.match_use_cases", fake_match_use_cases)
    result = understand_query("Which source IPs generated the most outbound connections?")

    assert result.mapped_question_ref == "q0.q002"
    assert result.mapped_use_case_ids == ["fake_conflict"]
    assert result.registry_consistency == "conflict"
    assert "question_registry_use_case_skill_conflict" in result.registry_warnings
    assert result.llm_advisory_recommended is True
    assert result.clarification_needed is False


def test_time_window_normalization_is_centralized() -> None:
    assert normalize_time_window("last 15 minutes") == "earliest=-15m latest=now"
    assert normalize_time_window("last 2 hours") == "earliest=-2h latest=now"
    assert normalize_time_window("yesterday") == "earliest=-1d@d latest=@d"
    assert normalize_time_window("earliest=-4h latest=now index=pgcil_soc") == "earliest=-4h latest=now"


def test_skill_registry_keeps_routable_and_pipeline_stage_separate() -> None:
    registry = load_skill_registry()
    query_understanding = get_skill("query_understanding")
    attack_discovery = get_skill("attack_discovery")

    assert query_understanding is not None
    assert query_understanding.routable is False
    assert query_understanding.pipeline_stage is True
    assert attack_discovery is not None
    assert attack_discovery.routable is True
    assert attack_discovery.pipeline_stage is False
    assert any(item.skill_id == "answer_guard" and not item.routable for item in registry)


def test_skill_chain_is_advisory_and_preserves_selected_router_skill() -> None:
    use_case = match_use_cases("Show SOP for brute-force investigation", limit=1)[0]
    chain = build_skill_chain("knowledge_recall", use_case)

    assert chain.selected_skill == "knowledge_recall"
    assert chain.routable_skill == "knowledge_recall"
    assert chain.stages[0] == "query_understanding"
    assert "context_sufficiency" in chain.stages


def test_skill_selection_result_records_registry_and_router_decision() -> None:
    use_case = match_use_cases("Show SOP for brute-force investigation", limit=1)[0]
    result = select_skill_chain(
        routed={"skill": "knowledge_recall", "tool_plan": ["retrieve_approved_context"], "llm_shadow": {"skill": "alert_summary"}},
        selected_use_case=use_case,
    )

    assert result.selected_skill == "knowledge_recall"
    assert result.rule_based_skill == "knowledge_recall"
    assert result.registry_primary_skill == "knowledge_recall"
    assert result.llm_assisted_skill == "alert_summary"
    assert result.alternatives == ["alert_summary"]
    assert result.selected_chain.selected_skill == "knowledge_recall"
    assert "router_selection_preserved_for_phase_2" in result.policy_notes


def test_chat_response_includes_optional_query_understanding_without_spl_for_sop(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes_chat.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.routing.skill_router.get_telemetry_connector", lambda: _FakeTelemetry())
    monkeypatch.setattr("app.orchestration.workflow_planner.get_telemetry_connector", lambda: _FakeTelemetry())
    response = chat(ChatRequest(message="Show SOP for brute-force investigation"))

    assert response.query_understanding is not None
    assert response.query_understanding.requested_output_type == "sop"
    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "soc_show_sop"
    assert response.selected_skill_chain is not None
    assert response.selected_skill_chain.selected_skill == "knowledge_recall"
    assert response.skill_selection is not None
    assert response.skill_selection.selected_skill == "knowledge_recall"
    assert response.skill_selection.selected_chain == response.selected_skill_chain
    assert response.candidate_spl is None
    assert response.spl_validation is None


def test_demo_scenario_includes_same_phase_2_selection_shape() -> None:
    payload = run_demo_scenario("failed_login_spike_app01")

    assert payload["demo_mode"] is True
    assert payload["query_understanding"]["mapped_use_case_ids"]
    assert payload["selected_use_case"]["use_case_id"] == "auth_failed_login_spike"
    assert payload["selected_skill_chain"]["selected_skill"] == payload["selected_skill"]
    assert payload["skill_selection"]["selected_skill"] == payload["selected_skill"]
    assert payload["skill_selection"]["selected_chain"] == payload["selected_skill_chain"]
    assert "router_selection_preserved_for_phase_2" in payload["skill_selection"]["policy_notes"]


class _FakeTelemetry:
    def record_routing_decision(self, *args: object, **kwargs: object) -> None:
        return None

    def record_routing_disagreement(self, *args: object, **kwargs: object) -> None:
        return None

    def record_step(self, *args: object, **kwargs: object) -> None:
        return None

    def record_spl_validation(self, *args: object, **kwargs: object) -> None:
        return None
