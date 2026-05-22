def validate_evidence(evidence: list[dict[str, object]]) -> dict[str, object]:
    return {"valid": isinstance(evidence, list), "count": len(evidence)}
