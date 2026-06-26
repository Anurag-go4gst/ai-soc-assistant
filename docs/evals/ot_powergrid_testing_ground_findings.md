# OT PowerGrid (Google-25) testing-ground findings

Date: 2026-06-18. Branch: `cp-cyclic-evidence-loop`.

The 25 OT-generic power-sector questions (Google list, Cisco plan Part 10.3) were run
through the **live deterministic `/chat` pipeline** (MCP execution off, review-only) as a
probe corpus to find genuine coverage bugs vs by-design gaps. Bank:
[`ot_powergrid_question_bank.json`](ot_powergrid_question_bank.json). This is a
testing-ground artifact, **not** a governance commit gate.

## Result: 25/25 produce a review-only SPL/metadata artifact (was 9/25)

Final: **22 spl_review (incl. 10 via the OT-protocol family pack on the guided path) +
3 metadata_hygiene, 0 bare knowledge_recall.** Three defects fixed: (1) paraphrase
misses, (2) hunt-shaped OT/identity questions dropping to thin `knowledge_recall`
instead of the guided rescue, (3) no draft family for the OT-protocol hunts.

### Defect 3 fix — OT-protocol draft family pack

`backend/app/spl/ot_protocol_families.py` adds 9 tier-1 lab families
(`ot_scada_default_credentials`, `ot_modbus_nonstandard_port`, `ot_ami_firmware_anomaly`,
`ot_rtu_connection_drops`, `ot_dnp3_function_code`, `ot_plc_mode_change`,
`ot_pmu_stream_gap`, `ot_dmz_firewall_policy_change`, `windows_account_creation_4720`)
plus a matcher reuse of `auth_impossible_travel` for concurrent-VPN. Each emits an
aggregated `stats … | head` SPL with placeholder index/sourcetype slots, one analyst
checklist item, one limitation, and one candidate-only MITRE anchor. Review-only:
`execution_eligible=false`, validator blocks only on the unresolved placeholder
index/sourcetype (resolved from the Environment KB), MCP execution off.

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

### Now review-only SPL draft via guided path — 10 (OT-protocol family pack)

These route to `guided_investigation` (SOC-KB RAG grounding + hypotheses + checklist +
weak-case LLM narration when flags/provider on) **and** now carry a concrete review-only
lab SPL draft from the new family pack:

| Q | Topic | Draft family |
|---|-------|--------------|
| g25.004 | SCADA default credentials | `ot_scada_default_credentials` |
| g25.005 | Modbus non-502 port | `ot_modbus_nonstandard_port` |
| g25.006 | smart meter / AMI firmware | `ot_ami_firmware_anomaly` |
| g25.009 | RTU connection drops | `ot_rtu_connection_drops` |
| g25.014 | vendor VPN concurrent logins | `auth_impossible_travel` (reuse) |
| g25.015 | DNP3 function codes | `ot_dnp3_function_code` |
| g25.019 | PLC stop/program mode | `ot_plc_mode_change` |
| g25.020 | PMU stream gaps | `ot_pmu_stream_gap` |
| g25.021 | OT DMZ firewall policy change | `ot_dmz_firewall_policy_change` |
| g25.022 | AD account creation 4720 | `windows_account_creation_4720` |

Drafts are heuristic and placeholder-bound: each carries an explicit limitation (e.g.
default-account / approved-firmware lookups not yet onboarded) and a candidate-only MITRE
anchor. They give analysts a concrete starting query, not a governed detection.

## Posture

All 25 stay review-only: `execution_enabled=false`, no live rows, MITRE candidate-only.
Fixes: paraphrase aliases + an out-of-registry shape-detector branch + 9 tier-1 OT lab
draft families (no new flags, no executability change; lab drafts never enter the MCP
gate). Cisco-50 gate
stays 50/50; full backend suite + governance regression green.
