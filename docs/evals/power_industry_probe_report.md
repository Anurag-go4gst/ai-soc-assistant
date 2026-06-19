# Power Industry Probe Report

Bank: **Power Industry Probe Bank (10)** | Questions: **10**

## Quality flags (heuristic)

- `thin_answer`: 1
- `no_spl_no_checklist`: 9
- `human_review_only`: 10
- `scorecard_fail`: 0
- `guided_path`: 0

## Per-question results

### pi.001 — GOOSE burst during outage
**Tier:** T2 | **Stress:** compound_ot_protocol + judgment

> Our protection relay at a 400kV substation logged an unexpected GOOSE message burst during a planned outage window. How should grid SOC investigate whether this is misoperation or malicious manipulation?

- Skill: `None` | Mode: `hybrid` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm the Cisco product source and normalize source/destination/action fields before using this draft.
- Narrow to the row's Cisco product family when the Environment KB has product-specific indexes.
- Use this as triage scaffolding only; promote repeated rows to a governed template after COE review.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.

### pi.002 — IEC 61850 MMS unapproved assets
**Tier:** T2 | **Stress:** out_of_catalog_hunt + missing_asset_list

> Find IEC 61850 MMS sessions from engineering laptops that are not on the approved maintenance asset list.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 9
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Guided investigation — signal class: protocol command (review-only)
Detected OT/protocol signals: mms.
Hypotheses
- Approved engineering or vendor maintenance command.
- Misconfigured master/slave polling or unsolicited response storm.
- Unauthorized write or function-code abuse on OT field gear.
Evidence to collect
- OT protocol logs: function code, register/object, source master, response timing.

### pi.003 — vendor VPN + OT firewall correlation
**Tier:** T2 | **Stress:** multi_signal_correlation

> Correlate vendor contractor VPN logins with any OT DMZ firewall policy changes on the same day. What should analysts validate first?

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=True) | Checklist: 0 | Actions: 0
- Human review: True (precondition_review) | Scorecard: `review`

**Summary excerpt:**

Objective: Correlate vendor contractor VPN logins with any OT DMZ firewall policy changes on the same day. What should analysts validate first?
A governed SPL draft was produced and passed deterministic validation; it is review-only and was not executed (MCP execution disabled).
Review steps:
- Confirm the index/sourcetype and field mappings match your deployment before running.
- Validate the time window and any thresholds against the asset baseline.
- Run as review-only first; treat counts as evidence to corroborate, not a verdict.
Limitations: no live results were returned; no severity or MITRE technique is claimed from the draft alone.

### pi.004 — PMU stream gap sabotage hunt
**Tier:** T2 | **Stress:** ambiguous_cause + hunt

> A PMU at our regional control center stopped streaming synchrophasor data for 20 minutes then resumed. Hunt for signs of ingestion sabotage versus upstream network loss.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Correlate stream gaps with PDC health, GPS time-sync loss, or network congestion.
- Limitation: gaps inferred from status fields; true sample-rate gap detection needs PDC counters.
- MITRE (candidate, unconfirmed): T0815 Denial of Service (ICS) — only if gaps are adversary-induced.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
SOC review checklist:
- Correlate stream gaps with PDC health, GPS time-sync loss, or network congestion.
- Limitation: gaps inferred from status fields; true sample-rate gap detection needs PDC counters.

### pi.005 — AMI head-end firmware
**Tier:** T2 | **Stress:** missing_lookup + detection_imperative

> Are there any unapproved firmware downloads initiated from the AMI head-end system in the last week?

- Skill: `None` | Mode: `clarification` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Compare observed firmware versions against the approved baseline per meter model.
- Limitation: 'unauthorized' needs an approved-firmware baseline (lookup pending).
- MITRE (candidate, unconfirmed): T0857 System Firmware (ICS) — confirm only with a change/anomaly signal.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
SOC review checklist:
- Compare observed firmware versions against the approved baseline per meter model.
- Limitation: 'unauthorized' needs an approved-firmware baseline (lookup pending).

### pi.006 — transformer diff alarm attack judgment
**Tier:** T1/T2 | **Stress:** analytics + mitre_overclaim_risk

> Show transformer differential protection alarm spikes across all 400kV bays and tell me if this pattern alone indicates a coordinated attack.

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=True) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Objective: Show transformer differential protection alarm spikes across all 400kV bays and tell me if this pattern alone indicates a coordinated attack.
A governed SPL draft was produced and passed deterministic validation; it is review-only and was not executed (MCP execution disabled).
Review steps:
- Confirm the index/sourcetype and field mappings match your deployment before running.
- Validate the time window and any thresholds against the asset baseline.
- Run as review-only first; treat counts as evidence to corroborate, not a verdict.
Limitations: no live results were returned; no severity or MITRE technique is claimed from the draft alone.

### pi.007 — SCADA historian gap + RDP jump host
**Tier:** T2 | **Stress:** checklist_request + multi_source

> What is the investigation checklist when SCADA historian gaps coincide with new remote desktop sessions on OT jump hosts?

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm approved corporate IT and OT zone labels or CIDR ranges.
- Identify source IT hosts and destination OT/control-room assets.
- Review firewall rule name, action, app, protocol, destination port, and session state.
- Compare traffic with approved change or maintenance window.
- Escalate if traffic is unauthorized, recurring, high-volume, or targets critical OT assets.
- Do not declare compromise from firewall traffic alone.
This draft is scoped to allowed/established traffic. If you want all attempts, including denied/blocked traffic, remove or adjust the action/session-state filters during SOC review.

### pi.008 — IEC-104 rogue master
**Tier:** T2 | **Stress:** out_of_catalog_protocol_hunt

> Hunt for IEC-104 STARTDT or STOPDT command sequences from master stations not listed in our asset CMDB.

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=True) | Checklist: 0 | Actions: 0
- Human review: True (precondition_review) | Scorecard: `review`

**Summary excerpt:**

Asset-scoped investigation — IEC-104 (review-only)
Checklist:
- Pin the investigation to IEC-104: confirm owner, function, zone, and criticality.
- Pull this asset's syslog/event history and compare against its own baseline and peer assets.
- Correlate the anomaly with change tickets, maintenance windows, and recent config/firmware pushes.
- Check upstream access paths (engineering workstation, jump host, vendor session) for the same window.
- Validate time integrity before trusting event ordering on the device.
Judgment: odd syslog on this asset alone does NOT confirm compromise — corroborate across independent signals (access, change, network) before declaring an incident. No MITRE technique or severity is claimed from this question alone.

### pi.009 — EMS portal fail-then-success
**Tier:** T1 | **Stress:** success_after_failure + ot_context

> Compare failed authentication events on the Energy Management System web portal with successful logins from the same source IPs within 15 minutes.

- Skill: `None` | Mode: `clarification` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm the success genuinely followed the failure burst (not interleaved noise).
- Check whether the successful login came from the same source IP/host as the failures.
- Review MFA outcome and device posture for the successful login when available.
- Correlate with password-reset, IdP admin, or lockout events before escalation.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
SOC review checklist:
- Confirm the success genuinely followed the failure burst (not interleaved noise).

### pi.010 — storm restoration remote ops
**Tier:** T2 | **Stress:** benign_vs_malicious_separation

> During storm restoration we see many simultaneous remote switch operations across substations. How do I separate legitimate operator activity from potential unauthorized remote control?

- Skill: `None` | Mode: `clarification` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

Investigation planning is complete. Provide source profile details or run a review-only search when logs are required; no MCP execution was performed.
