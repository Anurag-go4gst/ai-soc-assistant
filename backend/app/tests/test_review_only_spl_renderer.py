"""Golden + control tests for the dedicated review-only SPL answer renderer.

The renderer owns the visible answer for review-only SPL drafts (one fixed-order
template) and suppresses the generic title/review-type/investigation-plan producers.
Routing / RunContract / HIL / MCP / source-evidence are not exercised here — these
assert visible-answer composition only.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.chat.pipeline import build_live_chat_response
from app.schemas.requests import ChatRequest
from app.tests.support.chat_visible import (
    assert_review_only_title,
    first_visible_line,
    visible_chat_prose,
)

SUBSTATION_QUERY = (
    "Show me all external connections or remote access sessions currently mapping "
    "to the substation networks."
)
GUIDANCE_QUERY = "How should SOC investigate external connections from OT networks?"
UNMATCHED_LIVE_QUERY = "Show me privileged VPN sessions from last night."

_CONTROL_PLANE_FLAGS = (
    "ai_soc_spl_draft_preview_enabled",
    "ai_soc_spl_template_governance_enabled",
    "ai_soc_curated_enrichment_activation_enabled",
    "ai_soc_planner_path_selection_enabled",
    "soc_kb_retrieval_enabled",
    "ai_soc_t2_answer_shape_enabled",
    "ai_soc_t2_rag_surfacing_enabled",
)


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag in _CONTROL_PLANE_FLAGS:
        monkeypatch.setattr(settings, flag, True)


def _visible(query: str) -> str:
    response = build_live_chat_response(ChatRequest(message=query))
    return visible_chat_prose(response)


def test_substation_query_renders_clean_review_only_spl_answer() -> None:
    response = build_live_chat_response(ChatRequest(message=SUBSTATION_QUERY))
    visible = visible_chat_prose(response)
    first_line = first_visible_line(response)
    lowered = visible.lower()

    # 1. Main title is on the card heading (may be scrubbed to performed).
    assert_review_only_title(first_line)

    # 2. Status block.
    assert "Severity: Not assigned from this question alone" in visible
    assert "Execution: Not executed" in visible or "Execution: Not performed" in visible
    assert "HIL/SOC review required before any future execution path" in visible

    # 3. Scope line (strong family match → IT-to-OT framing).
    assert "Scope: IT-to-OT firewall boundary review" in visible

    # 4. Review-only notice + checklist/SPL/assumptions each exactly once.
    draft = response.spl_draft_preview
    warning = str(getattr(draft, "warning", "") or "").lower()
    assert "lab-only draft spl preview" in warning
    # 4. Checklist and SPL live on the analyst card (top-level message may be empty).
    card = response.analyst_response
    assert card is not None
    assert card.analyst_checklist
    assert card.draft_spl_code
    assert "search index=" in (card.draft_spl_code or "").lower()
    assert lowered.count("assumptions and placeholders") <= 1

    # 8. Honest review-only posture; no live-backed claims in visible surfaces.
    assert "live-backed" not in lowered
    assert "review-only" in lowered or "no live execution" in lowered.replace(" ", "")


def test_substation_query_suppresses_competing_producers() -> None:
    response = build_live_chat_response(ChatRequest(message=SUBSTATION_QUERY))
    visible = visible_chat_prose(response)
    lowered = visible.lower()
    card = response.analyst_response
    assert card is not None
    title = str(card.finding_title or "").lower()
    assert "review-only spl draft" in title
    # "Not assigned from this question alone" must not appear before the title.
    assert not title.startswith("not assigned from this question alone")
    summary = str(card.direct_answer_summary or "").lower()
    assert "not assigned from this question alone" in summary
    assert "review type: analytics/query review" not in lowered
    assert "investigation steps" not in lowered
    assert "analyst workflow" not in lowered
    assert "investigation plan" not in lowered
    assert "v.ai soc governed" not in lowered


def test_substation_card_clears_competing_severity_producers() -> None:
    # The severity rationale carries the generic "Review type" banner; the card status
    # block states severity instead, so the rationale/safety-note are cleared.
    card = build_live_chat_response(ChatRequest(message=SUBSTATION_QUERY)).analyst_response
    assert card is not None
    assert not card.severity_rationale
    assert not card.severity_safety_note


def test_substation_query_has_no_priority_prefixes_or_live_claims() -> None:
    visible = _visible(SUBSTATION_QUERY)
    for token in ("P1 ", "P2 ", "P3 ", "P1—", "P2—", "P3—", "P1 —", "P2 —", "P3 —"):
        assert token not in visible
    for claim in ("Detected", "Observed", "Found ", "Currently showing", "Mapped to"):
        assert claim not in visible


def test_substation_card_uses_review_only_title_and_spl_only_profile() -> None:
    response = build_live_chat_response(ChatRequest(message=SUBSTATION_QUERY))
    card = response.analyst_response
    assert card is not None
    assert_review_only_title(card.finding_title or "")
    assert card.response_profile == "spl_only"
    # Checklist is owned once; investigation-steps/plan producers are cleared.
    assert not card.investigation_steps
    assert not card.recommended_actions
    assert card.analyst_checklist
    # No splunk results table on a review-only/not-executed path.
    assert not card.splunk_results_table


def test_guidance_query_is_not_forced_into_review_only_spl_template() -> None:
    # Control 1: a pure guidance ask must not be reshaped into the SPL template.
    visible = _visible(GUIDANCE_QUERY)
    first_line = next((line for line in visible.splitlines() if line.strip()), "")
    assert first_line != "Review-only SPL draft — no live query was executed"
    assert not first_line.lower().startswith("review-only spl draft — no live query was")


def test_unmatched_live_data_query_uses_clean_template_without_forced_title() -> None:
    # Control 2: unmatched live-data ask still gets the clean review-only template,
    # but no IT-to-OT title is forced without a strong family match.
    response = build_live_chat_response(ChatRequest(message=UNMATCHED_LIVE_QUERY))
    visible = visible_chat_prose(response)
    lowered = visible.lower()
    title = str(getattr(response.analyst_response, "finding_title", "") or "")
    if title.lower().startswith("review-only spl draft"):
        assert_review_only_title(first_visible_line(response))
        assert "it-to-ot firewall boundary review" not in lowered
        assert lowered.count("soc review checklist") <= 1
        assert "live-backed" not in lowered

SCADA_T2_QUERY = (
    "Provide a complete review-only SPL query for index=scada_perf using earliest=-30d to "
    "compute an eventstats stdev baseline by rtu_id and filter anomalies in the last 24h "
    "using transmission_error_count."
)


def test_scada_t2_review_only_card_uses_profile_aware_gaps_not_auth_gaps() -> None:
    response = build_live_chat_response(ChatRequest(message=SCADA_T2_QUERY))
    card = response.analyst_response
    assert card is not None
    lim = " ".join(card.limitations or []).lower()
    checklist = " ".join(card.analyst_checklist or []).lower()
    for bad in ("privileged account", "mfa", "post-login", "post login"):
        assert bad not in lim
    assert "metric field validation missing" in lim
    assert "operational baseline sign-off missing" in lim
    assert "not threshold alert" not in checklist
    assert "anomaly ranking" in checklist
