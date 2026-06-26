"""Tests for semantic constraint extraction and SPL coverage validation."""

from __future__ import annotations

import pytest

from app.config import settings
from app.spl.draft_preview import build_draft_preview
from app.spl.t2_constraints import (
    ConstraintExtractionResult,
    extract_semantic_constraints,
    validate_constraint_coverage,
)
from app.spl.t2_pre_parse import pre_parse_spl_tokens
from app.spl.template_slot_bindings import build_user_bound_skeleton
from app.spl.user_constraint_bindings import build_user_constraint_bindings

_WINEVENT_OFF_SHIFT = (
    "Run a Splunk search on the wineventlog index for Event ID 4624 (Successful Logon) "
    "originating from substation subnets outside normal shift hours."
)
_WINEVENT_EXPLICIT_SHIFT = (
    "Find Event ID 4624 from substation subnets outside 7am to 7pm."
)


def test_pre_parse_extracts_off_shift_constraint() -> None:
    tokens = pre_parse_spl_tokens(_WINEVENT_OFF_SHIFT)
    types = [item["constraint_type"] for item in tokens.semantic_constraints]
    assert "off_shift_filter" in types
    assert "event_code_filter" in types
    assert "subnet_filter" in types


def test_off_shift_extraction_with_configured_shift_hours() -> None:
    result = extract_semantic_constraints(
        _WINEVENT_OFF_SHIFT,
        shift_config={"shift_start_hour": 6, "shift_end_hour": 22},
    )
    off_shift = next(c for c in result.constraints if c.constraint_type == "off_shift_filter")
    assert off_shift.value == {"shift_start_hour": 6, "shift_end_hour": 22}
    assert result.missing_bindings == []


def test_off_shift_missing_config_surfaces_bindings() -> None:
    result = extract_semantic_constraints(_WINEVENT_OFF_SHIFT, shift_config={})
    off_shift = next(c for c in result.constraints if c.constraint_type == "off_shift_filter")
    assert off_shift.status == "missing_config"
    assert "normal_shift_start_hour" in result.missing_bindings
    assert "normal_shift_end_hour" in result.missing_bindings


def test_explicit_shift_hours_7am_to_7pm() -> None:
    result = extract_semantic_constraints(_WINEVENT_EXPLICIT_SHIFT)
    off_shift = next(c for c in result.constraints if c.constraint_type == "off_shift_filter")
    assert off_shift.value == {"shift_start_hour": 7, "shift_end_hour": 19}


@pytest.fixture(autouse=True)
def _enable_draft_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)


def test_winevent_off_shift_spl_includes_hour_filter() -> None:
    preview = build_draft_preview(
        _WINEVENT_OFF_SHIFT,
        spl_validation={"spl_template_status": "missing"},
    )
    assert preview is not None
    spl = preview["draft_spl"]
    assert 'strftime(_time, "%H")' in spl
    assert "login_hour < 6" in spl
    assert "login_hour >= 22" in spl
    assert "cidrmatch" in spl
    constraints = preview.get("semantic_constraints") or []
    off_shift = next(c for c in constraints if c["constraint_type"] == "off_shift_filter")
    assert off_shift["status"] == "implemented"


def test_missing_shift_config_does_not_silently_drop_off_shift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Environment KB has no shift hours, off-shift must not be silently dropped."""

    def _empty_profile(_query: str, **_: object) -> object:
        from app.spl.source_profile_bindings import SourceProfileBindingResult

        return SourceProfileBindingResult()

    monkeypatch.setattr(
        "app.spl.t2_constraints.build_source_profile_binding_slots",
        _empty_profile,
    )
    bindings = build_user_constraint_bindings(
        _WINEVENT_OFF_SHIFT,
        extra_slots={},
        preserve_user_explicit_indexes=True,
    )
    assert "normal_shift_start_hour" in bindings.missing_constraints or any(
        item.get("slot") == "normal_shift_start_hour"
        for item in bindings.unbound_constraints
    )


def test_constraint_coverage_validator_flags_missing_off_shift() -> None:
    constraints = [
        {
            "constraint_type": "off_shift_filter",
            "value": {"shift_start_hour": 6, "shift_end_hour": 22},
            "status": "requested",
        }
    ]
    serialized, missing = validate_constraint_coverage(constraints, "index=wineventlog | stats count")
    assert "off_shift_filter" in missing
    assert serialized[0]["status"] == "not_implemented"


def test_user_bound_skeleton_explicit_index_wins() -> None:
    bindings = build_user_constraint_bindings(
        _WINEVENT_OFF_SHIFT,
        extra_slots={
            "index": "pgcil_soc",
            "approved_source_cidr": "10.40.0.0/16",
            "normal_shift_start_hour": "6",
            "normal_shift_end_hour": "22",
        },
        preserve_user_explicit_indexes=True,
    )
    spl = build_user_bound_skeleton(bindings)
    assert "index=wineventlog" in spl
    assert "pgcil_soc" not in spl.split("|", 1)[0]


def test_pre_parse_off_shift_uses_source_profile_shift_hours() -> None:
    """T2 pre-parse must share Environment KB shift hours with the bindings path."""
    tokens = pre_parse_spl_tokens(_WINEVENT_OFF_SHIFT)
    off_shift = next(c for c in tokens.semantic_constraints if c["constraint_type"] == "off_shift_filter")
    assert off_shift["status"] == "requested"
    assert off_shift["value"] == {"shift_start_hour": 6, "shift_end_hour": 22}
    assert tokens.missing_constraint_bindings == []
