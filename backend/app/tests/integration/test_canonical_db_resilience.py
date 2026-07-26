"""Fail-closed persistence behaviour without a live database."""

from __future__ import annotations

import pytest

from app.chat.canonical_handoff_models import CanonicalHandoffRecord
from app.chat.canonical_handoff_repository import HandoffPersistenceError, use_in_memory_store_for_tests
from app.chat.canonical_handoff_store import save_handoff
from app.config import settings

pytestmark = pytest.mark.integration


def test_handoff_persistence_fail_closed_when_database_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_in_memory_store_for_tests(False)
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql://ai_soc:change-me@postgres:5432/ai_soc_assistant",
    )
    with pytest.raises(HandoffPersistenceError):
        save_handoff(
            CanonicalHandoffRecord(
                handoff_id="int:failclosed",
                handoff_version=1,
                status="created",
            )
        )
