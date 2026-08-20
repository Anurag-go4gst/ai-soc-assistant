"""EC-only SOC-KB fixture: Newly Observed External / MCP Endpoint Monitoring and Blocking SOP.

Not vendor guidance. Not ingested into production SOC-KB. Experience Center only.
"""

from __future__ import annotations

from typing import Any

from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP

SOP_DOC_ID = "SOC-SOP-NEW-EXT-MCP-001"
SOP_TITLE = "Newly Observed External / MCP Endpoint Monitoring and Blocking SOP"
SOP_OWNER = "Enterprise SOC — Detection & Response"


SOP_SECTIONS: tuple[dict[str, str], ...] = (
    {
        "heading": "Investigation requirements",
        "body": (
            "Before monitoring or containment: (1) replay existing IOC-based content; "
            "(2) search the requested window plus a prior novelty window; "
            "(3) identify destination systems, ports/services, allow vs deny, and session timing; "
            "(4) investigate every permitted session with authentication correlation if those logs exist; "
            "(5) check local IOC / TI evidence; (6) establish inventory identity before labelling an MCP endpoint."
        ),
    },
    {
        "heading": "Monitoring criteria",
        "body": (
            "Raise targeted monitoring when an external IP is newly observed, is unlisted in local IOC/TI, "
            "and existing IOC-based notables do not cover the indicator — especially newly registered MCP endpoints."
        ),
    },
    {
        "heading": "Monitoring duration",
        "body": (
            "Default targeted monitoring window is 14 days from notable/draft approval, or until identity is "
            "accepted as expected business traffic and residual allows cease — whichever is later."
        ),
    },
    {
        "heading": "Escalation thresholds",
        "body": (
            "Escalate to Network/SOC lead when: permitted sessions grow, authentication becomes attributable "
            "to the indicator, unexpected services appear, or follow-on internal activity is observed."
        ),
    },
    {
        "heading": "When monitoring alone is appropriate",
        "body": (
            "Monitoring without a block is the default when malicious use is not confirmed, permitted sessions "
            "are few and unexplained, and no SOP blocking threshold is met."
        ),
    },
    {
        "heading": "Conditions that justify preparing a block",
        "body": (
            "Prepare a conditional IP block (HIL) when permitted sessions require Network review, even if the "
            "block is not yet authorized. Preparing a request is not executing a change."
        ),
    },
    {
        "heading": "Conditions requiring HIL / Network approval",
        "body": (
            "Execute a firewall/SOAR block only after Network/SOC approval when at least one blocking threshold "
            "is met: confirmed malicious use; successful authentication attributable to the IP plus unexpected "
            "MCP behaviour; confirmed follow-on lateral movement; or an explicit policy exception denial."
        ),
    },
    {
        "heading": "Change / incident requirements",
        "body": (
            "Open or update an incident with confirmed vs unconfirmed evidence before containment. "
            "A block, if approved, requires a change record; monitoring drafts do not."
        ),
    },
    {
        "heading": "Block verification",
        "body": (
            "After an approved block executes, verify the simulated/enforced rule against the indicator "
            "and confirm residual allows drop. Do not mark verification complete if the block was not executed."
        ),
    },
    {
        "heading": "Rollback / unblock conditions",
        "body": (
            "Unblock only with Network approval if identity is confirmed expected MCP traffic and residual "
            "risk is accepted, or if the block caused a documented business outage."
        ),
    },
    {
        "heading": "Post-action monitoring",
        "body": (
            "After monitoring is raised — and after any block — continue watching the indicator and affected "
            "internal systems for residual allows or new destinations for the remainder of the 14-day window."
        ),
    },
    {
        "heading": "Incident update requirements",
        "body": (
            "Update the incident with identity, local TI result, permitted-session validation, SOP decision "
            "(monitor vs block), and final verification. Do not close as malicious without confirmatory evidence."
        ),
    },
)


def sop_excerpt_for_indicator(indicator: str = PRIMARY_ATTACKER_IP) -> str:
    return (
        f"{SOP_TITLE} ({SOP_DOC_ID}) applies to newly observed external indicator {indicator}. "
        "Default action is targeted monitoring for 14 days. Blocking requires a defined behavioural "
        "or policy threshold plus Network/SOC HIL approval. Unlisted in local IOC/TI is not benign; "
        "a notable that does not fire is not proof the indicator is safe."
    )


def sop_source_evidence() -> dict[str, Any]:
    rows = [
        {
            "doc_id": SOP_DOC_ID,
            "title": SOP_TITLE,
            "owner": SOP_OWNER,
            "heading": section["heading"],
            "excerpt": section["body"],
        }
        for section in SOP_SECTIONS
    ]
    return {
        "evidence_id": "ev-s1-sop-rag",
        "trace_id": "pending",
        "source_type": "rag",
        "source_name": SOP_TITLE,
        "tool_name": "retrieve_soc_kb",
        "collection_status": "collected",
        "query_or_request_summary": (
            "Governed SOC-KB retrieval: newly observed external / MCP endpoint monitoring and blocking SOP"
        ),
        "result_count": len(rows),
        "fields_returned": ["doc_id", "title", "owner", "heading", "excerpt"],
        "preview_rows": rows,
        "provenance": "experience_center_fixture",
        "provider_used": "governed_rag_fixture",
        "warnings": ["coe_synthetic_fixture", "ec_only_not_production_soc_kb"],
        "output_type": "fixture_preview",
        "sensitivity_flags": [],
    }
