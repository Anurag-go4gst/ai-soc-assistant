"""Optional Instruct-only LLM assist for Q4A drafts (author-time only)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from app.coverage.coverage_models import PatternCoverageEntry

from deterministic import draft_entry_deterministic
from registries import RegistrySnapshot

REASONING_MODEL_MARKERS = ("reasoning", "foundation-sec-reasoning", "foundation_sec_reasoning")
INSTRUCT_MODEL_MARKERS = ("instruct", "foundation-sec-instruct", "foundation_sec_instruct")


def assert_instruct_only(*, model_family: str | None = None, provider: str | None = None) -> None:
    combined = f"{model_family or ''} {provider or ''}".lower()
    if any(marker in combined for marker in REASONING_MODEL_MARKERS):
        raise ValueError("Foundation-sec-Reasoning and reasoning providers are rejected for Q4A coverage drafting")
    if model_family and not any(marker in model_family.lower() for marker in INSTRUCT_MODEL_MARKERS):
        if "reasoning" in model_family.lower():
            raise ValueError(f"Non-instruct model family rejected: {model_family}")


def build_llm_prompt(
    question: str,
    question_ref: str,
    snapshot: RegistrySnapshot,
) -> str:
    return (
        "You are an author-time assistant drafting ONE coverage manifest entry as JSON.\n"
        "Return only a JSON object for the `entry` fields (no markdown).\n"
        "Never invent template_ref, lookup_ref, detection_ref, or evidence_contract_ref.\n"
        "Choose only from these closed sets:\n"
        f"runtime_skills: {sorted(snapshot.runtime_skills)}\n"
        f"production_template_refs (non-sample): {sorted(snapshot.production_template_refs)}\n"
        f"lookup_refs: {sorted(snapshot.lookup_refs)}\n"
        f"bindable_detection_refs: {sorted(snapshot.detection_refs_bindable)}\n"
        f"detection_families: {sorted(snapshot.detection_families)}\n"
        f"evidence_contract_refs: {sorted(snapshot.evidence_contract_refs)}\n"
        f"readiness_labels: {sorted(snapshot.readiness_labels)}\n"
        f"route_status_values: {sorted(snapshot.route_status_values)}\n"
        "All governance execution flags must be false. sample_only must be false.\n"
        f"question_ref: {question_ref}\n"
        f"question: {question}\n"
    )


def parse_llm_entry_payload(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM output did not contain a JSON object")
    return json.loads(text[start : end + 1])


def draft_entry_with_llm(
    question: str,
    question_ref: str,
    pattern_type: str | None,
    snapshot: RegistrySnapshot,
    *,
    llm_raw_output_provider: Callable[[], str],
    model_family: str = "instruct",
    provider: str = "stub",
) -> tuple[PatternCoverageEntry, list[str]]:
    assert_instruct_only(model_family=model_family, provider=provider)
    baseline = draft_entry_deterministic(question, question_ref, pattern_type, snapshot)
    prompt = build_llm_prompt(question, question_ref, snapshot)
    _ = prompt  # prompt is for live providers; stub tests ignore content
    raw = llm_raw_output_provider()
    payload = parse_llm_entry_payload(raw)
    if "entry" in payload and isinstance(payload["entry"], dict):
        payload = payload["entry"]
    merged = baseline.model_dump()
    merged.update(payload)
    merged["question"] = question
    merged["question_ref"] = question_ref
    disagreements: list[str] = []
    for key in ("template_ref", "lookup_ref", "detection_ref", "evidence_contract_ref"):
        llm_val = payload.get(key)
        base_val = getattr(baseline, key)
        if llm_val is not None and llm_val != base_val:
            disagreements.append(f"llm_overrode_{key}:{llm_val}")
            if key == "template_ref" and llm_val not in snapshot.production_template_refs:
                merged[key] = base_val
                disagreements.append(f"deterministic_restored_{key}")
            elif key == "detection_ref" and llm_val not in snapshot.detection_refs_bindable:
                merged[key] = base_val
                disagreements.append(f"deterministic_restored_{key}")
            elif key == "lookup_ref" and llm_val not in snapshot.lookup_refs:
                merged[key] = base_val
                disagreements.append(f"deterministic_restored_{key}")
            elif key == "evidence_contract_ref" and llm_val not in snapshot.evidence_contract_refs:
                merged[key] = base_val
                disagreements.append(f"deterministic_restored_{key}")
    entry = PatternCoverageEntry.model_validate(merged)
    return entry, disagreements
