from __future__ import annotations

import re
from typing import Any

from app.spl.policy import SplValidationPolicy, load_spl_policy, policy_with_template_profile

SECRET_PATTERNS = (
    re.compile(r"\b(password|passwd|secret|token|api[_-]?key|credential)\b", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
)

QUERY_SHAPE_RAW_SEARCH = "raw_search"
QUERY_SHAPE_TSTATS_DATAMODEL = "tstats_datamodel"
QUERY_SHAPE_FROM_DATAMODEL = "from_datamodel"

APPROVED_DATAMODELS = {
    "Authentication",
    "Network_Traffic",
    "Network_Resolution",
    "DNS",
    "Endpoint",
    "Web",
    "Change",
    "Intrusion_Detection",
    "Risk",
    "Notable",
}
DATAMODEL_ALIASES = {
    "network_resolution": "Network_Resolution",
    "dns": "DNS",
}
APPROVED_DATASETS = {
    "Authentication": {"Authentication"},
    "Network_Traffic": {"All_Traffic", "Network_Traffic"},
    "Network_Resolution": {"DNS", "Network_Resolution"},
    "DNS": {"DNS"},
    "Endpoint": {"Processes", "Endpoint"},
    "Web": {"Web"},
    "Change": {"Change"},
    "Intrusion_Detection": {"Intrusion_Detection", "IDS_Attacks"},
    "Risk": {"Risk"},
    "Notable": {"Notable"},
}
DATAMODEL_FIELD_ALLOWLIST = {
    "Authentication": {"user", "src", "src_ip", "dest", "dest_host", "app", "action", "result", "signature", "vendor_product", "_time"},
    "Network_Traffic": {"src", "src_ip", "dest", "dest_ip", "dest_port", "transport", "app", "action", "bytes", "bytes_in", "bytes_out", "packets", "_time"},
    "Network_Resolution": {"src", "src_ip", "host", "query", "query_type", "answer", "domain", "record_type", "_time"},
    "DNS": {"src", "src_ip", "host", "query", "query_type", "answer", "domain", "record_type", "_time"},
    "Endpoint": {"host", "user", "process", "process_name", "parent_process", "command_line", "file_name", "file_hash", "action", "_time"},
    "Web": {"user", "src", "src_ip", "dest", "url", "domain", "http_method", "status", "bytes", "action", "_time"},
    "Change": {"user", "object", "object_category", "action", "change_type", "src", "dest", "_time"},
    "Intrusion_Detection": {"src", "dest", "signature", "severity", "action", "vendor_product", "_time"},
    "Risk": {"risk_object", "risk_object_type", "risk_score", "rule_name", "severity", "status", "owner", "notable_id", "_time"},
    "Notable": {"risk_object", "risk_object_type", "risk_score", "rule_name", "severity", "status", "owner", "notable_id", "_time"},
}
APPROVED_DATAMODEL_AGGREGATIONS = {"count", "sum", "dc", "values", "latest", "earliest"}
CIM_PIPELINE_COMMANDS = {"tstats", "from", "where", "fields", "table", "sort", "head", "stats", "rename"}
RISKY_COMMANDS = {"collect", "outputlookup", "delete", "sendemail", "map", "script", "rest", "loadjob", "savedsearch", "inputlookup"}


def validate_spl(
    query: str,
    policy: SplValidationPolicy | None = None,
    template_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or load_spl_policy()
    policy = policy_with_template_profile(policy, template_profile)
    spl = _normalize_whitespace(query)
    query_shape = _detect_query_shape(spl)
    if query_shape == QUERY_SHAPE_TSTATS_DATAMODEL:
        return _validate_tstats_datamodel(spl, policy)
    if query_shape == QUERY_SHAPE_FROM_DATAMODEL:
        return _validate_from_datamodel(spl, policy)
    return _validate_raw_search(spl, policy)


def _validate_raw_search(spl: str, policy: SplValidationPolicy) -> dict[str, Any]:
    lowered = spl.lower()
    reject_reasons: list[str] = []
    warnings: list[str] = []

    if not policy.enabled:
        reject_reasons.append("spl_validation_disabled")
    if not spl:
        reject_reasons.append("empty_spl")

    commands = _extract_commands(spl)
    command_set_for_block = set(commands) | _risky_command_tokens(lowered)
    if _lookup_allowed(spl, policy):
        command_set_for_block.discard("inputlookup")
    blocked = sorted(command_set_for_block.intersection(set(policy.blocked_commands) | RISKY_COMMANDS))
    disallowed = sorted(command for command in set(commands) if command not in policy.allowed_commands)
    indexes = _extract_field_values(spl, "index")
    sourcetypes = _extract_field_values(spl, "sourcetype")

    if blocked:
        reject_reasons.append(f"blocked_command:{','.join(blocked)}")
    if disallowed:
        reject_reasons.append(f"disallowed_command:{','.join(disallowed)}")
    reject_reasons.extend(_lookup_rejects(spl, commands, policy))
    reject_reasons.extend(_join_transaction_rejects(spl, commands, policy))
    warnings.extend(_tiered_command_warnings(spl, commands))
    if not commands or commands[0] != "search":
        reject_reasons.append("first_command_must_be_search")
    if "earliest=" not in lowered or "latest=" not in lowered:
        reject_reasons.append("missing_time_bounds")
    if "earliest=0" in lowered or "earliest=all" in lowered or "alltime" in lowered:
        reject_reasons.append("unbounded_all_time_search")
    if not set(commands).intersection({"stats", "timechart"}):
        reject_reasons.append("missing_aggregation")
    if not indexes:
        reject_reasons.append("missing_index")
    if any(index not in policy.allowed_indexes for index in indexes):
        reject_reasons.append("disallowed_index")
    if any("*" in index for index in indexes) and not policy.allow_wildcard_indexes:
        reject_reasons.append("wildcard_index_not_allowed")
    if not sourcetypes:
        reject_reasons.append("missing_sourcetype")
    if any(sourcetype not in policy.allowed_sourcetypes for sourcetype in sourcetypes):
        reject_reasons.append("disallowed_sourcetype")
    if re.search(r"`[^`]+`", spl) and not policy.allow_macros:
        reject_reasons.append("macros_not_allowed")
    if ("[" in spl or "]" in spl) and not policy.allow_subsearches:
        reject_reasons.append("subsearches_not_allowed")
    if re.search(r"\b(https?://|curl\b|wget\b|webhook\b)\b", lowered) and not policy.allow_external_calls:
        reject_reasons.append("external_calls_not_allowed")
    if any(pattern.search(spl) for pattern in SECRET_PATTERNS):
        reject_reasons.append("credential_or_secret_pattern")

    enforced_limits = {
        "max_result_limit": policy.max_result_limit,
        "result_limit_enforced": True,
        "enforcement_mode": "out_of_band",
        "default_earliest": policy.default_earliest,
        "default_latest": policy.default_latest,
    }
    limit_value = _result_limit_value(spl)
    if limit_value is None:
        reject_reasons.append("missing_result_limit")
    elif limit_value > policy.max_result_limit:
        reject_reasons.append("result_limit_exceeds_policy")

    approved = not reject_reasons
    normalized_spl = spl if approved else None
    return {
        "approved": approved,
        "normalized_spl": normalized_spl,
        "reject_reasons": reject_reasons,
        "warnings": warnings,
        "enforced_limits": enforced_limits,
        "policy_version": policy.policy_version,
        # Backward-compatible aliases for existing tests and debug surfaces.
        "valid": approved,
        "errors": reject_reasons,
        "blocked_commands": blocked,
        "requires_human_approval": bool(reject_reasons),
        "query_shape": QUERY_SHAPE_RAW_SEARCH,
        "datamodel": None,
        "dataset": None,
        "cim_fields_validated": [],
        "summariesonly_required": False,
        "summariesonly_present": False,
        "time_bounds_present": "missing_time_bounds" not in reject_reasons,
        "result_limit_present": "missing_result_limit" not in reject_reasons,
        "blocked_commands_found": blocked,
        "validation_profile": "raw_search_v1",
        "execution_eligible": False,
    }


# --- Lab-candidate validation (review-only, never executable) ----------------
# An LLM SPL failover candidate uses angle-bracket placeholders for index /
# sourcetype because it cannot know customer-specific source config (air-gapped,
# COE-supplied). Such SPL can never pass the execution validator (placeholders are
# disallowed indexes) but is safe to SHOW to an analyst for review — exactly the
# contract the deterministic lab draft families already use. This validator keeps
# every safety check (blocked commands, time bounds, aggregation, head limit,
# subsearches, external calls) but treats placeholder index/sourcetype as eligible.
# It NEVER approves for execution: approved stays False, normalized_spl stays None.
_PLACEHOLDER_TOKEN_RE = re.compile(r"^<[^>]+>$")

# Index/sourcetype rejects that are acceptable for lab review when backed by a
# placeholder token (the value is `<something>`, not a real disallowed index).
_LAB_ELIGIBLE_SOURCE_REJECTS = {
    "disallowed_index",
    "disallowed_sourcetype",
    "wildcard_index_not_allowed",
    "missing_index",
    "missing_sourcetype",
}

# Detect a genuine secret assignment vs a bareword hunt term. `password=hunter2`,
# a PEM private key, or a Bearer token are real secrets; `action=password_change`
# or hunting for `credential` / `lsass` indicators are not.
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(password|passwd|secret|token|api[_-]?key|credential)\s*=\s*\S", re.IGNORECASE
)


def _is_placeholder_token(value: str) -> bool:
    return bool(_PLACEHOLDER_TOKEN_RE.match((value or "").strip()))


def _secret_reject_is_lab_benign(spl: str) -> bool:
    """True when the only secret-pattern hits are bareword hunt terms, not an
    actual embedded secret (assignment, private key, or bearer token)."""
    if _SECRET_ASSIGNMENT_RE.search(spl):
        return False
    if re.search(r"-----BEGIN [A-Z ]+PRIVATE KEY-----", spl):
        return False
    if re.search(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", spl, re.IGNORECASE):
        return False
    return True


def lab_validation_eligible(reject_reasons: list[str], spl: str) -> bool:
    """True when a full-validator failure is downgradable to a lab candidate:
    every remaining reject is a placeholder-source reject (backed by a real
    placeholder token) or a lab-benign secret-pattern hit."""
    remaining = set(reject_reasons)
    benign = set(_LAB_ELIGIBLE_SOURCE_REJECTS)
    if "credential_or_secret_pattern" in remaining and _secret_reject_is_lab_benign(spl):
        benign.add("credential_or_secret_pattern")
    if not remaining.issubset(benign):
        return False
    values = _extract_field_values(spl, "index") + _extract_field_values(spl, "sourcetype")
    return any(_is_placeholder_token(value) for value in values)


def validate_spl_lab_candidate(query: str, policy: SplValidationPolicy | None = None) -> dict[str, Any]:
    """Validate an SPL for analyst-review (lab) exposure only.

    Runs the full raw-search safety checks, then accepts placeholder index/
    sourcetype and lab-benign secret-pattern terms. ALWAYS returns
    approved=False and normalized_spl=None — lab candidates are never executable.
    """
    policy = policy or load_spl_policy()
    spl = _normalize_whitespace(query)
    base = _validate_raw_search(spl, policy)
    eligible = lab_validation_eligible(base.get("reject_reasons") or [], spl)
    return {
        **base,
        "approved": False,
        "normalized_spl": None,
        "lab_candidate_eligible": eligible,
        "exposure_tier": "lab_candidate",
        "validation_profile": "lab_candidate_v1",
        "execution_eligible": False,
    }


def _validate_tstats_datamodel(spl: str, policy: SplValidationPolicy) -> dict[str, Any]:
    reject_reasons, warnings, blocked_commands = _common_cim_rejects(spl, policy)
    commands = _extract_commands(spl)
    lowered = spl.lower()
    datamodel, dataset = _extract_datamodel_reference(spl)
    canonical_datamodel = _canonical_datamodel(datamodel)
    cim_fields = _extract_cim_fields(spl, canonical_datamodel, dataset)
    aggregations = _extract_tstats_aggregations(spl)
    summariesonly_present = bool(re.search(r"\bsummariesonly\s*=\s*true\b", lowered))
    time_bounds_present = _time_bounds_present(lowered)
    result_limit_present = _has_result_limit(spl)

    if not commands or commands[0] != "tstats":
        reject_reasons.append("first_command_must_be_tstats")
    if not datamodel:
        reject_reasons.append("missing_datamodel")
    elif canonical_datamodel not in APPROVED_DATAMODELS:
        reject_reasons.append("unknown_datamodel")
    if dataset and canonical_datamodel in APPROVED_DATASETS and dataset not in APPROVED_DATASETS[canonical_datamodel]:
        reject_reasons.append("unknown_dataset")
    if not summariesonly_present:
        reject_reasons.append("summariesonly_required")
    if not time_bounds_present:
        reject_reasons.append("missing_time_bounds")
    if not result_limit_present:
        reject_reasons.append("missing_result_limit")
    if not aggregations or any(item not in APPROVED_DATAMODEL_AGGREGATIONS for item in aggregations):
        reject_reasons.append("invalid_tstats_aggregation")
    reject_reasons.extend(_field_rejects(canonical_datamodel, cim_fields))
    reject_reasons.extend(_cim_command_rejects(commands))

    return _cim_result(
        spl=spl,
        policy=policy,
        query_shape=QUERY_SHAPE_TSTATS_DATAMODEL,
        datamodel=canonical_datamodel if canonical_datamodel in APPROVED_DATAMODELS else datamodel,
        dataset=dataset,
        cim_fields=cim_fields,
        summariesonly_required=True,
        summariesonly_present=summariesonly_present,
        time_bounds_present=time_bounds_present,
        result_limit_present=result_limit_present,
        blocked_commands=blocked_commands,
        reject_reasons=reject_reasons,
        warnings=warnings,
        validation_profile="cim_tstats_datamodel_v1",
    )


def _validate_from_datamodel(spl: str, policy: SplValidationPolicy) -> dict[str, Any]:
    reject_reasons, warnings, blocked_commands = _common_cim_rejects(spl, policy)
    commands = _extract_commands(spl)
    lowered = spl.lower()
    datamodel, dataset = _extract_datamodel_reference(spl)
    canonical_datamodel = _canonical_datamodel(datamodel)
    cim_fields = _extract_cim_fields(spl, canonical_datamodel, dataset)
    time_bounds_present = _time_bounds_present(lowered)
    result_limit_present = _has_result_limit(spl)

    if not commands or commands[0] != "from":
        reject_reasons.append("first_command_must_be_from_datamodel")
    if not datamodel:
        reject_reasons.append("missing_datamodel")
    elif canonical_datamodel not in APPROVED_DATAMODELS:
        reject_reasons.append("unknown_datamodel")
    if dataset and canonical_datamodel in APPROVED_DATASETS and dataset not in APPROVED_DATASETS[canonical_datamodel]:
        reject_reasons.append("unknown_dataset")
    if not time_bounds_present:
        reject_reasons.append("missing_time_bounds")
    if not result_limit_present:
        reject_reasons.append("missing_result_limit")
    reject_reasons.extend(_field_rejects(canonical_datamodel, cim_fields))
    reject_reasons.extend(_cim_command_rejects(commands))
    if "stats" in commands and not _extract_stats_aggregations(spl):
        reject_reasons.append("invalid_from_datamodel_aggregation")

    return _cim_result(
        spl=spl,
        policy=policy,
        query_shape=QUERY_SHAPE_FROM_DATAMODEL,
        datamodel=canonical_datamodel if canonical_datamodel in APPROVED_DATAMODELS else datamodel,
        dataset=dataset,
        cim_fields=cim_fields,
        summariesonly_required=False,
        summariesonly_present=False,
        time_bounds_present=time_bounds_present,
        result_limit_present=result_limit_present,
        blocked_commands=blocked_commands,
        reject_reasons=reject_reasons,
        warnings=warnings,
        validation_profile="cim_from_datamodel_v1",
    )


def _normalize_whitespace(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip())


def _detect_query_shape(spl: str) -> str:
    lowered = spl.lower().lstrip()
    if re.match(r"^tstats\b", lowered):
        return QUERY_SHAPE_TSTATS_DATAMODEL
    if re.match(r"^from\s+datamodel\s*=", lowered):
        return QUERY_SHAPE_FROM_DATAMODEL
    return QUERY_SHAPE_RAW_SEARCH


def _extract_commands(spl: str) -> list[str]:
    parts = [part.strip() for part in spl.split("|") if part.strip()]
    commands: list[str] = []
    for index, part in enumerate(parts):
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", part)
        if not match:
            continue
        command = match.group(1).lower()
        if command == "bucket":
            command = "bin"
        if index == 0 and command not in {"search", "tstats", "from", "inputlookup"}:
            commands.append("search")
        else:
            commands.append(command)
    return commands


def _safe_lookup_name(value: str) -> str:
    from app.spl.policy import _safe_lookup_name as policy_safe_lookup_name

    return policy_safe_lookup_name(value)


def _extract_lookup_names(spl: str) -> list[str]:
    names: list[str] = []
    for match in re.finditer(r"(?:^|\|\s*)(lookup|inputlookup)\s+([^\s|]+)", spl, re.IGNORECASE):
        raw = match.group(2)
        names.append(_safe_lookup_name(raw))
    return names


def _lookup_allowed(spl: str, policy: SplValidationPolicy) -> bool:
    names = _extract_lookup_names(spl)
    return bool(names) and all(name and name in policy.allowed_lookups for name in names)


def _lookup_rejects(spl: str, commands: list[str], policy: SplValidationPolicy) -> list[str]:
    if not ({"lookup", "inputlookup"} & set(commands)):
        return []
    names = _extract_lookup_names(spl)
    if not names or any(not name for name in names):
        return ["lookup_name_invalid"]
    allowed = set(policy.allowed_lookups)
    rejected = sorted(name for name in names if name not in allowed)
    if rejected:
        return [f"lookup_not_allowlisted:{','.join(rejected)}"]
    return []


def _join_transaction_rejects(spl: str, commands: list[str], policy: SplValidationPolicy) -> list[str]:
    rejects: list[str] = []
    lowered = spl.lower()
    if "join" in commands:
        if not policy.allow_join:
            rejects.append("join_not_allowed")
        if not _has_final_head(lowered):
            rejects.append("join_requires_result_head")
        if not re.search(r"\|\s*join\b[^|]*\bmax=\d+\b", lowered):
            rejects.append("join_requires_max_option")
    if "transaction" in commands:
        if not policy.allow_transaction:
            rejects.append("transaction_not_allowed")
        if not re.search(r"\|\s*transaction\b[^|]*(?:maxspan=\S+|maxevents=\d+)", lowered):
            rejects.append("transaction_requires_maxspan_or_maxevents")
    return rejects


def _tiered_command_warnings(spl: str, commands: list[str]) -> list[str]:
    if "mvexpand" not in commands:
        return []
    lowered = spl.lower()
    mvexpand_match = re.search(r"\|\s*mvexpand\b", lowered)
    if mvexpand_match and not re.search(r"\|\s*head\s+\d+\b", lowered[mvexpand_match.end() :]):
        return ["mvexpand_without_downstream_head"]
    return []


def _has_final_head(lowered_spl: str) -> bool:
    return bool(re.search(r"\|\s*head\s+\d+\s*$", lowered_spl.strip()))


def _extract_field_values(spl: str, field: str) -> list[str]:
    return [match.group(1).strip('"').lower() for match in re.finditer(rf"\b{field}=([^\s|]+)", spl, re.IGNORECASE)]


def _has_result_limit(spl: str) -> bool:
    return _result_limit_value(spl) is not None


def _result_limit_value(spl: str) -> int | None:
    lowered = spl.lower()
    head_match = re.search(r"\|\s*head\s+(\d+)", lowered)
    if head_match:
        return int(head_match.group(1))
    sort_match = re.search(r"\|\s*sort\s+(\d+)\s+", lowered)
    if sort_match:
        return int(sort_match.group(1))
    return None


def _common_cim_rejects(spl: str, policy: SplValidationPolicy) -> tuple[list[str], list[str], list[str]]:
    lowered = spl.lower()
    reject_reasons: list[str] = []
    warnings: list[str] = []
    commands = _extract_commands(spl)
    blocked = sorted((set(commands) | _risky_command_tokens(lowered)).intersection(set(policy.blocked_commands) | RISKY_COMMANDS))

    if not policy.enabled:
        reject_reasons.append("spl_validation_disabled")
    if not spl:
        reject_reasons.append("empty_spl")
    if blocked:
        reject_reasons.append(f"blocked_command:{','.join(blocked)}")
    if re.search(r"`[^`]+`", spl) and not policy.allow_macros:
        reject_reasons.append("macros_not_allowed")
    if ("[" in spl or "]" in spl) and not policy.allow_subsearches:
        reject_reasons.append("subsearches_not_allowed")
    if re.search(r"\b(https?://|curl\b|wget\b|webhook\b)\b", lowered) and not policy.allow_external_calls:
        reject_reasons.append("external_calls_not_allowed")
    if any(pattern.search(spl) for pattern in SECRET_PATTERNS):
        reject_reasons.append("credential_or_secret_pattern")
    if "earliest=0" in lowered or "earliest=all" in lowered or "alltime" in lowered:
        reject_reasons.append("unbounded_all_time_search")

    limit_value = _result_limit_value(spl)
    if limit_value is not None and limit_value > policy.max_result_limit:
        reject_reasons.append("result_limit_exceeds_policy")

    return reject_reasons, warnings, blocked


def _risky_command_tokens(lowered: str) -> set[str]:
    found: set[str] = set()
    for command in RISKY_COMMANDS:
        if re.search(rf"(^|\|\s*){re.escape(command)}\b", lowered):
            found.add(command)
    return found


def _cim_command_rejects(commands: list[str]) -> list[str]:
    disallowed = sorted(command for command in set(commands) if command not in CIM_PIPELINE_COMMANDS)
    return [f"disallowed_command:{','.join(disallowed)}"] if disallowed else []


def _extract_datamodel_reference(spl: str) -> tuple[str | None, str | None]:
    match = re.search(r"\bdatamodel\s*=\s*([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?", spl, re.IGNORECASE)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _canonical_datamodel(datamodel: str | None) -> str | None:
    if not datamodel:
        return None
    if datamodel in APPROVED_DATAMODELS:
        return datamodel
    lowered = datamodel.lower()
    if lowered in DATAMODEL_ALIASES:
        return DATAMODEL_ALIASES[lowered]
    for approved in APPROVED_DATAMODELS:
        if approved.lower() == lowered:
            return approved
    return datamodel


def _time_bounds_present(lowered: str) -> bool:
    return "earliest=" in lowered and "latest=" in lowered


def _extract_tstats_aggregations(spl: str) -> list[str]:
    first = spl.split("|", 1)[0]
    before_from = re.split(r"\bfrom\s+datamodel\s*=", first, flags=re.IGNORECASE)[0]
    after_tstats = re.sub(r"^tstats\b", "", before_from, flags=re.IGNORECASE).strip()
    after_tstats = re.sub(r"\bsummariesonly\s*=\s*(true|false)\b", "", after_tstats, flags=re.IGNORECASE)
    return [match.group(1).lower() for match in re.finditer(r"\b(count|sum|dc|values|latest|earliest)\b(?:\s*\(|\s+as\b|\s|$)", after_tstats, re.IGNORECASE)]


def _extract_stats_aggregations(spl: str) -> list[str]:
    aggregations: list[str] = []
    for part in [part.strip() for part in spl.split("|") if part.strip()]:
        if not part.lower().startswith("stats "):
            continue
        aggregations.extend(match.group(1).lower() for match in re.finditer(r"\b(count|sum|dc|values|latest|earliest)\b(?:\s*\(|\s+as\b|\s|$)", part, re.IGNORECASE))
    return aggregations


def _extract_cim_fields(spl: str, datamodel: str | None, dataset: str | None) -> list[str]:
    fields: set[str] = set()
    prefix_candidates = {item for item in (datamodel, dataset) if item}
    spl_without_dm_refs = re.sub(r"\bdatamodel\s*=\s*[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?", "", spl, flags=re.IGNORECASE)
    for prefix in prefix_candidates:
        for match in re.finditer(rf"\b{re.escape(prefix)}\.([A-Za-z_][A-Za-z0-9_]*)\b", spl_without_dm_refs, re.IGNORECASE):
            fields.add(match.group(1))

    for section in _field_sections(spl_without_dm_refs):
        for token in re.split(r"[\s,]+", section):
            field = _clean_field_token(token)
            if field:
                fields.add(field)
    return sorted(fields)


def _field_sections(spl: str) -> list[str]:
    sections: list[str] = []
    for match in re.finditer(r"\bby\s+([^|]+)", spl, re.IGNORECASE):
        sections.append(match.group(1))
    for command in ("table", "fields"):
        for match in re.finditer(rf"\|\s*{command}\s+([^|]+)", spl, re.IGNORECASE):
            sections.append(match.group(1))
    for match in re.finditer(r"\bwhere\s+([^|]+)", spl, re.IGNORECASE):
        sections.append(re.split(r"\bby\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0])
    return sections


def _clean_field_token(token: str) -> str | None:
    cleaned = token.strip().strip(",()")
    if not cleaned or cleaned.lower() in {"=", "!=", ">", "<", ">=", "<=", "and", "or", "by", "from"}:
        return None
    if "=" in cleaned:
        cleaned = cleaned.split("=", 1)[0]
    if "." in cleaned:
        cleaned = cleaned.rsplit(".", 1)[-1]
    if re.fullmatch(r"-?\d+|\"[^\"]*\"|'[^']*'|true|false|now", cleaned, re.IGNORECASE):
        return None
    if cleaned.lower() in {"earliest", "latest", "datamodel", "summariesonly", "as", "span"}:
        return None
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cleaned):
        return None
    return cleaned


def _field_rejects(datamodel: str | None, fields: list[str]) -> list[str]:
    if datamodel not in DATAMODEL_FIELD_ALLOWLIST:
        return []
    allowed = DATAMODEL_FIELD_ALLOWLIST[datamodel]
    unknown = sorted(field for field in fields if field not in allowed)
    return [f"unknown_cim_field:{','.join(unknown)}"] if unknown else []


def _cim_result(
    *,
    spl: str,
    policy: SplValidationPolicy,
    query_shape: str,
    datamodel: str | None,
    dataset: str | None,
    cim_fields: list[str],
    summariesonly_required: bool,
    summariesonly_present: bool,
    time_bounds_present: bool,
    result_limit_present: bool,
    blocked_commands: list[str],
    reject_reasons: list[str],
    warnings: list[str],
    validation_profile: str,
) -> dict[str, Any]:
    deduped_rejects = _dedupe_preserve_order(reject_reasons)
    approved = not deduped_rejects
    enforced_limits = {
        "max_result_limit": policy.max_result_limit,
        "result_limit_enforced": True,
        "enforcement_mode": "validator_required",
        "default_earliest": policy.default_earliest,
        "default_latest": policy.default_latest,
    }
    return {
        "approved": approved,
        "normalized_spl": spl if approved else None,
        "reject_reasons": deduped_rejects,
        "warnings": warnings,
        "enforced_limits": enforced_limits,
        "policy_version": policy.policy_version,
        "valid": approved,
        "errors": deduped_rejects,
        "blocked_commands": blocked_commands,
        "requires_human_approval": bool(deduped_rejects),
        "query_shape": query_shape,
        "datamodel": datamodel,
        "dataset": dataset,
        "cim_fields_validated": cim_fields,
        "summariesonly_required": summariesonly_required,
        "summariesonly_present": summariesonly_present,
        "time_bounds_present": time_bounds_present,
        "result_limit_present": result_limit_present,
        "blocked_commands_found": blocked_commands,
        "validation_profile": validation_profile,
        "execution_eligible": False,
    }


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
