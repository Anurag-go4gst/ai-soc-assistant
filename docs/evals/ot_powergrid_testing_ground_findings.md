# OT PowerGrid (Google-25) testing-ground findings

Date: 2026-06-18. Branch: `cp-cyclic-evidence-loop`.

The 25 OT-generic power-sector questions (Google list, Cisco plan Part 10.3) were run
through the **live deterministic `/chat` pipeline** (MCP execution off, review-only) as a
probe corpus to find genuine coverage bugs vs by-design gaps. Bank:
[`ot_powergrid_question_bank.json`](ot_powergrid_question_bank.json). This is a
testing-ground artifact, **not** a governance commit gate.

## Result: 25/25 land on a useful path (was 9/25)

Final routing: **12 spl_review + 3 metadata_hygiene + 10 guided_investigation, 0 bare
knowledge_recall.** Two defects were fixed: (1) paraphrase misses, and (2) hunt-shaped
OT/identity questions dropping to thin `knowledge_recall` instead of the guided rescue.

### Defect 2 fix — guided routing for detection-imperative hunts

The `soc_investigation_shape` detector required a literal `hunt`/`odd`/`anomaly` word,
so detection-imperative OT asks ("Flag/Detect/Identify <Modbus/DNP3/PLC/PMU …>") and
identity hunts (concurrent-session, AD-4720) fell to `knowledge_recall` with no artifact.
Extended the detector with an OT/ICS + identity-hunt context list gated to a detection
verb — and only consulted on the `out_of_registry` path, so use-case/registry matches are
unaffected. These 10 now reach `guided_investigation`, where SOC-KB RAG grounding + the
weak-case LLM composer engage (when LLM flags + provider are on). This restores the prior
plan's intent: out-of-registry hunt-shaped → guided, so the LLM can use them.



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

### Now guided_investigation — 10 (no dedicated family yet; LLM/RAG engage)

These have no OT-protocol/identity template, so they route to `guided_investigation`:
SOC-KB RAG grounding + hypotheses + analyst checklist, and the weak-case LLM composer
narrates when LLM flags + provider are on. Review-only; never fabricated. A future
Tier-1 draft family would upgrade each from guided hypotheses to a concrete review-only
SPL draft:

| Q | Topic | Future family |
|---|-------|---------------|
| g25.004 | SCADA default credentials | default-cred login family |
| g25.005 | Modbus non-502 port | OT protocol-port family |
| g25.006 | smart meter / AMI firmware | AMI firmware family |
| g25.009 | RTU connection drops | ICCP/RTU drop-rate family |
| g25.014 | vendor VPN concurrent logins | impossible-travel/concurrent-session family |
| g25.015 | DNP3 function codes | DNP3 family |
| g25.019 | PLC stop/program mode | PLC mode-change family |
| g25.020 | PMU stream gaps | PMU stream-gap family |
| g25.021 | OT DMZ firewall policy change | firewall config-change family |
| g25.022 | AD account creation 4720 | Windows 4720 account-creation family |

## Posture

All 25 stay review-only: `execution_enabled=false`, no live rows, MITRE candidate-only.
Fixes added only paraphrase aliases + an out-of-registry shape-detector branch (no new
families, no new flags, no executability change). Cisco-50 gate
stays 50/50; full backend suite + governance regression green.
