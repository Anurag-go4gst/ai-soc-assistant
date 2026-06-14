from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.llm.clients.failover_client import FailoverChatClient
from app.llm.sidecar_clients import build_failover_client_for_role


def test_disabled_role_returns_no_client() -> None:
    with patch("app.llm.sidecar_clients.resolve_sidecar_role_status") as resolve:
        resolve.return_value = MagicMock(
            enabled=False,
            role_configured=True,
            rejected_reason=None,
            llm_assist_skipped_reason="role_not_enabled",
        )
        assert build_failover_client_for_role("intent_shadow_classifier") is None


def test_unconfigured_role_uses_global_chain() -> None:
    fake_client = FailoverChatClient(chain=())
    with patch("app.llm.sidecar_clients.resolve_sidecar_role_status") as resolve:
        resolve.return_value = MagicMock(
            enabled=False,
            role_configured=False,
            rejected_reason=None,
            llm_assist_skipped_reason="role_not_configured",
        )
        with patch(
            "app.llm.sidecar_clients.build_failover_chat_client",
            return_value=fake_client,
        ) as build:
            result = build_failover_client_for_role("intent_shadow_classifier")
            assert result is fake_client
            build.assert_called_once()


def test_enabled_role_builds_client() -> None:
    fake_client = FailoverChatClient(chain=())
    with patch("app.llm.sidecar_clients.resolve_sidecar_role_status") as resolve:
        resolve.return_value = MagicMock(
            enabled=True,
            role_configured=True,
            rejected_reason=None,
            llm_assist_skipped_reason=None,
        )
        with patch(
            "app.llm.sidecar_clients.build_failover_chat_client",
            return_value=fake_client,
        ) as build:
            result = build_failover_client_for_role("intent_shadow_classifier")
            assert result is fake_client
            build.assert_called_once()
