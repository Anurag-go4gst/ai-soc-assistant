from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ProviderType(StrEnum):
    SPLUNK_MCP = "splunk_mcp"
    GENERIC_MCP = "generic_mcp"
    SECURITY_API = "security_api"
    NETWORK_API = "network_api"
    ASSET_INVENTORY = "asset_inventory"
    TICKETING = "ticketing"
    RAG_KNOWLEDGE = "rag_knowledge"
    MANUAL_INPUT = "manual_input"


class ProviderOperationCategory(StrEnum):
    DISCOVERY = "discovery"
    CONTEXT_LOOKUP = "context_lookup"
    EVENT_QUERY = "event_query"
    ASSET_LOOKUP = "asset_lookup"
    IDENTITY_LOOKUP = "identity_lookup"
    TICKET_LOOKUP = "ticket_lookup"
    CANDIDATE_GENERATION = "candidate_generation"
    EXPLANATION = "explanation"
    OPTIMIZATION = "optimization"
    EXECUTION = "execution"
    WRITE_ACTION = "write_action"
    ADMIN_ACTION = "admin_action"


class ProviderCapabilityProfile(BaseModel):
    provider_id: str
    provider_type: ProviderType
    available: bool
    environment_mode: str
    auth_configured: bool
    discovered_operations: list[ProviderOperationCategory] = Field(default_factory=list)
    allowed_operations: list[ProviderOperationCategory] = Field(default_factory=list)
    blocked_operations: list[ProviderOperationCategory] = Field(default_factory=list)
    read_only_supported: bool = True
    write_supported: bool = False
    hil_required_operations: list[ProviderOperationCategory] = Field(default_factory=list)
    evidence_output_supported: bool = True
    fallback_required: bool = False
    warnings: list[str] = Field(default_factory=list)


class ProviderPolicyDecision(BaseModel):
    allowed: bool
    reason: str
    hil_required: bool = False
    provider_id: str
    operation: ProviderOperationCategory


class ProviderOperationResult(BaseModel):
    status: str
    provider_id: str
    provider_type: ProviderType
    operation: ProviderOperationCategory
    source_evidence: dict[str, object] | None = None
    human_review: dict[str, object] | None = None
    reason: str | None = None
