"""Contract: FailoverChatClient must accept `seed` and negotiate it per hop.

Regression for the live `/chat` HTTP 500 on explicit SPL/detection requests:
`get_detection_plan` calls `client.generate(seed=...)`, but the configured
`FailoverChatClient.generate` had no `seed` parameter -> TypeError. The fix adds
`seed` and forwards it only to child hops whose `generate` accepts it.

All clients here are fakes; no real llama-server endpoint is touched, so the
live-LLM guard conftest stays satisfied.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.llm.clients.failover_client import FailoverChatClient
from app.llm.clients.local_chat_client import ChatResult, LocalChatClient, LocalChatError
from app.llm.clients.endpoint_resolver import build_failover_chat_client
from app.spl.llm_plan_compiler import get_detection_plan


@dataclass
class _SeedCapableClient:
    """Records the kwargs it received; accepts the full optional surface."""

    base_url: str = "http://fake-seed"
    model: str = "fake-seed-model"
    timeout_seconds: int = 60
    fail: bool = False
    received: dict = field(default_factory=dict)

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
        seed: int | None = None,
    ) -> ChatResult:
        self.received = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": response_format,
            "seed": seed,
        }
        if self.fail:
            raise LocalChatError("seed_client_forced_failure")
        return ChatResult(text="seed-capable-result", model=self.model, latency_ms=1)


@dataclass
class _SeedIncapableClient:
    """A hop whose `generate` does NOT accept `seed` (proves per-hop strip).

    Passing `seed=` here would raise TypeError; the failover client must omit it.
    """

    base_url: str = "http://fake-noseed"
    model: str = "fake-noseed-model"
    timeout_seconds: int = 60
    text: str = "no-seed-result"
    received: dict = field(default_factory=dict)

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
    ) -> ChatResult:
        self.received = {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": response_format,
        }
        return ChatResult(text=self.text, model=self.model, latency_ms=1)


def _call(client: FailoverChatClient, *, seed: int | None) -> ChatResult:
    return client.generate(
        system_prompt="sys",
        user_prompt="usr",
        max_tokens=64,
        temperature=0.0,
        response_format={"type": "json_object"},
        seed=seed,
    )


def test_seed_forwarded_to_seed_capable_child() -> None:
    capable = _SeedCapableClient()
    client = FailoverChatClient(chain=(("primary", capable),))

    result = _call(client, seed=4242)

    assert result.text == "seed-capable-result"
    assert capable.received["seed"] == 4242
    assert capable.received["response_format"] == {"type": "json_object"}


def test_seed_stripped_for_incapable_child_no_typeerror() -> None:
    incapable = _SeedIncapableClient()
    client = FailoverChatClient(chain=(("primary", incapable),))

    # Would raise TypeError if `seed` were forwarded to this hop.
    result = _call(client, seed=4242)

    assert result.text == "no-seed-result"
    assert "seed" not in incapable.received
    assert incapable.received["response_format"] == {"type": "json_object"}


def test_failover_succeeds_across_mixed_capability_chain() -> None:
    # First hop is seed-capable but fails; second hop cannot accept seed.
    capable = _SeedCapableClient(fail=True)
    incapable = _SeedIncapableClient(text="fallback-ok")
    client = FailoverChatClient(chain=(("primary", capable), ("fallback", incapable)))

    result = _call(client, seed=99)

    # Failover reached the incapable hop without a TypeError, and seed was
    # forwarded to the capable hop only.
    assert result.text == "fallback-ok"
    assert result.answered_label == "fallback"
    assert capable.received["seed"] == 99
    assert "seed" not in incapable.received


def test_get_detection_plan_no_typeerror_with_seed_incapable_hop() -> None:
    """The real crash path: get_detection_plan passes seed= into the client.

    With a seed-incapable hop in the chain, no TypeError must escape — the call
    must reach the model attempt and return cleanly (here, a parsed plan).
    """
    plan_obj = {
        "detection_family": "test_family",
        "data_domain": "ot_network",
        "time_window_hours": 24,
        "filters": [],
        "group_by": ["src_ip"],
        "metric": "count",
        "assumptions": [],
        "required_fields": ["src_ip"],
    }
    incapable = _SeedIncapableClient(text=json.dumps(plan_obj))
    client = FailoverChatClient(chain=(("primary", incapable),))

    payload, errors = get_detection_plan("detect modbus writes", client=client, seed=777)

    assert errors == []
    assert payload is not None
    assert payload["detection_family"] == "test_family"
    assert "seed" not in incapable.received


def test_detection_plan_through_real_failover_builder(monkeypatch) -> None:
    """Exercise the configured builder, not only a hand-built failover instance."""
    from app.llm.clients import endpoint_resolver

    monkeypatch.setattr(endpoint_resolver.settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(
        endpoint_resolver.settings, "ai_soc_llm_local_base_url", "http://builder-test"
    )
    monkeypatch.setattr(endpoint_resolver.settings, "ai_soc_llm_local_model", "test-model")
    monkeypatch.setattr(endpoint_resolver.settings, "ai_soc_llm_qwen_primary_enabled", False)
    monkeypatch.setattr(
        endpoint_resolver.settings, "ai_soc_llm_foundation_sec_instruct_base_url", ""
    )

    plan_obj = {
        "detection_family": "builder_family",
        "data_domain": "authentication",
        "time_window_hours": 1,
        "filters": [],
        "group_by": ["user"],
        "metric": "count",
        "assumptions": [],
        "required_fields": ["user"],
    }
    observed: dict[str, object] = {}

    def _generate(
        self: LocalChatClient,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: dict | None = None,
        seed: int | None = None,
    ) -> ChatResult:
        observed.update(seed=seed, response_format=response_format, base_url=self.base_url)
        return ChatResult(text=json.dumps(plan_obj), model=self.model, latency_ms=1)

    monkeypatch.setattr(LocalChatClient, "generate", _generate)
    client = build_failover_chat_client(sidecar=False)
    assert isinstance(client, FailoverChatClient)

    payload, errors = get_detection_plan("detect failed logins", client=client, seed=8080)

    assert errors == []
    assert payload and payload["detection_family"] == "builder_family"
    assert observed["seed"] == 8080
    assert observed["base_url"] == "http://builder-test"
