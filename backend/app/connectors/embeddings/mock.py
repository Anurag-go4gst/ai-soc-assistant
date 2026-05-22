from __future__ import annotations

import hashlib
import random

from app.connectors.mcp.base import ConnectorStatus


class MockEmbeddingsConnector:
    mode = "mock"

    def health(self) -> ConnectorStatus:
        return ConnectorStatus(mode=self.mode, configured=True, available=True, detail="mock")

    def embed_text(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
        rng = random.Random(seed)
        return [round(rng.uniform(-1.0, 1.0), 6) for _ in range(8)]
