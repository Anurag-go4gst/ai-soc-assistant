"""Minimal Splunk HEC client for the test harness.

Never log or print HEC tokens. Credentials are read exclusively from
environment variables and used only as HTTP Authorization headers.
"""

from __future__ import annotations

import json
import os
import ssl
from dataclasses import dataclass
from typing import Iterable, Sequence

import httpx


_BATCH_SIZE = 200


@dataclass(frozen=True)
class HecConfig:
    base_url: str
    token: str
    verify_tls: bool = True

    @classmethod
    def from_env(cls) -> "HecConfig":
        base_url = os.environ.get("SPLUNK_HEC_URL", "").rstrip("/")
        token = os.environ.get("SPLUNK_HEC_TOKEN", "")
        if not base_url:
            raise RuntimeError(
                "SPLUNK_HEC_URL is not set. Example: https://splunk.example.com:8088"
            )
        if not token:
            raise RuntimeError("SPLUNK_HEC_TOKEN is not set.")
        verify_tls = os.environ.get("SPLUNK_HEC_VERIFY_TLS", "true").lower() != "false"
        return cls(base_url=base_url, token=token, verify_tls=verify_tls)

    @property
    def collector_endpoint(self) -> str:
        return f"{self.base_url}/services/collector/event"


class HecClient:
    def __init__(self, config: HecConfig | None = None) -> None:
        self.config = config or HecConfig.from_env()
        self._client = httpx.Client(
            timeout=30.0,
            verify=self.config.verify_tls,
            headers={"Authorization": f"Splunk {self.config.token}"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HecClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def send_batch(self, events: Sequence[dict]) -> None:
        """Send a sequence of HEC payloads. Each item must already be a
        HEC envelope (with ``event`` plus optional ``time``, ``index``, etc).
        """
        if not events:
            return
        body = "\n".join(json.dumps(item, separators=(",", ":")) for item in events)
        response = self._client.post(self.config.collector_endpoint, content=body)
        if response.status_code >= 400:
            raise HecError(
                f"HEC ingest failed: {response.status_code} {response.reason_phrase}"
            )

    def send_all(self, events: Iterable[dict]) -> int:
        """Chunk and ingest. Returns total event count sent."""
        buf: list[dict] = []
        total = 0
        for item in events:
            buf.append(item)
            if len(buf) >= _BATCH_SIZE:
                self.send_batch(buf)
                total += len(buf)
                buf.clear()
        if buf:
            self.send_batch(buf)
            total += len(buf)
        return total


class HecError(RuntimeError):
    """Raised on non-2xx HEC responses."""


__all__ = ["HecClient", "HecConfig", "HecError"]
