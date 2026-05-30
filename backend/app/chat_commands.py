import re

_ZERO_WIDTH = re.compile(r"[\u200b-\u200d\ufeff]")


def is_clear_chat_command(message: str) -> bool:
    normalized = _ZERO_WIDTH.sub("", message.strip()).replace("\uff0f", "/").lower()
    normalized = re.sub(r"[.!?]+$", "", normalized)
    if normalized.startswith("/"):
        normalized = normalized[1:]
    return normalized == "clear"
