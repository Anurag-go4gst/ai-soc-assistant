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
_AGG_COMMAND = re.compile(r"\b(?:stats|bin|timechart)\b", re.IGNORECASE)
_STRFTIME = re.compile(r"\bstrftime\s*\(", re.IGNORECASE)
_STRFTIME_ON_TIME = re.compile(r"\bstrftime\s*\(\s*(?:_time|event_time|lockout_time)\s*,", re.IGNORECASE)
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
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard_id": self.standard_id,
            "quality_status": self.quality_status,
            "hard_fail_count": self.hard_fail_count,
            "warning_count": self.warning_count,
            "advisory_count": self.advisory_count,
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


def evaluate_draft_quality(spl: str, *, extra_text: str = "") -> DraftQualityReport:
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

    agg_index = _first_agg_index(stages)
    for index, stage in enumerate(stages):
        if not _STRFTIME.search(stage):
            continue
        if agg_index is not None and index < agg_index and _STRFTIME_ON_TIME.search(stage):
            report.add(
                "SOC-STD-SPL-001-Q03",
                "hard_fail",
                "strftime() on event time appears before stats/bin/timechart aggregation.",
            )
            break

    if _EARLIEST_LATEST_RAW.search(spl) and not _STRFTIME.search(spl):
        report.add(
            "SOC-STD-SPL-001-Q04",
            "hard_fail",
            "earliest(_time)/latest(_time) used without readable strftime() output.",
        )

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

    return report.finalize()


def lint_draft_spl(spl: str, *, extra_text: str = "") -> list[str]:
    """Backward-compatible flat violation list (hard_fail and warning only)."""
    report = evaluate_draft_quality(spl, extra_text=extra_text)
    return [
        item.rule_id
        for item in report.findings
        if item.severity in {"hard_fail", "warning"}
    ]
