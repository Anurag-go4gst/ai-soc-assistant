"""Experience Center SIEM-first investigation projection. /demo only — not production authority."""

from __future__ import annotations

from typing import Any, Literal

from app.demo.ec_response import (
    EcAttackChainStep,
    EcDetectionOpportunity,
    EcEvidenceFindingRow,
    EcSiemCoverageAssessment,
    EcSiemCoverageRow,
    EcSiemExistingContent,
    EcSiemGeneratedSearch,
    EcSiemToolTrace,
)
from app.safeguards.spl_validator import validate_spl

# ---------------------------------------------------------------------------
# I0 — Verified Splunk MCP inventory (from repo config/registry, not assumed live)
# ---------------------------------------------------------------------------

SAIA_TOOL_NAMES = frozenset(
    {
        "saia_generate_spl",
        "saia_explain_spl",
        "saia_optimize_spl",
        "saia_ask_splunk_question",
    }
)

VERIFIED_SPLUNK_READ_TOOLS = frozenset(
    {
        "splunk_run_query",
        "run_splunk_query",
        "search_splunk",
        "splunk.search",
        "splunk_get_info",
        "splunk_get_indexes",
        "splunk_get_index_info",
        "splunk_get_metadata",
        "get_splunk_metadata",
        "splunk_get_user_info",
        "splunk_get_knowledge_objects",
    }
)

CONDITIONAL_SPLUNK_TOOLS = frozenset({"splunk_run_saved_search"})

NONEXISTENT_TOOLS = frozenset({"find_data_source"})

SPLUNK_MCP_AUDIT_ROWS: list[dict[str, str]] = [
    {
        "capability": "Knowledge-object discovery",
        "tool": "splunk_get_knowledge_objects",
        "available": "configured",
        "allowlist": "SPLUNK_ALLOWED_CORE_TOOLS / MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST",
        "use": "Discover approved detections and saved searches before generating SPL",
    },
    {
        "capability": "Saved-search execution",
        "tool": "splunk_run_saved_search",
        "available": "conditional (splunk_allow_run_saved_search)",
        "allowlist": "not in default core allowlist; gated per deployment",
        "use": "Replay approved saved searches when coverage is partial or full",
    },
    {
        "capability": "Governed arbitrary SPL execution",
        "tool": "splunk_run_query",
        "available": "configured",
        "allowlist": "yes (canonical search tool)",
        "use": "Execute only authorized normalized_spl for evidence gaps",
    },
    {
        "capability": "Index list",
        "tool": "splunk_get_indexes",
        "available": "configured",
        "allowlist": "yes",
        "use": "Check SIEM data availability",
    },
    {
        "capability": "Index information",
        "tool": "splunk_get_index_info",
        "available": "configured",
        "allowlist": "yes",
        "use": "Scope gap searches to available indexes",
    },
    {
        "capability": "Metadata / sourcetype discovery",
        "tool": "splunk_get_metadata",
        "available": "configured",
        "allowlist": "yes",
        "use": "Identify tool-audit, DLP, and identity sourcetypes",
    },
    {
        "capability": "Splunk server identity",
        "tool": "splunk_get_info",
        "available": "configured",
        "allowlist": "yes",
        "use": "SIEM context (read-only)",
    },
    {
        "capability": "Data-source finder",
        "tool": "find_data_source",
        "available": "no",
        "allowlist": "—",
        "use": "Not exposed in this environment — do not model",
    },
    {
        "capability": "SAIA SPL generation",
        "tool": "saia_generate_spl",
        "available": "blocked",
        "allowlist": "discoverable but saia_conditional_blocked",
        "use": "Not used — AI SOC owns candidate SPL generation",
    },
]


def ec_verified_splunk_tools_for_projection() -> list[str]:
    """Tools EC may name in Layer 2 traces — verified registry surface only."""
    return sorted(VERIFIED_SPLUNK_READ_TOOLS | CONDITIONAL_SPLUNK_TOOLS)


def assert_no_saia_in_projection(payload: dict[str, Any]) -> None:
    blob = str(payload).lower()
    for name in SAIA_TOOL_NAMES:
        if name in blob:
            raise ValueError(f"saia_tool_in_ec_projection:{name}")


# ---------------------------------------------------------------------------
# S2 — governed gap SPL (validator read-only; never sent to MCP from EC)
# ---------------------------------------------------------------------------

S2_DETECTION_NAME = "AI Assistant — Prompt Injection Attempt"
S2_SAVED_SEARCH_NAME = "EC_AI_Prompt_Injection_Detection"
S2_GAP_CANDIDATE_SPL = (
    "search index=pgcil_soc sourcetype=pgcil:edr earliest=-24h latest=now "
    "tool_name=export_customer_records "
    "| stats count values(authorized) as authorized values(executed) as executed "
    "by session_id tool_name "
    "| head 100"
)


def s2_gap_spl_validation() -> dict[str, Any]:
    return validate_spl(S2_GAP_CANDIDATE_SPL)


def build_s2_attack_chain() -> list[EcAttackChainStep]:
    return [
        EcAttackChainStep(label="Prompt injection", status="confirmed", detail="Gateway indicators observed"),
        EcAttackChainStep(
            label="Sensitive tool requested",
            status="confirmed",
            detail="export_customer_records",
        ),
        EcAttackChainStep(label="Authorization", status="denied", detail="Tool authorization denied"),
        EcAttackChainStep(label="Execution receipt", status="none_observed", detail="No successful execution receipt"),
        EcAttackChainStep(label="Restricted-data access", status="not_confirmed", detail="Data audit incomplete"),
    ]


def build_s2_evidence_findings() -> list[EcEvidenceFindingRow]:
    return [
        EcEvidenceFindingRow(
            investigation_point="Prompt manipulation",
            finding="Confirmed",
            evidence_basis="Existing Splunk detection + gateway events",
        ),
        EcEvidenceFindingRow(
            investigation_point="Sensitive tool requested",
            finding="Confirmed",
            evidence_basis="Tool-call audit",
        ),
        EcEvidenceFindingRow(
            investigation_point="Authorization",
            finding="Blocked",
            evidence_basis="Authorization decision",
        ),
        EcEvidenceFindingRow(
            investigation_point="Successful execution",
            finding="Not observed",
            evidence_basis="No successful execution receipt",
        ),
        EcEvidenceFindingRow(
            investigation_point="Restricted data accessed",
            finding="Not confirmed",
            evidence_basis="Data audit incomplete",
        ),
        EcEvidenceFindingRow(
            investigation_point="Session compromise",
            finding="Not confirmed",
            evidence_basis="Identity evidence pending",
        ),
    ]


def build_s2_tool_traces(*, gap_validation: dict[str, Any]) -> list[EcSiemToolTrace]:
    normalized = gap_validation.get("normalized_spl")
    return [
        EcSiemToolTrace(
            purpose="Discover existing SOC content",
            capability="Splunk knowledge objects",
            mcp_tool="splunk_get_knowledge_objects",
            mode="READ",
            provenance="simulated_mcp",
        ),
        EcSiemToolTrace(
            purpose="Execute approved saved search",
            capability="Prompt-injection detection",
            mcp_tool="splunk_run_saved_search",
            mode="READ",
            detail=f"saved_search={S2_SAVED_SEARCH_NAME}",
            provenance="simulated_mcp",
        ),
        EcSiemToolTrace(
            purpose="Resolve successful-tool-execution evidence gap",
            capability="Governed SPL search",
            mcp_tool="splunk_run_query",
            mode="READ",
            candidate_spl=S2_GAP_CANDIDATE_SPL,
            normalized_spl=normalized,
            validator_status="PASS" if gap_validation.get("approved") else "FAIL",
            exact_call_authorization="APPROVED" if gap_validation.get("approved") else "BLOCKED",
            provenance="simulated_mcp",
        ),
    ]


def build_s2_siem_coverage(*, dlp_obtained: bool = False) -> EcSiemCoverageAssessment:
    rows = [
        EcSiemCoverageRow(
            investigation_need="Prompt injection",
            siem_status="Existing detection",
            decision="Reused",
        ),
        EcSiemCoverageRow(
            investigation_need="Sensitive tool request",
            siem_status="Existing/partial",
            decision="Correlated",
        ),
        EcSiemCoverageRow(
            investigation_need="Successful tool execution",
            siem_status="Coverage gap",
            decision="Governed search",
        ),
        EcSiemCoverageRow(
            investigation_need="Restricted-data access",
            siem_status="Incomplete",
            decision="Follow-up evidence",
        ),
        EcSiemCoverageRow(
            investigation_need="Identity/session",
            siem_status="Available, not queried",
            decision="Follow-up",
        ),
        EcSiemCoverageRow(
            investigation_need="DLP",
            siem_status="Available" if not dlp_obtained else "Reviewed",
            decision="Follow-up" if not dlp_obtained else "Reused search",
        ),
    ]
    gap_validation = s2_gap_spl_validation()
    return EcSiemCoverageAssessment(
        siem="Splunk",
        coverage_status="PARTIAL",
        existing_content=[
            EcSiemExistingContent(
                object_type="detection",
                name=S2_DETECTION_NAME,
                status="existing",
                purpose="Prompt/gateway prompt-injection indicators",
                coverage="PARTIAL",
                reused=True,
                execution_ref=f"saved_search:{S2_SAVED_SEARCH_NAME}",
            ),
        ],
        required_evidence=[
            {
                "evidence_id": "q1_prompt_injection",
                "question": "Were prompt-injection attacks attempted?",
                "coverage": "PARTIAL",
                "source_status": "reused_detection",
                "resolution": "Confirmed via existing detection replay",
            },
            {
                "evidence_id": "q2_tool_execution",
                "question": "Did any attempt lead to unauthorized tool execution?",
                "coverage": "GAP",
                "source_status": "gap_search_required",
                "resolution": "Governed tool-audit search — blocked, not executed",
            },
            {
                "evidence_id": "q3_restricted_data",
                "question": "Did any attempt result in restricted-data access?",
                "coverage": "NONE",
                "source_status": "incomplete",
                "resolution": "Follow-up datastore / DLP evidence required",
            },
        ],
        generated_searches=[
            EcSiemGeneratedSearch(
                evidence_requirement="Successful unauthorized tool execution",
                candidate_created=True,
                validator_status="PASS" if gap_validation.get("approved") else "FAIL",
                normalized=bool(gap_validation.get("normalized_spl")),
                execution_authorized=bool(gap_validation.get("approved")),
                source_evidence_ids=["ev-s2-tool"],
            ),
        ],
        remaining_gaps=[
            "Restricted customer-data access not established",
            "DLP window not fully correlated unless follow-up applied",
            "Identity/session context optional follow-up",
        ],
        coverage_rows=rows,
    )


def build_s2_detection_opportunity() -> EcDetectionOpportunity:
    return EcDetectionOpportunity(
        status="PREPARED",
        title="Detection opportunity identified",
        summary=(
            "No approved detection currently correlates prompt-injection indicators with "
            "sensitive AI-tool authorization outcomes."
        ),
        recommended_action="Create detection candidate",
        deploy_status="not_deployed",
        notes="Recommendation only — no automatic Splunk write in Experience Center.",
    )


S2_LAYER2_PATH = [
    "Understanding",
    "SIEM coverage discovery",
    "Existing detection/search found",
    "Coverage evaluation",
    "Existing evidence reused",
    "Evidence gaps identified",
    "SIEM data availability checked",
    "Governed SPL generated only for gaps",
    "SPL validation",
    "Splunk MCP execution",
    "SourceEvidence",
    "Evidence sufficiency",
    "InvestigationOutcome",
]
