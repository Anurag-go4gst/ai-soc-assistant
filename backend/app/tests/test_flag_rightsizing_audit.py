"""Plan 0.4 — flag rightsizing audit doc integrity checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
AUDIT_MD = REPO / "docs" / "architecture" / "flag_rightsizing_audit.md"
AUDIT_JSON = REPO / "docs" / "architecture" / "flag_rightsizing_audit_data.json"
ENV_EXAMPLE = REPO / ".env.example"

DELETE_DISPOSITIONS = frozenset({"delete", "delete_alias", "fold_in", "hardcode_then_delete"})


def _env_example_keys() -> set[str]:
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            keys.add(stripped.split("=", 1)[0].strip())
    return keys


def _audit_rows() -> list[dict]:
    return json.loads(AUDIT_JSON.read_text(encoding="utf-8"))


def test_audit_doc_and_data_present() -> None:
    assert AUDIT_MD.is_file()
    assert AUDIT_JSON.is_file()
    assert len(AUDIT_MD.read_text(encoding="utf-8")) > 5000


def test_every_env_example_key_in_disposition_table() -> None:
    rows = _audit_rows()
    table_keys = {row["env_key"] for row in rows}
    env_keys = _env_example_keys()
    assert env_keys <= table_keys, f"missing: {sorted(env_keys - table_keys)[:10]}"


def test_disposition_table_has_unique_keys() -> None:
    rows = _audit_rows()
    keys = [row["env_key"] for row in rows]
    assert len(keys) == len(set(keys))


def test_delete_and_fold_rows_carry_grep_or_git_evidence() -> None:
    rows = _audit_rows()
    for row in rows:
        if row["disposition"] not in DELETE_DISPOSITIONS:
            continue
        evidence = str(row.get("evidence") or "")
        assert "rg:" in evidence or "git:" in evidence, row["env_key"]


def test_dg4_batch_table_lists_counts() -> None:
    text = AUDIT_MD.read_text(encoding="utf-8")
    assert "**A** | Lowest" in text
    assert "| **D** | Highest" in text
    assert "{batch_counts" not in text
