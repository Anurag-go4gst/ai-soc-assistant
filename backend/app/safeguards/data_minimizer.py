def minimize_context(context: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in context.items() if "token" not in key.lower() and "password" not in key.lower()}
