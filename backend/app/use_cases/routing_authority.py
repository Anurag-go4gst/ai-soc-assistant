"""Row-level routing authority for the T0/T1 SPL architecture.

A deterministic exact-105 match, an unsafe/HIL policy, and catalogue rows that
declare ``t0_exact_authority=true`` are frozen T0 — the intent LLM is skipped.
Everything else (near/semantic-105, out-of-registry, and SPL-meta catalogue rows
such as ``soc_generate_spl``/``soc_optimize_spl``) is eligible for an advisory
LLM hop, normalized back through the deterministic registries.

This module imports only the use-case registry so it can be shared by both the
query parser and the sidecar skip policy without an import cycle.
"""
from __future__ import annotations

from typing import Any

# Paths the parser may report.  Centralised so callers do not re-spell them.
_LLM_PATHS = frozenset({"near_105_question", "semantic_105_question", "out_of_registry"})
_EXACT_PATH = "exact_105_question"
_CATALOG_PATH = "use_case_catalog"
_EXACT_PLUS_CATALOG_PATH = "exact_105_plus_use_case_catalog"


def catalog_authority_row(use_case_id: str | None) -> dict[str, Any] | None:
    """Return the row-level authority metadata for ``use_case_id`` (or None)."""
    if not use_case_id:
        return None
    # Local import keeps this module free of a parser import cycle.
    from app.use_cases.registry import get_use_case

    row = get_use_case(str(use_case_id))
    if row is None:
        return None
    return {
        "use_case_id": row.use_case_id,
        "registry_tier": row.registry_tier,
        "use_case_type": row.use_case_type,
        "t0_exact_authority": row.t0_exact_authority,
        # Whether t0_exact_authority was set in the catalogue (vs defaulted).
        # T0 authority for a catalogue row requires an explicit opt-in.
        "t0_exact_authority_explicit": "t0_exact_authority" in row.model_fields_set,
        "llm_advisory_recommended": row.llm_advisory_recommended,
        "requires_t2_shape_check": row.requires_t2_shape_check,
        "pattern_strength": row.pattern_strength,
        "must_not_override_detection_family": row.must_not_override_detection_family,
        "execution_eligible_default": row.execution_eligible_default,
        "human_review_required": row.human_review_required,
    }


def llm_advisory_recommended(
    match_path: str | None,
    *,
    catalog_row: dict[str, Any] | None = None,
    registry_warnings: list[str] | None = None,
) -> bool:
    """Decide whether the intent LLM advisor should run for this turn.

    Mirrors the architecture decision: exact-105 stays deterministic T0; catalogue
    rows decide via their declared authority; near/semantic/out-of-registry paths
    always invite an advisory hop.
    """
    path = str(match_path or "").strip()

    # A registry/use-case skill conflict always invites the advisor, regardless
    # of path — the deterministic registries disagree and need adjudication.
    if registry_warnings:
        return True

    if path in _LLM_PATHS:
        return True
    if path == _EXACT_PATH:
        return False
    if path == _CATALOG_PATH:
        return _catalog_row_recommends(catalog_row)
    if path == _EXACT_PLUS_CATALOG_PATH:
        # An exact-105 match is present, but a catalogue row that explicitly
        # disowns T0 authority (e.g. an SPL-meta row) still warrants the advisor.
        if catalog_row is not None and catalog_row.get("t0_exact_authority") is False:
            return True
        return False

    return bool(registry_warnings)


def _catalog_row_recommends(catalog_row: dict[str, Any] | None) -> bool:
    # ROUTE notion (drives _deterministic_uncertain / LLM route override).  This
    # stays conservative: a plain catalogue match is treated as confident so the
    # LLM cannot override a correct deterministic route.  Only rows that
    # explicitly opt in (advisory rows / T1 SPL-meta rows) invite route assist.
    if catalog_row is None:
        return False
    if catalog_row.get("llm_advisory_recommended") is True:
        return True
    if catalog_row.get("t0_exact_authority") is False:
        return True
    return False


def sidecar_intent_is_t0(
    match_path: str | None,
    *,
    catalog_row: dict[str, Any] | None = None,
    registry_warnings: list[str] | None = None,
) -> bool:
    """T0 for the *intent-advisor sidecar skip* (distinct from the route notion).

    Per the architecture decision, the intent advisor is skipped (T0) only for:
      * exact-105 matches,
      * exact-105 + catalogue (unless the co-matched row is an explicit advisory
        / T1 SPL-meta row), and
      * catalogue rows that explicitly set ``t0_exact_authority=true``.

    A plain catalogue match is NOT T0 — the advisor runs (advisory, non-authoritative).
    Unsafe/HIL and sufficiency skips are handled separately by the skip policy.
    """
    path = str(match_path or "").strip()
    if registry_warnings:
        return False
    if path == _EXACT_PATH:
        return True
    if path == _EXACT_PLUS_CATALOG_PATH:
        if catalog_row is not None and (
            catalog_row.get("llm_advisory_recommended") is True
            or catalog_row.get("t0_exact_authority") is False
        ):
            return False
        return True
    if path == _CATALOG_PATH:
        return bool(
            catalog_row
            and catalog_row.get("t0_exact_authority_explicit")
            and catalog_row.get("t0_exact_authority") is True
        )
    return False
