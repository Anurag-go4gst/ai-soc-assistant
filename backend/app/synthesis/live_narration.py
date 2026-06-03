"""Live-model narration of the analyst summary for the live `/chat` path.

The model narrates prose ONLY. Every fact (severity, MITRE techniques + status,
recommended actions, aggregates, SPL, execution eligibility) is owned by the
deterministic pipeline and passed in as constrained context. The model is asked
to restate those governed facts as a readable SOC analyst summary and nothing
more. On any failure this returns None and the caller keeps the deterministic
summary — a live model is never allowed to break or block a chat answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.llm.clients import LocalChatClient, LocalChatError
from app.synthesis.models import GovernedSynthesisPackage

_SYSTEM_PROMPT = (
    "You are a SOC analyst assistant. You will be given a set of GOVERNED FACTS "
    "that were already computed by a deterministic security pipeline. Write a "
    "concise analyst summary (2-4 sentences) that restates only those facts in "
    "clear language for a SOC analyst.\n"
    "Hard rules:\n"
    "- Use ONLY the provided facts. Do not invent counts, IP addresses, users, "
    "hostnames, MITRE techniques, severities, or actions.\n"
    "- Do not infer absence of activity that is not stated.\n"
    "- Do not write SPL, queries, or code.\n"
    "- If a fact says evidence is missing, say it is missing; do not fill it in.\n"
    "- Output plain prose only, no headings, no JSON, no bullet symbols."
)


@dataclass(frozen=True)
class NarrationResult:
    summary: str
    model: str
    latency_ms: int
    usage: dict[str, int]


def narrate_analyst_summary(
    *,
    package: GovernedSynthesisPackage,
    deterministic_draft: dict[str, Any],
    severity_label: str | None,
    client: LocalChatClient,
) -> NarrationResult | None:
    """Return a model-narrated summary, or None on any failure."""
    user_prompt = _build_governed_prompt(
        package=package,
        deterministic_draft=deterministic_draft,
        severity_label=severity_label,
    )
    max_tokens = min(settings.ai_soc_llm_max_output_tokens, 256)
    try:
        result = client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=settings.ai_soc_llm_temperature,
        )
    except LocalChatError:
        return None
    summary = result.text.strip()
    if not summary:
        return None
    return NarrationResult(
        summary=summary[:1200],
        model=result.model,
        latency_ms=result.latency_ms,
        usage=result.usage,
    )


def _build_governed_prompt(
    *,
    package: GovernedSynthesisPackage,
    deterministic_draft: dict[str, Any],
    severity_label: str | None,
) -> str:
    """Render the governed facts as a compact, fixed-structure fact sheet.

    Source: the deterministic draft + governed package only. No raw event text
    and no `source_evidence` rows are included, so attacker-controlled fields
    never reach the model.
    """
    lines: list[str] = ["GOVERNED FACTS:"]
    if severity_label:
        priority = deterministic_draft.get("priority")
        lines.append(f"- Severity: {severity_label}" + (f" (priority {priority})" if priority else ""))

    mitre = deterministic_draft.get("mitre_mappings") or []
    if mitre:
        rendered = ", ".join(
            f"{row.get('technique_id')} [{row.get('status')}]"
            for row in mitre
            if isinstance(row, dict) and row.get("technique_id")
        )
        if rendered:
            lines.append(f"- MITRE techniques (permitted set, with status): {rendered}")

    for aggregate in package.precomputed_aggregates:
        if aggregate.safe_for_model_use and aggregate.value is not None:
            lines.append(f"- Aggregate {aggregate.aggregate_key}: {aggregate.value} (source {aggregate.source})")

    actions = deterministic_draft.get("recommended_actions") or []
    if actions:
        lines.append("- Recommended actions (in order): " + ", ".join(str(a) for a in actions))

    missing = [item.analyst_wording for item in package.missing_evidence[:4]]
    if missing:
        lines.append("- Missing/unavailable evidence: " + " ".join(missing))

    lines.append(
        "\nWrite the analyst summary now using only the facts above."
    )
    return "\n".join(lines)
