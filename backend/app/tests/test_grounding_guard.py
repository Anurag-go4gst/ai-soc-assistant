"""Phase 2.5: cite-only grounding guard + out-of-catalog notice preservation."""

from __future__ import annotations

from app.chat.contracts.answer_contract import AnswerContract
from app.synthesis.governed_answer_composer import (
    build_composer_prompt,
    out_of_catalog_notice_preserved,
    validate_composed_prose,
    validate_grounding,
)

_CORPUS = (
    "raw_query: investigate smb top talkers\n"
    "candidate_mitre: T1021\n"
    "soc_kb_snippets: review SMB sessions on index=network sourcetype=smb traffic\n"
    "known source 10.4.4.4 flagged"
)


def test_grounded_prose_passes() -> None:
    text = "Review SMB sessions; the governed context references index=network and host 10.4.4.4."
    ok, reason = validate_grounding(text, _CORPUS)
    assert ok, reason


def test_invented_ip_rejected() -> None:
    text = "The attacker at 203.0.113.99 moved laterally."
    ok, reason = validate_grounding(text, _CORPUS)
    assert not ok and "203.0.113.99" in reason


def test_invented_index_rejected() -> None:
    text = "Run this against index=secret_logs to confirm."
    ok, reason = validate_grounding(text, _CORPUS)
    assert not ok and "secret_logs" in reason


def test_invented_hash_rejected() -> None:
    text = "Hash d41d8cd98f00b204e9800998ecf8427e was observed."
    ok, reason = validate_grounding(text, _CORPUS)
    assert not ok and "hash" in reason.lower()


def test_runnable_spl_pipe_rejected() -> None:
    text = "Just run | tstats count where index=network to see the spike."
    ok, reason = validate_grounding(text, _CORPUS)
    assert not ok


def test_generic_prose_not_false_flagged() -> None:
    # No IOC/source/SPL tokens — must not trip the guard.
    text = "Confirm whether the source is owned, check MFA status, and escalate per policy."
    ok, reason = validate_grounding(text, _CORPUS)
    assert ok, reason


def test_notice_required_when_contract_has_it() -> None:
    contract = AnswerContract(
        missing_evidence=[],
        hil_status="not_required",
        out_of_catalog_notice="This hunt is not a vetted catalog detection.",
    )
    bad = "Here is the SMB analysis with next steps."
    ok, reason = out_of_catalog_notice_preserved(bad, contract)
    assert not ok and "out-of-catalog" in reason.lower()

    good = "Note: this is not a vetted catalog detection; validate against local telemetry and policy."
    ok, _ = out_of_catalog_notice_preserved(good, contract)
    assert ok


def test_notice_guard_noop_without_notice() -> None:
    contract = AnswerContract(missing_evidence=[], hil_status="not_required")
    ok, _ = out_of_catalog_notice_preserved("any prose", contract)
    assert ok


def test_knowledge_answer_may_name_the_asked_technique() -> None:
    # "what is T1110" knowledge answer: T1110 is not in the evidence buckets but the
    # explanation must be allowed to name it. The evidence-supported guard still applies.
    contract = AnswerContract(
        missing_evidence=[], hil_status="not_required",
        intent_family="knowledge_only", answer_mode="rag_only",
    )
    ok, reason = validate_composed_prose(
        "MITRE ATT&CK technique T1110 is Brute Force; respond by checking lockouts and MFA.",
        contract,
    )
    assert ok, reason


def test_investigation_answer_still_blocks_unlisted_technique() -> None:
    contract = AnswerContract(
        missing_evidence=[], hil_status="not_required",
        intent_family="live_investigation", answer_mode="live_investigation",
    )
    ok, reason = validate_composed_prose(
        "The alert maps to T1486 ransomware encryption.", contract,
    )
    assert not ok and "T1486" in reason


def test_required_notice_is_injected_into_prompt() -> None:
    contract = AnswerContract(
        missing_evidence=["mfa_status"], hil_status="not_required",
        out_of_catalog_notice="This hunt is not a vetted catalog detection.",
        candidate_mitre=["T1110"], mitre_technique_ids=["T1110"],
    )
    prompt = build_composer_prompt(contract, None, weak_case_composition=True)
    assert "REQUIRED NOTICE" in prompt and "not a vetted catalog detection" in prompt
    assert "ALLOWED MITRE technique IDs" in prompt and "T1110" in prompt
