def filter_prompt_injection(text: str) -> dict[str, object]:
    suspicious = "ignore previous" in text.lower()
    return {"allowed": not suspicious, "suspicious": suspicious}
