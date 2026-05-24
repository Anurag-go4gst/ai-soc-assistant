from fastapi import APIRouter, HTTPException

from app.demo.scenarios import list_demo_scenarios, run_demo_scenario
from app.schemas.responses import PlaceholderResponse

router = APIRouter(prefix="/scenarios", tags=["scenarios"])
demo_router = APIRouter(prefix="/demo/scenarios", tags=["demo-scenarios"])


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
    scenarios = list_demo_scenarios()
    return {
        "demo_mode": True,
        "evidence_origin": "coe_synthetic_fixture",
        "no_live_customer_data": True,
        "scenarios": scenarios,
        "count": len(scenarios),
    }


@demo_router.post("/{scenario_id}/run", response_model=PlaceholderResponse)
def run_demo_scenario_fixture(scenario_id: str) -> PlaceholderResponse:
    try:
        payload = run_demo_scenario(scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown demo scenario") from exc
    return PlaceholderResponse(**payload)
