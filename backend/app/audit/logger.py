def audit_event(action: str, metadata: dict[str, object]) -> dict[str, object]:
    return {"action": action, "metadata": metadata}
