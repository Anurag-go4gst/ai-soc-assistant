from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

TEMPLATES_PATH = Path(__file__).with_name("templates.json")

QUERY_SHAPE_RAW_SEARCH = "raw_search"
QUERY_SHAPE_TSTATS_DATAMODEL = "tstats_datamodel"
QUERY_SHAPE_FROM_DATAMODEL = "from_datamodel"
SUPPORTED_QUERY_SHAPES = (
    QUERY_SHAPE_RAW_SEARCH,
    QUERY_SHAPE_TSTATS_DATAMODEL,
    QUERY_SHAPE_FROM_DATAMODEL,
)

VALIDATOR_PROFILE_RAW_SEARCH = "raw_search_v1"
VALIDATOR_PROFILE_TSTATS_DATAMODEL = "cim_tstats_datamodel_v1"
VALIDATOR_PROFILE_FROM_DATAMODEL = "cim_from_datamodel_v1"


class EvidenceOutputContract(BaseModel):
    """Stage 3K-Q1B evidence-output contract for downstream evidence builders.

    Aligned with Stage 3K.1A aggregate safety: model-consumed packages must receive
    precomputed safe aggregates only and must never imply summed per-source counts.
    """

    output_type: str  # e.g. ranked_entities, raw_events, timechart, distinct_count
    entity_field: str | None = None
    metric_field: str | None = None
    sort_order: str | None = None
    supports_global_aggregates: bool = False
    model_safe_aggregates_only: bool = True


class SplTemplateDefinition(BaseModel):
    """SPL template definition.

    Stage 3K-Q1B extends the schema with CIM/tstats/datamodel readiness metadata.
    Existing raw-search templates continue to load unchanged because every new
    field is optional and ``query_shape`` defaults to ``raw_search``.
    """

    template_id: str
    status: str
    use_case_id: str
    name: str | None = None
    description: str | None = None
    query_shape: str = QUERY_SHAPE_RAW_SEARCH
    datamodel: str | None = None
    dataset: str | None = None
    cim_fields: list[str] = Field(default_factory=list)
    required_entities: list[str] = Field(default_factory=list)
    optional_entities: list[str] = Field(default_factory=list)
    required_parameters: list[str] = Field(default_factory=list)
    optional_parameters: list[str] = Field(default_factory=list)
    aggregation_shape: str | None = None
    group_by_fields: list[str] = Field(default_factory=list)
    metric_fields: list[str] = Field(default_factory=list)
    allowed_metrics: list[str] = Field(default_factory=list)
    time_bound_required: bool = False
    result_limit_required: bool = False
    summariesonly_required: bool = False
    validator_profile: str | None = None
    evidence_output_contract: EvidenceOutputContract | None = None
    enabled: bool | None = None
    production_ready: bool | None = None
    sample_only: bool = False
    safety_notes: str | None = None
    default_time_window: str | None = None
    spl_text: str | None = None
    returned_fields: list[str] = Field(default_factory=list)
    validation_rules: dict[str, object] = Field(default_factory=dict)
    result_limits: dict[str, object] = Field(default_factory=dict)
    severity_inputs: list[str] = Field(default_factory=list)
    answer_sections_supported: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_query_shape_contract(self) -> "SplTemplateDefinition":
        if self.query_shape not in SUPPORTED_QUERY_SHAPES:
            raise ValueError(f"unsupported query_shape: {self.query_shape}")

        if self.query_shape == QUERY_SHAPE_RAW_SEARCH:
            # raw_search keeps its original behavior; CIM metadata is not required.
            return self

        # Local import avoids a circular dependency between the registry and the
        # validator, while still letting us reuse the Q1A allowlists as the single
        # source of truth.
        from app.safeguards.spl_validator import (
            APPROVED_DATAMODELS,
            APPROVED_DATASETS,
            DATAMODEL_FIELD_ALLOWLIST,
        )

        if not self.datamodel:
            raise ValueError(f"{self.query_shape} template missing datamodel")
        if self.datamodel not in APPROVED_DATAMODELS:
            raise ValueError(f"{self.query_shape} template has unknown datamodel: {self.datamodel}")
        if self.dataset and self.dataset not in APPROVED_DATASETS.get(self.datamodel, set()):
            raise ValueError(
                f"{self.query_shape} template has unknown dataset {self.dataset} for {self.datamodel}"
            )
        if not self.validator_profile:
            raise ValueError(f"{self.query_shape} template missing validator_profile")
        if not self.time_bound_required:
            raise ValueError(f"{self.query_shape} template must set time_bound_required=true")
        if not self.result_limit_required:
            raise ValueError(f"{self.query_shape} template must set result_limit_required=true")

        allowed_fields = DATAMODEL_FIELD_ALLOWLIST.get(self.datamodel, set())
        declared_fields = set(self.cim_fields) | set(self.group_by_fields) | set(self.metric_fields)
        for field_name in declared_fields:
            # metric_fields can be raw alias names (e.g. failed_login_count); only
            # cim_fields and group_by_fields are required to match the CIM allowlist.
            if field_name in self.metric_fields and field_name not in self.cim_fields:
                continue
            if field_name not in allowed_fields:
                raise ValueError(
                    f"{self.query_shape} template references unknown CIM field "
                    f"{field_name} for datamodel {self.datamodel}"
                )

        if self.query_shape == QUERY_SHAPE_TSTATS_DATAMODEL:
            if self.validator_profile != VALIDATOR_PROFILE_TSTATS_DATAMODEL:
                raise ValueError(
                    f"tstats_datamodel template must use validator_profile "
                    f"{VALIDATOR_PROFILE_TSTATS_DATAMODEL}"
                )
            if not self.summariesonly_required:
                raise ValueError("tstats_datamodel template must set summariesonly_required=true")
            non_aggregate = self.aggregation_shape == "non_aggregate"
            if not (self.group_by_fields or self.metric_fields or non_aggregate):
                raise ValueError(
                    "tstats_datamodel template must declare group_by/metric fields "
                    "or aggregation_shape='non_aggregate'"
                )

        if self.query_shape == QUERY_SHAPE_FROM_DATAMODEL:
            if self.validator_profile != VALIDATOR_PROFILE_FROM_DATAMODEL:
                raise ValueError(
                    f"from_datamodel template must use validator_profile "
                    f"{VALIDATOR_PROFILE_FROM_DATAMODEL}"
                )
            if not (self.cim_fields or self.group_by_fields or self.metric_fields):
                raise ValueError(
                    "from_datamodel template must declare selected or aggregation fields"
                )

        return self

    def is_production_executable(self) -> bool:
        """Production executable = active, explicitly enabled, production_ready, not sample-only."""
        if self.status != "active":
            return False
        if self.sample_only:
            return False
        if self.enabled is False:
            return False
        if self.production_ready is False:
            return False
        return True


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
        "query_shape": template.query_shape,
        "datamodel": template.datamodel,
        "validator_profile": template.validator_profile,
        "returned_fields": template.returned_fields,
        "validation_rules": template.validation_rules,
        "result_limits": template.result_limits,
        "answer_sections_supported": template.answer_sections_supported,
    }


def supported_query_shapes() -> list[str]:
    return list(SUPPORTED_QUERY_SHAPES)


def enabled_templates() -> list[SplTemplateDefinition]:
    return [t for t in load_spl_templates() if t.is_production_executable()]


def disabled_templates() -> list[SplTemplateDefinition]:
    return [t for t in load_spl_templates() if not t.is_production_executable()]


def templates_by_datamodel(datamodel: str) -> list[SplTemplateDefinition]:
    return [t for t in load_spl_templates() if t.datamodel == datamodel]


def templates_by_query_shape(query_shape: str) -> list[SplTemplateDefinition]:
    return [t for t in load_spl_templates() if t.query_shape == query_shape]


def registry_metadata() -> dict[str, Any]:
    templates = load_spl_templates()
    return {
        "supported_query_shapes": supported_query_shapes(),
        "total_templates": len(templates),
        "enabled_template_ids": [t.template_id for t in templates if t.is_production_executable()],
        "disabled_template_ids": [t.template_id for t in templates if not t.is_production_executable()],
        "sample_only_template_ids": [t.template_id for t in templates if t.sample_only],
        "templates_by_query_shape": {
            shape: [t.template_id for t in templates if t.query_shape == shape]
            for shape in SUPPORTED_QUERY_SHAPES
        },
        "templates_by_datamodel": {
            t.datamodel: [x.template_id for x in templates if x.datamodel == t.datamodel]
            for t in templates
            if t.datamodel
        },
        "validator_profiles": sorted(
            {t.validator_profile for t in templates if t.validator_profile}
        ),
    }
