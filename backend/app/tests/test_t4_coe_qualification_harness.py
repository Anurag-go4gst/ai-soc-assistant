"""Output contract for scripts/eval_t4_coe_qualification.py — no live Cisco calls."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.chat.semantic_t4_understanding import (
    _SEMANTIC_T4_SYSTEM_PROMPT,
    _build_semantic_t4_user_prompt,
)

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "eval_t4_coe_qualification.py"
_spec = importlib.util.spec_from_file_location("eval_t4_coe_qualification", _SCRIPT)
assert _spec and _spec.loader
harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harness)

_REQUIRED_CLASSES = {
    "lateral_movement",
    "dga_dns_c2",
    "malicious_vs_administrative_powershell",
    "identity_compromise",
    "potential_exfiltration",
    "ambiguous_missing_referent_clarification",
    "insufficient_evidence_inconclusive",
    "competing_hypotheses",
}


def test_eight_representative_cases() -> None:
    assert len(harness.CASES) == 8
    ids = [case["case_id"] for case in harness.CASES]
    assert ids == [
        "lateral_movement",
        "dga_dns_c2",
        "powershell_malicious_vs_admin",
        "identity_compromise",
        "potential_exfiltration",
        "missing_referent_clarification",
        "insufficient_evidence_inconclusive",
        "competing_hypotheses",
    ]
    assert {case["class"] for case in harness.CASES} == _REQUIRED_CLASSES


def test_emit_prompts_does_not_call_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _forbidden(query: str, _contract: object) -> str:
        calls.append(query)
        raise AssertionError("emit-prompts must not call the live T4 provider")

    monkeypatch.setattr(
        "app.chat.semantic_t4_understanding._live_single_hop_provider",
        _forbidden,
    )
    monkeypatch.setattr(harness, "_inference_health", lambda: {"measured": False})
    monkeypatch.setattr(harness, "_models_liveness", lambda: {"measured": False})
    report = harness.build_report(mode="emit-prompts")
    assert calls == []
    assert report["mode"] == "emit-prompts"
    assert harness.assert_output_contract(report) == []


def test_emit_prompts_records_required_fields_and_production_prompt() -> None:
    report = harness.build_report(mode="emit-prompts")
    assert len(report["cases"]) == 8
    for row, case in zip(report["cases"], harness.CASES, strict=True):
        for field in harness.CASE_RECORD_FIELDS:
            assert field in row, field
        prompt = row["exact_t4_prompt"]
        assert prompt["system"] == _SEMANTIC_T4_SYSTEM_PROMPT
        pack = harness._prompt_pack(case)
        expected_user = _build_semantic_t4_user_prompt(case["query"], pack["_base_contract"])
        assert prompt["user"] == expected_user
        assert row["raw_proposal"] is None
        assert row["latency_ms"] is None
        assert row["provider_failure_kind"] is None
        assert "locked_fields_do_not_change" in prompt["user"]
        assert "Do not select a skill or route" in prompt["system"]


def test_f3_stays_open_and_v1_models_is_liveness() -> None:
    report = harness.build_report(mode="emit-prompts")
    assert report["f3_disposition"]["f3_status"] == "open"
    assert report["f3_disposition"]["f3_closed"] is False
    assert report["f3_disposition"]["coe_pass_not_assumed"] is True
    serving = report["serving"]
    assert serving["f3_closed"] is False
    assert serving["measured"] is False
    assert serving["models_liveness"]["kind"] == "liveness_not_inference_health"
    assert serving["inference_health"]["not"] == "/v1/models"
    assert serving["inference_health"]["probe"] == "bounded_generation"
    for key in (
        "latency",
        "timeout_error_rate",
        "concurrency",
        "slot_pressure",
        "application_t4_integration",
    ):
        assert key in serving
    assert serving["latency"]["p50_ms"] is None
    assert serving["latency"]["p95_ms"] is None


def test_injected_malformed_and_authority_keys_fail_closed() -> None:
    checks = harness.serving_contract_checks()
    assert "schema_invalid" in checks["malformed_output"]["rejected_reasons"]
    assert checks["malformed_output"]["locked_fields_preserved"] is True
    assert "authority_key_present" in checks["authority_key_rejected"]["rejected_reasons"]
    assert checks["authority_key_rejected"]["direct_widening"] is False
    assert checks["authority_key_rejected"]["capability_widening"] == []
    assert checks["provider_unavailable"]["failure_kind"] == "provider_unavailable"
    assert checks["provider_unavailable"]["did_not_restart"] is True
    assert checks["slot_pressure_synthetic"]["failure_kind"] == "slot_busy"
    assert checks["human_restart_only"]["restart_authorized"] is False
    assert checks["human_restart_only"]["procedure_does_not_restart"] is True


def test_harness_contains_no_cisco_restart_commands() -> None:
    import ast

    text = _SCRIPT.read_text(encoding="utf-8")
    lowered = text.lower()
    for needle in (
        "systemctl restart",
        "systemctl reboot",
        "docker restart",
        "docker compose restart llama",
        "service llama-server restart",
        "pkill llama",
        "kill -9",
    ):
        assert needle not in lowered
    tree = ast.parse(text)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"system", "popen"}:
                hits.append(node.func.attr)
    assert hits == []
    assert "human_restart_only" in text
    assert "Never restarts Cisco" in text


def test_hunt_cases_use_call_t4_overlay_missing_referent_stays_clarify() -> None:
    report = harness.build_report(mode="emit-prompts")
    by_id = {row["case_id"]: row for row in report["cases"]}
    referent = by_id["missing_referent_clarification"]
    assert referent["t4_call_permitted"] is False
    assert referent["measurement_overlay"] == "production_clarify_unresolved_referent"
    assert referent["production_next_action"] == "CLARIFY"
    hunts = [
        "lateral_movement",
        "dga_dns_c2",
        "powershell_malicious_vs_admin",
        "identity_compromise",
        "potential_exfiltration",
        "competing_hypotheses",
    ]
    for case_id in hunts:
        row = by_id[case_id]
        assert row["t4_call_permitted"] is True, case_id
        assert row["unresolved_fields"], case_id
        assert "normalized_goal" in row["exact_t4_prompt"]["user"] or row["unresolved_fields"]
    inconclusive = by_id["insufficient_evidence_inconclusive"]
    assert inconclusive["t4_call_permitted"] is True


def test_t4_cannot_grant_route_in_invariants() -> None:
    report = harness.build_report(mode="emit-prompts")
    invariants = report["invariants"]
    assert invariants["reuses_production_t4"] is True
    assert invariants["t4_cannot_grant_route_capability_or_tool_authority"] is True
    assert invariants["v1_models_is_liveness_not_inference_health"] is True
    assert invariants["no_automatic_cisco_restart"] is True
    assert "semantic_t4_understanding._merge_proposal" in invariants["merge"]
