"""Deterministic golden-answer regression runner."""

from __future__ import annotations

import argparse
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from app.api.routes_chat import chat
from app.config import settings
from app.evals.golden_answers.schema import GoldenCase, GoldenCaseError, load_jsonl_cases
from app.schemas.requests import ChatRequest

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASE_DIR = Path(__file__).resolve().parent / "golden_answers"
DEFAULT_REPORT_JSON = REPO_ROOT / "docs" / "evals" / "out" / "golden_answer_eval.json"
DEFAULT_REPORT_MD = REPO_ROOT / "docs" / "evals" / "out" / "golden_answer_eval.md"

SAFE_ENV_DEFAULTS: dict[str, str] = {
    "CONTROL_PLANE_ENABLED": "true",
    "MCP_GLOBAL_EXECUTION_ENABLED": "false",
    "MCP_SERVER_MOCK_EXECUTION_ENABLED": "false",
    "AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED": "false",
    "AI_SOC_LLM_ANSWER_GUARD_ENABLED": "false",
}

SAFE_SETTING_DEFAULTS: dict[str, Any] = {
    "control_plane_enabled": True,
    "mcp_global_execution_enabled": False,
    "mcp_server_mock_execution_enabled": False,
    "ai_soc_llm_final_synthesis_enabled": False,
    "ai_soc_llm_answer_guard_enabled": False,
    "ai_soc_llm_live_synthesis_enabled": False,
    "soc_kb_retrieval_enabled": True,
    "spl_allowed_sourcetypes": "pgcil:auth,aws:cloudtrail",
}


@dataclass
class AssertionFailure:
    path: str
    expected: Any
    observed: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseResult:
    case_id: str
    tier: int
    source: str
    category: str
    query: str
    passed: bool
    failures: list[AssertionFailure] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tier": self.tier,
            "source": self.source,
            "category": self.category,
            "query": self.query,
            "passed": self.passed,
            "failures": [failure.to_dict() for failure in self.failures],
            "observed": self.observed,
        }


@dataclass
class RunnerSummary:
    generated_at: str
    overall_pass: bool
    case_count: int
    passed_count: int
    failed_count: int
    by_tier: dict[str, dict[str, int]]
    by_category: dict[str, dict[str, int]]
    case_files: list[str]
    results: list[CaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overall_pass": self.overall_pass,
            "case_count": self.case_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "by_tier": self.by_tier,
            "by_category": self.by_category,
            "case_files": self.case_files,
            "constraints": {
                "control_plane_enabled": True,
                "mcp_global_execution_enabled": False,
                "mcp_server_mock_execution_enabled": False,
                "final_synthesis_enabled": False,
                "answer_guard_enabled": False,
                "candidate_spl_executed": False,
            },
            "results": [result.to_dict() for result in self.results],
        }


def _model_to_dict(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_model_to_dict(item) for item in value]
    if isinstance(value, tuple):
        return [_model_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _model_to_dict(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return _model_to_dict(value.model_dump())
    if hasattr(value, "dict"):
        return _model_to_dict(value.dict())
    return value


def _json_path_get(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
            continue
        return None
    return current


def _response_to_observed(response: Any) -> dict[str, Any]:
    payload = _model_to_dict(response)
    analyst = payload.get("analyst_response") or {}
    mitre_mappings = payload.get("mitre_mappings") or []
    spl_validation = payload.get("spl_validation") or {}
    execution = payload.get("execution") or {}
    query_to_intent = payload.get("query_to_intent") or {}
    intent = query_to_intent.get("intent_classification") or {}
    selected_use_case = payload.get("selected_use_case") or {}

    normalized_spl = spl_validation.get("normalized_spl")
    observed = {
        "message": payload.get("message"),
        "selected_skill": payload.get("selected_skill"),
        "selected_use_case_id": selected_use_case.get("use_case_id"),
        "answer_mode": (payload.get("evidence_plan") or {}).get("answer_mode"),
        "response_mode": payload.get("response_mode"),
        "synthesis_mode": payload.get("synthesis_mode"),
        "route_final": (payload.get("route_adjudication") or {}).get("final_route"),
        "route_authority_source": (payload.get("route_adjudication") or {}).get("authority_source"),
        "intent_family": intent.get("intent_family"),
        "intent_answer_goal": intent.get("answer_goal"),
        "candidate_spl_required": payload.get("candidate_spl") is not None,
        "spl_approved": spl_validation.get("approved"),
        "normalized_spl": normalized_spl,
        "execution_status": execution.get("status"),
        "execution_intent": execution.get("execution_intent"),
        "execution_block_reason": execution.get("block_reason"),
        "executed_spl": execution.get("executed_spl"),
        "mitre_visible": [item.get("technique_id") for item in mitre_mappings if isinstance(item, dict)],
        "mitre_answer_visible": (payload.get("mitre_decision") or {}).get("answer_visible"),
        "mitre_rejected": (payload.get("mitre_decision") or {}).get("rejected_techniques") or [],
        "analyst_mitre_visible": [
            item.get("Technique")
            for item in (analyst.get("mitre_mappings") or [])
            if isinstance(item, dict)
        ],
        "analyst_not_claimed": [
            item.get("Technique")
            for item in (analyst.get("not_claimed") or [])
            if isinstance(item, dict)
        ],
        "analyst_response_profile": analyst.get("response_profile"),
        "analyst_has_playbook": analyst.get("retrieved_playbook") is not None,
        "analyst_has_actions": bool(analyst.get("recommended_actions")),
        "analyst_spl_matches_normalized": bool(normalized_spl)
        and analyst.get("spl_code") == normalized_spl,
    }
    observed["raw"] = payload
    return observed


def _fail(
    failures: list[AssertionFailure],
    path: str,
    expected: Any,
    observed: Any,
    message: str,
) -> None:
    failures.append(
        AssertionFailure(
            path=path,
            expected=expected,
            observed=observed,
            message=message,
        )
    )


def _assert_equal(
    failures: list[AssertionFailure],
    observed: dict[str, Any],
    path: str,
    expected: Any,
) -> None:
    actual = _json_path_get(observed["raw"], path) if "." in path else observed.get(path)
    if actual != expected:
        _fail(failures, path, expected, actual, "value mismatch")


def _assert_contains_all(
    failures: list[AssertionFailure],
    *,
    path: str,
    text: str,
    required: Iterable[str],
) -> None:
    text_lower = text.lower()
    for phrase in required:
        if phrase.lower() not in text_lower:
            _fail(failures, path, f"contains {phrase!r}", text, "required phrase missing")


def _assert_contains_none(
    failures: list[AssertionFailure],
    *,
    path: str,
    text: str,
    forbidden: Iterable[str],
) -> None:
    text_lower = text.lower()
    for phrase in forbidden:
        if phrase.lower() in text_lower:
            _fail(failures, path, f"does not contain {phrase!r}", text, "forbidden phrase present")


def assert_case(case: GoldenCase, response: Any) -> CaseResult:
    observed = _response_to_observed(response)
    expected = case.expected
    failures: list[AssertionFailure] = []

    for field_name in (
        "selected_skill",
        "selected_use_case_id",
        "answer_mode",
        "response_mode",
        "route_final",
        "route_authority_source",
        "intent_family",
    ):
        value = getattr(expected, field_name)
        if value is not None and observed.get(field_name) != value:
            _fail(failures, field_name, value, observed.get(field_name), "value mismatch")

    if expected.intent_answer_goals:
        actual_goals = observed.get("intent_answer_goal") or []
        if isinstance(actual_goals, str):
            actual_goals = [actual_goals]
        for goal in expected.intent_answer_goals:
            if goal not in actual_goals:
                _fail(failures, "intent_answer_goal", goal, actual_goals, "required intent goal missing")

    if expected.candidate_spl is not None:
        spl_exp = expected.candidate_spl
        candidate = observed["raw"].get("candidate_spl")
        validation = observed["raw"].get("spl_validation")
        normalized_spl = observed.get("normalized_spl") or ""
        candidate_spl_text = ""
        if isinstance(candidate, dict):
            candidate_spl_text = str(candidate.get("candidate_spl") or "")
        spl_text = normalized_spl or candidate_spl_text
        if spl_exp.required is not None and bool(candidate) != spl_exp.required:
            _fail(failures, "candidate_spl", spl_exp.required, bool(candidate), "candidate presence mismatch")
        if spl_exp.approved is not None:
            actual_approved = validation.get("approved") if isinstance(validation, dict) else None
            if actual_approved != spl_exp.approved:
                _fail(failures, "spl_validation.approved", spl_exp.approved, actual_approved, "SPL approval mismatch")
        if spl_exp.normalized_required and not normalized_spl:
            _fail(failures, "spl_validation.normalized_spl", "present", normalized_spl, "normalized SPL missing")
        if spl_exp.generation_mode is not None:
            actual_mode = candidate.get("generation_mode") if isinstance(candidate, dict) else None
            if actual_mode != spl_exp.generation_mode:
                _fail(failures, "candidate_spl.generation_mode", spl_exp.generation_mode, actual_mode, "generation mode mismatch")
        _assert_contains_all(
            failures,
            path="spl_validation.normalized_spl",
            text=spl_text,
            required=spl_exp.must_include,
        )
        _assert_contains_none(
            failures,
            path="spl_validation.normalized_spl",
            text=spl_text,
            forbidden=spl_exp.must_not_include,
        )

    if expected.execution is not None:
        execution = observed["raw"].get("execution") or {}
        exp = expected.execution
        if exp.expected_status is not None and execution.get("status") != exp.expected_status:
            _fail(failures, "execution.status", exp.expected_status, execution.get("status"), "execution status mismatch")
        if exp.execution_intent is not None and execution.get("execution_intent") != exp.execution_intent:
            _fail(
                failures,
                "execution.execution_intent",
                exp.execution_intent,
                execution.get("execution_intent"),
                "execution intent mismatch",
            )
        if exp.block_reason is not None and execution.get("block_reason") != exp.block_reason:
            _fail(failures, "execution.block_reason", exp.block_reason, execution.get("block_reason"), "block reason mismatch")
        if exp.allowed is False and execution.get("status") == "executed":
            _fail(failures, "execution.status", "not executed", execution.get("status"), "execution was not allowed")
        if exp.executed_spl_absent and execution.get("executed_spl") is not None:
            _fail(failures, "execution.executed_spl", None, execution.get("executed_spl"), "candidate SPL was executed")

    if expected.human_review is not None:
        review = observed["raw"].get("human_review") or {}
        exp = expected.human_review
        if exp.required is not None and review.get("required") != exp.required:
            _fail(failures, "human_review.required", exp.required, review.get("required"), "human review mismatch")
        if exp.review_type is not None and review.get("review_type") != exp.review_type:
            _fail(failures, "human_review.review_type", exp.review_type, review.get("review_type"), "human review type mismatch")

    if expected.mitre is not None:
        exp = expected.mitre
        visible = set(item for item in observed.get("mitre_visible", []) if item)
        if exp.answer_visible is not None and observed.get("mitre_answer_visible") != exp.answer_visible:
            _fail(
                failures,
                "mitre_decision.answer_visible",
                exp.answer_visible,
                observed.get("mitre_answer_visible"),
                "MITRE answer visibility mismatch",
            )
        if exp.visible_exact and visible != set(exp.visible):
            _fail(failures, "mitre_mappings.technique_id", exp.visible, sorted(visible), "visible MITRE set mismatch")
        else:
            for technique in exp.visible:
                if technique not in visible:
                    _fail(failures, "mitre_mappings.technique_id", technique, sorted(visible), "visible technique missing")
        for technique in exp.not_visible:
            if technique in visible:
                _fail(failures, "mitre_mappings.technique_id", f"not {technique}", sorted(visible), "technique should not be visible")
        rejected = set(observed.get("mitre_rejected") or [])
        for technique in exp.rejected:
            if technique not in rejected:
                _fail(failures, "mitre_decision.rejected_techniques", technique, sorted(rejected), "rejected technique missing")
        if exp.analyst_visible_exact is not None:
            analyst_visible = set(item for item in observed.get("analyst_mitre_visible", []) if item)
            if analyst_visible != set(exp.analyst_visible_exact):
                _fail(
                    failures,
                    "analyst_response.mitre_mappings.Technique",
                    exp.analyst_visible_exact,
                    sorted(analyst_visible),
                    "analyst visible MITRE set mismatch",
                )
        analyst_not_claimed = set(item for item in observed.get("analyst_not_claimed", []) if item)
        for technique in exp.analyst_not_claimed:
            if technique not in analyst_not_claimed:
                _fail(
                    failures,
                    "analyst_response.not_claimed.Technique",
                    technique,
                    sorted(analyst_not_claimed),
                    "analyst not-claimed technique missing",
                )

    if expected.analyst_response is not None:
        exp = expected.analyst_response
        analyst = observed["raw"].get("analyst_response") or {}
        if exp.retrieved_playbook_present is not None and observed["analyst_has_playbook"] != exp.retrieved_playbook_present:
            _fail(
                failures,
                "analyst_response.retrieved_playbook",
                exp.retrieved_playbook_present,
                observed["analyst_has_playbook"],
                "playbook presence mismatch",
            )
        if exp.recommended_actions_present is not None and observed["analyst_has_actions"] != exp.recommended_actions_present:
            _fail(
                failures,
                "analyst_response.recommended_actions",
                exp.recommended_actions_present,
                observed["analyst_has_actions"],
                "recommended action presence mismatch",
            )
        if exp.response_profile is not None and analyst.get("response_profile") != exp.response_profile:
            _fail(
                failures,
                "analyst_response.response_profile",
                exp.response_profile,
                analyst.get("response_profile"),
                "response profile mismatch",
            )
        if exp.spl_code_matches_normalized is not None and observed["analyst_spl_matches_normalized"] != exp.spl_code_matches_normalized:
            _fail(
                failures,
                "analyst_response.spl_code",
                "matches normalized_spl",
                analyst.get("spl_code"),
                "analyst SPL does not match normalized SPL",
            )

    if expected.answer_text is not None:
        exp = expected.answer_text
        analyst = observed["raw"].get("analyst_response") or {}
        text = "\n".join(
            str(part or "")
            for part in (
                observed["raw"].get("message"),
                analyst.get("one_sentence_finding"),
                analyst.get("summary"),
                json.dumps(analyst, sort_keys=True),
            )
        )
        if exp.exact is not None and observed["raw"].get("message") != exp.exact:
            _fail(failures, "message", exp.exact, observed["raw"].get("message"), "message exact text mismatch")
        _assert_contains_all(failures, path="answer_text", text=text, required=exp.must_include)
        _assert_contains_none(failures, path="answer_text", text=text, forbidden=exp.must_not_include)

    for item in expected.json_path_equals:
        actual = _json_path_get(observed["raw"], item.path)
        if actual != item.value:
            _fail(failures, item.path, item.value, actual, "json path value mismatch")

    for item in expected.json_path_in_set:
        actual = _json_path_get(observed["raw"], item.path)
        if actual not in item.values:
            _fail(failures, item.path, item.values, actual, "json path value outside expected set")

    for path in expected.present:
        actual = _json_path_get(observed["raw"], path)
        if actual is None or actual == [] or actual == "":
            _fail(failures, path, "present", actual, "required value missing")

    for path in expected.absent:
        actual = _json_path_get(observed["raw"], path)
        if actual is not None:
            _fail(failures, path, None, actual, "value should be absent")

    compact_observed = {key: value for key, value in observed.items() if key != "raw"}
    return CaseResult(
        case_id=case.case_id,
        tier=case.tier,
        source=case.source,
        category=case.category,
        query=case.query,
        passed=not failures,
        failures=failures,
        observed=compact_observed,
    )


@contextmanager
def safe_runtime(case: GoldenCase | None = None):
    env_overrides = dict(SAFE_ENV_DEFAULTS)
    if case is not None:
        env_overrides.update(case.required_env)
    old_env = {key: os.environ.get(key) for key in env_overrides}
    old_settings = {
        key: getattr(settings, key)
        for key in SAFE_SETTING_DEFAULTS
        if hasattr(settings, key)
    }
    try:
        os.environ.update(env_overrides)
        for key, value in SAFE_SETTING_DEFAULTS.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        yield
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for key, value in old_settings.items():
            setattr(settings, key, value)


def run_case(case: GoldenCase) -> CaseResult:
    try:
        with safe_runtime(case):
            response = chat(ChatRequest(message=case.query))
    except Exception as exc:  # pragma: no cover - exact app exceptions vary by in-flight branch.
        return CaseResult(
            case_id=case.case_id,
            tier=case.tier,
            source=case.source,
            category=case.category,
            query=case.query,
            passed=False,
            failures=[
                AssertionFailure(
                    path="chat",
                    expected="chat response",
                    observed=f"{type(exc).__name__}: {exc}",
                    message="chat call raised exception",
                )
            ],
            observed={},
        )
    return assert_case(case, response)


def summarize(results: list[CaseResult], *, case_files: list[Path]) -> RunnerSummary:
    def bucket_counts(values: Iterable[str]) -> dict[str, dict[str, int]]:
        buckets: dict[str, dict[str, int]] = {}
        for key in values:
            buckets.setdefault(key, {"passed": 0, "failed": 0})
        return buckets

    by_tier = bucket_counts(str(result.tier) for result in results)
    by_category = bucket_counts(result.category for result in results)
    for result in results:
        status = "passed" if result.passed else "failed"
        by_tier[str(result.tier)][status] += 1
        by_category[result.category][status] += 1

    passed_count = sum(1 for result in results if result.passed)
    failed_count = len(results) - passed_count
    return RunnerSummary(
        generated_at=datetime.now(UTC).isoformat(),
        overall_pass=failed_count == 0,
        case_count=len(results),
        passed_count=passed_count,
        failed_count=failed_count,
        by_tier=by_tier,
        by_category=by_category,
        case_files=[str(path) for path in case_files],
        results=results,
    )


def render_markdown(summary: RunnerSummary) -> str:
    lines = [
        "# Golden Answer Evaluation",
        "",
        f"Generated: {summary.generated_at}",
        f"Overall: {'PASS' if summary.overall_pass else 'FAIL'}",
        f"Cases: {summary.case_count} ({summary.passed_count} passed, {summary.failed_count} failed)",
        "",
        "## By Tier",
        "",
        "| Tier | Passed | Failed |",
        "|---|---:|---:|",
    ]
    for tier, counts in sorted(summary.by_tier.items()):
        lines.append(f"| {tier} | {counts['passed']} | {counts['failed']} |")
    lines.extend(
        [
            "",
            "## By Category",
            "",
            "| Category | Passed | Failed |",
            "|---|---:|---:|",
        ]
    )
    for category, counts in sorted(summary.by_category.items()):
        lines.append(f"| {category} | {counts['passed']} | {counts['failed']} |")
    lines.extend(["", "## Cases", "", "| Case | Result | Category | Failures |", "|---|---|---|---|"])
    for result in summary.results:
        failure_summary = "<br>".join(f"{failure.path}: {failure.message}" for failure in result.failures)
        lines.append(
            f"| `{result.case_id}` | {'PASS' if result.passed else 'FAIL'} | "
            f"{result.category} | {failure_summary or ''} |"
        )
    lines.append("")
    return "\n".join(lines)


def discover_case_files(*, tier: int | None = None, all_cases: bool = False, case_dir: Path = DEFAULT_CASE_DIR) -> list[Path]:
    if all_cases:
        return sorted(case_dir.glob("*.jsonl"))
    if tier == 0:
        return [case_dir / "tier0_control_plane.jsonl"]
    if tier == 2:
        return sorted(
            [
                case_dir / "question_105_golden.jsonl",
                case_dir / "use_case_catalog_golden.jsonl",
            ]
        )
    if tier == 3:
        path = case_dir / "flagged_regressions.jsonl"
        return [path] if path.is_file() else []
    if tier is None:
        raise GoldenCaseError("Select --tier or --all")
    return sorted(case_dir.glob(f"tier{tier}_*.jsonl"))


def run_cases(cases: list[GoldenCase], *, case_files: list[Path]) -> RunnerSummary:
    results = [run_case(case) for case in cases]
    return summarize(results, case_files=case_files)


def write_reports(summary: RunnerSummary, *, json_path: Path = DEFAULT_REPORT_JSON, md_path: Path = DEFAULT_REPORT_MD) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic golden-answer regression cases.")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--tier", type=int, help="Run one golden-answer tier.")
    selector.add_argument("--all", action="store_true", help="Run every JSONL golden-answer case.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout.")
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--no-write", action="store_true", help="Do not write reports under docs/evals/out.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        case_files = discover_case_files(tier=args.tier, all_cases=args.all, case_dir=args.case_dir)
        missing = [path for path in case_files if not path.exists()]
        if missing:
            raise GoldenCaseError(f"missing case file(s): {', '.join(str(path) for path in missing)}")
        cases = load_jsonl_cases(case_files)
        if args.tier is not None:
            cases = [case for case in cases if case.tier == args.tier]
        summary = run_cases(cases, case_files=case_files)
        if not args.no_write:
            write_reports(summary, json_path=args.report_json, md_path=args.report_md)
        if args.json:
            print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
        else:
            print(render_markdown(summary))
        return 0 if summary.overall_pass else 1
    except GoldenCaseError as exc:
        print(f"golden-answer runner error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
