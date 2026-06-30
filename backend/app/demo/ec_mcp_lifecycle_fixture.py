"""Splunk MCP playbook chronology fixtures for Experience Center (demo-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PLAYBOOK_PATH = Path(__file__).resolve().parents[1] / "connectors" / "mcp" / "mcp_tool_playbook.json"

PRIMARY_ATTACKER_IP = "198.51.100.42"
INCIDENT_ID = "FW-INC-2026-0615"


def load_mcp_playbook() -> dict[str, Any]:
    return json.loads(_PLAYBOOK_PATH.read_text(encoding="utf-8"))


def default_chronology() -> list[str]:
    playbook = load_mcp_playbook()
    return list(playbook.get("default_chronology") or [])


def discovery_only_chronology() -> list[str]:
    return [
        "splunk_get_info",
        "splunk_get_indexes",
        "splunk_get_metadata",
        "splunk_get_knowledge_objects",
    ]


def tool_metadata(tool_name: str) -> dict[str, Any]:
    playbook = load_mcp_playbook()
    tools = playbook.get("tools") or {}
    entry = tools.get(tool_name)
    return dict(entry) if isinstance(entry, dict) else {}


def build_discovery_hops(*, include_search: bool = True, discovery_only: bool = False) -> list[dict[str, Any]]:
  """Ordered discovery hops with redacted outputs for EC governance + progress UX."""
  if discovery_only:
      names = discovery_only_chronology()
  else:
      names = default_chronology()
      if not include_search:
          names = [name for name in names if name != "splunk_run_query"]

  hops: list[dict[str, Any]] = []
  for tool in names:
      meta = tool_metadata(tool)
      hop: dict[str, Any] = {
          "tool": tool,
          "phase": meta.get("phase") or ("search" if tool == "splunk_run_query" else "discovery"),
          "status": "success",
          "when": meta.get("when"),
          "why": meta.get("why"),
          "produces": list(meta.get("produces") or []),
      }
      if tool == "splunk_get_info":
          hop["lines"] = ["Splunk instance reachable · server_name=pgcil-hybrid-01"]
      elif tool == "splunk_get_indexes":
          hop["lines"] = [
              "Index 'pgcil_soc' discovered (Environment KB alias cisco_asa → pgcil_soc).",
          ]
      elif tool == "splunk_get_metadata":
          hop["lines"] = [
              "Sourcetype 'pgcil:firewall' on pgcil_soc.",
              "Sourcetype 'cisco:asa' on pgcil_soc (Env KB mapped from cisco_asa).",
          ]
      elif tool == "splunk_get_knowledge_objects":
          hop["lines"] = [
              "[SUCCESS] Lookup 'power_sector_iocs.csv' (Wave-3 threat intel) discovered.",
          ]
      elif tool == "splunk_run_query":
          hop["lines"] = [
              "Submitting governed search job…",
              "Job dispatchState=DONE · results ready.",
          ]
          hop["input_contract"] = ["search_query", "earliest_time", "latest_time", "max_results"]
      hops.append(hop)
  return hops


def build_mcp_console_lines(hops: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = ["[MCP ACTIVATED] Splunk MCP session ready"]
    for hop in hops:
        tool = str(hop.get("tool") or "")
        lines.append(f"-> Calling tool: {tool}()")
        for detail in hop.get("lines") or []:
            lines.append(f"   [SUCCESS] {detail}")
    return lines


def build_mcp_discovery_context(
    *,
    discovery_only: bool = False,
    include_search: bool = True,
) -> dict[str, Any]:
    hops = build_discovery_hops(discovery_only=discovery_only, include_search=include_search)
    return {
        "indexes": ["pgcil_soc"],
        "index_aliases": {"cisco_asa": "pgcil_soc"},
        "sourcetypes": ["pgcil:firewall", "cisco:asa"],
        "field_hints": {
            "src": "source IP",
            "dest": "destination IP",
            "action": "firewall action",
        },
        "discovery_hops": hops,
        "populated_at_stage": "pre_spl_mcp_discovery",
        "tools_called": [str(hop.get("tool")) for hop in hops if hop.get("tool")],
    }


def build_job_lifecycle(*, sid: str = "demo-sid-fw-0615") -> dict[str, Any]:
    return {
        "sid": sid,
        "poll_states": ["1/3", "2/3", "DONE"],
        "duration_ms": 1840,
        "status": "ok",
    }


def build_ec_stage_latencies(scenario_id: str) -> list[dict[str, Any]]:
    """Per-hop latencies mapped to investigation progress step ids."""
    def _entry(stage: str, ms: int) -> dict[str, Any]:
        return {"stage": stage, "recorded_ms": ms, "replayed_ms": ms}

    base = [
        _entry("query", 420),
        _entry("route", 380),
        _entry("workflow", 520),
    ]
    discovery = build_discovery_hops(
        discovery_only=scenario_id == "splunk_env_asa_ti_readiness",
        include_search=scenario_id not in {"splunk_env_asa_ti_readiness", "firewall_baseline_template_spl"},
    )
    if scenario_id in {
        "firewall_deny_coordinated_attack",
        "network_blast_radius_attacker_ip",
        "successful_login_after_failures",
        "failed_login_spike_app01",
        "dns_beaconing_c2_hunt",
    }:
        base.append(_entry("spl_validation", 640))
    for hop in discovery:
        tool = str(hop.get("tool") or "")
        if tool == "splunk_run_query":
            base.append(_entry("mcp_connect", 1960))
            base.append(_entry("mcp_evidence", 720))
        elif tool in {"splunk_get_info", "splunk_get_indexes", "splunk_get_metadata", "splunk_get_knowledge_objects"}:
            base.append(_entry("mcp_connect", 480))
    base.extend(
        [
            _entry("rag", 360),
            _entry("mitre_severity", 440),
            _entry("llm_governance", 520),
            _entry("package", 380),
        ]
    )
    return base
