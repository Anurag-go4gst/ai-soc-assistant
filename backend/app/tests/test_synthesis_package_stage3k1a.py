from __future__ import annotations

import json
from typing import Any

from app.actions.capability_policy import action_capability_for
from app.synthesis.models import build_governed_synthesis_package
from app.threat.mitre_kb import map_mitre_for_use_case


def _source_evidence_with_per_source_distinct_counts() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "ev-splunk-failed-app01",
            "collection_status": "collected",
            "source_type": "splunk_mcp",
            "preview_rows": [
                {"host": "APP-01", "src": "10.10.4.21", "failed_logins": 42, "distinct_users": 7},
                {"host": "APP-01", "src": "10.10.4.22", "failed_logins": 31, "distinct_users": 4},
                {"host": "APP-01", "src": "10.10.4.19", "failed_logins": 28, "distinct_users": 3},
            ],
        }
    ]


def _structured_context() -> dict[str, Any]:
    return {
        "trace_id": "trace-stage3k1a",
        "selected_skill": "attack_discovery",
        "metrics": {"collected_evidence_count": 1, "total_result_count": 3},
        "missing_evidence": [
            "privileged_account_status",
            "cmdb_asset_criticality",
            "success_after_failure",
            "post_login_activity",
        ],
        "structured_facts": [
            {
                "fact_id": "fact-001",
                "statement": "APP-01 shows repeated failed authentication from three source IPs.",
                "source_refs": ["ev-splunk-failed-app01"],
            }
        ],
    }


def _package() -> dict[str, Any]:
    package = build_governed_synthesis_package(
        structured_context=_structured_context(),
        source_evidence=_source_evidence_with_per_source_distinct_counts(),
        mitre_mappings=map_mitre_for_use_case("auth_failed_login_spike", ["ev-splunk-failed-app01"]),
        action_capability=action_capability_for("auth_failed_login_spike", "P2 High"),
    )
    return package.model_dump()


def test_per_source_distinct_counts_remain_trace_only_and_are_not_summed() -> None:
    source_evidence = _source_evidence_with_per_source_distinct_counts()
    assert [row["distinct_users"] for row in source_evidence[0]["preview_rows"]] == [7, 4, 3]

    package = _package()
    aggregates = package["precomputed_aggregates"]

    assert aggregates == [
        {
            "aggregate_key": "global_distinct_users",
            "value": None,
            "status": "not_available",
            "source": "not_available",
            "computed_by": "not_available",
            "evidence_refs": [],
            "safe_for_model_use": False,
        }
    ]
    assert 14 not in json.loads(json.dumps(package)).values()


def test_synthesis_package_contains_no_per_source_distinct_user_fields() -> None:
    package = _package()
    serialized = json.dumps(package, sort_keys=True)

    assert "per_source_distinct_users" not in serialized
    assert "distinct_users_by_source" not in serialized
    assert "unique_users_by_source" not in serialized
    assert serialized.count("global_distinct_users") == 1
    assert "preview_rows" not in serialized


def test_missing_evidence_uses_unknown_wording_not_negative_claims() -> None:
    package = _package()
    missing = {item["evidence_key"]: item for item in package["missing_evidence"]}

    assert missing["privileged_account_status"]["analyst_wording"] == "privileged-account status is not yet available"
    assert missing["cmdb_asset_criticality"]["analyst_wording"] == "CMDB asset criticality is not yet available"
    serialized = json.dumps(package).lower()
    assert "no privileged" not in serialized
    assert "non-critical" not in serialized


def test_permitted_mitre_set_is_deterministic_and_t1078_requires_validation_without_session_evidence() -> None:
    package = _package()
    techniques = {item["technique_id"]: item for item in package["permitted_mitre_techniques"]}

    assert set(techniques) == {"T1110.001", "T1078"}
    assert techniques["T1110.001"]["status"] == "supported"
    assert techniques["T1078"]["status"] == "requires_validation"
    assert package["guard_constraints"]["model_may_introduce_new_mitre"] is False
    assert package["guard_constraints"]["mitre_must_be_from_permitted_set"] is True


def test_actions_are_capped_at_tier1_and_blocked_actions_have_no_execution_path() -> None:
    package = _package()
    constraints = package["guard_constraints"]
    actions = {item["action_id"]: item for item in package["permitted_actions"]}

    assert constraints["max_action_tier"] == 1
    assert constraints["no_raw_spl_execution"] is True
    assert constraints["no_remediation_actions"] is True
    for action_id in ("block_ip", "disable_user", "isolate_endpoint", "containment", "close_incident", "remediation", "write_action"):
        assert actions[action_id]["allowed"] is False
        assert actions[action_id]["execution_path"] == "none"
    assert actions["generate_spl"]["allowed"] is True
    assert actions["generate_spl"]["tier"] == 1


def test_safe_global_distinct_users_requires_explicit_provenance() -> None:
    context = _structured_context()
    context["metrics"]["global_distinct_users"] = 9
    context["aggregate_provenance"] = {
        "global_distinct_users.source": "splunk",
        "global_distinct_users.computed_by": "splunk_global_query",
    }

    package = build_governed_synthesis_package(
        structured_context=context,
        source_evidence=_source_evidence_with_per_source_distinct_counts(),
        mitre_mappings=[],
        action_capability=action_capability_for("auth_failed_login_spike", "P2 High"),
    ).model_dump()

    assert package["precomputed_aggregates"][0]["aggregate_key"] == "global_distinct_users"
    assert package["precomputed_aggregates"][0]["value"] == 9
    assert package["precomputed_aggregates"][0]["source"] == "splunk"
    assert package["precomputed_aggregates"][0]["computed_by"] == "splunk_global_query"
    assert package["precomputed_aggregates"][0]["safe_for_model_use"] is True
