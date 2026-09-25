"""S3 — carry out an approved perimeter block through the firewall-change process."""

from __future__ import annotations

from app.demo import ec_environment as E
from app.demo.ec_agent.spec_engine import Action, Check, Email, ScenarioSpec

IP = E.EXTERNAL_IP

S3 = ScenarioSpec(
    scenario_id="s3_firewall_team_coordination",
    family="s3_firewall_coordination",
    label="S3 · Firewall block with the network team",
    question=(
        "The external IP on our jump-host incident has been confirmed malicious and the SOC lead has approved a "
        "block. Follow our firewall-block process and coordinate the block with the network team."
    ),
    legacy_phrasings=(
        "Malicious activity from 198.51.100.42 is confirmed. Follow our company's firewall-block process and coordinate the block with the firewall team.",
    ),
    demo_order=3,
    plan_title="Approved perimeter block — plan ready",
    plan_intro=(
        f"I'll check what our block process requires, what else uses {IP}, and how the edge firewall is "
        "configured today. Nothing changes until you approve."
    ),
    checks=(
        Check(
            id="block_process",
            title="What does our block process require?",
            plan=f"Retrieve {E.SOP_FIREWALL_BLOCK}.",
            tool="soc_kb",
            operation=f"soc_kb.retrieve · {E.SOP_FIREWALL_BLOCK}",
            result=(
                f"{E.SOP_FIREWALL_BLOCK}: block the single address (/32) under an emergency change, tell affected "
                "owners, and verify on the device and in the logs."
            ),
            evidence=(
                f"{E.SOP_FIREWALL_BLOCK} §2–§4, approved version 2026.1",
                f"Approval: SOC lead, recorded on {E.INCIDENT_S1}",
            ),
        ),
        Check(
            id="what_else_uses_ip",
            title="What legitimate traffic would the block stop?",
            plan=f"Search the last 7 days of allowed traffic from {IP}.",
            tool="splunk_mcp",
            spl=(
                f'search index=netfw sourcetype=cisco:ftd src_ip="{IP}" action=allowed earliest=-7d latest=now '
                "| stats count as connections by dest_ip, dest_port | head 50"
            ),
            result=(
                f"Besides its connections to {E.JUMP_HOST}, {IP} carries about 18% of the partner's API calls to {E.API_GATEWAY}. "
                "The partner's other 2 addresses carry the rest."
            ),
            evidence=(
                f"{E.API_GATEWAY}:443 — 12,406 calls in 7 days from {IP}",
                "Impact: the partner loses one of 3 outbound addresses; the tracking API keeps working",
            ),
            attention="ATTENTION",
        ),
        Check(
            id="firewall_config",
            title="How is the edge firewall configured today?",
            plan=f"Read the current rules on {E.EDGE_FIREWALL}/02.",
            tool="agilus_mcp",
            operation=f"agilus.read_device_config · {E.EDGE_FIREWALL}, FW-EDGE-02",
            result=(
                f"No block exists for {IP}. Rule ACL-PARTNER-0147 still allows the partner's addresses into the whole "
                "admin subnet."
            ),
            evidence=(
                "Config read from both HA members; running and saved config match",
                f"ACL-PARTNER-0147: {E.PARTNER_EGRESS_GROUP} (3 addresses) → 10.20.1.0/24 and {E.API_GATEWAY}, port 443",
            ),
        ),
    ),
    conclusion_headline=(
        f"Ready to block: {IP} can be blocked on its own with limited partner impact, and the over-wide partner "
        "rule should be narrowed in the same change."
    ),
    points=(
        f"The block is scoped to {IP}/32, as {E.SOP_FIREWALL_BLOCK} requires.",
        f"Narrowing ACL-PARTNER-0147 to {E.API_GATEWAY} closes the path that let the partner's addresses reach the jump host.",
        "The partner must be told, because one of their outbound addresses stops working.",
    ),
    unresolved=("Whether the partner's host at this address is compromised — the partner has to investigate.",),
    threat="Confirmed",
    asset_tier=0,
    evidence_state="confirmed_compromise",
    subject=f"{IP} on {E.EDGE_FIREWALL}/02",
    existing_incident=E.INCIDENT_S1,
    decision=(
        f"Proposed: raise an emergency change, apply the block and the rule narrowing through Agilus under that "
        f"change, tell Network Operations and the partner's owner, and update {E.INCIDENT_S1}."
    ),
    actions=(
        Action(
            id="raise_change",
            title="Raise the emergency change",
            proposal=f"ITSM emergency change: block {IP}/32 and limit ACL-PARTNER-0147 to {E.API_GATEWAY}. Rollback: remove the block object.",
            tool="itsm",
            verb="change",
            ticket_id=E.CHANGE_S3_BLOCK,
            ticket_summary="Block 3.110.47.92/32; limit ACL-PARTNER-0147 to APIGW-01",
            assignment_group="Network Operations",
            executed=f"Emergency change {E.CHANGE_S3_BLOCK} raised and approved by the SOC lead",
        ),
        Action(
            id="apply_block",
            title="Apply the block and narrow the partner rule",
            proposal=f"Agilus pushes the two rule changes to {E.EDGE_FIREWALL}/02 under the emergency change.",
            tool="agilus_mcp",
            verb="agilus_change",
            executed=f"Block and rule change applied on {E.EDGE_FIREWALL}/02 under {E.CHANGE_S3_BLOCK}",
            verified=f"Agilus config read shows both rules; Splunk shows only blocked connections from {IP} since the change",
        ),
        Action(
            id="notify_owners",
            title="Tell Network Operations and the partner's owner",
            proposal="Short email to Network Operations and the Integration team.",
            tool="email",
            verb="email",
            email=Email(
                to="Network Operations",
                mailbox="NETWORK_TEAM",
                cc="Integration team",
                cc_mailbox="INCIDENT_OWNER",
                subject=f"[{{incident}}] {IP} blocked at the edge firewall",
                body=(
                    "You're receiving this because change {ticket:raise_change} changes the edge firewall"
                    f" and affects "
                    f"partner {E.PARTNER_ID}.\n\n"
                    f"What changed: {IP} is blocked on {E.EDGE_FIREWALL}/02, and ACL-PARTNER-0147 now allows the "
                    f"partner's addresses to {E.API_GATEWAY} only. Reason: an unauthorised {E.SVC_NETOPS} login from this "
                    "address.\n\n"
                    "Please:\n"
                    "1. Integration team — tell the partner their address is blocked and ask them to investigate "
                    "that host.\n"
                    "2. Network Operations — confirm the partner API still works from their other addresses.\n\n"
                    "{tickets}\n\n"
                    "SOC Tier 2"
                ),
            ),
            executed="Sent to Network Operations, cc Integration team",
            status_after="AWAITING_REPLY",
        ),
        Action(
            id="update_incident",
            title=f"Update {E.INCIDENT_S1}",
            proposal="Record the change, the verification and the partner notice on the incident.",
            tool="itsm",
            verb="ticket_update",
            executed=f"{E.INCIDENT_S1} updated with {E.CHANGE_S3_BLOCK} and the verification",
            verified="read back from ITSM",
        ),
    ),
    final_state="CONTAINED — BLOCK VERIFIED",
    final_headline=f"{IP} blocked and the partner rule narrowed; both verified on the firewall and in Splunk.",
    pending=("Partner to investigate their host", "Network Operations to confirm the partner API is unaffected"),
    next_triggers=f"Keep {E.INCIDENT_S1} open until the partner reports on their host and IAM confirms the {E.SVC_NETOPS} reset.",
)
