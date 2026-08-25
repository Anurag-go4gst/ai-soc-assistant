"""P4 PP6 — active-versus-candidate evaluation contract self-tests.

The contract's whole job is to refuse promotion without live evidence. These tests
mostly prove it refuses.
"""

from __future__ import annotations

import pytest

from app.llm.policy.evaluation import (
    ACTIVATION_REQUIREMENTS,
    EVAL_CONTRACT_VERSION,
    REQUIRED_FROZEN_METRICS,
    FrozenThresholds,
    PromotionRefused,
    PromptArm,
    PromptEvaluationContract,
    contract_for_role,
    freeze_thresholds,
)
from app.llm.policy.registry import ROLE_CONTRACTS

_MINIMUMS = {name: 0.0 for name in REQUIRED_FROZEN_METRICS}


def _arm(tag: str) -> PromptArm:
    return PromptArm(template_id=f"tmpl.{tag}", version="1.0.0", stable_prefix_hash=f"hash-{tag}")


def _contract(**over) -> PromptEvaluationContract:
    base = dict(
        role_id="probe",
        active=_arm("active"),
        candidate=_arm("candidate"),
        eval_status="LIVE_AB_COMPLETE",
        thresholds=freeze_thresholds("probe", _MINIMUMS),
        satisfied_requirements=ACTIVATION_REQUIREMENTS,
    )
    base.update(over)
    return PromptEvaluationContract(**base)


def test_contract_version_is_declared() -> None:
    assert EVAL_CONTRACT_VERSION == "prompt_ab_eval_contract_v1"


# --- current posture: nothing has been run live -----------------------------


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_every_role_starts_with_no_candidate_and_no_live_run(role_id: str) -> None:
    contract = contract_for_role(role_id)
    assert contract.candidate is None
    assert contract.eval_status == "NOT_RUN_LIVE"
    assert contract.thresholds is None


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_active_arm_is_bound_to_the_real_prompt(role_id: str) -> None:
    contract = contract_for_role(role_id)
    assert contract.active.template_id
    assert contract.active.version
    assert len(contract.active.stable_prefix_hash) == 64


@pytest.mark.parametrize("role_id", sorted(ROLE_CONTRACTS))
def test_no_role_can_be_activated_today(role_id: str) -> None:
    allowed, reason = contract_for_role(role_id).can_activate()
    assert allowed is False
    assert reason == "no_candidate_prompt"


# --- the gate refuses without live evidence ---------------------------------


def test_deterministic_tests_passing_is_not_promotion_evidence() -> None:
    """The load-bearing refusal: schema-valid is not better."""
    allowed, reason = _contract(eval_status="DETERMINISTIC_ONLY").can_activate()
    assert allowed is False
    assert reason == "live_ab_not_complete:DETERMINISTIC_ONLY"


@pytest.mark.parametrize(
    "status", ["NOT_RUN_LIVE", "DETERMINISTIC_ONLY", "LIVE_AB_IN_PROGRESS", "BLOCKED_INFRASTRUCTURE"]
)
def test_only_a_completed_live_ab_permits_activation(status: str) -> None:
    allowed, _ = _contract(eval_status=status).can_activate()
    assert allowed is False


def test_activation_refused_without_frozen_thresholds() -> None:
    allowed, reason = _contract(thresholds=None).can_activate()
    assert allowed is False
    assert reason == "thresholds_never_frozen"


@pytest.mark.parametrize("dropped", ACTIVATION_REQUIREMENTS)
def test_every_activation_requirement_is_load_bearing(dropped: str) -> None:
    remaining = tuple(r for r in ACTIVATION_REQUIREMENTS if r != dropped)
    allowed, reason = _contract(satisfied_requirements=remaining).can_activate()
    assert allowed is False
    assert dropped in reason


def test_activate_or_raise_refuses_loudly() -> None:
    with pytest.raises(PromotionRefused, match="no_candidate_prompt"):
        _contract(candidate=None).activate_or_raise()


def test_fully_evidenced_candidate_is_permitted() -> None:
    """The gate must be satisfiable, or it would just be a wall."""
    allowed, reason = _contract().can_activate()
    assert allowed is True
    assert reason == "activation_requirements_satisfied"


# --- thresholds are frozen up front, completely ------------------------------


def test_freezing_requires_every_metric() -> None:
    partial = {k: 0.0 for k in list(REQUIRED_FROZEN_METRICS)[:-1]}
    with pytest.raises(ValueError, match="missing"):
        freeze_thresholds("probe", partial)


def test_freezing_rejects_an_invented_metric() -> None:
    """A metric added after results are visible is how an A/B gets talked into a win."""
    with pytest.raises(ValueError, match="unknown metric"):
        freeze_thresholds("probe", {**_MINIMUMS, "vibes": 1.0})


def test_frozen_thresholds_are_immutable() -> None:
    frozen = freeze_thresholds("probe", _MINIMUMS)
    with pytest.raises(Exception):
        frozen.minimums = ()  # type: ignore[misc]
    assert isinstance(frozen, FrozenThresholds)


def test_frozen_thresholds_cover_the_named_metric_set() -> None:
    frozen = freeze_thresholds("probe", _MINIMUMS)
    assert set(frozen.metric_names()) == set(REQUIRED_FROZEN_METRICS)


def test_required_metrics_include_semantic_and_cost_axes() -> None:
    for required in (
        "semantic_correctness",
        "schema_validity",
        "repair_rate",
        "semantic_loss_rate",
        "invented_constraint_rate",
        "latency_p95_ms",
        "input_tokens",
        "provider_cache_hit_rate",
    ):
        assert required in REQUIRED_FROZEN_METRICS


# --- infrastructure failures are separated from semantic results -------------


def test_infrastructure_notes_are_separate_from_metrics() -> None:
    contract = _contract(
        eval_status="BLOCKED_INFRASTRUCTURE",
        infrastructure_notes=("local model endpoint unreachable",),
    )
    allowed, reason = contract.can_activate()
    assert allowed is False
    assert "BLOCKED_INFRASTRUCTURE" in reason
    assert contract.infrastructure_notes  # recorded, never scored


def test_blocked_infrastructure_is_not_a_semantic_loss() -> None:
    """An unreachable endpoint must not read as the candidate performing badly."""
    contract = _contract(eval_status="BLOCKED_INFRASTRUCTURE")
    assert contract.unmet_requirements() == ()
    assert contract.can_activate()[0] is False
