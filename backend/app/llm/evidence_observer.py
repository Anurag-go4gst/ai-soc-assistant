"""Evidence observer role: parse bounded MCP row observations (plan item 8)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.adapter.role_results import adapt_llm_output
from app.llm.adapter.schemas import EvidenceObserverPayload
from app.llm.prompts import PROMPT_CONTRACTS
from app.safeguards.prompt_injection_filter import filter_prompt_injection
from app.synthesis.models import GovernedEvidenceObservation

EVIDENCE_OBSERVER_ROLE = "evidence_observer"
MAX_OBSERVATIONS = 5
MAX_ROWS = 50
MAX_ROW_CHARS = 200
ROW_FIELD_WHITELIST = ("_time", "host", "sourcetype", "user", "action", "search_string", "src_ip", "dest_ip", "dest_port")
WITHHELD_ROW_TEXT = "[row withheld: injection_suspect]"


@dataclass
class EvidenceObserverParseResult:
    accepted: bool
    payload: EvidenceObserverPayload | None = None
    governed_observations: list[GovernedEvidenceObservation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    next_hop_hint: str | None = None
    unreadable: bool = False


@dataclass(frozen=True)
class SanitizedObserverRows:
    prompt_text: str
    row_text_by_index: dict[int, str]
    injection_withheld_count: int = 0
    warnings: list[str] = field(default_factory=list)


def prompt_contract_for_evidence_observer() -> dict[str, Any]:
    return dict(PROMPT_CONTRACTS[EVIDENCE_OBSERVER_ROLE])


def _row_has_prompt_injection(row: Mapping[str, Any]) -> bool:
    for value in row.values():
        if not isinstance(value, str):
            continue
        verdict = filter_prompt_injection(value)
        if not verdict.get("allowed", True):
            return True
    return False


def sanitize_row_for_prompt(row: Mapping[str, Any], *, row_index: int) -> str:
    if _row_has_prompt_injection(row):
        return f"{row_index}: {WITHHELD_ROW_TEXT}"
    parts: list[str] = []
    for key in ROW_FIELD_WHITELIST:
        value = row.get(key)
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    if not parts:
        parts.append(json.dumps({k: row[k] for k in sorted(row) if k in ROW_FIELD_WHITELIST}, default=str))
    line = " ".join(parts).strip()
    if len(line) > MAX_ROW_CHARS:
        line = line[: MAX_ROW_CHARS - 3] + "..."
    return f"{row_index}: {line}" if line else f"{row_index}: [empty]"


def sanitize_rows_for_observer(rows: list[Mapping[str, Any]]) -> SanitizedObserverRows:
    row_text_by_index: dict[int, str] = {}
    withheld = 0
    for index, row in enumerate(rows[:MAX_ROWS], start=1):
        line = sanitize_row_for_prompt(row, row_index=index)
        row_text_by_index[index] = line
        if WITHHELD_ROW_TEXT in line:
            withheld += 1
    warnings = ["mcp_result_prompt_injection_blocked"] if withheld else []
    return SanitizedObserverRows(
        prompt_text="\n".join(row_text_by_index.values()),
        row_text_by_index=row_text_by_index,
        injection_withheld_count=withheld,
        warnings=warnings,
    )


def format_rows_for_prompt(rows: list[Mapping[str, Any]]) -> str:
    return sanitize_rows_for_observer(rows).prompt_text


def to_governed_observations(payload: EvidenceObserverPayload) -> list[GovernedEvidenceObservation]:
    governed: list[GovernedEvidenceObservation] = []
    for item in payload.observations[:MAX_OBSERVATIONS]:
        governed.append(
            GovernedEvidenceObservation(
                claim=item.claim,
                row_refs=list(item.row_refs),
                confidence=item.confidence,
            )
        )
    return governed


def parse_evidence_observer_output(raw_output: str) -> EvidenceObserverParseResult:
    extraction = extract_first_json_object(raw_output)
    if not extraction.parsed_ok or extraction.payload is None:
        return EvidenceObserverParseResult(
            accepted=False,
            warnings=list(extraction.warnings),
            errors=list(extraction.errors or ["json_extraction_failed"]),
        )

    adapted = adapt_llm_output(role=EVIDENCE_OBSERVER_ROLE, raw_output=raw_output)
    if not adapted.accepted or not isinstance(adapted.normalized_payload, dict):
        return EvidenceObserverParseResult(
            accepted=False,
            warnings=list(adapted.warnings),
            errors=list(adapted.errors or ["adapter_rejected"]),
        )

    try:
        payload = EvidenceObserverPayload.model_validate(adapted.normalized_payload)
    except Exception as exc:  # noqa: BLE001 - surfaced as parse failure
        return EvidenceObserverParseResult(
            accepted=False,
            warnings=list(adapted.warnings),
            errors=[str(exc)],
        )

    warnings = list(adapted.warnings)
    if isinstance(extraction.payload, dict):
        raw_observations = extraction.payload.get("observations")
        if isinstance(raw_observations, list) and len(raw_observations) > MAX_OBSERVATIONS:
            warnings.append("observations_capped_at_5")

    return EvidenceObserverParseResult(
        accepted=True,
        payload=payload,
        governed_observations=to_governed_observations(payload),
        warnings=warnings,
        next_hop_hint=payload.next_hop_hint,
        unreadable=bool(payload.unreadable),
    )
