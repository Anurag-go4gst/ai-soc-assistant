"""Curated SOP/policy seed for the investigation lifecycle (architecture P12).

Content only. It flows through the **existing** ``KnowledgeRepository`` import
draft/publish path so governed retrieval keeps producing ``SourceEvidence`` — there
is no new ingestion pipeline and no direct RAG-to-LLM path.

The five documents cover the gaps the investigation scenarios hit: a never-seen-before
external endpoint, firewall blocking, zero-day response, emergency change, and Cisco
hardening. Every runtime entry carries a ``source_excerpt`` and citation, because the
importer refuses runtime entries without one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

SEED_BATCH_ID = "investigation-sop-seed-v1"
SEED_COLLECTION_ID = "soc_sop"

_NOW = "2026-08-21T00:00:00Z"


def _document(
    *,
    doc_id: str,
    title: str,
    document_type: str,
    namespace: str,
    tags: list[str],
    allowed_use: list[str],
) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "canonical_doc_id": doc_id,
        "collection_id": SEED_COLLECTION_ID,
        "title": title,
        "document_type": document_type,
        "namespace": namespace,
        "domain": "soc_operations",
        "environment": "coe",
        "version": "1.0",
        "revision": "1",
        "status": "published",
        "approval_status": "coe_reviewed",
        "lifecycle_stage": "published",
        "is_current_version": True,
        "allowed_use": allowed_use,
        "applies_to_skills": ["guided_investigation", "knowledge_recall", "attack_discovery"],
        "risk_level": "medium",
        "sensitivity": "internal",
        "tags": tags,
        "owner": "COE SOC Operations",
        "uploaded_by": "coe.seed",
        "reviewed_by": "coe.soc",
        "approved_by": "coe.soc",
        "created_at": _NOW,
        "updated_at": _NOW,
        "reviewed_at": _NOW,
        "approved_at": _NOW,
        "retrieval_backend": "deterministic",
    }


def _entry(
    *,
    entry_id: str,
    doc_id: str,
    title: str,
    section_id: str,
    excerpt: str,
    citation: str,
    hints: list[str],
    constraints: list[str],
) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "doc_id": doc_id,
        "doc_version": "1.0",
        "collection_id": SEED_COLLECTION_ID,
        "title": title,
        "section_id": section_id,
        "section_title": title,
        "entry_type": "procedure",
        "source_excerpt": excerpt,
        "source_refs": [f"{doc_id}.md#{section_id}"],
        "citation": citation,
        "retrieval_hints": hints,
        "synonyms": [],
        "positive_examples": hints[:3],
        "negative_examples": [],
        "answer_constraints": constraints,
        "allowed_use": ["hil_guidance", "synthesis_context"],
        "status": "published",
        "approval_status": "coe_reviewed",
        "risk_level": "medium",
        "retrieval_backend": "deterministic",
    }


SEED_DOCUMENTS: list[dict[str, Any]] = [
    _document(
        doc_id="coe-new-external-endpoint-sop-v1",
        title="New External / MCP Endpoint Monitoring SOP",
        document_type="sop",
        namespace="network",
        tags=["external", "new endpoint", "egress", "beaconing"],
        allowed_use=["hil_guidance", "synthesis_context", "environment_grounding"],
    ),
    _document(
        doc_id="coe-firewall-blocking-sop-v1",
        title="Firewall Blocking SOP",
        document_type="sop",
        namespace="network",
        tags=["firewall", "block", "containment"],
        allowed_use=["hil_guidance", "synthesis_context"],
    ),
    _document(
        doc_id="coe-zero-day-response-sop-v1",
        title="Zero-Day Response SOP",
        document_type="playbook",
        namespace="vulnerability",
        tags=["zero-day", "cve", "exploitation"],
        allowed_use=["hil_guidance", "synthesis_context"],
    ),
    _document(
        doc_id="coe-emergency-change-procedure-v1",
        title="Emergency Change Procedure",
        document_type="sop",
        namespace="change_management",
        tags=["emergency change", "cab", "approval"],
        allowed_use=["hil_guidance", "synthesis_context"],
    ),
    _document(
        doc_id="coe-cisco-hardening-policy-v1",
        title="Cisco Hardening Policy",
        document_type="asset_policy",
        namespace="infrastructure",
        tags=["cisco", "hardening", "baseline"],
        allowed_use=["hil_guidance", "synthesis_context", "asset_context"],
    ),
]


SEED_ENTRIES: list[dict[str, Any]] = [
    _entry(
        entry_id="coe-new-external-endpoint-triage",
        doc_id="coe-new-external-endpoint-sop-v1",
        title="Triaging a never-before-seen external endpoint",
        section_id="EXT-001",
        excerpt=(
            "For a first-seen external destination, establish the internal initiator, the "
            "process or service responsible, the volume and periodicity of the traffic, and "
            "whether any peer host contacted the same destination, before assigning intent."
        ),
        citation="New External / MCP Endpoint Monitoring SOP v1.0 EXT-001",
        hints=[
            "new external ip",
            "never seen before destination",
            "first seen endpoint",
            "unknown external address",
        ],
        constraints=[
            "A first-seen destination is not by itself evidence of compromise.",
            "Do not assign intent without initiator and periodicity evidence.",
        ],
    ),
    _entry(
        entry_id="coe-new-external-endpoint-escalation",
        doc_id="coe-new-external-endpoint-sop-v1",
        title="Escalation thresholds for external endpoint activity",
        section_id="EXT-002",
        excerpt=(
            "Escalate when the destination is contacted on a fixed interval, when the "
            "initiating process is not an approved egress client, or when more than one "
            "internal host contacts the destination within the same window."
        ),
        citation="New External / MCP Endpoint Monitoring SOP v1.0 EXT-002",
        hints=["escalate external traffic", "beaconing interval", "multiple hosts same destination"],
        constraints=["State which threshold was met; do not generalize from one observation."],
    ),
    _entry(
        entry_id="coe-firewall-block-preconditions",
        doc_id="coe-firewall-blocking-sop-v1",
        title="Preconditions before requesting a firewall block",
        section_id="FW-001",
        excerpt=(
            "Before requesting a block, confirm the indicator is not shared infrastructure, "
            "record the business impact of the block, identify a rollback owner, and obtain "
            "explicit approval. Blocks are never applied directly from an investigation."
        ),
        citation="Firewall Blocking SOP v1.0 FW-001",
        hints=["block the ip", "firewall block request", "deny traffic"],
        constraints=[
            "A block requires explicit approval and a named rollback owner.",
            "Never describe a block as applied unless a verified receipt exists.",
        ],
    ),
    _entry(
        entry_id="coe-zero-day-exposure-assessment",
        doc_id="coe-zero-day-response-sop-v1",
        title="Assessing exposure to a newly announced vulnerability",
        section_id="ZD-001",
        excerpt=(
            "Determine affected product versions in the estate, whether the vulnerable "
            "component is reachable from untrusted networks, and whether any telemetry "
            "matches published exploitation indicators. Absence of matching telemetry is "
            "not proof the estate was not exploited."
        ),
        citation="Zero-Day Response SOP v1.0 ZD-001",
        hints=["zero day", "newly announced cve", "are we exploited", "vulnerability exposure"],
        constraints=[
            "Absence of evidence is reported as inconclusive, never as benign.",
            "Do not claim patch status without an authoritative inventory source.",
        ],
    ),
    _entry(
        entry_id="coe-emergency-change-approval",
        doc_id="coe-emergency-change-procedure-v1",
        title="Emergency change approval path",
        section_id="EC-001",
        excerpt=(
            "An emergency change requires an incident reference, a named approver, a "
            "documented rollback, and post-implementation review within one business day. "
            "Retrospective approval does not replace the named approver."
        ),
        citation="Emergency Change Procedure v1.0 EC-001",
        hints=["emergency change", "out of band change", "urgent patch approval"],
        constraints=["Name the approver and the rollback; never imply self-approval."],
    ),
    _entry(
        entry_id="coe-cisco-hardening-baseline",
        doc_id="coe-cisco-hardening-policy-v1",
        title="Cisco device hardening baseline",
        section_id="CIS-001",
        excerpt=(
            "Management interfaces are restricted to the management VLAN, unused services "
            "are disabled, local accounts are individually attributable, and configuration "
            "changes are logged to the central collector."
        ),
        citation="Cisco Hardening Policy v1.0 CIS-001",
        hints=["cisco hardening", "device baseline", "management vlan restriction"],
        constraints=["Cite the baseline clause; do not infer device state from policy text."],
    ),
]


def seed_batch() -> dict[str, Any]:
    return {
        "import_batch_id": SEED_BATCH_ID,
        "collection_id": SEED_COLLECTION_ID,
        "environment": "coe",
        "status": "ready_for_review",
        "source": "curated_investigation_sop_seed",
        "uploaded_by": "coe.seed",
        "created_at": _NOW,
        "updated_at": datetime.now(UTC).isoformat(),
    }
