def plan_route(intent: str) -> dict[str, object]:
    return {
        "source": "llm_planner",
        "route": "investigate_alert",
        "confidence": 0.62,
        "intent": intent,
        "note": "Mock planner decision. No LLM call is made.",
    }
