"""S6d — durable structured session pin store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.chat.session_store import (
    SessionPins,
    clear_all_session_pins_for_tests,
    delete_session_pins,
    get_session_pins,
    save_session_pins,
)
from app.config import settings


@pytest.fixture(autouse=True)
def _reset_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "ai_soc_session_store_backend", "file")
    monkeypatch.setattr(settings, "ai_soc_session_store_file_dir", str(tmp_path / "pins"))
    clear_all_session_pins_for_tests()


def test_ttl_expiry_deletes_pins() -> None:
    session_id = "ttl-session"
    save_session_pins(
        SessionPins(
            session_id=session_id,
            last_alert_id="ALT-1",
            updated_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        ),
        refresh_ttl=False,
    )
    assert get_session_pins(session_id) is None


def test_multi_session_isolation() -> None:
    save_session_pins(SessionPins(session_id="sess-a", last_alert_id="A"))
    save_session_pins(SessionPins(session_id="sess-b", last_alert_id="B"))
    assert get_session_pins("sess-a").last_alert_id == "A"
    assert get_session_pins("sess-b").last_alert_id == "B"


def test_stale_pins_ignored_on_read() -> None:
    session_id = "stale"
    save_session_pins(
        SessionPins(
            session_id=session_id,
            last_alert_id="ALT-old",
            updated_at=datetime.now(UTC) - timedelta(hours=3),
            expires_at=datetime.now(UTC) - timedelta(seconds=30),
        ),
        refresh_ttl=False,
    )
    assert get_session_pins(session_id) is None


def test_memory_fallback_when_backend_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_session_store_backend", "memory")
    clear_all_session_pins_for_tests()
    save_session_pins(SessionPins(session_id="mem-1", last_alert_id="MEM"))
    assert get_session_pins("mem-1") is not None
    delete_session_pins("mem-1")
    assert get_session_pins("mem-1") is None


def test_file_backend_persists_across_reads() -> None:
    save_session_pins(SessionPins(session_id="file-1", last_use_case_id="auth_failed_login_spike"))
    reloaded = get_session_pins("file-1")
    assert reloaded is not None
    assert reloaded.last_use_case_id == "auth_failed_login_spike"
