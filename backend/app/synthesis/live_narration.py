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
from app.llm.clients.local_chat_errors import user_message_for_local_chat_error
from app.llm.sanitize_user_facing_prose import sanitize_user_facing_prose
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
    "- Output only the final analyst-facing answer.\n"
    "- Do not include hidden reasoning, chain-of-thought, scratchpad notes, planning text, or <think> tags.\n"
    "- Do not start with phrases like 'The user is asking', 'I need to', 'Let's break down', or 'Possible angles'.\n"
    "- Output plain prose only, no headings, no JSON, no bullet symbols."
)


@dataclass(frozen=True)
class NarrationResult:
    summary: str
    model: str
    latency_ms: int
    usage: dict[str, int]
    finish_reason: str | None = None
    sanitizer_notes: list[str] | None = None


@dataclass(frozen=True)
class NarrationFailure:
    code: str
    user_message: str


def narrate_analyst_summary(
    *,
    package: GovernedSynthesisPackage,
    deterministic_draft: dict[str, Any],
    severity_label: str | None,
    client: LocalChatClient,
    structured_context: dict[str, Any] | None = None,
) -> NarrationResult | NarrationFailure | None:
    """Return narrated summary, structured failure, or None when client misconfigured."""
    user_prompt = _build_governed_prompt(
        package=package,
        deterministic_draft=deterministic_draft,
        severity_label=severity_label,
        structured_context=structured_context or {},
    )
    max_tokens = min(settings.ai_soc_llm_max_output_tokens, 256)
    try:
        result = client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=settings.ai_soc_llm_temperature,
        )
    except LocalChatError as exc:
        return NarrationFailure(code=exc.code, user_message=exc.user_message)
    if result.finish_reason == "length":
        return NarrationFailure(
            code="live_narration_truncated",
            user_message="Live narration was truncated by the model; kept the deterministic summary.",
        )
    sanitized = sanitize_user_facing_prose(result.text)
    summary = sanitized.text.strip()
    if not summary:
        return NarrationFailure(
            code="empty_completion",
            user_message=user_message_for_local_chat_error("empty_completion"),
        )
    return NarrationResult(
        summary=summary[:1200],
        model=result.model,
        latency_ms=result.latency_ms,
        usage=result.usage,
        finish_reason=result.finish_reason,
        sanitizer_notes=sanitized.notes,
    )


def _build_governed_prompt(
    *,
    package: GovernedSynthesisPackage,
    deterministic_draft: dict[str, Any],
    severity_label: str | None,
    structured_context: dict[str, Any],
) -> str:
    """Render the governed facts as a compact, fixed-structure fact sheet.

    Source: the deterministic draft, the governed package, and only the
    deterministically-derived (`computed_by_ai_soc`) structured-fact statements
    plus aggregate metric counts. No raw event text, no `source_evidence` rows,
    and no extracted entity values (src IPs, users, hosts) are included, so
    attacker-controlled fields never reach the model.
    """
    lines: list[str] = ["GOVERNED FACTS:"]

    findings = [
        str(fact.get("statement") or "").strip()
        for fact in (structured_context.get("structured_facts") or [])
        if isinstance(fact, dict)
        and fact.get("derivation") == "computed_by_ai_soc"
        and str(fact.get("statement") or "").strip()
    ]
    for statement in findings[:4]:
        lines.append(f"- Finding: {statement}")

    metrics = structured_context.get("metrics") or {}
    total = metrics.get("total_result_count")
    if isinstance(total, int):
        lines.append(f"- Total previewable rows collected across sources: {total}")

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

    draft_summary = str(deterministic_draft.get("analyst_summary") or "").strip()
    if draft_summary:
        lines.append(
            "- Summary draft to rewrite in clear analyst prose (use only these facts, do not invent): "
            + draft_summary[:1800]
        )

    lines.append(
        "\nWrite the analyst summary now using only the facts above."
    )
    return "\n".join(lines)
