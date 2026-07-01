"""Tier A 105-path regression harness — deterministic, path-only, no LLM/network.

Samples the 105 question catalogue (all top_n_aggregation rows by ref, loaded
from question_runtime_map_v1.json so text stays in sync) plus synthetic rows for
classes the catalogue does not contain (explicit SPL, unsafe/clarification).
Asserts path shape only: match_path, pattern_type, intent_family, path_type,
needs_spl/rag/mitre, severity behavior class, answer_mode — never answer prose.

Tier B (all 105 rows) lives in scripts/eval_105_path_honoring.py.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from app.chat.evidence_planner import plan_evidence
from app.chat.intent_classifier import build_query_to_intent
from app.chat.planning_decision import plan_path_and_tools
from app.query_understanding.parser import understand_query
from app.risk.severity_policy import (
    ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL,
    apply_analytics_severity_guard,
    decide_severity,
)

_MAP_PATH = Path(__file__).resolve().parents[1] / "coverage" / "question_runtime_map_v1.json"
_EXACT_PATHS = {"exact_105_question", "exact_105_plus_use_case_catalog"}
_ROUTED_STUB = {"skill": "attack_discovery", "tool_plan": ["generate_spl", "validate_spl"]}

TOP_N_REFS = (
    "q0.q002",
    "q0.q003",
    "q0.q010",
    "q0.q017",
    "q0.q018",
    "q0.q034",
    "q0.q044",
    "q0.q059",
    "q0.q101",
)

# The 105 catalogue has no explicit-SPL or unsafe rows; these synthetic rows pin
# authority-order ranks 5 (explicit SPL intent) and 1 (unsafe/action block).
EXPLICIT_SPL_ROWS = (
    "Generate SPL for failed logins in the last 24 hours",
    "Write SPL to list VPN logins from new countries",
    "Draft a Splunk search for PowerShell encoded commands",
    "Create SPL for DNS queries to rare domains",
    "Produce SPL for outbound connections from OT servers",
)

RAG_SOP_ROWS = (
    ("Show me the SOP for phishing triage", "sop_or_playbook", "rag_only"),
    ("What is the playbook for ransomware response?", "sop_or_playbook", "rag_only"),
    ("When should we escalate a P2 incident?", "policy_knowledge", "rag_only"),
    ("What is DNS beaconing?", "knowledge_only", "generic_soc_guidance"),
    ("Explain T1110.001 password guessing", "mitre_explanation", "rag_only"),
)

UNSAFE_ENFORCEMENT_ROWS = (
    "Block this IP 10.1.1.5 on the firewall",
    "Isolate the host WS-01 right now",
)

EXPLICIT_RUN_SPL_ROWS = (
    "Run the SPL and give me the results",
)

# Exact-105 hunt/detection refs (one per major hunt pattern class) — must reach
# the review-only SPL path, never clarification.
HUNT_REFS = (
    "q0.q022",  # ioc_correlation
    "q0.q023",  # dns_beaconing_dga_behavior
    "q0.q024",  # multi_signal_correlation
    "q0.q025",  # new_or_unusual_source
    "q0.q026",  # threshold_anomaly
    "q0.q028",  # other_or_unclear
)


@lru_cache(maxsize=1)
def _question_by_ref() -> dict[str, dict[str, Any]]:
    payload = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    return {entry["question_ref"]: entry for entry in payload["entries"]}


def _run_path(query: str) -> dict[str, Any]:
    understanding = understand_query(query)
    result = build_query_to_intent(query=query, query_understanding=understanding)
    intent = result.intent_classification
    plan = plan_evidence(
        intent,
        query_to_intent=result.model_dump(),
        query_understanding=understanding,
    )
    decision = plan_path_and_tools(
        intent_classification=intent.model_dump(),
        evidence_plan=plan.model_dump(),
        routed=_ROUTED_STUB,
        query_understanding=understanding,
    )
    signals = result.query_signals
    severity = apply_analytics_severity_guard(
        decide_severity(None, None, []),
        analytics_query=bool(
            signals.get("exact_105_analytics")
            or signals.get("exact_105_hunt_spl")
            or signals.get("analytics_aggregation")
        ),
        alert_context_present=bool(signals.get("alert_context_present")),
    )
    return {
        "match_path": understanding.deterministic_match_path,
        "question_ref": understanding.mapped_question_ref,
        "pattern_type": understanding.mapped_pattern_type,
        "operation_type": understanding.mapped_operation_type,
        "intent_family": intent.intent_family,
        "requires_clarification": intent.requires_clarification,
        "path_type": decision.path_type,
        "needs_spl": plan.needs_spl,
        "needs_rag": plan.needs_rag,
        "needs_mitre": plan.needs_mitre,
        "answer_mode": plan.answer_mode,
        "severity_label": severity.severity_label,
        "execution_enabled": decision.execution_enabled,
    }


@pytest.mark.parametrize("ref", TOP_N_REFS)
def test_top_n_aggregation_rows_route_to_analytics_spl_review(ref: str) -> None:
    entry = _question_by_ref()[ref]
    assert entry["pattern_type"] == "top_n_aggregation"
    row = _run_path(entry["question"])
    assert row["match_path"] in _EXACT_PATHS, (ref, row["match_path"])
    assert row["question_ref"] == ref
    assert row["pattern_type"] == "top_n_aggregation"
    assert row["intent_family"] == "spl_generation_only", (ref, row["intent_family"])
    assert row["requires_clarification"] is False
    assert row["path_type"] == "spl_review", (ref, row["path_type"])
    assert row["needs_spl"] is True
    assert row["needs_mitre"] is False
    assert row["answer_mode"] == "live_investigation"
    assert row["severity_label"] == ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL, ref
    assert row["execution_enabled"] is False


@pytest.mark.parametrize("query", EXPLICIT_SPL_ROWS)
def test_explicit_spl_rows_keep_spl_review_path(query: str) -> None:
    row = _run_path(query)
    assert row["intent_family"] == "spl_generation_only", (query, row["intent_family"])
    assert row["path_type"] == "spl_review", (query, row["path_type"])
    assert row["needs_spl"] is True
    assert row["execution_enabled"] is False
    # Phase 1: explicit-SPL severity behavior is unchanged (no analytics guard).
    assert row["severity_label"] != ANALYTICS_SEVERITY_NOT_ASSIGNED_LABEL or row[
        "match_path"
    ] in _EXACT_PATHS


@pytest.mark.parametrize(("query", "family", "path_type"), RAG_SOP_ROWS)
def test_rag_sop_explanation_rows_stay_on_knowledge_paths(
    query: str, family: str, path_type: str
) -> None:
    row = _run_path(query)
    assert row["intent_family"] == family, (query, row["intent_family"])
    assert row["path_type"] == path_type, (query, row["path_type"])
    assert row["needs_spl"] is False
    assert row["needs_rag"] is True
    assert row["answer_mode"] == "rag_only"
    assert row["execution_enabled"] is False


@pytest.mark.parametrize("ref", HUNT_REFS)
def test_hunt_pattern_rows_route_to_spl_review(ref: str) -> None:
    entry = _question_by_ref()[ref]
    row = _run_path(entry["question"])
    assert row["match_path"] in _EXACT_PATHS, (ref, row["match_path"])
    assert row["intent_family"] == "spl_generation_only", (ref, row["intent_family"])
    assert row["requires_clarification"] is False
    assert row["path_type"] == "spl_review", (ref, row["path_type"])
    assert row["needs_spl"] is True
    assert row["execution_enabled"] is False


@pytest.mark.parametrize("query", UNSAFE_ENFORCEMENT_ROWS)
def test_unsafe_rows_stay_blocked(query: str) -> None:
    row = _run_path(query)
    assert row["intent_family"] == "clarification_required", (query, row["intent_family"])
    assert row["path_type"] == "unsafe_blocked", (query, row["path_type"])
    assert row["needs_spl"] is False
    assert row["execution_enabled"] is False


@pytest.mark.parametrize("query", EXPLICIT_RUN_SPL_ROWS)
def test_explicit_run_spl_rows_stay_review_only(query: str) -> None:
    row = _run_path(query)
    assert row["intent_family"] == "clarification_required", (query, row["intent_family"])
    assert row["path_type"] == "spl_review", (query, row["path_type"])
    assert row["execution_enabled"] is False
