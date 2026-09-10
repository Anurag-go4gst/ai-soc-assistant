"""Hypothesis revision across two governed reads (closure item D).

READ #1 returns a SIGNED, well-known administrative binary, which weakens the
"malware binary" hypothesis on process identity alone -- and the agent must not
stop there. The same rows carry a suspicious context (service account, out of
hours, unexpected parent), so "legitimate tool being abused" becomes the material
question and a second bounded read is required to separate it from legitimate use.

Everything comes from the existing controlled external MCP server through normal
discovery/authorization. The expected conclusion is not encoded in the fixture or
in production code: only telemetry is.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from app.chat.canonical_handoff_store import clear_all_handoffs_for_tests
from app.chat.session_store import clear_all_session_pins_for_tests

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.tests.test_controlled_soc_lifecycle_acceptance import (  # noqa: E402
    LIFECYCLE_QUERY,
    _approve_investigation,
    _arm_hil,
    _arm_mcp,
    _chat,
    _discover,
    _stub_reasoners,
)
from tools.controlled_mcp_server.server import ControlledMcpServer  # noqa: E402

# Same structure as the proven controlled lifecycle query so the deterministic SPL
# producer renders and execution scope binds; only the process nouns differ. What
# is under test is reasoning over the returned evidence, not SPL authoring.
# The query is held CONSTANT at the already-proven controlled lifecycle ask, so
# the only variable is what READ #1 returns. Tuning query text until a template
# renders would make this measure SPL authoring instead of hypothesis revision.
REVISION_QUERY = LIFECYCLE_QUERY


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()
    yield
    clear_all_handoffs_for_tests()
    clear_all_session_pins_for_tests()


def test_two_governed_reads_revise_the_initial_hypothesis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = ControlledMcpServer(mode="admin_tool_revision")
    server.start()
    captured: dict = {}
    try:
        _arm_mcp(monkeypatch, server)
        _arm_hil(monkeypatch)
        _discover(server)
        _stub_reasoners(monkeypatch, captured)

        first = _chat(REVISION_QUERY)
        approval = first.investigation_approval or {}
        assert approval.get("status") in {"awaiting_approval", "edited_revalidated"}, approval

        # The plan must weigh the legitimate-tool alternative up front, not only malware.
        plan = approval.get("validated_plan") or first.validated_investigation_plan or {}
        plan_blob = json.dumps(plan).lower()
        assert "process" in plan_blob
        assert "persistence" in plan_blob or "network" in plan_blob

        second = _approve_investigation(first, REVISION_QUERY)
        payload = second.model_dump(mode="json")

        # READ #1 and READ #2 both executed through the governed connector.
        assert server.search_calls >= 2, json.dumps(
            {
                "search_calls": server.search_calls,
                "run_status": payload.get("investigation_run_status"),
                "execution": payload.get("execution"),
                "spl_validation": payload.get("spl_validation"),
                "candidate_spl": payload.get("candidate_spl"),
            },
            default=str,
        )[:3000]

        collected = [
            item
            for item in (payload.get("source_evidence") or [])
            if isinstance(item, dict)
            and item.get("collection_status") == "collected"
            and item.get("source_type") in {"splunk_mcp", "mcp_discovery"}
        ]
        assert collected, payload.get("source_evidence")
        evidence_blob = json.dumps(collected).lower()

        # Both reads reached governed evidence: the signed admin tool AND the
        # context that makes the session questionable.
        assert "psexec" in evidence_blob
        assert (
            "203.0.113.77" in evidence_blob
            or "scheduled_task_created" in evidence_blob
            or "svc_backup" in evidence_blob
        ), evidence_blob

        prompt = captured.get("plan_delta_prompt") or ""
        if prompt:
            assert "admitted_environment_evidence" in prompt
            assert "current_hypotheses" in prompt

        outcome = payload.get("investigation_outcome") or {}
        assessment = ((outcome.get("provenance") or {}).get("hypothesis_assessment") or {})
        history = assessment.get("history") or []
        items = assessment.get("items") or []
        assert items, outcome
        assessments_by_round = []
        for entry in history:
            if not isinstance(entry, dict):
                continue
            assessments_by_round.append(
                {
                    str(item.get("hypothesis_id")): str(item.get("assessment"))
                    for item in (entry.get("items") or [])
                    if isinstance(item, dict)
                }
            )
        # At least one hypothesis must change state across evidence rounds.
        changed = False
        if len(assessments_by_round) >= 2:
            first = assessments_by_round[0]
            for later in assessments_by_round[1:]:
                if later != first:
                    changed = True
                    break
        final_states = {str(item.get("hypothesis_id")): str(item.get("assessment")) for item in items}
        if assessments_by_round:
            changed = changed or final_states != assessments_by_round[0]
        assert changed, {
            "history": history,
            "items": items,
            "rounds": captured.get("assessment_rounds"),
        }
        assert assessment.get("evolution_summary"), assessment
        assert "h1" not in str(assessment.get("evolution_summary") or "").split()

        # A legitimate binary name never becomes a benign conclusion on its own.
        assert outcome.get("disposition") != "benign", outcome
        supported = outcome.get("supported_hypotheses") or []
        unconfirmed = outcome.get("unconfirmed_hypotheses") or []
        assert unconfirmed or supported, outcome

        # Remediation was recommended-only; nothing was written.
        assert payload.get("remediation_execution") is None
        assert (payload.get("action_capability") or {}).get("current_tier") in {1, 2}
    finally:
        server.stop()
