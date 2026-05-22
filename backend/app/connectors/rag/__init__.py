from app.config import settings
from app.connectors.rag.base import RagConnector
from app.connectors.rag.local_vector import LocalVectorRagConnector
from app.connectors.rag.mock import MockRagConnector


def get_rag_connector() -> RagConnector:
    mode = settings.rag_mode.strip().lower()
    if mode == "local_vector":
        return LocalVectorRagConnector()
    return MockRagConnector()


__all__ = ["RagConnector", "get_rag_connector"]
