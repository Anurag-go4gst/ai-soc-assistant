"""Schema helpers for deterministic golden-answer regression cases."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

GoldenCategory = Literal[
    "answer",
    "spl_candidate",
    "rag_policy",
    "mitre_mapping",
    "clarification",
    "unsupported",
    "source_unavailable",
]

GoldenSource = Literal[
    "control_plane_critical_flow",
    "question_runtime_map",
    "use_case_catalog",
    "flagged_regression",
]


class GoldenCaseError(ValueError):
    """Raised when a golden case row does not match the supported schema."""


@dataclass(frozen=True)
class JsonPathEquals:
    path: str
    value: Any


@dataclass(frozen=True)
class JsonPathInSet:
    path: str
    values: list[Any]


@dataclass(frozen=True)
class CandidateSplExpectation:
    required: bool | None = None
    approved: bool | None = None
    normalized_required: bool | None = None
    generation_mode: str | None = None
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionExpectation:
    allowed: bool | None = None
    expected_status: str | None = None
    execution_intent: str | None = None
    block_reason: str | None = None
    executed_spl_absent: bool = True


@dataclass(frozen=True)
class HumanReviewExpectation:
    required: bool | None = None
    review_type: str | None = None


@dataclass(frozen=True)
class MitreExpectation:
    answer_visible: bool | None = None
    visible: list[str] = field(default_factory=list)
    visible_exact: bool = False
    not_visible: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    analyst_visible_exact: list[str] | None = None
    analyst_not_claimed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalystResponseExpectation:
    retrieved_playbook_present: bool | None = None
    recommended_actions_present: bool | None = None
    response_profile: str | None = None
    spl_code_matches_normalized: bool | None = None


@dataclass(frozen=True)
class AnswerTextExpectation:
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    exact: str | None = None


@dataclass(frozen=True)
class GoldenExpected:
    selected_skill: str | None = None
    selected_use_case_id: str | None = None
    answer_mode: str | None = None
    response_mode: str | None = None
    route_final: str | None = None
    route_authority_source: str | None = None
    intent_family: str | None = None
    intent_answer_goals: list[str] = field(default_factory=list)
    candidate_spl: CandidateSplExpectation | None = None
    execution: ExecutionExpectation | None = None
    human_review: HumanReviewExpectation | None = None
    mitre: MitreExpectation | None = None
    analyst_response: AnalystResponseExpectation | None = None
    answer_text: AnswerTextExpectation | None = None
    json_path_equals: list[JsonPathEquals] = field(default_factory=list)
    json_path_in_set: list[JsonPathInSet] = field(default_factory=list)
    present: list[str] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    tier: int
    source: GoldenSource
    query: str
    category: GoldenCategory
    expected: GoldenExpected
    tags: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    required_env: dict[str, str] = field(default_factory=dict)
    notes: str | None = None


def _require_dict(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GoldenCaseError(f"{field_name} must be an object")
    return value


def _string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GoldenCaseError(f"{field_name} must be a list of strings")
    return value


def _parse_candidate_spl(raw: Any) -> CandidateSplExpectation | None:
    if raw is None:
        return None
    data = _require_dict(raw, field_name="expected.candidate_spl")
    return CandidateSplExpectation(
        required=data.get("required"),
        approved=data.get("approved"),
        normalized_required=data.get("normalized_required"),
        generation_mode=data.get("generation_mode"),
        must_include=_string_list(data.get("must_include"), field_name="expected.candidate_spl.must_include"),
        must_not_include=_string_list(data.get("must_not_include"), field_name="expected.candidate_spl.must_not_include"),
    )


def _parse_execution(raw: Any) -> ExecutionExpectation | None:
    if raw is None:
        return None
    data = _require_dict(raw, field_name="expected.execution")
    return ExecutionExpectation(
        allowed=data.get("allowed"),
        expected_status=data.get("expected_status"),
        execution_intent=data.get("execution_intent"),
        block_reason=data.get("block_reason"),
        executed_spl_absent=bool(data.get("executed_spl_absent", True)),
    )


def _parse_human_review(raw: Any) -> HumanReviewExpectation | None:
    if raw is None:
        return None
    data = _require_dict(raw, field_name="expected.human_review")
    return HumanReviewExpectation(required=data.get("required"), review_type=data.get("review_type"))


def _parse_mitre(raw: Any) -> MitreExpectation | None:
    if raw is None:
        return None
    data = _require_dict(raw, field_name="expected.mitre")
    analyst_exact = data.get("analyst_visible_exact")
    return MitreExpectation(
        answer_visible=data.get("answer_visible"),
        visible=_string_list(data.get("visible"), field_name="expected.mitre.visible"),
        visible_exact=bool(data.get("visible_exact", False)),
        not_visible=_string_list(data.get("not_visible"), field_name="expected.mitre.not_visible"),
        rejected=_string_list(data.get("rejected"), field_name="expected.mitre.rejected"),
        analyst_visible_exact=(
            _string_list(analyst_exact, field_name="expected.mitre.analyst_visible_exact")
            if analyst_exact is not None
            else None
        ),
        analyst_not_claimed=_string_list(
            data.get("analyst_not_claimed"),
            field_name="expected.mitre.analyst_not_claimed",
        ),
    )


def _parse_analyst_response(raw: Any) -> AnalystResponseExpectation | None:
    if raw is None:
        return None
    data = _require_dict(raw, field_name="expected.analyst_response")
    return AnalystResponseExpectation(
        retrieved_playbook_present=data.get("retrieved_playbook_present"),
        recommended_actions_present=data.get("recommended_actions_present"),
        response_profile=data.get("response_profile"),
        spl_code_matches_normalized=data.get("spl_code_matches_normalized"),
    )


def _parse_answer_text(raw: Any) -> AnswerTextExpectation | None:
    if raw is None:
        return None
    data = _require_dict(raw, field_name="expected.answer_text")
    return AnswerTextExpectation(
        must_include=_string_list(data.get("must_include"), field_name="expected.answer_text.must_include"),
        must_not_include=_string_list(
            data.get("must_not_include"),
            field_name="expected.answer_text.must_not_include",
        ),
        exact=data.get("exact"),
    )


def _parse_json_path_equals(raw: Any) -> list[JsonPathEquals]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise GoldenCaseError("expected.json_path_equals must be a list")
    parsed: list[JsonPathEquals] = []
    for index, item in enumerate(raw):
        data = _require_dict(item, field_name=f"expected.json_path_equals[{index}]")
        path = data.get("path")
        if not isinstance(path, str) or not path:
            raise GoldenCaseError(f"expected.json_path_equals[{index}].path must be a non-empty string")
        parsed.append(JsonPathEquals(path=path, value=data.get("value")))
    return parsed


def _parse_json_path_in_set(raw: Any) -> list[JsonPathInSet]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise GoldenCaseError("expected.json_path_in_set must be a list")
    parsed: list[JsonPathInSet] = []
    for index, item in enumerate(raw):
        data = _require_dict(item, field_name=f"expected.json_path_in_set[{index}]")
        path = data.get("path")
        values = data.get("values")
        if not isinstance(path, str) or not path:
            raise GoldenCaseError(f"expected.json_path_in_set[{index}].path must be a non-empty string")
        if not isinstance(values, list):
            raise GoldenCaseError(f"expected.json_path_in_set[{index}].values must be a list")
        parsed.append(JsonPathInSet(path=path, values=values))
    return parsed


def parse_golden_case(data: dict[str, Any], *, source_path: str = "<memory>", line_number: int = 0) -> GoldenCase:
    try:
        case_id = data["case_id"]
        tier = data["tier"]
        source = data["source"]
        query = data["query"]
        category = data["category"]
    except KeyError as exc:
        raise GoldenCaseError(f"{source_path}:{line_number}: missing required field {exc.args[0]}") from exc

    if not isinstance(case_id, str) or not case_id:
        raise GoldenCaseError(f"{source_path}:{line_number}: case_id must be a non-empty string")
    if not isinstance(tier, int) or tier < 0:
        raise GoldenCaseError(f"{source_path}:{line_number}: tier must be a non-negative integer")
    if source not in {"control_plane_critical_flow", "question_runtime_map", "use_case_catalog", "flagged_regression"}:
        raise GoldenCaseError(f"{source_path}:{line_number}: unsupported source {source!r}")
    if category not in {
        "answer",
        "spl_candidate",
        "rag_policy",
        "mitre_mapping",
        "clarification",
        "unsupported",
        "source_unavailable",
    }:
        raise GoldenCaseError(f"{source_path}:{line_number}: unsupported category {category!r}")
    if not isinstance(query, str) or not query:
        raise GoldenCaseError(f"{source_path}:{line_number}: query must be a non-empty string")

    expected_data = _require_dict(data.get("expected"), field_name="expected")
    expected = GoldenExpected(
        selected_skill=expected_data.get("selected_skill"),
        selected_use_case_id=expected_data.get("selected_use_case_id"),
        answer_mode=expected_data.get("answer_mode"),
        response_mode=expected_data.get("response_mode"),
        route_final=expected_data.get("route_final"),
        route_authority_source=expected_data.get("route_authority_source"),
        intent_family=expected_data.get("intent_family"),
        intent_answer_goals=_string_list(expected_data.get("intent_answer_goals"), field_name="expected.intent_answer_goals"),
        candidate_spl=_parse_candidate_spl(expected_data.get("candidate_spl")),
        execution=_parse_execution(expected_data.get("execution")),
        human_review=_parse_human_review(expected_data.get("human_review")),
        mitre=_parse_mitre(expected_data.get("mitre")),
        analyst_response=_parse_analyst_response(expected_data.get("analyst_response")),
        answer_text=_parse_answer_text(expected_data.get("answer_text")),
        json_path_equals=_parse_json_path_equals(expected_data.get("json_path_equals")),
        json_path_in_set=_parse_json_path_in_set(expected_data.get("json_path_in_set")),
        present=_string_list(expected_data.get("present"), field_name="expected.present"),
        absent=_string_list(expected_data.get("absent"), field_name="expected.absent"),
    )
    required_env = data.get("required_env") or {}
    if not isinstance(required_env, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in required_env.items()
    ):
        raise GoldenCaseError(f"{source_path}:{line_number}: required_env must be an object of strings")

    return GoldenCase(
        case_id=case_id,
        tier=tier,
        source=source,
        query=query,
        category=category,
        expected=expected,
        tags=_string_list(data.get("tags"), field_name="tags"),
        source_refs=_string_list(data.get("source_refs"), field_name="source_refs"),
        required_env=required_env,
        notes=data.get("notes"),
    )


def load_jsonl_cases(paths: list[Path]) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    seen: set[str] = set()
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                try:
                    raw = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise GoldenCaseError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
                case = parse_golden_case(raw, source_path=str(path), line_number=line_number)
                if case.case_id in seen:
                    raise GoldenCaseError(f"{path}:{line_number}: duplicate case_id {case.case_id!r}")
                seen.add(case.case_id)
                cases.append(case)
    return cases

