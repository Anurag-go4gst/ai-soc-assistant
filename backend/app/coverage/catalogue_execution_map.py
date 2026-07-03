"""COE-verified catalogue execution bindings (DG-5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

_MAP_PATH = Path(__file__).resolve().parent / "catalogue_execution_map_v1.json"
_CACHE: dict[str, Any] | None = None

ExecutionMode = Literal["governed_template", "saved_search"]


class CatalogueExecutionBinding(BaseModel):
    question_ref: str | None = None
    use_case_id: str | None = None
    match_paths: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode
    spl_template_id: str | None = None
    saved_search_name: str | None = None
    saved_search_app: str | None = "search"
    coe_verified: bool = False
    auto_execute_eligible: bool = False
    spl_template_fallback: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_binding(self) -> "CatalogueExecutionBinding":
        if self.auto_execute_eligible and not self.coe_verified:
            raise ValueError("auto_execute_eligible requires coe_verified")
        if self.execution_mode == "governed_template" and not self.spl_template_id:
            raise ValueError("governed_template requires spl_template_id")
        if self.execution_mode == "saved_search" and not self.saved_search_name:
            raise ValueError("saved_search requires saved_search_name")
        if not self.question_ref and not self.use_case_id:
            raise ValueError("question_ref or use_case_id required")
        return self


class CatalogueExecutionMap(BaseModel):
    map_version: str
    entries: list[CatalogueExecutionBinding]


def load_catalogue_execution_map(*, reload: bool = False) -> CatalogueExecutionMap:
    global _CACHE
    if not reload and _CACHE is not None:
        return CatalogueExecutionMap.model_validate(_CACHE)
    payload = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    model = CatalogueExecutionMap.model_validate(payload)
    _CACHE = model.model_dump()
    return model


def resolve_catalogue_execution_binding(
    *,
    question_ref: str | None,
    use_case_id: str | None,
) -> CatalogueExecutionBinding | None:
    catalog = load_catalogue_execution_map()
    ref = str(question_ref or "").strip() or None
    case_id = str(use_case_id or "").strip() or None
    for entry in catalog.entries:
        if ref and entry.question_ref == ref:
            return entry
    for entry in catalog.entries:
        if case_id and entry.use_case_id == case_id:
            return entry
    return None
