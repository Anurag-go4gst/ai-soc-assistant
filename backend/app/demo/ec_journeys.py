"""Presentation-only Experience Center journey metadata. Backend does not sleep."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.demo.ec_response import EcExecutionJourney, EcExecutionResource, EcExecutionStage

# Canonical 10-step initial pipeline (architecture-aligned presentation only).
_INITIAL_ARCHITECTURE_KEYS = (
    "understand",
    "resource-plan",
    "mcp-select",
    "mcp-connect",
    "evidence",
    "spl-validate",
    "mcp-execute",
    "correlate",
    "llm-advisory",
    "outcome",
)

INITIAL_ARCHITECTURE_STEP_COUNT = len(_INITIAL_ARCHITECTURE_KEYS)

S1_INITIAL_TITLES = (
    "Decomposing suspicious-IP investigation",
    "Planning evidence and resources",
    "Selecting governed MCP tools",
    "Connecting to Splunk MCP",
    "Reusing approved suspicious-IP investigation content",
    "Validating governed SPL searches",
    "Executing governed Splunk searches",
    "Correlating communication and affected systems",
    "Applying governed LLM advisory",
    "Building InvestigationOutcome and next options",
)

S3_INITIAL_TITLES = (
    "Decomposing firewall-team coordination",
    "Planning evidence and resources",
    "Selecting governed MCP tools",
    "Connecting to knowledge and process sources",
    "Reusing confirmed SIEM investigation evidence",
    "Validating coordination prerequisites",
    "Retrieving firewall-block process",
    "Evaluating action readiness",
    "Applying governed LLM advisory",
    "Building InvestigationOutcome and coordination options",
)

S5_INITIAL_TITLES = (
    "Decomposing Cisco remediation request",
    "Planning evidence and resources",
    "Selecting Cisco MCP capability",
    "Connecting to Cisco device MCP",
    "Checking R-17 version",
    "Version 14 identified",
    "Identifying applicable hardening policy source",
    "Deferring policy applicability to analyst review",
    "Applying governed LLM advisory",
    "Building remediation plan and next options",
)

_LLM_ACTIVITY = [
    "Applying governed LLM advisory signals…",
    "Applying severity, MITRE, and SPL governance overrides…",
    "Final synthesis disabled for Experience Center",
]


@dataclass
class InitialStepSpec:
    key: str
    title: str
    semantic_type: str = "gather"
    duration_ms_hint: int = 900
    activity: list[str] = field(default_factory=list)
    system: str | None = None
    operation: str | None = None
    mode: str = "read"
    outcome_change: str | None = None


def _stage(
    stage_id: str,
    title: str,
    *,
    description: str = "",
    activity: list[str] | None = None,
    semantic_type: str = "gather",
    duration_ms_hint: int = 900,
    system: str | None = None,
    operation: str | None = None,
    mode: str = "read",
    evidence_added: list[str] | None = None,
    outcome_change: str | None = None,
    action_state: str | None = None,
) -> EcExecutionStage:
    resource = None
    if system and operation:
        resource = EcExecutionResource(system=system, operation=operation, mode=mode)  # type: ignore[arg-type]
    return EcExecutionStage(
        id=stage_id,
        title=title,
        description=description,
        activity=activity or [],
        semantic_type=semantic_type,  # type: ignore[arg-type]
        duration_ms_hint=duration_ms_hint,
        resource=resource,
        evidence_added=evidence_added or [],
        outcome_change=outcome_change,
        action_state=action_state,
        provenance="experience_center_fixture",
    )


_HIL_WAIT = frozenset({"wait", "hil"})
_INITIAL_TARGET_MS = 11000
_FOLLOW_UP_TARGET_MS = 5500
_ACTION_TARGET_MS = 4200
_MCP_STAGE_WEIGHT = 1.55
_LLM_STAGE_WEIGHT = 1.45


def _stage_weight(stage: EcExecutionStage) -> float:
    if stage.semantic_type in _HIL_WAIT:
        return 0.0
    hint = int(stage.duration_ms_hint or 0)
    if hint <= 0:
        return 0.0
    weight = 1.0
    resource = stage.resource
    if resource and resource.system:
        weight = max(weight, _MCP_STAGE_WEIGHT)
    title = stage.title.lower()
    activity_blob = " ".join(stage.activity or []).lower()
    if "llm" in title or "foundation-sec" in activity_blob or "llm" in activity_blob:
        weight = max(weight, _LLM_STAGE_WEIGHT)
    return hint * weight


def _scale_stages(stages: list[EcExecutionStage], target_ms: int) -> list[EcExecutionStage]:
    weights = [_stage_weight(stage) for stage in stages]
    total = sum(weights)
    if total <= 0:
        return stages
    factor = target_ms / total
    scaled: list[EcExecutionStage] = []
    for stage, weight in zip(stages, weights, strict=True):
        if stage.semantic_type in _HIL_WAIT or weight <= 0:
            scaled.append(stage)
            continue
        scaled.append(stage.model_copy(update={"duration_ms_hint": max(450, int(round(weight * factor)))}))
    return scaled


def _journey(
    journey_id: str,
    stages: list[EcExecutionStage],
    *,
    kind: str = "initial",
    follow_up_id: str | None = None,
    header: str = "Running governed investigation pipeline",
) -> EcExecutionJourney:
    target = _INITIAL_TARGET_MS if kind == "initial" else _ACTION_TARGET_MS if kind == "action" else _FOLLOW_UP_TARGET_MS
    return EcExecutionJourney(
        journey_id=journey_id,
        kind=kind,  # type: ignore[arg-type]
        header=header,
        follow_up_id=follow_up_id,
        stages=_scale_stages(stages, target),
    )


def _steps_from_specs(prefix: str, specs: list[InitialStepSpec]) -> list[EcExecutionStage]:
    if len(specs) != INITIAL_ARCHITECTURE_STEP_COUNT:
        raise ValueError(f"{prefix} initial journey must have {INITIAL_ARCHITECTURE_STEP_COUNT} stages")
    return [
        _stage(
            f"{prefix}-{spec.key}",
            spec.title,
            semantic_type=spec.semantic_type,
            duration_ms_hint=spec.duration_ms_hint,
            activity=spec.activity,
            system=spec.system,
            operation=spec.operation,
            mode=spec.mode,
            outcome_change=spec.outcome_change,
        )
        for spec in specs
    ]


def _initial_journey(journey_id: str, prefix: str, specs: list[InitialStepSpec]) -> EcExecutionJourney:
    return _journey(journey_id, _steps_from_specs(prefix, specs))


def s1_initial() -> EcExecutionJourney:
    splunk = ("Splunk", "splunk_run_query")
    splunk_saved = ("Splunk", "splunk_run_saved_search")
    titles = S1_INITIAL_TITLES
    specs = [
        InitialStepSpec("understand", titles[0], semantic_type="understand", duration_ms_hint=800, activity=["Decomposing communication, affected systems, and auth questions…"]),
        InitialStepSpec("resource-plan", titles[1], semantic_type="plan", duration_ms_hint=850, activity=["Mapping evidence needs and governed resources…", "Resource plan locked for suspicious-IP hunt…"]),
        InitialStepSpec("mcp-select", titles[2], semantic_type="plan", duration_ms_hint=800, activity=["Selecting splunk_run_query and knowledge-object tools…", "Applying MCP execution gates…"]),
        InitialStepSpec("mcp-connect", titles[3], semantic_type="plan", duration_ms_hint=1000, activity=["Resolving Splunk MCP from registry…", "Connector ready for governed search…"], system=splunk[0], operation=splunk[1]),
        InitialStepSpec("evidence", titles[4], semantic_type="gather", duration_ms_hint=1000, activity=["Executing approved saved search…", "Partial coverage — historical gap remains…"], system=splunk_saved[0], operation=splunk_saved[1], outcome_change="coverage=PARTIAL"),
        InitialStepSpec("spl-validate", titles[5], semantic_type="evaluate", duration_ms_hint=900, activity=["Running deterministic SPL validator on bounded 30-day windows…"]),
        InitialStepSpec("mcp-execute", titles[6], semantic_type="gather", duration_ms_hint=1300, activity=["Executing governed Splunk search…", "Executing second governed search…", "Polling Splunk MCP job…"], system=splunk[0], operation=splunk[1]),
        InitialStepSpec("correlate", titles[7], semantic_type="correlate", duration_ms_hint=900, activity=["Merging firewall evidence across windows…", "Jump host 10.20.1.10 is the priority pivot…"]),
        InitialStepSpec("llm-advisory", titles[8], semantic_type="evaluate", duration_ms_hint=1200, activity=_LLM_ACTIVITY),
        InitialStepSpec("outcome", titles[9], semantic_type="outcome", duration_ms_hint=900, activity=["Separating confirmed, unconfirmed, and missing evidence…", "Preparing investigation and response options…"]),
    ]
    return _initial_journey("s1-initial", "s1", specs)


def s3_initial() -> EcExecutionJourney:
    titles = S3_INITIAL_TITLES
    specs = [
        InitialStepSpec("understand", titles[0], semantic_type="understand", duration_ms_hint=800, activity=["Parsing firewall-block coordination intent…"]),
        InitialStepSpec("resource-plan", titles[1], semantic_type="plan", duration_ms_hint=850, activity=["Planning email transport and process evidence…"]),
        InitialStepSpec("mcp-select", titles[2], semantic_type="plan", duration_ms_hint=800, activity=["Selecting knowledge and coordination connectors…"]),
        InitialStepSpec("mcp-connect", titles[3], semantic_type="plan", duration_ms_hint=900, activity=["Opening governed knowledge retrieval channel…"], system="Knowledge", operation="firewall_process", mode="knowledge"),
        InitialStepSpec("evidence", titles[4], semantic_type="gather", duration_ms_hint=950, activity=["Reusing confirmed SIEM evidence — no new Splunk search…"]),
        InitialStepSpec("spl-validate", titles[5], semantic_type="evaluate", duration_ms_hint=850, activity=["Checking mandatory request fields…"]),
        InitialStepSpec("mcp-execute", titles[6], semantic_type="gather", duration_ms_hint=1000, activity=["Retrieving company firewall-block process…"], system="Knowledge", operation="firewall_process", mode="knowledge"),
        InitialStepSpec("correlate", titles[7], semantic_type="evaluate", duration_ms_hint=850, activity=["Evaluating coordination action readiness…"]),
        InitialStepSpec("llm-advisory", titles[8], semantic_type="evaluate", duration_ms_hint=1200, activity=_LLM_ACTIVITY),
        InitialStepSpec("outcome", titles[9], semantic_type="outcome", duration_ms_hint=900, activity=["Packaging coordination outcome from reused evidence…", "Preparing coordination actions…"]),
    ]
    return _initial_journey("s3-initial", "s3", specs)


def s3_ingest_reply() -> EcExecutionJourney:
    return _journey(
        "s3-ingest",
        [
            _stage("s3-ingest-read", "Reviewing firewall-team reply", semantic_type="gather", duration_ms_hint=800, activity=["Reading inbound team response…"]),
            _stage("s3-ingest-evidence", "Ingesting team response as evidence", semantic_type="correlate", duration_ms_hint=850, activity=["Team reply added to SourceEvidence…"]),
            _stage("s3-reassess", "Reassessing whitelist exception", semantic_type="evaluate", duration_ms_hint=850, activity=["Exception does not automatically mean benign…"], outcome_change="disposition=needs_reassessment"),
            _stage("s3-outcome-update", "Updating InvestigationOutcome", semantic_type="outcome", duration_ms_hint=900, activity=["Recommended actions updated — block not automatic…"]),
        ],
        kind="follow_up",
        follow_up_id="ingest_firewall_reply",
        header="Processing team response",
    )


def s3_send_waiting() -> EcExecutionJourney:
    return _journey(
        "s3-send",
        [
            _stage("s3-send-prep", "Preparing firewall-team request", semantic_type="plan", duration_ms_hint=800),
            _stage("s3-send-hil", "Waiting for send approval", semantic_type="hil", duration_ms_hint=0, action_state="APPROVAL_REQUIRED"),
            _stage("s3-send-wait", "Waiting for firewall-team response", semantic_type="wait", duration_ms_hint=0, activity=["Inbound reply is fixture-backed unless a live connector is configured…"]),
        ],
        kind="action",
        follow_up_id="send_firewall_email",
        header="Connecting to email transport",
    )


def s5_initial() -> EcExecutionJourney:
    titles = S5_INITIAL_TITLES
    specs = [
        InitialStepSpec("understand", titles[0], semantic_type="understand", duration_ms_hint=800, activity=["Reviewing breach evidence for R-17…"]),
        InitialStepSpec("resource-plan", titles[1], semantic_type="plan", duration_ms_hint=850, activity=["Planning Cisco version and policy evidence…"]),
        InitialStepSpec("mcp-select", titles[2], semantic_type="plan", duration_ms_hint=800, activity=["Selecting simulated cisco.get_version…"], system="Cisco", operation="get_version"),
        InitialStepSpec("mcp-connect", titles[3], semantic_type="plan", duration_ms_hint=1000, activity=["Opening Cisco MCP channel…"], system="Cisco", operation="get_version"),
        InitialStepSpec("evidence", titles[4], semantic_type="gather", duration_ms_hint=900, activity=["Reading device version via governed MCP…"]),
        InitialStepSpec("spl-validate", titles[5], semantic_type="evaluate", duration_ms_hint=900, activity=["Version probe returned current_version=14…"], outcome_change="current_version=14"),
        InitialStepSpec("mcp-execute", titles[6], semantic_type="gather", duration_ms_hint=1000, activity=["Identifying hardening policy source for analyst review…"], system="Knowledge", operation="hardening_policy", mode="knowledge"),
        InitialStepSpec("correlate", titles[7], semantic_type="evaluate", duration_ms_hint=850, activity=["Policy applicability pending analyst review…", "Approval is required before upgrade…"]),
        InitialStepSpec("llm-advisory", titles[8], semantic_type="evaluate", duration_ms_hint=1200, activity=_LLM_ACTIVITY),
        InitialStepSpec("outcome", titles[9], semantic_type="outcome", duration_ms_hint=900, activity=["Building the remediation plan…", "Preparing change request options…"]),
    ]
    return _initial_journey("s5-initial", "s5", specs)


def s2_initial() -> EcExecutionJourney:
    splunk_ko = ("Splunk", "splunk_get_knowledge_objects")
    splunk_saved = ("Splunk", "splunk_run_saved_search")
    splunk_query = ("Splunk", "splunk_run_query")
    specs = [
        InitialStepSpec("understand", "Decomposing AI-security investigation", semantic_type="understand", duration_ms_hint=800, activity=["Separating attack attempt, tool execution, and restricted-data access…"]),
        InitialStepSpec("resource-plan", "Planning evidence and resources", semantic_type="plan", duration_ms_hint=850, activity=["Mapping tool-audit, identity, and DLP evidence needs…"]),
        InitialStepSpec("mcp-select", "Selecting governed MCP tools", semantic_type="plan", duration_ms_hint=800, activity=["Selecting Splunk search and metadata tools…"]),
        InitialStepSpec("mcp-connect", "Connecting to Splunk MCP", semantic_type="plan", duration_ms_hint=1000, activity=["Resolving Splunk MCP from registry…", "tools/list → splunk_run_query allowed ✓"], system=splunk_ko[0], operation=splunk_ko[1]),
        InitialStepSpec("evidence", "Checking existing SIEM coverage", semantic_type="plan", duration_ms_hint=1000, activity=["Looking for approved Splunk detections and saved searches…"], system=splunk_ko[0], operation=splunk_ko[1]),
        InitialStepSpec("spl-validate", "Preparing and validating governed SPL", semantic_type="evaluate", duration_ms_hint=950, activity=["Preparing bounded tool-audit search…", "Candidate query is deterministically validated…"]),
        InitialStepSpec("mcp-execute", "Executing approved detection and tool-audit search", semantic_type="gather", duration_ms_hint=1300, activity=["Executing approved detection…", "Executing governed tool-audit SPL…", "Polling Splunk MCP job…"], system=splunk_query[0], operation=splunk_query[1]),
        InitialStepSpec("correlate", "Correlating authorization and restricted-data evidence", semantic_type="correlate", duration_ms_hint=900, activity=["Prompt-injection attempt confirmed…", "export_customer_records blocked; breach not confirmed…"], outcome_change="attempted_blocked"),
        InitialStepSpec("llm-advisory", "Applying governed LLM advisory", semantic_type="evaluate", duration_ms_hint=1200, activity=_LLM_ACTIVITY),
        InitialStepSpec("outcome", "Building InvestigationOutcome and next options", semantic_type="outcome", duration_ms_hint=900, activity=["Attack confirmed · control blocked · breach not confirmed…", "Preparing contextual next investigation options…"]),
    ]
    # s2 evidence step also replays saved search — fold into mcp-execute activity; coverage check stays in evidence title
    specs[4] = InitialStepSpec(
        "evidence",
        "Checking existing SIEM coverage",
        semantic_type="gather",
        duration_ms_hint=1000,
        activity=["Looking for approved detections…", "Running approved detection preview…"],
        system=splunk_saved[0],
        operation=splunk_saved[1],
    )
    return _initial_journey("s2-initial", "s2", specs)


def s4_initial() -> EcExecutionJourney:
    specs = [
        InitialStepSpec("understand", "Decomposing zero-day advisory investigation", semantic_type="understand", duration_ms_hint=800),
        InitialStepSpec("resource-plan", "Planning evidence and resources", semantic_type="plan", duration_ms_hint=850, activity=["Mapping CVE hunt and playbook evidence needs…"]),
        InitialStepSpec("mcp-select", "Selecting governed MCP tools", semantic_type="plan", duration_ms_hint=800, activity=["Selecting Splunk knowledge-object tools…"]),
        InitialStepSpec("mcp-connect", "Connecting to Splunk MCP", semantic_type="plan", duration_ms_hint=1000, activity=["Opening Splunk MCP discovery channel…"], system="Splunk", operation="splunk_get_knowledge_objects"),
        InitialStepSpec("evidence", "Checking existing Splunk CVE/vendor detections", semantic_type="plan", duration_ms_hint=900, activity=["Searching knowledge objects for threat-specific content…"], system="Splunk", operation="splunk_get_knowledge_objects"),
        InitialStepSpec("spl-validate", "Validating governed IOC hunt SPL", semantic_type="evaluate", duration_ms_hint=900, activity=["No threat-specific detection to reuse — gap hunt only…"], outcome_change="detection=none"),
        InitialStepSpec("mcp-execute", "Identifying exploitation evidence gap", semantic_type="plan", duration_ms_hint=1000, activity=["Governed IOC hunt required only for gap…"]),
        InitialStepSpec(
            "correlate",
            "No predefined SOAR playbook available",
            semantic_type="evaluate",
            duration_ms_hint=1100,
            activity=["Checking for a predefined SOAR playbook…", "This is investigation context, not a failed stage…"],
            outcome_change="soar_playbook=not_available",
        ),
        InitialStepSpec("llm-advisory", "Applying governed LLM advisory", semantic_type="evaluate", duration_ms_hint=1200, activity=_LLM_ACTIVITY),
        InitialStepSpec("outcome", "Building InvestigationOutcome and next options", semantic_type="outcome", duration_ms_hint=900, activity=["Packaging zero-day outcome without playbook…", "Preparing next investigation options…"]),
    ]
    return _initial_journey("s4-initial", "s4", specs)


def s6_initial() -> EcExecutionJourney:
    specs = [
        InitialStepSpec("understand", "Decomposing privileged VPN failure investigation", semantic_type="understand", duration_ms_hint=800),
        InitialStepSpec("resource-plan", "Planning evidence and resources", semantic_type="plan", duration_ms_hint=850, activity=["Scoping Germany administrator VPN evidence…"]),
        InitialStepSpec("mcp-select", "Selecting governed MCP tools", semantic_type="plan", duration_ms_hint=800, activity=["Selecting ticket and VPN evidence connectors…"]),
        InitialStepSpec("mcp-connect", "Connecting to investigation sources", semantic_type="plan", duration_ms_hint=900, activity=["Opening governed evidence retrieval channels…"]),
        InitialStepSpec("evidence", "Scoping Germany administrator VPN", semantic_type="plan", duration_ms_hint=900, activity=["Applying scope constraint to prior evidence…"]),
        InitialStepSpec("spl-validate", "Validating scope and evidence applicability", semantic_type="evaluate", duration_ms_hint=850, activity=["Marking out-of-scope evidence without deleting history…"]),
        InitialStepSpec("mcp-execute", "Gathering scoped VPN evidence", semantic_type="gather", duration_ms_hint=1000, activity=["Retrieving scoped authentication failures…"]),
        InitialStepSpec("correlate", "Correlating continuity with prior incident context", semantic_type="correlate", duration_ms_hint=900, activity=["Comparing current scope with prior tickets…"]),
        InitialStepSpec("llm-advisory", "Applying governed LLM advisory", semantic_type="evaluate", duration_ms_hint=1200, activity=_LLM_ACTIVITY),
        InitialStepSpec("outcome", "Building InvestigationOutcome and next options", semantic_type="outcome", duration_ms_hint=900, activity=["Separating confirmed, superseded, and stale evidence…", "Preparing next investigation options…"]),
    ]
    return _initial_journey("s6-initial", "s6", specs)


def s7_initial() -> EcExecutionJourney:
    specs = [
        InitialStepSpec("understand", "Decomposing conflicting OT evidence question", semantic_type="understand", duration_ms_hint=800),
        InitialStepSpec("resource-plan", "Planning evidence and resources", semantic_type="plan", duration_ms_hint=850, activity=["Planning Splunk telemetry and CMDB reconciliation…"]),
        InitialStepSpec("mcp-select", "Selecting MCP and CMDB sources", semantic_type="plan", duration_ms_hint=800, activity=["Selecting Splunk and CMDB connectors…"]),
        InitialStepSpec("mcp-connect", "Connecting to Splunk MCP", semantic_type="plan", duration_ms_hint=1000, activity=["Opening Splunk MCP channel…"], system="Splunk", operation="splunk_run_query"),
        InitialStepSpec("evidence", "Loading Splunk unauthorized-access telemetry", semantic_type="gather", duration_ms_hint=1000, activity=["Loading Splunk unauthorized-access telemetry…"], system="Splunk", operation="splunk_run_query"),
        InitialStepSpec("spl-validate", "Loading CMDB retirement record", semantic_type="gather", duration_ms_hint=900, activity=["Loading CMDB retirement record…"]),
        InitialStepSpec("mcp-execute", "Correlating Splunk and CMDB records", semantic_type="correlate", duration_ms_hint=1000, activity=["Comparing live telemetry against CMDB state…"]),
        InitialStepSpec(
            "correlate",
            "Conflict detected",
            semantic_type="evaluate",
            duration_ms_hint=1400,
            activity=["Splunk activity vs CMDB retired…", "Do not force an incident yet…"],
            outcome_change="unresolved_conflict",
        ),
        InitialStepSpec("llm-advisory", "Applying governed LLM advisory", semantic_type="evaluate", duration_ms_hint=1200, activity=_LLM_ACTIVITY),
        InitialStepSpec("outcome", "Building InvestigationOutcome and next options", semantic_type="outcome", duration_ms_hint=900, outcome_change="unresolved_conflict", activity=["Packaging unresolved conflict outcome…", "Preparing next investigation options…"]),
    ]
    return _initial_journey("s7-initial", "s7", specs)


def s6_scope_change(follow_up_id: str) -> EcExecutionJourney:
    labels = {
        "scope_service_accounts": ("OUT_OF_SCOPE", "Administrator VPN evidence is no longer in the current scope"),
        "scope_build_servers": ("SUPERSEDED", "Broad service-account evidence is superseded by the build-server constraint"),
        "check_last_month_incident": ("STALE", "Prior incident is stale for current scope and reusable as context"),
    }
    status, detail = labels.get(follow_up_id, ("REUSABLE", "Re-evaluating prior evidence against the new scope"))
    return _journey(
        f"s6-{follow_up_id}",
        [
            _stage("s6-fu-understand", "Understanding scope change", semantic_type="understand", duration_ms_hint=700),
            _stage("s6-fu-reeval", "Re-evaluating prior evidence", semantic_type="evaluate", duration_ms_hint=800),
            _stage("s6-fu-status", f"Marking prior evidence {status}", semantic_type="evaluate", duration_ms_hint=900, activity=[detail], outcome_change=status),
            _stage("s6-fu-gather", "Gathering evidence for the new scope", semantic_type="gather", duration_ms_hint=900),
            _stage("s6-fu-outcome", "Updating InvestigationOutcome", semantic_type="outcome", duration_ms_hint=800),
        ],
        kind="follow_up",
        follow_up_id=follow_up_id,
        header="Continuing investigation",
    )


def _continue(
    journey_id: str,
    follow_up_id: str,
    stages: list[tuple[str, str, str]],
    *,
    header: str = "Continuing investigation",
) -> EcExecutionJourney:
    built = [
        _stage(f"{journey_id}-{idx}", title, semantic_type=semantic, duration_ms_hint=800, activity=[activity] if activity else None)
        for idx, (title, semantic, activity) in enumerate(stages, start=1)
    ]
    return _journey(journey_id, built, kind="follow_up", follow_up_id=follow_up_id, header=header)


def _action(
    journey_id: str,
    follow_up_id: str,
    stages: list[tuple[str, str, str]],
    *,
    header: str,
    system: str | None = None,
    operation: str | None = None,
) -> EcExecutionJourney:
    built = []
    for idx, (title, semantic, activity) in enumerate(stages, start=1):
        built.append(
            _stage(
                f"{journey_id}-{idx}",
                title,
                semantic_type=semantic,
                duration_ms_hint=700,
                activity=[activity] if activity else None,
                system=system if idx == 1 else None,
                operation=operation if idx == 1 else None,
            )
        )
    return _journey(journey_id, built, kind="action", follow_up_id=follow_up_id, header=header)


def _ticket_action(follow_up_id: str) -> EcExecutionJourney:
    return _action(
        f"act-ticket-{follow_up_id}",
        follow_up_id,
        [
            ("Selecting ITSM connector", "plan", "Choosing the simulated ticket system…"),
            ("Connecting to ITSM", "execute", "Opening the EC ticket channel…"),
            ("Recording ticket receipt", "evaluate", "Linking incident ticket to investigation evidence…"),
        ],
        header="Connecting to ITSM",
        system="ITSM",
        operation="ticket",
    )


def _email_action(follow_up_id: str, *, wait_inbound: bool = False) -> EcExecutionJourney:
    stages = [
        ("Selecting email transport", "plan", "Using the allowlisted EC SMTP adapter…"),
        ("Connecting to mail system", "execute", "Opening the outbound mail channel…"),
        ("Waiting for send approval", "hil", "Send email waits for explicit visitor action…"),
    ]
    if wait_inbound:
        stages.append(
            ("Waiting for inbound reply", "wait", "Inbound reply is fixture-backed unless a live connector is configured…"),
        )
    return _action(
        f"act-email-{follow_up_id}",
        follow_up_id,
        stages,
        header="Connecting to email transport",
        system="SMTP",
        operation="send",
    )


def _firewall_action(follow_up_id: str) -> EcExecutionJourney:
    verify = "verify" in follow_up_id
    stages = (
        [
            ("Selecting firewall controller", "plan", "Choosing the simulated firewall change API…"),
            ("Connecting to firewall", "verify", "Reading simulated rule state…"),
            ("Recording verification", "evaluate", "No live firewall claim…"),
        ]
        if verify
        else [
            ("Selecting firewall controller", "plan", "Choosing the simulated firewall change API…"),
            ("Connecting to firewall", "execute", "Opening the EC firewall channel…"),
            ("Approval required", "hil", "No production firewall change until Execute…"),
        ]
    )
    return _action(
        f"act-fw-{follow_up_id}",
        follow_up_id,
        stages,
        header="Connecting to firewall controller",
        system="Firewall",
        operation="change",
    )


def _agilus_action(follow_up_id: str) -> EcExecutionJourney:
    stages = [
        ("Selecting Agilus connector", "plan", "Agilus MCP analyzes vendor assets against version history…"),
        ("Connecting to Agilus", "execute", "Opening the Agilus patch orchestration channel…"),
        ("Approval required", "hil", "Patch apply waits for explicit analyst approval…"),
        ("Submitting patch job", "execute", "Agilus MCP submits emergency patch job to target gateways…"),
        ("Recording Agilus receipt", "wait", "Awaiting Agilus completion callback to update investigation…"),
    ]
    return _action(
        f"act-agilus-{follow_up_id}",
        follow_up_id,
        stages,
        header="Connecting to Agilus patch MCP",
        system="Agilus",
        operation="patch_submit",
    )


def _cisco_action(follow_up_id: str) -> EcExecutionJourney:
    verify = "verify" in follow_up_id
    stages = (
        [
            ("Selecting Cisco device", "plan", "cisco.get_version / cisco.upgrade are simulated…"),
            ("Connecting to Cisco device", "execute", "Opening the EC Cisco channel…"),
            ("Approval required", "hil", "No production device change until Execute…"),
            ("Recording device receipt", "evaluate", "No production Cisco change…"),
        ]
        if not verify
        else [
            ("Selecting Cisco device", "plan", "Reading cisco.get_version via governed MCP…"),
            ("Connecting to Cisco device", "verify", "Reading fixture version…"),
            ("Recording verification", "evaluate", "No live Cisco claim…"),
        ]
    )
    return _action(
        f"act-cisco-{follow_up_id}",
        follow_up_id,
        stages,
        header="Connecting to Cisco device",
        system="Cisco",
        operation="get_version" if verify else "upgrade",
    )


def _iam_action(follow_up_id: str) -> EcExecutionJourney:
    verify = "verify" in follow_up_id
    stages = (
        [
            ("Selecting identity provider", "plan", "Simulated IAM disable only…"),
            ("Connecting to IAM", "execute", "Opening the EC identity channel…"),
            ("Approval required", "hil", "Credential action waits for HIL…"),
        ]
        if not verify
        else [
            ("Selecting identity provider", "plan", "Checking simulated credential state…"),
            ("Connecting to IAM", "verify", "Reading fixture credential state…"),
            ("Recording verification", "evaluate", "No live IAM change…"),
        ]
    )
    return _action(
        f"act-iam-{follow_up_id}",
        follow_up_id,
        stages,
        header="Connecting to identity provider",
        system="IAM",
        operation="disable",
    )


def _closure_action(follow_up_id: str) -> EcExecutionJourney:
    return _action(
        f"act-close-{follow_up_id}",
        follow_up_id,
        [
            ("Compiling closure summary", "plan", "Structuring confirmed vs unconfirmed findings…"),
            ("Preparing executive summary", "outcome", "No production report is published…"),
        ],
        header="Preparing closure summary",
    )


def _looks_like_action(follow_up_id: str) -> bool:
    token = follow_up_id.lower()
    needles = (
        "email",
        "notify",
        "ticket",
        "incident",
        "firewall",
        "whitelist",
        "block",
        "upgrade",
        "cisco",
        "version",
        "credential",
        "closure",
        "summary",
        "send_",
        "ask_",
        "approve_",
        "execute_",
        "verify_",
        "cmdb",
        "change_ticket",
    )
    return any(item in token for item in needles)


def _infer_action(follow_up_id: str) -> EcExecutionJourney:
    token = follow_up_id.lower()
    if any(item in token for item in ("email", "notify", "ask_", "send_", "reply")):
        return _email_action(follow_up_id)
    if any(item in token for item in ("ticket", "incident", "cmdb")):
        return _ticket_action(follow_up_id)
    if any(item in token for item in ("firewall", "whitelist", "block")):
        return _firewall_action(follow_up_id)
    if any(item in token for item in ("cisco", "upgrade", "version")):
        return _cisco_action(follow_up_id)
    if "credential" in token or "iam" in token:
        return _iam_action(follow_up_id)
    if "closure" in token or "summary" in token:
        return _closure_action(follow_up_id)
    return _action(
        f"act-generic-{follow_up_id}",
        follow_up_id,
        [
            ("Selecting target system", "plan", "Choosing the governed connector for this action…"),
            ("Connecting to the external system", "execute", "Opening the EC action channel…"),
            ("Recording receipt", "evaluate", "No production side effect until Execute…"),
        ],
        header="Connecting to external system",
    )


def _fallback_non_initial(follow_up_id: str) -> EcExecutionJourney:
    if _looks_like_action(follow_up_id):
        return _infer_action(follow_up_id)
    return _continue(
        f"fu-{follow_up_id}",
        follow_up_id,
        [
            ("Selecting additional evidence", "plan", "Choosing the next governed evidence source…"),
            ("Retrieving evidence", "gather", "Retrieving governed fixture evidence…"),
            ("Updating InvestigationOutcome", "outcome", "Updating confirmed vs unconfirmed…"),
        ],
    )


S1_FOLLOW_UP_JOURNEYS = {
    "check_endpoint_activity": _continue(
        "s1-edr",
        "check_endpoint_activity",
        [
            ("Selecting EDR capability", "plan", "Selecting the simulated EDR resource…"),
            ("Retrieving endpoint evidence", "gather", "Retrieving jump-host endpoint evidence…"),
            ("Correlating process/network activity", "correlate", "Comparing EDR with firewall allows…"),
            ("Updating EvidenceState", "evaluate", "EDR is now obtained…"),
            ("Updating InvestigationOutcome", "outcome", "Malicious process activity remains unconfirmed…"),
        ],
    ),
    "check_threat_intel": _continue(
        "s1-ti",
        "check_threat_intel",
        [
            ("Selecting threat-intelligence source", "plan", "Selecting the EC TI fixture…"),
            ("Looking up indicator", "gather", "Looking up the suspicious IP…"),
            ("Evaluating reputation/context", "evaluate", "Fixture lists a suspicious scanner, not a live feed…"),
            ("Updating outcome", "outcome", "Updating InvestigationOutcome…"),
        ],
    ),
    "compare_previous_incidents": _continue(
        "s1-prior",
        "compare_previous_incidents",
        [
            ("Searching prior cases", "plan", "Searching historical tickets…"),
            ("Retrieving ticket", "gather", "Retrieving the overlapping incident…"),
            ("Comparing entities/tactics", "correlate", "Comparing indicator and jump host…"),
            ("Evaluating linkage", "evaluate", "Campaign linkage stays unconfirmed…"),
            ("Updating InvestigationOutcome", "outcome", "Updating supported context…"),
        ],
    ),
    "check_successful_auth": _continue(
        "s1-auth",
        "check_successful_auth",
        [
            ("Checking existing authentication coverage", "plan", "Looking for approved auth saved searches…"),
            ("Reviewing available auth data", "plan", "Checking Splunk auth sourcetypes…"),
            ("Reusing approved auth search", "gather", "Executing governed auth correlation…"),
            ("Correlating svc_jump_ops", "correlate", "Successful logons exist; source IP not proven…"),
            ("Updating EvidenceState", "evaluate", "Auth obtained; compromise still unconfirmed…"),
            ("Updating InvestigationOutcome", "outcome", "Successful authentication not equal to compromise…"),
        ],
    ),
    "check_privileged_accounts": _continue(
        "s1-priv",
        "check_privileged_accounts",
        [
            ("Selecting IAM capability", "plan", "Selecting privileged-account directory…"),
            ("Retrieving account class", "gather", "svc_jump_ops is a privileged service account…"),
            ("Updating InvestigationOutcome", "outcome", "Privileged-account compromise stays unconfirmed…"),
        ],
    ),
    "prepare_firewall_block": _firewall_action("prepare_firewall_block"),
    "create_incident_ticket": _ticket_action("create_incident_ticket"),
    "email_firewall_team": _email_action("email_firewall_team"),
    "verify_firewall_block": _firewall_action("verify_firewall_block"),
    "update_incident": _ticket_action("update_incident"),
    "generate_closure_summary": _closure_action("generate_closure_summary"),
}

S2_FOLLOW_UP_JOURNEYS = {
    "check_dlp": _continue("s2-dlp", "check_dlp", [
        ("Checking existing DLP coverage", "plan", "Looking for approved DLP saved searches…"),
        ("Reviewing available DLP data", "gather", "Checking Splunk DLP indexes and sourcetypes…"),
        ("Reusing approved DLP search", "gather", "Executing governed DLP correlation…"),
        ("Correlating data-movement evidence", "correlate", "No customer-record exfiltration in window…"),
        ("Updating EvidenceState", "evaluate", "DLP window obtained…"),
        ("Updating InvestigationOutcome", "outcome", "Breach still not confirmed…"),
    ]),
    "check_identity": _continue("s2-id", "check_identity", [
        ("Selecting identity evidence", "plan", "Selecting session context…"),
        ("Retrieving identity", "gather", "Interactive session intact…"),
        ("Updating InvestigationOutcome", "outcome", "Session hijack not confirmed…"),
    ]),
    "check_tool_call_history": _continue("s2-tools", "check_tool_call_history", [
        ("Checking existing tool-abuse coverage", "plan", "Reviewing approved tool-audit searches…"),
        ("Reusing existing search where suitable", "gather", "Reusing tool-audit saved search…"),
        ("Searching uncovered tool activity", "gather", "Bounded gap query for uncovered tools…"),
        ("Comparing authorization outcomes", "correlate", "No other unauthorized tools executed…"),
        ("Updating blast radius", "evaluate", "Sensitive tools targeted; no successful unauthorized executions…"),
        ("Updating InvestigationOutcome", "outcome", "Blocked attempt is not a breach…"),
    ]),
    "check_data_source": _continue("s2-data", "check_data_source", [
        ("Selecting restricted-data logs", "plan", "Selecting the datastore audit…"),
        ("Retrieving access logs", "gather", "No unauthorized restricted-table reads…"),
        ("Updating InvestigationOutcome", "outcome", "Restricted-data access not confirmed…"),
    ]),
    "create_ai_incident_ticket": _ticket_action("create_ai_incident_ticket"),
    "notify_app_security": _email_action("notify_app_security"),
    "disable_integration_credential": _iam_action("disable_integration_credential"),
    "verify_credential_state": _iam_action("verify_credential_state"),
    "update_incident": _ticket_action("update_incident"),
}

S7_FOLLOW_UP_JOURNEYS = {
    "check_ot_inventory": _continue("s7-otinv", "check_ot_inventory", [
        ("Selecting OT inventory", "plan", "Selecting OT inventory…"),
        ("Retrieving asset state", "gather", "OT inventory shows the device active…"),
        ("Updating InvestigationOutcome", "outcome", "CMDB may be stale — still not a forced incident…"),
    ]),
    "ask_ot_team": _email_action("ask_ot_team", wait_inbound=True),
    "create_incident_ticket": _ticket_action("create_incident_ticket"),
    "recommend_cmdb_correction": _ticket_action("recommend_cmdb_correction"),
}


_INITIAL = {
    "s1_governed_splunk_investigation": s1_initial,
    "s2_ai_prompt_injection": s2_initial,
    "s3_firewall_team_coordination": s3_initial,
    "s4_zero_day_no_playbook": s4_initial,
    "s5_cisco_hardening_remediation": s5_initial,
    "s6_investigation_continuity": s6_initial,
    "s7_conflicting_ot_evidence": s7_initial,
}

# Auto-applied plan prereads must not replace the canonical 10-step initial animation.
_PREREAD_ONLY_INITIAL: dict[str, frozenset[str]] = {
    "s4_zero_day_no_playbook": frozenset({"show_advisory"}),
}


def _use_initial_journey(scenario_id: str, applied: list[str]) -> bool:
    if not applied:
        return True
    preread = _PREREAD_ONLY_INITIAL.get(scenario_id)
    return bool(preread and set(applied).issubset(preread))

_FOLLOW_UPS: dict[str, dict[str, EcExecutionJourney]] = {
    "s1_governed_splunk_investigation": S1_FOLLOW_UP_JOURNEYS,
    "s2_ai_prompt_injection": S2_FOLLOW_UP_JOURNEYS,
    "s3_firewall_team_coordination": {
        "send_firewall_email": s3_send_waiting(),
        "ingest_firewall_reply": s3_ingest_reply(),
        "create_security_incident": _ticket_action("create_security_incident"),
        "request_ip_block": _firewall_action("request_ip_block"),
        "remove_whitelist": _firewall_action("remove_whitelist"),
        "verify_firewall_rule": _firewall_action("verify_firewall_rule"),
        "notify_soc_lead": _email_action("notify_soc_lead"),
        "reply_firewall_team": _email_action("reply_firewall_team"),
        "update_incident_ticket": _ticket_action("update_incident_ticket"),
    },
    "s4_zero_day_no_playbook": {
        "notify_network_team": _email_action("notify_network_team"),
        "apply_temporary_control": _firewall_action("apply_temporary_control"),
        "verify_temporary_control": _firewall_action("verify_temporary_control"),
        "create_emergency_incident": _ticket_action("create_emergency_incident"),
        "create_change_ticket": _ticket_action("create_change_ticket"),
        "request_agilus_patch": _agilus_action("request_agilus_patch"),
        "restrict_vpn_access": _action(
            "act-s4-restrict-vpn",
            "restrict_vpn_access",
            [
                ("Selecting access policy connector", "plan", "Preparing emergency VPN access restriction…"),
                ("Approval required", "hil", "Restrict VPN access waits for analyst approval…"),
            ],
            header="Access control — restrict VPN",
            system="VPN policy",
            operation="restrict_access",
        ),
        "enforce_mfa_vpn": _action(
            "act-s4-mfa",
            "enforce_mfa_vpn",
            [
                ("Selecting identity policy connector", "plan", "Preparing MFA enforcement policy…"),
                ("Approval required", "hil", "MFA enforcement waits for analyst approval…"),
            ],
            header="Access control — enforce MFA",
            system="Identity",
            operation="enforce_mfa",
        ),
        "run_network_assessment": _continue("s4-net", "run_network_assessment", [
            ("Connecting to CMDB MCP", "gather", "Listing internet-facing VPN gateways…"),
            ("Probing gateway versions", "gather", "Reading EdgeGate software versions…"),
            ("Recording exposure", "evaluate", "Computing partial exposure for vulnerable gateways…"),
        ]),
        "run_splunk_ioc_hunt": _continue("s4-splunk", "run_splunk_ioc_hunt", [
            ("Checking Splunk detections", "gather", "splunk_get_knowledge_objects for advisory…"),
            ("Running governed IOC hunt", "execute", "splunk_run_query across VPN telemetry…"),
            ("Recording hunt results", "evaluate", "No exploitation hits in reviewed window…"),
        ]),
        "run_vuln_scan": _action(
            "act-s4-vuln",
            "run_vuln_scan",
            [
                ("Connecting to vulnerability scanner MCP", "plan", "Selecting authenticated scan target…"),
                ("Running scan", "execute", "Scanning VPN-GW-01/02 for advisory condition…"),
                ("Recording findings", "evaluate", "Critical condition confirmed on vulnerable gateways…"),
            ],
            header="Vulnerability scanner MCP",
            system="Vuln scanner",
            operation="scan",
        ),
        "check_soar_playbooks": _continue("s4-soar", "check_soar_playbooks", [
            ("Querying SOAR registry", "gather", "Searching for VPN zero-day playbook…"),
            ("Listing related playbooks", "evaluate", "PB-EDGE-PATCH and PB-IR-SEV1 recommended…"),
        ]),
        "show_incident_response_plan": _continue("s4-ir", "show_incident_response_plan", [
            ("Querying SOC-KB", "gather", "Retrieving standard Sev-1 IR procedure…"),
            ("Recording IR checklist", "evaluate", "Governed emergency IR steps attached to investigation…"),
        ]),
        "run_investigation": _continue(
            "s4-inv-run",
            "run_investigation",
            [
                ("Connecting to CMDB MCP", "gather", "Resolving internet-facing VPN inventory…"),
                ("Identify VPN gateways", "gather", "12 internet-facing gateways returned…"),
                ("Connecting to Device MCP", "gather", "Probing installed EdgeGate versions…"),
                ("Check affected versions", "evaluate", "4 gateways in affected firmware range…"),
                ("Connecting to Splunk MCP", "execute", "Governed IOC search across VPN telemetry…"),
                ("Hunt exploitation IoCs", "evaluate", "No known IoC hits in reviewed window…"),
                ("Correlate auth anomalies", "correlate", "Unusual privileged management auth on 2 gateways…"),
                ("Agent adaptation", "evaluate", "Adding governed SIEM deep-dive for anomalous auth…"),
            ],
            header="Investigation in progress",
        ),
        "approve_investigation_vuln_scan": _continue(
            "s4-agilus-approve",
            "approve_investigation_vuln_scan",
            [
                ("Connecting to Agilus MCP", "plan", "Resolving governed Agilus endpoint…"),
                ("Authenticating service account", "gather", "Verifying read-only patch-catalog scope…"),
                ("Cross-referencing versions", "execute", "Mapping VPN-GW-01/02/05/08 to vendor catalog…"),
                ("Emergency patch match", "evaluate", "EG-VPN-12.3.5-EMERG applies to outdated builds…"),
                ("Check existing detections", "evaluate", "No threat-specific Splunk detection confirmed…"),
                ("Check SOAR playbooks", "gather", "VPN zero-day playbook not found — related playbooks listed…"),
                ("Retrieve IR guidance", "gather", "SOC-KB Sev-1 IR checklist attached…"),
                ("Synthesizing findings", "outcome", "Investigation complete — review findings below…"),
            ],
            header="Agilus MCP — version and patch analysis",
        ),
        "skip_investigation_vuln_scan": _continue(
            "s4-agilus-skip",
            "skip_investigation_vuln_scan",
            [
                ("Check existing detections", "evaluate", "No threat-specific Splunk detection confirmed…"),
                ("Check SOAR playbooks", "gather", "VPN zero-day playbook not found — related playbooks listed…"),
                ("Retrieve IR guidance", "gather", "SOC-KB Sev-1 IR checklist attached…"),
                ("Synthesizing findings", "outcome", "Investigation complete — review findings below…"),
            ],
            header="Completing investigation",
        ),
        "create_remediation_plan": _continue(
            "s4-rem-plan",
            "create_remediation_plan",
            [
                ("Reviewing investigation outcome", "evaluate", "4 vulnerable · 2 need deeper compromise review…"),
                ("Mapping affected assets", "correlate", "VPN-GW-01, 02, 05, 08 in remediation scope…"),
                ("Selecting compensating controls", "plan", "WAN restriction + step-up MFA for vulnerable gateways…"),
                ("Drafting P1 incident package", "plan", "INC-48219 emergency incident template prepared…"),
                ("Opening emergency change", "plan", "CHG-29173 with network approval gate…"),
                ("Preparing Agilus patch job", "plan", "EG-VPN-12.3.5-EMERG for all 4 gateways…"),
                ("Authoring Splunk monitoring", "plan", "Temporary exploitation alert for vulnerable gateways…"),
                ("Drafting stakeholder email", "plan", "Network + SOC notification draft prepared…"),
                ("Sequencing dependencies", "outcome", "Governed remediation plan ready for approval…"),
            ],
            header="Building remediation plan",
        ),
        "run_remediation": _continue(
            "s4-rem-run",
            "run_remediation",
            [
                ("Create P1 incident", "execute", "ITSM — INC-48219 opened…"),
                ("Create emergency change", "execute", "ITSM — CHG-29173 awaiting network approval…"),
                ("Restrict WAN management", "execute", "Network MCP — compensating control on 4 gateways…"),
                ("Enforce step-up MFA", "execute", "Identity MCP — emergency MFA policy applied…"),
                ("Submit emergency patch", "execute", "Agilus MCP — CHG-29173 linked to patch job…"),
                ("Deploy monitoring", "execute", "Splunk MCP — temporary alert candidate deployed…"),
                ("Notify stakeholders", "execute", "Email / Teams — network and SOC owners notified…"),
                ("Verifying outcomes", "verify", "Confirming controls, tickets, and monitoring state…"),
            ],
            header="Remediation in progress",
        ),
        "apply_access_controls": _action(
            "act-s4-access",
            "apply_access_controls",
            [
                ("Preparing access restrictions", "plan", "VPN session policy + MFA enforcement…"),
                ("Approval required", "hil", "Access controls wait for analyst approval…"),
            ],
            header="Access control policy",
            system="Identity/VPN",
            operation="policy",
        ),
        "deploy_splunk_monitoring": _continue("s4-monitor", "deploy_splunk_monitoring", [
            ("Preparing Splunk alert", "plan", "Governed real-time monitoring search…"),
            ("Validating SPL", "evaluate", "Alert candidate prepared — deployment requires approval…"),
        ]),
    },
    "s5_cisco_hardening_remediation": {
        "show_hardening_policy": _continue("s5-policy", "show_hardening_policy", [
            ("Opening hardening policy source", "plan", "Selecting EC scenario policy knowledge source…"),
            ("Retrieving hardening policy", "gather", "Loading enterprise hardening policy rule…"),
            ("Evaluating policy applicability", "evaluate", "Checking version-gated remediation requirement…"),
        ]),
        "check_current_version": _continue("s5-version", "check_current_version", [
            ("Selecting Cisco version probe", "plan", "Preparing cisco.get_version call…"),
            ("Reading device version", "gather", "Querying simulated Cisco MCP for current_version…"),
            ("Recording version evidence", "evaluate", "Version evidence added to investigation…"),
        ]),
        "check_maintenance_window": _continue("s5-maint", "check_maintenance_window", [
            ("Checking change calendar", "plan", "Looking up maintenance window constraints…"),
            ("Retrieving maintenance window", "gather", "Loading ITSM maintenance schedule…"),
            ("Recording window evidence", "evaluate", "Maintenance window attached to change plan…"),
        ]),
        "update_incident": _ticket_action("update_incident"),
        "generate_closure_summary": _closure_action("generate_closure_summary"),
        "create_change_ticket": _ticket_action("create_change_ticket"),
        "request_network_approval": _email_action("request_network_approval"),
        "approve_upgrade": _cisco_action("approve_upgrade"),
        "execute_upgrade": _cisco_action("execute_upgrade"),
        "verify_version": _cisco_action("verify_version"),
    },
    "s6_investigation_continuity": {
        "fetch_old_incident_ticket": _continue("s6-fetch", "fetch_old_incident_ticket", [
            ("Searching prior cases", "plan", "Selecting the previous ticket…"),
            ("Retrieving ticket", "gather", "Fetching the prior incident…"),
            ("Comparing entities/tactics", "correlate", "Comparing current scope with the prior ticket…"),
        ]),
        "update_incident_ticket": _ticket_action("update_incident_ticket"),
        "notify_incident_owner": _email_action("notify_incident_owner"),
    },
    "s7_conflicting_ot_evidence": S7_FOLLOW_UP_JOURNEYS,
}


def journey_for(scenario_id: str, applied_follow_up_ids: list[str] | None = None) -> EcExecutionJourney | None:
    applied = list(applied_follow_up_ids or [])
    if _use_initial_journey(scenario_id, applied):
        builder = _INITIAL.get(scenario_id)
        if builder is None:
            return None
        return builder()
    last = applied[-1]
    if last:
        if scenario_id == "s6_investigation_continuity" and last in {
            "scope_service_accounts",
            "scope_build_servers",
            "check_last_month_incident",
        }:
            return s6_scope_change(last)
        found = _FOLLOW_UPS.get(scenario_id, {}).get(last)
        if found is not None:
            return found
        return _fallback_non_initial(last)
    return None
