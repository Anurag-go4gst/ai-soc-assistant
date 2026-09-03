"""Canonical artifact ownership and path-based references for debug traces.

Heavy objects live once in the forensic bundle. Reviewer exports and timeline
events point at them with resolvable refs of the form ``artifact:<name>`` or
``timeline:llm_call:<interaction_id>``.
"""

from __future__ import annotations

from typing import Any

ARTIFACT_REF_PREFIX = "artifact:"
LLM_CALL_REF_PREFIX = "timeline:llm_call:"
FULL_BUNDLE_REF = "artifact:full_debug_bundle"

# Path from the forensic bundle root to the canonical owner. ``.`` is the bundle
# itself. Nested paths walk dict keys.
CANONICAL_ARTIFACT_PATHS: dict[str, str] = {
    "full_debug_bundle": ".",
    "effective_state": "explainability.effective_state",
    "final_answer": "explainability.final_output",
    "debug_summary": "explainability.debug_summary",
    "control_plane_trace": "explainability.control_plane_trace",
    "llm_interactions": "explainability.llm_interactions",
    "evidence_plan": "explainability.control_plane_trace.evidence_plan",
    "resource_plan": "explainability.control_plane_trace.evidence_plan.resource_plan",
    "source_profile": "explainability.effective_state.source_profile",
}


def artifact_ref(name: str) -> str:
    return f"{ARTIFACT_REF_PREFIX}{name}"


def llm_call_ref(interaction_id: str) -> str:
    return f"{LLM_CALL_REF_PREFIX}{interaction_id}"


def walk_path(root: Any, path: str) -> Any:
    if path in {"", "."}:
        return root
    cur: Any = root
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        return None
    return cur


def build_artifact_index(forensic_bundle: dict[str, Any]) -> dict[str, str]:
    """Map artifact name → ref. Only names whose path currently resolves."""
    index: dict[str, str] = {}
    for name, path in CANONICAL_ARTIFACT_PATHS.items():
        if name == "full_debug_bundle" or walk_path(forensic_bundle, path) is not None:
            index[f"{name}_ref"] = artifact_ref(name)
    return index


def resolve_artifact_ref(forensic_bundle: dict[str, Any], ref: str | None) -> Any:
    """Resolve a reviewer ref against the forensic bundle.

    ``artifact:full_debug_bundle`` returns the bundle itself. LLM call refs walk
    the forensic timeline (and ``explainability.llm_interactions`` fallback).
    Unknown refs raise ``KeyError``.
    """
    if not isinstance(ref, str) or not ref:
        raise KeyError("empty_artifact_ref")
    if ref.startswith(LLM_CALL_REF_PREFIX):
        interaction_id = ref[len(LLM_CALL_REF_PREFIX) :]
        found = _find_llm_interaction(forensic_bundle, interaction_id)
        if found is None:
            raise KeyError(ref)
        return found
    if not ref.startswith(ARTIFACT_REF_PREFIX):
        raise KeyError(ref)
    name = ref[len(ARTIFACT_REF_PREFIX) :]
    path = CANONICAL_ARTIFACT_PATHS.get(name)
    if path is None:
        raise KeyError(ref)
    value = walk_path(forensic_bundle, path)
    if name != "full_debug_bundle" and value is None:
        raise KeyError(ref)
    return forensic_bundle if name == "full_debug_bundle" else value


def resolve_all_refs(forensic_bundle: dict[str, Any], refs: dict[str, Any]) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, ref in refs.items():
        if not isinstance(ref, str):
            continue
        if ref.startswith(ARTIFACT_REF_PREFIX) or ref.startswith(LLM_CALL_REF_PREFIX):
            resolved[key] = resolve_artifact_ref(forensic_bundle, ref)
    return resolved


def _find_llm_interaction(forensic_bundle: dict[str, Any], interaction_id: str) -> dict[str, Any] | None:
    for event in forensic_bundle.get("timeline") or []:
        if not isinstance(event, dict):
            continue
        body = event.get("event") if isinstance(event.get("event"), dict) else event
        if str(body.get("interaction_id") or "") == interaction_id:
            return body
        forensic = body.get("forensic") if isinstance(body.get("forensic"), dict) else {}
        if str(body.get("interaction_id") or forensic.get("interaction_id") or "") == interaction_id:
            return body
    interactions = walk_path(forensic_bundle, "explainability.llm_interactions")
    if isinstance(interactions, list):
        for item in interactions:
            if isinstance(item, dict) and str(item.get("interaction_id") or "") == interaction_id:
                return item
    metadata = forensic_bundle.get("run", {})
    if isinstance(metadata, dict):
        meta = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else metadata
        stored = meta.get("llm_interactions") if isinstance(meta, dict) else None
        if isinstance(stored, list):
            for item in stored:
                if isinstance(item, dict) and str(item.get("interaction_id") or "") == interaction_id:
                    return item
    return None
