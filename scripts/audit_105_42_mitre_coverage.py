#!/usr/bin/env python3
"""Audit MITRE registry enrichment coverage for 105 questions and 42 use cases."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.threat.mitre_registry_enrichment import (  # noqa: E402
    allows_success_identity_evidence_context,
    is_failed_login_only_row,
    is_policy_or_sop_row,
    iter_all_question_mitre_metadata,
    iter_all_use_case_mitre_metadata,
    load_mitre_attack_subset_technique_ids,
    load_mitre_enrichment_drafts,
    normalize_legacy_mitre_fields,
)
from app.threat.mitre_registry_schema import MitreVisibilityPolicy  # noqa: E402

_HARD_ERRORS: list[str] = []
_WARNINGS: list[str] = []


def _error(message: str) -> None:
    _HARD_ERRORS.append(message)


def _warn(message: str) -> None:
    _WARNINGS.append(message)


def _audit_row(
    *,
    item: dict,
    meta,
    attack_ids: set[str],
    label: str,
) -> None:
    registry_block = item.get("mitre_registry")
    if not isinstance(registry_block, dict):
        _error(f"{label}: missing mitre_registry block on draft item")

    permitted = set(meta.mitre_permitted)
    candidate = set(meta.mitre_candidate)
    blocked = set(meta.mitre_blocked)

    if permitted & blocked:
        _error(f"{label}: mitre_permitted ∩ mitre_blocked = {sorted(permitted & blocked)}")
    if candidate & blocked:
        _error(f"{label}: mitre_candidate ∩ mitre_blocked = {sorted(candidate & blocked)}")

    for tid in meta.techniques_missing_from_attack_subset(attack_ids):
        _warn(f"{label}: permitted/candidate {tid} not in mitre_attack_subset.json (review)")

    for tid in meta.blocked_missing_from_attack_subset(attack_ids):
        pass  # defensive blocks OK

    if is_policy_or_sop_row(item):
        if meta.mitre_visibility_policy not in (
            MitreVisibilityPolicy.trace_only,
            MitreVisibilityPolicy.answer_if_requested,
        ):
            _error(
                f"{label}: policy/SOP row visibility={meta.mitre_visibility_policy.value} "
                "(expected trace_only or answer_if_requested)"
            )

    if is_failed_login_only_row(item) and not allows_success_identity_evidence_context(item):
        bad_permitted = permitted & {"T1003", "T1562.001"}
        if bad_permitted:
            _error(f"{label}: failed-login-only row permits {sorted(bad_permitted)} in mitre_permitted")
        if "T1078" in permitted:
            _error(f"{label}: failed-login-only row permits T1078 in mitre_permitted without success/identity context")
        if "T1003" in candidate:
            _error(f"{label}: failed-login-only row has T1003 in mitre_candidate")
        if "T1562.001" in candidate:
            _error(f"{label}: failed-login-only row has T1562.001 in mitre_candidate")
        if "T1078" in candidate and not allows_success_identity_evidence_context(item):
            _error(f"{label}: failed-login-only row has T1078 in mitre_candidate without success/identity context")


def main() -> int:
    try:
        drafts = load_mitre_enrichment_drafts()
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"HARD ERROR: invalid enrichment drafts: {exc}", file=sys.stderr)
        return 1

    attack_ids = set(load_mitre_attack_subset_technique_ids())
    q_metas = iter_all_question_mitre_metadata()
    u_metas = iter_all_use_case_mitre_metadata()

    count_with_registry = 0
    count_permitted = 0
    count_candidate = 0
    count_blocked = 0

    for question_ref, item in sorted(drafts["questions_by_id"].items()):
        if not isinstance(item, dict):
            continue
        meta = normalize_legacy_mitre_fields(item, question_ref=question_ref)
        if isinstance(item.get("mitre_registry"), dict):
            count_with_registry += 1
        if meta.mitre_permitted:
            count_permitted += 1
        if meta.mitre_candidate:
            count_candidate += 1
        if meta.mitre_blocked:
            count_blocked += 1
        _audit_row(item=item, meta=meta, attack_ids=attack_ids, label=f"105:{question_ref}")

    for use_case_id, item in sorted(drafts["use_cases_by_id"].items()):
        if not isinstance(item, dict):
            continue
        meta = normalize_legacy_mitre_fields(item, use_case_id=use_case_id)
        if isinstance(item.get("mitre_registry"), dict):
            count_with_registry += 1
        if meta.mitre_permitted:
            count_permitted += 1
        if meta.mitre_candidate:
            count_candidate += 1
        if meta.mitre_blocked:
            count_blocked += 1
        _audit_row(item=item, meta=meta, attack_ids=attack_ids, label=f"42:{use_case_id}")

    print("MITRE registry enrichment audit")
    print(f"  105 questions: {drafts['question_count']}")
    print(f"  42 use cases:  {drafts['use_case_count']}")
    print(f"  items with mitre_registry block: {count_with_registry}")
    print(f"  rows with non-empty mitre_permitted: {count_permitted}")
    print(f"  rows with non-empty mitre_candidate: {count_candidate}")
    print(f"  rows with non-empty mitre_blocked: {count_blocked}")
    print(f"  attack_subset technique count: {len(attack_ids)}")

    if _WARNINGS:
        print(f"\nWarnings ({len(_WARNINGS)}):")
        for line in _WARNINGS[:50]:
            print(f"  WARN: {line}")
        if len(_WARNINGS) > 50:
            print(f"  ... and {len(_WARNINGS) - 50} more warnings")

    if _HARD_ERRORS:
        print(f"\nHard errors ({len(_HARD_ERRORS)}):", file=sys.stderr)
        for line in _HARD_ERRORS:
            print(f"  ERROR: {line}", file=sys.stderr)
        return 1

    print("\nAudit passed (warnings only if any).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
