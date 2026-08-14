"""Plan 6 env-capture schema: reject secret-shaped keys before any VPS log is written."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

FORBIDDEN_KEY_RE = re.compile(r"token|password|secret|api_key", re.IGNORECASE)

SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "evals"
    / "plan6"
    / "env_capture.schema.json"
)

REQUIRED_TOP_LEVEL = (
    "git_sha",
    "flags",
    "mcp_mode",
    "mcp_connectivity",
    "db_reachable",
    "environment_identity",
    "timestamp",
    "corpus_version",
)


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def iter_keys(payload: Any, *, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.append(path)
            keys.extend(iter_keys(value, prefix=path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            keys.extend(iter_keys(value, prefix=f"{prefix}[{index}]"))
    return keys


def forbidden_keys(payload: Mapping[str, Any]) -> list[str]:
    hits: list[str] = []
    for path in iter_keys(payload):
        leaf = path.rsplit(".", 1)[-1]
        leaf = leaf.split("[", 1)[0]
        if FORBIDDEN_KEY_RE.search(leaf):
            hits.append(path)
    return hits


def validate_env_capture(payload: Mapping[str, Any]) -> list[str]:
    """Return error strings. Empty list means the capture is acceptable."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ["env capture must be a mapping"]
    secret_hits = forbidden_keys(payload)
    if secret_hits:
        errors.append(
            "forbidden secret-shaped keys: " + ", ".join(secret_hits)
        )
    for required in REQUIRED_TOP_LEVEL:
        if required not in payload:
            errors.append(f"missing required key: {required}")
    return errors
