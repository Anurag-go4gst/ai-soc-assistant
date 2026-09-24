"""One incident told across several Experience Center questions.

S1, Q1 and S3 describe the same IP (198.51.100.42), jump host (10.20.1.10) and account
(svc_jump_ops). Shown side by side without context their verdicts looked contradictory (MEDIUM
→ P1 → confirmed malicious). They are successive days of one incident, and the payload says so.
"""

from __future__ import annotations

from typing import Any

THREAD_ID = "INC-2026-89412"

_THREAD: dict[str, dict[str, Any]] = {
    "s1_governed_splunk_investigation": {
        "day": 0,
        "title": "New IP seen — watch raised",
        "verdict_so_far": "MEDIUM · not confirmed malicious · 14-day watch, no block",
        "next": {"scenario_id": "firewall_deny_coordinated_attack", "label": "Day 1 — the watch fires"},
    },
    "firewall_deny_coordinated_attack": {
        "day": 1,
        "title": "Watch fired — escalated to P1",
        "verdict_so_far": "Day 0 was MEDIUM; today the IP returned at volume and logons are attributed to it",
        "next": {"scenario_id": "s3_firewall_team_coordination", "label": "Day 1 — block it through the firewall process"},
    },
    "s3_firewall_team_coordination": {
        "day": 1,
        "title": "Block through the firewall process",
        "verdict_so_far": "P1 · account use attributed on Day 1 · block requested",
        "next": None,
    },
}


def story_thread_for(scenario_id: str) -> dict[str, Any] | None:
    entry = _THREAD.get(scenario_id)
    if entry is None:
        return None
    return {"thread_id": THREAD_ID, "total_days": 2, **entry}
