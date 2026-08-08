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


def test_page_states_current_specialist_limits_and_mobile_layout_contract() -> None:
    page = _page()

    assert "specialist_mcp · fixed marker today" in page
    assert "specialist_spl · fixed marker today" in page
    assert "Current implementation:</strong> a fixed advisory marker" in page
    assert ".journey-grid {" in page
    assert "@media (max-width: 760px)" in page
    assert ".governance-grid," in page
    assert ".journey-grid { grid-template-columns: 1fr; }" in page
