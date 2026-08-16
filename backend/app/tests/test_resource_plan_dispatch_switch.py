"""Plan 8 X3 — ResourcePlan vs dispatch-v2 authority switch pins.

Named so Plan 8's exact Verify command has a regression artifact. Consumes
Plan 7 A6/A7: dispatch-v2 is not normal authority; ResourcePlan execution
fences it. No flag or runtime change.
"""

from __future__ import annotations

from app.chat.contracts.pipeline_dispatch import legacy_dispatch_v2_authority_enabled
from app.config import Settings, settings


def test_repo_default_keeps_dispatch_v2_off_and_not_normal_authority() -> None:
    fields = Settings.model_fields
    assert fields["ai_soc_pipeline_dispatch_v2_enabled"].default is False
    assert fields["ai_soc_resource_plan_execution_enabled"].default is False


def test_resource_plan_execution_on_fences_dispatch_v2(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    assert legacy_dispatch_v2_authority_enabled() is False


def test_dispatch_v2_rollback_only_when_resource_plan_execution_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_pipeline_dispatch_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", False)
    assert legacy_dispatch_v2_authority_enabled() is True
