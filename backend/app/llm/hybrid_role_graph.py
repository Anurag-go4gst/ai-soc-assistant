"""P2-B adaptive multi-role hybrid graph — deterministic role planner.

Plans which LLM roles may run on a turn, their stage, dependencies, consumers,
skip reasons, and prompt versions. The live pipeline consults this plan before
each blocking hop; deterministic authority and P2-A pre-hop budget gates still
apply on top.

This is the cost-bounded orchestration layer required before expanding the full
multi-role graph. It does not call models itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from app.chat.guidance_templates import is_unsafe_blocked_path
from app.chat.skill_contribution import derive_boundary_class
from app.config import settings
from app.llm.prompts import PROMPT_CONTRACTS
from app.llm.sidecar_skip_policy import should_skip_sidecar

# Ordered pipeline stages (plan P2-B §1).
HYBRID_STAGES: tuple[str, ...] = (
    "understand",
    "skill_select",
    "retrieve",
    "specialist",
    "synthesize",
    "critique",
    "repair",
)

_INVESTIGATION_SKILLS = frozenset(
    {"guided_investigation", "attack_discovery", "alert_summary", "spl_generation"}
)
_COMPLEXITY_DEADLINE_BONUS = {"low": 0.0, "medium": 25.0, "high": 50.0}
_MAX_TURN_DEADLINE = 300.0  # ceiling for base + complexity bonus; see docs/architecture/llm_budget_model.md


def prompt_version_hash(role: str) -> str | None:
    contract = PROMPT_CONTRACTS.get(role)
    if not contract:
        return None
    payload = {
        "role": role,
        "purpose": contract.get("purpose"),
        "system_instruction": contract.get("system_instruction"),
        "output_schema": contract.get("output_schema"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return digest[:16]


@dataclass(frozen=True)
class HybridRoleNode:
    role_id: str
    stage: str
    enabled: bool
    skip_reason: str | None
    consumer: str
    depends_on: tuple[str, ...] = ()
    prompt_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "stage": self.stage,
            "enabled": self.enabled,
            "skip_reason": self.skip_reason,
            "consumer": self.consumer,
            "depends_on": list(self.depends_on),
            "prompt_version": self.prompt_version,
        }


@dataclass
class HybridRolePlan:
    stages: list[str]
    roles: list[HybridRoleNode]
    complexity_tier: str
    deadline_seconds: float

    def role_enabled(self, role_id: str) -> bool:
        for node in self.roles:
            if node.role_id == role_id:
                return node.enabled
        return False

    def skip_reason(self, role_id: str) -> str | None:
        for node in self.roles:
            if node.role_id == role_id:
                return node.skip_reason
        return None

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "stages": list(self.stages),
            "complexity_tier": self.complexity_tier,
            "deadline_seconds": self.deadline_seconds,
            "roles": [r.to_dict() for r in self.roles],
        }


def compute_complexity_tier(
    *,
    match_path: str | None,
    selected_skill: str | None,
    soc_investigation_shaped: bool = False,
    multi_leg: bool = False,
) -> str:
    if multi_leg or soc_investigation_shaped:
        return "high"
    path = str(match_path or "")
    skill = str(selected_skill or "")
    if path in {"out_of_registry", "near_105_question", "semantic_105_question"}:
        return "medium"
    if skill in _INVESTIGATION_SKILLS:
        return "medium"
    return "low"


def compute_turn_deadline_seconds(
    *,
    match_path: str | None = None,
    selected_skill: str | None = None,
    soc_investigation_shaped: bool = False,
    multi_leg: bool = False,
) -> float:
    base = float(getattr(settings, "ai_soc_llm_turn_deadline_seconds", 75.0) or 75.0)
    tier = compute_complexity_tier(
        match_path=match_path,
        selected_skill=selected_skill,
        soc_investigation_shaped=soc_investigation_shaped,
        multi_leg=multi_leg,
    )
    bonus = _COMPLEXITY_DEADLINE_BONUS.get(tier, 0.0)
    return min(_MAX_TURN_DEADLINE, base + bonus)


def _node(
    role_id: str,
    *,
    stage: str,
    enabled: bool,
    skip_reason: str | None,
    consumer: str,
    depends_on: tuple[str, ...] = (),
) -> HybridRoleNode:
    return HybridRoleNode(
        role_id=role_id,
        stage=stage,
        enabled=enabled,
        skip_reason=skip_reason,
        consumer=consumer,
        depends_on=depends_on,
        prompt_version=prompt_version_hash(role_id),
    )



def _boundary_blocks_llm_roles(
    *,
    query: str,
    path_type: str | None,
    skip_composer_reason: str | None,
) -> str | None:
    """Return a boundary class when every LLM role must stay off for this turn."""
    boundary = derive_boundary_class(query)
    if boundary:
        return boundary
    if is_unsafe_blocked_path(path_type):
        return "unsafe_execution"
    if skip_composer_reason in {
        "unsafe_blocked_deterministic_guidance",
        "explicit_run_spl_deterministic_guidance",
    }:
        return "unsafe_execution"
    return None


def build_hybrid_role_plan(
    *,
    query: str,
    match_path: str | None,
    selected_skill: str | None,
    answer_contract: Any | None,
    path_type: str | None,
    intent_family: str | None,
    draft_preview_active: bool,
    skip_composer: bool,
    skip_composer_reason: str | None,
    intent_advisory_skipped: bool,
    intent_skip_reason: str | None,
    soc_investigation_shaped: bool = False,
    multi_leg: bool = False,
) -> HybridRolePlan:
    """Deterministic adaptive graph for finalize-stage LLM roles."""
    boundary_class = _boundary_blocks_llm_roles(
        query=query,
        path_type=path_type,
        skip_composer_reason=skip_composer_reason,
    )
    tier = compute_complexity_tier(
        match_path=match_path,
        selected_skill=selected_skill,
        soc_investigation_shaped=soc_investigation_shaped,
        multi_leg=multi_leg,
    )
    deadline = compute_turn_deadline_seconds(
        match_path=match_path,
        selected_skill=selected_skill,
        soc_investigation_shaped=soc_investigation_shaped,
        multi_leg=multi_leg,
    )

    if boundary_class:
        boundary_skip = f"{boundary_class}_blocks_llm_roles"
        roles = [
            _node(
                role_id,
                stage=stage,
                enabled=False,
                skip_reason=boundary_skip,
                consumer=consumer,
                depends_on=depends_on,
            )
            for role_id, stage, consumer, depends_on in (
                ("intent_shadow_classifier", "understand", "build_query_to_intent", ()),
                ("missing_evidence_reasoner", "specialist", "answer_contract.limitations", ("retrieve",)),
                ("mitre_reasoner", "specialist", "analyst_response.foundation_sec_analysis", ("retrieve",)),
                ("risk_rationale_reasoner", "specialist", "analyst_response.severity_rationale", ("mitre_reasoner",)),
                (
                    "route_plan_candidate_generator",
                    "specialist",
                    "control_plane_trace.resource_plan_shadow",
                    ("retrieve",),
                ),
                ("governed_composer", "synthesize", "analyst_response.narrative", ("specialist",)),
                ("mcp_tool_plan_shadow", "critique", "control_plane_trace.mcp_tool_plan_shadow", ("synthesize",)),
            )
        ]
        return HybridRolePlan(
            stages=[],
            roles=roles,
            complexity_tier=tier,
            deadline_seconds=deadline,
        )

    contract_mode = getattr(answer_contract, "answer_mode", None) if answer_contract else None
    contract_hil = getattr(answer_contract, "hil_status", None) if answer_contract else None
    missing_evidence = list(getattr(answer_contract, "missing_evidence", None) or [])
    candidate_mitre = list(getattr(answer_contract, "candidate_mitre", None) or [])
    mitre_ids = list(getattr(answer_contract, "mitre_technique_ids", None) or [])

    t0_skip, t0_reason = should_skip_sidecar(match_path=match_path)
    intent_enabled = not intent_advisory_skipped and not t0_skip
    intent_skip = intent_skip_reason or (t0_reason if t0_skip else None)

    me_skip = None
    me_enabled = bool(answer_contract and missing_evidence)
    if not me_enabled:
        me_skip = "no_missing_evidence_context"
    else:
        skip, reason = should_skip_sidecar(answer_mode=contract_mode, hil_status=contract_hil)
        if skip:
            me_enabled = False
            me_skip = reason

    mitre_enabled = bool(answer_contract and (candidate_mitre or mitre_ids) and not draft_preview_active)
    mitre_skip = None
    if draft_preview_active:
        mitre_skip = "draft_spl_preview_active"
    elif not (candidate_mitre or mitre_ids):
        mitre_skip = "no_mitre_context"

    risk_enabled = bool(
        answer_contract
        and getattr(answer_contract, "severity_label", None)
        and not draft_preview_active
    )
    risk_skip = "draft_spl_preview_active" if draft_preview_active else (
        None if risk_enabled else "no_severity_context"
    )

    shadow_enabled = not draft_preview_active
    shadow_skip = "draft_spl_preview_active" if draft_preview_active else None

    composer_enabled = bool(
        answer_contract is not None
        and not skip_composer
        and not draft_preview_active
    )
    composer_skip = skip_composer_reason or (
        "draft_spl_preview_active" if draft_preview_active else "composer_skipped"
    )
    if skip_composer:
        composer_enabled = False

    tool_plan_enabled = not draft_preview_active
    tool_plan_skip = shadow_skip if not tool_plan_enabled else None

    roles = [
        _node(
            "intent_shadow_classifier",
            stage="understand",
            enabled=intent_enabled,
            skip_reason=intent_skip,
            consumer="build_query_to_intent",
        ),
        _node(
            "missing_evidence_reasoner",
            stage="specialist",
            enabled=me_enabled,
            skip_reason=me_skip,
            consumer="answer_contract.limitations",
            depends_on=("retrieve",),
        ),
        _node(
            "mitre_reasoner",
            stage="specialist",
            enabled=mitre_enabled,
            skip_reason=mitre_skip,
            consumer="analyst_response.foundation_sec_analysis",
            depends_on=("retrieve",),
        ),
        _node(
            "risk_rationale_reasoner",
            stage="specialist",
            enabled=risk_enabled,
            skip_reason=risk_skip,
            consumer="analyst_response.severity_rationale",
            depends_on=("mitre_reasoner",),
        ),
        _node(
            "route_plan_candidate_generator",
            stage="specialist",
            enabled=shadow_enabled,
            skip_reason=shadow_skip,
            consumer="control_plane_trace.resource_plan_shadow",
            depends_on=("retrieve",),
        ),
        _node(
            "governed_composer",
            stage="synthesize",
            enabled=composer_enabled,
            skip_reason=composer_skip if not composer_enabled else None,
            consumer="analyst_response.narrative",
            depends_on=("specialist",),
        ),
        _node(
            "mcp_tool_plan_shadow",
            stage="critique",
            enabled=tool_plan_enabled,
            skip_reason=tool_plan_skip,
            consumer="control_plane_trace.mcp_tool_plan_shadow",
            depends_on=("synthesize",),
        ),
    ]

    active_stages = [s for s in HYBRID_STAGES if any(r.stage == s and r.enabled for r in roles)]
    return HybridRolePlan(
        stages=active_stages,
        roles=roles,
        complexity_tier=tier,
        deadline_seconds=deadline,
    )
