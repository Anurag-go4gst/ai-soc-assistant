"""Post-validation analyst synthesis for review-only SPL drafts.

The FINAL VALIDATED SPL is immutable. This module only produces presentation
copy. On any LLM or grounding failure it falls back to a deterministic
explanation built from spl_semantic_v2 + governed mappings. It never
regenerates, repairs, or substitutes SPL.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.config import settings
from app.chat.llm_interaction_trace import capture_llm_interaction
from app.llm.adapter.json_extractor import extract_first_json_object
from app.llm.clients import LocalChatError, build_synthesis_client_from_settings
from app.llm.llm_call_context import CALL_PURPOSE_SYNTHESIS_LAB, llm_call_purpose_scope
from app.llm.sidecar_governance import run_sidecar_llm_with_timeout
from app.safeguards.trust_boundary import CONTROL_PREAMBLE, wrap_untrusted_source

SYNTHESIS_SOURCE_LLM = "LLM_SYNTHESIS"
SYNTHESIS_SOURCE_DETERMINISTIC = "DETERMINISTIC_SYNTHESIS_FALLBACK"

REVIEW_ONLY_TITLE = "Review-only SPL draft — not executed"
NO_EXECUTION_FOOTER = "No query was executed."

_SYNTHESIS_TIMEOUT_SECONDS = 45.0
_SYNTHESIS_MAX_TOKENS = 400


_SYSTEM_PROMPT = (
    CONTROL_PREAMBLE
    + "\nYou explain a FINAL VALIDATED Splunk SPL query to a SOC analyst.\n"
    "Return JSON only with keys: summary, what_it_does, mappings_assumptions, expected_result.\n"
    "Rules:\n"
    "- Do NOT return SPL, code fences, queries, indexes to add, or rewritten searches.\n"
    "- Explain only the supplied final_validated_spl and governed mappings.\n"
    "- summary: 1-2 sentences. what_it_does: 2-4 bullets. mappings_assumptions: 0-4 bullets.\n"
    "- expected_result: one sentence describing what one returned row means.\n"
    "- Do not mention MITRE, remediation, investigation steps, execution, result counts,\n"
    "  compilers, validators, authoring, MCP, or live compromise.\n"
    "- Do not invent datamodels, tstats, joins, indexes, or sourcetypes absent from the inputs.\n"
    "- Numeric windows and thresholds must match the supplied semantic contract.\n"
    "- Be concise and professional. No filler such as 'here is a query you could use'."
)

_SPL_IN_TEXT_RE = re.compile(
    r"(```)|(\bindex\s*=\s*\S)|(\|\s*(?:stats|tstats|join|eval|where|search|datamodel|from)\b)",
    re.IGNORECASE,
)
_CODE_FENCE_RE = re.compile(r"```")
_SENTENCE_RE = re.compile(r"[.!?]+")
_DURATION_RE = re.compile(
    r"\b(\d+)\s*(minutes?|minute|mins?|hours?|hour|hrs?|days?|day|seconds?|second|secs?|m|h|d|s)\b",
    re.IGNORECASE,
)
_INDEX_MENTION_RE = re.compile(
    r"\bindex(?:es)?\s*(?:`|=)?\s*([A-Za-z0-9:_<>-]+)",
    re.IGNORECASE,
)
_SOURCETYPE_MENTION_RE = re.compile(
    r"\bsourcetype\s*(?:`|=)?\s*([A-Za-z0-9:_<>-]+)",
    re.IGNORECASE,
)

_FORBIDDEN_SUBSTRINGS: tuple[tuple[str, str], ...] = (
    ("mitre", "forbidden_mitre"),
    ("att&ck", "forbidden_mitre"),
    ("t1110", "forbidden_mitre"),
    ("t1059", "forbidden_mitre"),
    ("remediation", "forbidden_remediation"),
    ("containment", "forbidden_remediation"),
    ("block the source", "forbidden_remediation"),
    ("block the ip", "forbidden_remediation"),
    ("disable account", "forbidden_remediation"),
    ("incident response", "forbidden_investigation"),
    ("investigation steps", "forbidden_investigation"),
    ("evidence required", "forbidden_investigation"),
    ("missing evidence", "forbidden_investigation"),
    ("recommended next", "forbidden_investigation"),
    ("query executed", "forbidden_execution_claim"),
    ("query was executed", "forbidden_execution_claim"),
    ("the query returned", "forbidden_result_count"),
    ("returned ", "forbidden_result_count"),
    ("results show", "forbidden_result_count"),
    ("compiler rescue", "forbidden_internal"),
    ("authoring_source", "forbidden_internal"),
    ("llm authoring", "forbidden_internal"),
    ("legacy_compiler", "forbidden_internal"),
    ("validator", "forbidden_internal"),
    ("account is compromised", "forbidden_live_claim"),
    ("compromised administrator", "forbidden_live_claim"),
    ("live compromise", "forbidden_live_claim"),
    ("malicious activity", "forbidden_live_claim"),
    ("first-success-only", "forbidden_sequence_collapse"),
    ("first success only", "forbidden_sequence_collapse"),
    ("aggregated sequences", "forbidden_sequence_collapse"),
)

_GENERIC_FILLER = (
    "here is a query you could use",
    "here is a query",
    "you could use the following",
)


class ReviewOnlySplSynthesisPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str
    what_it_does: list[str] = Field(default_factory=list)
    mappings_assumptions: list[str] = Field(default_factory=list)
    expected_result: str = ""

    @field_validator("summary", "expected_result")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return str(value or "").strip()

    @field_validator("what_it_does", "mappings_assumptions")
    @classmethod
    def _strip_list(cls, values: list[str]) -> list[str]:
        return [str(item).strip() for item in (values or []) if str(item).strip()]


@dataclass
class ReviewOnlyAnalystSynthesis:
    summary: str
    what_it_does: list[str]
    mappings_assumptions: list[str]
    expected_result: str
    source: str
    dropped_reasons: list[str] = field(default_factory=list)
    # Observability only. The debug bundle must be able to say whether an LLM was
    # asked to narrate this card, and how long it took, without inferring it from
    # a global llm_used boolean that a dropped SPL advisory also drives.
    llm_attempted: bool = False
    llm_latency_ms: int | None = None

    def public_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "what_it_does": list(self.what_it_does),
            "mappings_assumptions": list(self.mappings_assumptions),
            "expected_result": self.expected_result,
        }


def compact_semantic_contract(spec: dict[str, Any] | None) -> dict[str, Any]:
    spec = spec if isinstance(spec, dict) else {}
    roles = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    window = spec.get("analytical_window") if isinstance(spec.get("analytical_window"), dict) else {}
    process = spec.get("process_constraints") if isinstance(spec.get("process_constraints"), dict) else {}
    compact = {
        "analysis_shape": spec.get("analysis_shape"),
        "observation_window": spec.get("observation_window"),
        "baseline_window": spec.get("baseline_window"),
        "search_horizon": spec.get("search_horizon"),
        "temporal_grain": spec.get("temporal_grain"),
        "analytical_window": {
            "kind": window.get("kind"),
            "size": window.get("size"),
        }
        if window
        else None,
        "sequence_max_gap": spec.get("sequence_max_gap"),
        "explicit_threshold_present": spec.get("explicit_threshold_present"),
        "explicit_threshold_value": spec.get("explicit_threshold_value"),
        "required_event_sets": list(spec.get("required_event_sets") or []),
        "ordered_sequence": list(spec.get("ordered_sequence") or []),
        "actor_patterns": list(spec.get("actor_patterns") or []),
        "required_outputs": list(spec.get("required_outputs") or []),
        "entity_roles": {
            "subject": list(roles.get("subject") or []),
            "target": list(roles.get("target") or []),
            "correlate_by": list(roles.get("correlate_by") or []),
        },
        "process_constraints": {
            "parent": list(process.get("parent") or []),
            "child": list(process.get("child") or []),
        }
        if process
        else None,
    }
    return {key: value for key, value in compact.items() if value not in (None, [], {})}


def build_synthesis_input(
    *,
    original_user_request: str,
    spec: dict[str, Any] | None,
    final_validated_spl: str,
    governed_source_mappings: list[str] | None = None,
    validated_assumptions: list[str] | None = None,
) -> dict[str, Any]:
    contract = compact_semantic_contract(spec)
    return {
        "original_user_request": str(original_user_request or "").strip(),
        "spl_semantic_v2": contract,
        "final_validated_spl": str(final_validated_spl or "").strip(),
        "governed_source_mappings": [str(item).strip() for item in (governed_source_mappings or []) if str(item).strip()],
        "validated_assumptions": [str(item).strip() for item in (validated_assumptions or []) if str(item).strip()],
        "final_output_fields": list(contract.get("required_outputs") or []),
    }


def governed_mappings_for_card(
    *,
    spec: dict[str, Any] | None,
    final_validated_spl: str,
    candidate_spl: dict[str, Any] | None = None,
) -> list[str]:
    spec = spec if isinstance(spec, dict) else {}
    spl = str(final_validated_spl or "")
    mappings: list[str] = []
    cs = candidate_spl if isinstance(candidate_spl, dict) else {}
    post = cs.get("review_only_spl_postprocessor_trace")
    post = post if isinstance(post, dict) else {}
    resolved_index = str(post.get("resolved_index") or "").strip()
    if resolved_index and resolved_index != "<your_index>":
        mappings.append(f"Index `{resolved_index}` is the bound search index.")
    elif "<your_index>" in spl:
        mappings.append("`<your_index>` must be resolved to the approved source index before review.")
    constraints = spec.get("source_constraints") if isinstance(spec.get("source_constraints"), dict) else {}
    sourcetype = str(constraints.get("sourcetype") or post.get("resolved_sourcetype") or "").strip()
    if sourcetype and sourcetype not in {"<your_sourcetype>", "<sourcetype>"}:
        mappings.append(f"Sourcetype `{sourcetype}`.")
    if "4625" in spl:
        mappings.append(
            "Authentication failures use the governed failure/action mappings or EventCode 4625."
        )
    if "4624" in spl:
        mappings.append(
            "Successful logins use the governed success mapping or EventCode 4624."
        )
    if spec.get("analysis_shape") == "sequence":
        mappings.append(
            "User, source IP, and destination host are normalized from available authentication fields."
        )
    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for item in mappings:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:4]


def deterministic_synthesis(
    *,
    spec: dict[str, Any] | None,
    final_validated_spl: str,
    candidate_spl: dict[str, Any] | None = None,
    governed_source_mappings: list[str] | None = None,
) -> ReviewOnlyAnalystSynthesis:
    spec = spec if isinstance(spec, dict) else {}
    shape = str(spec.get("analysis_shape") or "")
    roles = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    process = spec.get("process_constraints") if isinstance(spec.get("process_constraints"), dict) else {}
    observation = _window_label(str(spec.get("observation_window") or "").strip())
    baseline = _window_label(str(spec.get("baseline_window") or "").strip())
    horizon = _window_label(str(spec.get("search_horizon") or "").strip())
    grain = str(spec.get("temporal_grain") or "").strip()
    analytical = spec.get("analytical_window") if isinstance(spec.get("analytical_window"), dict) else {}
    window = str(analytical.get("size") or "").strip()
    follow = str(spec.get("sequence_max_gap") or "").strip()
    threshold = spec.get("explicit_threshold_value")
    outputs = [str(item) for item in (spec.get("required_outputs") or []) if str(item).strip()]
    subject = _first(roles.get("subject")) or "account"
    target = _first(roles.get("target")) or "object"
    parents = [str(item) for item in (process.get("parent") or []) if str(item).strip()]
    children = [str(item) for item in (process.get("child") or []) if str(item).strip()]
    actors = [str(item) for item in (spec.get("actor_patterns") or []) if str(item).strip()]

    summary = "Review-only SPL draft matching the requested filters and outputs."
    bullets: list[str] = []
    expected = "Each row is one matching result for the requested outputs."

    if shape == "sequence":
        threshold_bit = f"more than {threshold} " if threshold not in (None, "") else ""
        window_bit = f" within {window}" if window else ""
        follow_bit = f" within {follow}" if follow else ""
        if follow in {"10m", "10 minutes"}:
            follow_bit = " within 10 minutes (600 seconds)"
        summary = (
            "Review-only authentication sequence query: a qualifying failure burst "
            "followed by a later successful login."
        )
        bullets = [
            f"Finds a failure burst of {threshold_bit}failed authentication attempts{window_bit} for the same user and source IP.",
            "Establishes that qualifying failure burst first, then a later successful login"
            f"{follow_bit}.",
            "Destination host comes from the successful-login event; each valid success keeps its own burst association.",
        ]
        expected = (
            "Each row represents a qualifying authentication-failure burst and a "
            "subsequent successful login associated with that burst."
        )
    elif shape == "parent_child" or (children and parents):
        child_bit = " or ".join(children) if children else "the child process"
        parent_bit = " or ".join(parents) if parents else "the parent process"
        window_bit = observation or "24h"
        summary = f"Review-only parent-child process query for {child_bit} launched by {parent_bit}."
        bullets = [
            f"Finds {child_bit} launched by {parent_bit} on the same process event during the last {window_bit}, grouped by host and user.",
            "The relationship is the parent process launching the child on that event, not a command-line substring match.",
        ]
        if outputs:
            bullets.append("Returns " + ", ".join(_human_outputs(outputs)) + ".")
        expected = (
            "Each row summarizes PowerShell child-process events launched by Word or Excel for a host and user."
            if {"powershell.exe", "winword.exe", "excel.exe"} <= {item.lower() for item in children + parents}
            else f"Each row summarizes {child_bit} events launched by {parent_bit} for a host and user."
        )
    elif shape == "first_seen":
        who = f"the same {subject}" if subject else "the same subject"
        if target in {"host", "dest", "dest_host", "destination_host"}:
            summary = "Review-only first-seen host query for matching accounts."
            actor_bit = " or ".join(actors) if actors else "matching accounts"
            bullets = [
                f"Looks at successful logons for accounts matching {actor_bit}."
                if actors
                else "Looks at successful logons for matching accounts.",
            ]
            if observation and baseline:
                bullets.append(
                    f"Compares the last {observation} with the preceding {baseline} history for {who}."
                )
            bullets.append(
                f"Keeps {target} values absent from that account baseline"
                + (f" and groups findings into {grain} windows." if grain else ".")
            )
            expected = (
                "Each row represents an account/time window containing one or more "
                "destination hosts not present in that account's preceding baseline."
            )
        else:
            summary = "Review-only first-seen destination-domain query for the same host."
            bullets = []
            if horizon:
                bullets.append(f"Retrieves a {horizon} total window.")
            if observation and baseline:
                bullets.append(
                    f"Uses the last {observation} as observation and the immediately preceding {baseline} as baseline."
                )
            bullets.append(
                f"Compares destination domains for {who} and keeps exact historical absences."
            )
            expected = (
                "Each row represents a destination domain observed during the last "
                f"{observation or '24h'} that was absent from that host's preceding "
                f"{baseline or '14d'} history."
            )
        if outputs and len(bullets) < 4:
            bullets.append("Returns " + ", ".join(_human_outputs(outputs)) + ".")
    else:
        if observation and baseline:
            bullets.append(
                f"Retrieves a {observation} observation window plus a preceding {baseline} baseline."
            )
        if outputs:
            bullets.append("Returns " + ", ".join(_human_outputs(outputs)) + ".")
        if not bullets:
            bullets.append("Produces a review-only SPL draft matching the requested filters and outputs.")

    mappings = list(governed_source_mappings or []) or governed_mappings_for_card(
        spec=spec,
        final_validated_spl=final_validated_spl,
        candidate_spl=candidate_spl,
    )
    return ReviewOnlyAnalystSynthesis(
        summary=_clip_sentences(summary, 2),
        what_it_does=bullets[:4],
        mappings_assumptions=mappings[:4],
        expected_result=_clip_sentences(expected, 1),
        source=SYNTHESIS_SOURCE_DETERMINISTIC,
    )


def validate_synthesis_payload(
    payload: ReviewOnlySplSynthesisPayload,
    *,
    spec: dict[str, Any] | None,
    final_validated_spl: str,
    raw_output: str | None = None,
    governed_source_mappings: list[str] | None = None,
) -> list[str]:
    reasons: list[str] = []
    if raw_output and _CODE_FENCE_RE.search(raw_output):
        reasons.append("code_block")
    haystack = " ".join(
        [
            payload.summary,
            " ".join(payload.what_it_does),
            " ".join(payload.mappings_assumptions),
            payload.expected_result,
        ]
    )
    if not payload.summary or not payload.what_it_does or not payload.expected_result:
        reasons.append("empty_content")
    if len(payload.what_it_does) < 2 or len(payload.what_it_does) > 4:
        reasons.append("what_it_does_count")
    if len(payload.mappings_assumptions) > 4:
        reasons.append("mappings_count")
    if _sentence_count(payload.summary) > 2:
        reasons.append("summary_too_long")
    if _sentence_count(payload.expected_result) > 1:
        reasons.append("expected_result_too_long")
    lowered = haystack.lower()
    for phrase in _GENERIC_FILLER:
        if phrase in lowered:
            reasons.append("generic_filler")
            break
    if _SPL_IN_TEXT_RE.search(haystack) or _SPL_IN_TEXT_RE.search(payload.summary):
        reasons.append("spl_in_synthesis")
    for phrase, code in _FORBIDDEN_SUBSTRINGS:
        if phrase in lowered:
            if code == "forbidden_result_count" and phrase == "returned " and "row" in lowered:
                if not re.search(r"returned\s+\d+", lowered):
                    continue
            reasons.append(code)
    spec = spec if isinstance(spec, dict) else {}
    spl = str(final_validated_spl or "")
    spl_lower = spl.lower()
    if "datamodel" in lowered and "datamodel" not in spl_lower:
        reasons.append("unsupported_datamodel")
    if "tstats" in lowered and "tstats" not in spl_lower:
        reasons.append("unsupported_tstats")
    if re.search(r"\bjoins?\b", lowered) and "| join" not in spl_lower:
        reasons.append("unsupported_join")
    reasons.extend(
        _unsupported_source_mentions(
            haystack,
            spl=spl,
            mappings=governed_source_mappings or [],
        )
    )
    reasons.extend(_numeric_mismatches(haystack, spec=spec, spl=spl))
    reasons.extend(_relationship_mismatches(lowered, spec=spec))
    return list(dict.fromkeys(reasons))


def parse_synthesis_json(raw_output: str) -> tuple[ReviewOnlySplSynthesisPayload | None, list[str]]:
    extracted = extract_first_json_object(raw_output)
    if not extracted.parsed_ok or not isinstance(extracted.payload, dict):
        return None, extracted.errors or ["json_parse_failed"]
    if "json_extracted_from_markdown_fence" in extracted.warnings:
        return None, ["code_block"]
    if any(key in extracted.payload for key in ("candidate_spl", "spl", "search_query", "normalized_spl")):
        return None, ["spl_in_synthesis"]
    try:
        payload = ReviewOnlySplSynthesisPayload.model_validate(extracted.payload)
    except ValidationError as exc:
        return None, [str(exc)]
    return payload, []


def synthesize_review_only_analyst_explanation(
    *,
    original_user_request: str,
    spec: dict[str, Any] | None,
    final_validated_spl: str,
    candidate_spl: dict[str, Any] | None = None,
    governed_source_mappings: list[str] | None = None,
    validated_assumptions: list[str] | None = None,
    llm_raw_output_provider: Callable[[], str] | None = None,
) -> ReviewOnlyAnalystSynthesis:
    mappings = list(governed_source_mappings or []) or governed_mappings_for_card(
        spec=spec,
        final_validated_spl=final_validated_spl,
        candidate_spl=candidate_spl,
    )
    fallback = deterministic_synthesis(
        spec=spec,
        final_validated_spl=final_validated_spl,
        candidate_spl=candidate_spl,
        governed_source_mappings=mappings,
    )
    payload, reasons, attempt = _attempt_llm_synthesis(
        original_user_request=original_user_request,
        spec=spec,
        final_validated_spl=final_validated_spl,
        governed_source_mappings=mappings,
        validated_assumptions=validated_assumptions or [],
        llm_raw_output_provider=llm_raw_output_provider,
    )
    fallback.llm_attempted = attempt.attempted
    fallback.llm_latency_ms = attempt.latency_ms
    if payload is None:
        fallback.dropped_reasons = reasons or ["llm_unavailable"]
        return fallback
    validation = validate_synthesis_payload(
        payload,
        spec=spec,
        final_validated_spl=final_validated_spl,
        governed_source_mappings=mappings,
    )
    if validation:
        fallback.dropped_reasons = validation
        return fallback
    return ReviewOnlyAnalystSynthesis(
        summary=payload.summary,
        what_it_does=payload.what_it_does,
        mappings_assumptions=payload.mappings_assumptions,
        expected_result=payload.expected_result,
        source=SYNTHESIS_SOURCE_LLM,
        llm_attempted=attempt.attempted,
        llm_latency_ms=attempt.latency_ms,
    )


def render_review_only_analyst_card_text(
    synthesis: ReviewOnlyAnalystSynthesis,
    final_validated_spl: str,
) -> str:
    lines = [REVIEW_ONLY_TITLE, "", synthesis.summary, "", "What this query does"]
    lines.extend(f"• {item}" for item in synthesis.what_it_does)
    lines.append("")
    spl = str(final_validated_spl or "").strip()
    if spl:
        lines.append(spl)
        lines.append("")
    if synthesis.mappings_assumptions:
        lines.append("Mappings / assumptions")
        lines.extend(f"• {item}" for item in synthesis.mappings_assumptions)
        lines.append("")
    if synthesis.expected_result:
        lines.append("Expected result")
        lines.append(synthesis.expected_result)
        lines.append("")
    lines.append(NO_EXECUTION_FOOTER)
    return "\n".join(lines).strip()


def attach_synthesis_trace(
    candidate_spl: dict[str, Any] | None,
    synthesis: ReviewOnlyAnalystSynthesis,
) -> None:
    if not isinstance(candidate_spl, dict):
        return
    trace = candidate_spl.get("utility_spl_draft_trace")
    if not isinstance(trace, dict):
        trace = {}
        candidate_spl["utility_spl_draft_trace"] = trace
    trace["analyst_synthesis_source"] = synthesis.source
    trace["analyst_synthesis"] = synthesis.public_payload()
    trace["analyst_synthesis_llm_attempted"] = bool(synthesis.llm_attempted)
    trace["analyst_synthesis_latency_ms"] = synthesis.llm_latency_ms
    if synthesis.dropped_reasons:
        trace["analyst_synthesis_dropped_reasons"] = list(synthesis.dropped_reasons)


@dataclass
class _SynthesisAttempt:
    """Observability record for the narration attempt (never analyst-visible)."""

    attempted: bool = False
    latency_ms: int | None = None


def _attempt_llm_synthesis(
    *,
    original_user_request: str,
    spec: dict[str, Any] | None,
    final_validated_spl: str,
    governed_source_mappings: list[str],
    validated_assumptions: list[str],
    llm_raw_output_provider: Callable[[], str] | None,
) -> tuple[ReviewOnlySplSynthesisPayload | None, list[str], _SynthesisAttempt]:
    attempt = _SynthesisAttempt()
    if llm_raw_output_provider is None and not getattr(settings, "ai_soc_llm_enabled", False):
        return None, ["llm_disabled"], attempt
    synthesis_input = build_synthesis_input(
        original_user_request=original_user_request,
        spec=spec,
        final_validated_spl=final_validated_spl,
        governed_source_mappings=governed_source_mappings,
        validated_assumptions=validated_assumptions,
    )
    user_prompt = "\n".join(
        [
            wrap_untrusted_source("user_query", synthesis_input["original_user_request"]),
            "SYNTHESIS_INPUT_JSON:",
            json.dumps({key: value for key, value in synthesis_input.items() if key != "original_user_request"}),
        ]
    )

    def _provider() -> str:
        if llm_raw_output_provider is not None:
            return llm_raw_output_provider()
        client = build_synthesis_client_from_settings()
        if client is None:
            raise LocalChatError("no_llm_endpoint_configured")
        with llm_call_purpose_scope(CALL_PURPOSE_SYNTHESIS_LAB):
            result = client.generate(
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=_SYNTHESIS_MAX_TOKENS,
                temperature=0.0,
                deadline=time.monotonic() + _SYNTHESIS_TIMEOUT_SECONDS,
                call_purpose=CALL_PURPOSE_SYNTHESIS_LAB,
            )
        return result.text

    attempt.attempted = True
    started = time.monotonic()
    try:
        call = run_sidecar_llm_with_timeout(
            _provider,
            timeout_seconds=_SYNTHESIS_TIMEOUT_SECONDS,
            call_purpose=CALL_PURPOSE_SYNTHESIS_LAB,
            wrapper_kind="review_only_spl_synthesis",
        )
    except LocalChatError as exc:
        attempt.latency_ms = int((time.monotonic() - started) * 1000)
        reasons = [exc.code or "llm_error"]
        _capture_synthesis_interaction(
            user_prompt=user_prompt,
            raw_text=None,
            parsed_payload=None,
            reject_reasons=reasons,
            transport_status="failed",
            parse_status="not_run",
            latency_ms=attempt.latency_ms,
        )
        return None, reasons, attempt
    attempt.latency_ms = int((time.monotonic() - started) * 1000)
    if call.timed_out:
        _capture_synthesis_interaction(
            user_prompt=user_prompt,
            raw_text=call.raw_output,
            parsed_payload=None,
            reject_reasons=["llm_timed_out"],
            transport_status="timed_out",
            parse_status="not_run",
            latency_ms=attempt.latency_ms,
        )
        return None, ["llm_timed_out"], attempt
    if not call.raw_output:
        reasons = list(call.notes) or ["empty_completion"]
        _capture_synthesis_interaction(
            user_prompt=user_prompt,
            raw_text=call.raw_output,
            parsed_payload=None,
            reject_reasons=reasons,
            transport_status="failed",
            parse_status="failed",
            latency_ms=attempt.latency_ms,
        )
        return None, reasons, attempt
    payload, errors = parse_synthesis_json(call.raw_output)
    if payload is None:
        _capture_synthesis_interaction(
            user_prompt=user_prompt,
            raw_text=call.raw_output,
            parsed_payload=None,
            reject_reasons=errors,
            transport_status="completed",
            parse_status="failed",
            latency_ms=attempt.latency_ms,
        )
        return None, errors, attempt
    extra = validate_synthesis_payload(
        payload,
        spec=spec,
        final_validated_spl=final_validated_spl,
        raw_output=call.raw_output,
        governed_source_mappings=governed_source_mappings,
    )
    if extra:
        _capture_synthesis_interaction(
            user_prompt=user_prompt,
            raw_text=call.raw_output,
            parsed_payload=payload.model_dump() if hasattr(payload, "model_dump") else None,
            reject_reasons=extra,
            transport_status="completed",
            parse_status="parsed",
            schema_status="valid",
            grounding_status="failed",
            latency_ms=attempt.latency_ms,
        )
        return None, extra, attempt
    _capture_synthesis_interaction(
        user_prompt=user_prompt,
        raw_text=call.raw_output,
        parsed_payload=payload.model_dump() if hasattr(payload, "model_dump") else None,
        reject_reasons=[],
        transport_status="completed",
        parse_status="parsed",
        schema_status="valid",
        grounding_status="passed",
        accepted=True,
        contributed_to_final_output=True,
        fallback_selected=False,
        latency_ms=attempt.latency_ms,
    )
    return payload, [], attempt


def _capture_synthesis_interaction(
    *,
    user_prompt: str,
    raw_text: str | None,
    parsed_payload: Any,
    reject_reasons: list[str],
    transport_status: str,
    parse_status: str,
    schema_status: str | None = None,
    grounding_status: str | None = None,
    accepted: bool = False,
    contributed_to_final_output: bool = False,
    fallback_selected: bool = True,
    latency_ms: int | None = None,
) -> None:
    try:
        capture_llm_interaction(
            role="review_only_spl_synthesis",
            stage="synthesis",
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=_SYNTHESIS_MAX_TOKENS,
            raw_text=raw_text,
            parsed_payload=parsed_payload,
            transport_status=transport_status,
            parse_status=parse_status,
            schema_status=schema_status,
            grounding_status=grounding_status,
            reject_reasons=reject_reasons,
            accepted=accepted,
            contributed_to_final_output=contributed_to_final_output,
            fallback_selected=fallback_selected,
            fallback_reason=reject_reasons[0] if reject_reasons else None,
            latency_ms=latency_ms,
        )
    except Exception:  # noqa: BLE001 - observability must never fail synthesis
        return


def _first(value: Any) -> str:
    if isinstance(value, list) and value:
        return str(value[0]).strip()
    return str(value or "").strip()


def _window_label(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    match = re.search(r"-(\d+[smhd])", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return text


def _human_outputs(outputs: list[str]) -> list[str]:
    aliases = {
        "src_ip": "source IP",
        "source_ip": "source IP",
        "failure_count": "failed-login count",
        "first_failure_time": "first failure time",
        "success_time": "successful-login time",
        "destination_host": "destination host",
        "distinct_new_host_count": "distinct new-host count",
        "connection_count": "connection count",
        "first_seen": "first seen",
        "event_count": "event count",
        "command_line": "command line",
    }
    return [aliases.get(item, item.replace("_", " ")) for item in outputs]


def _sentence_count(text: str) -> int:
    stripped = str(text or "").strip()
    if not stripped:
        return 0
    parts = [item for item in _SENTENCE_RE.split(stripped) if item.strip()]
    return max(1, len(parts)) if stripped else 0


def _clip_sentences(text: str, limit: int) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", stripped)
    return " ".join(parts[:limit]).strip()


def _unsupported_source_mentions(haystack: str, *, spl: str, mappings: list[str]) -> list[str]:
    allowed = {token.lower() for token in re.findall(r"[A-Za-z0-9:_<>-]+", spl)}
    for item in mappings:
        allowed.update(token.lower() for token in re.findall(r"[A-Za-z0-9:_<>-]+", item))
    allowed.update({"your_index", "<your_index>", "index"})
    reasons: list[str] = []
    for match in _INDEX_MENTION_RE.finditer(haystack):
        token = match.group(1).strip("`\"'")
        if token.lower() not in allowed and token.lower() not in {"the", "an", "a"}:
            reasons.append("unsupported_index")
            break
    for match in _SOURCETYPE_MENTION_RE.finditer(haystack):
        token = match.group(1).strip("`\"'")
        if token.lower() not in allowed:
            reasons.append("unsupported_sourcetype")
            break
    return reasons


def _numeric_mismatches(haystack: str, *, spec: dict[str, Any], spl: str) -> list[str]:
    allowed = _allowed_numbers(spec, spl)
    mentioned: set[int] = set()
    for match in _DURATION_RE.finditer(haystack):
        mentioned.add(int(match.group(1)))
    # Threshold-style "more than 20" without a unit.
    for match in re.finditer(r"\b(?:more than|greater than|over|at least|>)\s+(\d+)\b", haystack, re.IGNORECASE):
        mentioned.add(int(match.group(1)))
    unknown = sorted(value for value in mentioned if value not in allowed)
    if unknown:
        return ["numeric_constraint_mismatch"]
    return []


def _allowed_numbers(spec: dict[str, Any], spl: str) -> set[int]:
    blobs = [
        str(spec.get("observation_window") or ""),
        str(spec.get("baseline_window") or ""),
        str(spec.get("search_horizon") or ""),
        str(spec.get("temporal_grain") or ""),
        str(spec.get("sequence_max_gap") or ""),
        str((spec.get("analytical_window") or {}).get("size") or "")
        if isinstance(spec.get("analytical_window"), dict)
        else "",
        str(spec.get("explicit_threshold_value") or ""),
        spl,
    ]
    allowed: set[int] = {int(item) for item in re.findall(r"\d+", " ".join(blobs)) if item.isdigit()}
    gap = str(spec.get("sequence_max_gap") or "")
    if gap in {"10m", "10 minutes"}:
        allowed.add(600)
        allowed.add(10)
    if gap in {"15m", "15 minutes"}:
        allowed.add(900)
    window = ""
    if isinstance(spec.get("analytical_window"), dict):
        window = str(spec["analytical_window"].get("size") or "")
    if window in {"15m", "15 minutes"}:
        allowed.add(15)
    allowed.update({1, 2})  # one-hour windows / 1-2 sentence summaries
    return allowed


def _relationship_mismatches(lowered: str, *, spec: dict[str, Any]) -> list[str]:
    shape = str(spec.get("analysis_shape") or "")
    roles = spec.get("entity_roles") if isinstance(spec.get("entity_roles"), dict) else {}
    subject = {_first(roles.get("subject")).lower(), *[str(item).lower() for item in (roles.get("subject") or [])]}
    target = {_first(roles.get("target")).lower(), *[str(item).lower() for item in (roles.get("target") or [])]}
    reasons: list[str] = []
    if shape == "first_seen" and ("host" in target or "dest" in "".join(target)):
        if re.search(r"same source ip|same src_ip|compares hosts for the same source", lowered):
            reasons.append("entity_relationship_mismatch")
        if "regex" in lowered:
            reasons.append("entity_relationship_mismatch")
    if shape == "first_seen" and ("domain" in target or "dest_nt_domain" in target or "query" in target):
        if re.search(r"same user|same account", lowered):
            reasons.append("entity_relationship_mismatch")
        if "regex" in lowered:
            reasons.append("entity_relationship_mismatch")
    if shape == "parent_child":
        if re.search(r"commands? containing|appearing in command|command line contain", lowered):
            reasons.append("entity_relationship_mismatch")
    if shape == "sequence":
        if re.search(r"same destination host as (?:the )?correlation|same host for failures and success", lowered):
            reasons.append("entity_relationship_mismatch")
    _ = subject  # retained for future subject-specific checks
    return reasons
