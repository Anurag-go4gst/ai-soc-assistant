from __future__ import annotations

from typing import Any

from app.cve.evidence_adapter import vulnerability_source_from_evidence


def structure_context(
    *,
    query: str,
    trace_id: str,
    selected_skill: str,
    workflow_plan: dict[str, Any],
    spl_validation: dict[str, Any] | None,
    execution: dict[str, Any],
    source_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    collected = [item for item in source_evidence if item.get("collection_status") == "collected"]
    blocked = any(item.get("collection_status") in {"blocked", "requires_human_review"} for item in source_evidence)
    required_sources = list(workflow_plan.get("required_sources") or [])
    available_sources = [_source_ref(item) for item in collected]
    missing_evidence = _missing_evidence(required_sources, available_sources, source_evidence)
    facts = _structured_facts(collected)
    warnings = _warnings(source_evidence, spl_validation, execution)

    context_quality = "blocked" if blocked else "partial" if collected else "insufficient"
    if collected and not missing_evidence and not warnings:
        context_quality = "partial"

    return {
        "trace_id": trace_id,
        "query": query,
        "selected_skill": selected_skill,
        "source_evidence_refs": [str(item["evidence_id"]) for item in source_evidence],
        "structured_facts": facts,
        "entity_summary": _entity_summary(collected),
        "metrics": _metrics(collected),
        "timeline_candidates": _timeline_candidates(collected),
        "mitre_candidates": _mitre_candidates(collected),
        "tool_outputs_summary": _tool_outputs_summary(source_evidence),
        "capability_profile_ref": _capability_profile_ref(spl_validation),
        "spl_generation_provider": _provider(spl_validation, "selected_candidate_spl_provider"),
        "spl_explanation_provider": _provider(spl_validation, "spl_explanation_provider"),
        "spl_optimization_provider": _provider(spl_validation, "spl_optimization_provider"),
        "spl_guidance_provider": _provider(spl_validation, "spl_guidance_provider"),
        "fallback_mode": bool(spl_validation and spl_validation.get("fallback_required")),
        "execution_provider": execution.get("selected_mcp_tool"),
        "source_refs": [str(item["evidence_id"]) for item in source_evidence],
        "policy_context_refs": _policy_context_refs(spl_validation) + _rag_refs(collected, {"procedure", "rule", "escalation", "answer_constraint"}),
        "sop_action_hints": _sop_action_hints(collected),
        "answer_constraints": _rag_list(collected, "answer_constraints"),
        "prohibited_conclusions": [
            "final_soc_answer",
            "final_mitre_mapping",
            "root_cause",
            "incident_severity",
            *_rag_list(collected, "prohibited_conclusions"),
        ],
        "mitre_grounding_refs": _rag_refs(collected, {"mitre_mapping"}),
        "splunk_context_refs": _rag_refs(collected, {"environment_fact", "spl_guidance"}),
        "tool_policy_refs": _rag_refs(collected, {"tool_policy"}),
        "environment_grounding_refs": _rag_refs(collected, {"environment_fact", "asset_policy"}),
        "knowledge_ambiguity": _knowledge_ambiguity(source_evidence),
        "validation_warnings": _validation_warnings(source_evidence),
        "assumptions": ["structured_context_is_pre_synthesis"],
        "warnings": warnings,
        "missing_evidence": missing_evidence,
        "allowed_conclusions": ["source_coverage_and_collection_status_only"],
        "context_quality": context_quality,
        "synthesis_allowed": False,
        "rag_approval_summary": _rag_approval_summary(source_evidence),
        "evidence_origin_labels": _evidence_origin_labels(source_evidence),
        "vulnerability_source": vulnerability_source_from_evidence(source_evidence),
    }


def _structured_facts(collected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for index, evidence in enumerate(collected, start=1):
        evidence_id = str(evidence["evidence_id"])
        facts.append(
            {
                "fact_id": f"fact_{index:03d}",
                "statement": _fact_statement(evidence),
                "source_refs": [evidence_id],
                "derivation": "computed_by_ai_soc",
                "confidence": 1.0,
            }
        )
        for field in evidence.get("fields_returned", [])[:8]:
            facts.append(
                {
                    "fact_id": f"fact_{index:03d}_{field}",
                    "statement": f"Field observed in source preview: {field}.",
                    "source_refs": [evidence_id],
                    "derivation": "computed_by_ai_soc",
                    "confidence": 1.0,
                }
            )
    return facts


def _fact_statement(evidence: dict[str, Any]) -> str:
    if evidence.get("source_type") == "rag":
        return f"{evidence.get('source_name')} returned {evidence.get('result_count', 0)} governed SOC KB entries through governed retrieval."
    return f"{evidence.get('source_name')} returned {evidence.get('result_count', 0)} previewable rows through {evidence.get('tool_name') or 'unknown tool'}."


def _entity_summary(collected: list[dict[str, Any]]) -> dict[str, Any]:
    entities: dict[str, list[Any]] = {}
    for evidence in collected:
        for row in evidence.get("preview_rows", []):
            if not isinstance(row, dict):
                continue
            for key in ("user", "src", "dest", "host", "sourcetype"):
                if key in row and row[key] not in entities.setdefault(key, []):
                    entities[key].append(row[key])
    return {key: values[:10] for key, values in entities.items()}


def _metrics(collected: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "collected_evidence_count": len(collected),
        "total_result_count": sum(int(item.get("result_count") or 0) for item in collected),
    }


def _timeline_candidates(collected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for evidence in collected:
        for row in evidence.get("preview_rows", []):
            if isinstance(row, dict) and "_time" in row:
                candidates.append({"time": row["_time"], "source_refs": [evidence["evidence_id"]], "derivation": "computed_by_ai_soc"})
    return candidates[:10]


def _tool_outputs_summary(source_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_ref": item["evidence_id"],
            "source_type": item["source_type"],
            "source_name": item["source_name"],
            "tool_name": item.get("tool_name"),
            "collection_status": item["collection_status"],
            "result_count": item.get("result_count", 0),
            "fields_returned": item.get("fields_returned", []),
            "warnings": item.get("warnings", []),
        }
        for item in source_evidence
    ]


def _policy_context_refs(spl_validation: dict[str, Any] | None) -> list[str]:
    if not spl_validation:
        return []
    policy_version = spl_validation.get("policy_version")
    return [str(policy_version)] if policy_version else []


def _warnings(source_evidence: list[dict[str, Any]], spl_validation: dict[str, Any] | None, execution: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for evidence in source_evidence:
        warnings.extend(str(item) for item in evidence.get("warnings", []))
        warnings.extend(str(item) for item in evidence.get("sensitivity_flags", []))
        if evidence.get("source_type") == "rag" and evidence.get("collection_status") == "ambiguous":
            warnings.append("knowledge_ambiguity_requires_review")
    if spl_validation and spl_validation.get("reject_reasons"):
        warnings.extend(str(item) for item in spl_validation["reject_reasons"])
    if execution.get("block_reason"):
        warnings.append(str(execution["block_reason"]))
    if spl_validation and spl_validation.get("fallback_required"):
        warnings.append("Splunk AI Assistant tools unavailable; AI-SOC fallback provider used.")
    return sorted(set(warnings))


def _source_ref(evidence: dict[str, Any]) -> str:
    if evidence.get("source_type") in {"mcp", "splunk_mcp", "mcp_discovery"}:
        return "mcp:splunk"
    if evidence.get("source_type") == "rag":
        return "rag:sop"
    return str(evidence.get("source_type"))


def _provider(spl_validation: dict[str, Any] | None, key: str) -> str | None:
    if not spl_validation:
        return None
    value = spl_validation.get(key)
    return str(value) if value else None


def _capability_profile_ref(spl_validation: dict[str, Any] | None) -> str | None:
    profile = (spl_validation or {}).get("capability_profile") or {}
    if isinstance(profile, dict) and profile.get("server_id"):
        return f"splunk_capability:{profile['server_id']}"
    return None


def _missing_evidence(required_sources: list[str], available_sources: list[str], evidence: list[dict[str, Any]]) -> list[str]:
    missing = [source for source in required_sources if source not in available_sources]
    if "rag:sop" in required_sources and not _has_approved_sop(evidence):
        missing.append("approved_sop_guidance")
    if not any(item.get("collection_status") == "collected" for item in evidence):
        missing.append("collected_source_evidence")
    return sorted(set(missing))


def _has_approved_sop(evidence: list[dict[str, Any]]) -> bool:
    for item in evidence:
        if item.get("source_type") != "rag" or item.get("collection_status") != "collected":
            continue
        for row in item.get("preview_rows", []):
            if isinstance(row, dict) and row.get("document_type") in {"sop", "runbook"}:
                return True
    return False


def _rag_rows(collected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for evidence in collected:
        if evidence.get("source_type") != "rag":
            continue
        rows.extend(row for row in evidence.get("preview_rows", []) if isinstance(row, dict))
    return rows


def _rag_refs(collected: list[dict[str, Any]], entry_types: set[str]) -> list[str]:
    refs: list[str] = []
    for row in _rag_rows(collected):
        if row.get("entry_type") in entry_types or _doc_type_maps(row, entry_types):
            ref = str(row.get("citation") or row.get("entry_id") or "")
            if ref and ref not in refs:
                refs.append(ref)
    return refs


def _doc_type_maps(row: dict[str, Any], entry_types: set[str]) -> bool:
    doc_type = row.get("document_type")
    return (
        ("mitre_mapping" in entry_types and doc_type in {"mitre_enterprise_reference", "mitre_ics_reference"})
        or ("environment_fact" in entry_types and doc_type == "splunk_context_document")
        or ("tool_policy" in entry_types and doc_type == "mcp_tool_policy")
        or ("procedure" in entry_types and doc_type in {"sop", "runbook", "escalation_matrix"})
    )


def _rag_list(collected: list[dict[str, Any]], key: str) -> list[str]:
    values: list[str] = []
    for row in _rag_rows(collected):
        for item in row.get(key) or []:
            text = str(item)
            if text not in values:
                values.append(text)
    return values


def _sop_action_hints(collected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for row in _rag_rows(collected):
        if row.get("document_type") not in {"sop", "runbook", "escalation_matrix"}:
            continue
        hints.append(
            {
                "sop_reference": row.get("citation"),
                "sop_excerpt": row.get("source_excerpt"),
                "reviewer_role": row.get("reviewer_role"),
                "recommended_actions": row.get("recommended_actions") or [],
            }
        )
    return hints


def _knowledge_ambiguity(source_evidence: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for item in source_evidence:
        if item.get("source_type") == "rag" and item.get("collection_status") == "ambiguous":
            values.append("Knowledge retrieval is ambiguous and requires analyst review.")
    return values


def _validation_warnings(source_evidence: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for row in _rag_rows([item for item in source_evidence if item.get("collection_status") == "collected"]):
        if row.get("validation_status") and row.get("validation_status") != "runtime_eligible":
            values.append(str(row["validation_status"]))
    for item in source_evidence:
        for warning in item.get("warnings") or []:
            if "validation" in str(warning):
                values.append(str(warning))
    return sorted(set(values))


def _rag_approval_summary(source_evidence: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in source_evidence:
        if item.get("source_type") == "rag":
            summary = item.get("rag_approval_summary")
            if isinstance(summary, dict):
                return dict(summary)
    return None


def _evidence_origin_labels(source_evidence: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for item in source_evidence:
        origin = item.get("evidence_origin")
        if isinstance(origin, str) and origin.strip() and origin not in labels:
            labels.append(origin.strip())
    return labels


def _mitre_candidates(collected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in _rag_rows(collected):
        for mitre_ref in row.get("mitre_refs") or []:
            candidates.append({"technique_id": mitre_ref, "source_refs": [row.get("citation")], "derivation": "governed_soc_kb"})
    return candidates[:10]
