"""Bounded optimization LLM (Layer 3) — one call, proposal only, abstain OK."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from app.config import settings
from app.llm.clients import LocalChatClient, LocalChatError, build_synthesis_client_from_settings
from app.spl.draft_quality import OptimizationClass
from app.spl.rewrite_guard import assert_rewrite_preserves

SPL_OPTIMIZATION_LLM_ROLE = "spl_optimization_llm"

OptimizationLlmOutcome = Literal["OPTIMIZED", "NO_SAFE_OPTIMIZATION", "SKIPPED", "GUARD_FAILED"]


@dataclass(frozen=True)
class OptimizationLlmResult:
    outcome: OptimizationLlmOutcome
    candidate_spl_v1: str
    candidate_spl_v2: str | None = None
    llm_lineage: bool = True
    optimization_source: str = "optimization_llm"
    producer_lineage: str = SPL_OPTIMIZATION_LLM_ROLE
    model: str | None = None
    latency_ms: int | None = None
    advisory_rules: tuple[str, ...] = ()
    guard_result: dict[str, Any] = field(default_factory=dict)
    skip_reason: str | None = None


SPL_OPTIMIZATION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["OPTIMIZED", "NO_SAFE_OPTIMIZATION"]},
        "candidate_spl": {"type": "string"},
    },
    "required": ["status"],
}


# H1 — few-shot contract. The 8B instruct model is prompt-sensitive and, unhardened,
# over-claims OPTIMIZED: it swapped `NOT x=y` for `x!="y"` and stripped wildcards off
# search terms. Examples teach abstention far better than more prose, so keep this set
# short, high-signal, and weighted toward abstain. These examples are a *prevention*
# contract only — authority to accept a rewrite lives in assert_rewrite_preserves.
_FEW_SHOTS: tuple[dict[str, str], ...] = (
    {
        # A — negative filter: changing one negative form into another is not an
        # optimization, and NOT vs != differ on missing/null fields.
        "id": "A_negative_filter_abstain",
        "spl": "search index=auth NOT status=success | stats count by user",
        "issue": "broad negative filter",
        "tempted": 'status!="success"',
        "status": "NO_SAFE_OPTIMIZATION",
        "candidate": "search index=auth NOT status=success | stats count by user",
    },
    {
        # B — wildcard removal changes matching semantics.
        "id": "B_wildcard_abstain",
        "spl": 'search index=network host="*it*" | stats count',
        "issue": "leading wildcard",
        "tempted": 'host="it"',
        "status": "NO_SAFE_OPTIMIZATION",
        "candidate": 'search index=network host="*it*" | stats count',
    },
    {
        # C — doing nothing is a successful outcome.
        "id": "C_already_good_abstain",
        "spl": (
            "search index=auth sourcetype=linux_secure earliest=-1h latest=now action=failure "
            "| stats count by src_ip | sort -count | head 100"
        ),
        "issue": "none material",
        "tempted": "cosmetic reordering",
        "status": "NO_SAFE_OPTIMIZATION",
        "candidate": (
            "search index=auth sourcetype=linux_secure earliest=-1h latest=now action=failure "
            "| stats count by src_ip | sort -count | head 100"
        ),
    },
    {
        # D — never label an unchanged candidate OPTIMIZED.
        "id": "D_identical_abstain",
        "spl": "search index=web sourcetype=access_combined earliest=-24h latest=now status=500 | stats count by uri",
        "issue": "proposed revision is byte-identical to the input",
        "tempted": "returning the same SPL with status OPTIMIZED",
        "status": "NO_SAFE_OPTIMIZATION",
        "candidate": "search index=web sourcetype=access_combined earliest=-24h latest=now status=500 | stats count by uri",
    },
    {
        # E — the safe positive: same-field OR collapses to IN with the exact values.
        "id": "E_or_to_in_positive",
        "spl": "search index=auth (user=alice OR user=bob OR user=carol) | stats count by user",
        "issue": "same-field OR chain",
        "tempted": "adding a value that was not in the input",
        "status": "OPTIMIZED",
        "candidate": "search index=auth user IN (alice,bob,carol) | stats count by user",
    },
    {
        # E2 — the other safe positive. Prompt revision 1 was 6:1 abstain-weighted and
        # the model learned "always abstain" (0 of 4 genuine positives taken in the H5
        # bank). This example shows that editing NON-filtering stages is allowed.
        "id": "E2_early_projection_positive",
        "spl": (
            "search index=auth earliest=-1h latest=now action=failure "
            "| eval unused=1 | stats count by src_ip | head 100"
        ),
        "issue": "unused eval; no fields projection before the first aggregation",
        "tempted": "also 'tidying' the base search while you are in there",
        "status": "OPTIMIZED",
        "candidate": (
            "search index=auth earliest=-1h latest=now action=failure "
            "| fields src_ip | stats count by src_ip | head 100"
        ),
    },
    {
        # F — governed time is authority, never re-derived by the model.
        "id": "F_governed_time_abstain",
        "spl": (
            "search index=auth sourcetype=linux_secure earliest=-1h latest=now action=failure "
            "| eval noise=1 | stats count by src_ip | head 100"
        ),
        "issue": "unused eval / projection opportunity",
        "tempted": "relative_time(now(), '-1h') replacing earliest/latest",
        "status": "NO_SAFE_OPTIMIZATION",
        "candidate": (
            "search index=auth sourcetype=linux_secure earliest=-1h latest=now action=failure "
            "| eval noise=1 | stats count by src_ip | head 100"
        ),
    },
    {
        # G — TERM() is only for tokens whose exact minor-breaker semantics were already
        # intended; it is never a substitute for pattern matching.
        "id": "G_term_wildcard_abstain",
        "spl": 'search index=proxy sourcetype=proxy_log url="*login.corp*" | stats count by src_ip',
        "issue": "minor-breaker token / leading wildcard",
        "tempted": 'TERM(login.corp) replacing url="*login.corp*"',
        "status": "NO_SAFE_OPTIMIZATION",
        "candidate": 'search index=proxy sourcetype=proxy_log url="*login.corp*" | stats count by src_ip',
    },
)


def _render_few_shots() -> str:
    lines: list[str] = ["EXAMPLES (follow these exactly):"]
    for shot in _FEW_SHOTS:
        payload = json.dumps(
            {"status": shot["status"], "candidate_spl": shot["candidate"]},
            separators=(",", ":"),
        )
        lines.extend(
            [
                "",
                f"INPUT: {shot['spl']}",
                f"IDENTIFIED ISSUE: {shot['issue']}",
                f"TEMPTING BUT WRONG: {shot['tempted']}",
                f"OUTPUT: {payload}",
            ]
        )
    return "\n".join(lines)


def _system_prompt() -> str:
    return "\n".join(
        [
            "You are the AI SOC bounded SPL optimization module (Layer 3). Return JSON only.",
            "",
            "Optimization is OPTIONAL. Return OPTIMIZED only when the revised SPL is BOTH:",
            "  1. observably more efficient under one of the identified quality rules; AND",
            "  2. semantics-preserving under the governed investigation contract.",
            "If either is uncertain, return NO_SAFE_OPTIMIZATION. Abstaining is a successful outcome.",
            "",
            "NEVER claim OPTIMIZED when candidate_spl is identical to the input; return",
            "NO_SAFE_OPTIMIZATION instead. NEVER rewrite for stylistic equivalence: changing",
            "NOT x=y into x!=\"y\" (or the reverse) is NOT an optimization — the forms differ on",
            "missing and null fields.",
            "",
            "NEVER remove, add, or move a wildcard. NEVER turn wildcard matching into exact-token",
            "matching or exact matching into wildcard matching. NEVER invent or remove earliest,",
            "latest, or relative_time(). NEVER narrow or widen the governed time range. NEVER invent",
            "an index, sourcetype, field, lookup, value, or a positive domain for NOT / !=. NEVER",
            "change CIDR semantics, TERM() tokenization, quoting semantics, boolean grouping,",
            "required filters, required output fields, aggregation meaning, result limit, or",
            "investigation intent. NEVER add evidence assumptions. Never optimize by guessing.",
            "",
            "If fixing the identified issue would require any of the above: NO_SAFE_OPTIMIZATION.",
            "",
            "Two changes ARE safe, and you SHOULD return OPTIMIZED for them, because",
            "neither touches which events match:",
            "  1. Collapse a same-field OR chain into field IN (...) using ONLY the values",
            "     already present. Add no value; remove no value.",
            "  2. Drop an eval whose result no later stage uses, and/or add a `fields`",
            "     projection before the first aggregation -- keeping every column that a",
            "     later stats, table or sort still needs.",
            "Abstaining is correct when you are uncertain. It is NOT correct when the",
            "identified issue is one of these two and the search terms are left alone.",
            "",
            "Maximum one pass. No explanation outside JSON.",
            "",
            _render_few_shots(),
        ]
    )


#: Rule ids reach the prompt as opaque strings like "SOC-STD-SPL-001-Q18", which tell an
#: 8B model nothing. Translating them is prevention, not authority: the deterministic
#: lint still decides what fired, and the guard still decides what is accepted.
_RULE_GUIDANCE: dict[str, str] = {
    "Q03": "broad NOT / != in an early stage — usually NOT fixable safely; abstain unless a positive value set is already given",
    "Q04": "same-field OR chain — safe to collapse into IN() with the exact values present",
    "Q06": "multi-vendor field aliases could use coalesce() — do not invent an alias",
    "Q08": "base search should name index and sourcetype — never invent them",
    "Q09": "static filters could sit in the base search — only move filters that already exist",
    "Q15": "minor-breaker token might suit TERM() — only if exact-token matching was already intended",
    "Q16": "leading wildcard is expensive — but removing it changes matching; abstain",
    "Q17": "a non-streaming command runs earlier than necessary — only reorder when equivalence is provable",
    "Q18": "wide pipeline with no `fields` projection before the first aggregation — safe to project early, keeping every column later stages need",
}


def _describe_rules(advisory_rules: list[str]) -> str:
    described: list[str] = []
    for rule in advisory_rules:
        short = rule.rsplit("-", 1)[-1]
        guidance = _RULE_GUIDANCE.get(short)
        described.append(f"{rule} ({guidance})" if guidance else rule)
    return "; ".join(described) if described else "unspecified efficiency gap"


def _user_prompt(
    *,
    candidate_spl: str,
    advisory_rules: list[str],
    user_query: str | None = None,
) -> str:
    rules = _describe_rules(advisory_rules)
    parts = [
        "Input candidate_spl (v1):",
        candidate_spl,
        "",
        f"Efficiency rules triggered (advisory only): {rules}",
    ]
    if user_query:
        parts.extend(["", "Original investigation question:", user_query])
    parts.extend(
        [
            "",
            'Return JSON: {"status":"OPTIMIZED"|"NO_SAFE_OPTIMIZATION","candidate_spl":"..."}',
            "Decide status first, then emit candidate_spl.",
            "When NO_SAFE_OPTIMIZATION, candidate_spl MUST equal the input v1 unchanged.",
            "If you cannot prove the rewrite preserves meaning, choose NO_SAFE_OPTIMIZATION.",
        ]
    )
    return "\n".join(parts)


def _whitespace_normalized(spl: str) -> str:
    """Collapse benign whitespace so a reformatted-but-identical rewrite is recognised."""
    return " ".join((spl or "").split())


def _parse_payload(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    from app.llm.adapter.json_extractor import extract_first_json_object

    text = (raw or "").strip()
    if not text:
        return None, ["empty_output"]
    try:
        extraction = extract_first_json_object(text)
        if not extraction.parsed_ok or not isinstance(extraction.payload, dict):
            raise ValueError("parse_failed")
        payload = extraction.payload
    except Exception:  # noqa: BLE001
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None, ["invalid_json"]
    if not isinstance(payload, dict):
        return None, ["payload_not_object"]
    status = str(payload.get("status") or "").strip().upper()
    if status not in {"OPTIMIZED", "NO_SAFE_OPTIMIZATION"}:
        return None, ["invalid_status"]
    spl = str(payload.get("candidate_spl") or "").strip()
    if status == "OPTIMIZED" and not spl:
        return None, ["optimized_missing_spl"]
    if status == "NO_SAFE_OPTIMIZATION" and not spl:
        payload = {**payload, "candidate_spl": ""}
    return payload, []


def apply_optimization_llm(
    candidate_spl: str,
    *,
    classification: OptimizationClass | str,
    advisory_rules: list[str] | None = None,
    user_query: str | None = None,
    rqc: dict[str, Any] | None = None,
    client: LocalChatClient | None = None,
    llm_raw_output_provider: Any | None = None,
    llm_lineage: bool = True,
) -> OptimizationLlmResult:
    """One bounded optimization call; skipped unless classification requires Layer 3."""
    v1 = str(candidate_spl or "").strip()
    rules = tuple(str(r) for r in (advisory_rules or []) if str(r).strip())
    if str(classification) != "OPTIMIZATION_LLM_REQUIRED":
        return OptimizationLlmResult(
            outcome="SKIPPED",
            candidate_spl_v1=v1,
            llm_lineage=llm_lineage,
            advisory_rules=rules,
            skip_reason=f"classification={classification}",
        )
    if not settings.ai_soc_spl_optimization_llm_enabled:
        return OptimizationLlmResult(
            outcome="SKIPPED",
            candidate_spl_v1=v1,
            llm_lineage=llm_lineage,
            advisory_rules=rules,
            skip_reason="optimization_llm_disabled",
        )
    if not v1:
        return OptimizationLlmResult(
            outcome="SKIPPED",
            candidate_spl_v1=v1,
            llm_lineage=llm_lineage,
            advisory_rules=rules,
            skip_reason="empty_candidate",
        )

    raw_output: str | None = None
    model: str | None = None
    latency_ms: int | None = None

    if llm_raw_output_provider is not None:
        raw_output = str(llm_raw_output_provider())
    else:
        if settings.ai_soc_llm_mode.strip().lower() == "disabled" or not settings.ai_soc_llm_enabled:
            return OptimizationLlmResult(
                outcome="SKIPPED",
                candidate_spl_v1=v1,
                llm_lineage=llm_lineage,
                advisory_rules=rules,
                skip_reason="llm_disabled",
            )
        active = client or build_synthesis_client_from_settings()
        if active is None:
            return OptimizationLlmResult(
                outcome="SKIPPED",
                candidate_spl_v1=v1,
                llm_lineage=llm_lineage,
                advisory_rules=rules,
                skip_reason="no_client",
            )
        try:
            completion = active.generate(
                system_prompt=_system_prompt(),
                user_prompt=_user_prompt(
                    candidate_spl=v1,
                    advisory_rules=list(rules),
                    user_query=user_query,
                ),
                max_tokens=512,
                temperature=0.0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "spl_optimization",
                        "schema": SPL_OPTIMIZATION_JSON_SCHEMA,
                    },
                },
            )
        except LocalChatError:
            return OptimizationLlmResult(
                outcome="NO_SAFE_OPTIMIZATION",
                candidate_spl_v1=v1,
                candidate_spl_v2=None,
                llm_lineage=llm_lineage,
                advisory_rules=rules,
                skip_reason="llm_error",
            )
        raw_output = completion.text
        model = completion.model
        latency_ms = completion.latency_ms

    payload, errors = _parse_payload(raw_output or "")
    if payload is None:
        return OptimizationLlmResult(
            outcome="NO_SAFE_OPTIMIZATION",
            candidate_spl_v1=v1,
            llm_lineage=llm_lineage,
            advisory_rules=rules,
            model=model,
            latency_ms=latency_ms,
            skip_reason="parse_failed:" + ",".join(errors),
        )

    status = str(payload.get("status") or "").strip().upper()
    v2 = str(payload.get("candidate_spl") or v1).strip() or v1
    # H2 — an unchanged candidate is never an optimization, whatever the model claims.
    # Deterministic and independent of self-report: benign whitespace differences only.
    if status == "NO_SAFE_OPTIMIZATION" or _whitespace_normalized(v2) == _whitespace_normalized(v1):
        return OptimizationLlmResult(
            outcome="NO_SAFE_OPTIMIZATION",
            candidate_spl_v1=v1,
            candidate_spl_v2=None,
            llm_lineage=llm_lineage,
            advisory_rules=rules,
            model=model,
            latency_ms=latency_ms,
        )

    guard = assert_rewrite_preserves(v1, v2, rqc)
    if guard.get("verdict") != "PASS":
        return OptimizationLlmResult(
            outcome="GUARD_FAILED",
            candidate_spl_v1=v1,
            candidate_spl_v2=None,
            llm_lineage=llm_lineage,
            advisory_rules=rules,
            model=model,
            latency_ms=latency_ms,
            guard_result=guard,
        )

    return OptimizationLlmResult(
        outcome="OPTIMIZED",
        candidate_spl_v1=v1,
        candidate_spl_v2=v2,
        llm_lineage=llm_lineage,
        advisory_rules=rules,
        model=model,
        latency_ms=latency_ms,
        guard_result=guard,
    )
