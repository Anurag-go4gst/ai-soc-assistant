from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.query_understanding.success_after_failure import detect_success_after_failure
from app.use_cases.models import UseCaseDefinition, UseCaseSelection

CATALOG_PATH = Path(__file__).with_name("catalog.json")


@lru_cache(maxsize=1)
def load_use_case_catalog() -> list[UseCaseDefinition]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [UseCaseDefinition(**item) for item in payload.get("use_cases", [])]


def get_use_case(use_case_id: str) -> UseCaseDefinition | None:
    return next((item for item in load_use_case_catalog() if item.use_case_id == use_case_id), None)


# --- Bind diagnostics (plan 2026-08-19_1130 item 1) -------------------------
# Measurement only. Nothing here feeds selection; `confidence` still decides.
# Recorded so the coverage/margin distribution can be observed on real traffic
# before item 3 chooses a threshold from data instead of intuition.
import math as _math
from collections import Counter as _Counter


def _catalogue_document_frequency() -> _Counter:
    df: _Counter = _Counter()
    for use_case in load_use_case_catalog():
        words = {w for pattern in _expanded_match_terms(use_case) for w in pattern.lower().split()}
        for word in words:
            df[word] += 1
    return df


def _term_specificity(word: str, df: _Counter, catalogue_size: int) -> float:
    return _math.log(1 + catalogue_size / (1 + df.get(word, 0)))


def _bind_diagnostics(normalized_query: str, matched: list[str], df: _Counter, catalogue_size: int) -> dict:
    query_words = max(len(normalized_query.split()), 1)
    matched_words = sum(len(pattern.split()) for pattern in matched)
    coverage = matched_words / query_words
    specificity = (
        sum(_term_specificity(w, df, catalogue_size) for p in matched for w in p.lower().split())
        / max(matched_words, 1)
    )
    return {
        "coverage_ratio": round(coverage, 4),
        "specificity": round(specificity, 4),
        "coverage_score": round(coverage * specificity, 4),
    }


def match_use_cases(query: str, *, limit: int = 3) -> list[UseCaseSelection]:
    from app.chat.query_signals import term_is_negated

    normalized = " ".join(query.lower().split())
    _df = _catalogue_document_frequency()
    _catalogue_size = len(load_use_case_catalog())
    matches: list[UseCaseSelection] = []
    for use_case in load_use_case_catalog():
        # Containment alone reads "we have no SOAR playbook yet" as a request for
        # a playbook. A term the user says they LACK is context for the ask, not
        # the ask — drop those before scoring, or one negated word out of forty
        # binds a use case at 0.91 and closes spl_allowed/mcp_allowed.
        matched = [
            pattern
            for pattern in _expanded_match_terms(use_case)
            if pattern.lower() in normalized and not term_is_negated(normalized, pattern.lower())
        ]
        # "advisory" alone is not evidence of a CERT-In hash/IOC match.  It
        # falsely captured generic threat-intelligence advisories and bypassed
        # the T2 answer-shape path with an unrelated compliance use case.
        if use_case.use_case_id == "cert_in_hash_match" and not any(
            token in normalized for token in ("cert-in", "cert in", "hash", "ioc", "indicator")
        ):
            matched = []
        if not matched:
            continue
        confidence = min(
            0.95,
            0.62
            + (0.05 * len(matched))
            + _canonical_term_boost(matched, use_case.intent_patterns)
            + _intent_boost(normalized, use_case.use_case_id),
        )
        diagnostics = _bind_diagnostics(normalized, matched, _df, _catalogue_size)
        matches.append(
            UseCaseSelection(
                use_case_id=use_case.use_case_id,
                display_name=use_case.display_name,
                category=use_case.category,
                primary_skill=use_case.primary_skill,
                confidence=confidence,
                matched_patterns=matched,
                default_spl_template=use_case.default_spl_template,
                output_template=use_case.output_template,
                required_sources=use_case.required_sources,
                optional_sources=use_case.optional_sources,
                action_capability_tier=use_case.action_capability_tier,
                **diagnostics,
            )
        )
    _demote_weak_modifier_overrides(matches)
    ordered = sorted(matches, key=lambda item: item.confidence, reverse=True)
    # Runner-up margin is measured on the coverage score, not on `confidence`:
    # confidence saturates at 0.95 and cannot express "these two are close".
    if ordered:
        # Attach to the bind that is actually made (ordered[0] — confidence still
        # decides), not to whichever candidate happens to lead on coverage. The
        # question this must answer is "how thin and how contested is the bind we
        # committed", so the runner-up is the best OTHER candidate by coverage.
        selected = ordered[0]
        others = [item for item in ordered[1:] if item.coverage_score is not None]
        runner_up = max((item.coverage_score for item in others), default=None)
        selected.runner_up_score = runner_up
        selected.bind_margin = (
            round((selected.coverage_score or 0.0) - runner_up, 4)
            if runner_up is not None
            else None
        )
    return ordered[:limit]


# Confidence floor a weak SPL-meta modifier (e.g. soc_generate_spl) is pushed
# below when it co-occurs with a real detection-family row.  The meta row must
# never out-rank the detection family it is merely asking to query.
_WEAK_MODIFIER_DEMOTION = 0.40


def _demote_weak_modifier_overrides(matches: list[UseCaseSelection]) -> None:
    """Honour ``must_not_override_detection_family``.

    When a ``weak_modifier`` SPL-meta row matched a real detection-family row
    *only incidentally* — i.e. via a non-canonical term (display name/example),
    not one of its own intent patterns — demote it so the detection family wins.
    An explicit canonical request ("generate spl for …") keeps the meta row, so
    "Generate SPL for failed logins" still routes to soc_generate_spl.
    """
    matched_ids = {selection.use_case_id for selection in matches}
    definitions = {item.use_case_id: item for item in load_use_case_catalog() if item.use_case_id in matched_ids}
    has_detection_family = any(
        definitions[selection.use_case_id].use_case_type != "meta_output_artifact"
        for selection in matches
        if selection.use_case_id in definitions
    )
    if not has_detection_family:
        return
    for selection in matches:
        definition = definitions.get(selection.use_case_id)
        if definition is None:
            continue
        if not (definition.must_not_override_detection_family and definition.pattern_strength == "weak_modifier"):
            continue
        canonical = {" ".join(p.lower().split()) for p in definition.intent_patterns}
        matched_canonical = {" ".join(p.lower().split()) for p in selection.matched_patterns}
        if canonical & matched_canonical:
            # Explicit SPL-generation request — the meta row is the right route.
            continue
        selection.confidence = max(0.0, selection.confidence - _WEAK_MODIFIER_DEMOTION)


def _expanded_match_terms(use_case: UseCaseDefinition) -> list[str]:
    terms = [
        *use_case.intent_patterns,
        use_case.display_name,
        *use_case.example_queries,
    ]
    normalized_terms: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = " ".join(term.lower().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_terms.append(term)
    return normalized_terms


def _canonical_term_boost(matched: list[str], intent_patterns: list[str]) -> float:
    canonical = {" ".join(item.lower().split()) for item in intent_patterns}
    matched_canonical = {" ".join(item.lower().split()) for item in matched}
    return 0.06 if canonical & matched_canonical else 0.0


def _intent_boost(normalized_query: str, use_case_id: str) -> float:
    if use_case_id == "aws_security_group_modifications" and all(
        term in normalized_query for term in ("aws", "security group")
    ):
        return 0.24
    if use_case_id == "aws_console_success_logins_by_user" and all(
        term in normalized_query for term in ("aws", "console")
    ):
        return 0.28
    if use_case_id == "aws_iam_policy_modifications" and all(
        term in normalized_query for term in ("aws", "iam")
    ):
        return 0.28
    if use_case_id == "auth_failed_login_top_users_exclude_service_accounts" and (
        "exclude service account" in normalized_query or "excluding service account" in normalized_query
    ):
        return 0.30
    if use_case_id == "soc_show_sop" and any(term in normalized_query for term in ("sop", "playbook", "runbook")):
        return 0.18
    if use_case_id == "soc_generate_spl" and "spl" in normalized_query:
        return 0.18
    if use_case_id == "soc_map_alert_mitre" and any(term in normalized_query for term in ("mitre", "att&ck")):
        return 0.18
    if use_case_id == "edr_powershell_suspicious_command" and "powershell" in normalized_query:
        return 0.34
    if use_case_id == "dns_beaconing_candidate" and (
        "dns beaconing" in normalized_query or "beaconing candidate" in normalized_query
    ):
        return 0.34
    if use_case_id == "auth_success_after_failure" and detect_success_after_failure(normalized_query):
        return 0.40
    if use_case_id == "auth_failed_login_spike" and detect_success_after_failure(normalized_query):
        return -0.20
    return 0.0
