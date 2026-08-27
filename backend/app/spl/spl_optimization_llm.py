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


def _system_prompt() -> str:
    return (
        "You are the AI SOC bounded SPL optimization module (Layer 3). Return JSON only. "
        "Improve ONLY the identified efficiency issues while preserving investigation meaning. "
        "Preserve index, sourcetype, governed time scope, required filters, required output fields, "
        "aggregation meaning, and result limit semantics. Invent no index, sourcetype, field, or lookup. "
        "Add no evidence assumptions. Never force a rewrite of valid SPL — if no semantics-preserving "
        "improvement exists, return status NO_SAFE_OPTIMIZATION with candidate_spl equal to the input. "
        "Maximum one pass; no explanation outside JSON."
    )


def _user_prompt(
    *,
    candidate_spl: str,
    advisory_rules: list[str],
    user_query: str | None = None,
) -> str:
    rules = ", ".join(advisory_rules) if advisory_rules else "unspecified efficiency gap"
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
            "When NO_SAFE_OPTIMIZATION, candidate_spl MUST equal the input v1 unchanged.",
        ]
    )
    return "\n".join(parts)


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
    if status == "NO_SAFE_OPTIMIZATION" or v2 == v1:
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
