"""S7 investigation step findings — derived from EC fixture evidence only."""

from __future__ import annotations

from typing import Any

from app.demo.ec_conflict_s7 import S7_DEVICE

ASSET = S7_DEVICE
IP = "10.80.4.14"


def _complete(applied: list[str], follow_up_id: str) -> bool:
    return follow_up_id in applied


def finding_for_investigation_step(
    step_id: str,
    *,
    status: str,
    applied: list[str] | None = None,
    agent_state: dict[str, Any] | None = None,
    outcome: dict[str, Any] | None = None,
    selected: bool = True,
) -> dict[str, Any] | None:
    del agent_state
    applied = list(applied or [])
    outcome = outcome or {}
    token = status.upper()
    if not selected or token == "SKIPPED":
        return {
            "headline_finding": "Skipped — not included in the approved investigation plan.",
            "headlines_by_status": {
                "QUEUED": "Queued",
                "RUNNING": "Running…",
                "COMPLETE": "Skipped",
            },
            "attention_state": "INFORMATIONAL",
            "evidence_sources": [],
            "caveat": "Skipped steps do not produce attributable findings.",
        }
    if token == "RUNNING":
        return {
            "headline_finding": "Running…",
            "headlines_by_status": {
                "QUEUED": "Queued",
                "RUNNING": "Running…",
                "COMPLETE": "Complete",
            },
            "attention_state": "NORMAL",
            "evidence_sources": [],
        }
    if token not in {"COMPLETE"}:
        return {
            "headline_finding": "Queued — waiting for investigation run",
            "headlines_by_status": {
                "QUEUED": "Queued — waiting for investigation run",
                "RUNNING": "Running…",
                "COMPLETE": "Complete",
            },
            "attention_state": "NORMAL",
            "evidence_sources": [],
        }

    if step_id == "replay_splunk":
        return {
            "headline_finding": f"Unauthorized-access telemetry for {ASSET} / {IP} is present in Splunk",
            "headlines_by_status": {
                "QUEUED": "Queued — replay Splunk OT access events",
                "RUNNING": "Replaying Splunk unauthorized-access telemetry…",
                "COMPLETE": f"Splunk events confirmed for {ASSET}",
            },
            "key_evidence": [
                f"asset={ASSET}",
                f"ip={IP}",
                "signature=unauthorized_ot_access",
            ],
            "confidence": "high",
            "attention_state": "ATTENTION",
            "caveat": "Telemetry confirms activity, not that the CMDB record is wrong, and not a forced incident.",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s7-splunk",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_query",
                },
            ],
        }

    if step_id == "load_cmdb":
        return {
            "headline_finding": f"CMDB lists {ASSET} as retired — sources conflict",
            "headlines_by_status": {
                "QUEUED": "Queued — load CMDB retirement record",
                "RUNNING": "Reading CMDB asset record…",
                "COMPLETE": f"CMDB retired vs Splunk activity — unresolved until inventory",
            },
            "key_evidence": [f"asset={ASSET}", "status=retired"],
            "confidence": "high",
            "attention_state": "RISK",
            "caveat": "A retired CMDB row does not prove the device is gone. No CMDB MCP is onboarded.",
            "evidence_sources": [
                {
                    "source": "CMDB (simulated)",
                    "evidence_id": "ev-s7-cmdb",
                    "provenance": "simulated_mcp",
                    "tool": None,
                },
            ],
        }

    if step_id == "ot_inventory":
        done = _complete(applied, "check_ot_inventory")
        path_b = outcome.get("path") == "B"
        if path_b:
            headline = f"No live asset behind {ASSET} — identity recycled"
        elif done:
            headline = f"OT inventory shows {ASSET} active on cell 4 — CMDB likely stale"
        else:
            headline = "OT inventory not yet queried"
        return {
            "headline_finding": headline,
            "headlines_by_status": {
                "QUEUED": "Queued — check live OT inventory",
                "RUNNING": "Querying OT inventory…",
                "COMPLETE": headline,
            },
            "key_evidence": (
                [f"asset={ASSET}", "status=retired_identity_recycled"]
                if path_b
                else [f"asset={ASSET}", "status=active", "cell=4"]
            ),
            "confidence": "high",
            "attention_state": "NO_MATCH" if path_b else "RISK",
            "evidence_sources": [
                {
                    "source": "OT inventory (simulated)",
                    "evidence_id": "ev-s7-otinv" if done and not path_b else "ev-s7-stale",
                    "provenance": "simulated_mcp",
                    "tool": None,
                },
            ],
        }

    if step_id == "firewall_window":
        done = _complete(applied, "check_firewall_activity")
        return {
            "headline_finding": (
                f"East-west OT allow to {IP} in the same window"
                if done
                else "Firewall window not yet queried"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — check firewall segmentation",
                "RUNNING": "Reading Splunk-indexed OT firewall telemetry…",
                "COMPLETE": f"Allow to {IP} from ot-eng in the investigation window",
            },
            "key_evidence": [f"dest={IP}", "action=allow", "src_zone=ot-eng"],
            "confidence": "high",
            "attention_state": "ATTENTION",
            "evidence_sources": [
                {
                    "source": "Splunk MCP",
                    "evidence_id": "ev-s7-fw",
                    "provenance": "simulated_mcp",
                    "tool": "splunk_run_query",
                },
            ],
        }

    if step_id == "arp_mac":
        done = _complete(applied, "check_arp_mac")
        return {
            "headline_finding": (
                f"MAC 00:1b:44:11:3a:b7 still answering for {IP} on vlan ot-4"
                if done
                else "Switch ARP/MAC not yet queried"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — check switch ARP/MAC",
                "RUNNING": "Reading ARP/MAC table…",
                "COMPLETE": f"{IP} still answering on the OT VLAN",
            },
            "key_evidence": [f"ip={IP}", "mac=00:1b:44:11:3a:b7", "vlan=ot-4"],
            "confidence": "high",
            "attention_state": "ATTENTION",
            "caveat": "No switch/network MCP is onboarded — this is a simulated table read.",
            "evidence_sources": [
                {
                    "source": "Network (simulated)",
                    "evidence_id": "ev-s7-arp",
                    "provenance": "simulated_mcp",
                    "tool": None,
                },
            ],
        }

    if step_id == "stale_identity":
        done = _complete(applied, "confirm_stale_identity")
        return {
            "headline_finding": (
                "Telemetry belongs to a recycled/stale asset identity — no live compromise"
                if done
                else "Recycled-identity path not selected"
            ),
            "headlines_by_status": {
                "QUEUED": "Queued — Path B recycled identity (off by default)",
                "RUNNING": "Checking recycled identity…",
                "COMPLETE": "Recycled identity — not an incident",
            },
            "key_evidence": [f"asset={ASSET}", "status=retired_identity_recycled"],
            "confidence": "high",
            "attention_state": "NO_MATCH" if done else "INFORMATIONAL",
            "evidence_sources": [
                {
                    "source": "OT inventory (simulated)",
                    "evidence_id": "ev-s7-stale",
                    "provenance": "simulated_mcp",
                    "tool": None,
                },
            ]
            if done
            else [],
        }

    return None
