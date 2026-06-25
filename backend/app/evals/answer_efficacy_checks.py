"""Shared answer-quality / data-efficacy checks for live probes and batch evals."""

from __future__ import annotations

import re
from typing import Any

_PRIORITY_PREFIX = re.compile(r"^P[1-4]\s*[—\-–:]\s*", re.I)
_WHITESPACE = re.compile(r"\s+")


def normalize_action_text(action: str) -> str:
    """Collapse priority labels and whitespace for duplicate detection."""
    text = _PRIORITY_PREFIX.sub("", str(action or "").strip().lower())
    return _WHITESPACE.sub(" ", text)


def analyst_visible_text(payload: dict[str, Any]) -> str:
    """Merge analyst-visible prose used for marker and substance checks."""
    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    parts: list[str] = []
    for key in ("direct_answer_summary", "summary", "headline", "analyst_summary"):
        val = analyst.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    msg = payload.get("message")
    if isinstance(msg, str) and msg.strip():
        parts.append(msg.strip())
    for key in ("review_notice", "evidence_summary", "splunk_status_line"):
        val = analyst.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    for key in (
        "hypotheses",
        "recommended_actions",
        "analyst_checklist",
        "investigation_steps",
        "triage_checklist",
        "evidence_checklist",
        "limitations",
        "missing_evidence",
        "required_evidence",
    ):
        values = analyst.get(key)
        if isinstance(values, list):
            parts.extend(str(item).strip() for item in values if str(item).strip())
    return "\n".join(parts)


def analyst_card_text(payload: dict[str, Any]) -> str:
    """Analyst-visible prose from the structured card only (excludes ``message``).

    Used for per-surface duplicate-marker counting, where the card and the markdown
    ``message`` fallback are alternate render surfaces rather than additive content.
    """
    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    parts: list[str] = []
    # ``one_sentence_finding`` is intentionally omitted: the frontend renders it only as
    # a fallback for ``direct_answer_summary`` (never both), so counting it would
    # double-count a single rendered body for duplicate-marker detection.
    for key in ("direct_answer_summary", "summary", "headline", "analyst_summary"):
        val = analyst.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    for key in ("review_notice", "evidence_summary", "splunk_status_line"):
        val = analyst.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    for key in (
        "hypotheses",
        "recommended_actions",
        "analyst_checklist",
        "investigation_steps",
        "triage_checklist",
        "evidence_checklist",
        "limitations",
        "missing_evidence",
        "required_evidence",
    ):
        values = analyst.get(key)
        if isinstance(values, list):
            parts.extend(str(item).strip() for item in values if str(item).strip())
    return "\n".join(parts)


def extract_response_observed(payload: dict[str, Any], *, query: str) -> dict[str, Any]:
    """Normalize /chat payload fields for efficacy scoring."""
    from app.chat.signal_class_guidance import classify_signal_class

    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    contract = payload.get("answer_contract") if isinstance(payload.get("answer_contract"), dict) else {}
    trace = payload.get("control_plane_trace") if isinstance(payload.get("control_plane_trace"), dict) else {}
    qti = payload.get("query_to_intent") if isinstance(payload.get("query_to_intent"), dict) else {}
    mappings = qti.get("candidate_mappings") if isinstance(qti.get("candidate_mappings"), dict) else {}
    composer = trace.get("llm_composer") if isinstance(trace.get("llm_composer"), dict) else {}

    recommended = analyst.get("recommended_actions") or contract.get("recommended_actions") or []
    steps = analyst.get("investigation_steps") or contract.get("investigation_steps") or []
    checklist = (
        analyst.get("analyst_checklist")
        or contract.get("analyst_checklist_safe")
        or analyst.get("investigation_checklist")
        or []
    )
    if not isinstance(recommended, list):
        recommended = []
    if not isinstance(steps, list):
        steps = []
    if not isinstance(checklist, list):
        checklist = []

    visible = analyst_visible_text(payload)
    hypotheses = analyst.get("hypotheses") or []
    hyp_text = visible.lower()
    if isinstance(hypotheses, list):
        hyp_text = f"{hyp_text}\n" + "\n".join(str(h) for h in hypotheses).lower()

    norm_actions = [normalize_action_text(a) for a in recommended if str(a).strip()]
    norm_steps = [normalize_action_text(s) for s in steps if str(s).strip()]

    return {
        "selected_skill": payload.get("selected_skill") or (payload.get("routing") or {}).get("skill"),
        "answer_mode": contract.get("answer_mode") or payload.get("answer_mode"),
        "match_path": mappings.get("match_path"),
        "signal_class": classify_signal_class(query),
        "message": visible,
        "message_len": len(visible.strip()),
        "recommended_actions": recommended,
        "investigation_steps": steps,
        "analyst_checklist": checklist,
        "action_count": len(recommended),
        "step_count": len(steps),
        "checklist_count": len(checklist),
        "duplicate_actions": len(norm_actions) - len(set(norm_actions)),
        "action_step_overlap": len(set(norm_actions) & set(norm_steps)),
        "hypothesis_text": hyp_text,
        "llm_composer": composer,
        "composer_attempted": composer.get("composer_attempted"),
        "llm_composer_used": composer.get("llm_composer_used"),
        "llm_composer_skipped_reason": composer.get("llm_composer_skipped_reason"),
        "composer_is_enabled": composer.get("composer_is_enabled"),
        "execution_status": str((payload.get("execution") or {}).get("status") or ""),
    }


def _marker_hits(text: str, markers: tuple[str, ...] | list[str]) -> list[str]:
    lowered = text.lower()
    return [marker for marker in markers if marker.lower() in lowered]


def evaluate_probe_expectations(
    *,
    query: str,
    payload: dict[str, Any],
    expect: dict[str, Any] | None,
    synthesis_enabled: bool = False,
) -> list[str]:
    """Return violation codes for a single probe row (empty = pass)."""
    if not expect:
        return []
    observed = extract_response_observed(payload, query=query)
    violations: list[str] = []
    visible = observed["message"]
    hyp_text = str(observed["hypothesis_text"])

    expected_skill = expect.get("selected_skill")
    if expected_skill and observed["selected_skill"] != expected_skill:
        violations.append(f"skill_mismatch:expected={expected_skill}:actual={observed['selected_skill']}")

    expected_paths = expect.get("match_path")
    if expected_paths:
        allowed = expected_paths if isinstance(expected_paths, list) else [expected_paths]
        if observed["match_path"] not in allowed:
            violations.append(
                f"match_path_mismatch:expected={allowed}:actual={observed['match_path']}"
            )

    expected_signal = expect.get("signal_class")
    if expected_signal and observed["signal_class"] != expected_signal:
        violations.append(
            f"signal_class_mismatch:expected={expected_signal}:actual={observed['signal_class']}"
        )

    for forbidden in expect.get("forbid_signal_classes") or []:
        if observed["signal_class"] == forbidden:
            violations.append(f"forbidden_signal_class:{forbidden}")

    min_len = int(expect.get("min_message_len") or 0)
    if min_len and observed["message_len"] < min_len:
        violations.append(f"thin_message:{observed['message_len']}<{min_len}")

    min_checklist = int(expect.get("min_checklist_items") or 0)
    min_actions = int(expect.get("min_recommended_actions") or 0)
    if min_checklist and observed["checklist_count"] < min_checklist and observed["action_count"] < min_checklist:
        if observed["message_len"] < max(min_len or 280, 280):
            violations.append(f"thin_guided_envelope:checklist={observed['checklist_count']}")

    if min_actions and observed["action_count"] < min_actions:
        violations.append(f"too_few_actions:{observed['action_count']}<{min_actions}")

    max_actions = expect.get("max_recommended_actions")
    if max_actions is not None and observed["action_count"] > int(max_actions):
        violations.append(f"excessive_actions:{observed['action_count']}>{max_actions}")

    if expect.get("unique_action_prefixes") and observed["duplicate_actions"] > 0:
        violations.append(f"duplicate_recommended_actions:{observed['duplicate_actions']}")

    if expect.get("no_action_step_overlap") and observed["action_step_overlap"] > 0:
        violations.append(f"action_step_overlap:{observed['action_step_overlap']}")

    forbidden_hyp = tuple(expect.get("forbid_hypothesis_markers") or ())
    hits = _marker_hits(hyp_text, forbidden_hyp)
    if hits:
        violations.append(f"wrong_hypothesis_markers:{','.join(hits)}")

    required_hyp = tuple(expect.get("require_hypothesis_markers") or ())
    if required_hyp and not _marker_hits(hyp_text, required_hyp):
        violations.append(f"missing_hypothesis_markers:{','.join(required_hyp)}")

    required_msg = tuple(expect.get("require_message_markers") or ())
    if required_msg and not _marker_hits(visible, required_msg):
        violations.append(f"missing_message_markers:{','.join(required_msg)}")

    if expect.get("require_out_of_catalog_notice"):
        markers = ("out-of-catalog", "out of catalog", "unverified", "review-only", "validate")
        if not _marker_hits(visible, markers):
            violations.append("out_of_catalog_notice_missing")

    composer_expect = expect.get("composer")
    if isinstance(composer_expect, dict):
        forbid_skip = composer_expect.get("forbid_skip_reason")
        if synthesis_enabled and forbid_skip:
            skip = observed.get("llm_composer_skipped_reason")
            if skip == forbid_skip:
                violations.append(f"composer_skip:{skip}")
        if synthesis_enabled and composer_expect.get("require_attempted"):
            if not observed.get("composer_attempted"):
                violations.append("composer_not_attempted")

    if expect.get("forbid_execution_claim"):
        lowered = visible.lower()
        negated_execution = (
            "not executed" in lowered
            or "no live query was executed" in lowered
            or "no mcp execution was run" in lowered
        )
        if observed["execution_status"] == "executed":
            violations.append("unexpected_execution")
        elif re.search(r"\b(executed|returned \d+ rows)\b", lowered) and not negated_execution:
            violations.append("possible_execution_overclaim")

    return violations


def evaluate_universal_efficacy(
    *,
    query: str,
    payload: dict[str, Any],
    category: str | None = None,
    synthesis_enabled: bool = False,
) -> list[str]:
    """Cross-cutting efficacy checks applied to any live-efficacy row."""
    observed = extract_response_observed(payload, query=query)
    violations: list[str] = []
    visible = observed["message"]
    lowered = visible.lower()

    if observed["duplicate_actions"] > 0:
        violations.append(f"duplicate_recommended_actions:{observed['duplicate_actions']}")

    if observed["action_count"] > 10:
        violations.append(f"excessive_recommended_actions:{observed['action_count']}")

    if observed["action_step_overlap"] > 0:
        violations.append(f"action_step_overlap:{observed['action_step_overlap']}")

    signal_class = observed["signal_class"]
    if signal_class not in {"unknown", "network_beacon"} and (
        "no specialised ot family" in lowered or "firewall, dns, proxy, and endpoint telemetry" in lowered
    ):
        violations.append(f"recognised_signal_returned_generic:{signal_class}")

    if observed["selected_skill"] == "guided_investigation" and observed["message_len"] < 180:
        if category not in {"boundary"}:
            violations.append(f"thin_guided_message:{observed['message_len']}")

    if synthesis_enabled and observed.get("composer_is_enabled"):
        skip = observed.get("llm_composer_skipped_reason")
        if skip == "insufficient_deadline_reserve":
            violations.append("composer_budget_false_skip")

    violations.extend(_coe_stop_condition_violations(payload, visible))
    return violations


_RUN_CONTRACT_REQUIRED_FIELDS = (
    "execution_status",
    "collected_evidence_count",
    "source_evidence_available",
    "allow_live_result_language",
    "allow_results_table",
    "effective_hil_required",
)
_ROUTING_REQUIRED_FIELDS = (
    "canonical_skill",
    "legacy_authoritative",
    "authority_holder",
)


def _coe_stop_condition_violations(payload: dict[str, Any], visible: str) -> list[str]:
    violations: list[str] = []
    contract = payload.get("run_contract") if isinstance(payload.get("run_contract"), dict) else None
    if contract is None:
        return ["run_contract_missing"]

    routing = contract.get("routing") if isinstance(contract.get("routing"), dict) else {}
    for field in _RUN_CONTRACT_REQUIRED_FIELDS:
        if field not in contract:
            violations.append(f"run_contract_field_missing:{field}")
    for field in _ROUTING_REQUIRED_FIELDS:
        if field not in routing:
            violations.append(f"run_contract_field_missing:routing.{field}")
    if "legacy_skill" not in routing:
        violations.append("run_contract_field_missing:routing.legacy_skill")

    execution_status = str(contract.get("execution_status") or "")
    collected = int(contract.get("collected_evidence_count") or 0)
    lowered = visible.lower()
    if "live-backed" in lowered and (execution_status != "executed" or collected <= 0):
        violations.append("live_backed_without_execution")

    analyst = payload.get("analyst_response") if isinstance(payload.get("analyst_response"), dict) else {}
    table = analyst.get("splunk_results_table") if isinstance(analyst.get("splunk_results_table"), list) else []
    if table and contract.get("allow_results_table") is False:
        violations.append("results_table_not_allowed")

    severity = str(analyst.get("severity_label") or "")
    if not severity or "not assigned" in severity.lower():
        actions = analyst.get("recommended_actions") if isinstance(analyst.get("recommended_actions"), list) else []
        for action in actions:
            if _PRIORITY_PREFIX.match(str(action or "")):
                violations.append("priority_prefix_without_severity")
                break

    route_authority = payload.get("route_authority") if isinstance(payload.get("route_authority"), dict) else {}
    displayed_holder = route_authority.get("authority_holder")
    contract_holder = routing.get("authority_holder")
    if displayed_holder and contract_holder and displayed_holder != contract_holder:
        violations.append("route_authority_holder_contradiction")
    shadow = payload.get("route_plan_shadow") if isinstance(payload.get("route_plan_shadow"), dict) else {}
    compare = shadow.get("route_authority_compare") if isinstance(shadow.get("route_authority_compare"), dict) else {}
    compare_holder = compare.get("authority_holder")
    if compare_holder and contract_holder and compare_holder != contract_holder:
        violations.append("route_authority_holder_contradiction")

    # The analyst card and the markdown ``message`` are mutually exclusive render
    # surfaces (card when present, else message). Count duplicate-section markers per
    # surface (max) rather than summed, so a single body mirrored into both surfaces is
    # not mistaken for a duplicate while a section repeated within one surface still is.
    card_lower = analyst_card_text(payload).lower()
    message_lower = str(payload.get("message") or "").lower()

    def _surface_marker_count(marker: str) -> int:
        return max(_count_marker(card_lower, marker), _count_marker(message_lower, marker))

    if _surface_marker_count("lab-only draft spl preview") > 1:
        violations.append("duplicate_spl_warning")
    if _surface_marker_count("soc review checklist") > 1:
        violations.append("duplicate_soc_review_checklist")
    return violations


def _count_marker(text: str, marker: str) -> int:
    return text.count(marker.lower())
