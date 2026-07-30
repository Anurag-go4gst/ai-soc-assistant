"""Workstream E pre-PR hardening: fingerprint, wrapper events, context, deadlines."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from app.llm.clients.endpoint_fingerprint import (
    ADAPTER_LOCAL_CHAT,
    API_PROTOCOL_OPENAI_CHAT,
    CandidateContractFingerprint,
    RequestContractFingerprint,
    auth_source_label,
    candidate_fingerprint_from_client,
    candidates_equivalent,
)
from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import ChatResult, LocalChatClient, LocalChatError
from app.llm.llm_call_context import (
    CALL_PURPOSE_COMPOSER,
    CALL_PURPOSE_ROUTING,
    CALL_PURPOSE_SYNTHESIS_LAB,
    get_call_purpose,
    llm_call_purpose_scope,
    run_with_call_context,
)
from app.llm.sidecar_governance import NOTE_LLM_SLOT_BUSY, run_sidecar_llm_with_timeout
from app.synthesis.narration_deadline import hop_timeout_seconds
from app.synthesis.turn_timing import (
    EndpointAttemptOutcome,
    WrapperEventOutcome,
    finalize_turn_timing,
    record_endpoint_attempt,
    record_suppressed_candidate,
    synthesis_turn_timing_scope,
)


def _contract(**kwargs: object) -> RequestContractFingerprint:
    return RequestContractFingerprint.from_generate_kwargs(
        call_purpose=str(kwargs.get("call_purpose", "routing")),
        max_tokens=int(kwargs.get("max_tokens", 10)),  # type: ignore[arg-type]
        temperature=float(kwargs.get("temperature", 0.0)),  # type: ignore[arg-type]
        response_format=kwargs.get("response_format"),  # type: ignore[arg-type]
        seed=kwargs.get("seed"),  # type: ignore[arg-type]
    )


def _client(
    *,
    base_url: str = "http://llm.example/v1",
    model: str = "model-a",
    api_key: str = "",
    adapter_type: str = ADAPTER_LOCAL_CHAT,
    api_protocol: str = API_PROTOCOL_OPENAI_CHAT,
) -> LocalChatClient:
    return LocalChatClient(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_seconds=60,
        adapter_type=adapter_type,
        api_protocol=api_protocol,
    )


def _fp(
    client: LocalChatClient,
    *,
    label: str = "local_primary",
    transport_mode: str = "synthesis",
    contract: RequestContractFingerprint | None = None,
) -> CandidateContractFingerprint:
    return candidate_fingerprint_from_client(
        client,
        provider_label=label,
        transport_mode=transport_mode,
        request_contract=contract or _contract(),
    )


def test_exact_duplicate_contract_suppressed_within_chain() -> None:
    primary = _client()
    duplicate = _client()
    contract = _contract(call_purpose="composer")
    assert candidates_equivalent(
        _fp(primary, contract=contract),
        _fp(duplicate, contract=contract),
    )


def test_same_url_model_different_adapter_retained() -> None:
    left = _client(adapter_type=ADAPTER_LOCAL_CHAT)
    right = _client(adapter_type="other_adapter")
    assert not candidates_equivalent(_fp(left), _fp(right))


def test_same_url_model_different_auth_source_retained() -> None:
    left = _client(api_key="")
    right = _client(api_key="secret-token")
    assert auth_source_label(api_key="", provider_label="local_primary") != auth_source_label(
        api_key="secret-token",
        provider_label="local_primary",
    )
    assert not candidates_equivalent(_fp(left), _fp(right))


def test_same_url_model_different_request_contract_retained() -> None:
    left = _fp(_client(), contract=_contract(max_tokens=10))
    right = _fp(_client(), contract=_contract(max_tokens=20))
    assert not candidates_equivalent(left, right)


def test_separate_routing_and_synthesis_invocations_both_preserved() -> None:
    primary = MagicMock(spec=LocalChatClient)
    primary.base_url = "http://llm.example/v1"
    primary.model = "model-a"
    primary.timeout_seconds = 60
    primary.adapter_type = ADAPTER_LOCAL_CHAT
    primary.api_protocol = API_PROTOCOL_OPENAI_CHAT
    primary.api_key = ""
    primary.generate.side_effect = [
        LocalChatError("url_error:timeout"),
        ChatResult(text="ok", model="model-a", latency_ms=5, answered_label="local_primary"),
    ]
    with synthesis_turn_timing_scope():
        client = FailoverChatClient(chain=(("local_primary", primary),))
        with llm_call_purpose_scope(CALL_PURPOSE_ROUTING):
            with pytest.raises(LocalChatError):
                client.generate(
                    system_prompt="sys",
                    user_prompt="user",
                    max_tokens=10,
                    temperature=0.0,
                    call_purpose=CALL_PURPOSE_ROUTING,
                )
        with llm_call_purpose_scope(CALL_PURPOSE_SYNTHESIS_LAB):
            result = client.generate(
                system_prompt="sys",
                user_prompt="user2",
                max_tokens=10,
                temperature=0.0,
                call_purpose=CALL_PURPOSE_SYNTHESIS_LAB,
            )
        payload = finalize_turn_timing()
    assert result.text == "ok"
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 2
    purposes = {row["call_purpose"] for row in payload["attribution_v2"]["endpoint_attempts"]}
    assert purposes == {CALL_PURPOSE_ROUTING, CALL_PURPOSE_SYNTHESIS_LAB}


def test_timeout_suppression_does_not_start_equivalent_second_candidate() -> None:
    primary = MagicMock(spec=LocalChatClient)
    primary.base_url = "http://llm.example/v1"
    primary.model = "model-a"
    primary.timeout_seconds = 60
    primary.adapter_type = ADAPTER_LOCAL_CHAT
    primary.api_protocol = API_PROTOCOL_OPENAI_CHAT
    primary.api_key = ""
    primary.generate.side_effect = LocalChatError("url_error:timeout")
    duplicate = MagicMock(spec=LocalChatClient)
    duplicate.base_url = "http://llm.example/v1"
    duplicate.model = "model-a"
    duplicate.timeout_seconds = 60
    duplicate.adapter_type = ADAPTER_LOCAL_CHAT
    duplicate.api_protocol = API_PROTOCOL_OPENAI_CHAT
    duplicate.api_key = ""
    duplicate.generate.return_value = ChatResult(text="ok", model="model-a", latency_ms=1)
    with synthesis_turn_timing_scope():
        client = FailoverChatClient(
            chain=(
                ("local_primary", primary),
                ("local_primary", duplicate),
            )
        )
        with llm_call_purpose_scope(CALL_PURPOSE_COMPOSER):
            with pytest.raises(LocalChatError):
                client.generate(
                    system_prompt="sys",
                    user_prompt="user",
                    max_tokens=10,
                    temperature=0.0,
                    call_purpose=CALL_PURPOSE_COMPOSER,
                )
        payload = finalize_turn_timing()
    duplicate.generate.assert_not_called()
    assert payload["attribution_v2"]["suppressed_candidate_count"] == 1
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 1


def test_wrapper_timeout_does_not_create_endpoint_attempt() -> None:
    def _slow() -> str:
        time.sleep(0.2)
        return "late"

    with synthesis_turn_timing_scope():
        result = run_sidecar_llm_with_timeout(
            _slow,
            timeout_seconds=0.05,
            call_purpose=CALL_PURPOSE_COMPOSER,
            wrapper_kind="composer",
        )
        payload = finalize_turn_timing()
    assert result.timed_out is True
    v2 = payload["attribution_v2"]
    assert v2["endpoint_attempt_count"] == 0
    assert len(v2["wrapper_events"]) == 1
    assert v2["wrapper_events"][0]["outcome"] == "timeout"
    assert v2["endpoint_attempt_timeout_count"] == 0


def test_wrapper_and_endpoint_nested_not_double_subtracted() -> None:
    with synthesis_turn_timing_scope():
        record_endpoint_attempt(40, outcome=EndpointAttemptOutcome.COMPLETED, call_purpose="routing")
        from app.synthesis.turn_timing import record_wrapper_event

        record_wrapper_event(
            100,
            call_purpose="routing",
            wrapper_kind="sidecar",
            outcome=WrapperEventOutcome.COMPLETED,
        )
        payload = finalize_turn_timing()
    v2 = payload["attribution_v2"]
    assert v2["endpoint_attempt_ms_total"] == 40
    assert v2["endpoint_attempt_count"] == 1
    assert len(v2["wrapper_events"]) == 1


def test_call_purpose_reaches_executor_worker() -> None:
    observed: list[str | None] = []

    def _worker() -> str:
        observed.append(get_call_purpose())
        return "ok"

    with llm_call_purpose_scope(CALL_PURPOSE_ROUTING):
        assert run_with_call_context(_worker) == "ok"
    assert observed == [CALL_PURPOSE_ROUTING]
    assert get_call_purpose() is None


def test_concurrent_sessions_retain_distinct_purposes() -> None:
    seen: dict[str, str | None] = {}
    barrier = threading.Barrier(2)

    def _worker(name: str, purpose: str) -> None:
        with llm_call_purpose_scope(purpose):
            barrier.wait(timeout=2)
            seen[name] = get_call_purpose()

    t1 = threading.Thread(target=_worker, args=("a", CALL_PURPOSE_ROUTING))
    t2 = threading.Thread(target=_worker, args=("b", CALL_PURPOSE_COMPOSER))
    t1.start()
    t2.start()
    t1.join(timeout=3)
    t2.join(timeout=3)
    assert seen == {"a": CALL_PURPOSE_ROUTING, "b": CALL_PURPOSE_COMPOSER}


def test_frozen_session_ignores_late_endpoint_and_wrapper_events() -> None:
    from app.synthesis.turn_timing import TurnTimingSession, record_wrapper_event

    session = TurnTimingSession()
    session.record_endpoint_attempt(5, outcome=EndpointAttemptOutcome.COMPLETED)
    payload = session.finalize()
    session.record_endpoint_attempt(90_000, outcome=EndpointAttemptOutcome.TIMEOUT)
    record_wrapper_event(90_000, call_purpose="shadow", wrapper_kind="sidecar", outcome=WrapperEventOutcome.TIMEOUT)
    assert payload["attribution_v2"]["endpoint_attempt_count"] == 1
    assert payload["attribution_v2"].get("wrapper_events", []) == []


def test_inner_socket_timeout_capped_to_wrapper_remaining_budget() -> None:
    deadline = time.monotonic() + 0.5
    capped = hop_timeout_seconds(120, deadline)
    assert capped is not None
    assert capped <= 0.5 + 0.05


def test_no_endpoint_call_starts_after_deadline() -> None:
    primary = MagicMock(spec=LocalChatClient)
    primary.base_url = "http://llm.example/v1"
    primary.model = "model-a"
    primary.timeout_seconds = 60
    primary.adapter_type = ADAPTER_LOCAL_CHAT
    primary.api_protocol = API_PROTOCOL_OPENAI_CHAT
    primary.api_key = ""
    primary.generate.side_effect = LocalChatError("url_error:timeout")
    client = FailoverChatClient(chain=(("local_primary", primary), ("fallback", primary)))
    with pytest.raises(LocalChatError):
        client.generate(
            system_prompt="sys",
            user_prompt="user",
            max_tokens=10,
            temperature=0.0,
            deadline=time.monotonic() - 1,
            call_purpose=CALL_PURPOSE_COMPOSER,
        )
    primary.generate.assert_not_called()


def test_slot_saturation_records_wrapper_event_not_endpoint() -> None:
    import app.llm.sidecar_governance as sg

    sg._MODEL_SLOT_SEMAPHORE = threading.BoundedSemaphore(1)
    sg._MODEL_SLOT_SEMAPHORE.acquire()

    def _slow() -> str:
        time.sleep(0.2)
        return "ok"

    try:
        with synthesis_turn_timing_scope():
            result = run_sidecar_llm_with_timeout(_slow, timeout_seconds=1.0, call_purpose="routing")
            payload = finalize_turn_timing()
    finally:
        sg._MODEL_SLOT_SEMAPHORE.release()

    assert NOTE_LLM_SLOT_BUSY in result.notes
    v2 = payload["attribution_v2"]
    assert v2["endpoint_attempt_count"] == 0
    assert v2["wrapper_events"][0]["outcome"] == "saturated"
