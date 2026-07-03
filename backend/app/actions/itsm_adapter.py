"""Item 6.1 — ITSM adapter interface + mock implementation.

The action lane (`app.actions.action_lane`) dispatches an approved action
through an adapter matching this interface. Only `MockItsmAdapter` exists
today; a real connector (ServiceNow, Jira, etc.) is a future plan item once
a user names the target system — this module makes no assumption about
which one.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any


class ItsmAdapter(ABC):
    """Interface every ITSM connector (mock or live) must implement."""

    @abstractmethod
    def create_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a ticket from a validated, CanonicalFacts-derived payload.

        Returns an outcome dict with at least `status` ("created" or
        "failed") and, on success, a `ticket_id`. Never raises for ordinary
        adapter-level failures — callers key audit/outcome recording off the
        returned dict, not exceptions.
        """


class MockItsmAdapter(ItsmAdapter):
    """Deterministic mock — never calls a real ITSM system. Fixture-tested
    posture only (`onboarding_status: fixture_tested` on the registry row)."""

    def create_ticket(self, payload: dict[str, Any]) -> dict[str, Any]:
        ticket_id = f"MOCK-{uuid.uuid4().hex[:8].upper()}"
        return {
            "status": "created",
            "ticket_id": ticket_id,
            "provider": "mock_itsm",
            "created_at": datetime.now(UTC).isoformat(),
            "summary": payload.get("summary"),
        }
