from app.config import settings
from app.connectors.llm.base import LlmConnector
from app.connectors.llm.dev_teacher import DevTeacherLlmConnector
from app.connectors.llm.local_runtime import LocalRuntimeLlmConnector
from app.connectors.llm.mock import MockLlmConnector


def get_llm_connector() -> LlmConnector:
    mode = settings.llm_mode.strip().lower()
    if mode == "local_runtime":
        return LocalRuntimeLlmConnector()
    if mode == "dev_teacher":
        return DevTeacherLlmConnector()
    return MockLlmConnector()


__all__ = ["LlmConnector", "get_llm_connector"]
