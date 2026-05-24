from __future__ import annotations

from app.providers.base import ProviderCapabilityProfile, ProviderOperationCategory, ProviderType
from app.splunk.capabilities import SplunkCapabilityProfile


def splunk_provider_profile(profile: SplunkCapabilityProfile) -> ProviderCapabilityProfile:
    discovered: list[ProviderOperationCategory] = []
    allowed: list[ProviderOperationCategory] = []
    blocked: list[ProviderOperationCategory] = [ProviderOperationCategory.WRITE_ACTION, ProviderOperationCategory.ADMIN_ACTION]

    if profile.run_query_available:
        discovered.append(ProviderOperationCategory.EVENT_QUERY)
        allowed.append(ProviderOperationCategory.EVENT_QUERY)
        discovered.append(ProviderOperationCategory.EXECUTION)
        allowed.append(ProviderOperationCategory.EXECUTION)
    if profile.get_indexes_available or profile.get_metadata_available or profile.get_info_available:
        discovered.append(ProviderOperationCategory.DISCOVERY)
        discovered.append(ProviderOperationCategory.CONTEXT_LOOKUP)
        allowed.extend([ProviderOperationCategory.DISCOVERY, ProviderOperationCategory.CONTEXT_LOOKUP])
    if profile.saia_generate_spl_available:
        discovered.append(ProviderOperationCategory.CANDIDATE_GENERATION)
        if profile.saia_usable:
            allowed.append(ProviderOperationCategory.CANDIDATE_GENERATION)
    if profile.saia_explain_spl_available:
        discovered.append(ProviderOperationCategory.EXPLANATION)
        if profile.saia_usable:
            allowed.append(ProviderOperationCategory.EXPLANATION)
    if profile.saia_optimize_spl_available:
        discovered.append(ProviderOperationCategory.OPTIMIZATION)
        if profile.saia_usable:
            allowed.append(ProviderOperationCategory.OPTIMIZATION)
    if profile.run_saved_search_available and not profile.run_saved_search_allowed:
        blocked.append(ProviderOperationCategory.EXECUTION)

    return ProviderCapabilityProfile(
        provider_id=profile.server_id,
        provider_type=ProviderType.SPLUNK_MCP,
        available=profile.mcp_available,
        environment_mode=profile.environment_mode,
        auth_configured=profile.authenticated_user_available or profile.mcp_available,
        discovered_operations=_unique(discovered),
        allowed_operations=_unique(allowed),
        blocked_operations=_unique(blocked),
        read_only_supported=True,
        write_supported=False,
        hil_required_operations=[ProviderOperationCategory.EXECUTION] if profile.run_saved_search_requires_hil else [],
        evidence_output_supported=True,
        fallback_required=profile.fallback_required,
        warnings=list(profile.warnings),
    )


def _unique(items: list[ProviderOperationCategory]) -> list[ProviderOperationCategory]:
    values: list[ProviderOperationCategory] = []
    for item in items:
        if item not in values:
            values.append(item)
    return values
