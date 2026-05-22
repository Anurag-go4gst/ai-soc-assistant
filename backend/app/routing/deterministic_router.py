def route_intent(intent: str) -> dict[str, object]:
    normalized = intent.lower()
    if "brute" in normalized or "login" in normalized:
        route = "investigate_authentication"
        confidence = 0.8
    elif "database" in normalized or "pool" in normalized:
        route = "investigate_database"
        confidence = 0.75
    else:
        route = "investigate_alert"
        confidence = 0.55

    return {
        "source": "deterministic_router",
        "route": route,
        "confidence": confidence,
        "intent": intent,
    }
