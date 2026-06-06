"""Negative-evidence extractor — present/absent evidence preconditions.

Aggregates *present* positive-evidence keys and *explicit* absence signals from
the user query, structured context, and RAG excerpts, with precedence:

    query signals  ->  structured_context  ->  RAG excerpts

Only query + RAG carry content today (live MCP execution stays off), but the
extractor accepts all three so the same code path holds once tool evidence is
wired. Output feeds `mitre_evidence_preconditions.precondition_negated` so a
candidate technique lacking its required evidence is demoted to Not Claimed.

This module makes no authority decision; it is a pure projection of signals.
"""

from __future__ import annotations

from typing import Any

# Positive-evidence key -> the query_signals flags that prove its presence.
# Presence of ANY listed flag marks the evidence key present.
_PRESENCE_FROM_SIGNAL: dict[str, tuple[str, ...]] = {
    "successful_login": ("positive_successful_login", "success_after_failure"),
    "failed_login_pattern": ("failed_login",),
    "spray_breadth": ("spray_breadth",),
    "source_ip_novelty": ("source_ip_novelty",),
    "valid_account_abuse": ("valid_account_abuse",),
    "powershell_command_evidence": ("powershell_command_evidence",),
    "script_block_evidence": ("powershell_command_evidence",),
    "encoded_command": ("encoded_command",),
    "suspicious_parent_process": ("suspicious_parent_process",),
    "download_cradle": ("download_cradle",),
    "endpoint_network_connection": ("endpoint_network_connection",),
    "email_auth_failure": ("email_auth_failure",),
    "sender_return_path_mismatch": ("sender_return_path_mismatch",),
    "malicious_url_or_domain": ("malicious_url_or_domain",),
    "attachment_hash_verdict": ("attachment_hash_verdict",),
    "mail_gateway_verdict": ("mail_gateway_verdict",),
    "periodicity": ("periodicity",),
    "jitter_profile": ("jitter_profile",),
    "repeated_destination": ("repeated_destination",),
    "rare_domain": ("rare_domain",),
    "byte_pattern": ("byte_pattern",),
    "host_association": ("host_association",),
    "network_telemetry": ("periodicity", "jitter_profile", "repeated_destination", "rare_domain", "byte_pattern"),
    "file_rename_volume": ("file_rename_volume",),
    "extension_pattern": ("extension_pattern",),
    "encryption_behavior": ("encryption_behavior",),
    "impacted_paths": ("impacted_paths",),
    "process_evidence": ("process_evidence",),
    "shadow_copy_deletion": ("shadow_copy_deletion",),
    "service_stop": ("service_stop",),
    "host_spread": ("host_spread",),
}

# Explicit absence signals -> the evidence key they negate (for trace/prose).
_NEGATION_FROM_SIGNAL: dict[str, str] = {
    "negative_successful_login": "successful_login",
    "negative_endpoint_telemetry": "endpoint_telemetry",
    "negative_cred_dumping": "credential_dumping_evidence",
}


def extract_negative_evidence(
    *,
    query_signals: dict[str, Any] | None = None,
    source_evidence: list[dict[str, Any]] | None = None,
    structured_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return present-evidence keys, explicit negations, and RAG prohibitions."""
    signals = query_signals or {}

    present: set[str] = set()
    for evidence_key, flags in _PRESENCE_FROM_SIGNAL.items():
        if any(bool(signals.get(flag)) for flag in flags):
            present.add(evidence_key)

    explicit_negations: set[str] = set()
    for flag, evidence_key in _NEGATION_FROM_SIGNAL.items():
        if bool(signals.get(flag)):
            explicit_negations.add(evidence_key)
    # An explicit negation always wins over a weak presence inference.
    present -= explicit_negations

    prohibited = _rag_prohibited_conclusions(source_evidence, structured_context)

    return {
        "present_evidence": sorted(present),
        "explicit_negations": sorted(explicit_negations),
        "rag_prohibited_conclusions": prohibited,
    }


def present_evidence_keys(negative_evidence: dict[str, Any] | None) -> set[str]:
    """Helper for consumers: the set of present positive-evidence keys."""
    if not negative_evidence:
        return set()
    return {str(item) for item in negative_evidence.get("present_evidence") or []}


def _rag_prohibited_conclusions(
    source_evidence: list[dict[str, Any]] | None,
    structured_context: dict[str, Any] | None,
) -> list[str]:
    """Collect RAG/structured prohibited conclusions (precedence: structured, then RAG).

    These constrain prose and, where they map to a technique precondition, can
    block a claim. Returned for the AnswerContract/validator; deduplicated.
    """
    prohibited: list[str] = []

    def _add(values: Any) -> None:
        if not isinstance(values, list):
            return
        for value in values:
            text = str(value).strip()
            if text and text not in prohibited:
                prohibited.append(text)

    _add((structured_context or {}).get("prohibited_conclusions"))
    for envelope in source_evidence or []:
        if not isinstance(envelope, dict):
            continue
        if envelope.get("source_type") != "rag":
            continue
        _add(envelope.get("prohibited_conclusions"))
    return prohibited
