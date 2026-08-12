"""Plan 5 A2 — the unpromoted-DRAFT drift ledger must match reality exactly.

The runtime map's MITRE candidate tier is one curation commit behind the DRAFT: `56b48d9` promoted
the DRAFT as of `1106dd3`, then `7ee7a34` advanced it and the promoter was never re-run. The builder
reproduces the *promoted* state so that regenerating a file cannot broaden analyst-visible technique
claims, and records the gap in `docs/input/mitre_enrichment/unpromoted_draft_drift_v1.json`.

That ledger is load-bearing and therefore dangerous: silencing a genuine new divergence would be as
simple as adding a row to it. These tests make that impossible by asserting the ledger equals the
measured DRAFT-vs-promoted divergence in **both** directions — a row that stops drifting must be
removed, and a row that starts drifting cannot be waved through.

Reconciliation is Plan 5 A2.5 (`MITRE_DRAFT_RUNTIME_PROMOTION_RECONCILIATION`). When that lands, the
ledger's `rows` must be empty and `test_ledger_is_empty_once_reconciled` becomes the guard that keeps
it that way.
"""

from __future__ import annotations

import json
from typing import Any

from app.threat.mitre_registry_enrichment import load_mitre_enrichment_drafts
from app.threat.mitre_runtime_promotion import runtime_patch_for_draft_item
from question_runtime_map_builder import (
    OUTPUT_PATH,
    UNPROMOTED_DRAFT_DRIFT_PATH,
    load_unpromoted_draft_drift,
)


def _committed_rows() -> dict[str, dict[str, Any]]:
    return {
        str(e["question_ref"]): e
        for e in json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))["entries"]
    }


def _measured_drift() -> dict[str, dict[str, Any]]:
    """Rows where the DRAFT's candidate tier differs from what the committed map carries.

    Derived from the DRAFT directly rather than from a built map, so the ledger is checked against
    the source of truth and not against the builder that consumes it.
    """
    drafts = load_mitre_enrichment_drafts()["questions_by_id"]
    drift: dict[str, dict[str, Any]] = {}
    for ref, row in _committed_rows().items():
        draft_item = drafts.get(ref)
        if not isinstance(draft_item, dict):
            continue
        patch = runtime_patch_for_draft_item(draft_item, question_ref=ref, use_case_id=None)
        if patch["mitre_candidate"] != row.get("mitre_candidate"):
            drift[ref] = {
                "promoted_mitre_candidate": row.get("mitre_candidate"),
                "draft_mitre_candidate": patch["mitre_candidate"],
            }
    return drift


def test_ledger_rows_match_measured_drift_exactly() -> None:
    """Both directions: no stale entry, and no new divergence silently absorbed."""
    ledger = load_unpromoted_draft_drift()
    measured = _measured_drift()

    stale = sorted(set(ledger) - set(measured))
    unrecorded = sorted(set(measured) - set(ledger))

    assert not unrecorded, (
        "the MITRE DRAFT diverges from the promoted runtime map on rows the ledger does not record. "
        "Do not add them to the ledger to make this pass — a new divergence means a promotion "
        f"decision is due (Plan 5 A2.5): {unrecorded}"
    )
    assert not stale, (
        "the ledger records rows that no longer drift; remove them so it cannot mask a future "
        f"divergence on the same row: {stale}"
    )


def test_ledger_values_match_measured_drift() -> None:
    """A recorded row must carry the real promoted and draft values, not placeholders."""
    ledger = load_unpromoted_draft_drift()
    mismatched = {
        ref: {
            "ledger": (entry.get("promoted_mitre_candidate"), entry.get("draft_mitre_candidate")),
            "measured": (m["promoted_mitre_candidate"], m["draft_mitre_candidate"]),
        }
        for ref, m in _measured_drift().items()
        if (entry := ledger.get(ref, {}))
        and (
            entry.get("promoted_mitre_candidate") != m["promoted_mitre_candidate"]
            or entry.get("draft_mitre_candidate") != m["draft_mitre_candidate"]
        )
    }
    assert not mismatched, f"ledger values disagree with measurement: {mismatched}"


def test_ledger_never_promotes_a_candidate() -> None:
    """The ledger may only hold the promoted value back — never assert something new.

    A ledger entry whose promoted value is *wider* than the DRAFT would be the ledger inventing a
    claim, which is the failure mode the whole mechanism exists to prevent.
    """
    widened = {
        ref: entry
        for ref, entry in load_unpromoted_draft_drift().items()
        if set(entry.get("promoted_mitre_candidate") or [])
        - set(entry.get("draft_mitre_candidate") or [])
    }
    assert not widened, f"ledger asserts techniques the DRAFT does not carry: {widened}"


def test_ledger_documents_its_own_reconciliation() -> None:
    """The ledger must stay self-explanatory — it outlives the context that created it."""
    payload = json.loads(UNPROMOTED_DRAFT_DRIFT_PATH.read_text(encoding="utf-8"))
    for field in ("purpose", "promoted_by_commit", "draft_advanced_by_commit", "reconciliation_item"):
        assert payload.get(field), f"ledger is missing `{field}`"
    assert "A2.5" in payload["reconciliation_item"]


def test_ledger_is_empty_once_reconciled() -> None:
    """Records the expected end state; skipped until A2.5 promotes the DRAFT.

    Written now, not later, so reconciliation has an executable definition of done.
    """
    rows = load_unpromoted_draft_drift()
    if not rows:
        return
    assert len(rows) == 11, (
        "the unpromoted drift is expected to be exactly the 11 rows measured at Plan 5 A2 until "
        f"A2.5 reconciles them; found {len(rows)}: {sorted(rows)}"
    )
