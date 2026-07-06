"""Curated ATLAS → ATT&CK → governed SPL template hints (plan 2026-07-06 items 13/16)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.threat.attack_data_resolver import technique_resolver_from_settings

_CROSSWALK_PATH = Path(__file__).resolve().with_name("atlas_attack_crosswalk.json")


def _load_crosswalk() -> dict[str, Any] | None:
    try:
        payload = json.loads(_CROSSWALK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    entries = payload.get("entries") if isinstance(payload, dict) else None
    return payload if isinstance(entries, list) else None


def _entry_for_attack_ref(attack_technique_ref: str) -> dict[str, Any] | None:
    ref = str(attack_technique_ref or "").strip()
    if not ref:
        return None
    payload = _load_crosswalk()
    if payload is None:
        return None
    for entry in payload.get("entries") or []:
        if isinstance(entry, dict) and str(entry.get("attack_technique_ref") or "") == ref:
            return entry
    return None


def atlas_technique_to_template_hints(technique_id: str) -> list[str]:
    detail = technique_resolver_from_settings().detail(technique_id)
    if not detail:
        return []
    attack_ref = str(detail.get("attack_technique_ref") or "")
    entry = _entry_for_attack_ref(attack_ref)
    if entry is None:
        return []
    template_ids = entry.get("template_ids") or []
    return [str(item) for item in template_ids if str(item).strip()]


def atlas_technique_suggested_remediation(technique_id: str) -> dict[str, Any] | None:
    detail = technique_resolver_from_settings().detail(technique_id)
    if not detail:
        return None
    attack_ref = str(detail.get("attack_technique_ref") or "")
    entry = _entry_for_attack_ref(attack_ref)
    if entry is None:
        return None
    remediation = entry.get("suggested_remediation")
    return dict(remediation) if isinstance(remediation, dict) else None
