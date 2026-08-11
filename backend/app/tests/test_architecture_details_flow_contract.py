"""Published architecture page contract for the canonical analyst-facing flow."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PAGE = REPO_ROOT / "docs" / "architecture" / "details.html"
PUBLISHED_PAGE = REPO_ROOT / "frontend" / "public" / "docs" / "architecture" / "details.html"


def _page() -> str:
    return SOURCE_PAGE.read_text(encoding="utf-8")


def test_source_and_published_architecture_pages_are_identical() -> None:
    assert _page() == PUBLISHED_PAGE.read_text(encoding="utf-8")


def test_primary_flow_explains_tiers_specialists_and_dispatch_in_plain_language() -> None:
    page = _page()

    required_text = (
        'id="plain-flow-title"',
        "T1–T3 · recognized request",
        "T4 · not confidently recognized",
        "resolve T4 → T0",
        "Routing Contract Auditor",
        "Knowledge Coverage Auditor",
        "MCP Readiness Auditor",
        "SPL Readiness Auditor",
        "Combine the reports without changing the approved plan",
        "D1 · Knowledge only",
        "D2 · Composed plan",
        "D3 · SPL workflow",
        "D4 · Stop or ask",
        "Knowledge Retrieval Worker",
        "Nine checks before an answer is released",
    )
    for text in required_text:
        assert text in page, text

    assert "D0" not in page
    assert not re.search(r'class="chip iris"[^>]*>T0<', page)


def test_visible_architecture_svg_has_desktop_mobile_and_accessible_descriptions() -> None:
    page = _page()

    assert 'class="architecture-visual"' in page
    assert 'class="arch-svg desktop"' in page
    assert 'class="arch-svg mobile"' in page
    assert 'aria-labelledby="arch-desktop-title arch-desktop-desc"' in page
    assert 'aria-labelledby="arch-mobile-title arch-mobile-desc"' in page
    assert "Every planned path then runs the Routing Contract" in page
    assert ".arch-svg.desktop { display: none; }" in page
    assert ".arch-svg.mobile { display: block; }" in page


def test_both_active_journeys_include_fan_out_merge_and_distinct_dispatch() -> None:
    page = _page()
    known_start = page.index('id="journey-known-title"')
    reference_start = page.index('id="journey-reference-title"')
    known = page[known_start:reference_start]
    reference = page[
        reference_start : page.index("</article>", reference_start) + len("</article>")
    ]

    for journey in (known, reference):
        assert "all four specialist reports" in journey.lower()
        assert "merge" in journey.lower()

    assert "T1–T3" in known and "D3" in known
    assert "T4 → T0" in reference and "D1" in reference


def _architecture_svg(variant: str) -> str:
    page = _page()
    start = page.index(f'<svg class="arch-svg {variant}"')
    return page[start : page.index("</svg>", start) + len("</svg>")]


def test_architecture_map_carries_the_flow_through_workers_governance_and_release() -> None:
    """The map must not stop at dispatch — it has to reach the analyst card."""
    governance_nodes = (
        "spl_validate",
        "mcp_execution_gate",
        "context_sufficiency",
        "decide_facts",
        "answer_guard",
        "human_review",
        "policy_veto",
        "finalize",
        "validate_final_answer",
    )

    for variant in ("desktop", "mobile"):
        svg = _architecture_svg(variant)

        # Stage 7: the workers each dispatch path is allowed to run.
        assert "Knowledge Retrieval Worker" in svg, variant
        assert "Approved step workers" in svg, variant
        assert "spl_source_resolve" in svg, variant
        assert "No evidence worker" in svg, variant

        # Stage 8: all nine checks, laid out in the order _add_governance_chain
        # wires them, so positions must increase monotonically through the SVG.
        # Anchored so stage 7's non_planned_finalize label cannot be mistaken
        # for governance check 8 (finalize).
        matches = [re.search(rf"[>·] ?{node}<", svg) for node in governance_nodes]
        assert all(match is not None for match in matches), (
            variant,
            [node for node, match in zip(governance_nodes, matches) if match is None],
        )
        positions = [match.start() for match in matches if match is not None]
        assert positions == sorted(positions), (variant, positions)

        # Stage 9: the turn actually ends somewhere.
        assert "Analyst card + durable trace" in svg, variant


def test_architecture_map_states_where_each_dispatch_path_enters_governance() -> None:
    """D4 reaches finalize directly, so it must not be drawn entering at check 1."""
    desktop = _architecture_svg("desktop")
    assert desktop.count("enters at check 1") == 2
    assert "enters at check 2" in desktop
    assert "enters at check 8" in desktop

    mobile = _architecture_svg("mobile")
    assert "D1 and D2 enter at 1 · D3 at 2 · D4 at 8" in mobile


def test_page_states_current_specialist_limits_and_mobile_layout_contract() -> None:
    page = _page()

    assert "specialist_mcp · fixed marker today" in page
    assert "specialist_spl · fixed marker today" in page
    assert "Current implementation:</strong> a fixed advisory marker" in page
    assert ".journey-grid {" in page
    assert "@media (max-width: 760px)" in page
    assert ".governance-grid," in page
    assert ".journey-grid { grid-template-columns: 1fr; }" in page
