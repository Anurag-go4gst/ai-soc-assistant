"""Governed LLM SPL candidate prompt + safe schema parser (T1 SPL-native).

The LLM may only *propose* a review-only SPL draft.  Its output is parsed safely
(fences stripped, schema enforced) and forced to ``execution_eligible=false`` /
``review_required=true``.  Nothing here makes SPL executable; deterministic
validation + analyst approval remain the only path to execution.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.spl.t2_pre_parse import UNSAFE_SPL_COMMANDS, PreParsedSplTokens

ALLOWED_SPL_COMMANDS: frozenset[str] = frozenset(
    {
        "search",
        "fields",
        "eval",
        "bin",
        "stats",
        "eventstats",
        "streamstats",
        "where",
        "table",
        "sort",
        "rename",
        "dedup",
        "lookup",
        "coalesce",
    }
)

BLOCKED_SPL_COMMANDS: frozenset[str] = UNSAFE_SPL_COMMANDS

_RUNTIME_OPERATION_ENUM = (
    "threshold_anomaly",
    "lookup_correlation",
    "aggregate_and_rank",
    "entity_timeline",
    "sequence_detection",
    "unknown",
)

_REQUIRED_KEYS = ("runtime_operation", "candidate_spl")


def build_spl_candidate_prompt(query: str, *, tokens: PreParsedSplTokens) -> str:
    """Return a compact, bounded prompt for a review-only SPL draft."""
    constraints = tokens.to_constraints()
    return (
        "You are a Splunk SPL drafting assistant for a SOC analyst.\n"
        "Return JSON ONLY. No prose, no markdown fences.\n"
        "Schema: {\"runtime_operation\": <enum>, \"candidate_spl\": <string>, "
        "\"entity_fields\": [..], \"metric_fields\": [..], \"assumptions\": [..]}\n"
        f"runtime_operation MUST be one of: {', '.join(_RUNTIME_OPERATION_ENUM)}.\n"
        "Do NOT claim execution, live results, severity, or MITRE mapping. "
        "The SPL is review-only.\n"
        f"Allowed SPL commands only: {', '.join(sorted(ALLOWED_SPL_COMMANDS))}.\n"
        f"Never use blocked commands: {', '.join(sorted(BLOCKED_SPL_COMMANDS))}, "
        "and never use an unbounded index=*.\n"
        "Honour these deterministic hard tokens verbatim where given:\n"
        f"{json.dumps(constraints)}\n"
        f"Analyst request: {query}\n"
    )


@dataclass
class ParsedSplCandidate:
    parsed_ok: bool
    runtime_operation: str = "unknown"
    candidate_spl: str = ""
    entity_fields: list[str] = field(default_factory=list)
    metric_fields: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    execution_eligible: bool = False  # always false; never trusted from the model
    review_required: bool = True
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parsed_ok": self.parsed_ok,
            "runtime_operation": self.runtime_operation,
            "candidate_spl": self.candidate_spl,
            "entity_fields": self.entity_fields,
            "metric_fields": self.metric_fields,
            "assumptions": self.assumptions,
            "execution_eligible": False,
            "review_required": True,
            "warnings": self.warnings,
        }


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        # Drop the opening fence (``` or ```json) and the trailing fence.
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_spl_candidate(raw_output: str | None) -> ParsedSplCandidate:
    """Safely parse an LLM SPL candidate.  Always fails closed to review-only."""
    if not raw_output or not raw_output.strip():
        return ParsedSplCandidate(parsed_ok=False, warnings=["empty_llm_output"])

    text = _strip_fences(raw_output)
    # Recover the first balanced JSON object if surrounded by stray text.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ParsedSplCandidate(parsed_ok=False, warnings=["no_json_object"])
    try:
        payload = json.loads(text[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return ParsedSplCandidate(parsed_ok=False, warnings=["json_decode_failed"])
    if not isinstance(payload, dict):
        return ParsedSplCandidate(parsed_ok=False, warnings=["json_not_object"])

    warnings: list[str] = []
    for key in _REQUIRED_KEYS:
        if key not in payload:
            warnings.append(f"missing_key:{key}")

    operation = str(payload.get("runtime_operation") or "unknown").strip().lower()
    if operation not in _RUNTIME_OPERATION_ENUM:
        warnings.append(f"runtime_operation_out_of_enum:{operation}")
        operation = "unknown"

    candidate_spl = str(payload.get("candidate_spl") or "").strip()

    return ParsedSplCandidate(
        parsed_ok=True,
        runtime_operation=operation,
        candidate_spl=candidate_spl,
        entity_fields=[str(v) for v in payload.get("entity_fields", []) if v],
        metric_fields=[str(v) for v in payload.get("metric_fields", []) if v],
        assumptions=[str(v) for v in payload.get("assumptions", []) if v],
        execution_eligible=False,
        review_required=True,
        warnings=warnings,
    )
