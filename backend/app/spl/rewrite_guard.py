"""OPTIONAL_PHASE_S S2 — compose existing fidelity + RQC guards into one rewrite gate.

Does not invent a second semantic checker. Callers that receive FAIL must retain v1
as the selected candidate (still subject to its own validator/risk chain).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from app.spl.rqc_constraint_preservation import evaluate_rqc_constraint_preservation
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity, validate_spl_structure

RewriteVerdict = Literal["PASS", "FAIL"]

_INDEX_RE = re.compile(r"\bindex\s*=\s*([^\s|]+)", re.IGNORECASE)
_SOURCETYPE_RE = re.compile(r"\bsourcetype\s*=\s*([^\s|]+)", re.IGNORECASE)
_EARLIEST_RE = re.compile(r"\bearliest\s*=\s*([^\s|]+)", re.IGNORECASE)
_LATEST_RE = re.compile(r"\blatest\s*=\s*([^\s|]+)", re.IGNORECASE)
_HEAD_RE = re.compile(r"\|\s*head\s+(\d+)", re.IGNORECASE)
_STATS_SHAPE_RE = re.compile(r"\b(stats|tstats|timechart|streamstats)\b", re.IGNORECASE)


def _tokens(pattern: re.Pattern[str], spl: str) -> set[str]:
    return {m.group(1).strip("\"'") for m in pattern.finditer(spl or "")}


def _structural_invariants(spl: str) -> dict[str, Any]:
    heads = [int(m.group(1)) for m in _HEAD_RE.finditer(spl or "")]
    return {
        "indexes": _tokens(_INDEX_RE, spl),
        "sourcetypes": _tokens(_SOURCETYPE_RE, spl),
        "earliest": _tokens(_EARLIEST_RE, spl),
        "latest": _tokens(_LATEST_RE, spl),
        "head_limits": set(heads),
        "has_aggregation": bool(_STATS_SHAPE_RE.search(spl or "")),
    }


def assert_rewrite_preserves(
    v1: str,
    v2: str,
    rqc: dict[str, Any] | None = None,
    *,
    intent_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """PASS/FAIL gate for candidate_spl_v1 → candidate_spl_v2.

    Composes:
      - structural invariant comparison (index, sourcetype, time scope, result limit,
        aggregation presence)
      - evaluate_rqc_constraint_preservation (governed RQC slots must not drop)
      - validate_semantic_fidelity when an intent_spec is supplied (v2 must not add losses)
    """
    violations: list[str] = []

    struct_errors = validate_spl_structure(v2 or "")
    if struct_errors:
        violations.extend(f"structure:{err}" for err in struct_errors)

    inv1 = _structural_invariants(v1 or "")
    inv2 = _structural_invariants(v2 or "")

    if inv1["indexes"] and not inv1["indexes"].issubset(inv2["indexes"]):
        violations.append("index")
    if inv1["sourcetypes"] and not inv1["sourcetypes"].issubset(inv2["sourcetypes"]):
        violations.append("sourcetype")
    if inv1["earliest"] and not inv1["earliest"].issubset(inv2["earliest"]):
        violations.append("time_scope_earliest")
    if inv1["latest"] and not inv1["latest"].issubset(inv2["latest"]):
        violations.append("time_scope_latest")
    if inv1["head_limits"] and not inv1["head_limits"].issubset(inv2["head_limits"]):
        # Allow a stricter (smaller) head only when v1 had a head — still a limit change
        # that needs explicit recording; treat non-superset as result_limit violation.
        if not inv2["head_limits"]:
            violations.append("result_limit")
        elif min(inv2["head_limits"]) > max(inv1["head_limits"]):
            violations.append("result_limit")
    if inv1["has_aggregation"] and not inv2["has_aggregation"]:
        violations.append("aggregation_meaning")

    rqc1 = evaluate_rqc_constraint_preservation(v1, resolved_query_contract=rqc)
    rqc2 = evaluate_rqc_constraint_preservation(v2, resolved_query_contract=rqc)
    dropped = sorted(set(rqc1.get("present") or []) - set(rqc2.get("present") or []))
    if dropped:
        violations.append(f"governed_filters:{','.join(dropped)}")
    # Newly missing vs v1 present also covered; additionally any missing that v1 had as present
    for key in rqc1.get("present") or []:
        if key in (rqc2.get("missing") or []):
            if f"governed_filters:{key}" not in violations and not any(
                v.startswith("governed_filters:") and key in v for v in violations
            ):
                violations.append(f"governed_filters:{key}")

    if intent_spec is not None:
        fid1 = validate_semantic_fidelity(intent_spec, v1 or "")
        fid2 = validate_semantic_fidelity(intent_spec, v2 or "")
        new_losses = sorted(set(fid2.get("losses") or []) - set(fid1.get("losses") or []))
        if new_losses:
            violations.append(f"semantic_fidelity:{','.join(new_losses)}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for item in violations:
        if item not in seen:
            seen.add(item)
            ordered.append(item)

    verdict: RewriteVerdict = "PASS" if not ordered else "FAIL"
    return {
        "verdict": verdict,
        "violations": ordered,
        "retain_v1": verdict == "FAIL",
        "rqc_v1": rqc1,
        "rqc_v2": rqc2,
        "invariants_v1": {k: sorted(v) if isinstance(v, set) else v for k, v in inv1.items()},
        "invariants_v2": {k: sorted(v) if isinstance(v, set) else v for k, v in inv2.items()},
    }
