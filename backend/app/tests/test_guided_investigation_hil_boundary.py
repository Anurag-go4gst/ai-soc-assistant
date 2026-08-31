"""Regression: investigation-plan HIL boundary + guided LLM failure classification."""

from __future__ import annotations

import pytest

from app.actions.capability_policy import action_capability_for
from app.chat.awaiting_investigation_plan_gate import (
    _AWAITING_APPROVAL_STATUSES,
    classify_guided_llm_failure,
    is_awaiting_investigation_approval,
    should_treat_guided_skip_as_degraded,
    strip_material_fields_for_awaiting_approval,
)
from app.chat.contracts.investigation_envelope import InvestigationApprovalStatus
from app.chat.investigation_plan_builder import _is_authentication_sequence
from app.chat.guided_investigation_synthesizer import (
    build_guided_llm_degraded_message,
    build_guided_llm_trace,
)
from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.query_understanding.parser import _event_types
from app.schemas.requests import ChatRequest
from app.synthesis.lab_runner import run_governed_synthesis_lab


_SSH_COMPROMISE_QUERY = (
    "We saw 25 failed SSH logins from 198.51.100.42 followed by one successful "
    "login for the same user. Investigate whether this is likely a compromise and "
    "tell me what evidence you need to confirm it."
)


@pytest.fixture(autouse=True)
def _investigation_plan_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_investigation_plan_before_resource_plan_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_planner_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_investigation_outcome_v2_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_guided_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)
    monkeypatch.setattr(settings, "langgraph_orchestration_enabled", False)
    monkeypatch.setattr(settings, "legacy_selected_skill_authority_enabled", False)


def test_event_types_preserve_failed_and_successful_ssh() -> None:
    types = _event_types(_SSH_COMPROMISE_QUERY)
    assert "authentication_failure" in types
    assert "authentication_success" in types


def test_synthesis_lab_already_narrated_is_orchestration_not_unavailable() -> None:
    assert classify_guided_llm_failure("synthesis_lab_already_narrated") == "ORCHESTRATION_SKIP"
    assert should_treat_guided_skip_as_degraded("synthesis_lab_already_narrated") is False
    trace = build_guided_llm_trace(
        path_type="guided_investigation",
        composer_trace={"llm_composer_skipped_reason": "synthesis_lab_already_narrated"},
    )
    assert trace.guided_llm_required is True
    assert trace.guided_llm_used is False
    assert trace.guided_llm_degraded_fallback is False
    assert trace.guided_llm_failure_class == "ORCHESTRATION_SKIP"


def test_degraded_message_never_leaks_internal_codes_or_env_vars() -> None:
    msg = build_guided_llm_degraded_message(
        failure_reason="synthesis_lab_already_narrated",
        checklist=["Collect auth logs"],
    )
    assert "synthesis_lab_already_narrated" not in msg
    assert "AI_SOC_GUIDED_LLM_TIMEOUT_SECONDS" not in msg
    assert "planner is unavailable" not in msg.lower()
    assert "No telemetry was queried" in msg

    timeout_msg = build_guided_llm_degraded_message(failure_reason="llm_timed_out")
    assert "timed out" in timeout_msg.lower()
    assert "AI_SOC_" not in timeout_msg

    unavailable_msg = build_guided_llm_degraded_message(failure_reason="provider_unavailable")
    assert "unavailable" in unavailable_msg.lower()
    assert "provider_unavailable" not in unavailable_msg


def test_is_awaiting_investigation_approval_statuses() -> None:
    assert is_awaiting_investigation_approval({"investigation_approval": {"status": "awaiting_approval"}})
    assert is_awaiting_investigation_approval(
        {"canonical_planning_outcome": {"status": "awaiting_investigation_plan"}}
    )
    assert not is_awaiting_investigation_approval({"investigation_approval": {"status": "approved"}})
    assert not is_awaiting_investigation_approval({})


def test_pre_approval_ssh_query_plan_only_no_outcome_or_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    response = build_live_chat_response(ChatRequest(message=_SSH_COMPROMISE_QUERY))

    approval = response.investigation_approval
    assert isinstance(approval, dict)
    assert approval.get("status") in {"awaiting_approval", "edited_awaiting_approval"}

    assert response.investigation_outcome is None
    evidence = list(response.source_evidence or [])
    collected = [
        item
        for item in evidence
        if isinstance(item, dict) and str(item.get("collection_status") or "") == "collected"
    ]
    assert collected == []

    # No analyst-facing conclusion / disposition packaging before approval.
    assert response.analyst_response is None

    message = str(response.message or "")
    assert "synthesis_lab_already_narrated" not in message
    assert "AI_SOC_GUIDED_LLM_TIMEOUT_SECONDS" not in message
    assert "SesameOp" not in message

    # Plan must preserve failed+success auth semantics when entities are present.
    plan = response.validated_investigation_plan
    assert isinstance(plan, dict)
    blob = str(plan).lower()
    assert "fail" in blob or "authentication_failure" in blob or "ssh" in blob

    for item in list(response.source_evidence or []):
        assert "SesameOp" not in str(item)


def test_stopword_only_overlap_cannot_surface_unrelated_knowledge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C4A: reproduce the measured 0.427 seam and pin the generic correction.

    Before the stopword filter the ATLAS narratives (incl. AML.CS0042 "SesameOp")
    matched this SSH query on the function words "and"/"for" alone across six
    scored fields, summing to 0.427 — past ``soc_kb_min_confidence`` (0.35).
    """
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    from app.knowledge.soc_kb_retriever import (
        RETRIEVAL_STOPWORDS,
        _is_topical_overlap,
        retrieve_soc_kb,
    )

    assert {"and", "for", "the"}.issubset(RETRIEVAL_STOPWORDS)
    # The rule is "not on stopwords ALONE" — one topical term still scores.
    assert not _is_topical_overlap({"and", "for"})
    assert _is_topical_overlap({"and", "hours"})
    # SOC-meaningful words are never stopwords, whatever their grammar.
    assert not (RETRIEVAL_STOPWORDS & {"after", "before", "no", "not", "one", "out", "up"})

    result = retrieve_soc_kb(
        query=_SSH_COMPROMISE_QUERY,
        selected_skill="guided_investigation",
        workflow_stage="context",
        workflow_plan={},
        required_sources=[],
        execution_block_reason=None,
    )
    entries = list(result.get("retrieved_entries") or [])
    doc_ids = {str(entry.get("doc_id") or "") for entry in entries}
    assert not any(doc_id.startswith("atlas-aml.") for doc_id in doc_ids), doc_ids
    blob = " ".join(str(entry) for entry in entries)
    assert "SesameOp" not in blob
    assert "OpenAI Assistants" not in blob


def test_topical_knowledge_still_retrieved_after_stopword_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The correction must not starve genuinely relevant SOC-KB retrieval."""
    monkeypatch.setattr(settings, "soc_kb_retrieval_enabled", True)
    from app.knowledge.soc_kb_retriever import retrieve_soc_kb

    result = retrieve_soc_kb(
        query="What is our SOP for handling a brute force authentication attack?",
        selected_skill="knowledge_recall",
        workflow_stage="context",
        workflow_plan={},
        required_sources=[],
        execution_block_reason=None,
    )
    entries = list(result.get("retrieved_entries") or [])
    assert entries, "topical SOP query must still retrieve governed knowledge"
    assert any("coe-auth-sop" in str(entry.get("doc_id") or "") for entry in entries)

    # The in-catalogue row that a blunter "delete stopwords" variant regressed:
    # "after hours" is SOC vocabulary and must keep scoring above the floor.
    after_hours = retrieve_soc_kb(
        query=(
            "What is the full activity timeline for a given entity in the N hours "
            "before and after a detection?"
        ),
        selected_skill="knowledge_recall",
        workflow_stage="context",
        workflow_plan={},
        required_sources=[],
        execution_block_reason=None,
    )
    hits = list(after_hours.get("retrieved_entries") or [])
    assert hits, "q0.q104 after-hours retrieval must survive the stopword rule"
    assert any("after_hours" in str(hit.get("entry_id") or "") for hit in hits)


def test_guided_owns_hop_skips_lab_live_narration(monkeypatch: pytest.MonkeyPatch) -> None:
    """When guided LLM owns the turn, synthesis lab must not set provider=local_model."""
    monkeypatch.setattr(settings, "ai_soc_llm_final_synthesis_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_live_synthesis_enabled", True)

    result = run_governed_synthesis_lab(
        structured_context={"answer_mode": "partial_answer"},
        source_evidence=[],
        context_sufficiency={"answer_mode": "partial_answer", "synthesis_readiness": "ready"},
        mitre_mappings=[],
        action_capability=action_capability_for(None, None),
        severity_label=None,
        spl_validation=None,
        human_review=None,
        allow_live_narration=False,
    )
    assert result.status.provider != "local_model"


def test_awaiting_statuses_are_real_lifecycle_members() -> None:
    """C1: no invented status; both real awaiting states get the same boundary."""
    declared = set(InvestigationApprovalStatus.__args__)  # type: ignore[attr-defined]
    assert _AWAITING_APPROVAL_STATUSES <= declared, _AWAITING_APPROVAL_STATUSES - declared
    assert _AWAITING_APPROVAL_STATUSES == {"awaiting_approval", "edited_revalidated"}
    for status in _AWAITING_APPROVAL_STATUSES:
        assert is_awaiting_investigation_approval({"investigation_approval": {"status": status}})
    for status in ("approved", "cancelled", "replanning_required"):
        assert not is_awaiting_investigation_approval({"investigation_approval": {"status": status}})


def test_strip_helper_owns_every_material_surface() -> None:
    """C2: the helper — not the pipeline — decides what a pre-approval turn may carry."""
    packaged = strip_material_fields_for_awaiting_approval(
        analyst_response=object(),
        analyst_summary=object(),
        proposed_actions=[{"action": "block_ip"}],
        source_evidence=[{"source_type": "rag", "collection_status": "collected"}],
        state={
            "investigation_outcome": {"disposition": "inconclusive"},
            "email_draft": {"to": "soc@example.com"},
            "remediation_execution": {"status": "executed"},
            "investigation_approval": {"status": "awaiting_approval"},
            "validated_investigation_plan": {"investigation_objective": "keep me"},
        },
    )
    assert packaged.analyst_response is None
    assert packaged.analyst_summary is None
    assert packaged.proposed_actions is None
    assert packaged.source_evidence == []
    assert packaged.state["investigation_outcome"] is None
    assert packaged.state["email_draft"] is None
    assert packaged.state["remediation_execution"] is None
    # Planning surfaces survive.
    assert packaged.state["investigation_approval"] == {"status": "awaiting_approval"}
    assert packaged.state["validated_investigation_plan"] == {"investigation_objective": "keep me"}


def test_pipeline_has_no_second_material_strip_implementation() -> None:
    """C2: exactly one production owner; the pipeline must not duplicate the logic."""
    import inspect

    from app.chat import pipeline as pipeline_module

    source = inspect.getsource(pipeline_module)
    assert "strip_material_fields_for_awaiting_approval(" in source
    # The old inline duplicate assigned these three keys together in the packaging block.
    assert source.count('"remediation_execution": None') == 0


def test_edit_revalidated_plan_keeps_the_no_execution_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1/Test 2: an edited+revalidated plan awaiting approval executes nothing."""
    monkeypatch.setattr(settings, "ai_soc_resource_plan_execution_enabled", True)
    first = build_live_chat_response(ChatRequest(message=_SSH_COMPROMISE_QUERY, session_id="hil-edit"))
    approval = first.investigation_approval
    assert isinstance(approval, dict)
    assert approval.get("status") == "awaiting_approval"

    edited = build_live_chat_response(
        ChatRequest(
            message="Edit",
            session_id="hil-edit",
            investigation_review_action="edit",
            investigation_handoff_id=str(approval["handoff_id"]),
            investigation_handoff_version=int(approval["handoff_version"]),
            investigation_plan_edits={
                "evidence_needed": ["post-login process execution on the destination host"]
            },
        )
    )
    edited_approval = edited.investigation_approval or {}
    assert edited_approval.get("status") == "edited_revalidated"
    assert int(edited_approval.get("handoff_version") or 0) > int(approval["handoff_version"])
    assert is_awaiting_investigation_approval({"investigation_approval": edited_approval})

    assert edited.approved_investigation_envelope is None
    assert edited.investigation_outcome is None
    assert edited.analyst_response is None
    collected = [
        item
        for item in list(edited.source_evidence or [])
        if isinstance(item, dict) and item.get("collection_status") == "collected"
    ]
    assert collected == []


def test_authentication_sequence_adds_post_login_evidence_requirement() -> None:
    """C3/Test 3: failed-then-successful auth must require post-login activity evidence."""
    from app.chat.investigation_plan_builder import build_deterministic_investigation_plan

    plan = build_deterministic_investigation_plan(
        query=_SSH_COMPROMISE_QUERY,
        entities={
            "event_type": ["authentication_failure", "authentication_success"],
            "source_ip": ["198.51.100.42"],
        },
    )
    blob = " ".join(plan.evidence_needed).lower()
    assert "post-login" in blob
    for token in ("commands", "processes", "privilege", "persistence", "lateral movement"):
        assert token in blob, token
    # An evidence requirement, never an assertion that these occurred.
    assert "compromise confirmed" not in blob
    assert "was compromised" not in blob


def test_single_outcome_authentication_query_gets_no_post_login_requirement() -> None:
    """C3/Test 4: negative semantics — no invented post-compromise requirements."""
    from app.chat.investigation_plan_builder import build_deterministic_investigation_plan

    for entities in (
        {"event_type": ["authentication_success"]},
        {"event_type": ["authentication_failure"]},
        {},
    ):
        plan = build_deterministic_investigation_plan(
            query="Show successful logins for the finance service account today",
            entities=entities,
        )
        blob = " ".join(plan.evidence_needed).lower()
        assert "post-login" not in blob, entities
    assert not _is_authentication_sequence({"event_type": ["authentication_success"]})
