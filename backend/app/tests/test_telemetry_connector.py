from app.connectors.telemetry.db import DbTelemetryConnector


def test_telemetry_db_records_trace_and_step(monkeypatch) -> None:
    connector = DbTelemetryConnector(database_url="postgresql://example/test")
    calls: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(connector, "_run", lambda sql, *args: calls.append((sql, args)))

    handle = connector.start_trace("trace-1", entrypoint="test", metadata={"password": "redacted"})
    connector.record_step("trace-1", "route", "ok", detail="done")
    connector.end_trace("trace-1")

    assert handle.trace_id == "trace-1"
    assert len(calls) == 3
    assert "ai_trace_runs" in calls[0][0]
    assert "ai_trace_steps" in calls[1][0]
    assert "password" not in str(calls[0][1])


def test_routing_disagreement_can_be_recorded(monkeypatch) -> None:
    connector = DbTelemetryConnector(database_url="postgresql://example/test")
    calls: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(connector, "_run", lambda sql, *args: calls.append((sql, args)))

    connector.record_routing_disagreement(
        "trace-2",
        deterministic_skill="alert_summary",
        planner_skill="attack_discovery",
        reason="confidence_delta",
    )

    assert len(calls) == 1
    assert "routing_disagreements" in calls[0][0]
    assert "confidence_delta" in str(calls[0][1])


def test_harness_result_can_be_recorded(monkeypatch) -> None:
    connector = DbTelemetryConnector(database_url="postgresql://example/test")
    calls: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(connector, "_run", lambda sql, *args: calls.append((sql, args)))

    test_run_id = connector.record_harness_result(
        "trace-3",
        test_run_id="run-3",
        case_id="case_01",
        user_query="show failed logins",
        expected_skill="attack_discovery",
        actual_skill="attack_discovery",
        generated_spl_ref="search index=pgcil_soc | stats count",
        spl_validation_result={"passed": True},
        mcp_execution_status="mock",
        expected_findings={"min_rows": 1},
        actual_findings_summary="1 rows",
        layer_results={"skill": True, "spl_spec": True, "findings": True},
        final_pass=True,
    )

    assert test_run_id == "run-3"
    assert len(calls) == 2
    assert "harness_test_runs" in calls[0][0]
    assert "harness_test_case_results" in calls[1][0]


def test_slim_control_plane_trace_keeps_plan_dispatch() -> None:
    from app.connectors.telemetry.db import _slim_control_plane_trace

    trace = {
        "rag_trace": {"hits": 1},
        "plan_dispatch": {"dispatch_authority": "pipeline_dispatch_v2", "dispatch_schedule": ["rag_early"]},
        "pipeline_dispatch": {"decision": {"stage_schedule": ["rag_early"]}},
        "secret_blob": "drop-me",
    }
    slim = _slim_control_plane_trace(trace)
    assert slim["plan_dispatch"]["dispatch_authority"] == "pipeline_dispatch_v2"
    assert "secret_blob" not in slim
