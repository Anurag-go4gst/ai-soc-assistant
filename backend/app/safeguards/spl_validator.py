import re

BLOCKED_COMMANDS = {
    "delete",
    "outputlookup",
    "sendemail",
    "script",
    "map",
    "collect",
}

AGGREGATION_COMMANDS = {
    "stats",
    "timechart",
    "chart",
    "top",
    "rare",
}


def _tokens(query: str) -> set[str]:
    return set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", query.lower()))


def validate_spl(query: str) -> dict[str, object]:
    tokens = _tokens(query)
    blocked = sorted(tokens.intersection(BLOCKED_COMMANDS))
    has_time_range = "earliest=" in query.lower() and "latest=" in query.lower()
    has_aggregation = bool(tokens.intersection(AGGREGATION_COMMANDS))
    errors: list[str] = []

    if blocked:
        errors.append(f"Blocked SPL command(s): {', '.join(blocked)}")
    if not has_time_range:
        errors.append("SPL query must include earliest= and latest= time bounds.")
    if not has_aggregation:
        errors.append("SPL query must include an aggregation command.")

    return {
        "valid": not errors,
        "errors": errors,
        "blocked_commands": blocked,
        "requires_human_approval": bool(blocked),
    }
