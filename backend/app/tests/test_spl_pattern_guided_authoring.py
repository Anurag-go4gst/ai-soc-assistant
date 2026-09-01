"""P1 pattern-guided LLM authoring: vetted first_seen topology, preprocessor, traces."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import pytest

from app.chat.review_only_spl_renderer import (
    render_pattern_guided_review_answer,
    render_user_bound_spl_utility_answer,
)
from app.config import settings
from app.llm.clients.local_chat_client import ChatResult
from app.spl.llm_fallback import (
    AUTHORING_SOURCE_LEGACY_COMPILER_RESCUE,
    AUTHORING_SOURCE_LLM_PATTERN_NORMALIZED,
    AUTHORING_SOURCE_LLM_PATTERN_PRIMARY,
    PATTERN_ADAPTATION_JSON_SCHEMA,
    _AUTHORING_FEW_SHOTS,
    generate_llm_spl_fallback,
    select_vetted_authoring_pattern,
    spl_advisory_prompts,
)
from app.spl.llm_plan_compiler import compile_intent_spec_to_spl
from app.spl.review_only_spl_postprocessor import (
    _normalize_prefix_like_wildcards,
    normalize_review_only_spl,
)
from app.spl.spl_intent_spec import build_spl_intent_spec
from app.spl.spl_semantic_fidelity import validate_semantic_fidelity
from app.spl.utility_spl_authoring import (
    _build_utility_llm_context,
    candidate_from_universal_utility_authoring,
)

P1 = (
    "Write an SPL query to find successful Windows logons (EventCode=4624) by "
    "accounts matching admin-* or svc-* during the last 7 days. Compare them with "
    "a separate preceding 30-day history for the same account and flag destination "
    "hosts that the account had not previously accessed. Group results into "
    "one-hour windows and return the user, new host, source IP, and distinct count "
    "of new hosts. Do not execute the query."
)


class _Telemetry:
    def record_step(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_spl_validation(self, *args: Any, **kwargs: Any) -> None:
        return None


def _profile() -> Any:
    return __import__(
        "app.splunk.capabilities", fromlist=["build_splunk_capability_profile"]
    ).build_splunk_capability_profile(required_saia_tool="saia_generate_spl")


def _llm_payload(spl: str) -> str:
    return json.dumps(
        {
            "status": "candidate_generated",
            "candidate_spl": spl,
            "index": "<index>",
            "sourcetype": "<sourcetype>",
            "unresolved_slots": ["index"],
            "assumptions": ["review-only pattern adaptation"],
            "required_fields": ["user", "host", "src_ip"],
            "execution_eligible": False,
            "governed": False,
            "catalog_approved": False,
        }
    )


@pytest.fixture
def spl_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_soc_spl_draft_preview_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_enabled", True)
    monkeypatch.setattr(settings, "ai_soc_llm_mode", "local")
    monkeypatch.setattr(settings, "ai_soc_llm_utility_spl_draft_enabled", True)
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile",
        lambda: {},
    )
    monkeypatch.setattr(
        "app.spl.utility_spl_authoring.load_persisted_source_profile_document",
        lambda: {"values": {}, "field_sources": {}},
    )


def _run(query: str, *, provider) -> tuple[dict[str, Any], dict[str, Any]]:
    result = candidate_from_universal_utility_authoring(
        trace_id="pattern-guided-p1",
        skill="spl_generation",
        user_query=query,
        telemetry=_Telemetry(),
        profile=_profile(),
        spl_governance=None,
        llm_raw_output_provider=provider,
    )
    assert result is not None
    return result


def test_first_seen_pattern_is_vetted_compiler_topology() -> None:
    spec = build_spl_intent_spec(P1)
    pattern = select_vetted_authoring_pattern(spec)
    assert pattern is not None
    assert pattern["pattern_id"] == "first_seen"
    assert pattern["pattern_enabled"] is True
    body = str(pattern["payload"]["candidate_spl"])
    assert "streamstats values(baseline_object)" in body
    assert "mvmap(baseline_objects, if(baseline_objects==object_norm,1,0))" in body
    assert "seen_before=coalesce(max(exact_matches),0)" in body.replace(" ", "")
    assert "| where seen_before=0" in body
    assert re.search(r"mvfilter\s*\(\s*\w+\s*==", body) is None
    assert "mvfind" not in body.lower()
    assert "4624" not in body
    assert "admin-" not in body
    assert "svc-" not in body
    assert "EventCode" not in body
    compiled = compile_intent_spec_to_spl(spec)
    assert "streamstats" in compiled
    assert "values(baseline_object)" in compiled
    assert "mvmap(baseline_objects" in compiled
    assert "seen_before=0" in compiled.replace(" ", "")
    assert re.search(r"mvfilter\s*\(\s*\w+\s*==", compiled) is None
    fidelity = validate_semantic_fidelity(spec, compiled)
    assert fidelity["passed"] is True, fidelity


def test_parent_child_pattern_is_generic() -> None:
    spec = build_spl_intent_spec(P3)
    assert spec["analysis_shape"] == "parent_child"
    pattern = select_vetted_authoring_pattern(spec)
    assert pattern is not None
    assert pattern["pattern_id"] == "parent_child"
    assert pattern["pattern_enabled"] is True
    body = str(pattern["payload"]["candidate_spl"])
    lowered = body.lower()
    assert "powershell" not in lowered
    assert "winword" not in lowered
    assert "excel" not in lowered
    assert "earliest=-24h" not in lowered
    assert "like(child_process" in lowered
    assert "like(parent_process" in lowered
    assert "count as event_count" in lowered
    compiled = compile_intent_spec_to_spl(spec)
    fid = validate_semantic_fidelity(spec, compiled)
    assert fid.get("passed") is True, fid


def test_p3_prompt_preserves_parent_child_topology() -> None:
    spec = build_spl_intent_spec(P3)
    ctx = _build_utility_llm_context(P3, family="unmapped_live_data_request", intent_spec=spec)
    system, user = spl_advisory_prompts(P3, utility_authoring=True, context=ctx)
    assert "PRESERVE PATTERN TOPOLOGY" in system
    assert "Selected governed pattern: parent_child" in system
    assert "streamstats values(baseline_object)" not in system
    example_start = system.find("Worked example")
    assert example_start > 0
    example = system[example_start:]
    assert "powershell" not in example.lower()
    assert "winword" not in example.lower()
    assert "excel" not in example.lower()
    assert "child.exe" in example.lower()
    assert P3 in user


def test_p3_preprocessor_does_not_swap_parent_child() -> None:
    spec = build_spl_intent_spec(P3)
    compiled = compile_intent_spec_to_spl(spec)
    out = normalize_review_only_spl(
        compiled,
        {
            "is_explicit_spl_authoring": True,
            "llm_generated": True,
            "semantic_analyst_intent": spec,
        },
    )
    compact = out.normalized_spl.replace(" ", "").lower()
    assert "like(image" in compact
    assert "like(parentimage" in compact
    assert "powershell.exe" in compact
    assert "winword.exe" in compact
    inverted = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        'Image="*winword.exe" ParentImage="*powershell.exe"\n'
        "| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen "
        "values(Image) as child_process values(ParentImage) as parent_process "
        "values(CommandLine) as command_line by host, user"
    )
    inverted_out = normalize_review_only_spl(
        inverted,
        {
            "is_explicit_spl_authoring": True,
            "llm_generated": True,
            "semantic_analyst_intent": spec,
        },
    )
    still = inverted_out.normalized_spl.replace(" ", "").lower()
    assert 'image="*winword.exe"' in still
    assert 'parentimage="*powershell.exe"' in still
    fid = validate_semantic_fidelity(spec, inverted_out.normalized_spl)
    assert "parent_child_inverted" in (fid.get("losses") or [])


def test_p3_renderer_describes_same_event_parent_child() -> None:
    spec = build_spl_intent_spec(P3)
    spl = compile_intent_spec_to_spl(spec)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "utility_spl_draft_trace": {
                "pattern_id": "parent_child",
                "pattern_selected": True,
                "semantic_intent_spec": spec,
            },
        }
    )
    lowered = text.lower()
    assert text.startswith("Review-only SPL draft — not executed")
    assert "What this query does" in text
    assert "powershell.exe launched by winword.exe or excel.exe" in lowered
    assert "same process event" in lowered
    assert "grouped by host and user" in lowered
    assert "Filters successful Windows logons (EventCode=4624)." not in text
    assert "Investigation steps" not in text
    assert "MITRE" not in text
    assert "No query was executed." in text


def test_p1_prompt_preserves_pattern_topology() -> None:
    spec = build_spl_intent_spec(P1)
    ctx = _build_utility_llm_context(P1, family="unmapped_live_data_request", intent_spec=spec)
    system, user = spl_advisory_prompts(P1, utility_authoring=True, context=ctx)
    combined = system + "\n" + user
    assert "PRESERVE PATTERN TOPOLOGY" in system
    assert "streamstats values(baseline_object)" in system
    assert "mvmap" in system
    assert "seen_before" in system
    assert re.search(r"mvfilter\s*\(\s*baseline_objects\s*==", system) is None
    assert "Selected governed pattern: first_seen" in system
    assert "windows_account_lockout" not in system
    assert "- end with `head 100`;" not in system
    assert "do NOT end with `head 100`" in system
    example_start = system.find("Worked example")
    assert example_start > 0
    example = system[example_start:]
    assert "4624" not in example
    assert "admin-*" not in example
    assert P1 in user


def test_preprocessor_prefix_like_only_when_contract_is_prefix() -> None:
    spec = build_spl_intent_spec(P1)
    raw = (
        'search index=wineventlog earliest=-37d latest=now EventCode=4624\n'
        '| eval user_norm=lower(coalesce(user, "unknown"))\n'
        '| where like(user_norm,"*admin-*") OR like(user_norm,"svc-*")'
    )
    rewritten, changes = _normalize_prefix_like_wildcards(raw, spec)
    assert 'like(user_norm,"admin-%")' in rewritten
    assert 'like(user_norm,"svc-%")' in rewritten
    assert "*admin-*" not in rewritten
    assert changes
    unrelated = '| where like(process,"*powershell*")'
    same, none = _normalize_prefix_like_wildcards(unrelated, spec)
    assert same == unrelated
    assert none == []


def test_injected_faithful_p1_is_llm_pattern_not_compiler_rescue(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    candidate, validation = _run(P1, provider=lambda: _llm_payload(compiled))
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert candidate.get("spl_authoring_unavailable") is False
    assert trace.get("pattern_id") == "first_seen"
    assert candidate.get("authoring_source") in {
        AUTHORING_SOURCE_LLM_PATTERN_PRIMARY,
        AUTHORING_SOURCE_LLM_PATTERN_NORMALIZED,
    }
    assert trace.get("legacy_compiler_rescue") is not True
    assert trace.get("llm_pattern_success") is True
    assert (trace.get("raw_llm_spl") or "").strip()
    assert validation.get("approved") is False
    assert validation.get("normalized_spl") in (None, "")
    assert candidate.get("execution_eligible") is False
    final = str(candidate.get("candidate_spl") or "")
    assert "earliest=-37d" in final.replace(" ", "")
    assert "mvmap(baseline_objects" in final
    assert "seen_before=0" in final.replace(" ", "")
    assert re.search(r"mvfilter\s*\(\s*\w+\s*==", final) is None
    assert "streamstats" in final


def test_malformed_llm_uses_legacy_compiler_rescue(spl_flags: None) -> None:
    candidate, validation = _run(P1, provider=lambda: "{{{{not json")
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert candidate.get("authoring_source") == AUTHORING_SOURCE_LEGACY_COMPILER_RESCUE
    assert trace.get("legacy_compiler_rescue") is True
    assert trace.get("llm_pattern_success") is False
    assert candidate.get("spl_authoring_unavailable") is False
    assert (candidate.get("candidate_spl") or "").strip()
    assert validation.get("approved") is False
    assert validation.get("normalized_spl") in (None, "")


def test_p1_mutants_fail_validator() -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    regex = compiled.replace(
        "mvmap(baseline_objects, if(baseline_objects==host_norm,1,0))",
        "mvfind(baseline_objects, host_norm)",
    )
    regex_fid = validate_semantic_fidelity(spec, regex)
    assert regex_fid.get("passed") is False
    assert "regex_membership" in (regex_fid.get("losses") or [])

    seven_only = compiled.replace("earliest=-37d", "earliest=-7d")
    seven_fid = validate_semantic_fidelity(spec, seven_only)
    assert seven_fid.get("passed") is False

    no_stream = re.sub(
        r"\|\s*streamstats values\(baseline_object\) as baseline_objects by [^\s|]+",
        "| stats count by user_norm",
        compiled,
        count=1,
        flags=re.I,
    )
    acc_fid = validate_semantic_fidelity(spec, no_stream)
    assert "first_seen_subject_accumulation_missing" in (acc_fid.get("losses") or [])


def test_mvfilter_cross_field_is_rejected_while_mvmap_passes() -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    assert "mvmap(baseline_objects, if(baseline_objects==host_norm,1,0))" in compiled
    assert "seen_before=coalesce(max(exact_matches),0)" in compiled.replace(" ", "")
    assert "| where seen_before=0" in compiled
    assert validate_semantic_fidelity(spec, compiled).get("passed") is True

    replaced = compiled.replace(
        "mvmap(baseline_objects, if(baseline_objects==host_norm,1,0))",
        "mvfilter(baseline_objects == host_norm)",
    )
    replaced_fid = validate_semantic_fidelity(spec, replaced)
    assert replaced_fid.get("passed") is False
    assert "mvfilter_cross_field" in (replaced_fid.get("losses") or [])
    assert "exact_membership_missing" in (replaced_fid.get("losses") or [])

    both = (
        compiled.replace(
            "| eval exact_matches=",
            "| eval leftover=mvfilter(baseline_objects == host_norm) | eval exact_matches=",
        )
    )
    both_fid = validate_semantic_fidelity(spec, both)
    assert both_fid.get("passed") is False
    assert "mvfilter_cross_field" in (both_fid.get("losses") or [])
    assert "exact_membership_missing" in (both_fid.get("losses") or [])


def test_p4_mvfilter_cross_field_is_rejected_while_mvmap_passes() -> None:
    spec = build_spl_intent_spec(P4)
    compiled = compile_intent_spec_to_spl(spec)
    assert "mvmap(baseline_objects, if(baseline_objects==domain_norm,1,0))" in compiled
    assert validate_semantic_fidelity(spec, compiled).get("passed") is True
    replaced = compiled.replace(
        "mvmap(baseline_objects, if(baseline_objects==domain_norm,1,0))",
        "mvfilter(baseline_objects == domain_norm)",
    )
    fid = validate_semantic_fidelity(spec, replaced)
    assert fid.get("passed") is False
    assert "mvfilter_cross_field" in (fid.get("losses") or [])
    assert "exact_membership_missing" in (fid.get("losses") or [])


def test_first_seen_alias_accumulation_is_not_a_false_positive() -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    aliased = (
        compiled.replace("baseline_object", "baseline_host")
        .replace("baseline_objects", "baseline_hosts")
    )
    fid = validate_semantic_fidelity(spec, aliased)
    assert "first_seen_subject_accumulation_missing" not in (fid.get("losses") or [])
    assert fid.get("passed") is True, fid.get("losses")


def test_streamstats_alone_is_not_accumulation() -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    mere = re.sub(
        r"\|\s*streamstats values\([^)]+\) as \w+ by [^\s|]+",
        "| streamstats count as c by user_norm",
        compiled,
        count=1,
        flags=re.I,
    )
    fid = validate_semantic_fidelity(spec, mere)
    assert "first_seen_subject_accumulation_missing" in (fid.get("losses") or [])


def test_extra_src_ip_partition_fails_user_only_first_seen() -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    extra = compiled.replace(
        "streamstats values(baseline_object) as baseline_objects by user_norm",
        "streamstats values(baseline_host) as baseline_hosts by user_norm, src_ip_norm",
    ).replace(
        "eval baseline_object=if(period=\"baseline\", host_norm, null())",
        "eval baseline_host=if(period=\"baseline\", host_norm, null())",
    ).replace("baseline_objects", "baseline_hosts")
    fid = validate_semantic_fidelity(spec, extra)
    assert "first_seen_extra_correlation_key" in (fid.get("losses") or [])
    assert any("per account" in str(item) for item in (fid.get("repair_feedback") or []))
    assert "first_seen_subject_accumulation_missing" not in (fid.get("losses") or [])


def test_late_bin_after_stats_is_unreachable_grain() -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    late = compiled.replace("| bin _time span=1h | stats", "| stats").replace(
        "by user_norm, _time",
        "by user_norm | bin _time span=1h",
    )
    fid = validate_semantic_fidelity(spec, late)
    assert "required_temporal_grain_unreachable" in (fid.get("losses") or [])
    assert any("_time must still exist" in str(item) for item in (fid.get("repair_feedback") or []))


LIVE_P1_RAW = """
search index=wineventlog sourcetype=pgcil:auth earliest=-37d latest=now
| eval user_norm=lower(coalesce(user, "unknown")), src_ip_norm=coalesce(src_ip, "unknown"), host_norm=lower(coalesce(host, "unknown"))
| where EventCode=4624 AND (user LIKE "admin-*" OR user LIKE "svc-*")
| eval period=if(_time>=relative_time(now(),"-7d"),"observation","baseline")
| eval baseline_host=if(period="baseline", host_norm, null())
| sort 0 + _time
| streamstats values(baseline_host) as baseline_hosts by user_norm, src_ip_norm
| where period="observation"
| eval new_host=if(mvcount(mvfilter(baseline_hosts == host_norm))>0, null(), host_norm)
| where isnotnull(new_host)
| stats values(src_ip_norm) as src_ip, values(host_norm) as host, dc(host) as distinct_new_host_count by user_norm
| bin _time span=1h
| fields user_norm, host, src_ip_norm, distinct_new_host_count
""".strip()


def test_captured_live_p1_alias_is_not_false_positive_but_real_losses_remain() -> None:
    spec = build_spl_intent_spec(P1)
    rewritten, changes = _normalize_prefix_like_wildcards(LIVE_P1_RAW, spec)
    assert "actor_prefix_wildcard_normalized" in changes
    assert 'like(user_norm,"admin-%")' in rewritten
    fid = validate_semantic_fidelity(spec, rewritten)
    losses = fid.get("losses") or []
    assert "first_seen_subject_accumulation_missing" not in losses
    assert "first_seen_extra_correlation_key" in losses
    assert "required_temporal_grain_unreachable" in losses
    assert "output_missing:new_host" in losses
    assert fid.get("passed") is False


def test_boolean_distinct_count_is_not_host_dc() -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    mutated = compiled.replace(
        "dc(host_norm) as distinct_new_host_count",
        "max(new_host) as distinct_new_host_count",
    )
    fid = validate_semantic_fidelity(spec, mutated)
    assert "distinct_count_not_host_field" in (fid.get("losses") or [])


def test_preprocessor_infix_like_prefix_wildcards() -> None:
    spec = build_spl_intent_spec(P1)
    raw = (
        'search index=wineventlog earliest=-37d latest=now EventCode=4624\n'
        '| eval user_norm=lower(coalesce(user, "unknown"))\n'
        '| where user LIKE "admin-*" OR user LIKE "svc-*"'
    )
    rewritten, changes = _normalize_prefix_like_wildcards(raw, spec)
    assert 'like(user_norm,"admin-%")' in rewritten
    assert 'like(user_norm,"svc-%")' in rewritten
    assert "LIKE" not in rewritten
    assert "actor_prefix_wildcard_normalized" in changes
    search_star = "search index=wineventlog user=admin-*"
    same, none = _normalize_prefix_like_wildcards(search_star, spec)
    assert same == search_star
    assert none == []


def test_pattern_guided_synthesis_render(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    candidate, _validation = _run(P1, provider=lambda: _llm_payload(compiled))
    text = render_user_bound_spl_utility_answer(candidate_spl=candidate)
    assert text.startswith("Review-only SPL draft — not executed")
    assert "What this query does" in text
    assert "Mappings / assumptions" in text
    assert "No query was executed." in text
    assert "Investigation steps" not in text
    assert "MITRE" not in text
    assert compiled.split("|", 1)[0].strip()[:20] in text or "search " in text.lower()
    assert "4624" in text or "successful" in text.lower()


def test_user_bound_skeleton_keeps_concise_title() -> None:
    text = render_user_bound_spl_utility_answer(
        candidate_spl={
            "candidate_spl": "search index=pgcil_soc earliest=-30d latest=now",
            "generation_mode": "deterministic_user_bound_skeleton",
        }
    )
    assert text.startswith("Review-only - not executed")
    assert "What this query does" not in text


def test_pattern_guided_renderer_uses_spec_not_invention() -> None:
    spec = build_spl_intent_spec(P1)
    spl = compile_intent_spec_to_spl(spec)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "utility_spl_draft_trace": {
                "pattern_id": "first_seen",
                "pattern_selected": True,
                "semantic_intent_spec": spec,
            },
            "review_only_spl_postprocessor_trace": {
                "resolved_index": "wineventlog",
                "index_resolution_source": "user_explicit",
            },
        }
    )
    assert "preceding 30d" in text or "preceding 30" in text
    assert "admin-*" in text
    assert "wineventlog" in text
    assert "not executed" in text.lower()


class _CaptureClient:
    def __init__(self, *, text: str, finish_reason: str = "stop") -> None:
        self.kwargs: dict[str, Any] = {}
        self._text = text
        self._finish_reason = finish_reason

    def generate(self, **kwargs: Any) -> ChatResult:
        self.kwargs = kwargs
        return ChatResult(
            text=self._text,
            model="stub-instruct",
            latency_ms=1,
            finish_reason=self._finish_reason,
        )


def test_pattern_adaptation_uses_compact_schema(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P1)
    ctx = _build_utility_llm_context(P1, family="unmapped_live_data_request", intent_spec=spec)
    client = _CaptureClient(text="{}")
    generate_llm_spl_fallback(
        user_query=P1,
        utility_authoring=True,
        client=client,
        context=ctx,
    )
    fmt = client.kwargs.get("response_format") or {}
    schema = ((fmt.get("json_schema") or {}).get("schema") or {})
    assert fmt.get("type") == "json_schema"
    assert (fmt.get("json_schema") or {}).get("name") == "spl_pattern_adaptation"
    assert schema.get("additionalProperties") is False
    assert set(schema.get("required") or []) == {"status", "candidate_spl"}
    assert schema.get("properties") == PATTERN_ADAPTATION_JSON_SCHEMA["properties"]


def test_complete_length_json_is_not_discarded(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P1)
    compiled = compile_intent_spec_to_spl(spec)
    ctx = _build_utility_llm_context(P1, family="unmapped_live_data_request", intent_spec=spec)
    payload = json.dumps({"status": "candidate_generated", "candidate_spl": compiled})
    client = _CaptureClient(text=payload, finish_reason="length")
    result = generate_llm_spl_fallback(
        user_query=P1,
        utility_authoring=True,
        client=client,
        context=ctx,
    )
    assert result is not None
    assert result.finish_reason == "length"
    assert result.authoring_failure_code != "finish_reason_length"
    assert compiled in (result.candidate_spl or "")


def test_truncated_length_json_still_fails_closed(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P1)
    ctx = _build_utility_llm_context(P1, family="unmapped_live_data_request", intent_spec=spec)
    client = _CaptureClient(
        text='{"status":"candidate_generated","candidate_spl":"search index=',
        finish_reason="length",
    )
    result = generate_llm_spl_fallback(
        user_query=P1,
        utility_authoring=True,
        client=client,
        context=ctx,
    )
    assert result is not None
    assert result.authoring_failure_code == "finish_reason_length"
    assert not (result.candidate_spl or "").strip()


def test_compact_prompt_asks_only_status_and_candidate_spl() -> None:
    spec = build_spl_intent_spec(P1)
    ctx = _build_utility_llm_context(P1, family="unmapped_live_data_request", intent_spec=spec)
    system, user = spl_advisory_prompts(P1, utility_authoring=True, context=ctx)
    closer = user.rsplit("Return only JSON", 1)[-1]
    assert "status and candidate_spl" in closer or '"candidate_spl"' in closer
    assert "soc_std_rules_applied" not in closer
    assert "catalog_approved" not in closer
    example_start = system.find("Example response:")
    assert example_start > 0
    example_json = system[example_start:].split("\n", 1)[0].replace("Example response:", "").strip()
    parsed = json.loads(example_json)
    assert set(parsed) == {"status", "candidate_spl"}
    assert "streamstats" in parsed["candidate_spl"]


P2 = (
    "Write a review-only SPL query to identify users with more than 20 failed "
    "authentication attempts within 15 minutes followed by a successful login "
    "from the same source IP within the next 10 minutes. Return user, source IP, "
    "destination host, failed-login count, first failure time, and "
    "successful-login time. Do not execute."
)


def test_sequence_pattern_is_generic_burst_then_follow() -> None:
    spec = build_spl_intent_spec(P2)
    pattern = select_vetted_authoring_pattern(spec)
    assert pattern is not None
    assert pattern["pattern_id"] == "sequence"
    assert pattern["pattern_enabled"] is True
    body = str(pattern["payload"]["candidate_spl"])
    assert "4624" not in body
    assert "4625" not in body
    assert "EventCode" not in body
    assert "streamstats last(" in body
    assert "_time>burst_last" in body.replace(" ", "")
    assert "time_window=" in body
    compiled = compile_intent_spec_to_spl(spec)
    fid = validate_semantic_fidelity(spec, compiled)
    assert fid.get("passed") is True, fid
    compact = compiled.replace(" ", "")
    assert "time_window=15m" in compiled
    assert "burst_count>20" in compact
    assert "_time>burst_last_epoch" in compact
    assert "rename burst_count as failure_count" in compiled
    assert not re.search(r"\|\s*streamstats[^|]*\bby\s+[^|]*\bhost", compiled, re.I)


def test_p2_sequence_mutants_a_through_j() -> None:
    spec = build_spl_intent_spec(P2)
    compiled = compile_intent_spec_to_spl(spec)

    and_retrieval = compiled.replace(
        compiled.split("|", 1)[0],
        "search index=<your_index> sourcetype=pgcil:auth earliest=-24h latest=now "
        "(action=failure OR EventCode=4625) (action=success OR EventCode=4624) ",
    )
    and_fid = validate_semantic_fidelity(spec, and_retrieval)
    assert "sequence_event_union_missing" in (and_fid.get("losses") or [])

    host_by = re.sub(
        r"(streamstats(?:(?!\n\|).)*by )([^\n|]+)",
        r"\1user_norm, src_ip_norm, host_norm",
        compiled,
        count=1,
        flags=re.I | re.S,
    )
    host_fid = validate_semantic_fidelity(spec, host_by)
    assert "sequence_host_overcorrelation" in (host_fid.get("losses") or [])
    assert any("source IP only" in str(item) for item in (host_fid.get("repair_feedback") or []))

    gte = compiled.replace("burst_count>20", "burst_count>=20").replace(
        "failure_count>20", "failure_count>=20"
    )
    gte_fid = validate_semantic_fidelity(spec, gte)
    assert "sequence_threshold_inclusive" in (gte_fid.get("losses") or [])

    before = compiled.replace("_time>burst_last_epoch", "_time<burst_last_epoch")
    before_fid = validate_semantic_fidelity(spec, before)
    assert "sequence_success_before_failure" in (before_fid.get("losses") or [])

    late = compiled.replace("<=600", "<=601")
    late_fid = validate_semantic_fidelity(spec, late)
    assert "sequence_gap_missing" in (late_fid.get("losses") or [])

    no_first = compiled.replace("first_failure", "start_time")
    no_first_fid = validate_semantic_fidelity(spec, no_first)
    assert any("first_failure" in str(item) for item in (no_first_fid.get("losses") or []))

    no_success = compiled.replace("success_time", "login_time")
    no_success_fid = validate_semantic_fidelity(spec, no_success)
    assert any("success_time" in str(item) for item in (no_success_fid.get("losses") or []))

    fail_only = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now "
        "(action=failure OR EventCode=4625) | stats count as failure_count by user_norm"
    )
    fail_fid = validate_semantic_fidelity(spec, fail_only)
    assert "required_event_type_missing" in (fail_fid.get("losses") or [])

    success_only = (
        "search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-24h latest=now "
        "(action=success OR EventCode=4624) | stats count by user_norm"
    )
    success_fid = validate_semantic_fidelity(spec, success_only)
    assert "required_event_type_missing" in (success_fid.get("losses") or [])

    no_burst = re.sub(
        r"\|\s*streamstats last\([^|]+",
        "| where event_type=\"successful_login\" AND failure_count>20",
        compiled,
        count=1,
        flags=re.I,
    )
    burst_fid = validate_semantic_fidelity(spec, no_burst)
    assert "sequence_burst_not_established_before_follow" in (burst_fid.get("losses") or [])


_P2_COLLAPSE_STATS = (
    '| stats count as sequence_matches max(burst_count) as failure_count '
    'min(burst_first_epoch) as first_failure_keep latest(_time) as success_time_epoch '
    'latest(host_norm) as host_norm earliest(_time) as first_match_epoch '
    'latest(_time) as last_match_epoch by user_norm, src_ip_norm'
)


def _p2_prefix_through_where(compiled: str) -> str:
    match = re.search(
        r'^(.*\|\s*where event_type="successful_login"[^|]*)',
        compiled,
        re.I | re.S,
    )
    assert match is not None
    return match.group(1)


def test_p2_two_sequences_same_user_ip_are_not_cross_mixed() -> None:
    spec = build_spl_intent_spec(P2)
    compiled = compile_intent_spec_to_spl(spec)
    compact = compiled.replace(" ", "")
    after_where = re.split(
        r'\|\s*where event_type="successful_login"',
        compiled,
        maxsplit=1,
        flags=re.I,
    )[1]
    assert re.search(r"\|\s*stats\b", after_where, re.I) is None
    assert "max(burst_count)" not in compact
    assert "latest(host_norm)" not in compact
    assert "rename burst_count as failure_count" in compiled
    assert "first_failure=strftime(burst_first_epoch" in compact
    assert "success_time=strftime(_time" in compact
    fid = validate_semantic_fidelity(spec, compiled)
    assert fid.get("passed") is True, fid
    mixed = {
        "user": "alice",
        "src_ip": "10.0.0.5",
        "failure_count": 25,
        "first_failure": "09:45",
        "success_time": "18:00",
        "destination_host": "HOST-B",
    }
    preserved = [
        {
            "user": "alice",
            "src_ip": "10.0.0.5",
            "failure_count": 25,
            "first_failure": "09:45",
            "success_time": "10:00",
            "destination_host": "HOST-A",
        },
        {
            "user": "alice",
            "src_ip": "10.0.0.5",
            "failure_count": 22,
            "first_failure": "17:40",
            "success_time": "18:00",
            "destination_host": "HOST-B",
        },
    ]
    assert mixed not in preserved


def test_p2_sequence_identity_collapsed_mutants() -> None:
    spec = build_spl_intent_spec(P2)
    compiled = compile_intent_spec_to_spl(spec)
    prefix = _p2_prefix_through_where(compiled)
    assert validate_semantic_fidelity(spec, compiled).get("passed") is True

    mutant1 = (
        prefix
        + " | stats max(burst_count) as failure_count min(burst_first_epoch) as first_failure "
        "latest(_time) as success_time by user_norm, src_ip_norm"
    )
    fid1 = validate_semantic_fidelity(spec, mutant1)
    assert "sequence_identity_collapsed" in (fid1.get("losses") or [])

    mutant2 = (
        prefix
        + " | stats max(burst_count) as failure_count latest(host_norm) as host_norm "
        "by user_norm, src_ip_norm"
    )
    fid2 = validate_semantic_fidelity(spec, mutant2)
    assert "sequence_identity_collapsed" in (fid2.get("losses") or [])

    mutant3 = prefix + " " + _P2_COLLAPSE_STATS + (
        ' | eval first_failure=strftime(first_failure_keep, "%Y-%m-%d %H:%M:%S"), '
        'success_time=strftime(success_time_epoch, "%Y-%m-%d %H:%M:%S")'
    )
    fid3 = validate_semantic_fidelity(spec, mutant3)
    assert "sequence_identity_collapsed" in (fid3.get("losses") or [])

    ok_by_success_time = (
        prefix
        + " | stats max(burst_count) as failure_count latest(host_norm) as host_norm "
        "by user_norm, src_ip_norm, _time"
    )
    ok_fid = validate_semantic_fidelity(spec, ok_by_success_time)
    assert "sequence_identity_collapsed" not in (ok_fid.get("losses") or [])


def test_p2_preprocessor_does_not_rewrite_sequence_semantics() -> None:
    spec = build_spl_intent_spec(P2)
    compiled = compile_intent_spec_to_spl(spec)
    out = normalize_review_only_spl(
        compiled,
        {
            "is_explicit_spl_authoring": True,
            "llm_generated": True,
            "semantic_analyst_intent": spec,
        },
    )
    by_clauses = re.findall(r"\|\s*streamstats[^|]*\bby\s+([^|]+)", out.normalized_spl, re.I)
    assert by_clauses
    for clause in by_clauses:
        assert "user" in clause.lower()
        assert "src_ip" in clause.lower()
        assert not re.search(r"\bhost(?:_norm)?\b", clause)
    assert "streamstats last(" in out.normalized_spl
    assert "_time>burst_last_epoch" in out.normalized_spl.replace(" ", "")
    assert "time_window=15m" in out.normalized_spl


def test_injected_faithful_p2_is_llm_pattern_not_compiler_rescue(spl_flags: None) -> None:
    spec = build_spl_intent_spec(P2)
    compiled = compile_intent_spec_to_spl(spec)
    candidate, validation = _run(P2, provider=lambda: _llm_payload(compiled))
    trace = candidate.get("utility_spl_draft_trace") or {}
    assert candidate.get("authoring_source") in {
        AUTHORING_SOURCE_LLM_PATTERN_PRIMARY,
        AUTHORING_SOURCE_LLM_PATTERN_NORMALIZED,
    }
    assert trace.get("legacy_compiler_rescue") is not True
    assert trace.get("llm_pattern_success") is True
    assert trace.get("pattern_id") == "sequence"
    assert validation.get("approved") is False
    assert validation.get("normalized_spl") in (None, "")
    assert candidate.get("execution_eligible") is False


def test_p2_renderer_describes_burst_then_success() -> None:
    spec = build_spl_intent_spec(P2)
    spl = compile_intent_spec_to_spl(spec)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "utility_spl_draft_trace": {
                "pattern_id": "sequence",
                "pattern_selected": True,
                "semantic_intent_spec": spec,
            },
        }
    )
    lowered = text.lower()
    assert "failure burst" in lowered
    assert "successful login" in lowered
    assert "Filters successful Windows logons (EventCode=4624)." not in text


P3 = (
    "Write a review-only SPL query to find powershell.exe launched by winword.exe "
    "or excel.exe during the last 24 hours. Group by host and user and return host, "
    "user, parent process, child process, command line, first seen, last seen, and "
    "event count. Do not execute the query."
)


def test_p3_parent_child_mutants_a_through_h() -> None:
    spec = build_spl_intent_spec(P3)
    compiled = compile_intent_spec_to_spl(spec)
    compiled_fid = validate_semantic_fidelity(spec, compiled)
    assert compiled_fid.get("passed") is True, compiled_fid
    compact = compiled.replace(" ", "").lower()
    assert "earliest=-24h" in compact
    assert "like(image" in compact
    assert "like(parentimage" in compact

    inverted = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        'Image="*winword.exe" ParentImage="*powershell.exe"\n'
        "| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen "
        "values(Image) as child_process values(ParentImage) as parent_process "
        "values(CommandLine) as command_line by host, user"
    )
    inv_fid = validate_semantic_fidelity(spec, inverted)
    assert "parent_child_inverted" in (inv_fid.get("losses") or [])

    cmd_only = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        'process_name="winword.exe" CommandLine="powershell.exe -enc aaa"\n'
        '| eval command_line=coalesce(CommandLine, "unknown")\n'
        "| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen "
        "values(command_line) as command_line by host, user"
    )
    cmd_fid = validate_semantic_fidelity(spec, cmd_only)
    assert "child_process_not_proven" in (cmd_fid.get("losses") or [])
    assert any("command-line" in str(item).lower() or "command_line" in str(item).lower() for item in (cmd_fid.get("repair_feedback") or []))

    no_parent = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        'Image="*powershell.exe"\n'
        "| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen "
        "values(Image) as child_process values(CommandLine) as command_line by host, user"
    )
    parent_fid = validate_semantic_fidelity(spec, no_parent)
    assert "parent_process_missing" in (parent_fid.get("losses") or [])

    unrelated = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        'Image="*powershell.exe"\n'
        '| join type=inner [ search index=<index> ParentImage="*winword.exe" ]\n'
        "| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen "
        "values(Image) as child_process values(ParentImage) as parent_process "
        "values(CommandLine) as command_line by host, user"
    )
    rel_fid = validate_semantic_fidelity(spec, unrelated)
    assert "parent_child_relationship_missing" in (rel_fid.get("losses") or [])

    dropped = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        '| eval child_process=coalesce(Image,"unknown"), '
        'parent_process=coalesce(ParentImage,"unknown"), '
        'command_line=coalesce(CommandLine,"unknown")\n'
        '| where like(Image, "%powershell.exe%") AND '
        '(like(ParentImage, "%winword.exe%") OR like(ParentImage, "%excel.exe%"))\n'
        "| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen "
        "by host, user\n"
        "| fields parent_process, child_process, command_line, host, user, event_count, "
        "first_seen, last_seen"
    )
    drop_fid = validate_semantic_fidelity(spec, dropped)
    assert "field_lineage_missing" in (drop_fid.get("losses") or [])

    no_count = compiled.replace("count as event_count", "max(_time) as last_event")
    count_fid = validate_semantic_fidelity(spec, no_count)
    assert "output_missing:event_count" in (count_fid.get("losses") or [])

    count_only = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        '| where like(Image, "%powershell.exe%") AND like(ParentImage, "%winword.exe%")\n'
        "| stats count as event_count values(parent_process) as parent_process "
        "values(child_process) as child_process values(command_line) as command_line "
        "by host, user"
    )
    seen_fid = validate_semantic_fidelity(spec, count_only)
    assert "output_missing:first_seen" in (seen_fid.get("losses") or [])
    assert "output_missing:last_seen" in (seen_fid.get("losses") or [])

    eval_in_search = (
        'search index=<index> sourcetype=<sourcetype> earliest=-24h latest=now '
        'like(Image, "%powershell.exe%") like(ParentImage, "%winword.exe%")\n'
        "| stats count as event_count earliest(_time) as first_seen latest(_time) as last_seen "
        "values(Image) as child_process values(ParentImage) as parent_process "
        "values(CommandLine) as command_line by host, user"
    )
    ctx_fid = validate_semantic_fidelity(spec, eval_in_search)
    assert "command_context_invalid" in (ctx_fid.get("losses") or [])


def test_p2_quality_fail_still_records_raw_llm_spl(spl_flags: None) -> None:
    bad = (
        "search index=wineventlog earliest=-24h latest=now "
        "(EventCode=4625 OR EventCode=4624)\n"
        '| eval user_norm=lower(coalesce(user, "unknown"))\n'
        "| sort 0 _time\n"
        "| streamstats time_window=15m count as c by user_norm\n"
        "| table user_norm"
    )
    candidate, validation = _run(P2, provider=lambda: _llm_payload(bad))
    trace = candidate.get("utility_spl_draft_trace") or {}
    raw = str(trace.get("raw_llm_spl") or "")
    assert "streamstats" in raw
    assert "sort 0 _time" in raw
    assert candidate.get("authoring_source") == AUTHORING_SOURCE_LEGACY_COMPILER_RESCUE
    assert validation.get("approved") is False
    assert candidate.get("execution_eligible") is False


P4 = (
    "Write a review-only SPL query to find destination domains contacted during "
    "the last 24 hours that were not previously seen for the same host during the "
    "preceding 14 days. Return host, source IP, destination domain, first-seen "
    "time, and connection count. Do not execute."
)


def test_p4_reuses_first_seen_pattern() -> None:
    p1 = build_spl_intent_spec(P1)
    p4 = build_spl_intent_spec(P4)
    assert p1["analysis_shape"] == "first_seen"
    assert p4["analysis_shape"] == "first_seen"
    p1_pat = select_vetted_authoring_pattern(p1)
    p4_pat = select_vetted_authoring_pattern(p4)
    assert p1_pat is not None and p4_pat is not None
    assert p1_pat["pattern_id"] == p4_pat["pattern_id"] == "first_seen"
    assert p1_pat is p4_pat
    assert p4["entity_roles"]["subject"][0] == "host"
    assert p4["entity_roles"]["target"][0] == "domain"
    assert p4.get("observation_window") == "24h"
    assert p4.get("baseline_window") == "14d"
    assert "earliest=-15d" in str(p4.get("search_horizon") or "")
    compiled = compile_intent_spec_to_spl(p4)
    fid = validate_semantic_fidelity(p4, compiled)
    assert fid.get("passed") is True, fid
    compact = compiled.replace(" ", "")
    assert "earliest=-15d" in compact
    assert 'relative_time(now(),"-24h")' in compact
    assert "streamstats values(baseline_object) as baseline_objects by host_norm" in compiled
    assert "by user" not in compiled.lower().split("streamstats")[1].split("|")[0]
    assert "as new_host" not in compiled.lower()
    assert "as domain" in compiled.lower()
    assert "count as connection_count" in compiled.lower()
    assert "mvmap(baseline_objects" in compiled
    assert "seen_before=0" in compiled.replace(" ", "")
    assert "mvfind" not in compiled.lower()
    assert re.search(r"mvfilter\s*\(\s*\w+\s*==", compiled) is None


def test_p4_first_seen_mutants_a_through_h() -> None:
    spec = build_spl_intent_spec(P4)
    compiled = compile_intent_spec_to_spl(spec)
    assert validate_semantic_fidelity(spec, compiled).get("passed") is True

    only_obs = compiled.replace("earliest=-15d", "earliest=-24h")
    a_fid = validate_semantic_fidelity(spec, only_obs)
    assert "baseline_unreachable" in (a_fid.get("losses") or [])
    assert "baseline_data_unreachable" in (a_fid.get("losses") or [])

    overlap = compiled.replace(
        'baseline_object=if(period="baseline", domain_norm, null())',
        'baseline_object=if(_time>=relative_time(now(), "-14d"), domain_norm, null())',
    )
    b_fid = validate_semantic_fidelity(spec, overlap)
    assert "observation_baseline_overlap" in (b_fid.get("losses") or [])

    by_user = compiled.replace(
        "streamstats values(baseline_object) as baseline_objects by host_norm",
        "streamstats values(baseline_object) as baseline_objects by user_norm",
    )
    c_fid = validate_semantic_fidelity(spec, by_user)
    assert "first_seen_subject_wrong" in (c_fid.get("losses") or [])

    as_host = compiled.replace("as domain", "as new_host")
    d_fid = validate_semantic_fidelity(spec, as_host)
    assert "output_entity_mismatch" in (d_fid.get("losses") or [])

    regex = compiled.replace(
        "mvmap(baseline_objects, if(baseline_objects==domain_norm,1,0))",
        "mvfind(baseline_objects, domain_norm)",
    )
    e_fid = validate_semantic_fidelity(spec, regex)
    assert "regex_membership" in (e_fid.get("losses") or [])
    assert "exact_membership_missing" in (e_fid.get("losses") or [])

    no_count = compiled.replace("count as connection_count ", "")
    f_fid = validate_semantic_fidelity(spec, no_count)
    assert "output_missing:connection_count" in (f_fid.get("losses") or [])

    no_first = compiled.replace("earliest(_time) as first_seen_epoch ", "").replace(
        '| eval first_seen=strftime(first_seen_epoch, "%Y-%m-%d %H:%M:%S") | fields - first_seen_epoch',
        "",
    )
    g_fid = validate_semantic_fidelity(spec, no_first)
    assert "output_missing:first_seen" in (g_fid.get("losses") or [])

    no_src = compiled.replace("values(src_ip_norm) as src_ip ", "")
    h_fid = validate_semantic_fidelity(spec, no_src)
    assert "output_missing:src_ip" in (h_fid.get("losses") or [])


def test_p4_renderer_keeps_host_domain_first_seen() -> None:
    spec = build_spl_intent_spec(P4)
    spl = compile_intent_spec_to_spl(spec)
    text = render_pattern_guided_review_answer(
        candidate_spl={
            "candidate_spl": spl,
            "utility_spl_draft_trace": {
                "pattern_id": "first_seen",
                "pattern_selected": True,
                "semantic_intent_spec": spec,
            },
        }
    )
    lowered = text.lower()
    assert text.startswith("Review-only SPL draft — not executed")
    assert "preceding 14d" in text or "preceding 14" in text
    assert "same host" in lowered
    assert "Filters successful Windows logons (EventCode=4624)." not in text
    assert "Investigation steps" not in text
    assert "MITRE" not in text
    assert "No query was executed." in text


_P1_COMPILER_SHA256_D04C00A5 = "f27b363dc854b64411104b34698cca82544e9f85b4f6bf1986b2adfbf4693ef8"
_P2_COMPILER_SHA256_6C1D6C4B = "97b84cdf8e4aaecfc4a49825f5913d79959d6da1ca7489b0f4ce1ffcad1b8e1c"
_P3_COMPILER_SHA256_D04C00A5 = "0bed5774228536dc771475418724980b643326f1a4468f133157b0d8df755f15"
_P4_COMPILER_SHA256_D04C00A5 = "a4d195beecd85bd8e57e90b4d6ce71b437c12426bb8e7bf7a3b3dd14ba635eb8"


def test_p1_p3_p4_compiler_spl_unchanged_from_d04c00a5() -> None:
    snapshots = (
        (P1, _P1_COMPILER_SHA256_D04C00A5, "mvmap(baseline_objects, if(baseline_objects==host_norm,1,0))"),
        (P3, _P3_COMPILER_SHA256_D04C00A5, "powershell.exe"),
        (P4, _P4_COMPILER_SHA256_D04C00A5, "mvmap(baseline_objects, if(baseline_objects==domain_norm,1,0))"),
    )
    for query, expected, needle in snapshots:
        spl = compile_intent_spec_to_spl(build_spl_intent_spec(query))
        assert needle in spl
        assert hashlib.sha256(spl.encode()).hexdigest() == expected


def test_p1_p2_p3_p4_compiler_spl_unchanged_from_6c1d6c4b() -> None:
    snapshots = (
        (P1, _P1_COMPILER_SHA256_D04C00A5, "mvmap(baseline_objects, if(baseline_objects==host_norm,1,0))"),
        (P2, _P2_COMPILER_SHA256_6C1D6C4B, "burst_count>20"),
        (P3, _P3_COMPILER_SHA256_D04C00A5, "powershell.exe"),
        (P4, _P4_COMPILER_SHA256_D04C00A5, "mvmap(baseline_objects, if(baseline_objects==domain_norm,1,0))"),
    )
    for query, expected, needle in snapshots:
        spl = compile_intent_spec_to_spl(build_spl_intent_spec(query))
        assert needle in spl
        assert hashlib.sha256(spl.encode()).hexdigest() == expected
