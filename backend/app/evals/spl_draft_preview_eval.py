"""SPL draft preview evaluation — lab-only draft lane checks."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.chat.pipeline import build_live_chat_response
from app.config import settings
from app.schemas.requests import ChatRequest
from app.spl.draft_preview import build_draft_preview, match_detection_family
from app.spl.draft_preview_lint import _scrub_lab_disclaimers, lint_draft_spl


def _scrub_disclaimer_text(text: str) -> str:
    return _scrub_lab_disclaimers(text)

REPO_ROOT = Path(__file__).resolve().parents[3]
QUESTIONS_PATH = REPO_ROOT / "docs" / "evals" / "known_spl_draft_questions.json"
SCHEMA_VERSION = "2026-06-08-spl-draft-preview-v1"

_PROFILE_FLAGS_ON: dict[str, bool] = {
    "ai_soc_spl_draft_preview_enabled": True,
    "ai_soc_spl_template_governance_enabled": True,
    "ai_soc_curated_enrichment_activation_enabled": True,
    "ai_soc_llm_spl_fallback_enabled": False,
    "mcp_global_execution_enabled": False,
    "mcp_server_mock_execution_enabled": False,
    "control_plane_enabled": False,
}

_PROFILE_FLAGS_OFF: dict[str, bool] = {
    "ai_soc_spl_draft_preview_enabled": False,
    "ai_soc_spl_template_governance_enabled": True,
    "ai_soc_curated_enrichment_activation_enabled": True,
    "ai_soc_llm_spl_fallback_enabled": False,
    "mcp_global_execution_enabled": False,
    "mcp_server_mock_execution_enabled": False,
    "control_plane_enabled": False,
}

_RESULTS_FOUND = re.compile(r"\b(results?\s+(?:were\s+)?found|found\s+\d+\s+(?:events?|results?))\b", re.IGNORECASE)
_APPROVED_CLAIM = re.compile(
    r"\b(catalog[\s-]?approved|governed\s+spl\s+draft\s+ready|approved\s+for\s+execution|execution\s+eligible)\b",
    re.IGNORECASE,
)
_EXECUTED_CLAIM = re.compile(r"\b(was\s+executed|executed\s+successfully)\b", re.IGNORECASE)


@dataclass
class DraftEvalRow:
    question_id: str
    family: str
    query: str
    draft_flag: bool
    draft_present: bool
    checks: dict[str, bool]
    violations: list[str]
    draft_preview: dict[str, Any] | None
    execution_status: str | None


@dataclass
class DraftEvalResult:
    schema_version: str
    generated_at: str
    total_rows: int
    passed_rows: int
    failed_rows: int
    rows: list[DraftEvalRow]
    summary_checks: dict[str, int]


def load_questions(path: Path | None = None) -> list[dict[str, Any]]:
    payload = json.loads((path or QUESTIONS_PATH).read_text(encoding="utf-8"))
    return list(payload.get("questions") or [])


@contextmanager
def _eval_settings(profile: dict[str, bool]) -> Iterator[None]:
    originals: dict[str, bool] = {}
    for key, value in profile.items():
        originals[key] = bool(getattr(settings, key))
        setattr(settings, key, value)
    try:
        yield
    finally:
        for key, value in originals.items():
            setattr(settings, key, value)


def _chat_response(query: str, *, draft_enabled: bool) -> Any:
    profile = _PROFILE_FLAGS_ON if draft_enabled else _PROFILE_FLAGS_OFF
    with _eval_settings(profile):
        return build_live_chat_response(ChatRequest(message=query))


def _draft_from_response(response: Any) -> dict[str, Any] | None:
    preview = getattr(response, "spl_draft_preview", None)
    if preview is None:
        return None
    if hasattr(preview, "model_dump"):
        return preview.model_dump()
    return preview if isinstance(preview, dict) else None


def _text_blob(response: Any) -> str:
    parts = [
        str(getattr(response, "message", "") or ""),
        str(getattr(response, "note", "") or ""),
    ]
    analyst = getattr(response, "analyst_response", None)
    if analyst is not None:
        parts.append(str(getattr(analyst, "review_notice", "") or ""))
        parts.append(str(getattr(analyst, "one_sentence_finding", "") or ""))
        parts.append(str(getattr(analyst, "draft_spl_code", "") or ""))
    return "\n".join(parts)


def _evaluate_row(question: dict[str, Any], *, draft_enabled: bool) -> DraftEvalRow:
    query = str(question.get("query") or "")
    question_id = str(question.get("id") or "")
    family = str(question.get("family") or match_detection_family(query) or "")
    response = _chat_response(query, draft_enabled=draft_enabled)
    draft = _draft_from_response(response)
    execution = getattr(response, "execution", None)
    execution_status = str(getattr(execution, "status", "") or "") if execution is not None else None
    spl_validation = getattr(response, "spl_validation", None)
    governed_ready = bool(
        spl_validation is not None
        and getattr(spl_validation, "approved", False)
        and getattr(spl_validation, "normalized_spl", None)
    )
    text = _text_blob(response)
    violations: list[str] = []

    draft_spl = str((draft or {}).get("draft_spl") or "")
    assumptions_text = " ".join((draft or {}).get("assumptions") or [])
    lint_violations = lint_draft_spl(draft_spl, extra_text=assumptions_text) if draft else []
    checks = {
        "draft_only_when_flag_on": (draft is None) if not draft_enabled else (draft is not None),
        "family_match": match_detection_family(query) == family,
        "not_governed": not governed_ready,
        "draft_not_governed_flag": not bool((draft or {}).get("governed")),
        "draft_not_catalog_approved": not bool((draft or {}).get("catalog_approved")),
        "execution_disabled": (draft or {}).get("execution_enabled") is False if draft else True,
        "review_required": (draft or {}).get("review_required") is True if draft else True,
        "warning_present": bool((draft or {}).get("warning")) if draft else True,
        "placeholder_index": "<" in draft_spl if draft else True,
        "validator_ran": bool((draft or {}).get("validator_status")) if draft else True,
        "draft_lint_clean": not lint_violations if draft else True,
        "no_newline_in_quoted_strings": "quoted_string_contains_newline" not in lint_violations if draft else True,
        "windows_paths_escaped": not any(v.startswith("unescaped_windows_path_backslash") for v in lint_violations)
        if draft
        else True,
        "strftime_for_time_fields": "earliest_or_latest_time_without_strftime" not in lint_violations if draft else True,
        "no_execution": execution_status != "executed",
        "no_results_found_claim": _RESULTS_FOUND.search(text) is None,
        "no_approved_claim": _APPROVED_CLAIM.search(_scrub_disclaimer_text(text)) is None,
        "no_executed_claim": _EXECUTED_CLAIM.search(_scrub_disclaimer_text(text)) is None,
    }

    if draft_enabled and draft is None:
        violations.append("expected_draft_missing")
    if not draft_enabled and draft is not None:
        violations.append("draft_present_when_flag_off")
    if draft and draft.get("governed"):
        violations.append("draft_marked_governed")
    if draft and draft.get("execution_enabled") is not False:
        violations.append("draft_execution_enabled")
    if execution_status == "executed":
        violations.append("spl_or_mcp_executed")
    if _RESULTS_FOUND.search(text):
        violations.append("results_found_claim")
    if draft and not draft.get("warning"):
        violations.append("warning_missing")
    if draft and lint_violations:
        violations.extend(lint_violations)
    if family == "windows_account_lockout" and draft:
        if "caller_host" not in draft_spl or "Caller_Computer_Name" not in draft_spl:
            violations.append("lockout_missing_caller_host_fields")
            checks["lockout_caller_host_fields"] = False
        else:
            checks["lockout_caller_host_fields"] = True
    if family == "sysmon_web_shell_spawn" and draft:
        checks["sysmon_pwsh_parent_variants"] = "pwsh.exe" in draft_spl and "tomcat.exe" in draft_spl
        if not checks["sysmon_pwsh_parent_variants"]:
            violations.append("sysmon_missing_pwsh_or_web_parents")

    return DraftEvalRow(
        question_id=question_id,
        family=family,
        query=query,
        draft_flag=draft_enabled,
        draft_present=draft is not None,
        checks=checks,
        violations=violations,
        draft_preview=draft,
        execution_status=execution_status,
    )


def run_spl_draft_preview_eval(
    *,
    questions_path: Path | None = None,
) -> DraftEvalResult:
    questions = load_questions(questions_path)
    rows: list[DraftEvalRow] = []
    for question in questions:
        rows.append(_evaluate_row(question, draft_enabled=False))
        rows.append(_evaluate_row(question, draft_enabled=True))

    passed = sum(1 for row in rows if not row.violations and all(row.checks.values()))
    summary_checks: dict[str, int] = {}
    for row in rows:
        for key, value in row.checks.items():
            summary_checks[key] = summary_checks.get(key, 0) + (1 if value else 0)

    return DraftEvalResult(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_rows=len(rows),
        passed_rows=passed,
        failed_rows=len(rows) - passed,
        rows=rows,
        summary_checks=summary_checks,
    )


def result_to_report(result: DraftEvalResult) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "generated_at": result.generated_at,
        "total_rows": result.total_rows,
        "passed_rows": result.passed_rows,
        "failed_rows": result.failed_rows,
        "summary_checks": result.summary_checks,
        "rows": [
            {
                "question_id": row.question_id,
                "family": row.family,
                "draft_flag": row.draft_flag,
                "draft_present": row.draft_present,
                "execution_status": row.execution_status,
                "checks": row.checks,
                "violations": row.violations,
                "draft_status": (row.draft_preview or {}).get("draft_status"),
                "validator_status": (row.draft_preview or {}).get("validator_status"),
            }
            for row in result.rows
        ],
    }


def render_summary_markdown(result: DraftEvalResult) -> str:
    lines = [
        "# SPL Draft Preview Eval Summary",
        "",
        f"- Generated: {result.generated_at}",
        f"- Rows: {result.total_rows}",
        f"- Passed: {result.passed_rows}",
        f"- Failed: {result.failed_rows}",
        "",
        "## Check counts",
        "",
    ]
    for key, count in sorted(result.summary_checks.items()):
        lines.append(f"- {key}: {count}/{result.total_rows}")
    lines.extend(["", "## Failures", ""])
    failures = [row for row in result.rows if row.violations or not all(row.checks.values())]
    if not failures:
        lines.append("- None")
    else:
        for row in failures:
            lines.append(
                f"- {row.question_id} (flag={'on' if row.draft_flag else 'off'}): "
                f"{', '.join(row.violations) or 'check_failures'}"
            )
    return "\n".join(lines) + "\n"


def write_spl_draft_preview_outputs(
    result: DraftEvalResult,
    *,
    json_path: Path,
    md_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result_to_report(result), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_summary_markdown(result), encoding="utf-8")
