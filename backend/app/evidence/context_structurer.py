from __future__ import annotations

from typing import Any


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
        "mitre_candidates": [],
        "tool_outputs_summary": _tool_outputs_summary(source_evidence),
        "policy_context_refs": _policy_context_refs(spl_validation),
        "assumptions": ["structured_context_is_pre_synthesis"],
        "warnings": warnings,
        "missing_evidence": missing_evidence,
        "allowed_conclusions": ["source_coverage_and_collection_status_only"],
        "prohibited_conclusions": [
            "final_soc_answer",
            "final_mitre_mapping",
            "root_cause",
            "incident_severity",
        ],
        "context_quality": context_quality,
        "synthesis_allowed": False,
    }


def _structured_facts(collected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for index, evidence in enumerate(collected, start=1):
        evidence_id = str(evidence["evidence_id"])
        facts.append(
            {
                "fact_id": f"fact_{index:03d}",
                "statement": f"{evidence.get('source_name')} returned {evidence.get('result_count', 0)} previewable rows through {evidence.get('tool_name') or 'unknown tool'}.",
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
    if spl_validation and spl_validation.get("reject_reasons"):
        warnings.extend(str(item) for item in spl_validation["reject_reasons"])
    if execution.get("block_reason"):
        warnings.append(str(execution["block_reason"]))
    return sorted(set(warnings))


def _source_ref(evidence: dict[str, Any]) -> str:
    if evidence.get("source_type") == "mcp":
        return "mcp:splunk"
    return str(evidence.get("source_type"))


def _missing_evidence(required_sources: list[str], available_sources: list[str], evidence: list[dict[str, Any]]) -> list[str]:
    missing = [source for source in required_sources if source not in available_sources]
    if not any(item.get("collection_status") == "collected" for item in evidence):
        missing.append("collected_source_evidence")
    return sorted(set(missing))
