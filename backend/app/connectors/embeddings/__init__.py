from app.config import settings
from app.connectors.embeddings.base import EmbeddingsConnector
from app.connectors.embeddings.local_embeddings import LocalEmbeddingsConnector
from app.connectors.embeddings.mock import MockEmbeddingsConnector


def get_embeddings_connector() -> EmbeddingsConnector:
    mode = settings.embeddings_mode.strip().lower()
    if mode == "local":
        return LocalEmbeddingsConnector()
    return MockEmbeddingsConnector()


__all__ = ["EmbeddingsConnector", "get_embeddings_connector"]
