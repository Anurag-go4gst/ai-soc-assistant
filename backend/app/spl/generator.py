from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CandidateSpl:
    trace_id: str
    skill: str
    user_query: str
    candidate_spl: str
    generation_mode: str
    confidence: float
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "skill": self.skill,
            "user_query": self.user_query,
            "candidate_spl": self.candidate_spl,
            "generation_mode": self.generation_mode,
            "confidence": self.confidence,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
        }


class StubSplGenerator:
    generation_mode = "stub"

    def generate(self, trace_id: str, skill: str, user_query: str) -> CandidateSpl:
        lowered = user_query.lower()
        spl, confidence, assumptions = _candidate_for_query(lowered)
        warnings: list[str] = []
        if skill not in {"attack_discovery", "spl_generation"}:
            spl = ""
            confidence = 0.0
            assumptions = ["SPL generation is not required for this routed skill at this stage."]
            warnings = ["spl_not_required"]

        return CandidateSpl(
            trace_id=trace_id,
            skill=skill,
            user_query=user_query,
            candidate_spl=spl,
            generation_mode=self.generation_mode,
            confidence=confidence,
            assumptions=assumptions,
            warnings=warnings,
        )


def generate_candidate_spl(trace_id: str, skill: str, user_query: str) -> CandidateSpl:
    return StubSplGenerator().generate(trace_id=trace_id, skill=skill, user_query=user_query)


def _candidate_for_query(query: str) -> tuple[str, float, list[str]]:
    base = "search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now"
    if "source ip" in query and "failed" in query:
        return (
            f"{base} action=failure | stats count as fail_count by src | sort -fail_count | head 100",
            0.82,
            ["Uses pgcil_soc auth sourcetype and last-hour bounds."],
        )
    success_after_failures = ("successful login" in query or "success after" in query or "success following" in query) and (
        "multiple failed" in query
        or "followed" in query
        or "after failure" in query
        or "after failures" in query
        or "after failed" in query
        or "following failure" in query
        or "following failed" in query
        or "failures" in query
    )
    if success_after_failures:
        return (
            f"{base} | stats count(eval(action=\"failure\")) as fail_count count(eval(action=\"success\")) as success_count by user, src | where fail_count >= 5 AND success_count > 0 | sort -fail_count | head 100",
            0.76,
            ["Correlates failed then successful auth per user and source; aggregate form because stateful stream commands are not allowlisted."],
        )
    if "new" in query or "unusual" in query:
        return (
            f"{base} action=success | stats count by src | where NOT cidrmatch(\"10.0.0.0/8\", src) | sort -count | head 100",
            0.74,
            ["Treats non-RFC1918 source addresses as unusual for the stub generator."],
        )
    if "lockout" in query or "locked" in query:
        return (
            f"{base} signature=account_locked | timechart span=10m count | head 100",
            0.70,
            ["Account lockout trend candidate retained for generator coverage; chat does not request SPL for alert_summary."],
        )
    if "top users" in query or "most authentication events" in query:
        return (
            f"{base} | stats count by user | sort -count | head 100",
            0.70,
            ["Top user volume candidate retained for generator coverage; chat does not request SPL for knowledge_recall."],
        )
    return (
        f"{base} action=failure | stats count as fail_count by user | where fail_count > 50 | sort -fail_count | head 100",
        0.80,
        ["Fallback auth failure candidate for Stage 3C stub generation."],
    )
