"""WS-F — deterministic grounding assembly for guided-hunt / T2 rescue paths.

Wires ``assemble_grounding()`` into the live ``guided_investigation`` pipeline.
The blocking answer stays deterministic review-only guidance; this module only
supplies advisory context for trace surfaces and weak-case LLM composition.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from app.chat.grounding_assembler import GroundingBlock, assemble_grounding
from app.threat.attack_data_resolver import technique_resolver_from_settings
from app.use_cases.content_enrichment import content_enrichment_records

T2_UNVERIFIED_BANNER = (
    "Out-of-catalogue, review-only — validate against local telemetry and policy."
)
T2_LLM_ASSISTED_BANNER = (
    "LLM-assisted, out-of-catalogue, unverified — validate against local telemetry and policy."
)
_T2_UNVERIFIED_BANNER = T2_UNVERIFIED_BANNER  # backwards-compatible private alias

_DETECTION_FAMILY_SIGNALS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("dns", "beacon", "domain"), "dns_beaconing_candidate"),
    (("powershell", "encoded", "lolbin"), "edr_powershell_suspicious_command"),
    (("login", "auth", "brute", "credential"), "auth_failed_login_spike"),
    (("lateral", "rdp", "smb"), "lateral_movement_review"),
    (("exfil", "egress", "upload"), "network_exfil_volume"),
    (("llm", "model", "prompt injection", "mcp"), "ai_threat_hunt"),
)


@lru_cache(maxsize=1)
def _skill_register_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for use_case_id, record in content_enrichment_records().items():
        refs = record.get("github_reference_skills")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            path = str(ref.get("path") or "").strip()
            if not path:
                continue
            skill_id = Path(path).parent.name if "/" in path else path
            rows.append(
                {
                    "github_skill_id": skill_id,
                    "internal_use_cases": [use_case_id],
                }
            )
    return rows


def soc_kb_refs_from_retrieval(soc_kb_retrieval: dict[str, Any] | None) -> list[str]:
    """Refs-only SOC-KB pointers (entry_id / title) — not raw chunk bodies."""
    if not isinstance(soc_kb_retrieval, dict):
        return []
    refs: list[str] = []
    for entry in soc_kb_retrieval.get("retrieved_entries") or []:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("entry_id") or entry.get("doc_id") or "").strip()
        title = str(entry.get("title") or entry.get("heading") or "").strip()
        if entry_id and title:
            refs.append(f"{entry_id}:{title[:120]}")
        elif entry_id:
            refs.append(entry_id)
        elif title:
            refs.append(title[:120])
    return refs[:8]


def skill_refs_for_question(query: str) -> list[str]:
    """Deterministic github-skill register matches (metadata refs only)."""
    normalized = " ".join((query or "").lower().split())
    if not normalized:
        return []
    matches: list[str] = []
    for record in _skill_register_records():
        skill_id = str(record.get("github_skill_id") or "")
        if not skill_id:
            continue
        phrase = skill_id.replace("-", " ")
        if phrase in normalized or any(token in normalized for token in phrase.split() if len(token) > 4):
            matches.append(f"github_skill:{skill_id}")
            continue
        for use_case in record.get("internal_use_cases") or []:
            uc = str(use_case).replace("_", " ")
            if uc in normalized:
                matches.append(f"github_skill:{skill_id}")
                break
    return sorted(set(matches))[:6]


def detection_families_for_question(query: str) -> list[str]:
    lowered = " ".join((query or "").lower().split())
    families: list[str] = []
    for keywords, family in _DETECTION_FAMILY_SIGNALS:
        if any(keyword in lowered for keyword in keywords):
            families.append(family)
    return families[:6]


def enterprise_mitre_refs_from_contract(answer_contract: Any | None) -> list[str]:
    if answer_contract is None:
        return []
    refs = list(getattr(answer_contract, "candidate_mitre", None) or [])
    return [str(item) for item in refs if item][:12]




def environment_kb_grounding_context() -> tuple[list[str], list[str]]:
    """Summarize configured Environment KB slots and asset registry hints."""
    from app.environment.asset_registry_store import load_asset_registry_document
    from app.spl.source_profile_catalog import list_source_profile_slot_definitions
    from app.spl.source_profile_resolver import build_policy_derived_profile, merge_profiles
    from app.spl.source_profile_store import load_persisted_source_profile_document

    document = load_persisted_source_profile_document()
    values = dict(document.get("values") or {})
    effective = merge_profiles(build_policy_derived_profile(), values)

    slot_summaries: list[str] = []
    missing_slots: list[str] = []
    for slot in list_source_profile_slot_definitions():
        slot_id = str(slot.get("slot_id") or "")
        configured = str(effective.get(slot_id) or "").strip()
        if configured:
            preview = configured if len(configured) <= 48 else configured[:45] + "..."
            slot_summaries.append(f"{slot_id}={preview}")
        else:
            missing_slots.append(slot_id)

    if missing_slots:
        slot_summaries.append(f"missing_slots={','.join(missing_slots[:8])}")

    assets = list(load_asset_registry_document().get("assets") or [])
    hints: list[str] = []
    if assets:
        hints.append(f"asset_count={len(assets)}")
        master_stations = sum(1 for row in assets if isinstance(row, dict) and row.get("is_master_station"))
        if master_stations:
            hints.append(f"master_station_count={master_stations}")
        purdue_layers = sorted(
            {
                str(row.get("purdue_layer") or "").strip()
                for row in assets
                if isinstance(row, dict) and str(row.get("purdue_layer") or "").strip()
            }
        )
        if purdue_layers:
            hints.append("purdue_layers=" + ",".join(purdue_layers[:6]))
        regions = sorted(
            {
                str(row.get("region") or "").strip()
                for row in assets
                if isinstance(row, dict) and str(row.get("region") or "").strip()
            }
        )
        if regions:
            hints.append("regions=" + ",".join(regions[:6]))
    else:
        hints.append("asset_registry=not_configured")

    return slot_summaries[:12], hints[:8]


def build_guided_hunt_grounding(
    *,
    query: str,
    answer_contract: Any | None = None,
    soc_kb_retrieval: dict[str, Any] | None = None,
    enrichment_projection: dict[str, Any] | None = None,
) -> GroundingBlock:
    """Assemble deterministic T2 grounding for a guided-hunt turn."""
    families = detection_families_for_question(query)
    if enrichment_projection:
        use_case = str(enrichment_projection.get("use_case_id") or "").strip()
        if use_case and use_case not in families:
            families.append(use_case)
    block = assemble_grounding(
        query,
        resolver=technique_resolver_from_settings(),
        detection_families=families,
        enterprise_mitre_refs=enterprise_mitre_refs_from_contract(answer_contract),
        soc_kb_refs=soc_kb_refs_from_retrieval(soc_kb_retrieval),
        skill_refs=skill_refs_for_question(query),
    )
    kb_slots, asset_hints = environment_kb_grounding_context()
    block.environment_kb_slots = kb_slots
    block.asset_registry_hints = asset_hints
    if _T2_UNVERIFIED_BANNER not in block.limitations:
        block.limitations.append(_T2_UNVERIFIED_BANNER)
    return block


def guided_hunt_grounding_trace(block: GroundingBlock) -> dict[str, Any]:
    return {
        "grounding": block.to_dict(),
        "prompt_block": block.to_prompt_block(),
        "unverified_banner": _T2_UNVERIFIED_BANNER,
        "advisory_only": True,
    }
