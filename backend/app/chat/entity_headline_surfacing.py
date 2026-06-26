"""WS-7b entity-bound investigation + WS-7c T1 headline enrichment.

Both target the same defect: a real SPL/asset answer exists in the payload but the
analyst message collapses to a status-only stub ("Governed SPL draft ready ...").

- WS-7c (T1 in-catalogue): when an SPL artifact is present but the message is a
  status-only stub, build a headline = hunt objective + review-only disclaimer +
  >=3 review steps. Applies to in-catalogue rows too, so it does NOT bypass on the
  happy path (unlike WS-0/WS-2).
- WS-7b (T2 entity ask): when the query names a concrete asset (relay id,
  substation, host) and the message is thin, emit an asset-scoped checklist plus an
  explicit "compromise not confirmed from this signal alone" line.
"""

from __future__ import annotations

import re
from typing import Any

from app.chat.contracts.answer_contract import AnswerContract
from app.config import settings
from app.schemas.responses import AnalystResponseEnvelope

# Status-only stubs that mean "a result exists but the card said nothing useful".
_STATUS_ONLY_STUBS: tuple[str, ...] = (
    "governed spl draft ready",
    "spl validation complete",
    "investigation planning is complete",
    "spl and mcp execution are disabled",
    "mcp execution is disabled",
)

# Named-asset detectors (relay tags, generic asset tags, OT host roles).
_RELAY_TAG = re.compile(r"\b[A-Z]{2,4}[-\s]?\d{3,5}\b")
_SUBSTATION = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+substation\b")
_HOST_ROLE = re.compile(r"\b(?:hmi|rtu|plc|ied|relay|historian|jump[-\s]?host)[-\s]?[A-Za-z0-9]{1,12}\b", re.IGNORECASE)


def is_status_only_message(message: str | None) -> bool:
    lowered = " ".join(str(message or "").lower().split())
    if not lowered:
        return True
    # Treat as status-only only when the whole message is short and stub-like.
    if len(lowered) > 320:
        return False
    return any(stub in lowered for stub in _STATUS_ONLY_STUBS)


def extract_named_assets(query: str) -> list[str]:
    found: list[str] = []
    for match in _RELAY_TAG.findall(query):
        token = match.strip()
        if token and token not in found:
            found.append(token)
    for sub in _SUBSTATION.findall(query):
        token = f"{sub.strip()} substation"
        if token not in found:
            found.append(token)
    for match in _HOST_ROLE.findall(query):
        token = match.strip()
        # Skip bare role words with no identifier (e.g. plain "relay").
        if token and any(ch.isdigit() for ch in token) and token not in found:
            found.append(token)
    return found[:6]


def _has_spl_artifact(
    answer_contract: AnswerContract | None,
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
) -> bool:
    if answer_contract is not None and bool(answer_contract.render_sections.get("spl_artifact")):
        return True
    if isinstance(spl_validation, dict) and str(spl_validation.get("normalized_spl") or "").strip():
        return True
    if isinstance(candidate_spl, dict) and str(candidate_spl.get("candidate_spl") or "").strip():
        return True
    return False


def build_entity_bound_checklist(query: str, assets: list[str]) -> str:
    asset_line = ", ".join(assets)
    return (
        f"Asset-scoped investigation — {asset_line} (review-only)\n\n"
        "Checklist:\n"
        f"- Pin the investigation to {asset_line}: confirm owner, function, zone, and criticality.\n"
        "- Pull this asset's syslog/event history and compare against its own baseline and peer assets.\n"
        "- Correlate the anomaly with change tickets, maintenance windows, and recent config/firmware pushes.\n"
        "- Check upstream access paths (engineering workstation, jump host, vendor session) for the same window.\n"
        "- Validate time integrity before trusting event ordering on the device.\n\n"
        "Judgment: odd syslog on this asset alone does NOT confirm compromise — corroborate across "
        "independent signals (access, change, network) before declaring an incident. No MITRE technique "
        "or severity is claimed from this question alone."
    )


def build_t1_headline(query: str) -> str:
    objective = " ".join(str(query).split())[:200]
    return (
        f"Objective: {objective}\n\n"
        "A governed SPL draft was produced and passed deterministic validation; it is review-only "
        "and was not executed (MCP execution disabled).\n\n"
        "Review steps:\n"
        "- Confirm the index/sourcetype and field mappings match your deployment before running.\n"
        "- Validate the time window and any thresholds against the asset baseline.\n"
        "- Run as review-only first; treat counts as evidence to corroborate, not a verdict.\n\n"
        "Limitations: no live results were returned; no severity or MITRE technique is claimed from the draft alone."
    )


def apply_entity_and_headline_surfacing(
    *,
    message: str,
    answer_contract: AnswerContract | None,
    analyst_response: AnalystResponseEnvelope | None,
    spl_validation: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
    user_query: str,
) -> tuple[str, AnalystResponseEnvelope | None]:
    """Enrich a status-only stub message in place; otherwise pass through.

    Intentionally NOT gated by the happy-path bypass — WS-7c must enrich
    in-catalogue T1 rows whose card collapsed to a status string.
    """
    if not settings.ai_soc_t2_answer_surfacing_enabled:
        return message, analyst_response
    if not is_status_only_message(message):
        return message, analyst_response

    assets = extract_named_assets(user_query)
    if assets:
        enriched = build_entity_bound_checklist(user_query, assets)
    elif _has_spl_artifact(answer_contract, spl_validation, candidate_spl):
        enriched = build_t1_headline(user_query)
    else:
        return message, analyst_response

    updated_response = analyst_response
    if analyst_response is not None:
        updated_response = analyst_response.model_copy(
            update={"direct_answer_summary": enriched[:2000]}
        )
        from app.chat.guidance_envelope import populate_envelope_from_guidance

        updated_response = populate_envelope_from_guidance(updated_response, enriched)
    return enriched, updated_response
