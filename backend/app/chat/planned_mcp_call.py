"""Governed planned MCP call contracts for harness continuity.

Populates InvestigationCapabilityBinding with purpose, argument templates,
bound planned arguments, and unresolved bindings derived from the playbook
and (when present) approved normalized SPL. Packaging only — no MCP I/O.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.chat.contracts.investigation_plan import InvestigationCapabilityBinding
from app.connectors.mcp.splunk_mcp_readiness import splunk_search_tool_arguments

_PLAYBOOK_PATH = Path(__file__).resolve().parents[1] / "connectors" / "mcp" / "mcp_tool_playbook.json"

# Keys the execution gate binds for splunk_run_query (must match AUTH0 hashing).
_SPLUNK_RUN_QUERY_TEMPLATE: dict[str, str] = {
    "search_query": "<normalized_spl>",
    "earliest_time": "<from_normalized_spl_or_policy_default>",
    "latest_time": "<from_normalized_spl_or_policy_default>",
    "max_results": "<policy_max_result_limit>",
}

_METADATA_TEMPLATES: dict[str, dict[str, str]] = {
    "splunk_get_info": {},
    "get_indexes": {},
    "splunk_get_indexes": {},
    "get_metadata": {"index": "<candidate_index>"},
    "splunk_get_metadata": {"index": "<candidate_index>"},
    "get_index_info": {"index": "<candidate_index>"},
    "splunk_get_index_info": {"index": "<candidate_index>"},
    "get_knowledge_objects": {"index": "<candidate_index_or_app>"},
    "splunk_get_knowledge_objects": {"index": "<candidate_index_or_app>"},
    "get_user_info": {},
    "get_kv_store_collections": {},
}


@lru_cache(maxsize=1)
def _playbook_tools() -> dict[str, Any]:
    try:
        payload = json.loads(_PLAYBOOK_PATH.read_text(encoding="utf-8"))
    except OSError:
        return {}
    tools = payload.get("tools") if isinstance(payload, dict) else None
    return tools if isinstance(tools, dict) else {}


def parse_mcp_capability_id(capability_id: str) -> tuple[str | None, str | None]:
    parts = str(capability_id or "").split(":")
    if len(parts) != 3 or parts[0] != "mcp":
        return None, None
    server = parts[1].strip() or None
    tool = parts[2].strip() or None
    return server, tool


def playbook_purpose(tool_name: str | None) -> str | None:
    if not tool_name:
        return None
    entry = _playbook_tools().get(tool_name)
    if not isinstance(entry, dict):
        # Accept alias without splunk_ prefix.
        entry = _playbook_tools().get(f"splunk_{tool_name}")
    if not isinstance(entry, dict):
        return None
    why = str(entry.get("why") or "").strip()
    when = str(entry.get("when") or "").strip()
    if why and when:
        return f"{why} ({when})"
    return why or when or None


def argument_template_for_tool(tool_name: str | None) -> dict[str, Any] | None:
    if not tool_name:
        return None
    if tool_name in {"splunk_run_query", "run_splunk_query"}:
        return dict(_SPLUNK_RUN_QUERY_TEMPLATE)
    if tool_name in _METADATA_TEMPLATES:
        return dict(_METADATA_TEMPLATES[tool_name])
    aliased = f"splunk_{tool_name}" if not tool_name.startswith("splunk_") else tool_name
    if aliased in _METADATA_TEMPLATES:
        return dict(_METADATA_TEMPLATES[aliased])
    entry = _playbook_tools().get(tool_name) or _playbook_tools().get(aliased)
    if isinstance(entry, dict) and entry.get("read_only") is True:
        return {}
    return None


def read_write_classification(tool_name: str | None) -> str:
    if tool_name in {"splunk_run_query", "run_splunk_query", "splunk_run_saved_search"}:
        return "execution_gated"
    return "read_only"


def enrich_capability_binding(
    binding: InvestigationCapabilityBinding,
    *,
    normalized_spl: str | None = None,
    trace_id: str | None = None,
    index_hint: str | None = None,
) -> InvestigationCapabilityBinding:
    """Fill purpose/templates/planned args on an existing binding (immutable copy)."""
    server, tool = parse_mcp_capability_id(binding.capability_id)
    purpose = binding.purpose or playbook_purpose(tool)
    template = binding.argument_template
    if template is None:
        template = argument_template_for_tool(tool)
    planned = binding.planned_arguments
    unresolved = list(binding.unresolved_arguments or [])
    rw = binding.read_write_classification or read_write_classification(tool)

    if tool in {"splunk_run_query", "run_splunk_query"}:
        if normalized_spl and str(normalized_spl).strip():
            planned = splunk_search_tool_arguments(
                normalized_spl=str(normalized_spl).strip(),
                trace_id=trace_id,
            )
            unresolved = []
        else:
            planned = None
            unresolved = ["search_query", "normalized_spl"]
    elif tool and template is not None and planned is None:
        # Metadata: bind known hints only; leave placeholders unresolved.
        bound: dict[str, Any] = {}
        unresolved = []
        for key, placeholder in template.items():
            if key == "index" and index_hint:
                bound[key] = index_hint
            else:
                unresolved.append(key)
        planned = bound if bound else None

    return binding.model_copy(
        update={
            "purpose": purpose,
            "argument_template": template,
            "planned_arguments": planned,
            "unresolved_arguments": unresolved,
            "read_write_classification": rw,
            "authorization_posture": binding.authorization_posture
            or "exact_call_auth0_grant_required",
        }
    )


def enrich_capability_bindings(
    bindings: list[InvestigationCapabilityBinding],
    *,
    normalized_spl: str | None = None,
    trace_id: str | None = None,
    index_hint: str | None = None,
) -> list[InvestigationCapabilityBinding]:
    return [
        enrich_capability_binding(
            item,
            normalized_spl=normalized_spl,
            trace_id=trace_id,
            index_hint=index_hint,
        )
        for item in bindings
    ]


def planned_arguments_hash(planned_arguments: dict[str, Any] | None) -> str:
    """Stable hash matching AUTH0 canonical_arguments_hash input encoding."""
    import hashlib

    if not planned_arguments:
        return ""
    canonical_args = json.dumps(planned_arguments, sort_keys=True, default=str)
    return hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()
