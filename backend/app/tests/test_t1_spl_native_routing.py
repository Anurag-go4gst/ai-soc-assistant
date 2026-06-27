"""Regression tests for T0/T1 SPL-native routing and review-only SPL generation.

Covers the architecture decision that ``soc_generate_spl``/``soc_optimize_spl``
are T1 SPL-native meta workflows (LLM-advisory eligible, never auto-T0) and the
deterministic T2 shape/repair pipeline that produces review-only SPL drafts.
"""
from __future__ import annotations

from app.llm.sidecar_skip_policy import should_skip_sidecar
from app.query_understanding.parser import understand_query
from app.spl.deterministic_spl_repair import repair_spl_candidate
from app.spl.governed_llm_spl import parse_spl_candidate
from app.spl.t2_generation import generate_review_only_spl
from app.spl.t2_shape import extract_spl_shape, normalize_runtime_operation
from app.use_cases.routing_authority import catalog_authority_row, llm_advisory_recommended


# --------------------------------------------------------------------------- #
# A. soc_generate_spl routing                                                  #
# --------------------------------------------------------------------------- #
def test_generate_spl_routes_t1_native_not_t0_exact() -> None:
    result = understand_query("Generate SPL for failed logins")
    assert "soc_generate_spl" in result.mapped_use_case_ids
    row = catalog_authority_row("soc_generate_spl")
    assert row is not None and row["registry_tier"] == "t1_spl_native"
    # LLM advisory path is eligible — this turn is NOT a deterministic T0 skip.
    assert result.llm_advisory_recommended is True
    skip, reason = should_skip_sidecar(
        match_path=result.deterministic_match_path, catalog_row=row
    )
    assert skip is False
    assert reason is None


def test_bare_spl_query_no_longer_greedy_wins() -> None:
    # "spl query" alone must not capture soc_generate_spl when stronger SOC
    # signals are present; the OT performance hunt is out-of-registry, not a T0
    # catalogue exact match.
    result = understand_query(
        "Provide a complete SPL query for index=scada_perf using earliest=-30d "
        "to compute eventstats stdev baseline by rtu_id and filter anomalies in "
        "last 24h using transmission_error_count"
    )
    assert result.deterministic_match_path != "exact_105_question"
    assert result.llm_advisory_recommended is True


def test_detection_family_beats_weak_spl_modifier() -> None:
    # must_not_override_detection_family: a real detection family wins over the
    # weak soc_generate_spl modifier when one is named.
    result = understand_query("Write SPL to detect impossible travel from VPN logs")
    assert result.mapped_use_case_ids[0] != "soc_generate_spl"


def test_incidental_generate_spl_mention_does_not_hijack_detection_family() -> None:
    # "generate spl" matched only via display name (non-canonical) alongside a
    # detection family -> demoted; the detection family wins.
    result = understand_query("Please generate spl dashboards for failed logins")
    assert result.mapped_use_case_ids[0] == "auth_failed_login_spike"


def test_canonical_generate_spl_for_keeps_meta_route() -> None:
    # Explicit canonical "generate spl for <topic>" stays soc_generate_spl even
    # when the topic names a detection family.
    result = understand_query("Generate SPL for impossible travel detection")
    assert result.mapped_use_case_ids[0] == "soc_generate_spl"


def test_operation_hint_no_false_positive_in_unrelated_words() -> None:
    from app.spl.t2_pre_parse import pre_parse_spl_tokens

    # "top"/"then"/"rank" inside laptop/strengthen/frankly must not fire hints.
    assert pre_parse_spl_tokens("Generate SPL for laptop inventory drift").operation_hints == []
    assert pre_parse_spl_tokens("Generate SPL to strengthen auth posture").operation_hints == []
    # Genuine signals still fire.
    assert "aggregate_and_rank" in pre_parse_spl_tokens("top talkers by bytes").operation_hints


# --------------------------------------------------------------------------- #
# B. SCADA threshold anomaly                                                   #
# --------------------------------------------------------------------------- #
_SCADA_QUERY = (
    "Provide a complete SPL query for index=scada_perf using earliest=-30d to "
    "compute eventstats stdev baseline by rtu_id and filter anomalies in last 24h "
    "using transmission_error_count."
)


def test_scada_threshold_anomaly_shape() -> None:
    shape = extract_spl_shape(_SCADA_QUERY)
    assert shape.runtime_operation == "threshold_anomaly"
    assert shape.source_profile == "scada_perf"
    assert "rtu_id" in shape.entity_fields
    assert "transmission_error_count" in shape.metric_fields


def test_scada_threshold_anomaly_review_only_renderable_no_dns_rejection() -> None:
    artifact = generate_review_only_spl(_SCADA_QUERY)
    assert artifact.execution_eligible is False
    assert artifact.review_required is True
    assert artifact.renderable is True
    assert "index=scada_perf" in artifact.candidate_spl
    # No DNS relevance heuristic should appear for a SCADA performance query.
    assert "dns" not in artifact.candidate_spl.lower()


def test_scada_invalid_over_pattern_is_repaired() -> None:
    shape = extract_spl_shape(_SCADA_QUERY)
    repaired = repair_spl_candidate(
        shape,
        llm_candidate_spl="index=scada_perf | eventstats stdev(transmission_error_count) over rtu_id",
    )
    assert repaired.blocked is False
    assert "rewrote_invalid_over_to_eventstats_by" in repaired.repairs
    assert " over " not in repaired.candidate_spl
    assert "eventstats" in repaired.candidate_spl and " by rtu_id" in repaired.candidate_spl


# --------------------------------------------------------------------------- #
# C. Cisco ASA IOC lookup                                                      #
# --------------------------------------------------------------------------- #
_ASA_QUERY = (
    "Generate SPL to correlate power_sector_iocs.csv indicator_ip with Cisco ASA "
    "traffic in index=cisco_asa against dest_ip for last 24h."
)


def test_asa_ioc_lookup_correlation() -> None:
    artifact = generate_review_only_spl(_ASA_QUERY)
    assert artifact.runtime_operation == "lookup_correlation"
    assert artifact.source_profile == "cisco_asa"
    assert artifact.renderable is True
    spl = artifact.candidate_spl
    assert "lookup power_sector_iocs.csv indicator_ip as dest_ip" in spl
    # table uses space-separated fields, not commas.
    assert "table src_ip dest_ip actions event_count matched_ioc" in spl
    # action/actions alias mismatch repaired: table references `actions`.
    assert "values(action) as actions" in spl
    assert "table src_ip dest_ip action " not in spl


# --------------------------------------------------------------------------- #
# D. Exact-105 preservation + unsafe/HIL precedence                            #
# --------------------------------------------------------------------------- #
_AUTHORITY_READY = {"effective_promotion_status": "authority_ready"}


def test_exact_105_skips_llm_only_after_promotion_lifecycle_ready() -> None:
    skip, reason = should_skip_sidecar(match_path="exact_105_question")
    assert skip is False
    assert reason is None

    skip, reason = should_skip_sidecar(
        match_path="exact_105_question",
        promotion_lifecycle_summary=_AUTHORITY_READY,
    )
    assert skip is True
    assert reason == "deterministic_exact_match_t0"


def test_plain_catalog_row_intent_advisor_not_t0() -> None:
    # Intent-advisor T0 is exact-105 / unsafe-HIL / explicitly-authoritative rows
    # only.  A plain catalogue row does NOT skip the advisor.
    skip, _ = should_skip_sidecar(
        match_path="use_case_catalog", catalog_row=catalog_authority_row("soc_explain_spl")
    )
    assert skip is False


def test_explicit_t0_authority_row_skips_advisor() -> None:
    # An explicit opt-in (t0_exact_authority=true) suppresses the advisor.
    explicit = {"t0_exact_authority": True, "t0_exact_authority_explicit": True}
    skip, reason = should_skip_sidecar(
        match_path="use_case_catalog",
        catalog_row=explicit,
    )
    assert skip is False
    assert reason is None

    skip, reason = should_skip_sidecar(
        match_path="use_case_catalog",
        catalog_row=explicit,
        promotion_lifecycle_summary=_AUTHORITY_READY,
    )
    assert skip is True
    assert reason == "deterministic_exact_match_t0"
    # Defaulted (non-explicit) true does NOT count as authoritative.
    defaulted = {"t0_exact_authority": True, "t0_exact_authority_explicit": False}
    skip2, _ = should_skip_sidecar(match_path="use_case_catalog", catalog_row=defaulted)
    assert skip2 is False


def test_plain_catalog_route_notion_stays_conservative() -> None:
    # The ROUTE notion (LLM override gate) stays confident for plain catalogue
    # rows so the LLM cannot override a correct deterministic route.
    assert llm_advisory_recommended("use_case_catalog", catalog_row=catalog_authority_row("soc_explain_spl")) is False
    # T1 SPL-meta rows still invite route assist.
    assert llm_advisory_recommended("use_case_catalog", catalog_row=catalog_authority_row("soc_generate_spl")) is True


# --------------------------------------------------------------------------- #
# E. Safety                                                                    #
# --------------------------------------------------------------------------- #
def test_unsafe_commands_block_candidate() -> None:
    shape = extract_spl_shape(_SCADA_QUERY)
    for unsafe in ("index=scada_perf | delete", "index=scada_perf | outputlookup evil.csv", "index=* | stats count"):
        repaired = repair_spl_candidate(shape, llm_candidate_spl=unsafe)
        assert repaired.blocked is True
        assert repaired.candidate_spl == ""
        assert repaired.block_reasons


def test_llm_output_always_review_only() -> None:
    parsed = parse_spl_candidate(
        '```json\n{"runtime_operation": "threshold_anomaly", "candidate_spl": "index=scada_perf", '
        '"execution_eligible": true}\n```'
    )
    assert parsed.parsed_ok is True
    # Model cannot self-assert executability.
    assert parsed.to_dict()["execution_eligible"] is False
    assert parsed.to_dict()["review_required"] is True


def test_malformed_llm_output_fails_closed() -> None:
    parsed = parse_spl_candidate("not json at all")
    assert parsed.parsed_ok is False
    assert parsed.candidate_spl == ""


def test_normalize_runtime_operation_labels() -> None:
    assert normalize_runtime_operation("anomaly detection") == "threshold_anomaly"
    assert normalize_runtime_operation("threat feed correlation") == "lookup_correlation"
    assert normalize_runtime_operation("top talkers") == "aggregate_and_rank"
    assert normalize_runtime_operation("bogus") == "unknown"
