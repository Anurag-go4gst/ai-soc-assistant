"""Plan 8 SPL1 — mandatory final-RQC constraints must survive into normalized SPL.

Does not map source-profile placeholders (that remains spl_source_resolve).
Does not authorize execution. LLM output cannot invent or drop constraints.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "rqc_constraint_preservation_v1"

_IP_ALIASES = ("src", "src_ip", "source_ip", "srcip")
_DEST_IP_ALIASES = ("dest", "dest_ip", "destination_ip", "dst")
_HOST_ALIASES = ("host", "hostname", "dest_host", "src_host")
_USER_ALIASES = ("user", "username", "account", "src_user")
_GEO_ALIASES = ("geo", "geo_country", "src_country", "country", "germany")
_TIME_TOKENS = ("earliest=", "latest=")


def rqc_slots_from_contract(rqc: dict[str, Any] | None) -> dict[str, str]:
    """Map final-RQC entities/time into existing SPL slot names."""
    if not isinstance(rqc, dict):
        return {}
    entities = rqc.get("entities") if isinstance(rqc.get("entities"), dict) else {}
    slots: dict[str, str] = {}
    src = _first_text(entities.get("source_ip") or entities.get("src_ip"))
    if src:
        slots["src_ip"] = src
    dest = _first_text(entities.get("destination_ip") or entities.get("dest_ip"))
    if dest:
        slots["dest_ip"] = dest
    host = _first_text(entities.get("host") or entities.get("hostname"))
    if host:
        slots["host"] = host
    user = _first_text(entities.get("user"))
    if user:
        slots["user"] = user
    port = _first_text(entities.get("port") or entities.get("port_numbers"))
    if port:
        slots["port"] = port
    domain = _first_text(entities.get("domain"))
    if domain:
        slots["domain"] = domain
    geo = _first_text(entities.get("geo") or entities.get("geography") or entities.get("country"))
    if geo:
        slots["geo"] = geo
    account_type = _first_text(entities.get("account_type"))
    if account_type:
        slots["account_type"] = account_type
    time_scope = rqc.get("time_scope") or entities.get("time_window")
    if isinstance(time_scope, str) and time_scope.strip():
        slots["time_window"] = time_scope.strip()
    return slots


def evaluate_rqc_constraint_preservation(
    spl: str | None,
    *,
    resolved_query_contract: dict[str, Any] | None,
    non_applicable: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return present/missing/non_applicable for mandatory RQC constraints."""
    reasons = dict(non_applicable or {})
    slots = rqc_slots_from_contract(resolved_query_contract)
    haystack = (spl or "").lower()
    present: list[str] = []
    missing: list[str] = []
    not_applicable: dict[str, str] = {}
    for key, value in slots.items():
        if key in reasons:
            not_applicable[key] = reasons[key]
            continue
        if _constraint_present(haystack, key, value):
            present.append(key)
        else:
            missing.append(key)
    return {
        "schema_version": SCHEMA_VERSION,
        "present": present,
        "missing": missing,
        "non_applicable": not_applicable,
        "dropped": list(missing),
    }


def apply_rqc_constraint_preservation(
    validation: dict[str, Any] | None,
    *,
    spl: str | None,
    resolved_query_contract: dict[str, Any] | None,
    non_applicable: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Fail closed when a mandatory RQC constraint is silently absent from SPL."""
    if not isinstance(validation, dict):
        return validation
    result = evaluate_rqc_constraint_preservation(
        spl or validation.get("normalized_spl"),
        resolved_query_contract=resolved_query_contract,
        non_applicable=non_applicable,
    )
    updated = {**validation, "rqc_constraint_preservation": result}
    if not result["dropped"]:
        return updated
    reject = list(updated.get("reject_reasons") or [])
    for key in result["dropped"]:
        code = f"rqc_constraint_dropped:{key}"
        if code not in reject:
            reject.append(code)
    updated["reject_reasons"] = reject
    updated["approved"] = False
    updated["normalized_spl"] = None
    return updated


def _constraint_present(haystack: str, key: str, value: str) -> bool:
    token = value.strip().lower()
    if not token:
        return True
    if key == "time_window":
        if "earliest=" in haystack and "latest=" in haystack:
            compact = token.replace(" ", "")
            if compact.lower() in haystack.replace(" ", ""):
                return True
            if "yesterday" in token or "-1d@d" in compact:
                return "-1d@d" in haystack or "yesterday" in haystack
            if "-24h" in compact:
                return "-24h" in haystack
            return any(marker in haystack for marker in _TIME_TOKENS)
        return False
    if key == "account_type":
        aliases = {token, token.replace("_", " "), token.replace("_", "")}
        if "service" in token:
            aliases.update({"service_account", "service account", "svc"})
        if "admin" in token:
            aliases.update({"admin", "administrator", "privileged"})
        return any(alias in haystack for alias in aliases if alias)
    if key == "geo":
        return any(alias in haystack for alias in (token, *_GEO_ALIASES) if alias == token or token in haystack)
    if key == "src_ip":
        return token in haystack or any(alias in haystack and token in haystack for alias in _IP_ALIASES)
    if key == "dest_ip":
        return token in haystack
    if key == "host":
        return token in haystack
    if key == "user":
        return token in haystack
    if key == "port":
        return token in haystack or f"port={token}" in haystack
    if key == "domain":
        return token in haystack
    return token in haystack


def _first_text(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            text = str(item).strip()
            if text:
                return text
        return None
    text = str(value).strip()
    return text or None
