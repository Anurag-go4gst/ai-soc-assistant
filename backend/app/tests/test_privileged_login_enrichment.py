"""Curated enrichment: auth_privileged_login_anomaly investigation checklist.

Content prepared ahead of WS2 (Anurag-curated, 2026-06-11). The governed
template `privileged_account_failure` is still `planned`, so the record is
deliberately metadata-only at runtime — these tests pin both the content
contract and the not-yet-runtime-active gating so later template activation
is a conscious step, not an accident.
"""

from __future__ import annotations

from app.use_cases.content_enrichment import (
    get_content_enrichment,
    load_curated_enrichment_context,
    resolve_use_case_activation,
)

USE_CASE = "auth_privileged_login_anomaly"


def test_record_present_with_complete_checklist_content() -> None:
    record = get_content_enrichment(USE_CASE)
    assert record is not None
    assert len(record.get("analyst_checklist") or []) >= 6
    assert len(record.get("investigation_workflow") or []) >= 6
    assert len(record.get("limitations") or []) >= 4
    assert record.get("mitre_candidates") == ["T1078"]
    assert "account_compromise" in (record.get("not_claimed_defaults") or [])


def test_checklist_covers_required_validation_areas() -> None:
    record = get_content_enrichment(USE_CASE)
    text = " ".join(record["analyst_checklist"] + record["investigation_workflow"]).lower()
    for topic in (
        "normal access pattern",
        "mfa",
        "crown-jewel",
        "ot",
        "post-login",
        "credential stores",
        "escalate",
    ):
        assert topic in text, topic


def test_limitations_forbid_compromise_claims() -> None:
    record = get_content_enrichment(USE_CASE)
    text = " ".join(record["limitations"]).lower()
    assert "does not confirm compromise" in text
    assert "hil" in text or "change approval" in text


def test_answer_rules_keep_mitre_candidate_only() -> None:
    record = get_content_enrichment(USE_CASE)
    rules = " ".join(record["answer_rules"]).lower()
    assert "t1078" in rules
    assert "candidate" in rules
    assert "source-grounded" in rules


def test_record_is_metadata_only_until_template_activates() -> None:
    """Honest gating pin: planned template => no runtime enrichment surfacing.

    When `privileged_account_failure` flips to active (or the SOP channel is
    chosen), this test must be revisited deliberately.
    """
    record = get_content_enrichment(USE_CASE)
    assert record.get("spl_template_status") == "planned"

    activation = resolve_use_case_activation(USE_CASE)
    assert activation.governed_enrichment_load_allowed is False
    assert "planned_allows_trace_metadata_only" in activation.reasons
    assert load_curated_enrichment_context(USE_CASE) is None


def test_safety_review_flags_all_true() -> None:
    record = get_content_enrichment(USE_CASE)
    safety = record.get("safety_review") or {}
    assert safety and all(safety.values())
