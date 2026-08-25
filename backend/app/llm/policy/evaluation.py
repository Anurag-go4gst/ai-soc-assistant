"""P4 PP6 — the active-versus-candidate prompt evaluation contract.

What this is
------------
The rules a prompt change must satisfy before it becomes active, plus the deterministic
machinery to enforce them. It is a contract, not a runner: P8 executes the live
comparison against a frozen bank on a real model.

What this deliberately is not
-----------------------------
It does not, and cannot, promote a candidate. ``EVAL_STATUS`` starts at
``NOT_RUN_LIVE`` and the only status that permits activation is ``LIVE_AB_COMPLETE``,
which nothing in P4 can produce. Deterministic tests passing is explicitly *not*
evidence about model behaviour: schema validity says the shape is right, never that
the answer is better. ``can_activate`` refuses on ``DETERMINISTIC_ONLY`` for exactly
that reason, so "local tests are green" cannot drift into "ship it".

Thresholds are frozen before a candidate runs, never after seeing its results.
``freeze_thresholds`` returns an immutable record; there is no setter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EVAL_CONTRACT_VERSION = "prompt_ab_eval_contract_v1"

EvalStatus = Literal[
    "NOT_RUN_LIVE",
    "DETERMINISTIC_ONLY",
    "LIVE_AB_IN_PROGRESS",
    "LIVE_AB_COMPLETE",
    "BLOCKED_INFRASTRUCTURE",
]

#: Metrics that must be frozen before either arm runs. Naming them here stops a
#: post-hoc metric being introduced once results are visible.
REQUIRED_FROZEN_METRICS: tuple[str, ...] = (
    "semantic_correctness",
    "schema_validity",
    "initial_pass_rate",
    "repair_rate",
    "fallback_rate",
    "invented_constraint_rate",
    "semantic_loss_rate",
    "latency_p50_ms",
    "latency_p95_ms",
    "input_tokens",
    "output_tokens",
    "cache_eligibility",
    "provider_cache_hit_rate",
)

#: Every one must hold before a candidate may be activated.
ACTIVATION_REQUIREMENTS: tuple[str, ...] = (
    "row_level_regression_review_complete",
    "governance_non_regression_proven",
    "security_non_regression_proven",
    "provenance_complete_report",
    "explicit_operator_approval",
    "rollback_target_recorded",
)


class PromotionRefused(RuntimeError):
    """Raised when activation is attempted without the evidence it requires."""


@dataclass(frozen=True)
class FrozenThresholds:
    """Thresholds fixed before the candidate runs. Immutable by construction."""

    contract_version: str
    role_id: str
    metrics: tuple[str, ...]
    minimums: tuple[tuple[str, float], ...]

    def metric_names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.minimums)


@dataclass(frozen=True)
class PromptArm:
    """One side of the comparison."""

    template_id: str
    version: str
    stable_prefix_hash: str


@dataclass(frozen=True)
class PromptEvaluationContract:
    role_id: str
    active: PromptArm
    candidate: PromptArm | None
    eval_status: EvalStatus
    thresholds: FrozenThresholds | None
    satisfied_requirements: tuple[str, ...] = field(default_factory=tuple)
    #: Infrastructure problems are reported here, never counted as semantic results.
    infrastructure_notes: tuple[str, ...] = field(default_factory=tuple)

    def unmet_requirements(self) -> tuple[str, ...]:
        return tuple(r for r in ACTIVATION_REQUIREMENTS if r not in self.satisfied_requirements)

    def can_activate(self) -> tuple[bool, str]:
        """Deterministic promotion gate. Returns (allowed, reason)."""
        if self.candidate is None:
            return False, "no_candidate_prompt"
        if self.eval_status != "LIVE_AB_COMPLETE":
            return False, f"live_ab_not_complete:{self.eval_status}"
        if self.thresholds is None:
            return False, "thresholds_never_frozen"
        unmet = self.unmet_requirements()
        if unmet:
            return False, f"unmet_activation_requirements:{','.join(unmet)}"
        return True, "activation_requirements_satisfied"

    def activate_or_raise(self) -> None:
        allowed, reason = self.can_activate()
        if not allowed:
            raise PromotionRefused(f"{self.role_id}: {reason}")


def freeze_thresholds(role_id: str, minimums: dict[str, float]) -> FrozenThresholds:
    """Freeze thresholds before a candidate runs.

    Every required metric must be present. Omitting one and adding it after results
    are visible is the classic way an A/B gets talked into a win.
    """
    missing = sorted(set(REQUIRED_FROZEN_METRICS) - set(minimums))
    if missing:
        raise ValueError(f"{role_id}: thresholds must be frozen for every metric; missing {missing}")
    unknown = sorted(set(minimums) - set(REQUIRED_FROZEN_METRICS))
    if unknown:
        raise ValueError(f"{role_id}: unknown metric(s) in frozen thresholds: {unknown}")
    return FrozenThresholds(
        contract_version=EVAL_CONTRACT_VERSION,
        role_id=role_id,
        metrics=REQUIRED_FROZEN_METRICS,
        minimums=tuple(sorted(minimums.items())),
    )


def contract_for_role(role_id: str) -> PromptEvaluationContract:
    """Current posture for a role: active prompt only, no candidate, nothing run live."""
    from app.llm.policy.registry import contract_for
    from app.llm.policy.templates import stable_prefix_hash

    role = contract_for(role_id)
    return PromptEvaluationContract(
        role_id=role_id,
        active=PromptArm(
            template_id=role.prompt_template_id,
            version=role.prompt_version,
            stable_prefix_hash=stable_prefix_hash(role_id),
        ),
        candidate=None,
        eval_status="NOT_RUN_LIVE",
        thresholds=None,
    )
