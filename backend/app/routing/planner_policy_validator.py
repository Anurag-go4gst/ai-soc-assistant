def validate_planner_policy(decision: dict[str, object]) -> dict[str, object]:
    return {
        "valid": bool(decision.get("route")),
        "decision": decision,
        "note": "Placeholder policy validator. No production policy checks yet.",
    }
