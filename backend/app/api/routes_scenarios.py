from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.demo import ec_actions
from app.demo.ec_query_match import resolve_ec_query_fuzzy, suggest_ec_queries
from app.demo.ec_response import ExperienceCenterResponse
from app.demo.ec_turn import UnknownFollowUpError, run_experience_center_turn
from app.demo.scenarios import (
    list_demo_scenarios,
    list_experience_center_scenarios,
    run_demo_scenario,
)
from app.schemas.responses import PlaceholderResponse

router = APIRouter(prefix="/scenarios", tags=["scenarios"])
demo_router = APIRouter(prefix="/demo/scenarios", tags=["demo-scenarios"])
ec_catalog_router = APIRouter(prefix="/demo/experience-center", tags=["demo-experience-center"])
ec_actions_router = APIRouter(prefix="/demo/ec-actions", tags=["demo-ec-actions"])


class EcFollowUpBody(BaseModel):
    follow_up_id: str
    session_id: str | None = None


class EcActionBody(BaseModel):
    session_id: str | None = None
    scenario_id: str | None = None
    kind: str | None = None
    label: str | None = None


class EcActionExecuteBody(BaseModel):
    draft: dict[str, Any] | None = None
    action: dict[str, Any] | None = None


class EcActionMutateBody(BaseModel):
    action: dict[str, Any] | None = None


class EcQueryResolveBody(BaseModel):
    query: str
    min_score: float = 0.38


@router.get("")
def list_scenarios() -> dict[str, list[str]]:
    return {
        "scenario_packs": [
            "brute_force",
            "db_pool_exhaustion",
            "ot_grid_anomaly",
        ]
    }


@demo_router.get("")
def list_demo_scenario_fixtures() -> dict[str, object]:
    """Frozen ChatPanel contract. Do not add Flagship/Lab here."""
    scenarios = list_demo_scenarios()
    return {
        "demo_mode": True,
        "evidence_origin": "coe_synthetic_fixture",
        "no_live_customer_data": True,
        "scenarios": scenarios,
        "count": len(scenarios),
    }


@ec_catalog_router.get("/scenarios")
def list_experience_center_catalog() -> dict[str, object]:
    """EC /scenarios picker only. ChatPanel must not call this."""
    scenarios = list_experience_center_scenarios()
    return {
        "demo_mode": True,
        "evidence_origin": "coe_synthetic_fixture",
        "no_live_customer_data": True,
        "catalog": "experience_center",
        "scenarios": scenarios,
        "count": len(scenarios),
    }


def run_demo_scenario_fixture(scenario_id: str) -> PlaceholderResponse:
    """PlaceholderResponse helper for tests and default-off /chat parity.

    HTTP /demo/scenarios/{id}/run uses ExperienceCenterResponse via
    ``run_experience_center_turn``. The frozen picker client still POSTs this path; extra EC
    fields are ignored by that client.
    """
    try:
        payload = run_demo_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown demo scenario") from exc
    return PlaceholderResponse(**payload)


@demo_router.post("/{scenario_id}/run", response_model=ExperienceCenterResponse)
def run_experience_center_scenario(scenario_id: str, session_id: str | None = None) -> ExperienceCenterResponse:
    try:
        return run_experience_center_turn(scenario_id, session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown demo scenario") from exc


@demo_router.post("/{scenario_id}/follow-up", response_model=ExperienceCenterResponse)
def follow_up_experience_center_scenario(scenario_id: str, body: EcFollowUpBody) -> ExperienceCenterResponse:
    try:
        return run_experience_center_turn(
            scenario_id,
            session_id=body.session_id,
            follow_up_id=body.follow_up_id,
        )
    except UnknownFollowUpError as exc:
        raise HTTPException(status_code=404, detail="Unknown follow-up") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown demo scenario") from exc


@ec_actions_router.post("/prepare", response_model=dict)
def prepare_ec_action(body: EcActionBody) -> dict:
    if not body.kind or not body.scenario_id:
        raise HTTPException(status_code=400, detail="kind_and_scenario_required")
    try:
        record = ec_actions.prepare_action(
            kind=body.kind,
            label=body.label or body.kind,
            session_id=body.session_id,
            scenario_id=body.scenario_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return record.model_dump()


@ec_catalog_router.get("/query-suggestions")
def experience_center_query_suggestions(q: str = "", limit: int = 8) -> dict[str, object]:
    suggestions = suggest_ec_queries(q, limit=min(max(limit, 1), 12))
    return {"query": q, "suggestions": suggestions, "count": len(suggestions)}


@ec_catalog_router.post("/resolve-query")
def experience_center_resolve_query(body: EcQueryResolveBody) -> dict[str, object]:
    scenario_id, score = resolve_ec_query_fuzzy(body.query, min_score=body.min_score)
    if scenario_id is None:
        return {"query": body.query, "scenario_id": None, "score": round(score, 3), "matched": False}
    return {"query": body.query, "scenario_id": scenario_id, "score": round(score, 3), "matched": True}


@ec_actions_router.post("/{action_id}/approve")
def approve_ec_action(action_id: str, body: EcActionMutateBody | None = None) -> dict:
    try:
        return ec_actions.approve_action(action_id, snapshot=(body.action if body else None)).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown EC action") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@ec_actions_router.post("/{action_id}/execute")
def execute_ec_action(action_id: str, body: EcActionExecuteBody | None = None) -> dict:
    try:
        record = ec_actions.execute_action(
            action_id,
            draft=(body.draft if body else None),
            snapshot=(body.action if body else None),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown EC action") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    dumped = record.model_dump()
    if dumped.get("production_side_effect") is not False:
        raise HTTPException(status_code=500, detail="production_side_effect_must_be_false")
    return dumped


@ec_actions_router.post("/{action_id}/verify")
def verify_ec_action(action_id: str, body: EcActionMutateBody | None = None) -> dict:
    try:
        return ec_actions.verify_action(action_id, snapshot=(body.action if body else None)).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown EC action") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
