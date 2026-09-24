"""S4 CIO layer — zero-day on internet-facing VPN gateways with no playbook."""

from __future__ import annotations

from app.demo.ec_agent.cio_content import CioContent, register_cio_content
from app.demo.fixtures.s4.pack import S4_SCENARIO_ID

S4_CIO_CONTENT = CioContent(
    scenario_id=S4_SCENARIO_ID,
    opening_narrative=(
        "My plan for the VPN zero-day: find which internet-facing gateways run affected firmware, "
        "look for signs of exploitation in Splunk, check what detection and playbook coverage we "
        "already have, and pull our incident-response and hardening guidance. We have no "
        "playbook for this, so I will build the response from those pieces. Nothing runs until "
        "you approve."
    ),
    step_why={
        "identify_gateways": {
            "rationale": "The exposure is limited to internet-facing gateways; we need the exact list before anything else.",
            "decides": "The scope of everything that follows.",
            "if_skipped": "We would patch or restrict blindly.",
        },
        "check_versions": {
            "rationale": "Only gateways on affected firmware are vulnerable; the rest need no emergency change.",
            "decides": "Which gateways enter the emergency patch scope.",
            "if_skipped": "Emergency changes would hit gateways that do not need them.",
        },
        "hunt_iocs": {
            "rationale": "A vulnerable gateway is not a compromised one; we look for exploitation before assuming it.",
            "decides": "Exposure-driven response vs compromise response.",
            "if_skipped": "We could miss an active intrusion.",
        },
        "auth_anomalies": {
            "rationale": "Exploits of VPN management planes usually show up as unusual admin logons.",
            "decides": "Which gateways need compromise review.",
            "if_skipped": "Quiet exploitation could go unseen.",
        },
        "auth_deep_dive": {
            "rationale": "Added because the hunt showed unusual management activity on 2 gateways; those need a closer look than the rest.",
            "decides": "Whether VPN-GW-01/02 move from 'vulnerable' to 'under compromise review'.",
            "if_skipped": "The two riskiest gateways would be treated like the others.",
        },
        "splunk_detections": {
            "rationale": "Tells leadership whether we would see a second attempt.",
            "decides": "Whether a temporary detection is needed now.",
            "if_skipped": "We would not know we are blind.",
        },
        "soar_playbooks": {
            "rationale": "No VPN zero-day playbook exists, so we reuse the closest emergency runbooks rather than improvise.",
            "decides": "Which runbook steps we adopt.",
            "if_skipped": "The response would be improvised.",
        },
        "ir_guidance": {
            "rationale": "Sev-1 procedure and temporary hardening controls are the policy basis for containment.",
            "decides": "Which compensating controls are approved.",
            "if_skipped": "Containment would not be policy-backed.",
        },
        "agilus_patch_analysis": {
            "rationale": "Agilus holds the vendor emergency-patch catalog; it confirms which build fixes which gateway.",
            "decides": "The exact patch and gateway list for the change ticket.",
            "if_skipped": "The patch request would rest on CMDB versions alone.",
        },
        "restrict_wan": {
            "rationale": "The vulnerability is in the WAN management listener; turning it off closes the attack path today, before the patch.",
            "reversible": "Yes — the listener can be re-enabled after patching.",
            "approver": "Network operations (change window)",
            "risk_if_skipped": "All 4 gateways stay exploitable until the patch lands.",
        },
        "enforce_mfa": {
            "rationale": "If admin credentials were harvested, step-up MFA stops them being reused.",
            "reversible": "Yes — conditional-access policy can be rolled back.",
            "approver": "Identity / IAM owner",
            "risk_if_skipped": "Stolen credentials remain usable.",
        },
        "create_incident": {
            "rationale": "A Sev-1 exposure on the perimeter needs a P1 record and a named owner.",
            "reversible": "Yes — can be downgraded.",
            "approver": "SOC lead",
            "risk_if_skipped": "No single owner for a multi-team response.",
        },
        "compromise_assessment": {
            "rationale": "Investigation flagged VPN-GW-01/02 for deeper review. Logs and a configuration snapshot must be captured before patching, because the patch reboot destroys volatile evidence.",
            "reversible": "Yes — read-only collection.",
            "approver": "SOC lead",
            "risk_if_skipped": "If they were compromised, patching first erases the evidence.",
        },
        "rotate_admin_creds": {
            "rationale": "Unusual admin activity on GW-01/02 means their admin credentials must be treated as exposed.",
            "reversible": "No — old credentials are revoked.",
            "approver": "Network operations + IAM",
            "risk_if_skipped": "An attacker holding those credentials keeps access after patching.",
        },
        "create_change": {
            "rationale": "Emergency patching still goes through change control, with rollback defined.",
            "reversible": "Yes — the change can be rejected or rolled back.",
            "approver": "Change advisory (emergency)",
            "risk_if_skipped": "An unmanaged change on perimeter devices.",
        },
        "submit_patch": {
            "rationale": "Agilus schedules the vendor emergency build on the 4 affected gateways once the change is approved.",
            "reversible": "Yes — rollback image kept by Agilus.",
            "approver": "Network operations (change approval)",
            "risk_if_skipped": "The vulnerability stays open.",
        },
        "deploy_monitoring": {
            "rationale": "No advisory-specific detection exists; a temporary alert covers the gap until the vendor ships one.",
            "reversible": "Yes — the alert is time-boxed.",
            "approver": "Detection engineering",
            "risk_if_skipped": "A second exploitation attempt would not alert.",
        },
        "notify_stakeholders": {
            "rationale": "Network and SOC owners must know the exposure, the controls and the timeline.",
            "reversible": "No — once sent, an email cannot be recalled.",
            "approver": "SOC analyst (explicit Send)",
            "risk_if_skipped": "Teams act on different information.",
        },
    },
    executive_brief={
        "investigation": {
            "verdict": "4 of 12 internet-facing VPN gateways are vulnerable. No exploitation confirmed, but 2 show unusual admin activity.",
            "business_impact": "Remote access for staff runs through these gateways. Exploitation would give an attacker a foothold inside the network perimeter.",
            "risk_from": "HIGH",
            "risk_to": "HIGH",
            "confidence": "82% — 7 days of Splunk telemetry; nothing before that window was reviewed.",
            "would_change_if": "The compromise review on VPN-GW-01/02 finds attacker activity → escalate to a confirmed breach.",
            "decision_needed": "Approve emergency containment: turn off WAN management, step-up MFA, a compromise review of 2 gateways, and the emergency patch.",
            "will_not_do": "Take the VPN offline — staff access continues while controls reduce exposure.",
        },
        "complete": {
            "verdict": "Exposure reduced: WAN management restricted, MFA tightened, evidence captured, patch scheduled. 2 gateways still under compromise review.",
            "business_impact": "VPN stays in service. The remaining risk window is until the patch is deployed.",
            "risk_from": "HIGH",
            "risk_to": "MEDIUM",
            "confidence": "82% — rises when the compromise review completes.",
            "would_change_if": "The compromise review finds attacker activity.",
            "decision_needed": "Approve the emergency patch window (change CHG-29173).",
            "will_not_do": "Declare the exposure closed before the patch is verified.",
        },
    },
)

register_cio_content(S4_CIO_CONTENT)
