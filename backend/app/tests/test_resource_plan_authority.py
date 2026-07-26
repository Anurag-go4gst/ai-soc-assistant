"""Guard tests — only plan_evidence_from_canonical may compose/commit ResourcePlan."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.chat.contracts.evidence_plan import EvidencePlan
from app.chat.plan_evidence_from_canonical import plan_evidence_from_canonical
from app.chat.canonical_handoff_builder import build_canonical_planning_input
from app.planner.composer import compose_resource_plan
from app.planner.resource_plan_authority import ResourcePlanAuthorityViolation
from app.query_understanding.parser import understand_query

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Item 23 classification table (spec §10) — production ``app/`` modules only.
_RESOURCE_PLAN_CONSTRUCTION: dict[str, str] = {
    "app/planner/composer.py": "approved_final_planner",
    "app/chat/guided_capability_validator.py": "validation",
    "app/planner/planner_hierarchy.py": "validation",
    "app/planner/llm_plan_bridge.py": "validation",
    "app/planner/plan_promotion_merge.py": "validation",
}

_COMPOSE_CALLER_ALLOWLIST = {
    "app/planner/composer.py",
    "app/chat/plan_evidence_from_canonical.py",
}

_COMMIT_CALLER_ALLOWLIST = {
    "app/chat/plan_evidence_from_canonical.py",
}

_EXECUTION_READ_MODULES = {
    "app/chat/guided_hybrid_executor.py",
    "app/planner/executor.py",
    "app/chat/canonical_execution_idempotency.py",
    "app/chat/canonical_planning_orchestrator.py",
}

_FORBIDDEN_COMMITTED_PLAN_MUTATORS = {
    "app/chat/guided_hybrid_executor.py",
    "app/chat/guided_hybrid_collection.py",
    "app/planner/executor.py",
    "app/chat/planning_telemetry.py",
    "app/chat/response_validation.py",
    "app/synthesis/governed_answer_composer.py",
}


def _app_py_files(*, include_tests: bool = False) -> list[Path]:
    paths = sorted((_REPO_ROOT / "app").rglob("*.py"))
    if include_tests:
        return paths
    return [path for path in paths if not _relative(path).startswith("app/tests/")]


def _relative(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _resource_plan_constructor_calls(path: Path) -> list[str]:
    """Return ``ResourcePlan(...)`` call sites (not the model class definition)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "ResourcePlan":
            hits.append(f"{path}:{node.lineno}")
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == "model_validate"
            and isinstance(func.value, ast.Name)
            and func.value.id == "ResourcePlan"
        ):
            continue
    return hits


def test_compose_resource_plan_requires_authority() -> None:
    from app.planner import resource_plan_authority as rpa

    plan = EvidencePlan(
        answer_mode="rag_only",
        rag_phase="rag_only",
        needs_rag=True,
        needs_spl=False,
        needs_mcp=False,
        needs_mitre=False,
        spl_allowed=False,
        mcp_allowed=False,
        policy_context_required=False,
        policy_context_recommended=False,
    )
    token = rpa._authority.set(None)
    try:
        with pytest.raises(ResourcePlanAuthorityViolation):
            compose_resource_plan(plan, intent_family="knowledge_only")
    finally:
        rpa._authority.reset(token)


def test_plan_evidence_from_canonical_is_approved_authority() -> None:
    query = "What is CVE-2026-12345?"
    qu = understand_query(query)
    canonical = build_canonical_planning_input(
        query=query,
        query_understanding=qu,
        routed={"skill": "knowledge_recall"},
        intent_classification={"intent_family": "reference_knowledge", "primary_intent": "knowledge_recall"},
        resolved_tier="T0",
        processing_lane="knowledge_short_circuit",
        handoff_id="cpi:authority-test",
    )
    plan, _, _ = plan_evidence_from_canonical(canonical, query_understanding=qu)
    assert plan.resource_plan is not None
    assert plan.resource_plan.get("provenance", {}).get("committed") is True


def test_only_approved_modules_compose_resource_plan() -> None:
    offenders: list[str] = []
    for path in _app_py_files():
        rel = _relative(path)
        if rel in _COMPOSE_CALLER_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if "compose_resource_plan(" in text or "compose_guided_resource_plan(" in text:
            offenders.append(rel)
    assert offenders == [], f"unexpected ResourcePlan composers: {offenders}"


def test_only_plan_evidence_from_canonical_commits_resource_plan() -> None:
    offenders: list[str] = []
    for path in _app_py_files():
        rel = _relative(path)
        if rel == "app/chat/canonical_handoff_store.py":
            continue
        if rel in _COMMIT_CALLER_ALLOWLIST:
            continue
        if "commit_resource_plan(" in path.read_text(encoding="utf-8"):
            offenders.append(rel)
    assert offenders == [], f"unexpected commit_resource_plan callers: {offenders}"


def test_resource_plan_direct_construction_classified() -> None:
    offenders: list[str] = []
    observed: dict[str, str] = {}
    for path in _app_py_files():
        rel = _relative(path)
        if rel == "app/planner/resource_plan.py":
            continue
        hits = _resource_plan_constructor_calls(path)
        if not hits:
            continue
        classification = _RESOURCE_PLAN_CONSTRUCTION.get(rel)
        observed[rel] = classification or "UNCLASSIFIED"
        if classification is None:
            offenders.extend(hits)
    assert offenders == [], (
        "ResourcePlan() construction outside classified modules: "
        f"{offenders}; observed={observed}"
    )
    assert set(observed) == set(_RESOURCE_PLAN_CONSTRUCTION), (
        "classification table drift — update _RESOURCE_PLAN_CONSTRUCTION: "
        f"observed={set(observed)}, expected={set(_RESOURCE_PLAN_CONSTRUCTION)}"
    )


def test_execution_modules_only_deserialize_resource_plan() -> None:
    offenders: list[str] = []
    for rel in _EXECUTION_READ_MODULES:
        path = _REPO_ROOT / rel
        if not path.exists():
            continue
        hits = _resource_plan_constructor_calls(path)
        if hits:
            offenders.extend(f"{rel}:{hit}" for hit in hits)
        text = path.read_text(encoding="utf-8")
        if "compose_resource_plan(" in text or "compose_guided_resource_plan(" in text:
            offenders.append(f"{rel}:compose_call")
        if "commit_resource_plan(" in text:
            offenders.append(f"{rel}:commit_call")
    assert offenders == [], f"execution/read modules must not compose/commit: {offenders}"


def test_guided_hybrid_and_telemetry_never_mutate_committed_plan() -> None:
    offenders: list[str] = []
    for rel in _FORBIDDEN_COMMITTED_PLAN_MUTATORS:
        path = _REPO_ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "compose_resource_plan(" in text or "compose_guided_resource_plan(" in text:
            offenders.append(f"{rel}:compose")
        if "commit_resource_plan(" in text:
            offenders.append(f"{rel}:commit")
        hits = _resource_plan_constructor_calls(path)
        if hits:
            offenders.append(f"{rel}:ResourcePlan()")
    assert offenders == [], f"committed-plan mutators found: {offenders}"


def test_resource_plan_authority_classification_table() -> None:
    """Pin the item-23 audit totals for completion-report §11."""
    compose_sites = 0
    commit_sites = 0
    construction_sites = 0
    deserialization_sites = 0
    for path in _app_py_files():
        rel = _relative(path)
        text = path.read_text(encoding="utf-8")
        if "compose_resource_plan(" in text or "compose_guided_resource_plan(" in text:
            compose_sites += text.count("compose_resource_plan(") + text.count(
                "compose_guided_resource_plan("
            )
        if "commit_resource_plan(" in text:
            commit_sites += text.count("commit_resource_plan(")
        if rel in _RESOURCE_PLAN_CONSTRUCTION:
            construction_sites += len(_resource_plan_constructor_calls(path))
        deserialization_sites += text.count("ResourcePlan.model_validate(")
    assert compose_sites >= 2
    assert commit_sites >= 2
    assert construction_sites >= len(_RESOURCE_PLAN_CONSTRUCTION)
    assert deserialization_sites >= 3
