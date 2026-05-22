from fastapi import APIRouter

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
def list_scenarios() -> dict[str, list[str]]:
    return {
        "scenario_packs": [
            "brute_force",
            "db_pool_exhaustion",
            "ot_grid_anomaly",
        ]
    }
