"""Suite-wide guards for backend tests.

The deployed runtime (Docker container, root `.env`) enables live LLM synthesis:
`CONTROL_PLANE_ENABLED=true` + `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` +
`AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true` with a reachable llama-server at
`host.docker.internal:8081`. Every `/api/chat` test then narrates through the
real single-slot CPU model (~minutes per generation, 120s timeout per call),
which serializes the suite into an apparent hang and starves the production
demo model. Tests must never depend on a live model: any accidental call is
converted into the same `LocalChatError` the runtime maps to its deterministic
fallback, so behavior matches an unreachable endpoint rather than a new mode.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.error import URLError

import pytest

LIVE_LLM_OPT_IN_ENV = "AI_SOC_TESTS_ALLOW_LIVE_LLM"


def _blocked_urlopen(*args: object, **kwargs: object) -> object:
    raise URLError(
        f"live LLM calls are disabled under pytest; set {LIVE_LLM_OPT_IN_ENV}=1 to opt in"
    )


@pytest.fixture(autouse=True)
def disable_spl_execution_confirmation_in_tests(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep legacy MCP gate tests direct; confirmation flow is covered in test_execution_confirmation."""
    monkeypatch.setattr("app.config.settings.ai_soc_require_spl_execution_confirmation", False)
    yield


@pytest.fixture(autouse=True)
def block_live_llm_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail any LocalChatClient network call with URLError -> LocalChatError fallback."""
    if os.environ.get(LIVE_LLM_OPT_IN_ENV) == "1":
        yield
        return
    monkeypatch.setattr("app.llm.clients.local_chat_client.urlopen", _blocked_urlopen)
    yield
