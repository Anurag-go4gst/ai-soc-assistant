from __future__ import annotations

from app.orchestration.workflow_planner import SOURCE_IDS
from app.query_understanding.models import OutputTemplate, RequestedOutputType
from app.routing.skills import validate_skill
from app.threat.mitre_kb import MITRE_MAPPING_STATUSES
from app.use_cases.registry import get_use_case


def validate_requested_output_type(value: str) -> str:
    try:
        return RequestedOutputType(value).value
    except ValueError as exc:
        raise ValueError(f"invalid requested_output_type: {value}") from exc


def validate_output_template(value: str) -> str:
    try:
        return OutputTemplate(value).value
    except ValueError as exc:
        raise ValueError(f"invalid output_template: {value}") from exc


def validate_use_case_id(value: str) -> str:
    if get_use_case(value) is None:
        raise ValueError(f"invalid use_case_id: {value}")
    return value


def validate_skill_id(value: str) -> str:
    return validate_skill(value)


def validate_source_id(value: str) -> str:
    if value not in SOURCE_IDS:
        raise ValueError(f"invalid source_id: {value}")
    return value


def validate_mitre_status(value: str) -> str:
    if value not in MITRE_MAPPING_STATUSES:
        raise ValueError(f"invalid mitre status: {value}")
    return value
