def adjudicate_route(comparison: dict[str, object]) -> dict[str, object]:
    planner = comparison["planner"]
    deterministic = comparison["deterministic"]

    if comparison["match"]:
        selected = planner
        reason = "planner and deterministic router agree"
    elif float(deterministic.get("confidence", 0)) >= 0.75:
        selected = deterministic
        reason = "deterministic router confidence reached safeguard threshold"
    else:
        selected = planner
        reason = "planner selected pending future policy validation"

    return {"selected": selected, "reason": reason}
