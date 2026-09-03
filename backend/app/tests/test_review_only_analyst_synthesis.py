"""Post-validation review-only analyst synthesis: schema, grounding, fallback, goldens."""

from __future__ import annotations

import json
from typing import Any

from app.chat.review_only_spl_renderer import render_pattern_guided_review_answer
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.review_only_analyst_synthesis import (
    SYNTHESIS_SOURCE_DETERMINISTIC,
    SYNTHESIS_SOURCE_LLM,
    ReviewOnlyAnalystSynthesis,
    ReviewOnlySplSynthesisPayload,
    parse_synthesis_json,
    render_review_only_analyst_card_text,
    synthesize_review_only_analyst_explanation,
    validate_synthesis_payload,
)
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.tests.test_spl_pattern_guided_authoring import P1, P2, P3, P4


def _payload(**overrides: Any) -> ReviewOnlySplSynthesisPayload:
    base = {
        "summary": "Review-only first-seen host query for matching accounts.",
        "what_it_does": [
            "Looks at successful logons for matching account prefixes.",
            "Compares last 7d to preceding 30d for the same account.",
            "Keeps hosts absent from the account baseline.",
        ],
        "mappings_assumptions": [],
        "expected_result": "Each row is one account/time window with new destination hosts.",
    }
    base.update(overrides)
    return ReviewOnlySplSynthesisPayload.model_validate(base)


def _context(query: str) -> tuple[dict[str, Any], str]:
    spec = build_spl_intent_spec(query)
    spl = compile_intent_spec_to_spl(spec)
    return spec, spl


def test_synthesis_schema_accepts_compact_json() -> None:
    raw = json.dumps(
        {
            "summary": "Review-only sequence query.",
            "what_it_does": ["Finds a failure burst.", "Then a later successful login."],
            "mappings_assumptions": ["Index is a placeholder."],
            "expected_result": "Each row is one burst plus a later success.",
        }
    )
    payload, errors = parse_synthesis_json(raw)
    assert errors == []
    assert payload is not None
    assert payload.summary.startswith("Review-only")


def test_deterministic_fallback_when_llm_disabled() -> None:
    spec, spl = _context(P2)
    result = synthesize_review_only_analyst_explanation(
        original_user_request=P2,
        spec=spec,
        final_validated_spl=spl,
    )
    assert result.source == SYNTHESIS_SOURCE_DETERMINISTIC
    assert "failure burst" in " ".join(result.what_it_does).lower()
    assert "datamodel" not in result.summary.lower()


def test_llm_success_uses_model_copy_when_grounded() -> None:
    spec, spl = _context(P1)
    raw = json.dumps(
        {
            "summary": "Review-only first-seen host query for matching accounts.",
            "what_it_does": [
                "Looks at successful logons for admin-* or svc-* accounts.",
                "Compares the last 7 days with the preceding 30-day history for the same account.",
                "Keeps hosts absent from that account baseline and groups them into one-hour windows.",
            ],
            "mappings_assumptions": [],
            "expected_result": "Each row is a user and new host in an hourly window.",
        }
    )
    result = synthesize_review_only_analyst_explanation(
        original_user_request=P1,
        spec=spec,
        final_validated_spl=spl,
        llm_raw_output_provider=lambda: raw,
    )
    assert result.source == SYNTHESIS_SOURCE_LLM
    assert result.summary.startswith("Review-only first-seen")


def test_grounding_rejects_p1_same_source_ip_comparison() -> None:
    spec, spl = _context(P1)
    payload = _payload(
        what_it_does=[
            "Looks at successful logons.",
            "This compares hosts for the same source IP.",
        ]
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "entity_relationship_mismatch" in reasons


def test_grounding_rejects_p2_authentication_datamodel() -> None:
    spec, spl = _context(P2)
    payload = _payload(
        summary="Uses the Authentication datamodel.",
        what_it_does=["Uses the Authentication datamodel.", "Then finds successes."],
        expected_result="Each row is a burst plus a later success.",
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "unsupported_datamodel" in reasons


def test_grounding_rejects_p2_join() -> None:
    spec, spl = _context(P2)
    payload = _payload(
        what_it_does=["Finds failures.", "It joins failures to successes."],
        expected_result="Each row is a mixed sequence.",
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "unsupported_join" in reasons


def test_grounding_rejects_p2_compromised_account() -> None:
    spec, spl = _context(P2)
    payload = _payload(
        summary="The account is compromised.",
        what_it_does=["Finds a failure burst.", "Then a later successful login."],
        expected_result="Each row is a compromise.",
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "forbidden_live_claim" in reasons


def test_grounding_rejects_p3_command_substring() -> None:
    spec, spl = _context(P3)
    payload = _payload(
        summary="Review-only parent-child process query.",
        what_it_does=["Finds commands containing powershell.", "Groups by host."],
        expected_result="Each row is a command match.",
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "entity_relationship_mismatch" in reasons


def test_grounding_rejects_p4_same_user_comparison() -> None:
    spec, spl = _context(P4)
    payload = _payload(
        summary="Review-only first-seen domain query.",
        what_it_does=["Looks at domains.", "This compares domains for the same user."],
        expected_result="Each row is a new domain.",
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "entity_relationship_mismatch" in reasons


def test_grounding_rejects_result_count_and_block_ip() -> None:
    spec, spl = _context(P1)
    payload = _payload(
        summary="The query returned 12 results.",
        what_it_does=["Looks at logons.", "Then block the source IP."],
        expected_result="Each row is a hit.",
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "forbidden_result_count" in reasons
    assert "forbidden_remediation" in reasons


def test_grounding_rejects_mitre_and_spl_block() -> None:
    spec, spl = _context(P2)
    payload = _payload(
        summary="Mapped to MITRE T1110.",
        what_it_does=["index=auth | stats count", "Then success."],
        expected_result="Each row is a burst.",
    )
    reasons = validate_synthesis_payload(payload, spec=spec, final_validated_spl=spl)
    assert "forbidden_mitre" in reasons
    assert "spl_in_synthesis" in reasons


def test_code_fence_and_malformed_json_fall_back() -> None:
    spec, spl = _context(P1)
    fenced = synthesize_review_only_analyst_explanation(
        original_user_request=P1,
        spec=spec,
        final_validated_spl=spl,
        llm_raw_output_provider=lambda: "```json\n{\"summary\":\"x\"}\n```",
    )
    assert fenced.source == SYNTHESIS_SOURCE_DETERMINISTIC
    malformed = synthesize_review_only_analyst_explanation(
        original_user_request=P1,
        spec=spec,
        final_validated_spl=spl,
        llm_raw_output_provider=lambda: "not json",
    )
    assert malformed.source == SYNTHESIS_SOURCE_DETERMINISTIC


def test_rejected_llm_does_not_change_spl() -> None:
    spec, spl = _context(P2)
    result = synthesize_review_only_analyst_explanation(
        original_user_request=P2,
        spec=spec,
        final_validated_spl=spl,
        llm_raw_output_provider=lambda: json.dumps(
            {
                "summary": "Uses the Authentication datamodel.",
                "what_it_does": ["Uses tstats.", "Joins failures to successes."],
                "expected_result": "The account is compromised.",
                "candidate_spl": " | tstats count from datamodel=Authentication",
            }
        ),
    )
    assert result.source == SYNTHESIS_SOURCE_DETERMINISTIC
    text = render_review_only_analyst_card_text(result, spl)
    assert spl in text
    assert "tstats" not in text
    assert "Authentication datamodel" not in text


def test_p1_synthesis_golden() -> None:
    spec, spl = _context(P1)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "user_query": P1,
            "utility_spl_draft_trace": {
                "pattern_id": "first_seen",
                "semantic_intent_spec": spec,
            },
        },
        user_query=P1,
    ).lower()
    assert "first-seen" in text or "first seen" in text or "absent" in text
    assert "7d" in text or "7 day" in text
    assert "30d" in text or "30 day" in text
    assert "same account" in text or "same user" in text
    assert "one-hour" in text or "1h" in text
    assert "join" not in text
    assert "datamodel" not in text
    assert "mitre" not in text
    assert "remediation" not in text
    assert spl.lower() in text


def test_p2_synthesis_golden() -> None:
    spec, spl = _context(P2)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "user_query": P2,
            "utility_spl_draft_trace": {
                "pattern_id": "sequence",
                "semantic_intent_spec": spec,
            },
        },
        user_query=P2,
    )
    lowered = text.lower()
    assert "more than 20" in lowered
    assert "15" in lowered
    assert "same user" in lowered and "source ip" in lowered
    assert "failure burst" in lowered
    assert "successful login" in lowered
    assert "10 minutes" in lowered or "600" in lowered
    assert "own burst" in lowered or "own" in lowered
    assert "### spl" in lowered
    assert "must be replaced with the approved authentication index" in lowered
    assert "authentication data is expected in sourcetype `pgcil:auth`" in lowered
    assert "datamodel" not in lowered
    assert "tstats" not in lowered
    assert "join" not in lowered
    assert "first-success-only" not in lowered
    assert "compromis" not in lowered
    assert spl in text


def test_p3_synthesis_golden() -> None:
    spec, spl = _context(P3)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "user_query": P3,
            "utility_spl_draft_trace": {
                "pattern_id": "parent_child",
                "semantic_intent_spec": spec,
            },
        },
        user_query=P3,
    ).lower()
    assert "powershell.exe" in text
    assert "winword.exe" in text
    assert "excel.exe" in text
    assert "same process event" in text
    assert "24h" in text or "24 hour" in text
    assert "command line contain" not in text
    assert "commands containing powershell" not in text


def test_p4_synthesis_golden() -> None:
    spec, spl = _context(P4)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "user_query": P4,
            "utility_spl_draft_trace": {
                "pattern_id": "first_seen",
                "semantic_intent_spec": spec,
            },
        },
        user_query=P4,
    ).lower()
    assert "24h" in text or "24 hour" in text
    assert "14d" in text or "14 day" in text
    assert "same host" in text
    assert "same user" not in text
    assert "regex" not in text
    assert "new host" not in text


def test_card_injects_validated_spl_not_model_spl() -> None:
    spec, spl = _context(P2)
    model_spl = "| tstats count from datamodel=Authentication"
    result = synthesize_review_only_analyst_explanation(
        original_user_request=P2,
        spec=spec,
        final_validated_spl=spl,
        llm_raw_output_provider=lambda: json.dumps(
            {
                "summary": "Review-only authentication sequence query.",
                "what_it_does": [
                    "Finds a failure burst of more than 20 failed authentication attempts within 15m.",
                    "Then a later successful login within 10 minutes.",
                    "Destination host comes from the successful-login event.",
                ],
                "expected_result": "Each row is one burst plus a later success.",
            }
        ),
    )
    text = render_review_only_analyst_card_text(result, spl)
    assert spl in text
    assert model_spl not in text
    assert "### SPL" in text
    assert "### Expected result" in text
    assert text.index("### What this query does") < text.index("### SPL")
    assert text.index("### SPL") < text.index(spl)


def test_card_text_uses_single_markdown_dash_and_unescaped_inline_code() -> None:
    synthesis = ReviewOnlyAnalystSynthesis(
        summary="Review-only authentication sequence query.",
        what_it_does=["• Finds more than 20 failed authentication attempts."],
        mappings_assumptions=[
            r"\`\<your\_index>\` must be replaced with the approved authentication index.",
            r"Authentication data is expected in sourcetype \`pgcil\:auth\`.",
        ],
        expected_result="Each row is one burst plus a later success.",
        source=SYNTHESIS_SOURCE_DETERMINISTIC,
    )
    text = render_review_only_analyst_card_text(synthesis, "search index=x")
    assert "- Finds more than 20 failed authentication attempts." in text
    assert "•" not in text
    assert "- - " not in text
    assert "`<your_index>`" in text
    assert r"\<" not in text
    assert r"\_" not in text
    assert "`pgcil:auth`" in text
    assert r"\:" not in text
