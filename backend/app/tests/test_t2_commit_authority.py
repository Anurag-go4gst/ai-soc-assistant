"""Phase-1 T2 commit hygiene: match_use_cases is the sole T2 commit authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.catalogue.live_router_bind import apply_live_catalogue_bind
from app.catalogue.match_tiers import match_catalogue_tier
from app.chat.pipeline import _selected_use_case
from app.chat.query_signals import extract_query_signals
from app.chat.session_context import pins_from_pipeline_state, resolve_session_context
from app.chat.session_store import SessionPins, clear_all_session_pins_for_tests, save_session_pins
from app.config import settings
from app.coverage.question_runtime_map import list_question_runtime_entries
from app.query_understanding.parser import understand_query
from app.schemas.requests import ChatRequest
from app.schemas.responses import PlaceholderResponse
from app.use_cases.registry import match_use_cases

_EXACT_105_PATHS = frozenset({"exact_105_question", "exact_105_plus_use_case_catalog"})


def test_zero_day_and_negated_sop_abstain() -> None:
    assert match_use_cases("We have no playbook for VPN zero-day response - write one for us.") == []
    assert match_use_cases("We have no SOP for this zero-day. Write one.") == []


def test_exposure_without_sop_intent_does_not_bind_sop() -> None:
    query = (
        "We have a SOAR playbook. Determine whether we are exposed and what "
        "immediate controls we should apply."
    )
    assert [m.use_case_id for m in match_use_cases(query)] == []


def test_genuine_sop_still_commits() -> None:
    matches = match_use_cases("Show me the SOP for phishing response.")
    assert matches
    assert matches[0].use_case_id == "soc_show_sop"


def test_close_candidates_abstain_when_margin_is_too_thin(monkeypatch) -> None:
    from app.use_cases import registry as use_case_registry

    query = "vpn login failures"
    committed = match_use_cases(query)
    assert committed, "production 0.10 band still commits this race"
    monkeypatch.setattr(use_case_registry, "_BIND_MARGIN_TOO_CLOSE", 0.20)
    assert match_use_cases(query) == []


def test_parser_primary_use_case_comes_only_from_committed_match_use_cases() -> None:
    queries = [
        "Show me the SOP for phishing response.",
        "Investigate failed login spike on APP-01",
        "We have no playbook for VPN zero-day response - write one for us.",
        "We have a SOAR playbook. Determine whether we are exposed and what immediate controls we should apply.",
        "What is the weather in Paris tomorrow?",
    ]
    for query in queries:
        committed = match_use_cases(query)
        understanding = understand_query(query)
        assert list(understanding.mapped_use_case_ids) == [item.use_case_id for item in committed], query
        if not committed:
            assert understanding.deterministic_match_path != "use_case_catalog", query
            assert understanding.use_case_match_source is None, query
        else:
            assert understanding.deterministic_match_path in {
                "use_case_catalog",
                "exact_105_plus_use_case_catalog",
            }, (query, understanding.deterministic_match_path)


def test_verbatim_105_questions_stay_on_exact_paths() -> None:
    """STOP condition: a verbatim 105 must not leave the exact T1 paths."""
    drifted: list[tuple[str, str, str]] = []
    for entry in list_question_runtime_entries():
        question = str(entry.get("question") or "")
        ref = str(entry.get("question_ref") or "")
        if not question:
            continue
        path = understand_query(question).deterministic_match_path
        if path not in _EXACT_105_PATHS:
            drifted.append((ref, path, question[:80]))
    assert drifted == []


def test_t2_abstain_is_not_populated_by_live_catalogue_bind() -> None:
    query = "We have no playbook for VPN zero-day response - write one for us."
    assert match_use_cases(query) == []
    understanding = understand_query(query)
    selected = _selected_use_case(query)
    assert selected is None
    out, _routed, _mappings, catalogue = apply_live_catalogue_bind(
        query=query,
        query_understanding=understanding,
        selected_use_case=selected,
        routed={"skill": "knowledge_recall"},
        candidate_mappings={},
    )
    assert out is None
    assert catalogue.use_case_id is None
    assert catalogue.accepted is False


def test_exclusion_abstain_cannot_be_bypassed_by_fuzzy_alias() -> None:
    query = (
        "We have a SOAR playbook. Determine whether we are exposed to a failed lgon spike."
    )
    assert match_use_cases(query) == []
    result = match_catalogue_tier(query)
    assert result.use_case_id is None
    assert result.match_path == "out_of_registry"
    understanding = understand_query(query)
    out, _routed, _mappings, catalogue = apply_live_catalogue_bind(
        query=query,
        query_understanding=understanding,
        selected_use_case=_selected_use_case(query),
        routed={"skill": "knowledge_recall"},
        candidate_mappings={},
    )
    assert out is None
    assert catalogue.accepted is False
    assert catalogue.use_case_id is None


def test_exact_105_authority_is_never_overwritten_by_live_catalogue_bind() -> None:
    question = next(
        str(entry.get("question") or "")
        for entry in list_question_runtime_entries()
        if entry.get("question")
    )
    understanding = understand_query(question)
    assert understanding.deterministic_match_path in _EXACT_105_PATHS
    selected = _selected_use_case(question)
    out, _routed, _mappings, catalogue = apply_live_catalogue_bind(
        query=question,
        query_understanding=understanding,
        selected_use_case=selected,
        routed={"skill": "spl_generation"},
        candidate_mappings={},
    )
    assert (None if out is None else out.use_case_id) == (
        None if selected is None else selected.use_case_id
    )
    assert catalogue.decision_reason in {
        "observed_catalogue_authority",
        "exact_authority_preserved",
    }


def test_signal_tie_break_only_selects_among_committed_candidates() -> None:
    empty = "What is the weather in Paris tomorrow?"
    assert match_use_cases(empty) == []
    assert (
        _selected_use_case(
            empty,
            query_signals={"powershell_context": True, "dns_beaconing": True},
        )
        is None
    )

    query = "Investigate suspicious powershell command and failed login spike"
    committed_ids = {item.use_case_id for item in match_use_cases(query, limit=5)}
    assert "edr_powershell_suspicious_command" in committed_ids
    selected = _selected_use_case(query, query_signals=extract_query_signals(query))
    assert selected is not None
    assert selected.use_case_id in committed_ids
    assert selected.use_case_id == "edr_powershell_suspicious_command"


def test_canonical_spl_action_is_authoritative_over_topical_hunt() -> None:
    """Explicit generate/optimize action outranks the named detection subject.

    Reuses ``meta_output_artifact`` + canonical intent_patterns; does not
    special-case soc_generate_spl or raise the 0.10 hunt-vs-hunt band.
    """
    generate_failed = match_use_cases("Generate SPL for failed logins")
    assert generate_failed
    assert generate_failed[0].use_case_id == "soc_generate_spl"
    assert all(item.use_case_id != "auth_failed_login_spike" for item in generate_failed)

    generate_mfa = match_use_cases("Generate SPL for MFA failures")
    assert generate_mfa
    assert generate_mfa[0].use_case_id == "soc_generate_spl"

    investigate = match_use_cases("Investigate failed logins")
    assert investigate
    assert investigate[0].use_case_id != "soc_generate_spl"

    hunt = match_use_cases("Investigate failed login spike on APP-01")
    assert hunt
    assert hunt[0].use_case_id == "auth_failed_login_spike"


def test_canonical_optimize_action_is_also_authoritative_over_topic() -> None:
    matches = match_use_cases("Optimize SPL for failed logins")
    assert matches
    assert matches[0].use_case_id == "soc_optimize_spl"


def test_explicit_mitre_mapping_action_outranks_topical_hunt() -> None:
    mapped = match_use_cases(
        "Map 148 failed login attempts across 12 accounts from external IPs to MITRE. "
        "There is no successful login, no endpoint telemetry, and no evidence of credential dumping."
    )
    assert mapped
    assert mapped[0].use_case_id == "soc_map_alert_mitre"
    assert mapped[0].primary_skill == "mitre_mapping"

    explicit = match_use_cases("Map this alert to MITRE")
    assert explicit
    assert explicit[0].use_case_id == "soc_map_alert_mitre"


def test_critical_notable_mitre_review_stays_the_review_capability() -> None:
    matches = match_use_cases(
        "Show me all critical alerts in the last 6 hours, cross-reference with MITRE ATT&CK, "
        "and check if any affected hosts have unpatched CVEs"
    )
    assert matches
    assert matches[0].use_case_id == "critical_notable_mitre_review"


def test_ambiguous_mitre_wording_does_not_coin_flip_mapping_vs_review() -> None:
    t1110 = match_use_cases("What does MITRE ATT&CK T1110 cover?")
    assert t1110
    assert t1110[0].use_case_id == "soc_map_alert_mitre"
    assert all(item.use_case_id != "critical_notable_mitre_review" for item in t1110)
    assert match_use_cases("What is MITRE ATT&CK?")[0].use_case_id != "critical_notable_mitre_review"


def test_hybrid_hunt_with_playbook_mention_keeps_the_hunt() -> None:
    matches = match_use_cases(
        "Find users with the highest failed login count in the last 24 hours, "
        "exclude service accounts, and tell me the analyst next action as per our playbook."
    )
    assert matches
    assert matches[0].use_case_id == "auth_failed_login_top_users_exclude_service_accounts"
    assert matches[0].use_case_id != "soc_show_sop"


def test_catalogue_inventory_phrases_bind_the_meta_row() -> None:
    from app.knowledge.mapping_exports import format_catalogue_inventory_answer

    for query in (
        "What questions do you support?",
        "What's in the catalogue?",
        "Show catalogue",
        "List use cases",
    ):
        matches = match_use_cases(query)
        assert matches, query
        assert matches[0].use_case_id == "soc_show_catalogue_index", query
        assert matches[0].primary_skill == "knowledge_recall"
        assert matches[0].default_spl_template is None
    answer = format_catalogue_inventory_answer()
    assert "knowledge/meta" in answer
    assert "does not generate or execute SPL" in answer
    assert "`soc_show_catalogue_index`" in answer
    assert "Frozen 105 questions: 105" in answer


def test_incidental_catalogue_word_does_not_bind_inventory() -> None:
    sop = match_use_cases("Which SOP in the catalogue covers phishing?")
    assert sop
    assert sop[0].use_case_id == "soc_show_sop"
    hunt = match_use_cases("Review the catalogue of failed login events on APP-01")
    assert hunt
    assert hunt[0].use_case_id != "soc_show_catalogue_index"
    assert match_use_cases("catalogue") == []


def test_inventory_row_does_not_add_q106_or_change_105_map() -> None:
    entries = list_question_runtime_entries()
    refs = [str(entry.get("question_ref") or "") for entry in entries]
    assert len(entries) == 105
    assert "q0.q106" not in refs
    assert all(ref.startswith("q0.q") for ref in refs if ref)


def test_abstained_first_turn_does_not_persist_a_use_case_for_the_next_question(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    clear_all_session_pins_for_tests()
    pins = pins_from_pipeline_state(
        session_id="sess-t2-abstain",
        trace_id="t-abstain",
        response=PlaceholderResponse(
            trace_id="t-abstain",
            message="ok",
            note="ok",
            user_query="We have no playbook for VPN zero-day response - write one for us.",
            selected_skill="knowledge_recall",
            selected_use_case=None,
        ),
        state={},
    )
    assert pins.last_use_case_id is None
    save_session_pins(pins)
    standalone = resolve_session_context(
        ChatRequest(
            message="Investigate failed login spike on APP-01",
            session_id="sess-t2-abstain",
        )
    )
    assert standalone.apply_use_case_id is None
    assert standalone.follow_up_kind is None


def test_committed_first_turn_mitre_follow_up_keeps_use_case_continuity(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    clear_all_session_pins_for_tests()
    committed = match_use_cases("Investigate failed login spike on APP-01")
    assert committed
    save_session_pins(
        SessionPins(
            session_id="sess-t2-follow",
            last_trace_id="t-commit",
            last_alert_id="ALT-2024-0891",
            last_use_case_id=committed[0].use_case_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    follow_up = resolve_session_context(
        ChatRequest(message="now map it to MITRE", session_id="sess-t2-follow")
    )
    assert follow_up.follow_up_kind == "mitre"
    assert follow_up.apply_use_case_id == committed[0].use_case_id
    assert follow_up.status.used_previous_context is True


def test_new_standalone_hunt_does_not_inherit_previous_use_case(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_session_context_enabled", True)
    clear_all_session_pins_for_tests()
    save_session_pins(
        SessionPins(
            session_id="sess-t2-standalone",
            last_trace_id="t-prior",
            last_alert_id="ALT-2024-0891",
            last_use_case_id="auth_failed_login_spike",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
    )
    standalone = resolve_session_context(
        ChatRequest(
            message="Investigate DNS beaconing from host dns-01",
            session_id="sess-t2-standalone",
        )
    )
    assert standalone.follow_up_kind is None
    assert standalone.apply_use_case_id is None
