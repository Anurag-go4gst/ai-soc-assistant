# OT PowerGrid (Google-25) testing-ground findings

Date: 2026-06-18. Branch: `cp-cyclic-evidence-loop`.

The 25 OT-generic power-sector questions (Google list, Cisco plan Part 10.3) were run
through the **live deterministic `/chat` pipeline** (MCP execution off, review-only) as a
probe corpus to find genuine coverage bugs vs by-design gaps. Bank:
[`ot_powergrid_question_bank.json`](ot_powergrid_question_bank.json). This is a
testing-ground artifact, **not** a governance commit gate.

## Result: 15/25 produce an analyst artifact (was 9/25 before fixes)

### Fixed — 6 mis-routes (machinery existed, paraphrase miss)

These had a real detection family / metadata path but analyst wording missed the
runtime-map match. Fix = analyst paraphrase aliases on the existing Cisco runtime-map
entries (`cisco_question_runtime_map_v1.json`), picked up by the semantic index.

| Q | Topic | Now routes to |
|---|-------|---------------|
| g25.002 | IT→OT Purdue crossing | `cisco_it_to_ot_crossing` (perim.001) → SPL |
| g25.007 | out-of-hours SLDC login | `cisco_vpn_after_hours_login` (identity.014) → SPL |
| g25.012 | detection macros/saved searches | `environment_hygiene` → `splunk_get_knowledge_objects` |
| g25.018 | OT index/sourcetype check | `environment_hygiene` → `splunk_get_indexes` |
| g25.024 | outbound non-India geo | `cisco_firewall_geo_egress` (perim.006) → SPL |
| g25.025 | Splunk cluster status | `environment_hygiene` → `splunk_get_info` |

### Already working — 9 (SPL/draft via use-case catalogue)

g25.001 (stealthwatch scan), g25.003 (CERT-In hash), g25.008 (TFTP HMI), g25.010
(cleartext to RTU), g25.011 (DNS tunneling), g25.013 (firewall deny spike), g25.016
(credential dumping), g25.017 (exfil volume), g25.023 (IEC-104/master spoof).

### By-design gaps — 10 (no dedicated family; honest knowledge_recall + HIL)

No OT-protocol template exists; pipeline returns review-only guidance / clarification
(never a fabricated or silently-wrong answer). Closing these needs **new Tier-1 draft
families** (follow-on, not a routing fix):

| Q | Topic | Needed |
|---|-------|--------|
| g25.004 | SCADA default credentials | default-cred login family |
| g25.005 | Modbus non-502 port | OT protocol-port family |
| g25.006 | smart meter / AMI firmware | AMI firmware family |
| g25.009 | RTU connection drops | ICCP/RTU drop-rate family (iccp_disconnect is ICCP-specific) |
| g25.014 | vendor VPN concurrent logins | impossible-travel/concurrent-session family (deferred in plan) |
| g25.015 | DNP3 function codes | DNP3 family |
| g25.019 | PLC stop/program mode | PLC mode-change family |
| g25.020 | PMU stream gaps | PMU stream-gap family |
| g25.021 | OT DMZ firewall policy change | firewall config-change family |
| g25.022 | AD account creation 4720 | Windows 4720 account-creation family |

## Posture

All 25 stay review-only: `execution_enabled=false`, no live rows, MITRE candidate-only.
The 6 fixes added only paraphrase aliases (no new families, no new flags). Cisco-50 gate
stays 50/50; full backend suite + governance regression green.
