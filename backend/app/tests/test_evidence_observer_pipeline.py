from __future__ import annotations

from app.chat.evidence_loop import initialize_loop
from app.chat.pipeline import graph_node_evidence_planning
from app.llm.sidecar_clients import SidecarInvocationResult
from app.llm.turn_llm_budget import TurnLlmBudget
from app.schemas.requests import ChatRequest


class _Telemetry:
    def __init__(self) -> None:
        self.llm_calls: list[dict] = []
        self.merges: list[dict] = []

    def record_llm_call(self, trace_id: str, **fields) -> None:
        self.llm_calls.append({"trace_id": trace_id, **fields})

    def merge_run_metadata(self, trace_id: str, metadata: dict) -> None:
        self.merges.append({"trace_id": trace_id, "metadata": metadata})


def _base_state() -> dict:
    return {
        **initialize_loop(["splunk_run_query"], required_produces=["result_rows"]),
        "request": ChatRequest(message="What did the last rows show for fw-edge-01?"),
        "trace_id": "observer-test",
        "effective_query": "What did the last rows show for fw-edge-01?",
        "evidence_plan": {"needs_mcp": True, "mcp_allowed": True},
        "structured_context": {"trace_id": "observer-test", "selected_skill": "spl_generation"},
        "execution": {
            "status": "executed",
            "result_count": 1,
            "results_preview": [
                {
                    "_time": "2026-07-05T00:00:00Z",
                    "host": "fw-edge-01",
                    "action": "denied",
                    "dest_port": "445",
                }
            ],
            "raw_result": {
                "rows": [
                    {
                        "_time": "2026-07-05T00:00:00Z",
                        "host": "fw-edge-01",
                        "action": "denied",
                        "dest_port": "445",
                    }
                ]
            },
        },
    }


def _enable_observer(monkeypatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_live_synthesis_enabled", True)


def test_observer_rows_attach_to_structured_context_and_trace(monkeypatch) -> None:
    _enable_observer(monkeypatch)
    calls: list[str] = []
    telemetry = _Telemetry()

    def fake_invoke(**kwargs):
        calls.append(kwargs["user_prompt"])
        return SidecarInvocationResult(
            raw_output=(
                '{"observations":[{"claim":"Host fw-edge-01 denied port 445",'
                '"row_refs":[1],"confidence":"high"}],"next_hop_hint":null,"unreadable":false}'
            ),
            timed_out=False,
            answered_label="fake_observer",
        )

    monkeypatch.setattr("app.chat.pipeline.invoke_sidecar_role_with_metadata", fake_invoke)
    monkeypatch.setattr("app.chat.pipeline.get_telemetry_connector", lambda: telemetry)
    state = {**_base_state(), "llm_turn_budget": TurnLlmBudget(deadline_seconds=75)}

    out = graph_node_evidence_planning(state)

    assert calls
    structured = out["structured_context"]
    assert structured["llm_observations"][0]["claim"] == "Host fw-edge-01 denied port 445"
    assert structured["llm_observations"][0]["provenance"] == "llm_observation"
    trace = out["evidence_observer_trace"]
    assert trace["role"] == "evidence_observer"
    assert trace["provider_label"] == "fake_observer"
    assert trace["grounded_n"] == 1
    assert trace["dropped_m"] == 0
    assert telemetry.llm_calls
    assert telemetry.llm_calls[0]["guard_status"] == "grounded"
    assert telemetry.merges
    persisted = str(telemetry.merges[0]["metadata"])
    assert "raw_result" not in persisted
    assert "dest_port" not in persisted
    assert "Numbered sanitized MCP rows" not in persisted


def test_observer_budget_exhaustion_records_skip_without_call(monkeypatch) -> None:
    _enable_observer(monkeypatch)
    called = False

    def fake_invoke(**kwargs):
        nonlocal called
        called = True
        return SidecarInvocationResult(raw_output=None, timed_out=False, answered_label=None)

    monkeypatch.setattr("app.chat.pipeline.invoke_sidecar_role_with_metadata", fake_invoke)
    state = {**_base_state(), "llm_turn_budget": TurnLlmBudget(max_sidecar_calls=0)}

    out = graph_node_evidence_planning(state)

    assert called is False
    assert out["evidence_observer_trace"]["skipped_reason"] == "turn_budget_exhausted"
    assert "llm_observations" not in out["structured_context"]


def test_observer_not_invoked_when_live_synthesis_disabled(monkeypatch) -> None:
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_final_synthesis_enabled", False)
    monkeypatch.setattr("app.chat.pipeline.settings.ai_soc_llm_live_synthesis_enabled", False)
    called = False

    def fake_invoke(**kwargs):
        nonlocal called
        called = True
        return SidecarInvocationResult(raw_output=None, timed_out=False, answered_label=None)

    monkeypatch.setattr("app.chat.pipeline.invoke_sidecar_role_with_metadata", fake_invoke)

    out = graph_node_evidence_planning(_base_state())

    assert called is False
    assert out["evidence_observer_trace"]["skipped_reason"] == "live_synthesis_disabled"
