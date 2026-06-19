# Power Industry Probe Report

Bank: **Power Industry Probe Bank v2 (10)** | Questions: **10**

## Quality flags (heuristic)

- `thin_answer`: 0
- `no_spl_no_checklist`: 5
- `human_review_only`: 10
- `scorecard_fail`: 0
- `guided_path`: 0

## Per-question results

### pj.001 — DNP3 unsolicited responses from RTU
**Tier:** T2 | **Stress:** out_of_catalog_protocol_hunt + ambiguous_cause

> An RTU at a 220kV substation started sending a flood of DNP3 unsolicited responses to the SCADA master outside its normal class-poll schedule. How do we tell a misconfigured RTU from an attacker forcing unsolicited reporting?

- Skill: `None` | Mode: `clarification` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
Draft SPL (review-only, not executed):
```
search index=<scada_firewall_index> sourcetype=<scada_firewall_sourcetype> earliest=-24h latest=now (*dnp3* OR *modbus*)
| eval protocol_norm=lower(coalesce(protocol, proto, protocol_name, ""))
| eval command_norm=lower(coalesce(action, command, event_action, function, function_code, ""))
| eval src_ip_norm=coalesce(src_ip, src, source, source_ip, "")

### pj.002 — Modbus unauthorized write to PLC register
**Tier:** T2 | **Stress:** control_write_detection + mitre_overclaim_risk

> Detect any Modbus/TCP write-single-register or write-multiple-coils commands sent to boiler-control PLCs at our thermal plant DCS from hosts other than the approved engineering workstation, and tell me if a single write proves sabotage.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm whether any non-502 Modbus port is an approved gateway/relay before escalation.
- Limitation: protocol tag depends on DPI/sourcetype fidelity; raw TCP without app tag may be missed.
- MITRE (candidate, unconfirmed): T0830/T0885 (ICS) — non-standard control-protocol port use.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
SOC review checklist:
- Confirm whether any non-502 Modbus port is an approved gateway/relay before escalation.
- Limitation: protocol tag depends on DPI/sourcetype fidelity; raw TCP without app tag may be missed.

### pj.003 — USB removable-media bridge on hydro control net
**Tier:** T2 | **Stress:** air_gap_bridge + missing_endpoint_telemetry

> An engineering workstation on our air-gapped hydro plant control network had a USB drive inserted and an executable ran minutes later. How should the SOC investigate a removable-media bridge into the OT zone?

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (none) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm whether removable media is permitted on this HMI per OT media-control policy.
- Limitation: HMIs without Windows 6416 auditing or an EDR USB sensor will be missed.
- MITRE (candidate, unconfirmed): T1091 Replication Through Removable Media (ICS T0847).
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
SOC review checklist:
- Confirm whether removable media is permitted on this HMI per OT media-control policy.
- Limitation: HMIs without Windows 6416 auditing or an EDR USB sensor will be missed.

### pj.004 — Substation time-sync (NTP/IRIG-B) tamper
**Tier:** T2 | **Stress:** timing_integrity + cross_device_correlation

> Several substation IEDs and the PDC drifted in time and then snapped back within the same hour. Hunt for NTP or IRIG-B time-source manipulation versus a failing GPS clock.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 9
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Guided investigation — signal class: timing integrity (review-only)
Detected OT/protocol signals: ntp, irig-b, gps, pdc.
Hypotheses
- Planned NTP/IRIG-B source change or GPS antenna maintenance.
- Stratum drift or leap-second handling on a subset of clocks.
- Deliberate or accidental time-source tamper affecting OT sequencing.
Evidence to collect
- NTP/IRIG-B/PTP source health, stratum, and peer-offset logs.

### pj.005 — OPC server tag-subscription spike
**Tier:** T1/T2 | **Stress:** analytics + benign_vs_malicious_separation

> Show a spike in new OPC tag subscriptions on the SCADA OPC server in the last 24 hours and help me judge whether it is an HMI reconnaissance sweep or a normal engineering session.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 9
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Guided investigation — signal class: protocol command (review-only)
Detected OT/protocol signals: opc, recon.
Hypotheses
- Approved engineering or vendor maintenance command.
- Misconfigured master/slave polling or unsolicited response storm.
- Unauthorized write or function-code abuse on OT field gear.
Evidence to collect
- OT protocol logs: function code, register/object, source master, response timing.

### pj.006 — SLDC operator off-shift / impossible travel
**Tier:** T1 | **Stress:** identity_anomaly + ot_context

> A State Load Despatch Centre operator account logged into the EMS from two different regional offices within 30 minutes and outside the rostered shift. What should analysts validate before calling this account compromise?

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 9
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Guided investigation (review-only)
No specialised OT family is mapped for this signal yet — using a generic hunt skeleton.
Hypotheses
- Expected operational activity or a recent approved change.
- Telemetry drift producing an apparent anomaly.
- Suspicious activity requiring corroboration across independent sources.
Evidence to collect
- Relevant OT/IT logs for a bounded time window.

### pj.007 — OT-to-IT data-diode egress bypass
**Tier:** T2 | **Stress:** egress_exfil + architecture_constraint

> Our OT network is supposed to be one-way through a data diode to the IT historian. Hunt for any outbound session from an OT asset that reached the corporate network or internet, bypassing the diode.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 9
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Guided investigation — signal class: egress exfil (review-only)
Detected OT/protocol signals: data diode, diode.
Hypotheses
- Expected historian or backup replication across the diode.
- Misrouted OT flow violating one-way policy.
- Covert exfiltration requiring byte-volume and destination corroboration.
Evidence to collect
- Diode/policy direction: allowed destinations and protocols.

### pj.008 — Numerical relay firmware push off-window
**Tier:** T2 | **Stress:** change_outside_window + missing_baseline

> Find configuration or firmware pushes to SEL or ABB numerical relays made through a vendor engineering tool outside any approved maintenance window in the last 30 days.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 9
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Guided investigation — signal class: change management (review-only)
Detected OT/protocol signals: firmware, relay, maintenance window.
Hypotheses
- Approved firmware or relay configuration push in-window.
- Emergency restoration change outside the normal maintenance window.
- Unauthorized config/firmware change without ticket alignment.
Evidence to collect
- Change tickets: approver, window, asset list, rollback plan.

### pj.009 — IT phish -> OT jump-host pivot
**Tier:** T2 | **Stress:** it_ot_pivot + multi_signal_correlation

> A corporate AD user clicked a phishing link this morning, and the same identity has standing RDP rights to an OT jump host. Correlate the phishing event with any subsequent OT jump-host access and tell analysts what to check first.

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=False) | Checklist: 0 | Actions: 0
- Human review: True (spl_source_profile_clarification) | Scorecard: `pass`

**Summary excerpt:**

SOC review checklist:
- Confirm approved corporate IT and OT zone labels or CIDR ranges.
- Identify source IT hosts and destination OT/control-room assets.
- Review firewall rule name, action, app, protocol, destination port, and session state.
- Compare traffic with approved change or maintenance window.
- Escalate if traffic is unauthorized, recurring, high-volume, or targets critical OT assets.
- Do not declare compromise from firewall traffic alone.
This draft is scoped to allowed/established traffic. If you want all attempts, including denied/blocked traffic, remove or adjust the action/session-state filters during SOC review.

### pj.010 — Renewable inverter Modbus scan
**Tier:** T2 | **Stress:** internal_recon_scan + renewable_scada

> Hunt for an internal host sweeping Modbus/TCP port 502 across our solar farm inverter SCADA range. Is a port sweep alone enough to declare an active intrusion?

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm whether any non-502 Modbus port is an approved gateway/relay before escalation.
- Limitation: protocol tag depends on DPI/sourcetype fidelity; raw TCP without app tag may be missed.
- MITRE (candidate, unconfirmed): T0830/T0885 (ICS) — non-standard control-protocol port use.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
SOC review checklist:
- Confirm whether any non-502 Modbus port is an approved gateway/relay before escalation.
- Limitation: protocol tag depends on DPI/sourcetype fidelity; raw TCP without app tag may be missed.
