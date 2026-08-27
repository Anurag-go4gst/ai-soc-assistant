"""SOC-STD-SPL-001 — lab-only SPL draft preview quality standard."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

STANDARD_ID = "SOC-STD-SPL-001"
Severity = Literal["hard_fail", "warning", "advisory"]

_QUOTED_STRING = re.compile(r'"(?:\\.|[^"\\])*"', re.DOTALL)
_UNESCAPED_WINDOWS_PATH = re.compile(
    r'"[^"]*(?<![\\])[\\](?![\\/"%])[A-Za-z0-9_.-]+',
)
_AGG_COMMAND = re.compile(r"\b(?:stats|bin|timechart|streamstats)\b", re.IGNORECASE)
_EVENTCODE_4740 = re.compile(r"\bEventCode\s*=\s*4740\b", re.IGNORECASE)
_CALLER_HOST_NORM = re.compile(r"\bcaller_host_norm\b", re.IGNORECASE)
_CALLER_COMPUTER_FIELD = re.compile(r"\bCaller_Computer_Name\b|\bCallerComputerName\b", re.IGNORECASE)
_COMPUTER_NAME_IN_CALLER_COALESCE = re.compile(
    r"caller[_\w]*\s*=\s*lower\s*\(\s*coalesce\s*\([^)]*(?<![\w])ComputerName(?![\w])",
    re.IGNORECASE,
)
_STREAMSTATS = re.compile(r"\bstreamstats\b", re.IGNORECASE)
_SORT_BEFORE_STREAMSTATS = re.compile(r"\bsort\s+0\s*\+\s*_time\b", re.IGNORECASE)
_BROKEN_HMI_REGEX = re.compile(r"\(\?i\)hmi\\n\s*\|\s*portal", re.IGNORECASE)
_FUZZY_ESP_ZONE = re.compile(
    r'like\s*\(\s*(?:src|dest)_zone_norm\s*,\s*"%',
    re.IGNORECASE,
)
_FUZZY_SESSION_STATE = re.compile(
    r'like\s*\(\s*session_state_norm\s*,\s*["\']%',
    re.IGNORECASE,
)
_ESP_NOISY_WILDCARD = re.compile(r"\(\s*\*it\*|\*corporate\*|\*ot\*|\*control\*", re.IGNORECASE)
_ESP_BLANK_SESSION_PASS = re.compile(r'session_state_norm\s*=\s*""', re.IGNORECASE)
_STRFTIME = re.compile(r"\bstrftime\s*\(", re.IGNORECASE)
_STRFTIME_ON_TIME = re.compile(
    r"\bstrftime\s*\(\s*(?:_time|event_time|lockout_time)\s*,",
    re.IGNORECASE,
)
_EVAL_ASSIGN = re.compile(r"\b(\w+)\s*=", re.IGNORECASE)
_TABLE_STAGE = re.compile(r"^\s*table\s+(.+)$", re.IGNORECASE)
_FIELDS_DROP = re.compile(r"^\s*fields\s+-\s+(.+)$", re.IGNORECASE)
_STATS_BY = re.compile(r"\bby\s+(.+)$", re.IGNORECASE | re.DOTALL)
_STATS_AS = re.compile(r"\bas\s+(\w+)\b", re.IGNORECASE)

_FAMILY_SHIFT_LEFT: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
    "windows_account_lockout": ((re.compile(r"EventCode\s*=\s*4740", re.I), "EventCode=4740"),),
    "sysmon_web_shell_spawn": ((re.compile(r"EventCode\s*=\s*1\b", re.I), "EventCode=1"),),
    "windows_privileged_group_changes": (
        (re.compile(r"EventCode\s*=\s*4728", re.I), "EventCode=4728/4732/4756"),
    ),
    "esp_it_to_ot_connection": (
        (re.compile(r"action\s*=\s*(?:allowed|accept|permit|success)", re.I), "action=allowed|accept|permit|success"),
    ),
    "firewall_it_ot_rdp": (
        (re.compile(r"action\s*=\s*(?:allowed|accept|permit|success)", re.I), "action=allowed|accept|permit|success"),
    ),
    "firewall_vendor_vpn_jump": (
        (re.compile(r"action\s*=\s*(?:allowed|accept|permit|success)", re.I), "action=allowed|accept|permit|success"),
    ),
    "firewall_ot_smb_lateral": (
        (re.compile(r"action\s*=\s*(?:allowed|accept|permit|success)", re.I), "action=allowed|accept|permit|success"),
    ),
    "firewall_ot_egress_denied": (
        (re.compile(r"action\s*=\s*(?:denied|blocked|drop|reject)", re.I), "action=denied|blocked|drop|reject"),
    ),
    "substation_hmi_brute_force": (
        (re.compile(r"\b(?:failure|fail|denied)\b", re.I), "(failure OR fail OR denied)"),
    ),
    "scada_dnp3_modbus_write": (
        (re.compile(r"\*dnp3\*|\*modbus\*", re.I), "(*dnp3* OR *modbus*)"),
    ),
}

_DELAYABLE_STATIC: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bEventCode\s*=\s*4740\b", re.I), "EventCode=4740"),
    (re.compile(r"\bEventCode\s*=\s*1\b", re.I), "EventCode=1"),
    (re.compile(r"\bEventCode\s*=\s*4728\b", re.I), "EventCode 4728/4732/4756"),
    (re.compile(r"\baction\s*=\s*allowed\b", re.I), "action=allowed"),
    (re.compile(r"\b(?:failure|fail|denied)\b", re.I), "failure/fail/denied"),
)
_CRITICAL_TABLE_FIELDS = frozenset(
    {
        "src_zone",
        "dest_zone",
        "src_zones",
        "dest_zones",
        "rule",
        "firewall_rules",
        "app",
        "applications",
        "caller_host",
        "caller_hosts",
        "command_line",
        "command_line_norm",
        "parent_image",
        "parent_image_norm",
        "child_image",
        "child_image_norm",
        "target_user",
        "target_user_norm",
        "added_user",
        "added_users",
        "group_name",
        "group_norm",
        "protocol",
        "protocol_norm",
        "protocols",
        "dest_port",
        "dest_port_norm",
        "dest_ports",
        "action",
        "action_norm",
        "actions",
        "session_state",
        "session_state_norm",
        "session_states",
    }
)
_EARLIEST_LATEST_RAW = re.compile(r"\b(?:earliest|latest)\s*\(\s*_time\s*\)", re.IGNORECASE)
_CIDR_IN = re.compile(r"\b(?:src_ip|dest_ip|source_ip|destination_ip)\s+IN\s*\(", re.IGNORECASE)
_COALESCE = re.compile(r"\bcoalesce\s*\(", re.IGNORECASE)
_CIDRMATCH = re.compile(r"\bcidrmatch\s*\(", re.IGNORECASE)
_SEARCH_BASE = re.compile(r"^\s*search\b", re.IGNORECASE)
_INDEX_SOURCETYPE = re.compile(r"\bindex\s*=", re.IGNORECASE)
_STATIC_FILTER = re.compile(
    r"\b(?:EventCode|action|protocol|src_zone|dest_zone)\s*=",
    re.IGNORECASE,
)

_PROHIBITED_CLAIMS = re.compile(
    r"\b("
    r"results?\s+(?:were\s+)?found|"
    r"found\s+\d+\s+(?:events?|results?)|"
    r"catalog[\s-]?approved|"
    r"governed\s+spl|"
    r"approved\s+for\s+execution|"
    r"execution\s+eligible|"
    r"was\s+executed|"
    r"executed\s+successfully"
    r")\b",
    re.IGNORECASE,
)

# OPTIONAL_PHASE_S S1 — advisory efficiency detectors (never hard_fail / warning).
_BASE_NOT_NE = re.compile(
    r"(?:(?<![\w])NOT(?![\w])\s+)|(?:!=)",
    re.IGNORECASE,
)
_SAME_FIELD_OR = re.compile(
    r"\b([A-Za-z_][\w.]*)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s|()]+)"
    r"(?:\s+OR\s+\1\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s|()]+))+",
    re.IGNORECASE,
)
_OR_TOKEN = re.compile(r"\bOR\b", re.IGNORECASE)
_TERM_WRAP = re.compile(r"\bTERM\s*\(", re.IGNORECASE)
_MINOR_BREAKER_TOKEN = re.compile(
    r"(?<![\w.])(?![A-Za-z_][\w.]*\s*=)([A-Za-z0-9][\w]*[._][\w.]+)(?![\w])",
)
_LEADING_WILDCARD_TERM = re.compile(
    r"(?<![\w=])\*(?!\s)[A-Za-z0-9_]{1,24}\b",
)
_NON_STREAMING_CMD = re.compile(r"^\s*(?:sort|stats)\b", re.IGNORECASE)
_FIELDS_KEEP = re.compile(r"^\s*fields\s+(?!-)", re.IGNORECASE)

OptimizationClass = Literal[
    "PASS",
    "AUTO_FIX_SAFE",
    "OPTIMIZATION_LLM_REQUIRED",
    "NO_SAFE_OPTIMIZATION",
]

# Same-field OR chain length at/above this → Q04 advisory (tune vs bank; start ~10).
_Q04_OR_CHAIN_THRESHOLD = 10


@dataclass(frozen=True)
class QualityFinding:
    rule_id: str
    severity: Severity
    message: str


@dataclass
class DraftQualityReport:
    standard_id: str = STANDARD_ID
    quality_status: str = "passed"
    hard_fail_count: int = 0
    warning_count: int = 0
    advisory_count: int = 0
    findings: list[QualityFinding] = field(default_factory=list)
    optimization_classification: OptimizationClass = "PASS"

    def add(self, rule_id: str, severity: Severity, message: str) -> None:
        self.findings.append(QualityFinding(rule_id=rule_id, severity=severity, message=message))
        if severity == "hard_fail":
            self.hard_fail_count += 1
        elif severity == "warning":
            self.warning_count += 1
        else:
            self.advisory_count += 1

    def finalize(self) -> "DraftQualityReport":
        if self.hard_fail_count:
            self.quality_status = "failed"
        elif self.warning_count:
            self.quality_status = "warning"
        else:
            self.quality_status = "passed"
        self.optimization_classification = classify_optimization(self)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard_id": self.standard_id,
            "quality_status": self.quality_status,
            "hard_fail_count": self.hard_fail_count,
            "warning_count": self.warning_count,
            "advisory_count": self.advisory_count,
            "optimization_classification": self.optimization_classification,
            "findings": [
                {"rule_id": item.rule_id, "severity": item.severity, "message": item.message}
                for item in self.findings
            ],
        }

    def violation_ids(self) -> list[str]:
        return [f"{item.rule_id}:{item.severity}" for item in self.findings]


def _scrub_lab_disclaimers(text: str) -> str:
    scrubbed = (text or "").lower()
    for safe in (
        "not catalog-approved",
        "not catalog approved",
        "not governed",
        "not approved",
        "do not execute",
        "without soc review",
        # Honest review-only / not-executed disclaimers must be scrubbed before
        # execution-claim detection so phrases like "no live query was executed" are
        # not misread as "was executed".
        "no live query was executed",
        "no mcp execution was run",
        "has not been executed",
        "not been executed",
        "review-only spl draft",
        "review-only",
    ):
        scrubbed = scrubbed.replace(safe, "")
    return scrubbed


def _pipeline_stages(spl: str) -> list[str]:
    return [stage.strip() for stage in spl.split("|")]


def _first_agg_index(stages: list[str]) -> int | None:
    for index, stage in enumerate(stages):
        if _AGG_COMMAND.search(stage):
            return index
    return None


def _table_columns(table_stage: str) -> list[str]:
    match = _TABLE_STAGE.match(table_stage.strip())
    if not match:
        return []
    return [token for token in match.group(1).split() if token and token != "-"]


def _eval_assignments(stage: str) -> set[str]:
    if not stage.lower().startswith("eval "):
        return set()
    return set(_EVAL_ASSIGN.findall(stage))


def _stats_outputs(stage: str) -> set[str]:
    outputs: set[str] = set()
    by_match = _STATS_BY.search(stage)
    if by_match:
        outputs.update(token for token in re.findall(r"\b\w+\b", by_match.group(1)) if token.lower() != "by")
    outputs.update(_STATS_AS.findall(stage))
    return outputs


def _available_fields_at_table(stages: list[str]) -> set[str] | None:
    agg_index = _first_agg_index(stages)
    if agg_index is None:
        return None
    available: set[str] = set()
    for index, stage in enumerate(stages):
        lowered = stage.lower()
        if lowered.startswith("table "):
            return available
        if index < agg_index and lowered.startswith("eval "):
            available.update(_eval_assignments(stage))
        elif _AGG_COMMAND.search(stage):
            available = _stats_outputs(stage)
        elif index > agg_index and lowered.startswith("eval "):
            available.update(_eval_assignments(stage))
        elif lowered.startswith("fields -"):
            drop_match = _FIELDS_DROP.match(stage.strip())
            if drop_match:
                available -= set(drop_match.group(1).split())
    return available


def _check_shift_left(
    report: DraftQualityReport,
    stages: list[str],
    *,
    detection_family: str | None,
) -> None:
    if not stages or not _SEARCH_BASE.search(stages[0]):
        return
    search_line = stages[0]

    if detection_family:
        for pattern, label in _FAMILY_SHIFT_LEFT.get(detection_family, ()):
            if pattern.search(search_line):
                continue
            if any(pattern.search(stage) for stage in stages):
                report.add(
                    "SOC-STD-SPL-001-U01",
                    "hard_fail",
                    f"Shift-left: {label} must appear in base search before the first pipe.",
                )

    for pattern, label in _DELAYABLE_STATIC:
        if pattern.search(search_line):
            continue
        if any(pattern.search(stage) for stage in stages[1:4]):
            report.add(
                "SOC-STD-SPL-001-U01",
                "warning",
                f"Static filter {label} should shift-left into base search when known.",
            )


def _check_native_time(report: DraftQualityReport, stages: list[str]) -> None:
    agg_index = _first_agg_index(stages)
    for index, stage in enumerate(stages):
        if not _STRFTIME.search(stage):
            continue
        if agg_index is not None and index < agg_index and _STRFTIME_ON_TIME.search(stage):
            report.add(
                "SOC-STD-SPL-001-U02",
                "hard_fail",
                "strftime(_time, ...) appears before bin/stats/streamstats/timechart.",
            )
            break
        if agg_index is None and _STRFTIME_ON_TIME.search(stage):
            # Event-level presentation after sort is allowed (no aggregation pipeline).
            if not any(stage.lower().startswith("sort") for stage in stages[:index]):
                report.add(
                    "SOC-STD-SPL-001-U02",
                    "warning",
                    "strftime(_time, ...) without prior sort/aggregation — prefer epoch alias after stats.",
                )


def _check_stats_inclusion(report: DraftQualityReport, stages: list[str]) -> None:
    table_index = next(
        (index for index, stage in enumerate(stages) if stage.lower().startswith("table ")),
        None,
    )
    if table_index is None:
        return
    available = _available_fields_at_table(stages)
    if available is None:
        return
    table_cols = _table_columns(stages[table_index])
    for column in table_cols:
        if column in available:
            continue
        severity: Severity = "hard_fail" if column in _CRITICAL_TABLE_FIELDS else "warning"
        report.add(
            "SOC-STD-SPL-001-U03",
            severity,
            f"Final table references `{column}` not preserved through stats/streamstats.",
        )


def _base_search_text(stages: list[str]) -> str:
    if stages and _SEARCH_BASE.search(stages[0]):
        return stages[0]
    return stages[0] if stages else ""


def _count_same_field_or_values(match: re.Match[str]) -> int:
    fragment = match.group(0)
    # field=value appears once per OR arm; count '=' occurrences in the matched fragment.
    return fragment.count("=")


def _check_efficiency_advisories(report: DraftQualityReport, stages: list[str], spl: str) -> None:
    """OPTIONAL_PHASE_S S1 — advisory-only efficiency gaps. Never promote severity."""
    base = _base_search_text(stages)

    # Q03 — broad NOT / != in base search / early stages
    early = " | ".join(stages[:3]) if stages else spl
    if _BASE_NOT_NE.search(early):
        report.add(
            "SOC-STD-SPL-001-Q03",
            "advisory",
            "Prefer positive value matches over broad NOT / != in early search stages "
            "(https://docs.splunk.com/Documentation/SplunkCloud/latest/Search/Writebettersearches).",
        )

    # Q04 — excessive same-context OR chain (same field)
    for match in _SAME_FIELD_OR.finditer(base or spl):
        if _count_same_field_or_values(match) >= _Q04_OR_CHAIN_THRESHOLD:
            report.add(
                "SOC-STD-SPL-001-Q04",
                "advisory",
                f"Excessive same-field OR chain (≥{_Q04_OR_CHAIN_THRESHOLD}); prefer IN() or a lookup.",
            )
            break

    # Q15 — TERM() candidate for minor-breaker tokens in base search
    if base and not _TERM_WRAP.search(base):
        for token_match in _MINOR_BREAKER_TOKEN.finditer(base):
            token = token_match.group(1)
            if "index" in token.lower() or "sourcetype" in token.lower():
                continue
            if "=" in token_match.group(0):
                continue
            # Skip field=value left-hand sides already handled elsewhere.
            report.add(
                "SOC-STD-SPL-001-Q15",
                "advisory",
                f"Minor-breaker token {token!r} may benefit from TERM() wrapping.",
            )
            break

    # Q16 — generic leading wildcard in search terms (not index=*) — do not touch Q13
    if _LEADING_WILDCARD_TERM.search(base or spl):
        report.add(
            "SOC-STD-SPL-001-Q16",
            "advisory",
            "Leading wildcard in a search term is expensive; prefer trailing wildcards or exact tokens.",
        )

    # Q17 — non-streaming commands earlier than necessary; carve out Q11 sort-before-streamstats
    stream_index = next(
        (index for index, stage in enumerate(stages) if _STREAMSTATS.search(stage)),
        None,
    )
    for index, stage in enumerate(stages):
        if not _NON_STREAMING_CMD.search(stage):
            continue
        # Q11 carve-out: required `sort 0 + _time` immediately before streamstats
        if (
            stream_index is not None
            and index < stream_index
            and _SORT_BEFORE_STREAMSTATS.search(stage)
        ):
            continue
        later = [
            j
            for j in range(index + 1, len(stages))
            if _AGG_COMMAND.search(stages[j]) or _NON_STREAMING_CMD.search(stages[j])
        ]
        if not later:
            continue
        intervening = stages[index + 1 : later[0]]
        if any(s.lower().startswith(("search ", "where ")) for s in intervening):
            report.add(
                "SOC-STD-SPL-001-Q17",
                "advisory",
                "Non-streaming command (sort/stats) appears earlier than necessary; "
                "keep filtering before aggregation when equivalence holds.",
            )
            break

    # Q18 — early projection opportunity (wide pipeline, no fields before first aggregation)
    # Compatible with U03: do not advise dropping fields that a later table requires.
    agg_index = _first_agg_index(stages)
    if agg_index is not None and agg_index >= 2:
        has_fields_before_agg = any(_FIELDS_KEEP.search(stage) for stage in stages[:agg_index])
        if not has_fields_before_agg:
            # If U03-critical table columns are present, still allow advisory — projection
            # should keep those columns; message states keep required outputs.
            report.add(
                "SOC-STD-SPL-001-Q18",
                "advisory",
                "Wide pipeline with no `fields` projection before first aggregation; "
                "project unused columns early while preserving U03-required outputs.",
            )


def classify_optimization(report: DraftQualityReport) -> OptimizationClass:
    """Map advisory efficiency findings to Layer-2/3 routing metadata (no authority change)."""
    if not report.findings and not report.advisory_count:
        return "PASS"

    advisory_ids = {
        item.rule_id
        for item in report.findings
        if item.severity == "advisory"
        and item.rule_id.startswith("SOC-STD-SPL-001-Q")
        and item.rule_id.split("-")[-1] in {"Q03", "Q04", "Q15", "Q16", "Q17", "Q18"}
    }
    if not advisory_ids:
        return "PASS"

    # AUTO_FIX_SAFE only when the sole efficiency signal is Q04 (same-field OR → IN).
    if advisory_ids == {"SOC-STD-SPL-001-Q04"}:
        return "AUTO_FIX_SAFE"

    llm_ids = {
        "SOC-STD-SPL-001-Q03",
        "SOC-STD-SPL-001-Q15",
        "SOC-STD-SPL-001-Q16",
        "SOC-STD-SPL-001-Q17",
        "SOC-STD-SPL-001-Q18",
    }
    if advisory_ids & llm_ids:
        return "OPTIMIZATION_LLM_REQUIRED"

    # Q04 mixed with non-efficiency advisories still routes to safe rewrite.
    if "SOC-STD-SPL-001-Q04" in advisory_ids:
        return "AUTO_FIX_SAFE"

    return "NO_SAFE_OPTIMIZATION"


def evaluate_draft_quality(
    spl: str,
    *,
    extra_text: str = "",
    detection_family: str | None = None,
) -> DraftQualityReport:
    """Evaluate draft SPL against SOC-STD-SPL-001."""
    report = DraftQualityReport()
    stages = _pipeline_stages(spl)
    combined_text = f"{spl}\n{extra_text}"

    for match in _QUOTED_STRING.finditer(spl):
        if "\n" in match.group(0) or "\r" in match.group(0):
            report.add(
                "SOC-STD-SPL-001-Q01",
                "hard_fail",
                "Quoted SPL string contains a newline.",
            )
            break

    for match in _UNESCAPED_WINDOWS_PATH.finditer(spl):
        report.add(
            "SOC-STD-SPL-001-Q02",
            "hard_fail",
            f"Unescaped Windows path backslash in {match.group(0)[:48]!r}.",
        )

    _check_native_time(report, stages)

    if _EARLIEST_LATEST_RAW.search(spl) and not _STRFTIME.search(spl):
        report.add(
            "SOC-STD-SPL-001-U02",
            "hard_fail",
            "earliest(_time)/latest(_time) used without readable strftime() after stats.",
        )

    _check_shift_left(report, stages, detection_family=detection_family)
    _check_stats_inclusion(report, stages)

    if _PROHIBITED_CLAIMS.search(_scrub_lab_disclaimers(combined_text)):
        report.add(
            "SOC-STD-SPL-001-Q05",
            "hard_fail",
            "Draft text implies executed, approved, or governed SPL.",
        )

    eval_stages = [stage for stage in stages if stage.lower().startswith("eval ")]
    if eval_stages and not _COALESCE.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q06",
            "advisory",
            "Draft uses eval stages but no coalesce() field normalization.",
        )
    elif eval_stages and len(_COALESCE.findall(spl)) < 2:
        report.add(
            "SOC-STD-SPL-001-Q06",
            "advisory",
            "Draft should prefer coalesce() for common multi-vendor field aliases.",
        )

    if _CIDR_IN.search(spl) and not _CIDRMATCH.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q07",
            "warning",
            "CIDR logic uses IN() instead of cidrmatch().",
        )

    if stages and _SEARCH_BASE.search(stages[0]):
        if not _INDEX_SOURCETYPE.search(stages[0]):
            report.add(
                "SOC-STD-SPL-001-Q08",
                "advisory",
                "Base search should include index= and sourcetype= placeholders.",
            )
        if not _STATIC_FILTER.search(spl):
            report.add(
                "SOC-STD-SPL-001-Q09",
                "advisory",
                "Base search should include static EventCode/action/protocol filters where available.",
            )
    else:
        report.add(
            "SOC-STD-SPL-001-Q08",
            "warning",
            "Draft does not start with a search command.",
        )

    if _EVENTCODE_4740.search(spl):
        if not _CALLER_COMPUTER_FIELD.search(spl) or not _CALLER_HOST_NORM.search(spl):
            report.add(
                "SOC-STD-SPL-001-Q10",
                "hard_fail",
                "Event 4740 draft must use caller_host_norm with Caller_Computer_Name/CallerComputerName coalesce.",
            )
        if _COMPUTER_NAME_IN_CALLER_COALESCE.search(spl):
            report.add(
                "SOC-STD-SPL-001-Q10",
                "hard_fail",
                "Event 4740 draft must not use ComputerName in caller_host coalesce (DC/collector field).",
            )

    if _STREAMSTATS.search(spl):
        stream_index = next(
            (index for index, stage in enumerate(stages) if _STREAMSTATS.search(stage)),
            None,
        )
        if stream_index is not None and not any(
            _SORT_BEFORE_STREAMSTATS.search(stage) for stage in stages[:stream_index]
        ):
            report.add(
                "SOC-STD-SPL-001-Q11",
                "hard_fail",
                "streamstats rolling window requires explicit `sort 0 + _time` before streamstats.",
            )

    if _BROKEN_HMI_REGEX.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q01",
            "hard_fail",
            "Broken multiline regex in quoted string (HMI/portal pattern).",
        )

    if detection_family == "substation_hmi_brute_force" and not _STREAMSTATS.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q11",
            "hard_fail",
            "HMI brute-force family must use streamstats time_window=5m rolling window.",
        )

    if detection_family == "esp_it_to_ot_connection" and _FUZZY_ESP_ZONE.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q12",
            "warning",
            "ESP IT→OT zone matching should use exact IN() zone labels or cidrmatch(), not fuzzy like() substrings.",
        )

    if detection_family == "esp_it_to_ot_connection" and _ESP_NOISY_WILDCARD.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q13",
            "hard_fail",
            "ESP IT→OT base search must not use noisy short wildcards (*it*, *corporate*, *ot*, *control*).",
        )

    if detection_family == "esp_it_to_ot_connection" and _ESP_BLANK_SESSION_PASS.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q13",
            "hard_fail",
            "ESP IT→OT draft must not treat blank session_state_norm as established.",
        )

    if (
        detection_family
        and (
            detection_family.startswith("esp_")
            or detection_family.startswith("firewall_")
        )
        and _FUZZY_SESSION_STATE.search(spl)
    ):
        report.add(
            "SOC-STD-SPL-001-Q14",
            "hard_fail",
            "Firewall draft must use strict session_state_norm IN() values only, not fuzzy like() matching.",
        )

    # OPTIONAL_PHASE_S S1 — advisory efficiency detectors (after hard rules; never raise severity).
    _check_efficiency_advisories(report, stages, spl)

    return report.finalize()


def lint_draft_spl(spl: str, *, extra_text: str = "") -> list[str]:
    """Backward-compatible flat violation list (hard_fail and warning only)."""
    report = evaluate_draft_quality(spl, extra_text=extra_text)
    return [
        item.rule_id
        for item in report.findings
        if item.severity in {"hard_fail", "warning"}
    ]
