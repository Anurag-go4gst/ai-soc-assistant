"""Harmful-SPL vigilance for LLM-lineage SPL (item 2.4, respec'd 2026-07-03).

Refined governance boundary (supersedes the flat "lab-tier LLM SPL is never
executable" invariant): raw lab-tier LLM SPL is STILL never directly
executable — that invariant is untouched, still enforced in
`app.safeguards.spl_validator.validate_spl_lab_candidate` and pinned by
`test_t2_governed_producer.py` / `test_llm_plan_compiler.py`. This module
governs a SEPARATE, narrower path: after an LLM-produced SPL template's
placeholder index/sourcetype slots are resolved to real, allowlisted values
(`app.spl.spl_source_resolve.resolve_spl_source_profile`) and the RESULT
passes the real `validate_spl` (not the lab-candidate variant), THIS module
classifies the resolved artifact into a risk tier before it may become
execution-eligible:

  - high  -> blocked. Never reaches the MCP gate. Validator rejection,
             detected prompt injection, or a still-present risky/blocked
             command token (defense in depth; the validator should already
             have caught this) all classify as high.
  - medium -> HIL required (the existing, unchanged per-call confirmation
              gate applies exactly as it always has).
  - low   -> auto-eligible candidate ONLY when every hard criterion holds:
             validator-approved, no injection, and the structural relevance
             gate confirms the SPL answers the question. Auto-eligibility is
             advisory data on the derived artifact; wiring it to actually
             skip confirmation is scoped separately (mock-mode only — see
             plan Drift log; live/registry mode's existing "always requires
             per-call confirmation" rule in
             `app.orchestration.mcp_execution_gate` is never overridden by
             this module).

Every classification call is meant to produce a full audit trail
(`checks_passed`/`checks_failed`) suitable for the trace spine — this module
never silently drops information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.safeguards.prompt_injection_filter import filter_prompt_injection
from app.safeguards.spl_validator import RISKY_COMMANDS
from app.spl.spl_relevance_check import check_spl_relevance

RiskTier = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class VigilanceResult:
    risk_tier: RiskTier
    auto_eligible: bool
    requires_hil: bool
    blocked: bool
    blocked_reason: str | None
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    injection_detected: bool = False
    relevance_passed: bool = False
    validator_approved: bool = False

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "risk_tier": self.risk_tier,
            "auto_eligible": self.auto_eligible,
            "requires_hil": self.requires_hil,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "checks_passed": list(self.checks_passed),
            "checks_failed": list(self.checks_failed),
            "injection_detected": self.injection_detected,
            "relevance_passed": self.relevance_passed,
            "validator_approved": self.validator_approved,
        }


def _blocked_result(reason: str, *, checks_passed: list[str], checks_failed: list[str], **flags: bool) -> VigilanceResult:
    return VigilanceResult(
        risk_tier="high",
        auto_eligible=False,
        requires_hil=False,
        blocked=True,
        blocked_reason=reason,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        **flags,
    )


def classify_llm_spl_risk(
    *,
    normalized_spl: str | None,
    validator_result: dict[str, Any],
    user_query: str,
) -> VigilanceResult:
    """Classify an LLM-lineage, slot-resolved SPL artifact into a risk tier.

    `validator_result` must be the REAL `validate_spl(...)` output computed
    on the resolved SPL (i.e. `resolve_result.validation` from
    `resolve_spl_source_profile`, never `validate_spl_lab_candidate`).
    """
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    validator_approved = bool(validator_result.get("approved")) and bool(normalized_spl)
    if validator_approved:
        checks_passed.append("validator_approved")
    else:
        checks_failed.append("validator_approved")
        return _blocked_result(
            "validator_rejected",
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            validator_approved=False,
        )

    # Defense in depth: the validator already blocks RISKY_COMMANDS /
    # spl_blocked_commands, but LLM-lineage SPL gets a second, independent
    # check against the same risky-command set before it may proceed.
    blocked_commands = set(validator_result.get("blocked_commands_found") or [])
    if blocked_commands & RISKY_COMMANDS or blocked_commands:
        checks_failed.append("no_risky_commands")
        return _blocked_result(
            "risky_command_present",
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            validator_approved=True,
        )
    checks_passed.append("no_risky_commands")

    if not bool(validator_result.get("time_bounds_present")):
        checks_failed.append("bounded_time")
        return _blocked_result(
            "missing_time_bounds",
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            validator_approved=True,
        )
    checks_passed.append("bounded_time")

    if not bool(validator_result.get("result_limit_present")):
        checks_failed.append("result_cap")
        return _blocked_result(
            "missing_result_cap",
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            validator_approved=True,
        )
    checks_passed.append("result_cap")

    injection = filter_prompt_injection(user_query or "")
    injection_detected = bool(injection.get("suspicious"))
    if injection_detected:
        checks_failed.append("no_injection_pattern")
        return _blocked_result(
            "prompt_injection_detected",
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            injection_detected=True,
            validator_approved=True,
        )
    checks_passed.append("no_injection_pattern")

    relevance = check_spl_relevance(user_query or "", normalized_spl)
    relevance_passed = bool(relevance.relevant)
    if relevance_passed:
        checks_passed.append("relevance_pass")
        return VigilanceResult(
            risk_tier="low",
            auto_eligible=True,
            requires_hil=False,
            blocked=False,
            blocked_reason=None,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            injection_detected=False,
            relevance_passed=True,
            validator_approved=True,
        )

    checks_failed.append("relevance_pass")
    return VigilanceResult(
        risk_tier="medium",
        auto_eligible=False,
        requires_hil=True,
        blocked=False,
        blocked_reason=None,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        injection_detected=False,
        relevance_passed=False,
        validator_approved=True,
    )
