"""Batch 0 — intent cascade hardening: 50-Cisco intent distribution gate.

Runs the deterministic intent node (understand_query + build_query_to_intent,
no live LLM) over the 50 Cisco questions and asserts the Engine-3-safe guided
floor eliminated the clarification dump:

- the SOC hunt questions never land on clarification_required, and
- >= 45/50 land in an actionable family.

This is the regression that protects the floor: a future change that re-broadens
the terminal clarification default (or narrows the shape signal) trips here.
"""

from __future__ import annotations

from collections import Counter

from app.chat.intent_classifier import build_query_to_intent
from app.query_understanding.parser import understand_query

# Appendix A — verbatim (id, question, kind). kind: hunt | metadata
CISCO_50 = [
    ("cisco.perim.001", "Show any blocked connection attempts crossing directly from the corporate Cisco VPN pool into the Core SCADA VLAN.", "hunt"),
    ("cisco.perim.002", "Identify any unauthorized OSPF or BGP routing updates detected on Substation router uplink interfaces today.", "hunt"),
    ("cisco.perim.003", "Flag any Cisco Firepower events where cleartext HTTP or VNC sessions were established toward Phase-1 RTUs.", "hunt"),
    ("cisco.perim.004", "List all MAC address flapping or port security violation alerts triggered on Cisco Catalyst switches across Western Grid substations.", "hunt"),
    ("cisco.perim.005", "Identify internal hosts flagged by Cisco Stealthwatch for rapid horizontal scanning within the Substation Automation network.", "hunt"),
    ("cisco.perim.006", "Show all outbound firewall connections originating from the Industrial DMZ to foreign geographic locations.", "hunt"),
    ("cisco.perim.007", "Are there any Security Group Tag (SGT) classification failures on our Cisco identity-defined network borders?", "hunt"),
    ("cisco.perim.008", "Flag any unusual ICMP packet sizes or baseline anomalies originating from critical grid control endpoints.", "hunt"),
    ("cisco.perim.009", "Show the audit trail of any Cisco IOS configuration changes made via SSH to our core substation switches.", "hunt"),
    ("cisco.perim.010", "Identify any substation endpoints bypassing our internal Cisco Umbrella DNS servers to resolve external domains directly.", "hunt"),
    ("cisco.identity.011", "List any technicians who used TACACS+ to elevate privileges to privilege level 15 on any Northern Grid router.", "hunt"),
    ("cisco.identity.012", "Flag any instances where a single MAC address was authenticated via MAB concurrently on two separate Cisco ISE nodes.", "hunt"),
    ("cisco.identity.013", "Identify any engineering workstations that failed Cisco ISE compliance posture checks due to disabled host firewalls.", "hunt"),
    ("cisco.identity.014", "Alert on any OEM vendor accounts logging in via Cisco AnyConnect VPN outside of our pre-approved maintenance change hours.", "hunt"),
    ("cisco.identity.015", "Show accounts triggering repeated Cisco ISE authentication failures across different Substation access points.", "hunt"),
    ("cisco.identity.016", "List all switch interfaces dynamically shut down or quarantined by Cisco ISE due to high-risk malware profiles.", "hunt"),
    ("cisco.identity.017", "Identify any unauthorized rogue wireless client connection logs discovered near the physical Substation control building.", "hunt"),
    ("cisco.identity.018", "Show any Cisco Duo authentication requests that were repeatedly denied by the end-user before a final approval.", "hunt"),
    ("cisco.identity.019", "Flag any endpoints whose device profile dynamically shifted in Cisco ISE from an 'RTU/IED' to a 'Windows/Linux Workstation'.", "hunt"),
    ("cisco.identity.020", "Show all persistent TACACS+ sessions on core grid switches that have remained open for longer than 8 continuous hours.", "hunt"),
    ("cisco.ot.021", "Detect any high-frequency burst patterns in IEC 61850 GOOSE messages, indicating potential message injection or grid physical faults.", "hunt"),
    ("cisco.ot.022", "Flag any manufacturing message specification (MMS) write or delete parameters targeting primary transmission line relays.", "hunt"),
    ("cisco.ot.023", "Show the connection drop frequency of ICCP data links linking our State Load Despatch Center to the National Grid.", "hunt"),
    ("cisco.ot.024", "Identify all Modbus Exception Codes returned by PLCs to map structural system processing errors or active denial of service attempts.", "hunt"),
    ("cisco.ot.025", "Cross-reference active industrial device network banners with our asset lookup file to locate mismatched firmware versions.", "hunt"),
    ("cisco.ot.026", "Flag any non-whitelisted source IP addresses attempting to issue broadcast polling requests to distribution transformers.", "hunt"),
    ("cisco.ot.027", "List all SQL or file database schema updates performed directly on the core Energy Management System (EMS) historical server.", "hunt"),
    ("cisco.ot.028", "Detect any industrial packets containing malformed or unassigned protocol operational code numbers.", "hunt"),
    ("cisco.ot.029", "Show any operational setpoint modifications transmitted to solar grid inverters over the last 24 hours.", "hunt"),
    ("cisco.ot.030", "Identify any cleartext TFTP backup connections containing configuration profiles originating from Substation HMIs.", "hunt"),
    ("cisco.compliance.031", "Identify any administrative SSH or TLS sessions utilizing weak, non-CEA-compliant cipher suites on grid infrastructure.", "hunt"),
    ("cisco.compliance.032", "Flag any engineers whose user accounts logged into an asset inside Substation 'A' while their physical badge entry was recorded at Substation 'B'.", "hunt"),
    ("cisco.compliance.033", "List any indicators of host or asset scanning mapping to network structures designated as CII nodes.", "hunt"),
    ("cisco.compliance.034", "Detect any actions where system auditing log processes or historical registers were cleared on Windows-based SCADA systems.", "hunt"),
    ("cisco.compliance.035", "Flag instances where two distinct master stations simultaneously issue conflicting control logic overrides to a single RTU.", "hunt"),
    ("cisco.compliance.036", "Identify any sudden stratum rating updates or modifications on local time sync GPS clocks across network blocks.", "hunt"),
    ("cisco.compliance.037", "Correlate physical safety digital log events to flag automated command sequences attempting to force breaker updates during manual repairs.", "hunt"),
    ("cisco.compliance.038", "Show any execution tracking parameters altering automatic generation control (AGC) metrics outside standard limits.", "hunt"),
    ("cisco.compliance.039", "List any host asset tracking entries revealing newly deployed network protocol analyzer tools on plant machines.", "hunt"),
    ("cisco.compliance.040", "Run an active telemetry comparison mapping all file download signatures against the file hash block list provided in today's CERT-In advisory.", "hunt"),
    ("cisco.endpoint.041", "Detect any instances where an engineering workstation executed a system terminal session spawned directly from a SCADA HMI runtime engine.", "hunt"),
    ("cisco.endpoint.042", "Flag any Cisco Secure Endpoint events tracking cross-process raw memory exploitation targeting active protection system logic.", "hunt"),
    ("cisco.endpoint.043", "Identify modifications executed against Windows hosts mapping system lookup validation definitions within critical grid tracking loops.", "hunt"),
    ("cisco.endpoint.044", "What operational security target logging boundaries do I have access validation permissions to audit across this instance session?", "metadata"),
    ("cisco.endpoint.045", "Provide structural tracking details for the specific structural capacity and total event generation of our regional storage pool.", "metadata"),
    ("cisco.endpoint.046", "List the total distinct log generation formats transmitting operational updates along with immediate pipeline ingest latency indicators.", "metadata"),
    ("cisco.endpoint.047", "Locate what active analytical tracking rules are currently instantiated to flag operational infrastructure degradation markers.", "metadata"),
    ("cisco.endpoint.048", "What is the active operational node version tracking structural configuration data across this processing cluster?", "metadata"),
    ("cisco.endpoint.049", "Identify if any Windows endpoints in the DMZ have installed unsigned kernel-level drivers over the last week.", "hunt"),
    ("cisco.endpoint.050", "Detect if the same administrative user ID is generating authentication failures across distinct physical substations within a 5-minute window.", "hunt"),
]

ACTIONABLE_FAMILIES = {
    "spl_generation_only",
    "live_investigation",
    "hybrid_alert_review",
    "hybrid_investigation",
    "hybrid_investigation_plus_policy",
    "attack_discovery",
    "guided_investigation",
}


def _classify_all() -> list[tuple[str, str, str | None]]:
    rows: list[tuple[str, str, str | None]] = []
    for qid, question, kind in CISCO_50:
        understanding = understand_query(question)
        result = build_query_to_intent(
            query=question,
            query_understanding=understanding,
            routed_skill=None,
            routing_provenance=None,
            llm_intent_advisory=None,
        )
        rows.append((qid, kind, result.intent_classification.intent_family))
    return rows


def test_hunt_questions_never_clarification_dump() -> None:
    rows = _classify_all()
    dumped = [
        (qid, fam)
        for qid, kind, fam in rows
        if kind == "hunt" and fam == "clarification_required"
    ]
    assert dumped == [], f"hunt questions dumped to clarification: {dumped}"


def test_actionable_family_floor() -> None:
    rows = _classify_all()
    actionable = sum(1 for _, _, fam in rows if fam in ACTIONABLE_FAMILIES)
    distribution = Counter(fam for _, _, fam in rows)
    assert actionable >= 45, (
        f"only {actionable}/50 Cisco questions landed in an actionable family; "
        f"distribution={dict(distribution)}"
    )
