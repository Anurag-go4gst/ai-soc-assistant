"""SPL clause-spec validator and findings assertions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpecResult:
    passed: bool
    reasons: tuple[str, ...]


def validate_spl_spec(spl: str, spec: dict[str, Any]) -> SpecResult:
    """Check that an SPL string satisfies a clause spec.

    Spec keys: must_contain (list[str]), must_contain_any (list[str]),
    forbidden (list[str]). Match is case-insensitive substring.
    """
    lowered = spl.lower()
    reasons: list[str] = []

    for token in spec.get("must_contain") or []:
        if str(token).lower() not in lowered:
            reasons.append(f"missing required token: {token!r}")

    any_tokens = spec.get("must_contain_any")
    if any_tokens:
        if not any(str(t).lower() in lowered for t in any_tokens):
            reasons.append(f"none of must_contain_any present: {any_tokens!r}")

    for token in spec.get("forbidden") or []:
        if str(token).lower() in lowered:
            reasons.append(f"forbidden token present: {token!r}")

    return SpecResult(passed=not reasons, reasons=tuple(reasons))


def validate_findings(
    rows: list[dict[str, Any]], expected: dict[str, Any]
) -> SpecResult:
    """Compare actual result rows against an expected_findings spec.

    Supports four spec keys:
      total_count       — single scalar over a one-row aggregate result
      row_count_min     — minimum row count
      row_assertions    — each {match, expect}: find a row matching `match`
                          field/value pairs, assert all `expect` fields equal
      ordered_rows      — exact ordered prefix match on rows
    """
    reasons: list[str] = []

    if "total_count" in expected:
        expected_total = int(expected["total_count"])
        if not rows:
            reasons.append(f"no rows; expected total_count={expected_total}")
        else:
            first = rows[0]
            actual = _coerce_int(
                first.get("total_count")
                or first.get("count")
                or sum(_coerce_int(v) for v in first.values() if _coerce_int(v) is not None)
            )
            if actual != expected_total:
                reasons.append(
                    f"total_count: expected {expected_total}, got {actual}"
                )

    if "row_count_min" in expected:
        minimum = int(expected["row_count_min"])
        if len(rows) < minimum:
            reasons.append(f"row count {len(rows)} below minimum {minimum}")

    for assertion in expected.get("row_assertions") or []:
        match = assertion["match"]
        expect = assertion["expect"]
        candidates = [row for row in rows if _row_matches(row, match)]
        if not candidates:
            reasons.append(f"no row matched {match!r}")
            continue
        row = candidates[0]
        for field, want in expect.items():
            got = _coerce_int(row.get(field))
            if got != want:
                reasons.append(
                    f"row {match!r} field {field!r}: expected {want}, got {got}"
                )

    expected_rows = expected.get("ordered_rows")
    if expected_rows:
        if len(rows) < len(expected_rows):
            reasons.append(
                f"ordered_rows: only {len(rows)} rows, expected >= {len(expected_rows)}"
            )
        else:
            for index, want in enumerate(expected_rows):
                got = rows[index]
                for field, expected_value in want.items():
                    actual = got.get(field)
                    if isinstance(expected_value, int):
                        actual = _coerce_int(actual)
                    if actual != expected_value:
                        reasons.append(
                            f"ordered_rows[{index}] field {field!r}: "
                            f"expected {expected_value!r}, got {actual!r}"
                        )

    return SpecResult(passed=not reasons, reasons=tuple(reasons))


def _row_matches(row: dict[str, Any], match: dict[str, Any]) -> bool:
    return all(str(row.get(k)) == str(v) for k, v in match.items())


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["SpecResult", "validate_spl_spec", "validate_findings"]
