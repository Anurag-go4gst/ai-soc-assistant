"""Stage 3L-S6: 105-question shadow route governance eval (deterministic only)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.coverage.coverage_loader import coverage_for_id
from app.coverage.manifest_promotion_gates import evaluate_promotion_gates
from app.coverage.question_runtime_map import question_runtime_entry
from app.routing.deterministic_router import route_skill_deterministic
from app.routing.intent_to_operation_bridge import evaluate_intent_operation_bridge
from app.routing.route_plan_models import runtime_skill_values
from app.routing.skills import valid_skill

EvalBucket = Literal[
    "promoted",
    "likely_routable",
    "lookup",
    "detection",
    "multi_signal",
    "context",
    "unsupported",
]

LOOKUP_OPERATIONS = frozenset(
    {
        "lookup_correlation",
        "notable_risk_lookup",
        "entity_context_lookup",
    }
)
DETECTION_OPERATIONS = frozenset({"behavioral_detection_binding"})
MULTI_SIGNAL_OPERATIONS = frozenset({"multi_signal_correlation"})
CONTEXT_OPERATIONS = frozenset(
    {
        "metadata_discovery",
        "entity_context_lookup",
        "entity_timeline",
        "notable_risk_lookup",
    }
)
TEMPLATE_OPERATIONS = frozenset(
    {
        "aggregate_and_rank",
        "threshold_anomaly",
        "sequence_detection",
    }
)

PROVISIONAL_TO_BUCKET: dict[str, EvalBucket] = {
    "likely_routable": "likely_routable",
    "likely_needs_lookup": "lookup",
    "likely_needs_detection": "detection",
    "likely_multi_signal": "multi_signal",
    "likely_needs_context": "context",
    "likely_unsupported": "unsupported",
    "likely_needs_review": "likely_routable",
}


@dataclass
class QuestionEvalResult:
    question_ref: str
    bucket: EvalBucket
    pass_: bool
    failures: list[str] = field(default_factory=list)
    question_text: str = ""
    provisional_status: str = ""
    dependency_type: str = ""
    likely_runtime_operation: str | None = None
    legacy_selected_skill: str | None = None
    bridge_compatible: bool | None = None
    bridge_status: str | None = None
    skill_drift: bool = False
    route_blocked: bool = False
    promoted_to_manifest: bool = False
    promotion_gates_ok: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["pass"] = payload.pop("pass_")
        return payload


@dataclass
class EvalSummary:
    generated_at: str
    map_path: str
    question_count: int
    overall_pass: bool
    buckets: dict[str, dict[str, int]]
    results: list[QuestionEvalResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "map_path": self.map_path,
            "question_count": self.question_count,
            "overall_pass": self.overall_pass,
            "buckets": self.buckets,
            "results": [item.to_dict() for item in self.results],
            "constraints": {
                "live_mcp": False,
                "live_llm": False,
                "route_authority_enabled": False,
                "selected_skill_mutated": False,
            },
        }


def load_operation_map(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_eval_bucket(entry: dict[str, Any]) -> EvalBucket:
    if entry.get("promoted_to_manifest"):
        return "promoted"
    provisional = str(entry.get("provisional_status") or "")
    return PROVISIONAL_TO_BUCKET.get(provisional, "unsupported")


def evaluate_question(entry: dict[str, Any], *, coe_signoff: bool = True) -> QuestionEvalResult:
    ref = str(entry["question_ref"])
    bucket = classify_eval_bucket(entry)
    runtime = question_runtime_entry(ref) or {}
    question_text = str(entry.get("question_text") or runtime.get("question") or "")
    operation = entry.get("likely_runtime_operation")
    dependency_type = str(entry.get("dependency_type") or "")
    failures: list[str] = []

    deterministic = route_skill_deterministic(question_text)
    legacy_skill = str(deterministic.get("skill") or "")
    if not valid_skill(legacy_skill):
        failures.append("invalid_legacy_selected_skill")

    if operation is not None and operation not in runtime_skill_values():
        failures.append("invalid_likely_runtime_operation")

    bridge = evaluate_intent_operation_bridge(legacy_skill, operation if isinstance(operation, str) else None)
    skill_drift = bool(runtime.get("skill_drift"))
    route_blocked = bool(runtime.get("route_blocked"))

    if runtime is None:
        failures.append("missing_runtime_map_row")

    # Legacy selected_skill vs proposed operation may disagree by design (shadow-only).
    # Eval pass/fail is structural governance — not router↔operation alignment.

    if bucket == "promoted":
        cov_id = entry.get("candidate_coverage_id")
        if not cov_id:
            failures.append("promoted_missing_coverage_id")
        else:
            manifest_entry = coverage_for_id(str(cov_id))
            if manifest_entry is None:
                failures.append("promoted_coverage_not_in_manifest")
            else:
                gate = evaluate_promotion_gates(
                    manifest_entry,
                    mode="committed",
                    coe_signoff_recorded=coe_signoff,
                )
                if not gate.manifest_integrity_ok:
                    failures.append("promotion_gates_failed")
        promotion_gates_ok = "promotion_gates_failed" not in failures
    else:
        promotion_gates_ok = None
        if bucket == "likely_routable":
            if route_blocked:
                failures.append("unexpected_route_blocked")
            if dependency_type and dependency_type not in {"template", "unknown"}:
                failures.append("dependency_type_not_template")
            if operation and operation not in TEMPLATE_OPERATIONS:
                if operation in LOOKUP_OPERATIONS | DETECTION_OPERATIONS | MULTI_SIGNAL_OPERATIONS:
                    failures.append("operation_class_mismatch_template_bucket")

        elif bucket == "lookup":
            if dependency_type != "lookup":
                failures.append("dependency_type_mismatch")
            if operation and operation not in LOOKUP_OPERATIONS:
                failures.append("operation_not_lookup_class")

        elif bucket == "detection":
            if dependency_type != "detection":
                failures.append("dependency_type_mismatch")
            if operation and operation not in DETECTION_OPERATIONS:
                failures.append("operation_not_detection_class")

        elif bucket == "multi_signal":
            if dependency_type != "multi_signal":
                failures.append("dependency_type_mismatch")
            if operation and operation not in MULTI_SIGNAL_OPERATIONS:
                failures.append("operation_not_multi_signal_class")

        elif bucket == "context":
            if dependency_type != "context":
                failures.append("dependency_type_mismatch")
            if operation and operation not in CONTEXT_OPERATIONS:
                failures.append("operation_not_context_class")

        elif bucket == "unsupported":
            if not route_blocked and str(entry.get("provisional_status")) != "likely_unsupported":
                if dependency_type != "unsupported":
                    failures.append("expected_blocked_or_unsupported")

    bridge_status = None
    if bridge.rejection_reason:
        bridge_status = bridge.rejection_reason
    elif bridge.compatible:
        bridge_status = "compatible"
    else:
        bridge_status = "incompatible"

    return QuestionEvalResult(
        question_ref=ref,
        bucket=bucket,
        pass_=not failures,
        failures=failures,
        question_text=question_text,
        provisional_status=str(entry.get("provisional_status") or ""),
        dependency_type=dependency_type,
        likely_runtime_operation=operation if isinstance(operation, str) else None,
        legacy_selected_skill=legacy_skill,
        bridge_compatible=bridge.compatible,
        bridge_status=bridge_status,
        skill_drift=skill_drift,
        route_blocked=route_blocked,
        promoted_to_manifest=bool(entry.get("promoted_to_manifest")),
        promotion_gates_ok=promotion_gates_ok,
    )


def run_105_shadow_eval(
    map_path: Path,
    *,
    coe_signoff: bool = True,
) -> EvalSummary:
    payload = load_operation_map(map_path)
    entries = list(payload.get("entries", []))
    results = [evaluate_question(entry, coe_signoff=coe_signoff) for entry in entries]
    buckets: dict[str, dict[str, int]] = {}
    for result in results:
        bucket_stats = buckets.setdefault(
            result.bucket,
            {"total": 0, "pass": 0, "fail": 0},
        )
        bucket_stats["total"] += 1
        if result.pass_:
            bucket_stats["pass"] += 1
        else:
            bucket_stats["fail"] += 1

    overall_pass = all(item.pass_ for item in results)
    return EvalSummary(
        generated_at=datetime.now(UTC).isoformat(),
        map_path=str(map_path),
        question_count=len(entries),
        overall_pass=overall_pass,
        buckets=buckets,
        results=results,
    )


def render_markdown(summary: EvalSummary) -> str:
    lines = [
        "# Stage 3L 105-Question Shadow Route Eval",
        "",
        f"- **Generated:** {summary.generated_at}",
        f"- **Map:** `{summary.map_path}`",
        f"- **Questions:** {summary.question_count}",
        f"- **Overall:** {'PASS' if summary.overall_pass else 'FAIL'}",
        "",
        "## Constraints",
        "",
        "- No live MCP",
        "- No live LLM",
        "- Route authority not enabled",
        "- `selected_skill` not mutated (deterministic router observation only)",
        "",
        "## Bucket summary",
        "",
        "| Bucket | Total | Pass | Fail |",
        "|--------|------:|-----:|-----:|",
    ]
    for bucket in (
        "promoted",
        "likely_routable",
        "lookup",
        "detection",
        "multi_signal",
        "context",
        "unsupported",
    ):
        stats = summary.buckets.get(bucket, {"total": 0, "pass": 0, "fail": 0})
        lines.append(
            f"| {bucket} | {stats['total']} | {stats['pass']} | {stats['fail']} | ",
        )
    failures = [item for item in summary.results if not item.pass_]
    if failures:
        lines.extend(["", "## Failures (first 25)", ""])
        for item in failures[:25]:
            lines.append(
                f"- `{item.question_ref}` ({item.bucket}): {', '.join(item.failures)}",
            )
    lines.append("")
    return "\n".join(lines)


def write_eval_outputs(
    summary: EvalSummary,
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary.to_dict(), indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
