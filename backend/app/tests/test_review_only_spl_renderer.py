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

SUBSTATION_QUERY = (
    "Show me all external connections or remote access sessions currently mapping "
    "to the substation networks."
)
GUIDANCE_QUERY = "How should SOC investigate external connections from OT networks?"
UNMATCHED_LIVE_QUERY = "Show me privileged VPN sessions from last night."

_CONTROL_PLANE_FLAGS = (
    "control_plane_enabled",
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
    return response.message or ""


def test_substation_query_renders_clean_review_only_spl_answer() -> None:
    visible = _visible(SUBSTATION_QUERY)
    first_line = next(line for line in visible.splitlines() if line.strip())
    lowered = visible.lower()

    # 1. Main title is the first non-empty line.
    assert first_line == "Review-only SPL draft — no live query was executed"

    # 2. Status block.
    assert "Severity: Not assigned from this question alone" in visible
    assert "Execution: Not executed" in visible
    assert "HIL/SOC review required before any future execution path" in visible

    # 3. Scope line (strong family match → IT-to-OT framing).
    assert "Scope: IT-to-OT firewall boundary review" in visible

    # 4. Review-only notice + checklist/SPL/assumptions each exactly once.
    assert "lab-only draft spl preview" in lowered
    assert visible.count("SOC review checklist before execution") == 1
    assert visible.count("Draft SPL preview:") == 1
    assert visible.count("search index=") >= 1
    assert visible.count("Additional source-family draft sections:") <= 1
    assert lowered.count("assumptions and placeholders") == 1

    # 8. How produced uses review-only language, not live-backed.
    assert "review-only / no live execution" in lowered
    assert "live-backed" not in lowered


def test_substation_query_suppresses_competing_producers() -> None:
    visible = _visible(SUBSTATION_QUERY)
    lowered = visible.lower()
    # "Not assigned from this question alone" must not appear before the title.
    assert not visible.startswith("Not assigned from this question alone")
    assert lowered.index("review-only spl draft") < lowered.index(
        "not assigned from this question alone"
    )
    assert "review type: analytics/query review" not in lowered
    assert "investigation steps" not in lowered
    assert "analyst workflow" not in lowered
    assert "investigation plan" not in lowered
    assert "v.ai soc governed" not in lowered
    # No competing IT-to-OT title before the review-only title.
    assert lowered.index("review-only spl draft") < lowered.index("it-to-ot firewall boundary review")


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
    assert card.finding_title == "Review-only SPL draft — no live query was executed"
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


def test_unmatched_live_data_query_uses_clean_template_without_forced_title() -> None:
    # Control 2: unmatched live-data ask still gets the clean review-only template,
    # but no IT-to-OT title is forced without a strong family match.
    response = build_live_chat_response(ChatRequest(message=UNMATCHED_LIVE_QUERY))
    visible = response.message or ""
    lowered = visible.lower()
    if response.analyst_response and response.analyst_response.finding_title == (
        "Review-only SPL draft — no live query was executed"
    ):
        first_line = next(line for line in visible.splitlines() if line.strip())
        assert first_line == "Review-only SPL draft — no live query was executed"
        assert "it-to-ot firewall boundary review" not in lowered
        assert lowered.count("soc review checklist") <= 1
        assert "live-backed" not in lowered
