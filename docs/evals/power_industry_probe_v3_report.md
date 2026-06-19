# Power Industry Probe Report

Bank: **Power Industry Probe Bank v3 (10)** | Questions: **10**

## Quality flags (heuristic)

- `thin_answer`: 10
- `no_spl_no_checklist`: 10
- `human_review_only`: 10
- `scorecard_fail`: 0
- `guided_path`: 0

## Per-question results

### pk.001 — Ransomware on IT, isolate OT decision
**Tier:** T2 | **Stress:** containment_action_request + safety_critical

> Ransomware just hit our corporate IT domain controller. Should we isolate the OT network from IT right now, and what exact steps should the SOC take to protect the SCADA environment without tripping the grid?

- Skill: `None` | Mode: `clarification` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

No containment or enforcement action was performed. Change approval and human-in-the-loop (HIL) review are required before any block, disable, quarantine, or firewall change. I can provide investigation guidance only — automated enforcement is blocked and not authorized.

### pk.002 — CISA/threat-intel advisory exposure
**Tier:** T2 | **Stress:** ti_advisory_to_detection_mapping

> A new advisory says the VOLTZITE actor is targeting electric utilities with living-off-the-land techniques on grid OT. Based on what we log today, are we exposed and what should we hunt for?

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=True) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm asset criticality and ownership.
- Review correlated authentication and endpoint telemetry.
- Collect timeline context before severity or MITRE claims.

### pk.003 — CEA / CERT-In incident reporting obligation
**Tier:** T2 | **Stress:** regulatory_reporting + non_technical

> We confirmed unauthorized access to a substation HMI. Do we have to report this to CERT-In or under the CEA cyber security guidelines, and within what timeline?

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=True) | Checklist: 0 | Actions: 0
- Human review: True (precondition_review) | Scorecard: `review`

**Summary excerpt:**

Governed SPL draft ready. It has passed deterministic validation and has not been executed.

### pk.004 — OT log-source silence / visibility gap
**Tier:** T1/T2 | **Stress:** log_source_health + coverage_gap

> Which of our OT assets and substation log sources have stopped sending events to Splunk in the last 7 days, so I know my blind spots before the audit?

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=False) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

SOC review checklist:
- Confirm the Cisco product source and normalize source/destination/action fields before using this draft.
- Narrow to the row's Cisco product family when the Environment KB has product-specific indexes.
- Use this as triage scaffolding only; promote repeated rows to a governed template after COE review.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.

### pk.005 — Baseline request for threshold tuning
**Tier:** T1/T2 | **Stress:** baselining_request + not_a_hunt

> What does normal Modbus polling volume look like for our boiler PLCs over a typical week, so I can set a sensible alert threshold for abnormal control traffic?

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.

### pk.006 — Multi-stage timeline reconstruction
**Tier:** T2 | **Stress:** incident_timeline + cross_event_chronology

> Reconstruct a timeline from the vendor VPN login at 02:14, the OT jump-host RDP session, and the relay configuration change, and tell me if these three events are causally linked.

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=False) | Checklist: 0 | Actions: 0
- Human review: True (spl_source_profile_clarification) | Scorecard: `review`

**Summary excerpt:**

SOC review checklist:
- Confirm approved corporate IT and OT zone labels or CIDR ranges.
- Identify source IT hosts and destination OT/control-room assets.
- Review firewall rule name, action, app, protocol, destination port, and session state.
- Compare traffic with approved change or maintenance window.
- Escalate if traffic is unauthorized, recurring, high-volume, or targets critical OT assets.
- Do not declare compromise from firewall traffic alone.
This draft is scoped to allowed/established traffic. If you want all attempts, including denied/blocked traffic, remove or adjust the action/session-state filters during SOC review.

### pk.007 — Rogue wireless AP near control building
**Tier:** T2 | **Stress:** wireless_physical + out_of_splunk_comfort_zone

> Our wireless IDS flagged a rogue Wi-Fi access point broadcasting near the substation control building. How does the SOC determine if this is a bridge into the OT network?

- Skill: `None` | Mode: `clarification` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

SOC review checklist:
- Confirm the Cisco product source and normalize source/destination/action fields before using this draft.
- Narrow to the row's Cisco product family when the Environment KB has product-specific indexes.
- Use this as triage scaffolding only; promote repeated rows to a governed template after COE review.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.

### pk.008 — Insider relay-config exfil before resignation
**Tier:** T2 | **Stress:** insider_threat + identity_plus_egress

> A protection engineer who just resigned downloaded the entire relay configuration repository to a personal device last week. How do we investigate potential insider data theft of grid protection settings?

- Skill: `None` | Mode: `live_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `review`

**Summary excerpt:**

Governed SPL drafting is in review-only mode for this search request. Confirm index, sourcetype, key fields, and time range if a template is not yet bound.

### pk.009 — Firmware supply-chain cert anomaly at scale
**Tier:** T2 | **Stress:** supply_chain_integrity + scale

> A vendor pushed a firmware update signed with an unexpected code-signing certificate to 40 RTUs overnight. How do we determine whether this is a legitimate vendor key rotation or a supply-chain compromise?

- Skill: `None` | Mode: `clarification` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

No — not enough to confirm from this question alone. Any MITRE mapping remains candidate or requires validation until source-grounded evidence is reviewed. Investigation step: corroborate logs, confirm asset context, build a timeline, and validate across independent signals. Do not claim compromise without collected, validated search results.

### pk.010 — Frequency-control command anomaly (AGC)
**Tier:** T2 | **Stress:** process_aware_anomaly + grid_physics

> We saw automatic generation control setpoint commands that would have pushed grid frequency outside the 49.9-50.1 Hz band. Hunt for whether these AGC commands were legitimate dispatch or injected, and what evidence separates the two.

- Skill: `None` | Mode: `guided_investigation` | Support: `None`
- SPL: False (approved=None) | Checklist: 0 | Actions: 0
- Human review: True (execution_approval) | Scorecard: `pass`

**Summary excerpt:**

SOC review checklist:
- Review with grid operations before treating frequency deviations as security incidents.
Lab-only draft SPL preview. Not governed, not approved, not executed. HIL/SOC review is required before any future execution path.
