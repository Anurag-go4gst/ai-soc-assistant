from __future__ import annotations

import pytest

from app.coverage.catalogue_execution_map import (
    CatalogueExecutionBinding,
    load_catalogue_execution_map,
    resolve_catalogue_execution_binding,
)


def test_map_loads_and_validates() -> None:
    catalog = load_catalogue_execution_map(reload=True)
    assert catalog.entries
    assert all(entry.coe_verified or not entry.auto_execute_eligible for entry in catalog.entries)


def test_auto_execute_requires_coe_verified() -> None:
    with pytest.raises(ValueError, match="coe_verified"):
        CatalogueExecutionBinding(
            question_ref="q0.q001",
            execution_mode="governed_template",
            spl_template_id="x",
            coe_verified=False,
            auto_execute_eligible=True,
        )


def test_resolve_by_question_ref() -> None:
    binding = resolve_catalogue_execution_binding(question_ref="q0.q046", use_case_id=None)
    assert binding is not None
    assert binding.spl_template_id == "auth_failed_login_spike"
