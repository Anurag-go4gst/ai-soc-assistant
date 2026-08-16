"""Suite-wide guards for backend tests.

The deployed runtime (Docker container, root `.env`) enables live LLM synthesis:
`AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` +
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
import threading
from collections.abc import Iterator
from urllib.error import URLError

import pytest

LIVE_LLM_OPT_IN_ENV = "AI_SOC_TESTS_ALLOW_LIVE_LLM"


def _is_integration_test(request: pytest.FixtureRequest) -> bool:
    return request.node.get_closest_marker("integration") is not None


@pytest.fixture(autouse=True)
def canonical_execution_idempotency_in_memory_for_tests(request: pytest.FixtureRequest) -> Iterator[None]:
    if _is_integration_test(request):
        yield
        return
    from app.chat.canonical_execution_idempotency import (
        clear_in_memory_store_for_tests,
        use_in_memory_store_for_tests,
    )

    use_in_memory_store_for_tests(True)
    yield
    clear_in_memory_store_for_tests()
    use_in_memory_store_for_tests(False)


@pytest.fixture(autouse=True)
def canonical_handoff_in_memory_for_tests(request: pytest.FixtureRequest) -> Iterator[None]:
    """Handoff persistence is fail-closed without DB; tests opt into in-memory store."""
    if _is_integration_test(request):
        yield
        return
    from app.chat.canonical_handoff_repository import (
        clear_in_memory_store_for_tests,
        use_in_memory_store_for_tests,
    )

    use_in_memory_store_for_tests(True)
    yield
    clear_in_memory_store_for_tests()
    use_in_memory_store_for_tests(False)


@pytest.fixture(autouse=True)
def resource_plan_test_authority() -> Iterator[None]:
    from app.planner.resource_plan_authority import (
        TEST_AUTHORITY,
        register_test_resource_plan_compose_hook,
        resource_plan_authority,
    )
    from app.tests.support.compose_resource_plan_testutil import attach_resource_plan_for_tests

    register_test_resource_plan_compose_hook(attach_resource_plan_for_tests)
    with resource_plan_authority(TEST_AUTHORITY):
        yield
    register_test_resource_plan_compose_hook(None)


@pytest.fixture(autouse=True)
def reset_model_slot_guard() -> Iterator[None]:
    """Give each test a fresh model-slot semaphore.

    The single-flight guard intentionally keeps a timed-out (orphaned) sidecar hop
    holding the slot until its provider truly finishes — correct single-slot
    semantics. In-process that means a slow-provider test could leave the slot held
    and poison the next test's non-blocking acquire. Rebinding to a fresh semaphore
    isolates tests; an orphan releasing the stale object is harmless.
    """
    from app.llm import sidecar_governance as sg

    sg._MODEL_SLOT_SEMAPHORE = threading.BoundedSemaphore(sg._MODEL_SLOTS)
    sg.reset_t4_circuit()
    os.environ.pop("AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD", None)
    yield


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


def _mcp_env_keys() -> set[str]:
    return {key for key in os.environ if key == "MCP_MODE" or key.startswith("MCP_")}


@pytest.fixture()
def isolated_connection_store_apply() -> Iterator[None]:
    """Snapshot every global `connection_store.apply_to_settings()` mutates.

    apply_to_settings writes ~15 settings attributes AND MCP_* environment variables
    (including MCP_SERVER_<id>_* for every configured server). Any test that triggers
    it without this fixture leaks that state into every later test in the suite
    (found 2026-07-05: one round-trip test broke 11 unrelated tests; #109:
    test_mcp_connection_store_multi.py leaked MCP_GLOBAL_EXECUTION_ENABLED).
    Request this fixture in any test that calls save_connection()/apply_to_settings()
    or routes_settings save/discover helpers that call them.
    """
    from app.config import settings

    touched_settings = (
        "splunk_mcp_enabled",
        "ai_soc_environment_mode",
        "ai_soc_mcp_connection_store_path",
        "splunk_mcp_server_id",
        "splunk_mcp_discovery_mode",
        "splunk_mcp_base_url",
        "splunk_mcp_token",
        "splunk_saia_tools_enabled",
        "splunk_ai_assistant_mode",
        "splunk_allow_run_saved_search",
        "splunk_allowed_saved_searches",
        "mcp_mode",
        "mcp_servers",
        "mcp_default_server",
        "mcp_global_execution_enabled",
    )
    settings_snapshot = {key: getattr(settings, key) for key in touched_settings}
    env_snapshot = {key: os.environ[key] for key in _mcp_env_keys()}
    yield
    for key, value in settings_snapshot.items():
        setattr(settings, key, value)
    leaked = _mcp_env_keys() - env_snapshot.keys()
    for key in leaked:
        del os.environ[key]
    os.environ.update(env_snapshot)
