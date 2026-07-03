"""Plan 5.1 — CanonicalFacts contract, spine, and migration superset."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.chat.canonical_facts_spine import (
    RETIRED_ADHOC_READ_KEYS,
    append_fact,
    attach_canonical_facts_to_state,
    empty_canonical_facts,
    facts_superset_of_master_state,
    harvest_canonical_facts_from_state,
    merge_canonical_facts,
    negative_evidence_from_facts,
    synthesis_fact_summary,
)
from app.chat.contracts.canonical_facts import CanonicalFacts
from app.chat.pipeline import build_live_chat_response
from app.evals.sentinel_eval import load_sentinel_rows, sentinel_runtime
from app.schemas.requests import ChatRequest

_PIPELINE_PATH = Path(__file__).resolve().parents[1] / "chat" / "pipeline.py"


def test_append_only_preserves_prior_facts() -> None:
    facts = empty_canonical_facts()
    facts = append_fact(
        facts,
        kind="entity",
        payload={"name": "host-a"},
        node="test",
        evidence_class="session",
    )
    facts = append_fact(
        facts,
        kind="rag_citation",
        payload={"ref": "soc-kb-1"},
        node="rag_early",
        evidence_class="rag",
    )
    assert len(facts.facts) == 2
    assert facts.facts[0].kind == "entity"
    assert facts.facts[1].provenance.node == "rag_early"


def test_merge_is_idempotent_on_fact_id() -> None:
    left = append_fact(empty_canonical_facts(), kind="entity", payload={"a": 1}, node="n1")
    right = harvest_canonical_facts_from_state({"source_evidence": [{"evidence_id": "e1", "source_type": "rag"}]})
    merged_once = merge_canonical_facts(left, right)
    merged_twice = merge_canonical_facts(merged_once, right)
    assert len(merged_twice.facts) == len(merged_once.facts)


def test_negative_evidence_from_facts_round_trip() -> None:
    facts = append_fact(
        empty_canonical_facts(),
        kind="negative_evidence",
        payload={"absent": ["powershell_command_evidence"]},
        node="negative_evidence_extractor",
    )
    assert negative_evidence_from_facts(facts) == {"absent": ["powershell_command_evidence"]}


def test_harvest_superset_of_master_signals() -> None:
    state = {
        "source_evidence": [{"evidence_id": "ev1", "source_type": "rag", "preview_rows": []}],
        "soc_kb_retrieval": {"retrieval_status": "retrieved", "citations": [{"doc": "sop-1"}]},
        "mitre_decision": {"answer_visible": True, "techniques": []},
        "evidence_plan": {
            "resource_plan": {
                "steps": [
                    {"step_id": "rag", "resource_id": "rag_corpus:soc_kb", "purpose": "knowledge_retrieval"}
                ]
            }
        },
        "structured_context": {"vulnerability_source": {"status": "not_onboarded"}},
    }
    facts = harvest_canonical_facts_from_state(state)
    assert facts_superset_of_master_state(state, facts)


def test_mitre_finalize_prefers_spine_negative_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat.pipeline import _mitre_outputs_for_finalize
    from app.config import settings

    monkeypatch.setattr(settings, "control_plane_enabled", True)
    facts = attach_canonical_facts_to_state(
        {
            "query_signals": {},
            "source_evidence": [],
            "structured_context": {},
            "canonical_facts": {
                "schema_version": "v1",
                "authority_holder": "canonical_facts_spine",
                "facts": [
                    {
                        "fact_id": "negative_evidence:test",
                        "kind": "negative_evidence",
                        "payload": {"absent": ["successful_login"]},
                        "provenance": {"node": "test", "evidence_class": "unknown"},
                    }
                ],
            },
        }
    )
    _, decision = _mitre_outputs_for_finalize(
        query="failed logins only",
        question_ref=None,
        use_case_id="auth_failed_login_spike",
        source_refs=[],
        intent_classification={"intent_family": "live_investigation"},
        evidence_plan={"needs_mitre": True},
        query_signals={},
        source_evidence=[],
        structured_context={},
        canonical_facts=facts.get("canonical_facts"),
    )
    assert decision is not None


@pytest.mark.parametrize("row", load_sentinel_rows()[:5], ids=lambda row: row["key"])
def test_sentinel_turns_emit_canonical_facts_superset(row) -> None:
    with sentinel_runtime():
        payload = build_live_chat_response(ChatRequest(message=row["question"])).model_dump(mode="json")
    facts_raw = payload.get("canonical_facts")
    assert isinstance(facts_raw, dict), row["key"]
    facts = CanonicalFacts.model_validate(facts_raw)
    assert facts.authority_holder == "canonical_facts_spine"
    assert facts_superset_of_master_state(payload, facts), row["key"]
    summary = synthesis_fact_summary(facts)
    assert summary["fact_count"] == len(facts.facts)


def test_grep_gate_mitre_path_uses_spine_reader() -> None:
    source = _PIPELINE_PATH.read_text(encoding="utf-8")
    assert "negative_evidence_from_facts" in source
    assert "attach_canonical_facts_to_state" in source


def test_retired_keys_documented() -> None:
    assert "mitre_decision" in RETIRED_ADHOC_READ_KEYS
    assert "source_evidence" in RETIRED_ADHOC_READ_KEYS
