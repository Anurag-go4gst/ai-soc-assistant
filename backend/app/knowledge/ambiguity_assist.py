from __future__ import annotations

from typing import Any, Protocol

from app.config import settings
from app.connectors.llm.registry import load_llm_registry_status


class AmbiguityAssistModel(Protocol):
    """Minimal model surface for candidate-constrained ambiguity assist.

    Implementations receive only already-eligible retrieved candidates and must
    return a structured selection. They cannot fetch, invent, or access drafts.
    """

    def assess(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class MockAmbiguityAssistModel:
    """Deterministic stand-in until a real provider connector is wired.

    Picks the single highest-confidence candidate; if the top two are within a
    tight margin it defers to human review instead of guessing.
    """

    def assess(self, payload: dict[str, Any]) -> dict[str, Any]:
        candidates = payload.get("candidates") or []
        if not candidates:
            return {"selected_entry_ids": [], "ambiguity_reason": "no_candidates", "needs_human_review": True, "confidence": 0.0}
        ranked = sorted(candidates, key=lambda item: -float(item.get("confidence") or 0.0))
        top = ranked[0]
        margin = float(top.get("confidence") or 0.0) - float(ranked[1].get("confidence") or 0.0) if len(ranked) > 1 else 1.0
        if margin < 0.05:
            return {
                "selected_entry_ids": [],
                "ambiguity_reason": "top_candidates_too_close",
                "needs_human_review": True,
                "confidence": round(float(top.get("confidence") or 0.0), 3),
            }
        return {
            "selected_entry_ids": [top.get("entry_id")],
            "ambiguity_reason": "single_clear_top_candidate",
            "needs_human_review": False,
            "confidence": round(float(top.get("confidence") or 0.0), 3),
        }


def _resolve_assist_provider() -> tuple[str | None, bool]:
    """Return (provider_name, available) resolved through the LLM registry."""
    provider = settings.soc_kb_llm_ambiguity_provider.strip()
    if not provider:
        return None, False
    registry = load_llm_registry_status()
    status = next((item for item in registry.providers if item.name == provider), None)
    return provider, bool(status and status.available)


def assist_status() -> dict[str, Any]:
    provider, available = _resolve_assist_provider()
    return {
        "enabled": settings.soc_kb_llm_ambiguity_assist_enabled,
        "provider": provider,
        "configured": bool(provider),
        "available": available,
        "max_candidates": settings.soc_kb_llm_ambiguity_max_candidates,
    }


def get_assist_model() -> AmbiguityAssistModel:
    # Real providers route through the LLM registry; the mock model is the safe
    # default until a registered provider is wired to this surface.
    return MockAmbiguityAssistModel()


def run_ambiguity_assist(
    *,
    query: str,
    eligible_candidates: list[dict[str, Any]],
    retrieval_status: str,
    model: AmbiguityAssistModel | None = None,
) -> dict[str, Any] | None:
    """Run candidate-constrained ambiguity assist.

    Returns ``None`` when disabled or when retrieval is not ambiguous. The model
    only ever sees already-eligible candidates and can only select among their
    ids; unknown ids are dropped and surfaced as warnings.
    """
    if not settings.soc_kb_llm_ambiguity_assist_enabled:
        return None
    if retrieval_status != "ambiguous":
        return None

    warnings: list[str] = []
    provider, available = _resolve_assist_provider()
    if not provider or not available:
        warnings.append("ambiguity_assist_provider_unavailable")
        return {
            "ran": False,
            "provider": provider,
            "selected_entry_ids": [],
            "ambiguity_reason": "provider_unavailable",
            "needs_human_review": True,
            "confidence": 0.0,
            "warnings": warnings,
        }

    max_candidates = max(1, settings.soc_kb_llm_ambiguity_max_candidates)
    bounded = eligible_candidates[:max_candidates]
    eligible_ids = {item.get("entry_id") for item in bounded}
    payload = {
        "query": query[:300],
        "candidates": [
            {
                "entry_id": item.get("entry_id"),
                "entry_title": item.get("entry_title"),
                "source_excerpt": item.get("source_excerpt"),
                "confidence": item.get("confidence"),
            }
            for item in bounded
        ],
    }

    try:
        raw = (model or get_assist_model()).assess(payload)
    except Exception as exc:  # noqa: BLE001 - assist failure must not break retrieval.
        warnings.append(f"ambiguity_assist_failed:{type(exc).__name__}")
        return {
            "ran": False,
            "provider": provider,
            "selected_entry_ids": [],
            "ambiguity_reason": "assist_failed",
            "needs_human_review": True,
            "confidence": 0.0,
            "warnings": warnings,
        }

    selected: list[str] = []
    for entry_id in raw.get("selected_entry_ids") or []:
        if entry_id in eligible_ids:
            selected.append(entry_id)
        else:
            warnings.append("ambiguity_assist_ignored_unknown_entry_id")

    needs_human_review = bool(raw.get("needs_human_review")) or not selected
    return {
        "ran": True,
        "provider": provider,
        "selected_entry_ids": selected,
        "ambiguity_reason": str(raw.get("ambiguity_reason") or "unspecified"),
        "needs_human_review": needs_human_review,
        "confidence": round(float(raw.get("confidence") or 0.0), 3),
        "warnings": warnings,
    }
