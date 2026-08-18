"""EC outbound email drafts follow SOC coordination SOP structure."""

from __future__ import annotations

from app.demo import ec_email_drafts
from app.demo.ec_mcp_lifecycle_fixture import PRIMARY_ATTACKER_IP
from app.demo.fixtures.s1.pack import _ACCOUNT, _HOST_B, _HOST_C, _JUMP
from app.demo.fixtures.s3.pack import _PROCESS_FIELDS


def test_s1_firewall_email_includes_sop_and_ticket_sections() -> None:
    extra = ec_email_drafts.s1_firewall_team_email(
        applied=["create_incident_ticket"],
        jump=_JUMP,
        host_b=_HOST_B,
        host_c=_HOST_C,
        account=_ACCOUNT,
        ticket_executed=False,
    )
    body = extra["email"]["body"]
    assert "Firewall Change & SOC Coordination SOP" in body
    assert "TICKET STATUS" in body
    assert PRIMARY_ATTACKER_IP in body
    assert "CONFIRMED FINDINGS" in body
    assert "REQUESTED ACTION" in body
    assert "Outbound coordination controls" in body


def test_s3_firewall_email_includes_mandatory_process_fields() -> None:
    extra = ec_email_drafts.s3_firewall_block_request_email(process_fields=_PROCESS_FIELDS, applied=[])
    body = extra["email"]["body"]
    assert "MANDATORY REQUEST FIELDS" in body
    assert _PROCESS_FIELDS["malicious_ip"] in body
    assert "Firewall-Block Process" in body


def test_s3_soc_lead_email_includes_escalation_sections() -> None:
    extra = ec_email_drafts.s3_soc_lead_email(applied=["ingest_firewall_reply"], process_fields=_PROCESS_FIELDS)
    body = extra["email"]["body"]
    assert "SOC Lead" in body
    assert "Escalation" in body or "escalation" in body.lower()
    assert PRIMARY_ATTACKER_IP in body
    assert "whitelisted" in body.lower()


def test_s6_owner_email_mentions_closed_and_updated() -> None:
    body = ec_email_drafts.s6_incident_owner_email(applied=["update_incident_ticket"])["email"]["body"]
    assert "CLOSED" in body
    assert "UPDATED" in body
    assert "INC-VPN-0712" in body
