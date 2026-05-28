"""Stage 3K-Q1F: extract exact route-plan candidate JSON from LLM wrappers.

LLM responses may wrap the candidate in markdown fences, labels, or trailing
commentary. This module extracts the first balanced ``{...}`` object and
``json.loads`` it verbatim — no repair, no field injection, no authority overrides.
"""

from __future__ import annotations

from app.llm.adapter.json_extractor import JsonExtractionResult, extract_first_json_object


def extract_route_plan_candidate_json(raw_output: str | None) -> JsonExtractionResult:
    """Extract one exact valid JSON object from wrapped LLM output.

    Supported wrappers (non-exhaustive):

    - Raw JSON only
    - Prose before/after the object
    - Markdown fences (e.g. ```json ... ```)
    - Multiple objects (first balanced object wins; warning recorded)

    Returns ``parsed_ok=False`` when no exact valid object can be loaded.
    """
    return extract_first_json_object(raw_output)
