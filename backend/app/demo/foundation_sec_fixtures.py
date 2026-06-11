from __future__ import annotations

from copy import deepcopy
from typing import Any


def foundation_sec_governance_for(scenario_id: str) -> dict[str, Any] | None:
    payload = FOUNDATION_SEC_GOVERNANCE_FIXTURES.get(scenario_id)
    return deepcopy(payload) if payload else None


def _base(*, captured_outputs: list[dict[str, Any]], governed_analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_type": "captured_foundation_sec_fixture",
        "live_llm_called": False,
        "final_answer_source": "governed_fixture",
        "display_mode": "main_answer_governed_model",
        "model_family": "Foundation-sec",
        "captured_outputs": captured_outputs,
        "governed_analysis": governed_analysis,
    }


FOUNDATION_SEC_GOVERNANCE_FIXTURES: dict[str, dict[str, Any]] = {
    "failed_login_spike_app01": _base(
        captured_outputs=[
            {
                "model_role": "analyst_response_drafter",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Instruct",
                "captured_prompt_type": "analyst_response",
                "captured_summary": "Identified a P2 High failed-login spike on APP-01 with 42, 31, and 28 failures from three source IPs between 13:42:10 and 14:37:22.",
                "useful_contribution": [
                    "Mapped the pattern to T1110.001 Password Guessing.",
                    "Preserved that no successful login was confirmed after the failures.",
                    "Referenced SOC-SOP-AUTH-001 v2026.04 for brute-force investigation.",
                ],
                "observed_limitations": [
                    "Added per-source distinct-user counts into an unsafe global target count.",
                    "Used wording that could imply privileged accounts were not targeted instead of saying privilege status is unavailable.",
                    "Sometimes recommended blocking source IPs before validation.",
                ],
            },
            {
                "model_role": "pattern_reasoner",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Reasoning",
                "captured_prompt_type": "investigation_reasoning",
                "captured_summary": "Treated the sustained failures across three source IPs as more concerning than a single expired-password case while avoiding confirmed compromise language.",
                "useful_contribution": [
                    "Explained why the distribution supports password guessing.",
                    "Kept T1078 unconfirmed.",
                    "Suggested source ownership, firewall, EDR, identity, and success-after-failure pivots.",
                ],
                "observed_limitations": [
                    "Included some broad process-improvement actions that are not immediate incident actions.",
                    "Some wording implied privileged-account absence rather than missing privilege evidence.",
                ],
            },
            {
                "model_role": "risk_rationale_reasoner",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Reasoning",
                "captured_prompt_type": "severity_rationale",
                "captured_summary": "Explained P2 High based on 101 failed logins, three source IPs, and missing P1 escalation evidence.",
                "useful_contribution": [
                    "Identified success-after-failure, privileged account impact, critical asset evidence, and malicious post-login activity as P1 triggers.",
                ],
                "observed_limitations": [
                    "Suggested confirming accounts are non-privileged; V.AI SOC governs this to checking whether accounts are privileged or service accounts.",
                ],
            },
        ],
        governed_analysis={
            "model_signal": "Foundation-sec model signal supports a high-confidence password-guessing pattern from sustained failed logins across three source IPs.",
            "vai_soc_decision": "V.AI SOC accepts T1110.001 as supported and keeps the final answer at P2 High because compromise, privileged-account impact, source ownership, and APP-01 criticality are not confirmed.",
            "evidence_used": [
                "10.10.4.21 produced 42 failed logins and 7 distinct users by source.",
                "10.10.4.22 produced 31 failed logins and 4 distinct users by source.",
                "10.10.4.19 produced 28 failed logins and 3 distinct users by source.",
                "Observed window spans 13:42:10 to 14:37:22.",
                "SOC-SOP-AUTH-001 v2026.04 supports brute-force triage.",
            ],
            "evidence_refs": ["ev-splunk-failed-app01", "ev-rag-bruteforce-sop"],
            "missing_evidence": [
                "Success-after-failure evidence for the same users and sources.",
                "Privileged or service account status for affected users.",
                "Source IP ownership and approved-use context.",
                "APP-01 CMDB criticality and business owner.",
                "Post-authentication activity on APP-01.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "unsafe global target count",
                    "vai_soc_governed": "Global distinct-user count is not claimed because per-source counts can overlap.",
                    "reason": "Avoids aggregate overclaim from per-source distinct counts.",
                    "rule": "guard.aggregate_overclaim",
                },
                {
                    "model_suggested": "privileged-account absence claim",
                    "vai_soc_governed": "Privileged-account status is not yet available.",
                    "reason": "Absence of identity evidence is not evidence of no privileged impact.",
                    "rule": "deterministic_identity_evidence_required",
                },
                {
                    "model_suggested": "Block source IPs early",
                    "vai_soc_governed": "Keep actions investigation and validation only.",
                    "reason": "No remediation/write action is available in this stage.",
                    "rule": "action_tier_policy",
                },
            ],
            "guardrail_notes": [
                "Severity is deterministic; model confidence is advisory.",
                "T1110.001 is supported; account compromise is not confirmed.",
                "Recommended actions use P1/P2/P3/P4 priority labels.",
            ],
        },
    ),
    "new_source_ip_logins": _base(
        captured_outputs=[
            {
                "model_role": "pattern_reasoner",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Reasoning",
                "captured_prompt_type": "unusual_source_reasoning",
                "captured_summary": "Treated successful logins from new source IPs as a Valid Accounts candidate requiring identity, MFA, and post-login validation.",
                "useful_contribution": [
                    "Recognised that new-source successful login evidence matters.",
                    "Suggested validating source ownership and account context before escalation.",
                ],
                "observed_limitations": [
                    "Could overstate T1078 without MFA/session and post-login evidence.",
                ],
            }
        ],
        governed_analysis={
            "model_signal": "Foundation-sec recognised the new source IP pattern as a potential Valid Accounts signal.",
            "vai_soc_decision": "V.AI SOC keeps the answer at P2 investigation and treats T1078 as validation-required until MFA, session, source ownership, and post-login evidence are available.",
            "evidence_used": [
                "svc_grid_ops logged in from 10.10.7.44 with no prior sightings.",
                "operator.rajesh logged in from 10.10.7.45 with no prior sightings.",
                "SOC guidance requires source ownership and account validation.",
            ],
            "evidence_refs": ["ev-splunk-new-source-app01", "ev-rag-new-source-sop"],
            "missing_evidence": [
                "MFA challenge and session result for each login.",
                "CMDB, VPN, jump-host, or DHCP ownership for 10.10.7.44 and 10.10.7.45.",
                "Account type and privilege status.",
                "First post-login activity and endpoint telemetry.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "Valid Accounts likely",
                    "vai_soc_governed": "T1078 remains validation-required.",
                    "reason": "Successful authentication from a new source is not proof of misuse by itself.",
                    "rule": "mitre_status_requires_grounding",
                }
            ],
            "guardrail_notes": [
                "The answer does not auto-approve baseline changes.",
                "No remediation or account action is recommended before validation.",
            ],
        },
    ),
    "successful_login_after_failures_run": _base(
        captured_outputs=[
            {
                "model_role": "pattern_reasoner",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Reasoning",
                "captured_prompt_type": "success_after_failure_reasoning",
                "captured_summary": "Interpreted the executed preview row as password guessing followed by one success for svc_grid_ops on APP-01.",
                "useful_contribution": [
                    "Kept T1110.001 Password Guessing supported from the returned row.",
                    "Kept T1078 Valid Accounts at requires_validation pending session and post-login evidence.",
                ],
                "observed_limitations": [
                    "Added prose before JSON and drifted from schema.",
                    "Used unsupported status wording for T1078 instead of requires_validation.",
                ],
            }
        ],
        governed_analysis={
            "model_signal": "Foundation-sec treated the executed preview row as a success-after-failure sequence for svc_grid_ops on APP-01.",
            "vai_soc_decision": "V.AI SOC accepts T1110.001 as supported from the returned row and keeps T1078 at requires_validation until MFA, session, and post-login evidence are collected.",
            "evidence_used": [
                "Splunk MCP search returned 58 failures and 1 success for svc_grid_ops from 10.10.4.21 on APP-01.",
                "Validated normalized SPL was the only query submitted to the MCP gate.",
            ],
            "evidence_refs": ["ev-splunk-success-after-fail-run"],
            "missing_evidence": [
                "Post-login process execution or command activity.",
                "EDR telemetry for APP-01.",
                "MFA/session context for the successful login.",
                "Privilege/service-account status for svc_grid_ops.",
                "APP-01 CMDB criticality.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "T1078 not confirmed",
                    "vai_soc_governed": "T1078 requires_validation.",
                    "reason": "The successful login is a candidate Valid Accounts signal, but confirmation requires post-login and session evidence.",
                    "rule": "mitre_status_normalization",
                }
            ],
            "guardrail_notes": [
                "Analysis is grounded on the executed preview row only.",
                "No malicious post-login activity is asserted.",
            ],
        },
    ),
    "mitre_mapping_auth_alert": _base(
        captured_outputs=[
            {
                "model_role": "pattern_reasoner",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Reasoning",
                "captured_prompt_type": "mitre_reasoning",
                "captured_summary": "Mapped repeated failures to T1110.001 and treated the observed success as a T1078 candidate requiring validation.",
                "useful_contribution": [
                    "Separated supported password guessing from validation-required Valid Accounts.",
                    "Identified session legitimacy and post-login activity as required pivots.",
                ],
                "observed_limitations": [
                    "Advisory MITRE reasoning still needs deterministic status normalization.",
                ],
            }
        ],
        governed_analysis={
            "model_signal": "Foundation-sec mapped the alert pattern to T1110.001 and raised T1078 as a validation candidate.",
            "vai_soc_decision": "V.AI SOC accepts T1110.001 as supported and keeps T1078 at requires_validation until session legitimacy, MFA, account ownership, and post-login activity are confirmed.",
            "evidence_used": [
                "Auth failure burst with post-failure success for svc_grid_ops on APP-01.",
                "58 failed logins and a successful login in the 60-minute alert window.",
            ],
            "evidence_refs": ["ev-splunk-mitre-auth"],
            "missing_evidence": [
                "MFA result and session legitimacy.",
                "Account ownership and privilege evidence.",
                "EDR/process telemetry after login.",
                "Firewall/VPN context for the source IP.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "T1078 candidate",
                    "vai_soc_governed": "T1078 requires_validation.",
                    "reason": "Technique status cannot be confirmed from login success alone.",
                    "rule": "mitre_status_requires_grounding",
                }
            ],
            "guardrail_notes": [
                "MITRE mapping is grounded in supplied alert evidence.",
                "No remediation action is recommended.",
            ],
        },
    ),
    "mitre_mapping_requires_context": _base(
        captured_outputs=[
            {
                "model_role": "intent_shadow_classifier",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Instruct",
                "captured_prompt_type": "intent_classification",
                "captured_summary": "Tried to proceed with map_mitre and clarification_needed=false even though alert_context_present=false.",
                "useful_contribution": [
                    "Recognised that the user wanted a MITRE mapping.",
                ],
                "observed_limitations": [
                    "Failed the deterministic clarification rule.",
                    "Attempted to map from the phrase 'this alert' without event evidence.",
                ],
            }
        ],
        governed_analysis={
            "model_signal": "Foundation-sec recognised a MITRE mapping request but attempted to proceed without alert evidence.",
            "vai_soc_decision": "V.AI SOC requires clarification before selecting a MITRE technique.",
            "evidence_used": [],
            "evidence_refs": [],
            "missing_evidence": [
                "Alert title or rule name.",
                "SPL or notable event details.",
                "Host, user, source IP, event type, and time window.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "clarification_needed=false",
                    "vai_soc_governed": "clarification_required",
                    "reason": "No alert context was supplied.",
                    "rule": "deterministic_clarification_override",
                }
            ],
            "guardrail_notes": [
                "No MITRE technique is selected without event evidence.",
                "Model confidence cannot override clarification policy.",
            ],
        },
    ),
    "mcp_metadata_discovery_app01": _base(
        captured_outputs=[
            {
                "model_role": "intent_shadow_classifier",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Instruct",
                "captured_prompt_type": "tool_selection",
                "captured_summary": "Recognised that index and sourcetype discovery was needed, but invented data-location names and generated SPL examples.",
                "useful_contribution": [
                    "Identified that discovery should happen before writing SPL.",
                ],
                "observed_limitations": [
                    "Invented index and sourcetype names.",
                    "Did not choose the expected deterministic discovery path.",
                    "Generated SPL examples instead of selecting safe discovery tools.",
                ],
            }
        ],
        governed_analysis={
            "model_signal": "Foundation-sec recognised that index and sourcetype discovery is required before SPL generation.",
            "vai_soc_decision": "V.AI SOC ignores invented index/sourcetype names and maps the discovery need to splunk_get_indexes and splunk_get_metadata.",
            "evidence_used": [
                "The user requested discovery of APP-01 authentication log indexes and sourcetypes before generating SPL.",
            ],
            "evidence_refs": [],
            "missing_evidence": [
                "Actual configured Splunk indexes.",
                "Actual sourcetypes containing APP-01 authentication events.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "invented index and sourcetype names",
                    "vai_soc_governed": "Use splunk_get_indexes and splunk_get_metadata.",
                    "reason": "LLM-invented data locations are not authority.",
                    "rule": "deterministic_tool_mapping",
                }
            ],
            "guardrail_notes": [
                "No SPL is generated for discovery.",
                "Raw LLM tool names are advisory only.",
            ],
        },
    ),
    "account_lockouts_over_time_spl": _base(
        captured_outputs=[
            {
                "model_role": "spl_advisory_generator",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Instruct",
                "captured_prompt_type": "spl_generation",
                "captured_summary": "Helped identify the SPL intent, but model SPL is not execution-authoritative.",
                "useful_contribution": [
                    "Recognised the analyst wanted lockout trend SPL.",
                ],
                "observed_limitations": [
                    "Model-generated SPL remains candidate-only and must not bypass validation.",
                ],
            }
        ],
        governed_analysis={
            "model_signal": "Foundation-sec can identify the SPL intent for account lockout trends.",
            "vai_soc_decision": "V.AI SOC uses deterministic template-generated SPL and requires validator approval before any gate can consider execution.",
            "evidence_used": [
                "Known account lockout trend use case.",
                "Template registry pattern for pgcil_soc / pgcil:auth.",
            ],
            "evidence_refs": [],
            "missing_evidence": [
                "Analyst review before operational use.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "model-generated SPL",
                    "vai_soc_governed": "template-generated validator-ready SPL",
                    "reason": "Known use cases use deterministic templates; model SPL is never execution authority.",
                    "rule": "spl_template_registry_authority",
                }
            ],
            "guardrail_notes": [
                "Candidate SPL has execution_eligible=false.",
                "Only validator-approved normalized SPL may reach the MCP gate.",
            ],
        },
    ),
    "airgapped_no_saia_success_after_failures": _base(
        captured_outputs=[
            {
                "model_role": "spl_advisory_generator",
                "model_family": "Foundation-sec",
                "model_name": "Foundation-sec-8B-Instruct",
                "captured_prompt_type": "spl_generation",
                "captured_summary": "Captured SPL-like output included invalid tstats-style fragments and incorrectly claimed execution eligibility.",
                "useful_contribution": [
                    "Recognised the successful-login-after-failures SPL intent.",
                ],
                "observed_limitations": [
                    "Produced unsafe/invalid SPL-like syntax.",
                    "Violated execution eligibility policy.",
                ],
            }
        ],
        governed_analysis={
            "model_signal": "Foundation-sec can identify the success-after-failure SPL intent.",
            "vai_soc_decision": "V.AI SOC replaces model SPL with the deterministic template-generated SPL and forces model SPL execution eligibility to false.",
            "evidence_used": [
                "Known success-after-failure use case.",
                "Template registry correlation SPL.",
            ],
            "evidence_refs": ["ev-splunk-success-after-fail"],
            "missing_evidence": [
                "Analyst review before operational use.",
                "Post-login, EDR, IAM, CMDB, and firewall evidence after results are reviewed.",
            ],
            "governance_overrides": [
                {
                    "model_suggested": "invalid tstats-style SPL with execution authority claim",
                    "vai_soc_governed": "template-generated validator-ready SPL with execution_eligible=false",
                    "reason": "LLM SPL is candidate-only and cannot grant execution authority.",
                    "rule": "llm_execution_eligibility_ignored",
                }
            ],
            "guardrail_notes": [
                "Invalid model SPL fragments are not shown as final SPL.",
                "Execution remains tied to normalized_spl plus MCP gate policy.",
            ],
        },
    ),
}
