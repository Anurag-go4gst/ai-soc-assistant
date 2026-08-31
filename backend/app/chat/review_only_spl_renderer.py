"""Dedicated renderer for review-only SPL draft answers.

When the RunContract says the canonical skill is ``spl_generation`` with a renderable
candidate that was not executed, the visible answer is composed by one renderer that
owns section ordering and labels. This replaces the generic multi-producer composition
(title / review-type banner / investigation-plan / analyst-workflow) which otherwise
prepends competing headings ahead of the review-only SPL answer shape.

This is section-level ownership, not string scrubbing: the renderer emits exactly the
sections it wants, in a fixed order, and the caller suppresses the competing card
producers so they cannot re-introduce duplicate/competing sections.

Governance is unchanged here — severity, execution status, HIL, MCP posture, source
evidence, and SPL validation are all read from the already-decided RunContract /
analyst response. The renderer only shapes the visible text.
"""

from __future__ import annotations

import re
from typing import Any

from app.chat.t2_review_checklist import (
    build_t2_review_checklist,
    is_t2_spl_native_candidate,
    t2_card_overlays,
    t2_spl_native_block,
)
from app.chat.signal_class_guidance import (
    format_signal_class_review_supplement,
    resolve_signal_class_review_supplement,
)
from app.spl.binding_semantics import format_profile_binding_line

_MAIN_TITLE = "Review-only SPL draft — no live query was executed"
_SEVERITY_NOT_ASSIGNED = "Not assigned from this question alone"
_EXECUTION_LINE = "Execution: Not executed"
_REVIEW_LINE = "Review: HIL/SOC review required before any future execution path"
_ANALYST_VALIDATION_LINE = "Requires analyst validation before MCP execution"
_REVIEW_ONLY_NOTICE = (
    "This is a lab-only draft SPL preview. It is not governed, not approved, and not executed."
)
_CHECKLIST_HEADER = "SOC review checklist before execution:"
_HOW_PRODUCED = "How this answer was produced: review-only / no live execution"

_PRIORITY_PREFIX = re.compile(r"^P[1-4]\s*[—\-–:]\s*", re.IGNORECASE)

# Generic fallback checklist for review-only SPL drafts without a family-specific one.
_GENERIC_CHECKLIST: tuple[str, ...] = (
    "Confirm the index, sourcetype, and field placeholders against your source profile.",
    "Identify the source and destination assets relevant to the question.",
    "Review the draft SPL filters, time window, and result limit before any execution.",
    "Compare any matches with approved change or maintenance activity.",
    "Escalate only after required evidence is collected and documented.",
    "Do not declare compromise from this draft alone.",
)

_FIREWALL_SCOPE = (
    "Scope: IT-to-OT firewall boundary review for external or remote-access-style "
    "connections to substation/OT networks."
)


def is_review_only_spl_answer(run_contract: Any) -> bool:
    """True when the answer is a renderable, non-executed SPL-generation draft.

    Mirrors the agreed trigger:
        run_contract.routing.canonical_skill == "spl_generation"
        and run_contract.spl_candidate_renderable is True
        and run_contract.execution_status != "executed"
    """
    if run_contract is None:
        return False
    routing = getattr(run_contract, "routing", None)
    canonical_skill = getattr(routing, "canonical_skill", None)
    return (
        canonical_skill == "spl_generation"
        and getattr(run_contract, "spl_candidate_renderable", False) is True
        and getattr(run_contract, "execution_status", "") != "executed"
    )


def _strip_priority_prefix(text: str) -> str:
    return _PRIORITY_PREFIX.sub("", str(text or "")).strip()


def _severity_text(analyst_response: Any) -> str:
    label = _strip_priority_prefix(str(getattr(analyst_response, "severity_label", "") or ""))
    if not label or "not assigned" in label.lower():
        return _SEVERITY_NOT_ASSIGNED
    return label


def _scope_line(
    analyst_response: Any,
    *,
    t2_source_profile: str | None = None,
    draft_preview: dict[str, Any] | None = None,
) -> str:
    """Family-aware scope line; only assert the IT-to-OT framing on a strong match.

    A T1 SPL-native (T2) draft owns its own source profile (e.g. scada_perf), so a
    co-matched IT-to-OT use case's scenario label must not drive the scope. For T2
    the scope is profile-aware and never the firewall/boundary framing.
    """
    if isinstance(draft_preview, dict):
        scope_notice = str(draft_preview.get("scope_notice") or "").strip()
        family = str(draft_preview.get("detection_family") or "")
        if family in {"esp_it_to_ot_connection", "firewall_vendor_vpn_jump"}:
            return _FIREWALL_SCOPE
        if draft_preview.get("metadata_source") == "binding_derived" and scope_notice:
            return scope_notice if scope_notice.startswith("Scope:") else f"Scope: {scope_notice}"
        review_type = str(draft_preview.get("review_type_display") or "").strip()
        if draft_preview.get("governed_template_missing") and review_type:
            return (
                "Scope: T1 SPL-generation review — lab draft only (no governed template bound); "
                f"{review_type}. Nothing was executed."
            )
    if t2_source_profile:
        return (
            f"Scope: Review-only SPL draft for source profile '{t2_source_profile}'; "
            "validate fields and time window before review. Nothing was executed."
        )
    haystack = " ".join(
        str(getattr(analyst_response, field, "") or "")
        for field in ("finding_title", "scenario_label")
    ).lower()
    if ("it-to-ot" in haystack or "it to ot" in haystack) or (
        "firewall" in haystack and ("ot" in haystack or "boundary" in haystack)
    ):
        return _FIREWALL_SCOPE
    return (
        "Scope: Review-only SPL draft for the requested live-data query; validate the "
        "source profile before review. No governed template is bound and nothing was executed."
    )


def _checklist_items(
    analyst_response: Any,
    draft_preview: dict[str, Any] | None,
    *,
    candidate_spl: dict[str, Any] | None = None,
) -> list[str]:
    if is_t2_spl_native_candidate(candidate_spl):
        return build_t2_review_checklist(t2_spl_native_block(candidate_spl))
    for source in (
        getattr(analyst_response, "analyst_checklist", None),
        (draft_preview or {}).get("investigation_checklist") if isinstance(draft_preview, dict) else None,
    ):
        items = [_strip_priority_prefix(str(item)) for item in (source or []) if str(item).strip()]
        if items:
            return items
    return list(_GENERIC_CHECKLIST)


def _draft_spl_text(
    analyst_response: Any,
    draft_preview: dict[str, Any] | None,
    *,
    candidate_spl: dict[str, Any] | None = None,
) -> str:
    if _is_concise_spl_utility(draft_preview, candidate_spl):
        utility_spl = str((candidate_spl or {}).get("candidate_spl") or "").strip()
        if utility_spl:
            return utility_spl
    if (
        isinstance(candidate_spl, dict)
        and candidate_spl.get("generation_mode") == "t2_spl_native_review"
    ):
        t2_spl = str(candidate_spl.get("candidate_spl") or "").strip()
        if t2_spl:
            return t2_spl
    code = str(getattr(analyst_response, "draft_spl_code", "") or "").strip()
    if code:
        return code
    if isinstance(draft_preview, dict):
        spl = str(draft_preview.get("draft_spl") or "").strip()
        if spl:
            return spl
    return ""


def _assumptions(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    return [str(item).strip() for item in (draft_preview.get("assumptions") or []) if str(item).strip()]


def _source_profile_used(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    rows: list[str] = []
    seen: set[tuple[str, str]] = set()
    for key in ("source_profile_bindings_applied", "source_profile_bindings"):
        for item in draft_preview.get(key) or []:
            if not isinstance(item, dict):
                continue
            slot = str(item.get("slot") or item.get("profile_key") or "").strip()
            value = str(item.get("value") or "").strip()
            if not slot or not value:
                continue
            identity = (slot, value)
            if identity in seen:
                continue
            seen.add(identity)
            source = str(item.get("source") or "source_profile").strip()
            rows.append(format_profile_binding_line(item))
    return rows


def _missing_bindings(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    rows: list[str] = []
    seen: set[tuple[str, str]] = set()
    for key in ("source_profile_bindings_missing", "unbound_constraints"):
        for item in draft_preview.get(key) or []:
            if not isinstance(item, dict):
                continue
            slot = str(item.get("slot") or item.get("profile_key") or "").strip()
            reason = str(item.get("reason") or "missing_binding").strip()
            if not slot:
                continue
            identity = (slot, reason)
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(f"- {slot}: {reason}")
    return rows


def _source_family_draft_sections(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    rendered: list[str] = []
    for section in draft_preview.get("source_family_draft_sections") or []:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        if not title:
            continue
        status = str(section.get("status") or "review_only").strip()
        rendered.append(f"{title} ({status}):")
        draft_spl = str(section.get("draft_spl") or "").strip()
        if draft_spl:
            rendered.append(draft_spl)
            continue
        missing = [str(item) for item in (section.get("missing_slots") or []) if str(item).strip()]
        if missing:
            rendered.append(f"Missing bindings: {', '.join(missing)}")
            continue
        references = [str(item) for item in (section.get("references") or []) if str(item).strip()]
        if references:
            rendered.append(f"References: {', '.join(references)}")
    return rendered




def _required_event_fields(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    fields = draft_preview.get("required_event_fields") or draft_preview.get("required_log_fields") or []
    return [str(item).strip() for item in fields if str(item).strip()]


def _required_profile_bindings(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    rows: list[str] = []
    bindings = draft_preview.get("required_source_profile_bindings")
    if isinstance(bindings, list) and bindings:
        for item in bindings:
            if isinstance(item, dict):
                rows.append(format_profile_binding_line(item))
        return rows
    for slot in draft_preview.get("required_source_profile_fields") or []:
        slot_text = str(slot).strip()
        if slot_text:
            rows.append(f"- {slot_text}")
    return rows



def _resolved_scope_bindings(draft_preview: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft_preview, dict):
        return []
    rows: list[str] = []
    for item in draft_preview.get("required_source_profile_bindings") or []:
        if not isinstance(item, dict) or not item.get("resolution"):
            continue
        rows.append(format_profile_binding_line(item))
    return rows



def _spl_artifact_handoff_trace_lines(handoff: dict[str, Any] | None) -> list[str]:
    if not isinstance(handoff, dict) or not handoff:
        return []
    lines = ["SPL artifact status (trace only):"]
    for key in (
        "spl_artifact_status",
        "spl_artifact_source",
        "candidate_provider_reason",
        "governed_template_bound",
        "t2_native_shape",
        "lab_preview_used",
        "llm_failover_used",
        "validator_status",
        "review_only",
        "must_not_execute_reason",
    ):
        value = handoff.get(key)
        if value is not None and value != "":
            lines.append(f"- {key}: {value}")
    return lines

SPL_AUTHORING_ABSTENTION_MESSAGE = (
    "Draft not produced because the generated query could not be compiled "
    "faithfully from the requested semantics. No query was executed."
)

_LOSS_ANALYST_REASONS: tuple[tuple[str, str], ...] = (
    ("output_missing:event_count", "the generated query omitted the requested event count"),
    ("output_missing:connection_count", "the generated query omitted the requested connection count"),
    ("output_missing:failure_count", "the generated query omitted the requested failed-login count"),
    ("output_missing:first_failure_time", "the generated query omitted the requested first-failure time"),
    ("output_missing:success_time", "the generated query omitted the requested successful-login time"),
    ("baseline_data_unreachable", "the generated query did not include the requested preceding baseline period"),
    ("baseline_window_missing", "the generated query did not include the requested preceding baseline period"),
    ("same_source_correlation_missing", "the generated query did not preserve the requested same-source-IP sequence"),
    ("sequence_ordering_missing", "the generated query did not preserve the requested event sequence"),
    ("sequence_gap_missing", "the generated query did not preserve the requested sequence timing"),
    ("parent_child_relation_missing", "the generated query did not preserve the requested parent-to-child process relationship"),
    ("unresolved_field_mapping", "no approved mapping exists for a requested organization-specific field"),
    ("unresolved_required_fields", "no approved mapping exists for a requested organization-specific field"),
)


def analyst_authoring_abstention_message(candidate_spl: dict[str, Any] | None = None) -> str:
    """Analyst-facing abstention copy — useful, no internal stage codes."""
    trace = (candidate_spl or {}).get("utility_spl_draft_trace") if isinstance(candidate_spl, dict) else None
    trace = trace if isinstance(trace, dict) else {}
    losses = [str(item) for item in (trace.get("lost_semantics") or [])]
    for prefix, reason in _LOSS_ANALYST_REASONS:
        if any(item == prefix or item.startswith(prefix) for item in losses):
            return f"Draft not produced because {reason}. No query was executed."
    degrade = str((trace.get("semantic_intent_spec") or {}).get("degrade_reason") or "")
    if "unresolved" in degrade:
        return (
            "Draft not produced because no approved mapping exists for a requested "
            "organization-specific field. No query was executed."
        )
    return SPL_AUTHORING_ABSTENTION_MESSAGE
_UNIVERSAL_UTILITY_TITLE = "Review-only universal SPL draft. This was not executed."
_UNIVERSAL_UTILITY_FAMILY = "universal_timestamp_spl"
_USER_BOUND_UTILITY_FAMILY = "user_bound_spl_authoring"


def _is_universal_spl_utility(
    draft_preview: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
) -> bool:
    """True only for the universal/template-free SPL authoring family.

    Strictly gated so analytics, q046, T2 SCADA/Cisco/Winevent, and investigation
    answers keep the full governance-framed SOC rendering.
    """
    dp = draft_preview if isinstance(draft_preview, dict) else {}
    cs = candidate_spl if isinstance(candidate_spl, dict) else {}
    return (
        dp.get("detection_family") == _UNIVERSAL_UTILITY_FAMILY
        or cs.get("detection_family") == _UNIVERSAL_UTILITY_FAMILY
    )


def _is_concise_spl_utility(
    draft_preview: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None,
) -> bool:
    dp = draft_preview if isinstance(draft_preview, dict) else {}
    cs = candidate_spl if isinstance(candidate_spl, dict) else {}
    if _is_universal_spl_utility(draft_preview, candidate_spl):
        return True
    if (
        dp.get("detection_family") == _USER_BOUND_UTILITY_FAMILY
        or cs.get("detection_family") == _USER_BOUND_UTILITY_FAMILY
    ):
        return True
    # Explicit utility-authoring candidates carry this trace; catalog T1
    # lab drafts do not, so they keep the T1 review card.
    return bool(cs.get("utility_spl_draft_trace")) and str(cs.get("generation_mode") or "") in {
        "deterministic_compiler_draft",
        "utility_llm_spl_draft",
        "utility_llm_spl_repair",
    }


def _universal_utility_index_and_usage_lines(
    candidate_spl: dict[str, Any] | None,
) -> list[str]:
    post = (candidate_spl or {}).get("review_only_spl_postprocessor_trace")
    post = post if isinstance(post, dict) else {}
    resolved_index = str(post.get("resolved_index") or "").strip()
    index_source = str(post.get("index_resolution_source") or "").strip()
    lines: list[str] = []
    if resolved_index and resolved_index != "<your_index>":
        if index_source in {
            "coe_environment_kb",
            "source_profile_resolver",
            "coe_generic_utility_default",
        }:
            lines.append(f"Using COE-resolved index `{resolved_index}`.")
        else:
            lines.append(f"Using resolved index `{resolved_index}`.")
    else:
        lines.append("`<your_index>` is a placeholder; replace it with the correct index before review.")
    lines.append("")
    lines.append("How to use:")
    if not resolved_index or resolved_index == "<your_index>":
        lines.append("- Replace `<your_index>` with your index (or bind a source profile).")
    lines.append("- `%H` extracts the hour of day.")
    lines.append("- `%w` is the weekday number (0=Sunday, 6=Saturday) and drives the weekend filter.")
    lines.append("- `%A` is the display-only day name.")
    lines.append("- Adjust `earliest`/`latest` to your time window.")
    lines.append("")
    lines.append(_HOW_PRODUCED)
    return lines


def render_universal_spl_utility_summary(
    *,
    candidate_spl: dict[str, Any] | None = None,
) -> str:
    """Card header text for universal utility SPL (index + usage; SPL lives in draft_spl_code)."""
    return "\n".join(_universal_utility_index_and_usage_lines(candidate_spl)).strip()


def render_universal_spl_utility_answer(
    *,
    analyst_response: Any,
    draft_preview: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None = None,
) -> str:
    """Concise SPL-first answer for explicit universal/template-free SPL authoring.

    No severity line, no long SOC checklist, no source-profile clarification, no
    compromise caveat — those stay in the governance trace. Just the not-executed
    notice, the SPL block, and a short usage explanation.
    """
    draft_spl = _draft_spl_text(analyst_response, draft_preview, candidate_spl=candidate_spl)
    lines: list[str] = [_UNIVERSAL_UTILITY_TITLE, ""]
    if draft_spl:
        lines.append(draft_spl)
        lines.append("")
    lines.extend(_universal_utility_index_and_usage_lines(candidate_spl))
    return "\n".join(lines).strip()


def render_user_bound_spl_utility_answer(
    *,
    candidate_spl: dict[str, Any] | None = None,
) -> str:
    draft_spl = str((candidate_spl or {}).get("candidate_spl") or "").strip()
    lines = ["Review-only - not executed", ""]
    if draft_spl:
        lines.append(draft_spl)
    return "\n".join(lines).strip()


_UTILITY_CARD_CLEARS: dict[str, Any] = {
    "scenario_label": None,
    "response_profile": "spl_only",
    "investigation_steps": [],
    "recommended_actions": [],
    "initial_assessment": [],
    "analyst_checklist": [],
    "required_evidence": [],
    "missing_evidence": [],
    "limitations": [],
    "mitre_mappings": [],
    "escalation_criteria": [],
    "closure_conditions": [],
    "severity_label": None,
    "severity_rationale": None,
    "severity_safety_note": None,
    "spl_status_detail": None,
    "spl_status": "review_required",
    "one_sentence_finding": None,
    "review_notice": None,
    "render_sections": {
        "spl_artifact": False,
        "draft_spl_preview": False,
        "live_results": False,
        "mitre_mapping": False,
        "not_claimed": False,
        "policy_citation": False,
        "investigation_guidance": False,
        "limitations": False,
    },
}


def render_review_only_spl_answer(
    *,
    analyst_response: Any,
    draft_preview: dict[str, Any] | None,
    t2_source_profile: str | None = None,
    candidate_spl: dict[str, Any] | None = None,
    spl_artifact_handoff: dict[str, Any] | None = None,
    user_query: str | None = None,
    match_path: str | None = None,
) -> str:
    """Compose the single clean visible answer for a review-only SPL draft.

    Fixed section order: title, status block, scope, review-only notice, SOC review
    checklist (numbered, once), draft SPL preview (once), assumptions (once), and an
    optional "How this answer was produced" line. The renderer never emits live-result
    language, severity priority prefixes, or a competing title/review-type banner.
    """
    if isinstance(candidate_spl, dict) and candidate_spl.get("spl_authoring_unavailable"):
        return analyst_authoring_abstention_message(candidate_spl)
    if _is_universal_spl_utility(draft_preview, candidate_spl):
        return render_universal_spl_utility_answer(
            analyst_response=analyst_response,
            draft_preview=draft_preview,
            candidate_spl=candidate_spl,
        )
    if _is_concise_spl_utility(draft_preview, candidate_spl):
        return render_user_bound_spl_utility_answer(candidate_spl=candidate_spl)

    lines: list[str] = [_MAIN_TITLE, ""]

    lines.append(f"Severity: {_severity_text(analyst_response)}")
    lines.append(_EXECUTION_LINE)
    lines.append(_REVIEW_LINE)
    lines.append(_ANALYST_VALIDATION_LINE)
    lines.append(f"Scope: {_scope_line(analyst_response, t2_source_profile=t2_source_profile, draft_preview=draft_preview).removeprefix('Scope: ')}")
    lines.append("")

    supplement = resolve_signal_class_review_supplement(
        user_query,
        match_path=match_path,
        draft_preview=draft_preview,
        candidate_spl=candidate_spl,
    )
    if supplement:
        lines.extend(format_signal_class_review_supplement(supplement))

    lines.append(_REVIEW_ONLY_NOTICE)
    lines.append("")

    event_fields = _required_event_fields(draft_preview)
    if event_fields:
        lines.append("Required event fields:")
        lines.extend(f"- {field}" for field in event_fields)
        lines.append("")

    profile_bindings = _required_profile_bindings(draft_preview)
    if profile_bindings:
        lines.append("Required source-profile bindings:")
        lines.extend(profile_bindings)
        lines.append("")

    resolved = _resolved_scope_bindings(draft_preview)
    if resolved:
        lines.append("Resolved source-profile bindings:")
        lines.extend(resolved)
        lines.append("")

    used = _source_profile_used(draft_preview)
    if used:
        lines.append("Source profile used:")
        lines.extend(used)
        lines.append("")

    missing = _missing_bindings(draft_preview)
    if missing:
        lines.append("Missing source bindings:")
        lines.extend(missing)
        lines.append("")

    family_sections = _source_family_draft_sections(draft_preview)
    if family_sections:
        lines.append("Additional source-family draft sections:")
        lines.extend(family_sections)
        lines.append("")

    lines.append(_CHECKLIST_HEADER)
    for index, item in enumerate(
        _checklist_items(analyst_response, draft_preview, candidate_spl=candidate_spl),
        start=1,
    ):
        lines.append(f"{index}. {item}")

    draft_spl = _draft_spl_text(analyst_response, draft_preview, candidate_spl=candidate_spl)
    if draft_spl:
        lines.append("")
        lines.append("Draft SPL preview:")
        lines.append(draft_spl)

    assumptions = _assumptions(draft_preview)
    if assumptions:
        lines.append("")
        lines.append("Assumptions and placeholders:")
        for item in assumptions:
            lines.append(f"- {item}")

    handoff_lines = _spl_artifact_handoff_trace_lines(spl_artifact_handoff)
    if handoff_lines:
        lines.append("")
        lines.extend(handoff_lines)

    lines.append("")
    lines.append(_HOW_PRODUCED)

    return "\n".join(lines).strip()


def apply_review_only_spl_render(
    *,
    run_contract: Any,
    analyst_response: Any,
    message: str,
    draft_preview: dict[str, Any] | None,
    candidate_spl: dict[str, Any] | None = None,
    spl_artifact_handoff: dict[str, Any] | None = None,
    user_query: str | None = None,
    match_path: str | None = None,
) -> tuple[Any, str]:
    """For review-only SPL answers, own the visible answer and suppress competing producers.

    Returns ``(analyst_response, message)``. When the trigger does not match, inputs are
    returned unchanged. Governance fields are not touched — only presentation:
      * ``message`` becomes the single composed visible answer.
      * The card's competing title / review-type / investigation-plan / analyst-workflow
        producers are suppressed at the section level (not scrubbed afterwards):
          - ``finding_title`` becomes the review-only title.
          - ``response_profile`` becomes ``spl_only`` so the frontend drops the
            investigation-plan, MITRE, and model-reasoning phases.
          - ``investigation_steps`` and ``recommended_actions`` are cleared so the same
            checklist is not rendered twice under "Investigation steps / Analyst workflow".
          - ``scenario_label`` is cleared so it cannot prepend a competing heading.
          - ``direct_answer_summary`` carries only the status/scope/notice header.
    """
    if not is_review_only_spl_answer(run_contract) or analyst_response is None:
        if (
            analyst_response is not None
            and isinstance(candidate_spl, dict)
            and candidate_spl.get("spl_authoring_unavailable")
        ):
            composed = analyst_authoring_abstention_message(candidate_spl)
            updates = {
                **_UTILITY_CARD_CLEARS,
                "finding_title": "Review-only SPL draft. This was not executed.",
                "direct_answer_summary": composed,
                "spl_code": None,
                "draft_spl_code": None,
                "spl_draft_preview": None,
            }
            return analyst_response.model_copy(update=updates), composed
        if (
            analyst_response is None
            or not _is_concise_spl_utility(draft_preview, candidate_spl)
            or not str((candidate_spl or {}).get("candidate_spl") or "").strip()
        ):
            return analyst_response, message

    if isinstance(candidate_spl, dict) and candidate_spl.get("spl_authoring_unavailable"):
        composed = analyst_authoring_abstention_message(candidate_spl)
        updates = {
            **_UTILITY_CARD_CLEARS,
            "finding_title": "Review-only SPL draft. This was not executed.",
            "direct_answer_summary": composed,
            "spl_code": None,
            "draft_spl_code": None,
            "spl_draft_preview": None,
        }
        return analyst_response.model_copy(update=updates), composed

    # Scope to lab-only draft answers. A governed, validated SPL draft (no lab preview,
    # spl_code present) is also review-only/not-executed but keeps its "Governed SPL
    # draft ready" wording — it is not "not governed, not approved".
    has_lab_draft = (
        isinstance(draft_preview, dict) and str(draft_preview.get("draft_spl") or "").strip()
    ) or bool(str(getattr(analyst_response, "draft_spl_code", "") or "").strip()) or (
        is_t2_spl_native_candidate(candidate_spl)
        and str((candidate_spl or {}).get("candidate_spl") or "").strip()
    ) or (
        _is_concise_spl_utility(draft_preview, candidate_spl)
        and str((candidate_spl or {}).get("candidate_spl") or "").strip()
    )
    if not has_lab_draft:
        return analyst_response, message

    # A T1 SPL-native (T2) review draft owns its own source profile; use it for the
    # scope so a co-matched IT-to-OT use case cannot drive the firewall framing.
    t2_source_profile: str | None = None
    if is_t2_spl_native_candidate(candidate_spl):
        t2_source_profile = str(t2_spl_native_block(candidate_spl).get("source_profile") or "") or None

    composed = render_review_only_spl_answer(
        analyst_response=analyst_response,
        draft_preview=draft_preview,
        t2_source_profile=t2_source_profile,
        candidate_spl=candidate_spl,
        spl_artifact_handoff=spl_artifact_handoff,
        user_query=user_query,
        match_path=match_path,
    )

    # Concise SPL-first card for explicit universal/template-free authoring only.
    # Governance fields on the run_contract are untouched; this only suppresses the
    # SOC-investigation card sections for this narrow utility mode.
    if _is_concise_spl_utility(draft_preview, candidate_spl):
        utility_spl = _draft_spl_text(analyst_response, draft_preview, candidate_spl=candidate_spl)
        is_universal = _is_universal_spl_utility(draft_preview, candidate_spl)
        card_summary = (
            render_universal_spl_utility_summary(candidate_spl=candidate_spl)
            if is_universal
            else "Review-only SPL artifact displayed exactly from deterministic user-bound constraints. Nothing was executed."
        )
        updates = {
            "finding_title": _UNIVERSAL_UTILITY_TITLE if is_universal else "Review-only SPL draft. This was not executed.",
            "scenario_label": None,
            "response_profile": "spl_only",
            "investigation_steps": [],
            "recommended_actions": [],
            "severity_label": None,
            "severity_rationale": None,
            "severity_safety_note": None,
            "direct_answer_summary": card_summary,
            "one_sentence_finding": None,
            "analyst_checklist": [],
            "initial_assessment": [],
            "required_evidence": [],
            "missing_evidence": [],
            "limitations": [],
            "mitre_mappings": [],
            "spl_code": None,
            "draft_spl_code": utility_spl or None,
            "spl_draft_preview": None,
            "spl_status_detail": None,
            "spl_status": "review_required",
            "spl_unbound_constraints": [],
            "review_notice": None,
            "render_sections": {
                "spl_artifact": True,
                "draft_spl_preview": True,
                "live_results": False,
                "mitre_mapping": False,
                "not_claimed": False,
                "policy_citation": False,
                "investigation_guidance": False,
                "limitations": False,
            },
        }
        overlays = t2_card_overlays(candidate_spl)
        if overlays:
            updates.update(overlays)
        return analyst_response.model_copy(update=updates), composed

    # Header text owned by the card summary (status block + scope only). The title is not
    # repeated here (the card renders ``finding_title`` as its heading), and the lab-only
    # notice is not repeated here either — it stays in the composed message and in the
    # card's owned ``spl_draft_preview.warning`` section, so the warning is not rendered
    # twice within the card surface. Checklist and SPL own their own sections.
    header_lines = [
        f"Severity: {_severity_text(analyst_response)}",
        _EXECUTION_LINE,
        _REVIEW_LINE,
        _ANALYST_VALIDATION_LINE,
        _scope_line(analyst_response, t2_source_profile=t2_source_profile, draft_preview=draft_preview),
    ]
    supplement = resolve_signal_class_review_supplement(
        user_query,
        match_path=match_path,
        draft_preview=draft_preview,
        candidate_spl=candidate_spl,
    )
    if supplement:
        header_lines.append(str(supplement.get("header") or ""))
        header_lines.extend(format_signal_class_review_supplement(supplement))

    updates: dict[str, Any] = {
        "finding_title": _MAIN_TITLE,
        "scenario_label": None,
        "response_profile": "spl_only",
        "investigation_steps": [],
        "recommended_actions": [],
        # ``severity_rationale`` carries the generic "Review type: analytics/query
        # review." banner; the status block already states severity, so clear it (and the
        # safety note) for this path so no competing top-level line is rendered.
        "severity_rationale": None,
        "severity_safety_note": None,
        "direct_answer_summary": "\n\n".join(header_lines),
        "analyst_checklist": _checklist_items(
            analyst_response, draft_preview, candidate_spl=candidate_spl
        ),
    }
    overlays = t2_card_overlays(candidate_spl)
    if overlays:
        updates.update(overlays)
    updated = analyst_response.model_copy(update=updates)
    return updated, composed
