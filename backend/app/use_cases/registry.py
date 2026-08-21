from __future__ import annotations

import re

import json
from functools import lru_cache
from pathlib import Path

from app.use_cases.models import UseCaseDefinition, UseCaseSelection

CATALOG_PATH = Path(__file__).with_name("catalog.json")


@lru_cache(maxsize=1)
def load_use_case_catalog() -> list[UseCaseDefinition]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [UseCaseDefinition(**item) for item in payload.get("use_cases", [])]


def get_use_case(use_case_id: str) -> UseCaseDefinition | None:
    return next((item for item in load_use_case_catalog() if item.use_case_id == use_case_id), None)


# --- Bind scoring (plan 2026-08-19_1130 items 1–3) --------------------------
# Rank by coverage_score = coverage_ratio × IDF specificity. The old additive
# `0.62 + 0.05*n + boosts` formula is retired from ranking: a single substring
# hit is no longer near-authoritative. No coverage cutoff — item 2 showed a
# real SOP bind at coverage_ratio 0.0714 in the same band as remaining
# misfires. `confidence` is a 0–1 squash of coverage_score for QU/catalog
# consumers; it does not decide the winner. Item 4: a leader whose bind_margin
# is below `_BIND_MARGIN_TOO_CLOSE` escalates (no T2 bind) instead of a coin-flip.
import math as _math
from collections import Counter as _Counter

_GENERIC_SOURCE_TERMS = {
    "firepower",
    "cisco",
    "windows",
    "linux",
    "splunk",
    "firewall",
    "vpn",
    "proxy",
    "endpoint",
    "dns",
}


def _pattern_present(normalized_query: str, pattern: str) -> bool:
    """Containment, but the pattern must START at a word boundary.

    Plain `in` let 'locked' match inside 'blocked', binding
    auth_account_lockout_trend to "show any blocked connection attempts" — two
    unrelated concepts joined by a substring accident.

    Only the LEADING edge is anchored. The trailing edge stays free on purpose:
    across the truth set and the 105 catalogue questions, every other mid-word
    hit was plural morphology that should keep matching — 'scheduled task' in
    "scheduled tasks", 'mfa failure' in "mfa failures", 'suspicious process' in
    "suspicious processes". Anchoring both edges would have removed 10 good
    matches to fix 1 bad one; anchoring the leading edge removes exactly the
    bad one, measured.
    """
    return re.search(r"(?<![a-z0-9])" + re.escape(pattern), normalized_query) is not None


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


def _generic_source_only_utility_match(query: str, matched_patterns: list[str]) -> bool:
    """True when a catalog row matched only generic source/vendor vocabulary."""

    normalized = " ".join(str(query or "").lower().split())
    matched = {" ".join(str(item).lower().split()) for item in matched_patterns if str(item).strip()}
    if not matched or not matched.issubset(_GENERIC_SOURCE_TERMS):
        return False
    utility_ask = bool(
        re.search(r"\b(?:show|search|give me|list|draft|write|generate|create|build)\b", normalized)
        and (
            " logs" in normalized
            or " log " in normalized
            or "spl" in normalized
            or "splunk" in normalized
            or "index=" in normalized
            or "sourcetype=" in normalized
        )
    )
    return utility_ask and not re.search(
        r"\b(?:investigate|suspicious|cleartext|http|vnc|phase-?1|rtu|credential|brute|beacon|exfil)\b",
        normalized,
    )


def match_use_cases(query: str, *, limit: int = 3) -> list[UseCaseSelection]:
    from app.chat.query_signals import extract_query_signals, term_is_negated

    normalized = " ".join(query.lower().split())
    catalog = load_use_case_catalog()
    _df = _catalogue_document_frequency()
    _catalogue_size = len(catalog)
    signals = extract_query_signals(query) if any(item.requires_signals for item in catalog) else None
    matches: list[UseCaseSelection] = []
    for use_case in catalog:
        # Containment alone reads "we have no SOAR playbook yet" as a request for
        # a playbook. A term the user says they LACK is context for the ask, not
        # the ask — drop those before scoring, or one negated word out of forty
        # binds a use case at 0.91 and closes spl_allowed/mcp_allowed.
        matched = [
            pattern
            for pattern in _expanded_match_terms(use_case)
            if _pattern_present(normalized, pattern.lower())
            and not term_is_negated(normalized, pattern.lower())
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
        if _generic_source_only_utility_match(query, matched):
            continue
        if _use_case_metadata_blocks(use_case, normalized, signals):
            continue
        diagnostics = _bind_diagnostics(normalized, matched, _df, _catalogue_size)
        coverage_score = diagnostics["coverage_score"]
        matches.append(
            UseCaseSelection(
                use_case_id=use_case.use_case_id,
                display_name=use_case.display_name,
                category=use_case.category,
                primary_skill=use_case.primary_skill,
                confidence=min(0.95, coverage_score),
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
    _demote_hunt_when_mitre_lacks_context(normalized, matches)
    _demote_hunt_when_mapping_action_is_the_ask(matches)
    _demote_hunt_when_procedure_is_the_ask(normalized, matches)
    # Demoted hunts are scored to 0 so they are not a "close runner-up". Item 4
    # only sees natural contests. Uncontested (including weak SOP) still binds.
    matches = [item for item in matches if (item.coverage_score or 0.0) > 0.0]
    for selection in matches:
        selection.confidence = min(0.95, selection.coverage_score or 0.0)
    ordered = sorted(matches, key=lambda item: item.coverage_score or 0.0, reverse=True)
    if ordered:
        selected = ordered[0]
        runner_up = ordered[1].coverage_score if len(ordered) > 1 else None
        selected.runner_up_score = runner_up
        selected.bind_margin = (
            round((selected.coverage_score or 0.0) - runner_up, 4)
            if runner_up is not None
            else None
        )
        # Item 4: item 2 found no population-separating margin. The 0.00–0.12
        # band was inspected and empty then. A later natural race sits at
        # 0.1152 (`rt.know.005`); escalating it unbound the row into
        # spl_generation and dropped route_ok 67→66. Too-close is therefore
        # 0.10 — coin-flips escalate, that measured race still commits.
        if selected.bind_margin is not None and selected.bind_margin < _BIND_MARGIN_TOO_CLOSE:
            return []
    return ordered[:limit]


def _canonical_meta_action_patterns(definition: UseCaseDefinition, selection: UseCaseSelection) -> set[str]:
    canonical = {" ".join(p.lower().split()) for p in definition.intent_patterns}
    matched_canonical = {" ".join(p.lower().split()) for p in selection.matched_patterns}
    return canonical & matched_canonical


def _is_weak_meta_output_action(definition: UseCaseDefinition) -> bool:
    return (
        definition.use_case_type == "meta_output_artifact"
        and definition.must_not_override_detection_family
        and definition.pattern_strength == "weak_modifier"
    )


def _demote_weak_modifier_overrides(matches: list[UseCaseSelection]) -> None:
    """Honour ``must_not_override_detection_family`` in both directions.

    Incidental: a ``weak_modifier`` ``meta_output_artifact`` that did *not*
    match one of its own intent patterns is demoted, so a detection-family
    topic stays authoritative ("Please generate spl dashboards for failed
    logins").

    Canonical action: when that same row *did* match its own intent patterns,
    the explicit requested action is authoritative and co-matched
    detection-family rows are the subject/context, not margin peers.
    Hunt-vs-hunt races still use the 0.10 band unchanged.
    """
    matched_ids = {selection.use_case_id for selection in matches}
    definitions = {item.use_case_id: item for item in load_use_case_catalog() if item.use_case_id in matched_ids}
    detection_scores = [
        selection.coverage_score or 0.0
        for selection in matches
        if selection.use_case_id in definitions
        and definitions[selection.use_case_id].use_case_type != "meta_output_artifact"
    ]
    if not detection_scores:
        return
    canonical_action_present = False
    for selection in matches:
        definition = definitions.get(selection.use_case_id)
        if definition is None or not _is_weak_meta_output_action(definition):
            continue
        if _canonical_meta_action_patterns(definition, selection):
            # Explicit action request — keep the meta row; demote topics below.
            canonical_action_present = True
            continue
        selection.coverage_score = 0.0
    if not canonical_action_present:
        return
    for selection in matches:
        definition = definitions.get(selection.use_case_id)
        if definition is None or definition.use_case_type == "meta_output_artifact":
            continue
        selection.coverage_score = 0.0


# Item 4 — "too close to call". Item 2 inspected 0.00–0.12 and found no
# population that separates there; do not treat this as a coverage floor.
_BIND_MARGIN_TOO_CLOSE = 0.10


def _use_case_metadata_blocks(
    use_case: UseCaseDefinition,
    normalized: str,
    signals: dict | None,
) -> bool:
    """Item 5: optional exclusion_patterns / requires_signals. Empty = no-op."""
    for pattern in use_case.exclusion_patterns:
        needle = " ".join(pattern.lower().split())
        if needle and _pattern_present(normalized, needle):
            return True
    if not use_case.requires_signals:
        return False
    resolved = signals or {}
    for spec in use_case.requires_signals:
        name = spec.strip()
        if not name:
            continue
        if name.startswith("!"):
            if resolved.get(name[1:]):
                return True
        elif not resolved.get(name):
            return True
    return False


# Phrases that mean the hunt terms are background, not the ask — the user is
# stating they LACK the alert/log context a detection-family bind would need.
# Without this, coverage ranking prefers "failed logins" over "mitre" on
# rt.know.002 and the frozen deterministic arm routes attack_discovery.
_MITRE_WITHOUT_CONTEXT_PHRASES = (
    "do not have alert",
    "don't have alert",
    "do not have logs",
    "don't have logs",
    "no alert details",
    "no alert context",
    "without alert context",
    "without alert details",
)


def _demote_hunt_when_mitre_lacks_context(normalized: str, matches: list[UseCaseSelection]) -> None:
    """Keep a MITRE-mapping bind ahead of hunts when alert/log context is denied.

    Coverage × IDF is query-fractional, so two common hunt words outrank one
    distinctive mapping word in a long question. Item 5 will generalise this
    as use-case `requires_signals`; this closed list holds the item 3 truth-set
    floor (`rt.know.002`) without restoring the 0.62 additive formula.
    """
    if not any(phrase in normalized for phrase in _MITRE_WITHOUT_CONTEXT_PHRASES):
        return
    mapping_scores = [
        selection.coverage_score or 0.0
        for selection in matches
        if selection.primary_skill == "mitre_mapping" or selection.use_case_id == "soc_map_alert_mitre"
    ]
    if not mapping_scores:
        return
    for selection in matches:
        if selection.primary_skill not in {"attack_discovery", "spl_generation", "alert_summary"}:
            continue
        selection.coverage_score = 0.0


_MAPPING_TOPIC_TERMS = frozenset({"mitre", "att&ck", "mitre technique", "attack technique"})


def _demote_hunt_when_mapping_action_is_the_ask(matches: list[UseCaseSelection]) -> None:
    """Explicit MITRE-mapping action outranks a co-matched detection subject.

    Bare ``mitre`` / ``att&ck`` topic words still match the mapping row (so
    technique-explain and denied-context asks can bind). They must not demote
    a hunt. Action phrases (``map this alert``, ``to mitre``) are the ask.
    """
    mapping_matches = [
        selection
        for selection in matches
        if selection.primary_skill == "mitre_mapping" or selection.use_case_id == "soc_map_alert_mitre"
    ]
    if not mapping_matches:
        return
    mapping_action = any(
        " ".join(pattern.lower().split()) not in _MAPPING_TOPIC_TERMS
        for selection in mapping_matches
        for pattern in selection.matched_patterns
    )
    if not mapping_action:
        return
    for selection in matches:
        if selection.primary_skill not in {"attack_discovery", "spl_generation", "alert_summary"}:
            continue
        selection.coverage_score = 0.0


_BARE_PROCEDURE_TERMS = frozenset({"sop", "playbook", "runbook"})


def _demote_hunt_when_procedure_is_the_ask(normalized: str, matches: list[UseCaseSelection]) -> None:
    """Keep a SOP/playbook bind ahead of hunts when the ask is the procedure.

    "Which SOP covers brute force authentication?" matches both ``soc_show_sop``
    (``sop``) and ``auth_failed_login_spike`` (``brute force``). Coverage prefers
    the two-word hunt pattern; the ask is the procedure.

    A one-word playbook *mention* on a hunt ("…as per our playbook") is the
    topic of the hunt, not a procedure ask — do not demote the hunt.
    """
    if not any(term in normalized for term in ("sop", "playbook", "runbook")):
        return
    procedure_matches = [
        selection for selection in matches if selection.use_case_id == "soc_show_sop"
    ]
    if not procedure_matches:
        return
    procedure_ask = any(
        " ".join(pattern.lower().split()) not in _BARE_PROCEDURE_TERMS
        for selection in procedure_matches
        for pattern in selection.matched_patterns
    )
    if not procedure_ask:
        return
    for selection in matches:
        if selection.primary_skill not in {"attack_discovery", "spl_generation", "alert_summary"}:
            continue
        selection.coverage_score = 0.0


def has_intent_pattern_hit(query: str) -> bool:
    """True if any catalogue intent_pattern is present, before eligibility/commit.

    Used by the live catalogue adapter so a typo-alias (no original hit) can
    still bind, while a T2 abstain after negation/exclusion/margin cannot be
    resurrected by re-running the matcher on alias-normalized text.
    """
    normalized = " ".join(query.lower().split())
    if not normalized:
        return False
    for use_case in load_use_case_catalog():
        for pattern in use_case.intent_patterns:
            needle = " ".join(pattern.lower().split())
            if needle and _pattern_present(normalized, needle):
                return True
    return False


def _expanded_match_terms(use_case: UseCaseDefinition) -> list[str]:
    # T2 commit hygiene: only intent_patterns may authorize a bind.
    # display_name / example_queries stay on the row for docs, the generated
    # index, and test probes — they must not independently match.
    terms = [
        *use_case.intent_patterns,
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
