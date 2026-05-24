from __future__ import annotations

from typing import Any

from app.config import settings

# Governed SOC KB JSON shape the external LLM must emit. Kept in sync with the
# fields enforced by ``app.knowledge.validation``.
KB_JSON_SCHEMA_SKELETON = {
    "import_batch": {
        "source_file_name": "<original file name>",
        "source_type": "pdf|text|json",
        "target_collection_id": "<collection_id>",
        "environment": "<environment>",
        "generated_by": "llm_extraction",
        "status": "ready_for_review",
        "checksum_sha256": "<source file sha256 or null>",
    },
    "documents": [
        {
            "doc_id": "<stable id>",
            "canonical_doc_id": "<canonical id>",
            "collection_id": "<collection_id>",
            "title": "<document title>",
            "document_type": "sop|playbook|splunk_context_document|detection_engineering_note|mitre_enterprise_reference|mitre_ics_reference|escalation_matrix|asset_policy|mcp_tool_policy|customer_context|runbook|other",
            "version": "<version string>",
            "revision": "<revision or null>",
            "status": "draft",
            "approval_status": "draft",
            "environment": "<environment>",
            "allowed_use": ["synthesis_context"],
            "risk_level": "low|medium|high|critical",
            "effective_from": "<iso8601 or null>",
            "effective_to": "<iso8601 or null>",
        }
    ],
    "entries": [
        {
            "entry_id": "<stable id>",
            "doc_id": "<parent doc_id>",
            "collection_id": "<collection_id>",
            "title": "<entry title>",
            "entry_type": "procedure|rule|escalation|answer_constraint|mitre_mapping|environment_fact|spl_guidance|tool_policy|asset_policy",
            "status": "draft",
            "approval_status": "draft",
            "allowed_use": ["synthesis_context"],
            "risk_level": "low|medium|high|critical",
            "source_excerpt": "<verbatim text from source>",
            "source_refs": ["<page/section/url>"],
            "citation": "<human-readable citation or null>",
            "answer_constraints": ["<constraint>"],
            "positive_examples": ["<example query>"],
            "negative_examples": ["<counter-example query>"],
            "test_cases": [{"query": "<query>", "expected": "<expected behavior>"}],
            "needs_human_review": True,
        }
    ],
}


def build_extraction_prompt(
    *,
    collection_id: str | None = None,
    document_type: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """Build the offline LLM extraction prompt for governed SOC KB import.

    The returned prompt is downloaded/copied by an admin and run against an
    external LLM together with the source document. The LLM is told to emit
    governed-schema JSON only and is explicitly forbidden from inventing policy,
    fields, citations, or sources. Output is draft-only until human publish.
    """
    env = environment or settings.soc_kb_environment
    target_collection = collection_id or "<collection_id>"
    target_doc_type = document_type or "<document_type>"

    rules = [
        "Return valid JSON only. No prose, no markdown, no code fences.",
        "Do not invent rules, policy, fields, citations, or sources.",
        "If the source does not contain a field, use null or omit it. Never fabricate a value.",
        "Preserve source excerpts verbatim in `source_excerpt`; do not paraphrase policy text.",
        "Every entry must cite where it came from in `source_refs`.",
        "Set every document and entry `status` to draft or ready_for_review and `approval_status` to draft.",
        "High-risk and critical entries MUST include source_excerpt, source_refs, positive_examples, and test_cases.",
        "Mark any uncertain or low-confidence entry with `needs_human_review: true`.",
        "Do not assign runtime/approved statuses; a human reviews and publishes.",
        f"Target collection_id is `{target_collection}`, document_type `{target_doc_type}`, environment `{env}`.",
    ]

    prompt_text = (
        "You are an offline SOC knowledge extraction assistant. Convert the SOURCE DOCUMENT below "
        "into governed SOC knowledge-base JSON for human review. You do not retrieve, browse, or "
        "invent information; you only restructure what the source already states.\n\n"
        "RULES:\n"
        + "\n".join(f"- {rule}" for rule in rules)
        + "\n\nEMIT JSON MATCHING THIS SHAPE (replace placeholders, omit unknown fields):\n"
        + _schema_text()
        + "\n\nSOURCE DOCUMENT:\n<paste source document text here>\n"
    )

    return {
        "prompt": prompt_text,
        "schema": KB_JSON_SCHEMA_SKELETON,
        "rules": rules,
        "target_collection_id": target_collection,
        "document_type": target_doc_type,
        "environment": env,
        "runtime_use": False,
        "generated_by": "llm_extraction",
        "drafts_affect_runtime": False,
    }


def _schema_text() -> str:
    import json

    return json.dumps(KB_JSON_SCHEMA_SKELETON, indent=2)
