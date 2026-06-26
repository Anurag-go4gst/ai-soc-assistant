"""Deterministic skill-contribution contract + investigation visible-section floor.

P1 steps 4–5 (plan `plans/2026-06-21_live-efficacy-remediation-and-test-quality.md`).

The live-efficacy-100 review found that skill selection behaved "more like a label
than an answer-shaping contract": investigation skills were selected but frequently
contributed no analyst-visible section. This module makes the contribution
*observable* and enforces a floor:

- `build_skill_contribution(...)` inspects the finalized analyst envelope and records
  what the selected skill actually contributed (sections + evidence keys), the
  routing provenance, a deterministic skip reason when nothing was contributed, and
  whether a visible domain-specific section survived into the card.
- `apply_investigation_floor(...)` guarantees that when an investigation skill is
  selected but produced no visible domain-specific section (and no legitimate skip
  reason applies), a deterministic generic investigation section is added and the
  gap is recorded — never a silent empty card.

Pure/deterministic. No LLM, no flags. It only ever *adds* a fallback section; it
never removes or rewrites authored content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas.responses import AnalystResponseEnvelope

# Skills whose job is to shape an investigation/detection answer (not a bounded
# knowledge lookup). These are the skills the visible-section floor applies to.
INVESTIGATION_SKILLS = frozenset(
    {"guided_investigation", "attack_discovery", "alert_summary", "spl_generation"}
)

# Envelope attributes that count as an analyst-visible, domain-specific section.
# Order is the reporting/precedence order for `primary_section`.
_DOMAIN_SECTION_FIELDS: tuple[tuple[str, str], ...] = (
    ("spl_code", "spl_artifact"),
    ("draft_spl_code", "spl_draft"),
    ("spl_draft_preview", "spl_draft_preview"),
    ("investigation_steps", "investigation_steps"),
    ("recommended_actions", "recommended_actions"),
    ("analyst_checklist", "analyst_checklist"),
    ("mitre_mappings", "mitre_mappings"),
    ("foundation_sec_analysis", "analysis_narrative"),
    ("retrieved_playbook", "playbook"),
    ("sop_guidance", "sop_guidance"),
    ("key_fields", "key_fields"),
    ("escalation_criteria", "escalation_criteria"),
)

# Legitimate reasons an investigation skill contributes no domain section. When one
# of these holds, the floor stands down (the empty card is correct by design).
_LEGITIMATE_SKIP_REASONS = frozenset(
    {
        "clarification_required",
        "human_review_required",
        "out_of_scope_boundary",
        "unsafe_execution_refused",
    }
)


@dataclass
class SkillContribution:
    selected_skill: str
    contributed_sections: list[str] = field(default_factory=list)
    contributed_evidence_keys: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    skip_reason: str | None = None
    visible_domain_section: bool = False
    survived_into_card: bool = False
    floor_applied: bool = False
    gap_recorded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_skill": self.selected_skill,
            "contributed_sections": list(self.contributed_sections),
            "contributed_evidence_keys": list(self.contributed_evidence_keys),
            "provenance": dict(self.provenance),
            "skip_reason": self.skip_reason,
            "visible_domain_section": self.visible_domain_section,
            "survived_into_card": self.survived_into_card,
            "floor_applied": self.floor_applied,
            "gap_recorded": self.gap_recorded,
        }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return bool(value)


def _populated_sections(envelope: AnalystResponseEnvelope) -> list[str]:
    sections: list[str] = []
    for attr, label in _DOMAIN_SECTION_FIELDS:
        if _has_value(getattr(envelope, attr, None)) and label not in sections:
            sections.append(label)
    return sections


def _section_is_render_visible(envelope: AnalystResponseEnvelope, sections: list[str]) -> bool:
    """A section counts as surviving unless render_sections explicitly hides all of them."""
    render = envelope.render_sections or {}
    if not render:
        # No visibility map → populated sections render by default.
        return bool(sections)
    # Map the abstract section labels back onto whatever render keys exist; if any
    # populated section is not explicitly disabled, it survives.
    for label in sections:
        if render.get(label) is not False:
            return True
    return bool(sections) and not all(render.get(s) is False for s in sections)


def _evidence_keys(source_evidence: Any) -> list[str]:
    keys: list[str] = []
    if not isinstance(source_evidence, (list, tuple)):
        return keys
    for item in source_evidence:
        if isinstance(item, dict):
            ref = item.get("source_id") or item.get("title") or item.get("id") or item.get("source")
        else:
            ref = getattr(item, "source_id", None) or getattr(item, "title", None) or getattr(item, "id", None)
        if isinstance(ref, str) and ref.strip():
            keys.append(ref.strip())
    return keys


def _derive_skip_reason(
    *,
    envelope: AnalystResponseEnvelope,
    human_review: dict[str, Any] | None,
    boundary_class: str | None,
) -> str | None:
    if boundary_class in {"out_of_scope", "out_of_scope_boundary"}:
        return "out_of_scope_boundary"
    if boundary_class in {"unsafe_execution", "prompt_injection"}:
        return "unsafe_execution_refused"
    if isinstance(human_review, dict) and human_review:
        reason = str(human_review.get("reason") or human_review.get("type") or "human_review_required")
        if "clarif" in reason.lower():
            return "clarification_required"
        return "human_review_required"
    status = (envelope.execution_status_label or "").lower()
    if "clarif" in status:
        return "clarification_required"
    return None



def derive_boundary_class(query: str) -> str | None:
    """Map a live query to a boundary skip class for the contribution contract."""
    from app.chat.query_signals import extract_query_signals
    from app.query_understanding.soc_investigation_shape import is_unsafe_execution

    normalized = " ".join(query.lower().split())
    signals = extract_query_signals(query)
    if is_unsafe_execution(normalized) or signals.get("block_or_contain") or signals.get("explicit_run_spl"):
        return "unsafe_execution"
    if signals.get("non_soc_or_out_of_scope"):
        return "out_of_scope_boundary"
    return None


def build_skill_contribution(
    *,
    selected_skill: str,
    envelope: AnalystResponseEnvelope | None,
    routing_provenance: dict[str, Any] | None = None,
    source_evidence: Any = None,
    human_review: dict[str, Any] | None = None,
    boundary_class: str | None = None,
) -> SkillContribution:
    """Build the deterministic skill-contribution record for the finalized answer."""
    contrib = SkillContribution(selected_skill=selected_skill or "knowledge_recall")
    prov = routing_provenance or {}
    contrib.provenance = {
        "authority_source": prov.get("authority_source"),
        "selected_by": prov.get("selected_by"),
        "deterministic_match_path": prov.get("deterministic_match_path"),
        "rescue_mode": prov.get("rescue_mode"),
    }
    if envelope is None:
        contrib.skip_reason = "no_envelope"
        return contrib

    sections = _populated_sections(envelope)
    contrib.contributed_sections = sections
    contrib.contributed_evidence_keys = _evidence_keys(source_evidence)
    contrib.visible_domain_section = bool(sections) and _section_is_render_visible(envelope, sections)
    contrib.survived_into_card = contrib.visible_domain_section
    if not sections:
        contrib.skip_reason = _derive_skip_reason(
            envelope=envelope, human_review=human_review, boundary_class=boundary_class
        )
    return contrib


# Deterministic, domain-generic investigation steps used only when an investigation
# skill produced no visible section and no legitimate skip reason applies. Kept
# review-only and execution-free, consistent with the rest of the pipeline.
_GUIDED_BRANCHING_HYPOTHESES: tuple[str, ...] = (
    "Approved vendor, maintenance, or expected operational activity.",
    "Configuration or telemetry drift producing an apparent anomaly.",
    "Suspicious activity requiring corroboration before severity or containment.",
)

_GENERIC_INVESTIGATION_FLOOR: tuple[str, ...] = (
    "Confirm the alert scope: affected hosts/identities, first/last seen, and the "
    "originating data source.",
    "Pull the supporting events for the observed behavior and verify they are not a "
    "known-good or sanctioned activity.",
    "Correlate across adjacent domains (identity, endpoint, network) for the same "
    "entity within the alert window.",
    "Record what evidence is still missing before severity or containment can be "
    "asserted; keep execution review-only until validated.",
)


def apply_investigation_floor(
    *,
    envelope: AnalystResponseEnvelope,
    contribution: SkillContribution,
) -> AnalystResponseEnvelope:
    """Add a deterministic generic investigation section when an investigation skill
    produced none and no legitimate skip reason applies. Records the gap on the
    contribution record. Returns the (possibly updated) envelope.
    """
    if contribution.selected_skill not in INVESTIGATION_SKILLS:
        return envelope
    if envelope.finding_title in {"GitHub investigation guidance", "CVE investigation guidance", "Cross-skill investigation plan", "MITRE evidence thresholds"}:
        contribution.visible_domain_section = True
        return envelope
    if contribution.visible_domain_section:
        return envelope
    if contribution.skip_reason in _LEGITIMATE_SKIP_REASONS:
        # Empty card is correct by design (clarification/boundary/HIL).
        return envelope

    steps = list(envelope.investigation_steps or [])
    recommended = list(envelope.recommended_actions or [])
    if contribution.selected_skill == "guided_investigation":
        for hypothesis in _GUIDED_BRANCHING_HYPOTHESES:
            label = f"Hypothesis: {hypothesis}"
            if label not in steps:
                steps.insert(0, label)
            if hypothesis not in recommended:
                recommended.insert(0, hypothesis)
    for step in _GENERIC_INVESTIGATION_FLOOR:
        if step not in steps:
            steps.append(step)
    render = dict(envelope.render_sections or {})
    render["investigation_steps"] = True
    if recommended:
        render["recommended_actions"] = True
    update_payload: dict[str, Any] = {"investigation_steps": steps, "render_sections": render}
    if recommended:
        update_payload["recommended_actions"] = recommended[:8]
    updated = envelope.model_copy(update=update_payload)

    contribution.floor_applied = True
    contribution.gap_recorded = True
    contribution.skip_reason = contribution.skip_reason or "investigation_floor_no_skill_section"
    if "investigation_steps" not in contribution.contributed_sections:
        contribution.contributed_sections.append("investigation_steps")
    contribution.visible_domain_section = True
    contribution.survived_into_card = True
    return updated

def apply_out_of_catalog_guidance_floor(
    *,
    envelope: AnalystResponseEnvelope | None,
    contribution: SkillContribution,
    message: str,
    match_path: str | None,
) -> AnalystResponseEnvelope | None:
    """Preserve shaped out-of-catalog guidance when synthesis produced no narrative."""
    if envelope is not None and contribution.visible_domain_section:
        return envelope
    if str(match_path or "") != "out_of_registry":
        return envelope
    if contribution.selected_skill not in INVESTIGATION_SKILLS:
        return envelope
    direct = str(message or "").strip()
    if not direct or direct.lower().startswith("no governed kb/sop match"):
        return envelope
    if envelope is None:
        envelope = AnalystResponseEnvelope(
            finding_title="SOC investigation guidance",
            one_sentence_finding=direct[:1200],
            direct_answer_summary=direct[:1200],
            response_profile="hybrid_alert_review",
        )
    else:
        envelope = envelope.model_copy(
            update={
                "direct_answer_summary": direct[:1200],
                "one_sentence_finding": direct[:1200] or envelope.one_sentence_finding,
            }
        )
    contribution.floor_applied = True
    contribution.gap_recorded = True
    contribution.skip_reason = contribution.skip_reason or "out_of_catalog_guidance_floor"
    if "analysis_narrative" not in contribution.contributed_sections:
        contribution.contributed_sections.append("analysis_narrative")
    contribution.visible_domain_section = True
    contribution.survived_into_card = True
    return envelope

