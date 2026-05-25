from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

TEMPLATES_PATH = Path(__file__).with_name("templates.json")


class SplTemplateDefinition(BaseModel):
    template_id: str
    status: str
    use_case_id: str
    required_entities: list[str] = Field(default_factory=list)
    default_time_window: str | None = None
    spl_text: str | None = None
    returned_fields: list[str] = Field(default_factory=list)
    validation_rules: dict[str, object] = Field(default_factory=dict)
    result_limits: dict[str, object] = Field(default_factory=dict)
    severity_inputs: list[str] = Field(default_factory=list)
    answer_sections_supported: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def load_spl_templates() -> list[SplTemplateDefinition]:
    payload = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))
    return [SplTemplateDefinition(**item) for item in payload.get("templates", [])]


def get_spl_template(template_id: str | None) -> SplTemplateDefinition | None:
    if not template_id:
        return None
    return next((item for item in load_spl_templates() if item.template_id == template_id), None)


def template_summary(template_id: str | None) -> dict[str, object] | None:
    template = get_spl_template(template_id)
    if not template:
        return None
    return {
        "template_id": template.template_id,
        "status": template.status,
        "use_case_id": template.use_case_id,
        "returned_fields": template.returned_fields,
        "validation_rules": template.validation_rules,
        "result_limits": template.result_limits,
        "answer_sections_supported": template.answer_sections_supported,
    }
