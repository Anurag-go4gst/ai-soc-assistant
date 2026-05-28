"""Stage 3K-Q3 vetted detection binding tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.detections.detection_binder import (
    REASON_UNKNOWN_FAMILY,
    REASON_UNVETTED_ONLY,
    bind_detection,
    preflight_detection_requirements,
)
from app.detections.detection_models import VettingStatus
from app.detections.detection_registry import clear_detection_registry_cache, load_detection_registry
from app.routing.route_plan_models import PreflightContext, RouteStatus
from app.routing.route_plan_normalizer import normalize_route_plan_candidate
from app.routing.route_plan_preflight import preflight_route_plan

_FIXTURE = Path(__file__).resolve().parents[1] / "detections" / "fixtures" / "detection_registry.sample.json"


@pytest.fixture(autouse=True)
def _reset_detection_registry_cache() -> None:
    clear_detection_registry_cache()
    yield
    clear_detection_registry_cache()


def test_approved_family_binds_expected_detection_ref() -> None:
    result = bind_detection("dga", {"query": "dns"}, registry_path=_FIXTURE)

    assert result.bound is True
    assert result.detection_ref == "soc.dga.v1"
    assert result.vetting_status == VettingStatus.APPROVED
    assert result.requires_human_validation is True


def test_unknown_family_returns_unbound() -> None:
    result = bind_detection("not_a_real_family", registry_path=_FIXTURE)

    assert result.bound is False
    assert result.unbound_reason == REASON_UNKNOWN_FAMILY


def test_provisional_and_unvetted_families_not_bindable() -> None:
    webshell = bind_detection("webshell", registry_path=_FIXTURE)
    c2 = bind_detection("c2", {"host": "host01"}, registry_path=_FIXTURE)

    assert webshell.bound is False
    assert webshell.unbound_reason == REASON_UNVETTED_ONLY
    assert c2.bound is False
    assert c2.unbound_reason == REASON_UNVETTED_ONLY


def test_dga_preflight_passes_when_registry_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_registry_enabled", True)

    result = preflight_route_plan(
        "Which DNS queries look like DGA activity?",
        PreflightContext(configured_detections=set()),
    )

    assert result.route_status is None
    assert not result.is_blocked


def test_missing_dga_detection_blocks_when_registry_disabled() -> None:
    result = preflight_route_plan(
        "Which DNS queries look like DGA activity?",
        PreflightContext(configured_detections=set()),
    )

    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_DETECTION
    assert "detection_ref" in result.missing_slots


def test_route_plan_detection_dependency_blocks_without_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "detection_registry_enabled", False)
    route_plan = {
        "evidence_needs": {"detection_required": True, "detection_family": "dga"},
        "parameters": {},
    }

    result = preflight_route_plan("query", PreflightContext(route_plan=route_plan))

    assert result.route_status == RouteStatus.CANNOT_ROUTE_MISSING_DETECTION


def test_unregistered_detection_ref_stripped_in_normalizer() -> None:
    candidate = {
        "route_plan_id": "rp_q3",
        "primary_skill": "behavioral_detection_binding",
        "parameters": {"detection_ref": "evil_detection", "time_window": "last_24_hours"},
        "model_advisory_metadata": {},
    }

    plan, warnings, _blocks = normalize_route_plan_candidate(candidate)

    assert "detection_ref" not in plan.get("parameters", {})
    assert any("unregistered_detection_ref_rejected" in warning for warning in warnings)
    rejections = plan["model_advisory_metadata"].get("detection_ref_rejections", [])
    assert any("evil_detection" in item for item in rejections)


def test_registry_fixture_honesty_labels() -> None:
    registry = load_detection_registry(_FIXTURE)
    document = registry.document

    assert document.coe_synthetic_fixture is True
    assert document.captured_live_run is False
    assert document.production_execution is False


def test_preflight_detection_requirements_when_registry_disabled() -> None:
    block = preflight_detection_requirements(detection_required=True, family="dga")

    assert block is not None
    assert block.bound is False
    assert block.unbound_reason == "missing_configured_detection"


def test_no_http_imports_in_detection_package() -> None:
    package_root = Path(__file__).resolve().parents[1] / "detections"
    for path in package_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import httpx" not in text
        assert "import requests" not in text
        assert "urllib.request" not in text


def test_registry_loads_from_json_fixture() -> None:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert any(item["detection_ref"] == "soc.dga.v1" for item in payload["detections"])
