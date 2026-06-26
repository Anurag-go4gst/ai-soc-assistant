"""Tests for SlotConstraintProjection handoff wrapper."""

from __future__ import annotations

import pytest

from app.config import settings
from app.spl.slot_constraint_projection import (
    build_slot_constraint_projection,
    projection_from_bindings,
)
from app.spl.source_profile_store import save_persisted_source_profile
from app.spl.user_constraint_bindings import build_user_constraint_bindings

_WINEVENT_OFF_SHIFT = (
    "Run a Splunk search on the wineventlog index for Event ID 4624 (Successful Logon) "
    "originating from substation subnets outside normal shift hours."
)
_SCADA = (
    "Provide a complete SPL query for index=scada_perf using earliest=-30d to compute "
    "eventstats stdev baseline by rtu_id and filter anomalies in last 24h using "
    "transmission_error_count"
)
_ASA = (
    "Generate a review-only SPL query to correlate power_sector_iocs.csv indicator_ip with Cisco ASA traffic "
    "in index=cisco_asa against dest_ip for the last 24h. Show src_ip, dest_ip, matched IOC, action, and count."
)


def _use_temp_source_profile(monkeypatch: pytest.MonkeyPatch, tmp_path, values: dict[str, str]) -> None:
    path = tmp_path / "source_profile_map.json"
    monkeypatch.setattr(settings, "ai_soc_source_profile_store_path", str(path))
    save_persisted_source_profile(
        values,
        field_sources={key: "coe_store" for key in values},
        updated_by="test",
    )


@pytest.fixture(autouse=True)
def _expanded_indexes(monkeypatch: pytest.MonkeyPatch) -> None:
    allowed_indexes = "pgcil_soc,ot_logs,wineventlog,syslog,cisco_asa,scada_perf,ot_soc"
    monkeypatch.setenv("SPL_ALLOWED_INDEXES", allowed_indexes)
    monkeypatch.setattr(settings, "spl_allowed_indexes", allowed_indexes)


def test_user_explicit_index_beats_profile_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    _use_temp_source_profile(
        monkeypatch,
        tmp_path,
        {
            "windows_index": "pgcil_soc",
            "ot_asset_cidr": "10.40.0.0/16",
            "normal_shift_start_hour": "6",
            "normal_shift_end_hour": "22",
        },
    )
    projection = build_slot_constraint_projection(
        _WINEVENT_OFF_SHIFT,
        built_at_stage="spl_generation",
    )
    assert projection.normalized_slots.get("index") == "wineventlog"
    dropped_slots = {str(item.get("slot")) for item in projection.dropped_profile_defaults}
    assert "index" in dropped_slots
    assert projection.applied_defaults.get("approved_source_cidr") == "10.40.0.0/16"
    off_shift = next(
        (c for c in projection.semantic_constraints if c.get("constraint_type") == "off_shift_filter"),
        None,
    )
    assert off_shift is not None
    assert off_shift.get("value") == {"shift_start_hour": 6, "shift_end_hour": 22}
    assert "normal_shift_start_hour" not in projection.missing_constraints
    assert not any(
        item.get("slot") == "normal_shift_start_hour" for item in projection.unbound_constraints
    )


def test_missing_shift_config_surfaces_missing_constraints(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    _use_temp_source_profile(monkeypatch, tmp_path, {"ot_asset_cidr": "10.40.0.0/16"})
    projection = build_slot_constraint_projection(
        _WINEVENT_OFF_SHIFT,
        built_at_stage="spl_generation",
    )
    assert "normal_shift_start_hour" in projection.missing_constraints
    assert "normal_shift_end_hour" in projection.missing_constraints


def test_planning_drift_flagged_when_slots_differ() -> None:
    bindings = build_user_constraint_bindings(_WINEVENT_OFF_SHIFT)
    projection = projection_from_bindings(
        bindings,
        built_at_stage="spl_generation",
        planning_snapshot={"normalized_slots": {"index": "pgcil_soc"}},
    )
    assert projection.drift_from_planning_snapshot is True
    assert any("normalized_slots.index" in item for item in projection.drift_details)


def test_planning_drift_false_when_aligned() -> None:
    bindings = build_user_constraint_bindings(_SCADA)
    projection = projection_from_bindings(
        bindings,
        built_at_stage="spl_generation",
        planning_snapshot={"normalized_slots": dict(bindings.normalized_slots)},
    )
    assert projection.drift_from_planning_snapshot is False


def test_scada_projection_preserves_index_and_metrics() -> None:
    projection = build_slot_constraint_projection(_SCADA, built_at_stage="spl_generation")
    assert projection.normalized_slots.get("index") == "scada_perf"


def test_asa_projection_preserves_lookup_and_index() -> None:
    projection = build_slot_constraint_projection(_ASA, built_at_stage="spl_generation")
    assert projection.normalized_slots.get("index") == "cisco_asa"
