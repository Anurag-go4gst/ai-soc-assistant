"""Plan item 2.4 — findings / conclusion / limitations distinct from diagnostics.

Pins CV.MULTI.01A (state C inconclusive + missing evidence) and CV.MULTI.01B
(state D suspicious findings) on InvestigationOutcome fixtures — not end-to-end
chat UI rewrite. Progress telemetry must not become findings authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.actions.capability_policy import action_capability_for
from app.chat.contracts.investigation_outcome import SCHEMA_VERSION_V2, derive_investigation_outcome

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = _REPO_ROOT / "docs" / "evals" / "answer_shape" / "fixtures"

_DIAGNOSTIC_TOKENS = (
    "chain_of_thought",
    "chain-of-thought",
    "hidden_reasoning",
    "scratchpad",
    "control_plane_trace",
    "workflow_plan",
)


def _investigation_rqc(**overrides: object) -> dict:
    base = {
        "intent_family": "live_investigation",
        "answer_goal": "live_results",
        "required_capabilities": ["spl", "mcp"],
    }
    base.update(overrides)
    return base


def _derive_multi_01a():
    return derive_investigation_outcome(
        evidence_state={
            "obtained": [],
            "missing": ["authentication_correlation", "session_corroboration"],
        },
        evidence_sufficiency={
            "status": "INSUFFICIENT",
            "missing": ["authentication_correlation", "session_corroboration"],
            "next_action": "DEGRADE",
        },
        context_sufficiency={
            "status": "insufficient_evidence",
            "reasons": ["MCP execution disabled"],
        },
        investigation_run_status={
            "status": "incomplete",
            "stop_reason": "mcp_off",
            "next_action": "DEGRADE",
        },
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(),
        severity_label="Not assigned",
        action_capability=action_capability_for(None, None),
        outcome_v2_enabled=True,
    )


def _derive_multi_01b():
    return derive_investigation_outcome(
        evidence_state={"obtained": ["mcp_auth"], "missing": []},
        evidence_sufficiency={"status": "SUFFICIENT", "missing": [], "next_action": "CONTINUE"},
        final_evidence_gate={
            "collected_evidence_refs": ["ev-auth"],
            "allow_live_result_language": True,
        },
        structured_context={
            "structured_facts": [
                {
                    "statement": "25 failed SSH then success from 198.51.100.42 to admin",
                    "source_refs": ["ev-auth"],
                }
            ],
            "source_evidence_refs": ["ev-auth"],
        },
        severity_label="P2 High",
        investigation_run_status={"status": "completed", "next_action": "CONTINUE"},
        investigation_approval={"status": "approved"},
        resolved_query_contract=_investigation_rqc(
            provenance={
                "original_query": (
                    "Investigate SSH. If compromised prepare remediation and "
                    "draft email to firewall and identity teams."
                )
            }
        ),
        action_capability=action_capability_for("auth_failed_login_spike", "P2 High"),
        outcome_v2_enabled=True,
    )


def test_cv_multi_01a_inconclusive_conclusion_and_named_missing_evidence() -> None:
    """CV.MULTI.01A — state C: inconclusive conclusion + missing-evidence named."""
    outcome = _derive_multi_01a()
    payload = outcome.model_dump(mode="json")
    assert payload["schema_version"] == SCHEMA_VERSION_V2
    assert payload["investigation_status"] == "incomplete"
    assert payload["disposition"] == "inconclusive"
    assert payload["missing_evidence"] == [
        "authentication_correlation",
        "session_corroboration",
    ]
    assert any("authentication_correlation" in item for item in payload["limitations"])
    assert any("MCP execution disabled" in item for item in payload["limitations"])
    # Honest inconclusive: no invented compromise confirmation
    blob = json.dumps(payload).lower()
    assert "compromise_confirmed" not in blob
    assert "account is compromised" not in blob
    for token in _DIAGNOSTIC_TOKENS:
        assert token not in blob


def test_cv_multi_01b_suspicious_conclusion_with_findings() -> None:
    """CV.MULTI.01B — state D: suspicious conclusion + findings PRESENT."""
    outcome = _derive_multi_01b()
    payload = outcome.model_dump(mode="json")
    assert payload["schema_version"] == SCHEMA_VERSION_V2
    assert payload["investigation_status"] == "completed"
    assert payload["disposition"] == "suspicious"
    assert payload["findings"]
    assert "198.51.100.42" in payload["findings"][0]
    # suspicious ≠ compromise_confirmed
    blob = json.dumps(payload).lower()
    assert "compromise_confirmed" not in blob
    for token in _DIAGNOSTIC_TOKENS:
        assert token not in blob


def test_findings_are_not_progress_diagnostics() -> None:
    """Progress / execution telemetry must not become findings authority."""
    outcome = _derive_multi_01a()
    progress_failure = "mcp_off"
    assert progress_failure not in outcome.findings
    assert all(progress_failure not in item for item in outcome.findings)
    # Limitations may name operational stop reasons; findings stay evidence-bound.
    assert outcome.disposition == "inconclusive"
    assert outcome.missing_evidence


def test_fixtures_match_live_derive_for_bank_rows() -> None:
    """Committed fixtures stay byte-aligned with live derive for harness scoring."""
    mapping = {
        "cv_multi_01a_outcome.json": _derive_multi_01a,
        "cv_multi_01b_outcome.json": _derive_multi_01b,
    }
    for name, derive in mapping.items():
        path = _FIXTURES / name
        assert path.is_file(), f"missing fixture {path}"
        frozen = json.loads(path.read_text(encoding="utf-8"))
        live = derive().model_dump(mode="json")
        assert frozen["investigation_outcome"] == live
        assert frozen["row_id"] in {"CV.MULTI.01A", "CV.MULTI.01B"}
        assert frozen["not_end_to_end_chat_capture"] is True
