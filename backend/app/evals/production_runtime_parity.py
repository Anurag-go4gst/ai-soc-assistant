"""Production dual-runtime parity — imperative canonical vs Resource Planner graph.

Compares the two **real production entry points** for `/chat`:

* ``runtime_a = imperative_canonical``   — ``build_live_chat_response`` (`_run_live_chat_pipeline`)
* ``runtime_b = resource_planner_graph`` — ``run_chat_via_resource_planner_graph`` (`rp_node_bootstrap`)

This deliberately replaces the older ``langgraph_dual_parity`` comparison, which measured
``run_planner_led_shadow_graph`` — a runtime with no production caller (plan item 30). That
result is legacy observational evidence and does **not** measure item-32 production parity.

Item 31 classifications:

``exact_match``          all projected comparison fields equal
``approved_difference``  every differing field carries a complete six-part approval record
``critical_mismatch``    any unapproved difference in a governance or behavioural field

Governance/behavioural fields are never approval-eligible. The approval registry starts empty:
a difference is a ``critical_mismatch`` until someone writes the six-part record for it.

Self-contained by design — it must not import from ``planner_led_shadow_graph``, which item 30a
may delete.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from app.chat.session_store import clear_all_session_pins_for_tests
from app.evals.langgraph_dual_parity import dual_parity_profile, load_eval_rows
from app.schemas.requests import ChatRequest

RUNTIME_A = "imperative_canonical"
RUNTIME_B = "resource_planner_graph"

EXPECTED_CORPUS_COUNT = 120
EXPECTED_BASE_105 = 105

#: Fields compared exactly. Every one is analyst-visible or governance-bearing.
COMPARISON_FIELDS: tuple[str, ...] = (
    # routing / tier / lane
    "match_path",
    "mapped_question_ref",
    "selected_skill",
    "route_final",
    "use_case_id",
    # intent / completeness
    "intent_family",
    "requires_clarification",
    "path_type",
    "branches",
    # answer shape
    "answer_mode",
    "contract_answer_mode",
    "response_mode",
    "enabled_sections",
    "analyst_enabled_sections",
    # SPL / plan authority
    "candidate_spl_present",
    "spl_approved",
    "normalized_spl_present",
    "execution_eligible",
    "spl_template_status",
    "draft_spl_present",
    "draft_status",
    "resource_plan_present",
    "resource_plan_committed",
    # governance / safety
    "human_review_required",
    "human_review_reason",
    "hil_required",
    "unsafe_blocked",
    "action_mode",
    "execution_status",
    "execution_intent",
    "executed_spl_present",
    # MITRE
    "mitre_answer_visible",
    "mitre_technique_ids",
    "severity_label",
)

#: Documented runtime-specific metadata — excluded because the two runtimes cannot produce
#: equal values by construction. Each entry states why. Nothing behavioural may be added here.
EXCLUDED_FIELDS: dict[str, str] = {
    "trace_id": "per-run UUID",
    "turn_id": "per-run UUID",
    "duration_ms": "wall-clock timing",
    "node_trace": "node visit order is runtime topology, not behaviour",
    "rp_graph_trace": "RP-graph-only trace envelope; no imperative counterpart",
    "decision_log": "append-only audit trail; ordering is topology-dependent",
    "resource_plan_id": "random per-plan UUID; presence and committed flag are compared instead",
}

#: Six-part approval records, keyed by field name. Empty by design — see module docstring.
#: Required keys: field, runtime_a_value, runtime_b_value, reason, contract_owner, approval_ref.
APPROVED_DIFFERENCES: dict[str, dict[str, str]] = {}

_APPROVAL_KEYS = frozenset({"field", "runtime_a_value", "runtime_b_value", "reason", "contract_owner", "approval_ref"})


class RuntimeFallbackError(RuntimeError):
    """Runtime B degraded or delegated instead of running the RP graph."""


def approval_is_complete(record: dict[str, Any] | None) -> bool:
    """True only when all six parts are present and non-empty."""
    if not isinstance(record, dict):
        return False
    return all(str(record.get(key) or "").strip() for key in _APPROVAL_KEYS)


def _sections(container: Any) -> list[str]:
    render = container.get("render_sections") if isinstance(container, dict) else None
    if not isinstance(render, dict):
        return []
    return sorted(name for name, enabled in render.items() if enabled)


def project_response(response: Any) -> dict[str, Any]:
    """Behavioural projection of a chat response. No runtime-specific metadata."""
    payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)

    query_to_intent = payload.get("query_to_intent") or {}
    mappings = query_to_intent.get("candidate_mappings") or {}
    intent = query_to_intent.get("intent_classification") or {}
    planning = payload.get("planning_decision") or {}
    evidence_plan = payload.get("evidence_plan") or {}
    resource_plan = evidence_plan.get("resource_plan") or {}
    provenance = resource_plan.get("provenance") or {}
    answer_contract = payload.get("answer_contract") or {}
    analyst = payload.get("analyst_response") or {}
    draft = (analyst.get("spl_draft_preview") or {}) if isinstance(analyst, dict) else {}
    candidate_spl = payload.get("candidate_spl") or {}
    spl_validation = payload.get("spl_validation") or {}
    execution = payload.get("execution") or {}
    human_review = payload.get("human_review") or {}
    adjudication = payload.get("route_adjudication") or {}
    severity = payload.get("severity_decision") or {}
    mitre_decision = payload.get("mitre_decision") or {}

    return {
        "match_path": mappings.get("match_path"),
        "mapped_question_ref": mappings.get("question_ref"),
        "selected_skill": payload.get("selected_skill"),
        "route_final": adjudication.get("final_route"),
        "use_case_id": (payload.get("selected_use_case") or {}).get("use_case_id")
        if isinstance(payload.get("selected_use_case"), dict)
        else planning.get("use_case_id"),
        "intent_family": intent.get("intent_family"),
        "requires_clarification": intent.get("requires_clarification"),
        "path_type": planning.get("path_type"),
        "branches": sorted(planning.get("branches") or []),
        "answer_mode": evidence_plan.get("answer_mode"),
        "contract_answer_mode": answer_contract.get("answer_mode"),
        "response_mode": payload.get("response_mode"),
        "enabled_sections": _sections(answer_contract),
        "analyst_enabled_sections": _sections(analyst),
        "candidate_spl_present": bool(candidate_spl),
        "spl_approved": spl_validation.get("approved"),
        "normalized_spl_present": bool(spl_validation.get("normalized_spl")),
        "execution_eligible": candidate_spl.get("execution_eligible"),
        "spl_template_status": payload.get("spl_template_status"),
        "draft_spl_present": bool(draft.get("draft_spl")),
        "draft_status": draft.get("draft_status"),
        "resource_plan_present": bool(resource_plan),
        "resource_plan_committed": bool(provenance.get("committed")),
        "human_review_required": answer_contract.get("human_review_required"),
        "human_review_reason": human_review.get("reason"),
        "hil_required": bool((payload.get("action_capability") or {}).get("hil_required")),
        "unsafe_blocked": planning.get("path_type") == "unsafe_blocked",
        "action_mode": evidence_plan.get("action_mode"),
        "execution_status": execution.get("status"),
        "execution_intent": execution.get("execution_intent"),
        "executed_spl_present": bool(execution.get("executed_spl")),
        "mitre_answer_visible": answer_contract.get("mitre_answer_visible"),
        "mitre_technique_ids": sorted(answer_contract.get("mitre_technique_ids") or []),
        "severity_label": severity.get("severity_label") if isinstance(severity, dict) else None,
    }


@contextmanager
def _forbid_shadow_graph() -> Iterator[None]:
    """Fail loudly if Runtime B reaches the legacy shadow graph."""
    import app.graph.planner_led_shadow_graph as shadow

    original = shadow.run_planner_led_shadow_graph

    def _tripwire(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeFallbackError(
            "runtime_b delegated to planner_led_shadow_graph; production parity requires the RP graph"
        )

    shadow.run_planner_led_shadow_graph = _tripwire  # type: ignore[assignment]
    try:
        yield
    finally:
        shadow.run_planner_led_shadow_graph = original  # type: ignore[assignment]


def _assert_not_degraded(response: Any, row_id: str) -> None:
    """RP graph emits a degraded facade when the graph yields no response."""
    note = str(getattr(response, "note", "") or "")
    if "degraded facade only" in note or "did not produce a finalized answer" in note:
        raise RuntimeFallbackError(f"{row_id}: runtime_b returned the RP degraded placeholder ({note[:80]})")


def first_divergence(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    """First differing comparison field, in declared order."""
    for field in COMPARISON_FIELDS:
        if a.get(field) != b.get(field):
            return field
    return None


def classify_row(a: dict[str, Any], b: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Return (classification, differing-field records)."""
    diffs: list[dict[str, Any]] = []
    for field in COMPARISON_FIELDS:
        if a.get(field) == b.get(field):
            continue
        record = APPROVED_DIFFERENCES.get(field)
        diffs.append(
            {
                "field": field,
                "runtime_a": a.get(field),
                "runtime_b": b.get(field),
                "approved": approval_is_complete(record),
            }
        )
    if not diffs:
        return "exact_match", []
    if all(diff["approved"] for diff in diffs):
        return "approved_difference", diffs
    return "critical_mismatch", diffs


def _commit_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parents[3],
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — provenance is best-effort, absence is recorded
        return "unknown"


def run_production_parity(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run every corpus row through both production entry points."""
    from app.chat.pipeline import build_live_chat_response
    from app.graph.resource_planner_graph import run_chat_via_resource_planner_graph

    if rows is None:
        rows = load_eval_rows()

    base_105 = sum(1 for row in rows if row.get("source") == "105_map")
    started = time.perf_counter()
    results: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        row_id = str(row.get("row_id") or row.get("key") or f"row-{index}")
        query = str(row.get("query") or row.get("question") or "")
        # Both sides get a fresh uuid session and the store is cleared between rows.
        # Without this, session pins leaked across rows and produced phantom divergence
        # (`session_context_stale_or_missing` on runtime A only) that did not reproduce
        # when the same row ran in isolation. Same reasoning as sentinel_eval.capture_row.
        clear_all_session_pins_for_tests()
        with dual_parity_profile():
            response_a = build_live_chat_response(
                ChatRequest(message=query, session_id=f"parity-a-{uuid.uuid4()}")
            )
            clear_all_session_pins_for_tests()
            with _forbid_shadow_graph():
                response_b = run_chat_via_resource_planner_graph(
                    ChatRequest(message=query, session_id=f"parity-b-{uuid.uuid4()}")
                )
        _assert_not_degraded(response_b, row_id)

        projection_a = project_response(response_a)
        projection_b = project_response(response_b)
        classification, diffs = classify_row(projection_a, projection_b)
        results.append(
            {
                "row_id": row_id,
                "source": row.get("source"),
                "query": query,
                "classification": classification,
                "first_divergence": first_divergence(projection_a, projection_b),
                "differences": diffs,
                "runtime_a": projection_a,
                "runtime_b": projection_b,
            }
        )

    counts = {
        "exact_match": sum(1 for r in results if r["classification"] == "exact_match"),
        "approved_difference": sum(1 for r in results if r["classification"] == "approved_difference"),
        "critical_mismatch": sum(1 for r in results if r["classification"] == "critical_mismatch"),
    }
    return {
        "metadata": {
            "runtime_a": RUNTIME_A,
            "runtime_b": RUNTIME_B,
            "commit_sha": _commit_sha(),
            "corpus_count": len(rows),
            "base_105_loaded": base_105,
            "generated_at": datetime.now(UTC).isoformat(),
            "duration_s": round(time.perf_counter() - started, 1),
            "excluded_fields": dict(EXCLUDED_FIELDS),
            "comparison_field_count": len(COMPARISON_FIELDS),
        },
        "summary": counts,
        "rows": results,
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    """Corpus and metadata integrity — a partial run must never look green."""
    failures: list[str] = []
    meta = report.get("metadata") or {}
    if meta.get("runtime_a") != RUNTIME_A:
        failures.append(f"runtime_a={meta.get('runtime_a')!r} (expected {RUNTIME_A!r})")
    if meta.get("runtime_b") != RUNTIME_B:
        failures.append(f"runtime_b={meta.get('runtime_b')!r} (expected {RUNTIME_B!r})")
    if int(meta.get("corpus_count") or 0) != EXPECTED_CORPUS_COUNT:
        failures.append(f"corpus_count={meta.get('corpus_count')} (expected {EXPECTED_CORPUS_COUNT})")
    if int(meta.get("base_105_loaded") or 0) != EXPECTED_BASE_105:
        failures.append(f"base_105_loaded={meta.get('base_105_loaded')} (expected {EXPECTED_BASE_105})")
    critical = int((report.get("summary") or {}).get("critical_mismatch") or 0)
    if critical:
        failures.append(f"critical_mismatch={critical} (target 0)")
    return failures


def write_report(report: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "production_runtime_parity.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return path
