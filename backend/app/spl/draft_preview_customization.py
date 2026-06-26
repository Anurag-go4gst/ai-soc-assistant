"""Query-aware customization for lab SPL draft previews."""

from __future__ import annotations

import re
from typing import Any

from app.query_understanding.time_window import normalize_time_window, time_window_or_default
from app.spl.template_compatibility import check_template_compatibility
from app.spl.template_slot_bindings import (
    build_user_bound_skeleton,
    render_spl_with_bindings,
    skeleton_output_plan,
)
from app.spl.source_profile_bindings import build_source_profile_binding_slots
from app.spl.user_constraint_bindings import build_user_constraint_bindings

_AUTH_FAILURE_FILTER = (
    "(action=failure OR action=failed OR action=denied OR result=failure)"
)

# Evidence keys the auth failed-login draft produces via coalesce/stats — not live gaps.
AUTH_FAILED_LOGIN_DRAFT_SATISFIED_EVIDENCE = frozenset(
    {"user", "src", "host", "fail_count", "time_window", "first_failure", "last_failure"}
)

_USER_RANKING_SPL = """
search index=<auth_index> sourcetype=<auth_sourcetype> {time_bounds} {failure_filter}
| eval user_norm=lower(coalesce(user, username, src_user, "unknown"))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_norm=lower(coalesce(dest, host, dest_host, ""))
| stats
    count as fail_count
    dc(src_ip_norm) as distinct_sources
    values(dest_norm) as targets
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by user_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| sort - fail_count
| head 25
""".strip()

_SOURCE_USER_PAIR_SPL = """
search index=<auth_index> sourcetype=<auth_sourcetype> {time_bounds} {failure_filter}
| eval user_norm=lower(coalesce(user, username, src_user, "unknown"))
| eval src_ip_norm=coalesce(src_ip, src, source, "")
| eval dest_norm=lower(coalesce(dest, host, dest_host, ""))
| stats
    count as fail_count
    values(dest_norm) as targets
    earliest(_time) as first_seen_epoch
    latest(_time) as last_seen_epoch
    by src_ip_norm user_norm
| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S")
| eval last_seen=strftime(last_seen_epoch, "%Y-%m-%d %H:%M:%S")
| fields - first_seen_epoch last_seen_epoch
| sort - fail_count
| head 100
""".strip()


def time_window_display_label(query: str) -> str:
    bounds = normalize_time_window(query)
    if bounds == "earliest=-60m latest=now":
        return "the last hour"
    if bounds == "earliest=-24h latest=now":
        return "the last 24 hours"
    if bounds and bounds.startswith("earliest="):
        return bounds.replace("earliest=", "from ").replace(" latest=now", " through now")
    return "defaulted to last 24 hours"


def auth_failed_login_aggregation_shape(query: str) -> str:
    """Return ``user_ranking`` or ``source_user_pair`` for auth failed-login drafts."""
    normalized = " ".join(query.lower().split())
    if re.search(
        r"\b(which users?|what users?|top users?|users? with|per user|by user|abnormally high)\b",
        normalized,
    ):
        return "user_ranking"
    if re.search(r"\b(source ips?|top sources?|by src|src_ip)\b", normalized):
        return "source_user_pair"
    return "source_user_pair"




def _apply_auth_profile_slots(spl: str, bindings: Any | None) -> str:
    if bindings is None:
        return spl
    index = bindings.normalized_slots.get("index") or (
        bindings.explicit_indexes[0] if bindings.explicit_indexes else None
    )
    sourcetype = bindings.normalized_slots.get("sourcetype") or (
        bindings.explicit_sourcetypes[0] if bindings.explicit_sourcetypes else None
    )
    if index:
        spl = spl.replace("<auth_index>", index)
    if sourcetype:
        spl = spl.replace("<auth_sourcetype>", sourcetype)
    return spl


def customize_auth_failed_login_threshold(
    user_query: str,
    *,
    draft_spl: str,
    assumptions: tuple[str, ...],
    bindings: Any | None = None,
) -> tuple[str, tuple[str, ...], str, str]:
    """Return customized SPL, assumptions, aggregation_shape, time_window_label."""
    time_bounds = time_window_or_default(user_query)
    window_label = time_window_display_label(user_query)
    shape = auth_failed_login_aggregation_shape(user_query)
    relative_rank = bool(re.search(r"\b(abnormal|highest|most)\b", " ".join(user_query.lower().split())))

    threshold_value = None
    if bindings is not None:
        threshold_value = (bindings.explicit_thresholds or {}).get("threshold")
    if threshold_value is None:
        threshold_match = re.search(r"\bmore\s+than\s+(\d+)\b", user_query, re.I)
        if threshold_match:
            threshold_value = threshold_match.group(1)

    if shape == "user_ranking":
        spl = _USER_RANKING_SPL.format(
            time_bounds=time_bounds,
            failure_filter=_AUTH_FAILURE_FILTER,
        )
        if threshold_value and not relative_rank:
            spl = spl.replace(
                "| sort - fail_count",
                f"| where fail_count > {threshold_value}\n| sort - fail_count",
            )
        spl = _apply_auth_profile_slots(spl, bindings)
        assumption_rows = (
            f"Ranks users by failed-login volume over {window_label}; "
            + (
                "abnormally high is surfaced by relative ranking (top-N), not a fixed count threshold."
                if relative_rank
                else (
                    f"Applies an explicit failed-login count threshold of > {threshold_value} before ranking."
                    if threshold_value
                    else "Tune any post-ranking threshold per environment; lower for privileged accounts."
                )
            ),
            "Field mappings use coalesce() for user, source IP, and host/dest — confirm names against your auth sourcetype during review.",
            "Replace <auth_index> and <auth_sourcetype> from your authentication source profile.",
            "This draft is lab-only; not governed, not approved, and not executed.",
        )
        return spl, assumption_rows, shape, window_label

    spl = _SOURCE_USER_PAIR_SPL.format(
        time_bounds=time_bounds,
        failure_filter=_AUTH_FAILURE_FILTER,
    )
    if threshold_value and not relative_rank:
        spl = spl.replace(
            "| sort - fail_count",
            f"| where fail_count > {threshold_value}\n| sort - fail_count",
        )
    spl = _apply_auth_profile_slots(spl, bindings)
    if relative_rank:
        assumption_rows = tuple(
            a.replace("24 hours", window_label)
            .replace("more than 20 failures", "an analyst-tuned threshold after ranking")
            for a in assumptions
        )
    else:
        assumption_rows = tuple(a.replace("24 hours", window_label) for a in assumptions)
        if not any("threshold" in row.lower() for row in assumption_rows):
            assumption_rows = (
                *assumption_rows,
                "The >20 failure filter is illustrative for spike hunts — remove or lower for low-and-slow review.",
            )
    return spl, assumption_rows, shape, window_label


def customize_draft_preview_for_query(
    user_query: str,
    *,
    family_id: str,
    draft_spl: str,
    assumptions: tuple[str, ...],
    llm_intent_advisory: dict[str, Any] | None = None,
) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """Apply query-aware SPL/time-window customization for a detection family."""
    source_profile_result = build_source_profile_binding_slots(user_query, family_id=family_id)
    bindings = build_user_constraint_bindings(
        user_query,
        llm_intent_advisory=llm_intent_advisory,
        extra_slots=source_profile_result.slots,
        source_profile_trace=source_profile_result.trace(),
    )
    metadata: dict[str, Any] = {
        "time_window_bounds": time_window_or_default(user_query),
        "time_window_label": time_window_display_label(user_query),
        "user_constraint_bindings": bindings.to_dict(),
        **source_profile_result.trace(),
    }
    supplemental_sections = (
        _remote_access_source_family_sections(source_profile_result.slots)
        if _has_remote_access_binding_trace(source_profile_result.trace())
        else []
    )
    if supplemental_sections:
        metadata["source_family_draft_sections"] = supplemental_sections
    compatibility = check_template_compatibility(None, bindings, family_id=family_id)
    metadata["template_compatibility"] = compatibility.to_dict()
    if compatibility.use_user_bound_skeleton:
        skeleton = build_user_bound_skeleton(bindings)
        _required, table_fields = skeleton_output_plan(bindings)
        metadata["skeleton_table_fields"] = table_fields
        metadata["used_user_bound_skeleton"] = True
        metadata["unbound_constraints"] = list(bindings.unbound_constraints)
        metadata["semantic_constraints"] = list(bindings.semantic_constraints)
        metadata["missing_constraints"] = list(bindings.missing_constraints)
        return skeleton, (), metadata
    if family_id == "scada_dnp3_modbus_write":
        outcome = render_spl_with_bindings(family_id, draft_spl, bindings)
        metadata["unbound_constraints"] = list(outcome.unbound_constraints)
        if outcome.bound_slots:
            metadata["partial_customization"] = True
        if outcome.used_user_bound_skeleton:
            metadata["used_user_bound_skeleton"] = True
        return outcome.spl, assumptions if not outcome.used_user_bound_skeleton else (), metadata
    if family_id == "auth_failed_login_threshold":
        spl, assumption_rows, shape, window_label = customize_auth_failed_login_threshold(
            user_query,
            draft_spl=draft_spl,
            assumptions=assumptions,
            bindings=bindings,
        )
        metadata["aggregation_shape"] = shape
        metadata["time_window_label"] = window_label
        return spl, assumption_rows, metadata

    time_bounds = time_window_or_default(user_query)
    if normalize_time_window(user_query):
        spl = re.sub(r"earliest=[^\s]+ latest=now", time_bounds, draft_spl.strip())
        assumption_rows = tuple(
            a.replace("24 hours", time_window_display_label(user_query)) for a in assumptions
        )
        return spl, assumption_rows, metadata
    return draft_spl, assumptions, metadata


_REMOTE_ACCESS_SECTION_SLOTS = frozenset(
    {
        "firewall_index",
        "firewall_sourcetype",
        "vpn_index",
        "vpn_sourcetype",
        "jump_host_index",
        "jump_host_sourcetype",
        "pam_index",
        "pam_sourcetype",
        "substation_mapping_lookup",
        "external_system_registry_lookup",
    }
)


def _has_remote_access_binding_trace(trace: dict[str, Any]) -> bool:
    for key in ("source_profile_bindings_found", "source_profile_bindings_missing"):
        for item in trace.get(key) or []:
            if isinstance(item, dict) and item.get("slot") in _REMOTE_ACCESS_SECTION_SLOTS:
                return True
    return False


def _remote_access_source_family_sections(slots: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if slots.get("vpn_index") and slots.get("vpn_sourcetype"):
        sections.append(
            {
                "title": "VPN remote-access sessions",
                "status": "review_only_draft",
                "draft_spl": (
                    f"search index={slots['vpn_index']} sourcetype={slots['vpn_sourcetype']} "
                    "earliest=-24h latest=now (action=success OR action=allowed OR result=success OR event=login)\n"
                    '| eval user_norm=lower(coalesce(user, username, src_user, ""))\n'
                    '| eval src_ip_norm=coalesce(src_ip, src, source, "")\n'
                    '| eval assigned_ip_norm=coalesce(assigned_ip, vpn_ip, client_ip, "")\n'
                    '| eval action_norm=lower(coalesce(action, status, result, event_action, ""))\n'
                    "| table _time user_norm src_ip_norm assigned_ip_norm action_norm\n"
                    "| sort 0 - _time\n"
                    "| head 100"
                ),
            }
        )
    else:
        sections.append(
            {
                "title": "VPN remote-access sessions",
                "status": "missing_source_bindings",
                "missing_slots": [
                    slot for slot in ("vpn_index", "vpn_sourcetype") if not slots.get(slot)
                ],
            }
        )

    jump_bound = slots.get("jump_host_index") and slots.get("jump_host_sourcetype")
    pam_bound = slots.get("pam_index") and slots.get("pam_sourcetype")
    if jump_bound or pam_bound:
        draft_parts: list[str] = []
        if jump_bound:
            draft_parts.append(
                f"search index={slots['jump_host_index']} sourcetype={slots['jump_host_sourcetype']} "
                "earliest=-24h latest=now (rdp OR ssh OR logon OR session)\n"
                '| eval user_norm=lower(coalesce(user, username, account, ""))\n'
                '| eval src_ip_norm=coalesce(src_ip, src, source, "")\n'
                '| eval dest_norm=lower(coalesce(dest, host, target, ""))\n'
                "| table _time user_norm src_ip_norm dest_norm\n"
                "| sort 0 - _time\n"
                "| head 100"
            )
        if pam_bound:
            draft_parts.append(
                f"search index={slots['pam_index']} sourcetype={slots['pam_sourcetype']} "
                "earliest=-24h latest=now (session OR checkout OR connect OR record)\n"
                '| eval user_norm=lower(coalesce(user, username, account, ""))\n'
                '| eval target_norm=lower(coalesce(target, asset, host, system, ""))\n'
                '| eval action_norm=lower(coalesce(action, status, result, event_action, ""))\n'
                "| table _time user_norm target_norm action_norm\n"
                "| sort 0 - _time\n"
                "| head 100"
            )
        sections.append(
            {
                "title": "Jump-host/PAM sessions",
                "status": "review_only_draft",
                "draft_spl": "\n\n".join(draft_parts),
            }
        )
    else:
        sections.append(
            {
                "title": "Jump-host/PAM sessions",
                "status": "missing_source_bindings",
                "missing_slots": [
                    slot
                    for slot in (
                        "jump_host_index",
                        "jump_host_sourcetype",
                        "pam_index",
                        "pam_sourcetype",
                    )
                    if not slots.get(slot)
                ],
            }
        )

    if slots.get("substation_mapping_lookup") or slots.get("external_system_registry_lookup"):
        sections.append(
            {
                "title": "Asset/substation mapping lookup",
                "status": "source_profile_reference",
                "references": [
                    str(slots[key])
                    for key in ("substation_mapping_lookup", "external_system_registry_lookup")
                    if slots.get(key)
                ],
            }
        )
    else:
        sections.append(
            {
                "title": "Asset/substation mapping lookup",
                "status": "missing_source_bindings",
                "missing_slots": [
                    slot
                    for slot in ("substation_mapping_lookup", "external_system_registry_lookup")
                    if not slots.get(slot)
                ],
            }
        )
    return sections


def draft_preview_satisfied_evidence_keys(family_id: str) -> frozenset[str]:
    if family_id == "auth_failed_login_threshold":
        return AUTH_FAILED_LOGIN_DRAFT_SATISFIED_EVIDENCE
    return frozenset()


def reconcile_evidence_plan_for_draft_preview(
    evidence_plan: dict[str, Any] | None,
    draft_preview: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Mark schema fields produced by draft SPL as present — not missing live evidence."""
    if not isinstance(evidence_plan, dict) or not isinstance(draft_preview, dict):
        return evidence_plan
    satisfied = draft_preview_satisfied_evidence_keys(
        str(draft_preview.get("detection_family") or "")
    )
    if not satisfied:
        return evidence_plan
    plan = dict(evidence_plan)
    present = set(plan.get("present_evidence_keys") or [])
    present |= satisfied
    plan["present_evidence_keys"] = sorted(present)
    plan["missing_required_evidence"] = [
        key
        for key in plan.get("missing_required_evidence") or []
        if key not in satisfied
    ]
    return plan
