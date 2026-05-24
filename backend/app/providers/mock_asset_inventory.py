from __future__ import annotations

from typing import Any

from app.config import settings
from app.evidence.source_evidence import build_provider_source_evidence
from app.orchestration.human_review import human_review
from app.providers.base import ProviderCapabilityProfile, ProviderOperationCategory, ProviderOperationResult, ProviderType
from app.providers.policy import check_provider_operation_policy

MOCK_ASSET_PROVIDER_ID = "mock_asset_inventory"


def mock_asset_inventory_profile(*, hil_required: bool = False, available: bool = True) -> ProviderCapabilityProfile:
    hil_operations = [ProviderOperationCategory.ASSET_LOOKUP] if hil_required else []
    return ProviderCapabilityProfile(
        provider_id=MOCK_ASSET_PROVIDER_ID,
        provider_type=ProviderType.ASSET_INVENTORY,
        available=available,
        environment_mode=settings.ai_soc_environment_mode,
        auth_configured=True,
        discovered_operations=[ProviderOperationCategory.ASSET_LOOKUP],
        allowed_operations=[ProviderOperationCategory.ASSET_LOOKUP],
        blocked_operations=[ProviderOperationCategory.WRITE_ACTION, ProviderOperationCategory.ADMIN_ACTION],
        read_only_supported=True,
        write_supported=False,
        hil_required_operations=hil_operations,
        evidence_output_supported=True,
        fallback_required=False,
        warnings=["mock_provider_no_external_api"],
    )


def run_mock_asset_lookup(
    *,
    trace_id: str,
    query: str,
    profile: ProviderCapabilityProfile | None = None,
    hil_approved: bool = False,
) -> ProviderOperationResult:
    profile = profile or mock_asset_inventory_profile()
    operation = ProviderOperationCategory.ASSET_LOOKUP
    decision = check_provider_operation_policy(profile, operation, hil_approved=hil_approved)
    if not decision.allowed:
        review = None
        if decision.hil_required:
            review = human_review(
                "provider_operation_review",
                decision.reason,
                "soc_lead",
                ["approve_provider_lookup", "reject_provider_lookup"],
                "Provider lookup requires human review before it can proceed.",
            )
        return ProviderOperationResult(
            status="requires_human_review" if decision.hil_required else "blocked",
            provider_id=profile.provider_id,
            provider_type=profile.provider_type,
            operation=operation,
            source_evidence=None,
            human_review=review,
            reason=decision.reason,
        )

    rows = [_mock_asset_row(query)]
    evidence = build_provider_source_evidence(
        trace_id=trace_id,
        source_type="asset_inventory",
        source_name=profile.provider_id,
        tool_name="mock_asset_lookup",
        collection_status="collected",
        query_or_request_summary=query,
        result_count=len(rows),
        preview_rows=rows,
        provider_used=profile.provider_id,
        tool_category=operation.value,
        provenance="mock_provider_stage3i",
        warnings=list(profile.warnings),
    )
    return ProviderOperationResult(
        status="collected",
        provider_id=profile.provider_id,
        provider_type=profile.provider_type,
        operation=operation,
        source_evidence=evidence,
        human_review=None,
        reason=decision.reason,
    )


def _mock_asset_row(query: str) -> dict[str, Any]:
    host = query.strip() or "unknown-host"
    return {
        "asset_id": f"mock-{host.lower().replace(' ', '-')[:40]}",
        "host": host[:80],
        "business_unit": "mock-soc-lab",
        "criticality": "medium",
        "source": "mock_asset_inventory",
    }
