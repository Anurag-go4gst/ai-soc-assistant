"""Splunk REST search client.

Used by the generator for idempotent re-ingest (delete prior synthetic
events in the test window) and by the harness for execution-layer
assertions. Token-based auth via env vars; never logs credentials.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class SplunkApiConfig:
    base_url: str
    token: str
    verify_tls: bool = True

    @classmethod
    def from_env(cls) -> "SplunkApiConfig":
        base_url = os.environ.get("SPLUNK_API_URL", "").rstrip("/")
        token = os.environ.get("SPLUNK_API_TOKEN", "")
        if not base_url:
            raise RuntimeError(
                "SPLUNK_API_URL is not set. Example: https://splunk.example.com:8089"
            )
        if not token:
            raise RuntimeError("SPLUNK_API_TOKEN is not set (Splunk auth token).")
        verify_tls = os.environ.get("SPLUNK_API_VERIFY_TLS", "true").lower() != "false"
        return cls(base_url=base_url, token=token, verify_tls=verify_tls)


class SplunkSearchClient:
    def __init__(self, config: SplunkApiConfig | None = None) -> None:
        self.config = config or SplunkApiConfig.from_env()
        self._client = httpx.Client(
            timeout=120.0,
            verify=self.config.verify_tls,
            headers={"Authorization": f"Bearer {self.config.token}"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SplunkSearchClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def run(
        self,
        spl: str,
        earliest_time: str | None = None,
        latest_time: str | None = None,
    ) -> list[dict[str, Any]]:
        """Run a blocking search and return result rows as dicts."""
        # Splunk requires the leading `search` keyword; add it if missing.
        body = spl.strip()
        if not body.lower().startswith(("search ", "|")):
            body = f"search {body}"

        params: dict[str, str] = {
            "search": body,
            "output_mode": "json",
            "exec_mode": "blocking",
        }
        if earliest_time is not None:
            params["earliest_time"] = earliest_time
        if latest_time is not None:
            params["latest_time"] = latest_time

        response = self._client.post(
            f"{self.config.base_url}/services/search/jobs",
            data=params,
        )
        if response.status_code >= 400:
            raise SplunkSearchError(
                f"Search job create failed: {response.status_code} {response.reason_phrase}"
            )

        # `exec_mode=blocking` returns once the search is done. Now fetch results.
        sid = _extract_sid(response.text)
        return self._fetch_results(sid)

    def _fetch_results(self, sid: str) -> list[dict[str, Any]]:
        # Poll briefly in case results aren't yet materialized.
        for _ in range(30):
            response = self._client.get(
                f"{self.config.base_url}/services/search/jobs/{sid}/results",
                params={"output_mode": "json", "count": 0},
            )
            if response.status_code == 204:
                time.sleep(0.5)
                continue
            if response.status_code >= 400:
                raise SplunkSearchError(
                    f"Result fetch failed: {response.status_code} {response.reason_phrase}"
                )
            data = response.json()
            return list(data.get("results", []))
        raise SplunkSearchError("Timed out waiting for search results.")

    def delete_events(
        self,
        index: str,
        source: str,
        earliest_time: str,
        latest_time: str,
    ) -> None:
        """Delete events written by the generator inside the test window.

        Requires the authenticated user to have the ``can_delete`` role.
        Silently tolerates `delete`-not-allowed failures by surfacing them
        so the caller can decide; never retries blindly.
        """
        spl = (
            f"search index={index} source={source} "
            f"earliest={earliest_time} latest={latest_time} | delete"
        )
        self.run(spl, earliest_time=earliest_time, latest_time=latest_time)


class SplunkSearchError(RuntimeError):
    """Raised on non-2xx Splunk REST responses or timeouts."""


def _extract_sid(xml_or_text: str) -> str:
    # Splunk returns either XML or JSON depending on params. We don't ask for
    # JSON on the create call (Splunk doesn't honor it consistently), so parse
    # both: <sid>...</sid> in XML, or {"sid": "..."} in JSON.
    text = xml_or_text.strip()
    if text.startswith("{"):
        import json

        payload = json.loads(text)
        sid = payload.get("sid")
        if not sid:
            raise SplunkSearchError("Splunk create-job response missing sid.")
        return str(sid)
    start = text.find("<sid>")
    end = text.find("</sid>")
    if start == -1 or end == -1:
        raise SplunkSearchError("Could not locate sid in search job response.")
    return text[start + len("<sid>") : end]


__all__ = ["SplunkSearchClient", "SplunkApiConfig", "SplunkSearchError"]
