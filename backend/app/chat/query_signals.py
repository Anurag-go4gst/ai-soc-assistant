"""Deterministic query-signal extraction for the control-plane intent stage."""

from __future__ import annotations

import re
from typing import Any

from app.chat.answer_shape_router import is_regulatory_reporting_query
from app.coverage.hunt_pattern_types import EXACT_105_HUNT_PATTERNS, cisco_hunt_pattern_types
from app.query_understanding.models import QueryUnderstandingResult
from app.query_understanding.soc_investigation_shape import (
    detect_hunt_hypothesis_guidance_phrasing,
    detect_investigation_hypothesis_guidance,
    detect_soc_investigation_shape,
)
from app.query_understanding.success_after_failure import detect_success_after_failure
from app.spl.runtime_source_profiles import resolve_runtime_profile_for_query

_TECHNIQUE_ID_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_MAP_TO_MITRE_RE = re.compile(r"\bmap\b.{0,120}\b(?:mitre|att&ck)\b", re.IGNORECASE)
_LOG_SEARCH_RE = re.compile(
    r"\b(?:search|find|look for)\b.{0,80}\b(?:logs?|firewall|proxy|endpoint|vpn|dns|powershell)\b",
    re.IGNORECASE,
)

_LOG_SEARCH_VERB_RE = re.compile(
    r"\b(?:search|find|show|check|look\s+for|look\s+in|look\s+across|run\s+query)\b",
    re.IGNORECASE,
)
_TELEMETRY_ANCHOR_RE = re.compile(
    r"\b(?:wineventlog|win:eventlog|syslog|cisco_asa|ot_logs|"
    r"firewall\s+logs?|vpn\s+logs?|index\s*=|sourcetype\s*=|"
    r"event\s+id|event\s+\d{3,5}|eventcode|function\s+code)\b",
    re.IGNORECASE,
)
_ENTITY_ANCHOR_RE = re.compile(
    r"\b(?:user\s+\w+|host\s+\w+|\b\d{1,3}(?:\.\d{1,3}){3}\b|cidr|subnet)\b",
    re.IGNORECASE,
)
_T2_SCOPE_ANCHOR_RE = re.compile(
    r"\b(?:src|source|dest|destination|from|to|between|vlan|dmz|zone|substation|"
    r"port\s+\d{1,5}|failed\s+login(?:s)?|event\s+id\s+\d+|eventcode\s*[=:]?\s*\d+)\b",
    re.IGNORECASE,
)
_T2_THRESHOLD_OR_WINDOW_RE = re.compile(
    r"\b(?:more\s+than|over|greater\s+than|at\s+least|>\s*\d+|\d+\+?)\b.{0,40}"
    r"\b(?:failed\s+login(?:s)?|minutes?|hours?|days?)\b",
    re.IGNORECASE,
)
_ANALYTICS_ENUM_RE = re.compile(
    r"\b(?:top|list|which|highest|count)\b.{0,40}\b(?:users?|hosts?|failed\s+login(?:s)?|logon(?:s)?)\b",
    re.IGNORECASE,
)


def _generic_explicit_log_search_floor(normalized: str) -> bool:
    """Broad log-retrieval floor: imperative verb + bounded telemetry/entity anchor."""
    if not _LOG_SEARCH_VERB_RE.search(normalized):
        return False
    if _TELEMETRY_ANCHOR_RE.search(normalized):
        return True
    if _ENTITY_ANCHOR_RE.search(normalized):
        return True
    return bool(_ANALYTICS_ENUM_RE.search(normalized))


def _t2_data_source_count(normalized: str) -> int:
    sources = (
        "wineventlog",
        "win:eventlog",
        "syslog",
        "cisco_asa",
        "ot_logs",
        "firewall",
        "vpn",
        "proxy",
        "endpoint",
        "dns",
        "powershell",
    )
    return sum(1 for source in sources if source in normalized)


def _meaningful_t2_entity_signal(normalized: str) -> bool:
    """Concrete log/query constraints that make LLM slot binding worth the hop."""
    anchors = 0
    anchors += int(bool(_TELEMETRY_ANCHOR_RE.search(normalized)))
    anchors += int(bool(_ENTITY_ANCHOR_RE.search(normalized)))
    anchors += int(bool(_T2_SCOPE_ANCHOR_RE.search(normalized)))
    anchors += int(bool(_T2_THRESHOLD_OR_WINDOW_RE.search(normalized)))
    anchors += int(_t2_data_source_count(normalized) >= 2)
    return anchors >= 2

_ANALYTICS_SUBJECT_RE = re.compile(
    r"\b(?:which|what)\s+(?:hosts?|users?|accounts?|devices?|machines?|systems?|endpoints?|"
    r"domains?|rules?|assets?|source\s+ips?|destination\s+ips?|ips?)\b",
    re.IGNORECASE,
)
_ANALYTICS_RANK_RE = re.compile(
    r"\b(?:most|top|highest|largest|busiest|noisiest|rank|ranked|ranking)\b",
    re.IGNORECASE,
)
# Named detection behaviours / SOC hunt nouns — result-seeking even without a
# ranking word or registry match (e.g. "kerberoasting", "credential dumping").
_DETECTION_TECHNIQUE_RE = re.compile(
    r"\b(?:kerberoast\w*|credential\s+dump\w*|lateral\s+movement|brute[\s-]?force|"
    r"exfil\w*|beacon\w*|c2|command[\s-]and[\s-]control|dga|tunnel\w*|"
    r"privilege\s+escalation|persistence|port\s+scan\w*|scanning|"
    r"shadow\s+cop\w*|log\s+clear\w*|impossible\s+travel|spray\w*)\b",
    re.IGNORECASE,
)
_ANALYTICS_PHRASES = (
    "top talkers",
    "top talker",
    "generating the most",
    "highest volume",
    "largest uploads",
    "largest upload",
    "most smb traffic",
    "most dns queries",
    "most failed logins",
    "top destinations",
    "top ports",
    "top sources",
    "top hosts",
    "still open",
    "open and unresolved",
)
_EXACT_105_MATCH_PATHS = ("exact_105_question", "exact_105_plus_use_case_catalog")


def _explicit_log_search_requested(normalized: str) -> bool:
    if _LOG_SEARCH_RE.search(normalized):
        return True
    return any(
        term in normalized
        for term in (
            "draft a splunk search",
            "draft splunk search",
            "draft spl",
            "write spl",
            "search logs",
            "search firewall logs",
            "search proxy logs",
            "search endpoint logs",
            "search firewall logs for",
            "find vpn logins",
            "find windows servers",
            "look for dns queries",
            "find successful logins",
            "find successful vpn logins",
            "find successful established connections",
            "check logs for",
            "give me current",
            "map all external",
        )
    )




_CVE_ID_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
_PAT_TOKEN_RE = re.compile(r"\b(?:pat|personal access token|leaked pat)\b", re.I)


def is_github_investigation_query(query: str) -> bool:
    """SOC asks about GitHub PAT/workflow/commit/audit investigation (review-only)."""
    normalized = " ".join(str(query or "").lower().split())
    if normalized.startswith("github focus:"):
        return True
    github_ref = any(
        term in normalized
        for term in ("github", "git hub", "github.com", "github actions", "gitlab", "gitea")
    )
    github_artifact = bool(_PAT_TOKEN_RE.search(normalized)) or any(
        term in normalized
        for term in (
            "workflow",
            "workflow_dispatch",
            "repo.push",
            "commit sha",
            "commit timeline",
            "audit log",
            "oauth_access",
            "oauth access",
            "ci workflow",
            "actions workflow",
            "workflow file",
            "push unauthorized",
        )
    )
    return github_ref and github_artifact



def is_cve_focus_query(query: str) -> bool:
    """CVE advisory review without live scanning (review-only)."""
    normalized = " ".join(str(query or "").lower().split())
    if normalized.startswith("cve focus:"):
        return True
    if _CVE_ID_RE.search(query or ""):
        return any(
            term in normalized
            for term in (
                "cisa advisory",
                "what can we confirm",
                "evidence is missing",
                "without live scanning",
                "unpatched",
                "vulnerability",
            )
        )
    return False

def is_cross_skill_investigation_query(query: str) -> bool:
    """Explicit cross-skill review plan (CVE + MITRE + GitHub stitch path)."""
    normalized = " ".join(str(query or "").lower().split())
    if "cross-skill" in normalized or "cross skill" in normalized:
        return True
    has_cve = "cve" in normalized
    has_mitre = "mitre" in normalized or "att&ck" in normalized
    has_github = "github" in normalized or is_github_investigation_query(query)
    # Require all three domains; alert+MITRE+CVE flagship review is not this path.
    return has_cve and has_mitre and has_github

def extract_query_signals(
    query: str,
    query_understanding: QueryUnderstandingResult | None = None,
) -> dict[str, Any]:
    normalized = " ".join(query.lower().split())
    regulatory_reporting = is_regulatory_reporting_query(query)
    qu = query_understanding

    policy_terms = any(
        term in normalized
        for term in (
            "escalation policy",
            "escalation matrix",
            "when should",
            "when to escalate",
            "policy for",
            "what is the policy",
            "escalation criteria",
            "escalation threshold",
            "before escalating",
            "l1 check",
        )
    )
    escalation_without_policy_word = "escalat" in normalized and "policy" not in normalized
    success_after_failure = detect_success_after_failure(normalized)
    failed_login = any(
        term in normalized
        for term in ("failed login", "failed logins", "failed-login", "login failure", "login failures")
    )
    sop_show_request = (
        any(
            term in normalized
            for term in ("playbook", "runbook", "sop", "standard operating procedure", "checklist")
        )
        and (
            ("show" in normalized and "playbook" in normalized)
            or "show me the sop" in normalized
            or "show me the runbook" in normalized
            or normalized.startswith("show sop")
            or normalized.startswith("show runbook")
            # WS1 T1.2: checklist asks are SOP-channel requests even when the
            # topic carries investigation verbs ("checklist for investigating X").
            or ("show" in normalized and "checklist" in normalized)
            or "checklist for" in normalized
            or "soc checklist" in normalized
        )
        and not any(
            term in normalized
            for term in (
                "investigate",
                "failed login",
                "search ",
                "find ",
                "run the spl",
                "run spl",
                "execute spl",
            )
        )
    )
    explicit_run_spl = bool(
        re.search(
            r"\b(run the spl|run spl|run this spl|execute the spl|execute spl|execute this search)\b",
            normalized,
        )
        or re.search(r"\brun this\b.{0,32}\bspl\b", normalized)
        or (
            (
                "give me results" in normalized
                or "give me live results" in normalized
                or "live results" in normalized
            )
            and ("spl" in normalized or "query" in normalized or "search" in normalized)
        )
        or "query splunk" in normalized
        or bool(re.search(r"\bquery splunk directly\b", normalized))
    )
    spl_suppressed = _spl_generation_suppressed(normalized) or sop_show_request
    explicit_log_search = _explicit_log_search_requested(normalized)
    spl_generation = (not spl_suppressed) and (
        _spl_generation_requested(normalized) or explicit_log_search or explicit_run_spl
    )
    run_execution = explicit_run_spl or any(
        term in normalized
        for term in (
            " and run",
            " then run",
            "run it",
            "run this",
            "execute it",
            "execute this",
            "search splunk",
            "run on ",
            "run in ",
        )
    )
    has_specific_scope = any(term in normalized for term in (" index=", "index ", "host=", "host ", "sourcetype=", "sourcetype ", "earliest=", "latest=", "last "))
    live_investigation_verbs = any(
        term in normalized
        for term in (
            "find ",
            "show ",
            "list ",
            "give me",
            "map ",
            "map all",
            "check logs",
            "investigate",
            "search for",
            "search logs",
            "search firewall",
            "search proxy",
            "search endpoint",
            "look for",
            "top users",
            "which users",
            "which hosts",
            "which accounts",
            "which ip",
            "current ",
        )
    ) or explicit_log_search
    negative_successful_login = any(
        term in normalized
        for term in ("no successful login", "no success", "no login success", "without successful login")
    )
    negative_endpoint_telemetry = any(
        term in normalized
        for term in ("no endpoint telemetry", "without endpoint telemetry", "no endpoint evidence")
    )
    negative_credential_dumping = any(
        term in normalized
        for term in ("no evidence of credential dumping", "no credential dumping", "without credential dumping")
    )
    positive_successful_login = success_after_failure or (
        "successful login" in normalized and not negative_successful_login
    )
    spray_breadth = bool(
        re.search(r"\bacross\s+\d+\s+(?:accounts|users)\b", normalized)
        or "many users" in normalized
        or "multiple users" in normalized
        or "password spray" in normalized
        or "password spraying" in normalized
    )
    source_ip_novelty = any(
        term in normalized
        for term in ("new source", "novel source", "unusual source", "new ip", "unusual ip", "unknown device")
    )
    valid_account_abuse = any(
        term in normalized
        for term in (
            "impossible travel",
            "suspicious device",
            "privilege use",
            "privileged action",
            "post-login activity",
            "post login activity",
            "account misuse",
        )
    )
    powershell_context = "powershell" in normalized or "script block" in normalized or "encodedcommand" in normalized
    powershell_command_evidence = powershell_context and any(
        term in normalized for term in ("command line", "command_line", "script block", "process", "event id", "event_id")
    )
    encoded_command = "encodedcommand" in normalized or "encoded command" in normalized or "-enc" in normalized
    suspicious_parent_process = any(
        term in normalized for term in ("parent process", "winword", "excel", "outlook", "wscript", "mshta")
    )
    download_cradle = any(term in normalized for term in ("download cradle", "invoke-webrequest", "iwr ", "http://", "https://"))
    endpoint_network_connection = powershell_context and any(term in normalized for term in ("network connection", "beacon", "outbound"))
    email_auth_failure = any(term in normalized for term in ("spf fail", "dkim fail", "dmarc fail", "authentication-results fail"))
    sender_return_path_mismatch = any(term in normalized for term in ("sender mismatch", "return-path mismatch", "reply-to mismatch", "reply_to mismatch"))
    malicious_url_or_domain = any(term in normalized for term in ("malicious url", "malicious domain", "url verdict", "domain verdict"))
    attachment_hash_verdict = any(term in normalized for term in ("attachment hash", "malicious attachment", "attachment verdict"))
    mail_gateway_verdict = any(term in normalized for term in ("gateway verdict", "mail gateway verdict", "secure email gateway"))
    periodicity = any(term in normalized for term in ("periodic", "periodicity", "regular interval"))
    jitter_profile = "jitter" in normalized
    repeated_destination = any(term in normalized for term in ("repeated destination", "repeated domain", "same domain", "same destination"))
    rare_domain = any(term in normalized for term in ("rare domain", "new domain", "low reputation domain"))
    byte_pattern = any(term in normalized for term in ("bytes out", "byte pattern", "small bytes", "outbound bytes"))
    host_association = any(term in normalized for term in ("host association", "host=", "src host", "user/host", "user host"))
    file_rename_volume = any(term in normalized for term in ("file rename", "rename count", "many files", "mass file"))
    extension_pattern = any(term in normalized for term in ("extension pattern", "new extension", "encrypted extension"))
    encryption_behavior = any(term in normalized for term in ("encryption behavior", "encrypted files", "encrypting files"))
    impacted_paths = any(term in normalized for term in ("affected paths", "impacted paths", "shared drive"))
    process_evidence = any(term in normalized for term in ("process_name", "process name", "process evidence"))
    shadow_copy_deletion = any(term in normalized for term in ("shadow copy", "vssadmin", "delete shadows"))
    service_stop = any(term in normalized for term in ("service stop", "stopped service", "net stop"))
    host_spread = any(term in normalized for term in ("host spread", "multiple hosts", "impacted host"))
    severity_request = "severity" in normalized
    review_only_spl = any(
        term in normalized
        for term in (
            "spl i can review",
            "review-only spl",
            "review only spl",
            "governed spl",
            "not execute",
            "but not execute",
            "without executing",
            "do not execute",
        )
    ) or (("spl" in normalized or "query" in normalized) and "review" in normalized and not run_execution)
    alert_context_present = bool(
        re.search(r"\balt-\d{4}-\d+\b", normalized)
        or re.search(r"\bfor alert\b", normalized)
        or re.search(r"\balert\s+[a-z0-9][\w.-]+\b", normalized)
    )
    explicit_mitre_context = (
        alert_context_present
        or bool(re.search(r"\b\d+\s+(?:failed login|failed-logins|login failure|failed authentication)", normalized))
        or bool(re.search(r"\bacross\s+\d+\s+(?:accounts|users|hosts|sources|ips)\b", normalized))
        or any(term in normalized for term in ("external ip", "external ips", "source ip", "source ips", "no successful login"))
    ) and (
        alert_context_present
        or success_after_failure
        or negative_successful_login
        or negative_endpoint_telemetry
        or negative_credential_dumping
    )
    mitre_explain = bool(_TECHNIQUE_ID_RE.search(query)) and any(
        term in normalized for term in ("explain", "what is", "describe", "meaning of")
    )
    analyst_action = any(
        term in normalized
        for term in (
            "analyst action",
            "what should i do",
            "what should we do",
            "next steps",
            "what do i do",
            "recommended action",
            "tell me what",
        )
    )
    playbook_procedure = any(
        term in normalized
        for term in ("playbook", "runbook", "sop", "standard operating procedure", "procedure steps", "checklist")
    )
    # A definition asks "what is/are <concept>" wanting an explanation. A ranked or
    # aggregated data ask ("what are the top 5 source IPs by DNS volume") is analytics,
    # not a definition — don't let the knowledge branch swallow it into knowledge_recall.
    knowledge_definition = (
        (normalized.startswith("what is ") or normalized.startswith("what are "))
        and not _ANALYTICS_RANK_RE.search(normalized)
        and not _ANALYTICS_SUBJECT_RE.search(normalized)
    )
    dga = "dga" in normalized or "domain generation" in normalized
    block_or_contain = any(
        term in normalized
        for term in (
            "block all",
            "block suspicious",
            "block this ip",
            "block the ip",
            "block the source ip",
            "block source ip",
            "block ip ",
            "block user ",
            "block the user",
            "block this user",
            "block account",
            "block the account",
            "block this account",
            "block on the firewall",
            "push a firewall",
            "push firewall",
            "firewall rule to deny",
            "deny rule",
            # destructive admin / policy-wipe asks (eff.098 class)
            "delete all firewall",
            "delete firewall",
            "remove all firewall",
            "remove firewall rule",
            "wipe firewall",
            "purge firewall",
            "contain ",
            "isolate ",
            "quarantine ",
            "disable all",
            "disable this user",
            "disable the user",
            # account-disable phrasings (oos.unsafe.01 defect): any
            # disable/lock/suspend ask targeting an account is containment.
            "disable the account",
            "disable account",
            "lock the account",
            "suspend the account",
            "disable his account",
            "disable her account",
            "disable their account",
            "kill the process",
            "kill process",
            "quarantine endpoint",
            "isolate the host",
            "isolate host",
            "clear mfa",
            "clear the mfa",
            "reset mfa factor",
            "expire session",
            "expire sessions",
            "expire all session",
            "revoke session",
            "revoke all session",
        )
    ) or bool(
        # disable/lock/suspend targeting any account, with words between
        # ("disable the CEO's account") — containment regardless of phrasing.
        re.search(r"\b(disable|lock|suspend)\b[^.?!]{0,40}\baccount\b", normalized)
    ) or bool(
        # network-segmentation containment phrasings: "cut the link", "sever the
        # connection", "air-gap / segment off the OT network".
        re.search(r"\b(cut|sever)\b[^.?!]{0,24}\b(link|connection|network)\b", normalized)
        or "air-gap" in normalized
        or "air gap" in normalized
        or "segment off" in normalized
    ) or bool(
        # destructive firewall/policy deletion without an explicit "block" verb
        re.search(r"\b(delete|remove|wipe|purge)\b[^.?!]{0,40}\bfirewall\b", normalized)
    ) or bool(
        # process-kill containment with words between verb and noun
        # ("kill the malicious process", "terminate that process").
        re.search(r"\b(kill|terminate)\b[^.?!]{0,30}\bprocess(es)?\b", normalized)
    ) or bool(
        # host/server power-off containment ("shut down the compromised server",
        # "power off the endpoint"). Requires an explicit asset noun so it never
        # trips on log/detection phrasing.
        re.search(
            r"\b(shut\s*down|shutdown|power\s*(off|down))\b[^.?!]{0,30}"
            r"\b(server|host|machine|endpoint|system|box|device|workstation)\b",
            normalized,
        )
    ) or bool(
        # firewall-rule enforcement asks ("add a firewall rule to drop that
        # traffic"). Matches firewall + a drop/deny/block verb in either order;
        # "denied/dropped traffic" (adjective, ASA log queries) is unaffected
        # because it lacks the "firewall" token paired with the imperative verb.
        re.search(r"\b(add|create|insert|apply|push|configure)\b[^.?!]{0,30}\bfirewall\b", normalized)
        or re.search(r"\bfirewall\b[^.?!]{0,30}\b(drop|deny|block)\b", normalized)
    )
    # Containment DECISION-SUPPORT (not an enforcement command): the analyst is
    # asking whether/how to contain, not ordering an action. These must reach the
    # IR/containment advisory shape (review-only staged guidance) instead of the
    # bare unsafe refusal. Conservative: requires interrogative/advisory framing
    # AND must not be an explicit "run it / do it now" enforcement imperative.
    _advisory_framing = any(
        phrase in normalized
        for phrase in (
            "should we",
            "should i",
            "what step",
            "what exact step",
            "how should",
            "how do we",
            "how can we",
            "is it safe to",
            "do we need to",
            "what is the right",
            "what do you recommend",
            "without tripping",
            "without disrupting",
        )
    )
    _enforcement_imperative = any(
        phrase in normalized
        for phrase in (
            "isolate it now",
            "isolate now",
            "right now isolate",
            "do it now",
            "block it now",
            "go ahead and",
            "just isolate",
            "just block",
            "just disable",
        )
    )
    containment_decision_support = bool(
        block_or_contain and _advisory_framing and not _enforcement_imperative and not explicit_run_spl
    )
    conceptual_mitre_judgment = bool(
        re.search(
            r"\b((enough|sufficient) to confirm|alone confirm|treated as lateral movement|prove compromise"
            r"|be confirmed (just |only )?from|confirmed (c2|command and control))\b",
            normalized,
        )
        and "?" in query
    )
    mitre_evidence_threshold = bool(
        normalized.startswith("mitre focus:")
        or (
            ("evidence threshold" in normalized or "status labels" in normalized or "status threshold" in normalized)
            and ("mitre" in normalized or "att&ck" in normalized or "dnp3" in normalized)
        )
        or re.search(
            r"\b(what evidence is needed|evidence (?:is )?needed|required evidence|evidence required)\b.{0,96}"
            r"\b(before|prior to|to declare|to call|to label)\b",
            normalized,
        )
        or re.search(r"\bbefore (?:declaring|calling|labeling|confirming)\b", normalized)
    )
    ot_protocol_investigation = bool(
        re.search(
            r"\b(dnp3|modbus|iec[\s-]?61850|goose|iec[\s-]?104|rtu|pmu|plc|hmi|scada|synchrophasor)\b",
            normalized,
            flags=re.I,
        )
        and re.search(
            r"\b(checklist|triage|hypothes|evidence should|evidence to collect|how to investigate|how to triage|investigate|investigation)\b",
            normalized,
            flags=re.I,
        )
    )
    procedural_investigation = any(
        term in normalized
        for term in (
            "investigation steps",
            "steps for investigation",
            "how to investigate",
            "investigation procedure",
        )
    ) or (
        "explain" in normalized
        and "step" in normalized
        and not live_investigation_verbs
        and not spl_generation
    )
    time_window_24h = any(term in normalized for term in ("last 24 hours", "last 24h", "past 24 hours", "24 hours", "24h"))
    exclude_service_accounts = "exclude service account" in normalized or "excluding service account" in normalized
    top_n_match = re.search(r"\b(?:top|first|limit|head)\s+(\d+)\b", normalized)
    dns_beaconing = any(
        term in normalized
        for term in ("dns beaconing", "beaconing candidate", "beaconing pattern", "dns beacon")
    ) or ("beaconing" in normalized and "dns" in normalized)
    security_log_investigation = any(
        term in normalized
        for term in (
            "dns",
            "firewall",
            "proxy",
            "endpoint",
            "vpn",
            "mfa",
            "authentication",
            "failed login",
            "login attempt",
            "windows",
            "service start",
            "powershell",
            "ot server",
            "scada",
            "control room",
            "engineering workstation",
        )
    )
    investigation_hypothesis_guidance = detect_investigation_hypothesis_guidance(query)
    investigation_triage_guidance = any(
        term in normalized
        for term in (
            "how should soc",
            "how should i investigate",
            "how should we investigate",
            "what should soc",
            "how should we",
            "what should we",
            # WS1 T1.2: paraphrase forms of "how should we investigate".
            # ("next steps" deliberately excluded — it appears inside ordinary
            # hybrid investigation+playbook requests.)
            "what now",
            "what next",
            "how do we proceed",
            "how to proceed",
            "guidance",
            "how should the analyst",
            "what should the analyst",
            "how should soc triage",
            "what should soc check",
            "what should soc investigate",
            "what should soc validate",
            "what should soc review",
            "what should the analyst review",
            "what should l1",
            "what should l1 check",
            "hunting hypotheses",
            "what should i validate",
            "what should we validate",
        )
    ) or investigation_hypothesis_guidance
    guidance_alert_context = alert_context_present and investigation_triage_guidance
    use_case_review_guidance = (
        conceptual_mitre_judgment
        or mitre_evidence_threshold
        or (
            (not alert_context_present or guidance_alert_context)
            and not run_execution
            and (review_only_spl or investigation_triage_guidance)
            and (
                powershell_context
                or dns_beaconing
                or procedural_investigation
                or security_log_investigation
                or investigation_triage_guidance
                or mitre_evidence_threshold
                or any(
                    term in normalized
                    for term in (
                        "analyst checklist",
                        "required evidence",
                        "evidence required",
                        "limitations",
                        "mfa",
                        "failed service",
                        "service start",
                    )
                )
            )
        )
    )
    explicit_search_intent = bool(
        spl_generation
        or explicit_log_search
        or use_case_review_guidance
        or (
            live_investigation_verbs
            and not policy_terms
            and not block_or_contain
            and not spl_suppressed
            and not sop_show_request
        )
    )
    mitre_map = (not use_case_review_guidance) and (
        bool(_MAP_TO_MITRE_RE.search(query))
        or any(
            term in normalized
            for term in ("map to mitre", "map this to mitre", "map alert to mitre", "map this alert")
        )
        or (
            "mitre mapping" in normalized
            and alert_context_present
        )
    )
    # Generic critical/notable alert investigation that asks for MITRE and/or CVE
    # context. Without this, such a query matches no investigation signal and falls
    # to pure `mitre_map` -> knowledge_only (no SPL/MITRE investigation), which made
    # the flagship "review critical alert + cross-reference MITRE + check CVEs" query
    # answer hollow. Scoped tightly (review/investigate verb + alert context +
    # MITRE-or-CVE ask + critical/notable/CVE subject) so pure "explain/map" asks stay
    # knowledge.
    _cve_or_vuln = any(term in normalized for term in ("cve", "unpatched", "vulnerab"))
    _review_verb = any(
        term in normalized
        for term in ("review", "investigate", "triage", "cross-reference", "cross reference", "look into")
    )
    _critical_subject = any(
        term in normalized for term in ("critical alert", "notable", "incident", "affected host")
    )
    critical_alert_review = bool(
        alert_context_present
        and not run_execution
        and _review_verb
        and (mitre_map or _cve_or_vuln)
        and (_critical_subject or _cve_or_vuln)
    )
    hybrid_alert_review = (
        (
            alert_context_present
            and (success_after_failure or failed_login)
            and mitre_map
            and (severity_request or review_only_spl)
            and not run_execution
        )
        or critical_alert_review
    )

    mitre_requires_alert_context = bool(
        not use_case_review_guidance
        and qu
        and qu.clarification_needed
        and "mitre_mapping_requires_alert_context" in (qu.ambiguity_flags or [])
        and not explicit_mitre_context
    )

    analytics_aggregation = bool(
        (_ANALYTICS_SUBJECT_RE.search(normalized) and _ANALYTICS_RANK_RE.search(normalized))
        or any(term in normalized for term in _ANALYTICS_PHRASES)
    )
    exact_105_match = bool(
        qu is not None
        and getattr(qu, "deterministic_match_path", None) in _EXACT_105_MATCH_PATHS
    )
    exact_105_analytics = exact_105_match and bool(
        getattr(qu, "mapped_pattern_type", None) == "top_n_aggregation"
        or getattr(qu, "mapped_primary_skill", None) == "aggregate_and_rank"
        or getattr(qu, "mapped_operation_type", None) in ("top_n", "aggregate_and_rank")
    )
    exact_105_hunt_spl = exact_105_match and (
        getattr(qu, "mapped_pattern_type", None) in EXACT_105_HUNT_PATTERNS
        or getattr(qu, "mapped_pattern_type", None) in cisco_hunt_pattern_types()
    )

    non_soc_or_out_of_scope = any(
        term in normalized
        for term in (
            "hr policy",
            "leave policy",
            "vacation policy",
            "vacation request",
            "payroll",
            "expense policy",
        )
    )
    soc_investigation_shaped = bool(
        detect_soc_investigation_shape(query, exact_105_match=exact_105_match)
        and not block_or_contain
        and not explicit_run_spl
        and not sop_show_request
        and not non_soc_or_out_of_scope
    )

    # Engine-3-safe floor shape signal (intent cascade hardening, Batch 0).
    # CLASS PATTERN, not per-question keywords: an imperative detection verb +
    # a broad security/telemetry subject identifies a SOC-shaped, actionable
    # hunt that should land on the guided floor instead of a hollow
    # clarification dump. Guarded against out-of-scope / containment / explicit
    # run-SPL so those keep their existing honest outcomes.
    soc_actionable_hunt = bool(
        _has_detection_verb(normalized)
        and _has_security_telemetry_subject(normalized)
        and not non_soc_or_out_of_scope
        and not block_or_contain
        and not explicit_run_spl
    )

    # Broad detection/analytics floor (anti-dead-end). Routes result-seeking SOC asks
    # to the governed SPL path (template -> family -> validated LLM T2 producer ->
    # honest scaffold), never a knowledge_recall dead-end. Genuine "how should I
    # investigate" hunts stay guided; knowledge/SOP/explain/unsafe/out-of-scope keep
    # their honest outcomes. Safe because the SPL producer is governed: it validates,
    # quality-lints, and forces execution off (no raw free-form SPL reaches the analyst).
    github_investigation_shaped = is_github_investigation_query(query)
    cross_skill_investigation = is_cross_skill_investigation_query(query)
    cve_focus_investigation = is_cve_focus_query(query)

    guidance_request = bool(
        procedural_investigation
        or investigation_triage_guidance
        or investigation_hypothesis_guidance
        or detect_hunt_hypothesis_guidance_phrasing(query)
        or sop_show_request
        or (playbook_procedure and not live_investigation_verbs)
    )
    _projected_needs_spl = bool(
        (spl_generation and not block_or_contain)
        or (
            live_investigation_verbs
            and not policy_terms
            and not block_or_contain
            and not spl_suppressed
        )
    )
    if (
        not guidance_request
        and not sop_show_request
        and not playbook_procedure
        and not use_case_review_guidance
        and _generic_explicit_log_search_floor(normalized)
    ):
        explicit_log_search = True
        if not spl_suppressed and (
            _TELEMETRY_ANCHOR_RE.search(normalized)
            or _ENTITY_ANCHOR_RE.search(normalized)
        ):
            spl_generation = True
        live_investigation_verbs = live_investigation_verbs or explicit_log_search
        explicit_search_intent = bool(
            spl_generation
            or explicit_log_search
            or use_case_review_guidance
            or (
                live_investigation_verbs
                and not policy_terms
                and not block_or_contain
                and not spl_suppressed
                and not sop_show_request
            )
        )
        _projected_needs_spl = bool(
            (spl_generation and not block_or_contain)
            or (
                live_investigation_verbs
                and not policy_terms
                and not block_or_contain
                and not spl_suppressed
            )
        )

    meaningful_t2_entities = bool(
        not guidance_request
        and not sop_show_request
        and not playbook_procedure
        and not use_case_review_guidance
        and not policy_terms
        and not non_soc_or_out_of_scope
        and not block_or_contain
        and not explicit_run_spl
        and _meaningful_t2_entity_signal(normalized)
    )
    ambiguous_t2_query = bool(
        meaningful_t2_entities
        and (
            "look across" in normalized
            or "across " in normalized
            or _t2_data_source_count(normalized) >= 2
            or bool(re.search(r"\b(?:from|source|src)\b.{0,80}\b(?:to|dest|destination)\b", normalized))
            or bool(re.search(r"\b(?:vlan|zone|dmz|substation)\b.{0,80}\b(?:port|permit|allow|deny)\b", normalized))
        )
    )

    runtime_spl_profile_request = resolve_runtime_profile_for_query(query) is not None

    live_data_request = bool(
        not block_or_contain
        and not explicit_run_spl
        and not guidance_request
        and not mitre_evidence_threshold
        and not use_case_review_guidance
        and not conceptual_mitre_judgment
        and not success_after_failure
        and (
            explicit_search_intent
            or soc_actionable_hunt
            or _projected_needs_spl
            or runtime_spl_profile_request
        )
    )

    soc_detection_intent = bool(
        (
            analytics_aggregation
            or _ANALYTICS_RANK_RE.search(normalized)
            or soc_actionable_hunt
            or explicit_search_intent
            or _DETECTION_TECHNIQUE_RE.search(normalized)
            or runtime_spl_profile_request
        )
        and not knowledge_definition
        and not playbook_procedure
        and not sop_show_request
        and not mitre_explain
        and not non_soc_or_out_of_scope
        and not block_or_contain
        and not explicit_run_spl
        and not (soc_investigation_shaped and guidance_request)
        and not github_investigation_shaped
        and not cve_focus_investigation
    )

    return {
        "normalized_query": normalized,
        "policy_terms": policy_terms,
        "escalation_without_policy_word": escalation_without_policy_word,
        "failed_login": failed_login,
        "spl_generation": spl_generation,
        "spl_suppressed": spl_suppressed,
        "dns_beaconing": dns_beaconing,
        "use_case_review_guidance": use_case_review_guidance,
        "run_execution": run_execution,
        "has_specific_scope": has_specific_scope,
        "live_investigation_verbs": live_investigation_verbs,
        "mitre_map": mitre_map,
        "explicit_mitre_context": explicit_mitre_context,
        "negative_successful_login": negative_successful_login,
        "negative_endpoint_telemetry": negative_endpoint_telemetry,
        "negative_cred_dumping": negative_credential_dumping,
        "mitre_explain": mitre_explain,
        "analyst_action": analyst_action,
        "playbook_procedure": playbook_procedure,
        "knowledge_definition": knowledge_definition,
        "dga": dga,
        "block_or_contain": block_or_contain,
        "conceptual_mitre_judgment": conceptual_mitre_judgment,
        "mitre_evidence_threshold": mitre_evidence_threshold,
        "ot_protocol_investigation": ot_protocol_investigation,
        "sop_show_request": sop_show_request,
        "procedural_investigation": procedural_investigation,
        "time_window_24h": time_window_24h,
        "exclude_service_accounts": exclude_service_accounts,
        "top_n": int(top_n_match.group(1)) if top_n_match else None,
        "mitre_requires_alert_context": mitre_requires_alert_context,
        "explicit_log_search": explicit_log_search,
        "explicit_search_intent": explicit_search_intent,
        "investigation_hypothesis_guidance": investigation_hypothesis_guidance,
        "investigation_triage_guidance": investigation_triage_guidance,
        "security_log_investigation": security_log_investigation,
        "success_after_failure": success_after_failure,
        "positive_successful_login": positive_successful_login,
        "spray_breadth": spray_breadth,
        "source_ip_novelty": source_ip_novelty,
        "valid_account_abuse": valid_account_abuse,
        "powershell_context": powershell_context,
        "powershell_command_evidence": powershell_command_evidence,
        "encoded_command": encoded_command,
        "suspicious_parent_process": suspicious_parent_process,
        "download_cradle": download_cradle,
        "endpoint_network_connection": endpoint_network_connection,
        "email_auth_failure": email_auth_failure,
        "sender_return_path_mismatch": sender_return_path_mismatch,
        "malicious_url_or_domain": malicious_url_or_domain,
        "attachment_hash_verdict": attachment_hash_verdict,
        "mail_gateway_verdict": mail_gateway_verdict,
        "periodicity": periodicity,
        "jitter_profile": jitter_profile,
        "repeated_destination": repeated_destination,
        "rare_domain": rare_domain,
        "byte_pattern": byte_pattern,
        "host_association": host_association,
        "file_rename_volume": file_rename_volume,
        "extension_pattern": extension_pattern,
        "encryption_behavior": encryption_behavior,
        "impacted_paths": impacted_paths,
        "process_evidence": process_evidence,
        "shadow_copy_deletion": shadow_copy_deletion,
        "service_stop": service_stop,
        "host_spread": host_spread,
        "severity_request": severity_request,
        "review_only_spl": review_only_spl,
        "analytics_aggregation": analytics_aggregation,
        "exact_105_analytics": exact_105_analytics,
        "exact_105_hunt_spl": exact_105_hunt_spl,
        "soc_investigation_shaped": soc_investigation_shaped,
        "github_investigation_shaped": github_investigation_shaped,
        "cross_skill_investigation": cross_skill_investigation,
        "cve_focus_investigation": cve_focus_investigation,
        "runtime_spl_profile_request": runtime_spl_profile_request,
        "live_data_request": live_data_request,
        "ambiguous_t2_query": ambiguous_t2_query,
        "meaningful_t2_entities": meaningful_t2_entities,
        "guidance_request": guidance_request,
        "soc_actionable_hunt": soc_actionable_hunt,
        "soc_detection_intent": soc_detection_intent,
        "sop_or_playbook_shaped": bool(playbook_procedure or sop_show_request),
        "spl_authoring_shaped": bool(spl_generation and not run_execution),
        "alert_summary_shaped": bool(alert_context_present and not spl_generation),
        "action_or_containment_shaped": bool(block_or_contain or explicit_run_spl),
        "non_soc_or_out_of_scope": non_soc_or_out_of_scope,
        "alert_context_present": alert_context_present,
        "hybrid_alert_review": hybrid_alert_review,
        "regulatory_reporting": regulatory_reporting,
        "containment_decision_support": containment_decision_support,
        "projected_needs_rag": policy_terms
        or escalation_without_policy_word
        or playbook_procedure
        or procedural_investigation
        or (knowledge_definition and not spl_generation and not live_investigation_verbs),
        "projected_needs_spl": (
            spl_generation
            and not block_or_contain
            or (
                live_investigation_verbs
                and not policy_terms
                and not block_or_contain
                and not spl_suppressed
            )
        ),
        "projected_needs_mcp": (
            live_investigation_verbs
            and not spl_generation
            and not policy_terms
            and not block_or_contain
            and not mitre_map
        )
        or (spl_generation and run_execution and not block_or_contain),
        "requires_hil": block_or_contain or explicit_run_spl,
        "explicit_run_spl": explicit_run_spl,
        "projected_action_mode": "recommend_only" if block_or_contain else None,
    }


# Class patterns for the Engine-3-safe guided floor (Batch 0). These are
# intentionally broad and grouped, not per-question. The verb pattern is an
# imperative detection intent; the subject pattern is a broad security /
# telemetry / OT lexicon. Both must fire (plus the negative guards in
# extract_query_signals) for soc_actionable_hunt.
_DETECTION_VERB_RE = re.compile(
    r"\b(?:show|list|identify|flag|detect|find any|locate|review|correlate|audit|trace|hunt for|"
    r"which hosts|which users|which accounts|which ips?|give me|map|check)\b"
    r"|\balert on\b"
    r"|\b(?:are|is) there\b",
    re.IGNORECASE,
)
_SECURITY_SUBJECT_TERMS = (
    "connection",
    "login",
    "auth",
    "authentication",
    "session",
    "traffic",
    "scan",
    "scanning",
    "packet",
    "icmp",
    "dns",
    "firewall",
    "vlan",
    "vpn",
    "tacacs",
    "ise",
    "duo",
    "mab",
    "goose",
    "mms",
    "modbus",
    "iccp",
    "plc",
    "rtu",
    "hmi",
    "scada",
    "ssh",
    "tls",
    "cipher",
    "driver",
    "process",
    "endpoint",
    "host",
    " ip ",
    "ip address",
    "source ip",
    "port",
    "certificate",
    "config change",
    "configuration change",
    "ios configuration",
    "privilege",
    "privileged",
    "route",
    "routing",
    "ospf",
    "bgp",
    "sgt",
    "umbrella",
    "stealthwatch",
    "firepower",
    "catalyst",
    "setpoint",
    "breaker",
    "relay",
    " ot ",
    "substation",
    "wireless",
    "rogue",
    "malware",
    "kernel",
    "tftp",
    "banner",
    "inverter",
    "transformer",
    "control logic",
    "audit trail",
    "audit log",
    "log process",
    "anyconnect",
    "secure endpoint",
    "secure email",
    "workstation",
    "device profile",
    "broadcast polling",
    "data link",
    "exception code",
    "protocol",
    "gps clock",
    "agc",
    "master station",
    "energy management",
)


def _has_detection_verb(normalized: str) -> bool:
    return bool(_DETECTION_VERB_RE.search(normalized))


def _has_security_telemetry_subject(normalized: str) -> bool:
    padded = f" {normalized} "
    return any(term in padded for term in _SECURITY_SUBJECT_TERMS)


def _spl_generation_suppressed(normalized: str) -> bool:
    if not ("spl" in normalized or "query" in normalized):
        return False
    return any(
        term in normalized
        for term in (
            "do not generate spl",
            "don't generate spl",
            "do not generate a spl",
            "do not generate any spl",
            "no spl",
            "without spl",
            "unless required",
            "unless absolutely required",
        )
    )


def _spl_generation_requested(normalized: str) -> bool:
    explicit_verbs = (
        "generate spl",
        "write spl",
        "create spl",
        "produce spl",
        "build spl",
        "spl query",
        "draft spl",
        "draft a splunk search",
        "draft splunk search",
    )
    if any(term in normalized for term in explicit_verbs):
        return True
    if "spl for" in normalized and "review" not in normalized:
        return True
    if normalized.startswith("draft a splunk") or normalized.startswith("draft splunk"):
        return True
    return False

def is_guidance_request(signals: dict[str, Any]) -> bool:
    """Procedural / triage / SOP asks — not live telemetry retrieval."""
    return bool(signals.get("guidance_request"))


def is_live_data_request(signals: dict[str, Any]) -> bool:
    """Enumeration or search-shaped SOC ask expecting data rows or SPL, not hunt prose."""
    return bool(signals.get("live_data_request"))
