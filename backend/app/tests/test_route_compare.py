from app.routing.deterministic_router import route_intent
from app.routing.llm_planner import plan_route
from app.routing.route_adjudicator import adjudicate_route
from app.routing.route_compare import compare_routes


def test_route_compare_and_adjudicate() -> None:
    planner = plan_route("brute force login activity")
    deterministic = route_intent("brute force login activity")
    comparison = compare_routes(planner, deterministic)
    adjudicated = adjudicate_route(comparison)

    assert comparison["match"] is False
    assert adjudicated["selected"]["source"] == "deterministic_router"
