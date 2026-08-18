from __future__ import annotations

import subprocess
from pathlib import Path
import sys

from app.actions.capability_policy import action_capability_for
from app.answer_guard.rules import (
    GUARD_IDS,
    GuardResult,
    guard_action_tier,
    guard_aggregate_overclaim,
    guard_clarification,
    guard_evidence_presence,
    guard_internal_leakage,
    guard_json_schema,
    guard_mitre_status,
    guard_priority_enum,
    guard_registry,
    guard_severity_authority,
    guard_sop_fidelity,
    guard_spl_execution,
    guard_splunk_table_fidelity,
)
from app.llm.adapter.role_results import adapt_llm_output


def _statuses(results: list[GuardResult]) -> list[str]:
    return [item.status for item in results]


def _has(results: list[GuardResult], status: str, guard_id: str) -> bool:
    return any(item.status == status and item.guard_id == guard_id for item in results)


def test_guard_ids_are_stable() -> None:
    assert set(GUARD_IDS) == {
        "guard.clarification",
        "guard.json_schema",
        "guard.registry",
        "guard.evidence_presence",
        "guard.aggregate_overclaim",
        "guard.sop_fidelity",
        "guard.mitre_status",
        "guard.severity_authority",
        "guard.action_tier",
        "guard.spl_execution",
        "guard.priority_enum",
        "guard.internal_leakage",
        "guard.splunk_table_fidelity",
    }


def test_clarification_guard_returns_finding_when_llm_skips_deterministic_clarification() -> None:
    results = guard_clarification({"clarification_needed": False}, {"clarification_required": True})

    assert _has(results, "fail", "guard.clarification")


def test_json_schema_and_registry_guards_use_adapter_result() -> None:
    valid = adapt_llm_output(
        role="spl_advisory_generator",
        raw_output='{"candidate_spl":"search index=pgcil_soc sourcetype=pgcil:auth | head 10","assumptions":[],"required_fields":[],"validation_notes":[],"execution_eligible":false}',
    )
    invalid = adapt_llm_output(role="spl_advisory_generator", raw_output='{"candidate_spl": }')

    assert _statuses(guard_json_schema(valid)) == ["pass"]
    assert _statuses(guard_registry(valid)) == ["pass"]
    assert _has(guard_json_schema(invalid), "fail", "guard.json_schema")
    assert _has(guard_registry(invalid), "fail", "guard.registry")


def test_aggregate_overclaim_prose_global_accounts_warns_without_global_distinct_users() -> None:
    results = guard_aggregate_overclaim({"analyst_summary": "14 targeted accounts were observed."}, {"total_failed_logins": 101})

    assert _has(results, "warn", "guard.aggregate_overclaim")


def test_aggregate_overclaim_structured_count_absent_from_evidence_fails() -> None:
    results = guard_aggregate_overclaim({"affected_accounts_count": 14}, {"total_failed_logins": 101})

    assert _has(results, "fail", "guard.aggregate_overclaim")


def test_aggregate_overclaim_structured_count_passes_when_supplied_by_evidence() -> None:
    results = guard_aggregate_overclaim({"affected_accounts_count": 14}, {"affected_accounts_count": 14})

    assert _statuses(results) == ["pass"]


def test_aggregate_overclaim_total_failed_logins_passes_when_supplied() -> None:
    results = guard_aggregate_overclaim({"total_failed_logins": 101}, {"total_failed_logins": 101})

    assert _statuses(results) == ["pass"]


def test_evidence_presence_structured_polarity_claims_require_evidence() -> None:
    assert _has(guard_evidence_presence({"privileged_account_impacted": True}, {}), "fail", "guard.evidence_presence")
    assert _has(guard_evidence_presence({"privileged_account_impacted": False}, {}), "fail", "guard.evidence_presence")
    assert _has(guard_evidence_presence({"app_critical": True}, {}), "fail", "guard.evidence_presence")
    assert _has(guard_evidence_presence({"app_critical": False}, {}), "fail", "guard.evidence_presence")


def test_evidence_presence_prose_mentions_warn_only() -> None:
    results = guard_evidence_presence({"analyst_summary": "Privileged accounts were not targeted."}, {})

    assert _has(results, "warn", "guard.evidence_presence")
    assert not _has(results, "fail", "guard.evidence_presence")


def test_evidence_presence_allows_deterministic_requires_validation_status() -> None:
    results = guard_evidence_presence({"mitre_mappings": [{"technique_id": "T1078", "status": "requires_validation"}]}, {})

    assert _statuses(results) == ["pass"]


def test_sop_fidelity_detects_wrong_version_and_hallucinated_id() -> None:
    results = guard_sop_fidelity(
        {"retrieved_playbook": {"sop_id": "FAKE-SOP", "version": "v9", "title": "Auth SOP"}},
        {"sop_id": "AUTH-001", "version": "v1", "title": "Auth SOP", "source_refs": ["sop.md#AUTH-001"]},
    )

    assert _has(results, "fail", "guard.sop_fidelity")


def test_sop_fidelity_detects_action_ids_instead_of_guidance() -> None:
    results = guard_sop_fidelity(
        {"retrieved_playbook": {"sop_id": "AUTH-001", "version": "v1", "title": "Auth SOP", "guidance": ["block_ip"]}},
        {"sop_id": "AUTH-001", "version": "v1", "title": "Auth SOP", "guidance": ["Validate scope before containment."], "source_refs": ["sop.md#AUTH-001"]},
    )

    assert _has(results, "fail", "guard.sop_fidelity")


def test_sop_fidelity_exact_guidance_passes() -> None:
    results = guard_sop_fidelity(
        {"retrieved_playbook": {"sop_id": "AUTH-001", "version": "v1", "title": "Auth SOP", "guidance": ["Validate scope before containment."]}},
        {"sop_id": "AUTH-001", "version": "v1", "title": "Auth SOP", "guidance": ["Validate scope before containment."], "source_refs": ["sop.md#AUTH-001"]},
    )

    assert _statuses(results) == ["pass"]


def test_mitre_status_cannot_upgrade_requires_validation_to_confirmed() -> None:
    results = guard_mitre_status({"mitre_mappings": [{"technique_id": "T1078", "status": "confirmed"}]}, {"T1078": "requires_validation"})

    assert _has(results, "fail", "guard.mitre_status")


def test_mitre_status_repeated_deterministic_status_passes() -> None:
    results = guard_mitre_status({"mitre_mappings": [{"technique_id": "T1110.001", "status": "supported"}]}, {"T1110.001": "supported"})

    assert _statuses(results) == ["pass"]


def test_mitre_equivalent_negative_phrase_without_status_change_is_not_flagged() -> None:
    results = guard_mitre_status(
        {"mitre_mappings": [{"technique_id": "T1078", "status": "requires_validation", "why": "T1078 is not confirmed."}]},
        {"T1078": "requires_validation"},
    )

    assert _statuses(results) == ["pass"]


def test_severity_authority_detects_conflict_and_allows_match() -> None:
    assert _has(guard_severity_authority({"severity_label": "P1 Critical", "why_not_higher": ["advisory"]}, "P3 Medium"), "fail", "guard.severity_authority")
    assert _statuses(guard_severity_authority({"severity_label": "P3 Medium", "why_not_higher": ["advisory"]}, "P3 Medium")) == ["pass"]


def test_priority_enum_requires_p_values_for_structured_priority() -> None:
    assert _has(guard_priority_enum({"priority": "High"}), "fail", "guard.priority_enum")
    assert _statuses(guard_priority_enum({"priority": "P1"})) == ["pass"]


def test_action_tier_blocks_remediation_under_tier_one_policy() -> None:
    policy = action_capability_for("auth_failed_login_spike", "P3 Medium").model_dump()
    results = guard_action_tier({"recommended_actions": ["block_ip"]}, policy)

    assert _has(results, "fail", "guard.action_tier")


def test_spl_execution_eligible_true_returns_finding() -> None:
    results = guard_spl_execution({"candidate_spl": "search index=pgcil_soc sourcetype=pgcil:auth | head 10", "execution_eligible": True})

    assert _has(results, "fail", "guard.spl_execution")


def test_adapter_already_forces_spl_execution_eligible_false() -> None:
    result = adapt_llm_output(
        role="spl_advisory_generator",
        raw_output='{"candidate_spl":"search index=pgcil_soc sourcetype=pgcil:auth | head 10","assumptions":[],"required_fields":[],"validation_notes":[],"execution_eligible":true}',
    )

    assert result.normalized_payload is not None
    assert result.normalized_payload["execution_eligible"] is False


def test_spl_guard_flags_invalid_spl_when_validator_called() -> None:
    results = guard_spl_execution({"candidate_spl": "delete index=pgcil_soc", "execution_eligible": False}, validate_candidate=True)

    assert _has(results, "fail", "guard.spl_execution")


def test_spl_guard_flags_candidate_spl_sent_to_mcp() -> None:
    results = guard_spl_execution({"candidate_spl": "search index=pgcil_soc", "sent_to_mcp": True})

    assert _has(results, "fail", "guard.spl_execution")


def test_internal_leakage_structured_field_fails_and_prose_warns() -> None:
    structured = guard_internal_leakage({"heading": "SourceEvidence"})
    prose = guard_internal_leakage({"analyst_summary": "This demo is not customer data."})

    assert _has(structured, "fail", "guard.internal_leakage")
    assert _has(prose, "warn", "guard.internal_leakage")


def test_internal_leakage_word_boundary_does_not_match_demonstrate() -> None:
    results = guard_internal_leakage({"analyst_summary": "The results demonstrate repeated failures."})

    assert _statuses(results) == ["pass"]


def test_splunk_table_fidelity_exact_rows_pass() -> None:
    rows = [{"host": "APP-01", "source_ip": "10.1.2.3", "failed_logins": 42, "first_seen": "10:00", "last_seen": "10:10", "action": "failure"}]

    assert _statuses(guard_splunk_table_fidelity(rows, rows)) == ["pass"]


def test_splunk_table_fidelity_changed_count_fails() -> None:
    evidence = [{"host": "APP-01", "source_ip": "10.1.2.3", "failed_logins": 42, "first_seen": "10:00", "last_seen": "10:10", "action": "failure"}]
    payload = [{"host": "APP-01", "source_ip": "10.1.2.3", "failed_logins": 43, "first_seen": "10:00", "last_seen": "10:10", "action": "failure"}]

    assert _has(guard_splunk_table_fidelity(payload, evidence), "fail", "guard.splunk_table_fidelity")


def test_splunk_table_fidelity_added_row_fails() -> None:
    evidence = [{"host": "APP-01", "source_ip": "10.1.2.3", "failed_logins": 42, "first_seen": "10:00", "last_seen": "10:10", "action": "failure"}]
    payload = [*evidence, {"host": "APP-01", "source_ip": "10.1.2.4", "failed_logins": 1, "first_seen": "10:00", "last_seen": "10:10", "action": "failure"}]

    assert _has(guard_splunk_table_fidelity(payload, evidence), "fail", "guard.splunk_table_fidelity")


def test_splunk_table_fidelity_altered_time_fails() -> None:
    evidence = [{"host": "APP-01", "source_ip": "10.1.2.3", "failed_logins": 42, "first_seen": "10:00", "last_seen": "10:10", "action": "failure"}]
    payload = [{"host": "APP-01", "source_ip": "10.1.2.3", "failed_logins": 42, "first_seen": "10:01", "last_seen": "10:10", "action": "failure"}]

    assert _has(guard_splunk_table_fidelity(payload, evidence), "fail", "guard.splunk_table_fidelity")


def test_splunk_table_fidelity_omitted_row_respects_strict_mode() -> None:
    evidence = [{"host": "APP-01", "source_ip": "10.1.2.3", "failed_logins": 42, "first_seen": "10:00", "last_seen": "10:10", "action": "failure"}]

    assert _has(guard_splunk_table_fidelity([], evidence, strict=True), "fail", "guard.splunk_table_fidelity")
    assert _has(guard_splunk_table_fidelity([], evidence, strict=False), "warn", "guard.splunk_table_fidelity")


def test_guards_are_not_imported_by_chat_route_import() -> None:
    code = (
        "import sys, traceback\n"
        "sys.modules.pop('app.answer_guard.rules', None)\n"
        "try:\n"
        "    import app.api.routes_chat\n"
        "except Exception:\n"
        "    traceback.print_exc()\n"
        "    raise SystemExit(2)\n"
        "raise SystemExit(1 if 'app.answer_guard.rules' in sys.modules else 0)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], check=False, env=_import_probe_env()
    )

    assert completed.returncode != 2, "import probe could not run — see child traceback"
    assert completed.returncode == 0, "app.api.routes_chat imported the dormant guards"


def _import_probe_env() -> dict[str, str]:
    """Env for an import-probe subprocess: repo root + backend on the path.

    Without this the child cannot import the repo-root ``contracts`` package, dies
    with ModuleNotFoundError, and returns 1 — the exact code this probe uses to
    mean "the guarded module WAS imported". The probe then reports a violation
    that did not happen. Distinguish the two: 0 clean, 1 guard imported, 2 the
    probe itself could not run.
    """
    import os

    backend = str(Path(__file__).resolve().parents[2])
    repo = str(Path(__file__).resolve().parents[3])
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (backend, repo, existing) if p)
    return env
