from __future__ import annotations

from app.chat.deterministic_route_plan_builder import build_deterministic_route_plan_candidate
from app.routing.route_plan_validator import validate_route_plan_candidate
from app.use_cases.registry import match_use_cases


def test_aws_security_group_catalog_builds_valid_deterministic_route_plan() -> None:
    query = "Write SPL to determine who made modifications to any AWS security groups"
    selected = match_use_cases(query, limit=1)[0]

    plan = build_deterministic_route_plan_candidate(
        query=query,
        selected_use_case=selected,
        query_understanding=None,
    )

    assert plan is not None
    assert plan["pattern_id"] == "aws_security_group_modifications"
    assert plan["evidence_needs"]["template_id"] == "aws_security_group_modifications"
    assert plan["source_class"] == "aws_cloudtrail"
    validation = validate_route_plan_candidate(plan)
    assert validation.is_valid, validation.blocking_findings
