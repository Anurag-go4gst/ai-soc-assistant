"""Query-aware customization for lab SPL draft previews."""

from __future__ import annotations

import re
from typing import Any

from app.query_understanding.time_window import normalize_time_window, time_window_or_default

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
    return "the requested time window"


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


def customize_auth_failed_login_threshold(
    user_query: str,
    *,
    draft_spl: str,
    assumptions: tuple[str, ...],
) -> tuple[str, tuple[str, ...], str, str]:
    """Return customized SPL, assumptions, aggregation_shape, time_window_label."""
    time_bounds = time_window_or_default(user_query)
    window_label = time_window_display_label(user_query)
    shape = auth_failed_login_aggregation_shape(user_query)
    relative_rank = bool(re.search(r"\b(abnormal|highest|most)\b", " ".join(user_query.lower().split())))

    if shape == "user_ranking":
        spl = _USER_RANKING_SPL.format(
            time_bounds=time_bounds,
            failure_filter=_AUTH_FAILURE_FILTER,
        )
        assumption_rows = (
            f"Ranks users by failed-login volume over {window_label}; "
            + (
                "abnormally high is surfaced by relative ranking (top-N), not a fixed count threshold."
                if relative_rank
                else "Tune any post-ranking threshold per environment; lower for privileged accounts."
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
) -> tuple[str, tuple[str, ...], dict[str, Any]]:
    """Apply query-aware SPL/time-window customization for a detection family."""
    metadata: dict[str, Any] = {
        "time_window_bounds": time_window_or_default(user_query),
        "time_window_label": time_window_display_label(user_query),
    }
    if family_id == "auth_failed_login_threshold":
        spl, assumption_rows, shape, window_label = customize_auth_failed_login_threshold(
            user_query,
            draft_spl=draft_spl,
            assumptions=assumptions,
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
