"""RAG-driven source-profile hints (SPL audit Phase H1).

Extracts `splunk_indexes` and `sourcetypes` from governed SOC-KB retrieval
results and maps them onto placeholder stems. Values are substituted
deterministically — the LLM never calls MCP or RAG directly on this path.
"""
from __future__ import annotations

from typing import Any

from app.spl.source_profile_resolver import _INDEX_STEMS, _SOURCETYPE_RULES, _stem_matches_index

_SOURCE_TO_INDEX_STEM: dict[str, str] = {
    "auth": "auth_index",
    "network": "network_index",
    "dns": "dns_index",
    "endpoint": "endpoint_index",
    "firewall": "firewall_index",
    "vpn": "vpn_index",
    "edr": "endpoint_index",
    "windows": "windows_index",
}


def _entries_from_retrieval(retrieval: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(retrieval, dict):
        return []
    entries = retrieval.get("entries")
    if isinstance(entries, list):
        return [entry for entry in entries if isinstance(entry, dict)]
    evidence = retrieval.get("source_evidence")
    if isinstance(evidence, list):
        return [entry for entry in evidence if isinstance(entry, dict)]
    return []


def _map_sourcetype_stem(sourcetype: str) -> str | None:
    lowered = sourcetype.lower()
    for stem, keywords in _SOURCETYPE_RULES:
        if any(keyword in lowered for keyword in keywords):
            return stem
    return None


def extract_rag_source_profile(
    retrieval: dict[str, Any] | None,
    *,
    required_sources: list[str] | None = None,
    required_slots: list[str] | None = None,
) -> dict[str, str]:
    profile: dict[str, str] = {}
    entries = _entries_from_retrieval(retrieval)
    if not entries:
        return profile

    indexes: list[str] = []
    sourcetypes: list[str] = []
    for entry in entries:
        indexes.extend(str(item) for item in entry.get("splunk_indexes") or [] if item)
        sourcetypes.extend(str(item) for item in entry.get("sourcetypes") or [] if item)

    unique_indexes = list(dict.fromkeys(indexes))
    unique_sourcetypes = list(dict.fromkeys(sourcetypes))

    for source in required_sources or []:
        stem = _SOURCE_TO_INDEX_STEM.get(source)
        if not stem:
            continue
        for index_name in unique_indexes:
            if _stem_matches_index(stem, index_name):
                profile.setdefault(stem, index_name)
                break
        if stem not in profile and len(unique_indexes) == 1:
            profile[stem] = unique_indexes[0]

    for sourcetype in unique_sourcetypes:
        stem = _map_sourcetype_stem(sourcetype)
        if stem:
            profile.setdefault(stem, sourcetype)

    if required_slots:
        return {slot: profile[slot] for slot in required_slots if slot in profile}
    return profile
