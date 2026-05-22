def record_decision(trace_id: str, decision: dict[str, object]) -> dict[str, object]:
    return {"trace_id": trace_id, "decision": decision}
