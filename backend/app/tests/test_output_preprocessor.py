"""Plan 1.1 — shared LLM output pre-processor.

Legacy direct ``extract_first_json_object`` callers intentionally left unchanged:
``llm_judge`` (eval-only), ``mitre_risk_rationale``, ``missing_evidence_reasoner``,
``routing/llm_route_plan_json``, ``spl/llm_fallback._strict_json_payload`` (internal).
Synthesis/action-proposal parsers deferred to plan 6.1.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.chat.llm_intent_advisor import generate_llm_intent_advisory
from app.config import settings
from app.llm.adapter.output_preprocessor import (
    BRIDGE_PROPOSAL_SCHEMA,
    preprocess_llm_output,
)
from app.planner.llm_plan_bridge import propose_validated_llm_plan
from app.spl.llm_plan_compiler import PLAN_JSON_SCHEMA, get_detection_plan

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "llm_outputs" / "preprocessor_corpus.json"


@pytest.fixture(name="corpus")
def fixture_corpus() -> dict[str, str]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_fenced_plan_parses_with_repaired_used(corpus: dict[str, str]) -> None:
    result = preprocess_llm_output(corpus["fenced_detection_plan"], PLAN_JSON_SCHEMA)
    assert result.payload is not None
    assert result.payload["data_domain"] == "auth"
    assert result.verdict in {"used", "repaired_used"}
    assert result.llm_output_utilization == "used"


def test_enum_case_normalized(corpus: dict[str, str]) -> None:
    result = preprocess_llm_output(corpus["enum_case_plan"], PLAN_JSON_SCHEMA)
    assert result.payload is not None
    assert result.payload["data_domain"] == "network"
    assert "enum_case_normalized:data_domain" in result.repairs
    assert result.verdict == "repaired_used"


def test_truncated_output_dropped(corpus: dict[str, str]) -> None:
    result = preprocess_llm_output(corpus["truncated"], BRIDGE_PROPOSAL_SCHEMA)
    assert result.payload is None
    assert result.verdict == "dropped:truncated"


def test_echo_of_input_dropped(corpus: dict[str, str]) -> None:
    echo = corpus["echo_of_input"]
    result = preprocess_llm_output(echo, BRIDGE_PROPOSAL_SCHEMA, echo_of=echo)
    assert result.payload is None
    assert result.verdict == "dropped:echo_of_input"


def test_retry_path_used_once(corpus: dict[str, str]) -> None:
    calls = {"n": 0}

    def _retry(_errors: list[str]) -> str:
        calls["n"] += 1
        return corpus["valid_plan"]

    result = preprocess_llm_output(
        corpus["truncated"],
        BRIDGE_PROPOSAL_SCHEMA,
        allow_retry=True,
        retry_fn=_retry,
    )
    assert calls["n"] == 1
    assert result.verdict == "retried_used"
    assert result.payload is not None


def test_plan_bridge_routes_through_preprocessor(monkeypatch: pytest.MonkeyPatch, corpus: dict[str, str]) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)

    class _FakeClient:
        def generate(self, **_kwargs):
            class _R:
                text = corpus["valid_plan"]

            return _R()

    plan = propose_validated_llm_plan(
        query="hunt dns beaconing",
        match_path="out_of_registry",
        action_mode=None,
        mcp_allowed=False,
        client=_FakeClient(),
        require_bridge_flags=False,
    )
    assert plan is not None
    assert plan.provenance.get("llm_output_utilization") == "used"


def test_plan_compiler_routes_through_preprocessor(corpus: dict[str, str]) -> None:
    plan, errors = get_detection_plan(
        "hunt rare dns queries",
        llm_raw_output_provider=lambda: corpus["trailing_comma_plan"],
    )
    assert errors == []
    assert plan is not None
    assert plan["data_domain"] == "dns"


def test_intent_advisor_never_retries_and_keeps_bound(monkeypatch: pytest.MonkeyPatch, corpus: dict[str, str]) -> None:
    monkeypatch.setattr(settings, "ai_soc_llm_intent_advisor_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")

    with patch("app.chat.llm_intent_advisor.preprocess_llm_output") as mocked:
        mocked.return_value = type(
            "R",
            (),
            {
                "payload": {"paraphrase_detected": False},
                "verdict": "used",
                "repairs": [],
                "extraction_warnings": [],
                "validation_errors": [],
                "llm_output_utilization": "used",
            },
        )()
        generate_llm_intent_advisory(
            "test query",
            llm_raw_output_provider=lambda: corpus["valid_intent_advisory"],
            timeout_seconds=2.0,
            allow_failover=True,
        )
        assert mocked.call_args.kwargs.get("allow_retry") is False

    advisory = generate_llm_intent_advisory(
        "test query",
        llm_raw_output_provider=lambda: corpus["valid_intent_advisory"],
        timeout_seconds=2.0,
    )
    assert advisory.llm_called is True
    assert advisory.dropped_reasons == []
