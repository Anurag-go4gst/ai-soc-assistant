from __future__ import annotations

import re

DEFAULT_TIME_WINDOW = "earliest=-24h latest=now"


def normalize_time_window(query: str) -> str | None:
    normalized = " ".join(query.lower().split())
    if not normalized:
        return None
    explicit = _explicit_spl_bounds(normalized)
    if explicit:
        return explicit
    if "last hour" in normalized or "past hour" in normalized:
        return "earliest=-60m latest=now"
    if match := re.search(r"\b(?:last|in)\s+(\d+)\s*(minute|minutes|min|mins|m)\b", normalized):
        return f"earliest=-{match.group(1)}m latest=now"
    if match := re.search(r"\blast\s+(\d+)\s*(hour|hours|hr|hrs|h)\b", normalized):
        return f"earliest=-{match.group(1)}h latest=now"
    if match := re.search(r"\blast\s+(\d+)\s*(day|days|d)\b", normalized):
        return f"earliest=-{match.group(1)}d latest=now"
    if "last 24h" in normalized or "last 24 hours" in normalized:
        return "earliest=-24h latest=now"
    if "today" in normalized:
        return "earliest=@d latest=now"
    if "yesterday" in normalized:
        return "earliest=-1d@d latest=@d"
    return None


def time_window_or_default(query: str, default: str = DEFAULT_TIME_WINDOW) -> str:
    return normalize_time_window(query) or default


def _explicit_spl_bounds(normalized_query: str) -> str | None:
    earliest = re.search(r"\bearliest=([^\s|]+)", normalized_query)
    latest = re.search(r"\blatest=([^\s|]+)", normalized_query)
    if earliest and latest:
        return f"earliest={earliest.group(1)} latest={latest.group(1)}"
    if earliest:
        return f"earliest={earliest.group(1)} latest=now"
    return None
