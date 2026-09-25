"""Story-thread badge for Experience Center questions — retired.

S1, Q1 and S3 used to carry a "Day 0 / Day 1 — the watch fires" badge. That scripted future
events: nothing guarantees a watch fires, and a watch firing never decides a verdict by itself.
The questions now link through facts instead — the same incident (INC0048213), IP, jump host and
account appear in each question's findings — so no scenario returns a thread.
"""

from __future__ import annotations

from typing import Any


def story_thread_for(scenario_id: str) -> dict[str, Any] | None:
    """No scenario carries a scripted story thread."""
    del scenario_id
    return None
