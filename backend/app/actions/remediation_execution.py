"""Deterministic remediation action gate (architecture P11).

Executes only what an :class:`ApprovedRemediationEnvelope` authorized, through a
registered connector, and then verifies. The structure is intentionally open:
onboarding Agilius / SOAR / a firewall / ITSM later means registering an adapter
here, not writing a second execution graph.

Invariants this module exists to hold:

* execution is bound to one approved envelope version and one plan fingerprint —
  a re-planned or edited plan cannot ride an older approval;
* a capability with no registered adapter is ``UNAVAILABLE``, never ``SUCCESS``;
* the investigation PlanDelta path cannot reach this module — only an approved
  remediation envelope can;
* every attempt yields a receipt, including refusals, so nothing is silent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable

from app.chat.contracts.remediation_plan import (
    ApprovedRemediationEnvelope,
    RemediationStep,
)
from app.chat.canonical_execution_idempotency import (
    AcquireOutcome,
    ExecutionIdempotencyError,
    run_idempotent_execution_step,
)

#: Terminal statuses. ``UNAVAILABLE`` is a first-class outcome, not an error.
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_SKIPPED_MANUAL = "SKIPPED_MANUAL"


@dataclass
class ActionReceipt:
    step_id: str
    capability_id: str
    status: str
    execution_mode: str
    external_side_effect: bool = False
    idempotency_key: str = ""
    reason: str | None = None
    verification_status: str = "not_attempted"
    verification_detail: str | None = None
    provider_message_id: str | None = None
    replayed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "capability_id": self.capability_id,
            "status": self.status,
            "execution_mode": self.execution_mode,
            "external_side_effect": self.external_side_effect,
            "idempotency_key": self.idempotency_key,
            "reason": self.reason,
            "verification_status": self.verification_status,
            "verification_detail": self.verification_detail,
            "provider_message_id": self.provider_message_id,
            "replayed": self.replayed,
        }


@dataclass
class RemediationExecutionResult:
    envelope_version: int
    plan_fingerprint: str
    receipts: list[ActionReceipt] = field(default_factory=list)
    refused_reason: str | None = None

    @property
    def executed_any(self) -> bool:
        return any(receipt.status == STATUS_SUCCESS for receipt in self.receipts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "envelope_version": self.envelope_version,
            "plan_fingerprint": self.plan_fingerprint,
            "refused_reason": self.refused_reason,
            "receipts": [receipt.as_dict() for receipt in self.receipts],
            "executed_any": self.executed_any,
        }


def idempotency_key_for(envelope: ApprovedRemediationEnvelope, step: RemediationStep) -> str:
    """Stable per (approved plan, step). Re-approving an edited plan changes it."""
    raw = f"{envelope.plan_fingerprint}:{envelope.envelope_version}:{step.step_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _execute_email(
    step: RemediationStep,
    *,
    envelope: ApprovedRemediationEnvelope,
    context: dict[str, Any],
) -> ActionReceipt:
    from app.actions.email_adapter import send_remediation_email

    key = str(context.get("downstream_idempotency_key") or "").strip() or idempotency_key_for(
        envelope, step
    )
    recipient = str(step.action_arguments.get("recipient") or "").strip()
    supplied_recipient = str(context.get("recipient") or "").strip()
    if supplied_recipient and supplied_recipient != recipient:
        return ActionReceipt(
            step_id=step.step_id,
            capability_id=step.capability_id,
            status=STATUS_FAILED,
            execution_mode="not_attempted",
            idempotency_key=key,
            reason="action_arguments_do_not_match_approved_plan",
        )
    if not recipient:
        return ActionReceipt(
            step_id=step.step_id,
            capability_id=step.capability_id,
            status=STATUS_FAILED,
            execution_mode="not_attempted",
            idempotency_key=key,
            reason="no_recipient_supplied",
        )
    receipt = send_remediation_email(
        to=recipient,
        subject=f"[AI-SOC] Remediation: {envelope.remediation_objective}"[:200],
        body=(
            f"Approved remediation step {step.step_id}.\n\n"
            f"Objective: {envelope.remediation_objective}\n"
            f"Action: {step.description}\n"
            f"Verification: {step.verification}\n"
            f"Approved envelope version: {envelope.envelope_version}\n"
        ),
        idempotency_key=key,
    )
    return ActionReceipt(
        step_id=step.step_id,
        capability_id=step.capability_id,
        status=receipt.status,
        execution_mode=receipt.execution_mode,
        external_side_effect=receipt.external_side_effect,
        idempotency_key=key,
        reason=receipt.reason,
        provider_message_id=receipt.provider_message_id,
    )


#: Capability id -> adapter. Onboarding a connector adds a row here plus its own
#: registry/allowlist entry; it does not change the lifecycle above.
ADAPTERS: dict[str, Callable[..., ActionReceipt]] = {
    "email_send": _execute_email,
}

_ACTION_EXECUTION_ROLES = frozenset(
    {"admin", "analyst", "demo_analyst", "soc_analyst", "soc_lead"}
)


def _verify(receipt: ActionReceipt, step: RemediationStep) -> ActionReceipt:
    """Post-action verification. An unverifiable success is reported as such."""
    if receipt.status != STATUS_SUCCESS:
        receipt.verification_status = "not_applicable"
        return receipt
    if receipt.capability_id == "email_send":
        verified = bool(receipt.provider_message_id)
        receipt.verification_status = "verified" if verified else "unverified"
        receipt.verification_detail = (
            f"Provider accepted message id {receipt.provider_message_id}."
            if verified
            else "Send reported success without a provider message id."
        )
        return receipt
    receipt.verification_status = "unverified"
    receipt.verification_detail = step.verification
    return receipt


def execute_approved_remediation(
    *,
    approved_envelope: dict[str, Any] | ApprovedRemediationEnvelope,
    current_plan_fingerprint: str | None = None,
    context: dict[str, Any] | None = None,
) -> RemediationExecutionResult:
    """Execute an approved remediation envelope; verify each executed step.

    ``current_plan_fingerprint`` guards against executing a stale approval after the
    analyst edited the plan: a mismatch refuses the whole envelope rather than
    executing a subset the analyst never approved.
    """
    envelope = (
        approved_envelope
        if isinstance(approved_envelope, ApprovedRemediationEnvelope)
        else ApprovedRemediationEnvelope.model_validate(approved_envelope)
    )
    result = RemediationExecutionResult(
        envelope_version=envelope.envelope_version,
        plan_fingerprint=envelope.plan_fingerprint,
    )
    if current_plan_fingerprint and current_plan_fingerprint != envelope.plan_fingerprint:
        result.refused_reason = "approved_plan_superseded"
        return result

    call_context = dict(context or {})
    role = str(call_context.get("rbac_role") or "demo_analyst").strip()
    if role not in _ACTION_EXECUTION_ROLES:
        result.refused_reason = f"rbac_denied:{role or 'unknown'}"
        return result
    for step in envelope.approved_steps:
        key = idempotency_key_for(envelope, step)
        if step.execution_mode != "execute":
            result.receipts.append(
                ActionReceipt(
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    status=STATUS_SKIPPED_MANUAL,
                    execution_mode="manual_or_alternate",
                    idempotency_key=key,
                    reason=step.unavailable_reason or "manual_step",
                )
            )
            continue
        adapter = ADAPTERS.get(step.capability_id)
        if adapter is None:
            result.receipts.append(
                ActionReceipt(
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    status=STATUS_UNAVAILABLE,
                    execution_mode="no_registered_connector",
                    idempotency_key=key,
                    reason="capability_has_no_registered_adapter",
                )
            )
            continue
        def _execute_once(*, downstream_idempotency_key: str | None = None) -> dict[str, Any]:
            adapter_context = {
                **call_context,
                "downstream_idempotency_key": downstream_idempotency_key,
            }
            return _verify(
                adapter(step, envelope=envelope, context=adapter_context), step
            ).as_dict()

        try:
            outcome, stored = run_idempotent_execution_step(
                resource_plan_id=f"remediation:{envelope.plan_fingerprint}",
                step_id=step.step_id,
                operation=f"action:{step.capability_id}",
                handoff_id=None,
                handoff_version=envelope.envelope_version,
                side_effecting=True,
                lease_owner=role,
                execute=_execute_once,
                operation_contract=(
                    "side_effecting_with_stable_idempotency"
                    if step.capability_id == "email_send"
                    else "side_effecting_without_stable_idempotency"
                ),
            )
        except ExecutionIdempotencyError as exc:
            result.receipts.append(
                ActionReceipt(
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    status=STATUS_FAILED,
                    execution_mode="not_attempted",
                    idempotency_key=key,
                    reason=exc.reason,
                )
            )
            continue
        if outcome in {AcquireOutcome.IN_PROGRESS, AcquireOutcome.REQUIRES_RECONCILIATION}:
            result.receipts.append(
                ActionReceipt(
                    step_id=step.step_id,
                    capability_id=step.capability_id,
                    status=STATUS_FAILED,
                    execution_mode="not_attempted",
                    idempotency_key=key,
                    reason=str(stored.get("reason") or outcome.value),
                )
            )
            continue
        receipt = ActionReceipt(**stored)
        if outcome == AcquireOutcome.REPLAY:
            receipt.replayed = True
        result.receipts.append(receipt)
    return result
