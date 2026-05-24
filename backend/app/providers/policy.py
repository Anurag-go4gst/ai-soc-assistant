from __future__ import annotations

from app.providers.base import ProviderCapabilityProfile, ProviderOperationCategory, ProviderPolicyDecision

DEFAULT_BLOCKED_OPERATIONS = {
    ProviderOperationCategory.WRITE_ACTION,
    ProviderOperationCategory.ADMIN_ACTION,
}


def check_provider_operation_policy(
    profile: ProviderCapabilityProfile,
    operation: ProviderOperationCategory,
    *,
    hil_approved: bool = False,
) -> ProviderPolicyDecision:
    if not profile.available:
        return _decision(profile, operation, False, "provider_unavailable")
    if operation in profile.blocked_operations or operation in DEFAULT_BLOCKED_OPERATIONS:
        return _decision(profile, operation, False, "operation_blocked_by_policy")
    if operation not in profile.allowed_operations:
        return _decision(profile, operation, False, "operation_not_allowed")
    if operation in profile.hil_required_operations and not hil_approved:
        return _decision(profile, operation, False, "human_review_required", hil_required=True)
    if not profile.evidence_output_supported:
        return _decision(profile, operation, False, "source_evidence_required")
    return _decision(profile, operation, True, "provider_policy_allowed")


def _decision(
    profile: ProviderCapabilityProfile,
    operation: ProviderOperationCategory,
    allowed: bool,
    reason: str,
    *,
    hil_required: bool = False,
) -> ProviderPolicyDecision:
    return ProviderPolicyDecision(
        allowed=allowed,
        reason=reason,
        hil_required=hil_required,
        provider_id=profile.provider_id,
        operation=operation,
    )
