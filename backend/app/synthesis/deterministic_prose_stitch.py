"""Track D: deterministic prose enhancements (no LLM) for weak-case answer families."""

from __future__ import annotations

from app.chat.query_signals import is_cross_skill_investigation_query


def build_cross_skill_stitch_block(user_query: str) -> str:
    """CVE + MITRE + GitHub legs for explicit cross-skill review plans."""
    normalized = " ".join(str(user_query or "").lower().split())
    has_cve = "cve" in normalized
    has_mitre = "mitre" in normalized or "att&ck" in normalized
    has_github = "github" in normalized or "commit" in normalized
    lines = ["Cross-skill investigation plan (review-only)"]
    if has_cve:
        lines.append(
            "CVE leg: confirm affected packages/versions from inventory and scanner outputs; "
            "do not claim exploitability without patch/version proof."
        )
    if has_mitre:
        lines.append(
            "MITRE leg: label each technique candidate/not-claimed with explicit evidence "
            "thresholds; no confirmed technique without corroboration."
        )
    if has_github:
        lines.append(
            "GitHub leg: collect actor, PAT provenance, commit SHA timeline, workflow diff, "
            "and audit_log events before containment."
        )
    lines.append(
        "MITRE status labels (review-only): Confirmed requires corroboration; "
        "Candidate is plausible pending evidence; Not-claimed when this question alone is insufficient."
    )
    lines.append(
        "No Splunk search or MCP execution was performed; conclusions remain candidate-only."
    )
    return "\n".join(lines)


def build_cross_skill_investigation_message(user_query: str) -> str:
    """Full analyst-visible message for multi-domain CVE/MITRE/GitHub review plans."""
    return build_cross_skill_stitch_block(user_query)


def apply_deterministic_prose_enhancements(
    message: str,
    *,
    user_query: str,
    intent_family: str | None = None,
    primary_intent: str | None = None,
) -> str:
    """Append deterministic stitch blocks when the turn is cross-skill shaped."""
    _ = intent_family
    if primary_intent == "cross_skill_investigation" or is_cross_skill_investigation_query(user_query):
        stitch = build_cross_skill_stitch_block(user_query)
        base = str(message or "").strip()
        if stitch.lower() in base.lower():
            return base
        return f"{base}\n\n{stitch}".strip() if base else stitch
    return message
