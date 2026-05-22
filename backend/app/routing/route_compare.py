def compare_routes(planner: dict[str, object], deterministic: dict[str, object]) -> dict[str, object]:
    return {
        "match": planner.get("route") == deterministic.get("route"),
        "planner": planner,
        "deterministic": deterministic,
        "confidence_delta": float(planner.get("confidence", 0)) - float(deterministic.get("confidence", 0)),
    }
