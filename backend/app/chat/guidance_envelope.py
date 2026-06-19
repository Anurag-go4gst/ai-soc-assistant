"""Populate analyst-envelope arrays from shaped guidance prose.

The T2 answer-shape / signal-class / WS-7 builders emit rich markdown (hypotheses,
evidence, checklist, steps) into the message, but the structured AnalystResponse
envelope arrays stayed empty — so the card's structured sections did not match the
prose. This parser lifts the bullet groups out of the message into the real
envelope fields (recommended_actions / analyst_checklist / investigation_steps /
initial_assessment) so structured == prose.
"""

from __future__ import annotations

import re
from typing import Any

from app.schemas.responses import AnalystResponseEnvelope

_BULLET = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
# A header line introduces a bullet group, e.g. "Hypotheses", "Evidence to collect:",
# "Checklist:", "Staged guidance:", "Next steps", "Review steps", "Approach:".
_HEADER = re.compile(r"^\s*([A-Za-z][A-Za-z /-]{2,40}?)\s*:?\s*$")

# Header keyword -> envelope bucket.
_HYPOTHESIS_KEYS = ("hypothes",)
_CHECKLIST_KEYS = ("checklist", "evidence", "staged guidance", "approach", "grid-physics framing")
_STEP_KEYS = ("step", "next steps", "review steps")


def _bucket_for_header(header: str) -> str:
    lowered = header.lower()
    if any(key in lowered for key in _HYPOTHESIS_KEYS):
        return "hypotheses"
    if any(key in lowered for key in _STEP_KEYS):
        return "steps"
    if any(key in lowered for key in _CHECKLIST_KEYS):
        return "checklist"
    return "checklist"


def parse_guidance_sections(text: str) -> dict[str, list[str]]:
    """Extract bullet groups from shaped guidance, keyed by bucket."""
    sections: dict[str, list[str]] = {"hypotheses": [], "checklist": [], "steps": []}
    current = "checklist"
    for raw in (text or "").splitlines():
        bullet = _BULLET.match(raw)
        if bullet:
            item = bullet.group(1).strip()
            if item and item not in sections[current]:
                sections[current].append(item)
            continue
        header = _HEADER.match(raw)
        if header and not raw.lstrip().startswith(("-", "*")):
            current = _bucket_for_header(header.group(1))
    return sections


def populate_envelope_from_guidance(
    envelope: AnalystResponseEnvelope,
    guidance_text: str,
    *,
    limitations: list[str] | None = None,
) -> AnalystResponseEnvelope:
    """Return a copy of the envelope with structured arrays filled from the prose.

    Never overwrites arrays that are already populated upstream.
    """
    sections = parse_guidance_sections(guidance_text)
    hypotheses = sections["hypotheses"]
    checklist = sections["checklist"]
    steps = sections["steps"]

    update: dict[str, Any] = {}
    if hypotheses and not envelope.initial_assessment:
        update["initial_assessment"] = hypotheses[:8]
    merged_checklist = checklist or hypotheses
    if merged_checklist and not envelope.analyst_checklist:
        update["analyst_checklist"] = merged_checklist[:10]
    if steps and not envelope.investigation_steps:
        update["investigation_steps"] = steps[:10]
    # recommended_actions drives the analyst card's action list; prefer concrete
    # steps, fall back to the checklist so the array is never empty when prose has one.
    actions = steps or checklist
    if actions and not envelope.recommended_actions:
        update["recommended_actions"] = actions[:10]
    if limitations and not envelope.limitations:
        lim = [str(item).strip() for item in limitations if str(item).strip()]
        if lim:
            update["limitations"] = lim[:8]

    if not update:
        return envelope
    return envelope.model_copy(update=update)
