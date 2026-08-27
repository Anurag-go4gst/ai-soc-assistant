"""OPTIONAL_PHASE_S S2 — compose existing fidelity + RQC guards into one rewrite gate.

Does not invent a second semantic checker. Callers that receive FAIL must retain v1
as the selected candidate (still subject to its own validator/risk chain).

H2 extends the same gate with **match-semantics preservation**. The S2 invariants only
compared index, sourcetype, governed time, result limit and aggregation presence, so a
rewrite of the *search terms themselves* was invisible: the live evaluation accepted
`(*it* OR *ot*)` -> `(it OR ot)` and `NOT status=success` -> `status!="success"`. Both
change which events match.

This is the authority half of Layer 3 hardening. The optimization model is prompted to
abstain (H1), but prompting is prevention -- the model never decides whether its own
rewrite is safe.
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
_TABLE_RE = re.compile(r"\|\s*table\s+([^|]+)", re.IGNORECASE)
_FIELDS_KEEP_RE = re.compile(r"\|\s*fields\s+(?!-)([^|]+)", re.IGNORECASE)
_STATS_BY_RE = re.compile(r"\b(?:stats|tstats|timechart|streamstats)\b[^|]*?\bby\s+([^|]+)", re.IGNORECASE)


def _tokens(pattern: re.Pattern[str], spl: str) -> set[str]:
    return {m.group(1).strip("\"'") for m in pattern.finditer(spl or "")}


def _output_fields(spl: str) -> set[str]:
    """Analyst-visible output columns: `table` / `fields` projections and stats groupings.

    Presence of an aggregation is not enough — dropping a column from the final table
    silently changes what the analyst sees, so H2 compares the columns themselves.
    """
    columns: set[str] = set()
    for pattern in (_TABLE_RE, _FIELDS_KEEP_RE, _STATS_BY_RE):
        for match in pattern.finditer(spl or ""):
            for raw in match.group(1).replace(",", " ").split():
                token = raw.strip().strip("\"'")
                if token and token.lower() not in {"as", "by"}:
                    columns.add(token.lower())
    return columns


def _structural_invariants(spl: str) -> dict[str, Any]:
    heads = [int(m.group(1)) for m in _HEAD_RE.finditer(spl or "")]
    return {
        "indexes": _tokens(_INDEX_RE, spl),
        "sourcetypes": _tokens(_SOURCETYPE_RE, spl),
        "earliest": _tokens(_EARLIEST_RE, spl),
        "latest": _tokens(_LATEST_RE, spl),
        "head_limits": set(heads),
        "has_aggregation": bool(_STATS_SHAPE_RE.search(spl or "")),
        "output_fields": _output_fields(spl),
    }


# --- H2: base-search match semantics -------------------------------------------------
#
# Design constraint that drives every choice below: this gate is SHARED with the
# accepted S4 AUTO_FIX_SAFE rewrite (`field=A OR field=B` -> `field IN (A,B)`) and runs
# on the live path via pipeline.py regardless of the Layer 3 flag. So `IN` lists are
# canonicalised to their equivalent same-field OR set *before* anything is compared --
# otherwise hardening the guard would regress an already-accepted rewrite.
#
# Comparison is over the whole query, not just the base search, so shifting a filter
# left out of `| where` into the base search preserves the signature (a real, safe
# optimization) while adding or dropping a predicate does not.

_IN_CLAUSE_RE = re.compile(
    r"\b([A-Za-z_][\w.]*)\s+IN\s*\(([^()]*)\)",
    re.IGNORECASE,
)
_FUNC_CALL_RE = re.compile(
    r"\b(TERM|cidrmatch|like|match|searchmatch)\s*\(([^()]*)\)",
    re.IGNORECASE,
)
_PREDICATE_RE = re.compile(
    r"(?P<field>[A-Za-z_][\w.]*)\s*(?P<op>!=|>=|<=|=|>|<)\s*"
    r"(?P<value>\"[^\"]*\"|\'[^\']*\'|[^\s|()]+)"
)
_BOOL_TOKENS = {"AND", "OR", "NOT", "XOR"}
# Only filtering stages carry match semantics. Restricting to them is what lets a real
# optimization edit the pipeline -- dropping an unused `| eval`, adding an early
# `| fields` projection -- without tripping the guard, while a change to `| where` or to
# the base search is still compared predicate by predicate.
_FILTER_STAGE_HEADS = ("search", "where")
# Structural / policy fields already covered by _structural_invariants; excluding them
# here keeps one violation per real problem instead of duplicate noise.
_STRUCTURAL_FIELDS = {"index", "sourcetype", "earliest", "latest", "source"}
_SPL_NOISE_TOKENS = {"search", "where", "|"}


def _split_stages(spl: str) -> list[str]:
    """Split on `|` without cutting inside a quoted string."""
    stages: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    for char in spl or "":
        if quote:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            buffer.append(char)
            continue
        if char == "|":
            stages.append("".join(buffer))
            buffer = []
            continue
        buffer.append(char)
    stages.append("".join(buffer))
    return [stage.strip() for stage in stages if stage.strip()]


def _filter_stages(spl: str) -> list[str]:
    """Base search plus every `search` / `where` stage — the stages that select events."""
    stages = _split_stages(spl)
    if not stages:
        return []
    selected = [stages[0]]
    for stage in stages[1:]:
        head = stage.split(None, 1)[0].lower() if stage.split() else ""
        if head in _FILTER_STAGE_HEADS:
            selected.append(stage)
    return selected


def _expand_in_clauses(text: str) -> str:
    """`field IN (a,b,c)` -> `(field=a OR field=b OR field=c)` — the S4 canonical form."""

    def _expand(match: re.Match[str]) -> str:
        field_name = match.group(1)
        raw_values = [v.strip() for v in match.group(2).split(",")]
        values = [v for v in raw_values if v]
        if not values:
            return match.group(0)
        return "(" + " OR ".join(f"{field_name}={value}" for value in values) + ")"

    return _IN_CLAUSE_RE.sub(_expand, text or "")


def _unquote(value: str) -> str:
    text = (value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _leaf_signature(raw: str) -> str | None:
    """Canonical signature for one search leaf, or None when it carries no meaning.

    `NOT field=v` and `field!=v` deliberately produce DIFFERENT signatures. They are not
    interchangeable in Splunk when the field is missing or null, so swapping one for the
    other must not pass a generic preservation guard.
    """
    text = (raw or "").strip()
    if not text or text.upper() in _BOOL_TOKENS or text.lower() in _SPL_NOISE_TOKENS:
        return None

    func = _FUNC_CALL_RE.fullmatch(text)
    if func:
        # TERM()/cidrmatch() tokenization intent is part of match semantics: TERM(a.b)
        # is not the bare token a.b and is not "*a.b*".
        args = ",".join(_unquote(a) for a in func.group(2).split(","))
        return f"{func.group(1).lower()}({args})"

    predicate = _PREDICATE_RE.fullmatch(text)
    if predicate:
        field_name = predicate.group("field").lower()
        if field_name in _STRUCTURAL_FIELDS:
            return None
        # Value is compared verbatim after quote stripping, so wildcard presence,
        # placement and the field that owns it are all preserved implicitly:
        # host="*it*" and host="it" simply are not the same signature.
        return f"{field_name}{predicate.group('op')}{_unquote(predicate.group('value'))}"

    # Bare search term. Wildcards are preserved verbatim for the same reason.
    return f"term:{_unquote(text)}"


def _tokenize_search(text: str) -> list[str]:
    """Split into parens, boolean operators and leaves, keeping function calls whole."""
    tokens: list[str] = []
    buffer: list[str] = []
    index = 0
    length = len(text)

    def _flush() -> None:
        if buffer:
            tokens.append("".join(buffer).strip())
            buffer.clear()

    while index < length:
        func = _FUNC_CALL_RE.match(text, index)
        if func:
            _flush()
            tokens.append(func.group(0))
            index = func.end()
            continue
        char = text[index]
        if char in "\"'":
            close = text.find(char, index + 1)
            if close == -1:
                buffer.append(text[index:])
                break
            buffer.append(text[index : close + 1])
            index = close + 1
            continue
        if char in "()":
            _flush()
            tokens.append(char)
            index += 1
            continue
        if char.isspace():
            _flush()
            index += 1
            continue
        buffer.append(char)
        index += 1
    _flush()
    return [tok for tok in tokens if tok]


def _match_semantics(spl: str) -> dict[str, Any]:
    """Canonical match-semantics signature: leaves, negation and OR-group membership."""
    leaves: list[str] = []
    groups: list[frozenset[str]] = []

    for stage in _filter_stages(spl or ""):
        _accumulate_stage_semantics(_expand_in_clauses(stage), leaves, groups)

    return {
        "leaves": frozenset(leaves),
        "or_groups": frozenset(groups),
    }


def _accumulate_stage_semantics(
    normalized: str,
    leaves: list[str],
    groups: list[frozenset[str]],
) -> None:
    tokens = _tokenize_search(normalized)
    # Stack of per-depth state: alternatives seen at this paren depth, and whether the
    # depth contains a top-level OR (i.e. it really is an OR group).
    stack: list[dict[str, Any]] = [{"alts": [], "has_or": False}]
    negate_next = False

    for token in tokens:
        upper = token.upper()
        if upper == "NOT":
            negate_next = True
            continue
        if upper in {"AND", "XOR"}:
            continue
        if upper == "OR":
            stack[-1]["has_or"] = True
            continue
        if token == "(":
            stack.append({"alts": [], "has_or": False, "negated": negate_next})
            negate_next = False
            continue
        if token == ")":
            if len(stack) == 1:
                # Unbalanced input; validate_spl_structure reports it separately.
                continue
            frame = stack.pop()
            if frame["has_or"] and frame["alts"]:
                prefix = "neg:" if frame.get("negated") else ""
                groups.append(frozenset(f"{prefix}{alt}" for alt in frame["alts"]))
            # A nested group contributes its members upward so that redundant parens
            # -- ((a OR b)) vs (a OR b) -- collapse instead of looking like a change.
            stack[-1]["alts"].extend(frame["alts"])
            continue

        signature = _leaf_signature(token)
        if signature is None:
            negate_next = False
            continue
        if negate_next:
            signature = f"neg:{signature}"
            negate_next = False
        leaves.append(signature)
        stack[-1]["alts"].append(signature)

    # The outermost frame is an OR group too when the chain was never parenthesised.
    # S4 rewrites `a=1 OR a=2` (no parens) into `a IN (1,2)`, which expands WITH parens;
    # without this the accepted rewrite would look like a grouping change.
    root = stack[0]
    if root["has_or"] and root["alts"]:
        groups.append(frozenset(root["alts"]))


def _match_semantics_violations(v1: str, v2: str) -> list[str]:
    """Report predicate/term and grouping changes between two candidates."""
    sig1 = _match_semantics(v1)
    sig2 = _match_semantics(v2)
    violations: list[str] = []

    dropped = sorted(sig1["leaves"] - sig2["leaves"])
    added = sorted(sig2["leaves"] - sig1["leaves"])
    if dropped:
        violations.append("match_semantics_dropped:" + ",".join(dropped))
    if added:
        violations.append("match_semantics_added:" + ",".join(added))
    if sig1["or_groups"] != sig2["or_groups"]:
        violations.append("boolean_grouping")
    return violations


def _serialize_match_semantics(spl: str) -> dict[str, Any]:
    """JSON-safe view of the signature for traces (frozensets are not serializable)."""
    signature = _match_semantics(spl)
    return {
        "leaves": sorted(signature["leaves"]),
        "or_groups": sorted(sorted(group) for group in signature["or_groups"]),
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
        aggregation presence, required output columns)
      - H2 match-semantics comparison (wildcard presence/placement, comparison operators,
        NOT vs != as distinct forms, quoting, TERM()/cidrmatch tokenization, field-value
        pairs, boolean grouping and AND/OR membership) with `field IN (a,b,c)`
        canonicalised to its equivalent same-field OR set
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
    if inv1["output_fields"] and not inv1["output_fields"].issubset(inv2["output_fields"]):
        missing = sorted(inv1["output_fields"] - inv2["output_fields"])
        violations.append("required_output_fields:" + ",".join(missing))

    # H2 — base-search match semantics. Wildcards, NOT vs !=, comparison operators,
    # quoting, TERM()/cidrmatch tokenization, field-value pairs and boolean grouping.
    violations.extend(_match_semantics_violations(v1 or "", v2 or ""))

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
        "match_semantics_v1": _serialize_match_semantics(v1 or ""),
        "match_semantics_v2": _serialize_match_semantics(v2 or ""),
    }
