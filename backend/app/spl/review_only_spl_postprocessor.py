"""Context-aware postprocessor for review-only SPL utility / lab drafts.

Scoped strictly to explicit SPL-authoring review-only drafts (universal /
template-free utility SPL and lab drafts). It NEVER runs on governed templates,
never authorizes execution, never invents an approved index, and never claims
findings. Safety/authority stay with RunContract / FinalEvidenceGate / the
deterministic validator; this module only normalizes draft hygiene:

* index resolution (user > COE family > source-profile > COE utility default >
  ``<your_index>`` placeholder)
* lookback hardening for placeholder/wildcard index drafts
* removal of an unnecessary pre-filter ``sort 0`` (dependency-aware)
* locale-safe weekend filtering (``%w`` logic, ``%A`` display preserved)

It is a pure function: same input + context yields same output. Wired at the
universal-skeleton emission point so it is exercised on the live deterministic
path (idempotent on an already-clean skeleton) and on mocked-LLM draft paths.
"""

from __future__ import annotations

from hashlib import sha256
import re
from dataclasses import dataclass, field
from typing import Any

# Default hardened lookback for placeholder/wildcard utility drafts.
_DEFAULT_EARLIEST = "-24h"
_DEFAULT_LATEST = "now"
_PLACEHOLDER_INDEX = "<your_index>"

# Earliest windows wider than 24h that we shrink for placeholder/wildcard drafts
# unless the user explicitly asked for the window.
_WIDE_EARLIEST_RE = re.compile(
    r"earliest\s*=\s*-?(\d+)\s*(d|w|mon|y)\b", re.IGNORECASE
)
_LOOKBACK_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def _lookback_seconds(text: str | None) -> int | None:
    match = re.search(r"earliest\s*=\s*-?(\d+)([smhdw])", str(text or ""), re.I)
    if not match:
        return None
    return int(match.group(1)) * _LOOKBACK_SECONDS[match.group(2).lower()]


def _baseline_period_present(spl: str) -> bool:
    lowered = spl.lower()
    return "period=" in lowered and "baseline" in lowered
_INDEX_TOKEN_RE = re.compile(r"index\s*=\s*([^\s|]+)", re.IGNORECASE)
_EARLIEST_TOKEN_RE = re.compile(r"earliest\s*=\s*[^\s|]+", re.IGNORECASE)
_LATEST_TOKEN_RE = re.compile(r"latest\s*=\s*[^\s|]+", re.IGNORECASE)

_SOURCETYPE_TOKEN_RE = re.compile(r"sourcetype\s*=\s*([^\s|]+)", re.IGNORECASE)
_COMMENT_LINE_RE = re.compile(r"^\s*(?:#|//|/\*)")


def _resolve_universal_sourcetype(context: dict[str, Any]) -> str | None:
    """Return a sourcetype only when explicitly configured — never invent one."""
    for key in (
        "user_explicit_sourcetype",
        "source_profile_sourcetype",
        "coe_generic_utility_default_sourcetype",
    ):
        value = str(context.get(key) or "").strip()
        if value:
            return value
    return None


def _is_universal_weekend_timestamp_spl(spl: str) -> bool:
    lowered = spl.lower()
    has_hour = "hour_of_day" in lowered or "%h" in lowered
    has_dow = "day_of_week_num" in lowered or "%w" in lowered
    has_weekend = (
        '("0","6")' in lowered
        or "weekend" in lowered
        or "saturday" in lowered
        or "sunday" in lowered
    )
    return has_hour and has_dow and has_weekend


def _build_canonical_universal_weekend_spl(
    resolved_index: str,
    *,
    sourcetype: str | None,
    earliest: str,
    latest: str,
) -> str:
    prefix = f"index={resolved_index} {earliest} {latest}"
    if sourcetype:
        prefix += f" sourcetype={sourcetype}"
    return "\n".join(
        [
            prefix,
            '| eval hour_of_day=strftime(_time,"%H")',
            '| eval day_of_week_num=strftime(_time,"%w")',
            '| eval day_of_week=strftime(_time,"%A")',
            '| where day_of_week_num IN ("0","6")',
            "| head 100",
            "| table _time hour_of_day day_of_week sourcetype host",
        ]
    )


def _polish_universal_utility_spl_shape(
    spl: str,
    *,
    resolved_index: str,
    context: dict[str, Any],
    trace: dict[str, Any],
) -> str:
    if not context.get("is_universal_spl") or not _is_universal_weekend_timestamp_spl(spl):
        return spl

    # Strip inline comments and a leading `search` keyword for clean utility output.
    cleaned_lines: list[str] = []
    for line in spl.splitlines():
        if _COMMENT_LINE_RE.match(line):
            continue
        cleaned_lines.append(line)
    spl = "\n".join(cleaned_lines).strip()
    spl = re.sub(r"^search\s+", "", spl, count=1, flags=re.IGNORECASE)

    user_time = bool(context.get("user_explicit_time_window"))
    earliest_match = _EARLIEST_TOKEN_RE.search(spl)
    latest_match = _LATEST_TOKEN_RE.search(spl)
    earliest = earliest_match.group(0) if earliest_match else f"earliest={_DEFAULT_EARLIEST}"
    latest = latest_match.group(0) if latest_match else f"latest={_DEFAULT_LATEST}"
    if not user_time:
        earliest = f"earliest={_DEFAULT_EARLIEST}"
        latest = f"latest={_DEFAULT_LATEST}"

    resolved_sourcetype = _resolve_universal_sourcetype(context)
    # Drop LLM-invented sourcetype unless resolver provided one.
    if _SOURCETYPE_TOKEN_RE.search(spl) and not resolved_sourcetype:
        spl = _SOURCETYPE_TOKEN_RE.sub("", spl, count=1)
        spl = re.sub(r"\s{2,}", " ", spl).strip()

    polished = _build_canonical_universal_weekend_spl(
        resolved_index,
        sourcetype=resolved_sourcetype,
        earliest=earliest,
        latest=latest,
    )
    trace["utility_spl_shape_polish_applied"] = polished != spl
    trace["utility_spl_shape"] = "canonical_weekend_timestamp"
    if resolved_sourcetype:
        trace["resolved_sourcetype"] = resolved_sourcetype
    return polished


# Family wording → trusted index gating. We only accept a concrete (non
# placeholder) index when the requested log family supports it.
_FAMILY_INDEX_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("windows", ("wineventlog", "windows", "win")),
    ("scada", ("scada", "ot")),
    ("ot", ("scada", "ot")),
    ("firewall", ("asa", "firewall", "cisco")),
    ("asa", ("asa", "firewall", "cisco")),
)


@dataclass
class NormalizedSplResult:
    normalized_spl: str
    trace: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _spl_hash(spl: str) -> str:
    return sha256((spl or "").encode("utf-8")).hexdigest()[:16]


def _coerce_slot_handoff(slot_handoff: Any) -> dict[str, str]:
    if slot_handoff is None:
        return {}
    if hasattr(slot_handoff, "normalized_slots"):
        raw = getattr(slot_handoff, "normalized_slots", None)
    elif isinstance(slot_handoff, dict) and isinstance(slot_handoff.get("normalized_slots"), dict):
        raw = slot_handoff.get("normalized_slots")
    elif isinstance(slot_handoff, dict):
        raw = slot_handoff
    else:
        raw = {}
    return {str(k): str(v) for k, v in dict(raw or {}).items() if v is not None and str(v).strip()}


def _changes_from_trace(trace: dict[str, Any], raw_spl: str, normalized_spl: str) -> list[str]:
    changes: list[str] = []
    if trace.get("prefix_wildcard_like_applied"):
        changes.append("actor_prefix_wildcard_normalized")
    if trace.get("index_rewrite_applied"):
        changes.append("index_placeholder_hygiene")
    if trace.get("lookback_rewrite_applied"):
        changes.append("time_bound_injected")
    if trace.get("command_reorder_applied"):
        changes.append("command_hygiene")
    if trace.get("locale_normalization_applied"):
        changes.append("locale_weekend_filter")
    if trace.get("utility_spl_shape_polish_applied"):
        changes.append("utility_shape_polish")
    if raw_spl.strip() != normalized_spl.strip() and not changes:
        changes.append("spl_text_normalized")
    return changes


def _default_finalize_context(
    *,
    family: str | None,
    slot_handoff: Any,
    llm_generated: bool,
    mcp_discovery_context: Any,
) -> dict[str, Any]:
    normalized_slots = _coerce_slot_handoff(slot_handoff)
    family_name = str(family or "").strip()
    discovery = mcp_discovery_context if isinstance(mcp_discovery_context, dict) else {}
    indexes = discovery.get("indexes") if isinstance(discovery.get("indexes"), list) else []
    sourcetypes = discovery.get("sourcetypes") if isinstance(discovery.get("sourcetypes"), list) else []
    return {
        "is_explicit_spl_authoring": family_name != "governed_template",
        "is_universal_spl": family_name in {"universal_timestamp_spl", "universal_spl"},
        "is_template_free": family_name != "governed_template",
        "llm_generated": bool(llm_generated),
        "deterministic_generated": not bool(llm_generated),
        "execution_authorized": False,
        "user_explicit_index": normalized_slots.get("index"),
        "user_explicit_sourcetype": normalized_slots.get("sourcetype"),
        "source_profile_index": str(indexes[0]).strip() if indexes else None,
        "source_profile_sourcetype": str(sourcetypes[0]).strip() if sourcetypes else None,
        "target_log_family": family_name,
        "user_explicit_time_window": bool(
            normalized_slots.get("earliest")
            or normalized_slots.get("latest")
            or normalized_slots.get("time_window")
        ),
    }


def finalize_review_only_spl(
    raw_spl: str,
    *,
    query: str,
    family: str | None,
    slot_handoff: Any = None,
    llm_generated: bool = False,
    mcp_discovery_context: Any = None,
    postprocessor_context: dict[str, Any] | None = None,
) -> NormalizedSplResult:
    """Evaluate the mandatory review-only SPL postprocessor and stamp hashes.

    Governed templates deliberately pass through this wrapper with a no-op trace:
    the hook proves it evaluated the SPL but must not rewrite template bytes.
    """
    raw_text = str(raw_spl or "")
    family_name = str(family or "")
    raw = raw_text if family_name == "governed_template" else raw_text.strip()
    ctx = _default_finalize_context(
        family=family,
        slot_handoff=slot_handoff,
        llm_generated=llm_generated,
        mcp_discovery_context=mcp_discovery_context,
    )
    if isinstance(postprocessor_context, dict):
        ctx.update(postprocessor_context)
    if query:
        from app.spl.user_constraint_bindings import build_user_constraint_bindings

        bindings = build_user_constraint_bindings(query)
        # Fill blanks only — never override an already-authoritative context
        # (utility authoring / COE handoff). Prevents a second finalize pass
        # from dropping user-explicit index/sourcetype literals to placeholders.
        if not ctx.get("user_explicit_index"):
            user_index = (
                str(bindings.normalized_slots.get("index") or "").strip()
                or (str(bindings.explicit_indexes[0]).strip() if bindings.explicit_indexes else "")
            )
            if user_index:
                ctx["user_explicit_index"] = user_index
        if not ctx.get("user_explicit_sourcetype"):
            user_st = (
                str(bindings.normalized_slots.get("sourcetype") or "").strip()
                or (
                    str(bindings.explicit_sourcetypes[0]).strip()
                    if bindings.explicit_sourcetypes
                    else ""
                )
            )
            if user_st:
                ctx["user_explicit_sourcetype"] = user_st
        if not ctx.get("user_explicit_time_bounds"):
            explicit_bounds = (
                str(bindings.explicit_time_window or "").strip()
                or str(bindings.normalized_slots.get("time_window") or "").strip()
                or None
            )
            if explicit_bounds:
                ctx["user_explicit_time_bounds"] = explicit_bounds
                ctx["user_explicit_time_window"] = True
    ctx["llm_generated"] = bool(llm_generated)
    ctx["deterministic_generated"] = not bool(llm_generated)
    ctx.setdefault("target_log_family", str(family or ""))
    if family_name == "governed_template":
        normalized = NormalizedSplResult(
            normalized_spl=raw,
            trace={
                "deterministic_postprocessor_applied": False,
                "skipped_reason": "template_already_normalized",
                "final_spl_authority": "governed_template",
            },
            warnings=[],
        )
    else:
        normalized = normalize_review_only_spl(raw, ctx)
    normalized_spl = normalized.normalized_spl
    trace = dict(normalized.trace)
    changes = _changes_from_trace(trace, raw, normalized_spl)
    applied = bool(changes)
    trace.update(
        postprocessor_evaluated=True,
        postprocessor_applied=applied,
        raw_spl_hash=_spl_hash(raw),
        normalized_spl_hash=_spl_hash(normalized_spl),
        changes=changes,
        postprocessor_family=str(family or ""),
        query_hash=_spl_hash(query or ""),
    )
    if not applied:
        trace["no_op_reason"] = (
            "template_already_normalized"
            if str(family or "") == "governed_template"
            else trace.get("skipped_reason") or "already_normalized"
        )
    return NormalizedSplResult(
        normalized_spl=normalized_spl,
        trace=trace,
        warnings=list(normalized.warnings),
    )


def _is_placeholder(index_value: str) -> bool:
    value = (index_value or "").strip()
    return value.startswith("<") and value.endswith(">")


def _family_supports_index(target_log_family: str | None, index_value: str) -> bool:
    """A concrete (non-placeholder) index is only trusted if the requested log
    family supports it — never accept an index just because an LLM emitted it."""
    family = (target_log_family or "").strip().lower()
    candidate = (index_value or "").strip().lower()
    if not candidate or _is_placeholder(candidate):
        return False
    for needle, tokens in _FAMILY_INDEX_HINTS:
        if needle in family and any(tok in candidate for tok in tokens):
            return True
    return False


def _resolve_index(context: dict[str, Any], original_index: str) -> tuple[str, str]:
    """Return (resolved_index, resolution_source) per the fixed precedence.

    1 user explicit, 2 COE target/source-family mapping, 3 source-profile
    single approved index, 4 explicitly configured COE generic utility default,
    5 ``<your_index>`` placeholder. A user-explicit wildcard is preserved.
    """
    user_index = (context.get("user_explicit_index") or "").strip()
    if user_index:
        return user_index, "user_explicit"

    coe_index = (context.get("coe_environment_index") or "").strip()
    if coe_index:
        return coe_index, "coe_environment_kb"

    profile_index = (context.get("source_profile_index") or "").strip()
    if profile_index:
        return profile_index, "source_profile_resolver"

    utility_default = (context.get("coe_generic_utility_default_index") or "").strip()
    if utility_default:
        return utility_default, str(
            context.get("coe_generic_utility_default_source") or "coe_generic_utility_default"
        )

    target_family = context.get("target_log_family")
    if _family_supports_index(target_family, original_index):
        return original_index.strip(), "draft_family_supported"

    # Explicit broad wildcard request — preserve intent, caller hardens time.
    if original_index.strip() == "*" and context.get("user_explicit_index") == "*":
        return "*", "user_explicit_wildcard"

    return _PLACEHOLDER_INDEX, "placeholder"


_LIKE_CALL_RE = re.compile(
    r"like\s*\(\s*([A-Za-z_][\w]*)\s*,\s*(['\"])([^'\"]+)\2\s*\)",
    re.IGNORECASE,
)
_LIKE_INFIX_RE = re.compile(
    r"\b([A-Za-z_][\w]*)\s+LIKE\s+(['\"])([^'\"]+)\2",
    re.IGNORECASE,
)
_NORM_FIELD_FOR = {
    "user": "user_norm",
    "username": "user_norm",
    "account": "user_norm",
    "account_name": "user_norm",
    "targetusername": "user_norm",
}


def _actor_prefix_stems(spec: dict[str, Any]) -> tuple[str, ...]:
    stems: list[str] = []
    for pattern in spec.get("actor_patterns") or []:
        token = str(pattern).strip()
        if token.endswith("*") and not token.startswith("*") and len(token) > 1:
            stems.append(token[:-1])
    return tuple(stems)


def _prefix_like_target(inner: str, stems: tuple[str, ...]) -> str | None:
    """Return `stem%` when inner is a prefix wildcard for a contract actor."""
    compact = inner.strip().replace("%", "*")
    while compact.startswith("*"):
        compact = compact[1:]
    while compact.endswith("*"):
        compact = compact[:-1]
    for stem in stems:
        if compact == stem or compact.rstrip("-") == stem.rstrip("-"):
            return f"{stem}%"
    return None


def _normalize_prefix_like_wildcards(
    spl: str,
    spec: dict[str, Any],
) -> tuple[str, list[str]]:
    """Translate LIKE `*` prefix wildcards to `%` when the contract is a prefix.

    Search-command `field=admin-*` is left unchanged (valid Splunk prefix syntax).
    Does not invent actors or rewrite contains-patterns that are not in the contract.
    """
    stems = _actor_prefix_stems(spec)
    if not stems or not spl:
        return spl, []
    changes: list[str] = []

    def _like_field(field: str) -> str:
        mapped = _NORM_FIELD_FOR.get(field.lower())
        if mapped and mapped.lower() in spl.lower():
            return mapped
        return field

    def _repl(match: re.Match[str]) -> str:
        field, quote, inner = match.group(1), match.group(2), match.group(3)
        target = _prefix_like_target(inner, stems)
        if target is None or inner == target:
            return match.group(0)
        out_field = _like_field(field)
        changes.append("actor_prefix_wildcard_normalized")
        changes.append(f"like({out_field}) {inner} -> {target}")
        return f"like({out_field},{quote}{target}{quote})"

    rewritten = _LIKE_CALL_RE.sub(_repl, spl)

    def _infix_repl(match: re.Match[str]) -> str:
        field, quote, inner = match.group(1), match.group(2), match.group(3)
        target = _prefix_like_target(inner, stems)
        if target is None:
            return match.group(0)
        out_field = _like_field(field)
        changes.append("actor_prefix_wildcard_normalized")
        changes.append(f"like({out_field}) {inner} -> {target}")
        return f"like({out_field},{quote}{target}{quote})"

    rewritten = _LIKE_INFIX_RE.sub(_infix_repl, rewritten)
    # Deduplicate the public change token while keeping detail rows.
    ordered: list[str] = []
    seen: set[str] = set()
    for item in changes:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return rewritten, ordered


def normalize_review_only_spl(
    raw_spl: str,
    context: dict[str, Any] | None = None,
) -> NormalizedSplResult:
    """Normalize a review-only SPL utility/lab draft. Pure + idempotent.

    Only acts when ``is_explicit_spl_authoring`` is truthy; otherwise the SPL is
    returned untouched so this can never reshape governed-template output.
    """
    ctx = dict(context or {})
    spec = ctx.get("semantic_analyst_intent") if isinstance(ctx.get("semantic_analyst_intent"), dict) else {}
    horizon = str(spec.get("search_horizon") or spec.get("time_window") or "").strip()
    if horizon:
        ctx["user_explicit_time_window"] = True
        ctx["user_explicit_time_bounds"] = horizon
    spl = (raw_spl or "").strip()
    trace: dict[str, Any] = {
        "deterministic_postprocessor_applied": False,
        "index_rewrite_applied": False,
        "lookback_rewrite_applied": False,
        "command_reorder_applied": False,
        "locale_normalization_applied": False,
    }
    warnings: list[str] = []

    if not spl or not ctx.get("is_explicit_spl_authoring"):
        trace["skipped_reason"] = "not_explicit_spl_authoring" if spl else "empty_spl"
        return NormalizedSplResult(normalized_spl=spl, trace=trace, warnings=warnings)

    trace["deterministic_postprocessor_applied"] = True

    if ctx.get("llm_generated"):
        rewritten, like_changes = _normalize_prefix_like_wildcards(spl, spec)
        if like_changes:
            spl = rewritten
            trace["prefix_wildcard_like_applied"] = True
            trace["prefix_wildcard_like_changes"] = like_changes[:8]

    # --- Phase 4: index resolution -------------------------------------------
    index_match = _INDEX_TOKEN_RE.search(spl)
    original_index = index_match.group(1) if index_match else ""
    resolved_index, resolution_source = _resolve_index(ctx, original_index)
    trace.update(
        original_index=original_index or None,
        resolved_index=resolved_index,
        index_resolution_source=resolution_source,
        placeholder_used=resolved_index == "<your_index>",
        raw_llm_index_dropped=False,
        raw_llm_index_dropped_reason=None,
    )
    if original_index and resolved_index != original_index:
        trace["index_rewrite_applied"] = True
        trace["index_rewrite_reason"] = f"{resolution_source}_over_draft_index"
        # An LLM-invented index that the family does not support is dropped.
        if ctx.get("llm_generated") and resolution_source == "placeholder":
            trace["raw_llm_index_dropped"] = True
            trace["raw_llm_index_dropped_reason"] = "unsupported_or_untrusted_llm_index"
        spl = _INDEX_TOKEN_RE.sub(f"index={resolved_index}", spl, count=1)

    # --- Phase 5: lookback hygiene -------------------------------------------
    placeholder_or_wildcard = _is_placeholder(resolved_index) or resolved_index == "*"
    user_time = bool(ctx.get("user_explicit_time_window"))
    earliest_match = _EARLIEST_TOKEN_RE.search(spl)
    original_earliest = earliest_match.group(0) if earliest_match else None
    trace["original_earliest"] = original_earliest
    final_earliest = original_earliest

    if not user_time and placeholder_or_wildcard:
        wide = _WIDE_EARLIEST_RE.search(spl)
        if not earliest_match:
            # No time bound at all → add a tight one after the index token.
            spl = _INDEX_TOKEN_RE.sub(
                f"index={resolved_index} earliest={_DEFAULT_EARLIEST} latest={_DEFAULT_LATEST}",
                spl,
                count=1,
            )
            trace["lookback_added"] = True
            trace["lookback_rewrite_applied"] = True
            final_earliest = f"earliest={_DEFAULT_EARLIEST}"
        elif wide:
            spl = _EARLIEST_TOKEN_RE.sub(f"earliest={_DEFAULT_EARLIEST}", spl, count=1)
            if not _LATEST_TOKEN_RE.search(spl):
                spl = _EARLIEST_TOKEN_RE.sub(
                    f"earliest={_DEFAULT_EARLIEST} latest={_DEFAULT_LATEST}", spl, count=1
                )
            trace["lookback_rewrite_applied"] = True
            trace["lookback_rewrite_reason"] = "wide_window_shrunk_for_placeholder_index"
            final_earliest = f"earliest={_DEFAULT_EARLIEST}"
    elif user_time and _WIDE_EARLIEST_RE.search(spl):
        warnings.append("broad_scope_warning")
        trace["broad_scope_warning"] = True

    explicit_bounds = str(ctx.get("user_explicit_time_bounds") or "").strip()
    if user_time and explicit_bounds:
        earliest_token = None
        latest_token = "latest=now"
        for part in explicit_bounds.split():
            if part.lower().startswith("earliest="):
                earliest_token = part
            elif part.lower().startswith("latest="):
                latest_token = part
        if earliest_token:
            existing_sec = _lookback_seconds(spl)
            requested_sec = _lookback_seconds(earliest_token) or _lookback_seconds(
                explicit_bounds
            )
            # A second finalize (live /chat) fills observation-only bounds from
            # "last Nd days" and must not collapse a reachable baseline envelope.
            if (
                _baseline_period_present(spl)
                and existing_sec is not None
                and requested_sec is not None
                and existing_sec > requested_sec
            ):
                trace["lookback_rewrite_skipped"] = "baseline_retrieval_envelope_preserved"
            else:
                if earliest_match:
                    spl = _EARLIEST_TOKEN_RE.sub(earliest_token, spl, count=1)
                else:
                    spl = _INDEX_TOKEN_RE.sub(
                        f"index={resolved_index} {earliest_token} {latest_token}",
                        spl,
                        count=1,
                    )
                if latest_token and not _LATEST_TOKEN_RE.search(spl):
                    spl = spl.replace(earliest_token, f"{earliest_token} {latest_token}", 1)
                trace["lookback_rewrite_applied"] = True
                trace["lookback_rewrite_reason"] = "user_explicit_time_window_enforced"
                final_earliest = earliest_token

    trace["final_earliest"] = final_earliest
    if resolved_index == "*":
        warnings.append("broad_scope_warning")
        trace["broad_scope_warning"] = True

    # --- Phase 6: dependency-aware command hygiene ---------------------------
    lines = [ln.rstrip() for ln in spl.splitlines()]
    removed: list[str] = []
    kept: list[str] = []
    required_streamstats = str(spec.get("analysis_shape") or "") in {"rolling", "sequence"} or "streamstats" in spl.lower()
    for ln in lines:
        stripped = ln.strip().lstrip("|").strip()
        # Preserve streamstats / time-order for rolling and sequence contracts.
        if required_streamstats and re.search(r"\b(streamstats|sort\s+0\s+_time)\b", stripped, re.I):
            kept.append(ln)
            continue
        # Drop an unnecessary leading `sort 0 ...` before any filter; cheap utility
        # drafts do not need a full sort, and it must not precede `where`.
        if re.match(r"sort\s+\d+\b", stripped, re.IGNORECASE) and not required_streamstats:
            removed.append(stripped)
            continue
        kept.append(ln)
    if removed:
        spl = "\n".join(kept)
        trace["command_reorder_applied"] = True
        trace["removed_expensive_commands"] = removed
    trace.setdefault("removed_expensive_commands", removed)
    trace["blocked_reorder_reasons"] = []
    trace["dependency_preserved"] = True

    # --- Phase 7: locale-safe weekend filtering ------------------------------
    # If a filter keys off the %A day name (e.g. where day_of_week="Saturday"),
    # normalize the *filter* to numeric %w while preserving %A as a display eval.
    name_filter = re.search(
        r"where[^|\n]*\b(day_of_week|dow|day)\b\s*(?:=|IN)\s*\(?[\"']?"
        r"(saturday|sunday)",
        spl,
        re.IGNORECASE,
    )
    trace["display_field_preserved"] = '"%A"' in spl or "%A" in spl
    if name_filter:
        trace["locale_normalization_applied"] = True
        trace["original_day_filter"] = name_filter.group(0)
        trace["normalized_day_filter"] = 'where day_of_week_num IN ("0","6")'
        warnings.append("locale_filter_normalized_to_pct_w")
        if "day_of_week_num" not in spl:
            insert = '| eval day_of_week_num=strftime(_time,"%w")\n'
            if "| where" in spl:
                spl = spl.replace("| where", insert + "| where", 1)
            else:
                spl = spl.rstrip() + "\n" + insert
        spl = re.sub(
            r"\|?\s*where[^|\n]*\b(day_of_week|dow|day)\b\s*(?:=|IN)\s*\(?[\"']?"
            r"(?:saturday|sunday)[^|\n]*",
            '| where day_of_week_num IN ("0","6")',
            spl,
            count=1,
            flags=re.IGNORECASE,
        )

    spl = _polish_universal_utility_spl_shape(
        spl,
        resolved_index=resolved_index,
        context=ctx,
        trace=trace,
    )

    trace["final_spl_authority"] = "deterministic_postprocessor"

    return NormalizedSplResult(normalized_spl=spl.strip(), trace=trace, warnings=warnings)
