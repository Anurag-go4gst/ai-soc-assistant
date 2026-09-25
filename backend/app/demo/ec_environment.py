"""One fictional enterprise shared by every Experience Center scenario.

Every scenario draws its hosts, accounts, tickets, SOPs, Splunk sources and priority rule from
here, so the same jump host or service account means the same thing in every question.

* **Time** — fixture text carries ``{D-9}`` / ``{D-9 03:12}`` / ``{W30}`` tokens, rendered against
  the moment the page is served. "Last 30 days" therefore always covers the dates shown.
* **The S1 partner address** (``3.110.47.92``) is a full address so the question reads like a
  real ticket. Nothing in the Experience Center ever contacts it; scanner addresses in other
  questions stay partly masked.
* **Priority** comes from :func:`incident_priority` (SOC-POL-PRIO-01), never from the fixture,
  and is kept separate from the threat assessment.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

# --- Hosts, accounts, identities -------------------------------------------------------------

JUMP_HOST = "JMP-ADM-01"
JUMP_HOST_IP = "10.20.1.10"
EDGE_FIREWALL = "FW-EDGE-01"
OT_FIREWALL = "FW-OT-01"
API_GATEWAY = "APIGW-01"
FINANCE_DB = "FIN-DB-02"
FINANCE_DB_IP = "10.30.7.21"
BRANCH_ROUTER = "RTR-BR-17"
OT_RTU = "SUB07-RTU-14"
OT_RTU_IP = "10.80.4.14"
OT_EWS = "SUB07-EWS-03"
OT_EWS_IP = "10.80.1.23"
AI_GATEWAY = "AIGW-01"
AI_APP = "Customer Help Assistant"
VPN_GATEWAYS = ("VPN-GW-01", "VPN-GW-02", "VPN-GW-03", "VPN-GW-04")

SVC_NETOPS = "svc_netops"
SVC_DEPLOY = "svc_deploy"
ADM_DBA = "adm_dba02"

PARTNER_ID = "PRT-0147"
PARTNER_NAME = "freight carrier tracking API"
PARTNER_EGRESS_GROUP = "PARTNER-0147-EGRESS"  # firewall object group: the partner's 3 registered addresses

EXTERNAL_IP = "3.110.47.92"
SCANNER_IPS = ("103.xx.xx.17", "103.xx.xx.29")

# --- Tickets (revealed only after the ITSM action that creates them runs) --------------------

INCIDENT_S1 = "INC0048213"
TASK_S1_DETECTION = "TASK0019220"
CHANGE_S3_BLOCK = "CHG0031177"
INCIDENT_S2 = "INC0048377"
TASK_S2_AI_PLATFORM = "TASK0019236"
INCIDENT_S4 = "INC0048290"
CHANGE_S4_WORKAROUND = "CHG0031162"
CHANGE_S4_PATCH = "CHG0031164"
INCIDENT_S5 = "INC0048301"
CHANGE_S5_REVERT = "CHG0031190"
INCIDENT_S6_EXISTING = "INC0047760"
TASK_S6_IAM = "TASK0019244"
INCIDENT_S7 = "INC0048402"
TASK_S7_CMDB = "TASK0019251"
CHANGE_S7_FW = "CHG0031196"
INCIDENT_R1 = "INC0048415"
TASK_Q2_DETECTION = "TASK0019260"
TASK_Q1_IAM = "TASK0019257"
TASK_S5_IAM = "TASK0019248"
TASK_S4_DETECTION = "TASK0019241"

# --- Knowledge base -------------------------------------------------------------------------

SOP_NEW_EXTERNAL = "SOC-SOP-NET-007"
SOP_FIREWALL_BLOCK = "SOC-SOP-FW-010"
SOP_PRIV_LOGON = "SOC-SOP-AUTH-003"
SOP_CRITICAL_VULN = "SOC-SOP-VULN-002"
SOP_AI_MISUSE = "SOC-SOP-AI-001"
SOP_OT_ACCESS = "SOC-SOP-OT-004"
STD_ROUTER_HARDENING = "NET-STD-HARDEN-01"
STD_DETECTION = "DE-STD-001"
ESCALATION_MATRIX = "SOC-ESC-MATRIX-01"
PRIORITY_POLICY = "SOC-POL-PRIO-01"

THREAT_INTEL_SOURCE = "Splunk ES threat lists (Talos feed + internal IOC list)"

# --- Splunk source profile ------------------------------------------------------------------

# The Experience Center environment's own allowlist. Every fixture search still goes through the
# real deterministic validator (``validate_spl``); only the allowlist differs, as it would per
# deployment.
SPL_SOURCE_PROFILE: dict[str, Any] = {
    "allowed_indexes": [
        "netfw", "wineventlog", "vpn", "tacacs", "network", "ot_ids", "aigw", "app", "dlp", "notable",
    ],
    "allowed_sourcetypes": [
        "cisco:ftd",
        "wineventlog:security",
        "cisco:asa",
        "tacacs:accounting",
        "cisco:ios",
        "ot:ids",
        "aigw:request",
        "app:toolcall",
        "dlp:event",
        "stash",
    ],
    "allowed_commands": ["search", "stats", "where", "table", "fields", "sort", "dedup", "rename", "eval", "bin", "head"],
}

# --- Priority policy (SOC-POL-PRIO-01) -----------------------------------------------------

ASSET_TIER_LABEL = {0: "Tier-0", 1: "Tier-1", 2: "Tier-2"}

_EVIDENCE_LABEL = {
    "confirmed_compromise": "compromise confirmed",
    "exploitation_confirmed": "exploitation confirmed",
    "unexplained_access": "unexplained access, no compromise confirmed",
    "exposure": "exposed, no exploitation confirmed",
    "unauthorized_change": "unauthorized change, cause not yet known",
    "attempted_misuse": "attempted misuse, no data or access gained",
    "benign": "explained and expected",
}

THREAT_ASSESSMENTS = frozenset({"Confirmed", "Suspected", "Unconfirmed", "Benign", "Insufficient evidence"})


def incident_priority(*, asset_tier: int, evidence_state: str) -> dict[str, str]:
    """Deterministic incident priority from asset criticality and evidence (SOC-POL-PRIO-01).

    Priority says how fast the SOC must act; it is not a verdict on the threat.
    """
    if evidence_state not in _EVIDENCE_LABEL:
        raise ValueError(f"unknown evidence_state: {evidence_state}")
    critical = asset_tier in (0, 1)
    if evidence_state in {"confirmed_compromise", "exploitation_confirmed"} and critical:
        priority, rule = "P1", 1
    elif evidence_state in {"unexplained_access", "exposure", "unauthorized_change"} and critical:
        priority, rule = "P2", 2
    elif evidence_state == "benign":
        priority, rule = "P4", 4
    else:
        priority, rule = "P3", 3
    tier = ASSET_TIER_LABEL.get(asset_tier, f"Tier-{asset_tier}")
    return {
        "priority": priority,
        "rule": f"{PRIORITY_POLICY} rule {rule}",
        "basis": f"{tier} asset · {_EVIDENCE_LABEL[evidence_state]}",
    }


# --- Time tokens ----------------------------------------------------------------------------

_DAY_TOKEN = re.compile(r"\{D(-?\d+)(?: (\d{2}:\d{2}))?\}")
_WINDOW_TOKEN = re.compile(r"\{W(\d+)\}")


def _day(now: datetime, offset: int) -> datetime:
    return now + timedelta(days=offset)


def render_time_tokens(text: str, *, now: datetime | None = None) -> str:
    """``{D-9}`` → ``16 Sep``; ``{D-9 03:12}`` → ``16 Sep 03:12``; ``{W30}`` → ``26 Aug – 25 Sep``."""
    if "{" not in text:
        return text
    current = now or datetime.now(timezone.utc)

    def day(match: re.Match[str]) -> str:
        rendered = _day(current, int(match.group(1))).strftime("%d %b").lstrip("0")
        return f"{rendered} {match.group(2)}" if match.group(2) else rendered

    def window(match: re.Match[str]) -> str:
        start = _day(current, -int(match.group(1))).strftime("%d %b").lstrip("0")
        end = current.strftime("%d %b").lstrip("0")
        return f"{start} – {end}"

    return _WINDOW_TOKEN.sub(window, _DAY_TOKEN.sub(day, text))


def render_tokens_deep(value: Any, *, now: datetime | None = None) -> Any:
    """Render time tokens in every string of a JSON-like structure (copy, not in place)."""
    current = now or datetime.now(timezone.utc)
    if isinstance(value, str):
        return render_time_tokens(value, now=current)
    if isinstance(value, list):
        return [render_tokens_deep(item, now=current) for item in value]
    if isinstance(value, tuple):
        return tuple(render_tokens_deep(item, now=current) for item in value)
    if isinstance(value, dict):
        return {key: render_tokens_deep(item, now=current) for key, item in value.items()}
    return value
