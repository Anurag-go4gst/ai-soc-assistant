"""Phase 13D-A — deterministic SPL/search intent and success-after-failure routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.routes_chat import chat
from app.chat.query_signals import extract_query_signals
from app.query_understanding.success_after_failure import detect_success_after_failure
from app.schemas.requests import ChatRequest
from app.use_cases.registry import match_use_cases

REPO_ROOT = Path(__file__).resolve().parents[3]
BANK_PATH = REPO_ROOT / "docs" / "evals" / "powergrid_soc_question_bank.json"


@pytest.fixture(autouse=True)
def _enable_control_plane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.config.settings.spl_allowed_sourcetypes", "pgcil:auth,aws:cloudtrail")


def _question(question_id: str) -> dict:
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    return next(row for row in bank["questions"] if row["question_id"] == question_id)


def _chat(query: str):
    return chat(ChatRequest(message=query))


# pg.dns.002 ("unusual DNS queries … How should SOC triage this?") is not in
# this list: the templateless `dns_unusual_query_volume` shell was culled, so
# the question is out-of-catalogue guided investigation rather than a fake T2
# hunt bind. Explicit DNS *search* rows (pg.dns.003/005) stay below.
@pytest.mark.parametrize(
    ("query", "question_id"),
    [
        (
            "Look for successful VPN logins after repeated failures for the same user.",
            "pg.auth.002",
        ),
        (
            "Draft a Splunk search to find VPN logins from countries not seen before for the same user.",
            "pg.auth.003",
        ),
        (
            "Search firewall logs for SMB traffic between OT network segments.",
            "pg.fw.004",
        ),
        (
            "Find successful established connections from vendor VPN to OT jump server.",
            "pg.fw.007",
        ),
        (
            "Search firewall logs for denied traffic from OT assets to the internet.",
            "pg.fw.009",
        ),
        (
            "Look for DNS queries from OT servers to newly observed domains in the last 24 hours.",
            "pg.dns.003",
        ),
        (
            "Draft a Splunk search for possible DNS tunneling from OT systems.",
            "pg.dns.005",
        ),
        (
            "Search proxy logs for large uploads from corporate network to unknown external domains.",
            "pg.dns.006",
        ),
        (
            "Find Windows servers where PowerShell made outbound network connections.",
            "pg.ep.001",
        ),
        (
            "Search endpoint logs for new service creation on control room servers.",
            "pg.ep.003",
        ),
        (
            "An EDR alert shows suspicious PowerShell on an engineering workstation. What should SOC check?",
            "pg.ep.004",
        ),
    ],
)
def test_explicit_search_questions_avoid_spl_not_required_path(query: str, question_id: str) -> None:
    response = _chat(query)
    signals = response.query_to_intent["query_signals"]
    intent = response.query_to_intent["intent_classification"]
    planning = response.planning_decision or {}
    path_type = planning.get("path_type")

    assert (
        signals.get("explicit_search_intent")
        or signals.get("spl_generation")
        or signals.get("use_case_review_guidance")
    )
    assert intent["intent_family"] != "clarification_required"
    assert path_type in {
        "spl_review",
        "spl_review_plus_rag",
        "hybrid_investigation",
    }, f"{question_id} path_type={path_type}"

    combined = f"{response.message or ''} {response.note or ''}".lower()
    assert "spl is not required" not in combined

    contract = response.answer_contract or {}
    if contract.get("spl_allowed"):
        assert contract.get("spl_status") != "not_required"


def test_pg_auth_002_success_after_failure_use_case_and_signals() -> None:
    query = _question("pg.auth.002")["question"]
    assert detect_success_after_failure(query.lower())
    signals = extract_query_signals(query)
    assert signals["success_after_failure"] is True

    matches = match_use_cases(query, limit=5)
    assert matches[0].use_case_id == "auth_success_after_failure"

    response = _chat(query)
    assert response.selected_use_case is not None
    assert response.selected_use_case.use_case_id == "auth_success_after_failure"
    assert (response.planning_decision or {}).get("path_type") in {
        "spl_review",
        "spl_review_plus_rag",
        "hybrid_investigation",
    }
    contract = response.answer_contract or {}
    assert contract.get("success_after_failure_context") is True


def test_success_after_failure_outranks_failed_login_spike() -> None:
    query = "Failed logins followed by a successful login for svc_ops from the same source."
    signals = extract_query_signals(query)
    assert signals["success_after_failure"] is True
    assert match_use_cases(query, limit=3)[0].use_case_id == "auth_success_after_failure"


def test_mfa_failure_outranks_generic_failed_login_on_coverage() -> None:
    """Item 3: coverage × IDF ranking, not additive confidence.

    Both rows match 'failure(s)'; the more specific MFA patterns must win.
    Under the retired 0.62+0.05*n formula both sat at 0.78 and the generic
    spike was committed (bind_margin −0.69 on the MFA question).
    """
    query = "Find MFA failures for privileged users in the last 24 hours."
    ordered = match_use_cases(query, limit=3)
    assert ordered[0].use_case_id == "auth_mfa_failure_spike"
    ids = [item.use_case_id for item in ordered]
    if "auth_failed_login_spike" in ids:
        mfa = next(item for item in ordered if item.use_case_id == "auth_mfa_failure_spike")
        generic = next(item for item in ordered if item.use_case_id == "auth_failed_login_spike")
        assert (mfa.coverage_score or 0) > (generic.coverage_score or 0)


def test_mcp_execution_stays_disabled_for_explicit_search() -> None:
    response = _chat("Search firewall logs for denied traffic from OT assets to the internet.")
    assert response.execution is not None
    assert response.execution.status != "executed"
    assert response.execution.executed_spl is None
