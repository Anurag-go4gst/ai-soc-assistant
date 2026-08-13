"""Plan 5 A0 — regenerating the runtime map must reproduce the committed artifact byte for byte.

`question_runtime_map_v1.json` is consumed by the live `/chat` MITRE policy path
(`backend/app/threat/mitre_registry_enrichment.py`) and by several report builders, but the
builder that authors it never reads the committed file. A later commit (`56b48d9`) promoted
MITRE registry metadata into the artifact without teaching the builder to reproduce it, so a
regeneration silently destroys that metadata.

These tests fail on purpose until the builder is corrected (item A2). They assert the property
that matters — regeneration is a no-op — and, when it does not hold, they name exactly which
fields were lost and which rows changed value, so the failure output is the A0 evidence.

No test here writes anything: the map is built in memory and compared against the committed
bytes. Regenerating in place is what the defect makes dangerous, so the regression guard must
not do it.
"""

from __future__ import annotations

import json
from typing import Any

from question_runtime_map_builder import OUTPUT_PATH, build_question_runtime_map

#: Serialization used by every writer of this artifact — `write_question_runtime_map`,
#: `write_all_question_maps`, and `scripts/promote_mitre_registry_to_runtime.py`. Byte
#: comparison is only meaningful if the test serializes identically.
def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def _committed() -> dict[str, Any]:
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def _entries_by_ref(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(entry["question_ref"]): entry for entry in payload["entries"]}


def _field_drift(
    committed: dict[str, Any], rebuilt: dict[str, Any]
) -> tuple[set[str], set[str], dict[str, list[str]]]:
    """Return (fields lost, fields added, {field: refs whose value changed})."""
    committed_rows = _entries_by_ref(committed)
    rebuilt_rows = _entries_by_ref(rebuilt)

    lost: set[str] = set()
    added: set[str] = set()
    changed: dict[str, list[str]] = {}

    for ref, committed_row in committed_rows.items():
        rebuilt_row = rebuilt_rows.get(ref, {})
        lost |= set(committed_row) - set(rebuilt_row)
        added |= set(rebuilt_row) - set(committed_row)
        for field in set(committed_row) & set(rebuilt_row):
            if committed_row[field] != rebuilt_row[field]:
                changed.setdefault(field, []).append(ref)

    return lost, added, changed


def test_rebuild_is_byte_identical_to_committed_artifact() -> None:
    """The property under repair: regeneration must be a no-op."""
    rebuilt = _serialize(build_question_runtime_map())
    committed = OUTPUT_PATH.read_text(encoding="utf-8")

    if rebuilt == committed:
        return

    lost, added, changed = _field_drift(_committed(), json.loads(rebuilt))
    detail = [
        f"regenerating {OUTPUT_PATH.relative_to(OUTPUT_PATH.parents[3])} is not idempotent:",
        f"  fields dropped ({len(lost)}): {sorted(lost) or 'none'}",
        f"  fields added ({len(added)}): {sorted(added) or 'none'}",
    ]
    for field, refs in sorted(changed.items()):
        detail.append(f"  field changed value on {len(refs)} row(s): {field}")
    raise AssertionError("\n".join(detail))


def test_rebuild_preserves_every_committed_field() -> None:
    """A dropped field is the destructive half of the defect — name each one."""
    lost, _added, _changed = _field_drift(_committed(), build_question_runtime_map())
    assert not lost, (
        "the builder drops fields the committed artifact carries; live consumers read these "
        f"(mitre_registry_enrichment.py, mapping_exports.py): {sorted(lost)}"
    )


def test_rebuild_preserves_every_committed_field_value() -> None:
    """A changed value is the second, separate defect — a real semantic conflict, not a loss."""
    _lost, _added, changed = _field_drift(_committed(), build_question_runtime_map())
    summary = {field: len(refs) for field, refs in sorted(changed.items())}
    assert not changed, (
        "the builder recomputes values that disagree with the committed artifact "
        f"(field -> rows affected): {summary}"
    )


def test_row_count_and_top_level_keys_are_stable() -> None:
    """Guards the fields the defect does not touch, so a future fix cannot regress them silently."""
    committed = _committed()
    rebuilt = build_question_runtime_map()

    assert set(rebuilt) == set(committed)
    assert rebuilt["question_count"] == committed["question_count"] == 105
    assert rebuilt["manifest_row_count"] == committed["manifest_row_count"]
    assert rebuilt["map_version"] == committed["map_version"]
    assert [e["question_ref"] for e in rebuilt["entries"]] == [
        e["question_ref"] for e in committed["entries"]
    ]
