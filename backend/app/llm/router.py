def select_model(task_type: str) -> dict[str, str]:
    return {"task_type": task_type, "model": "disabled", "note": "LLM routing is disabled."}
