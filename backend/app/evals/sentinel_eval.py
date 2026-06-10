"""Sentinel happy-path eval — T-PRE.2 of plans/2026-06-10_0356 (rev 3).

Runs the frozen 17-row sentinel set (docs/evals/sentinel_set.json, built by
scripts/build_sentinel_set.py) through the real in-process chat pipeline and
compares contract-level fields against a frozen baseline fixture. This is the
fast per-commit happy-path gate; the full 105+50 evals run only at workstream
boundaries.

Capture rules: contract fields only (enums, labels, booleans, ids, sorted
section lists). Never prose, timestamps, or trace ids — smoke asserts
contracts, not values.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.api.routes_chat import chat
from app.config import settings
from app.evals.golden_answer_runner import _model_to_dict, safe_runtime
from app.schemas.requests import ChatRequest

REPO_ROOT = Path(__file__).resolve().parents[3]
SENTINEL_SET_PATH = REPO_ROOT / "docs" / "evals" / "sentinel_set.json"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
BASELINE_PATH = Path(__file__).resolve().parent / "fixtures" / "sentinel_baseline.json"

SCHEMA_VERSION = 1


def _parse_env_example(path: Path = ENV_EXAMPLE_PATH) -> dict[str, str]:
    """Parse KEY=VALUE lines from the committed .env.example posture file."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _coerce(current: Any, raw: str) -> Any:
    """Coerce a raw env string to the type of the current settings value."""
    if isinstance(current, bool):
        return raw.lower() in {"true", "1", "yes", "on"}
    if isinstance(current, int) and not isinstance(current, bool):
        try:
            return int(raw)
        except ValueError:
            return current
    if isinstance(current, float):
        try:
            return float(raw)
        except ValueError:
            return current
    return raw


@contextmanager
def sentinel_runtime() -> Iterator[None]:
    """Pin a fully deterministic posture for sentinel capture.

    The capture must be identical whether invoked via scripts/eval_sentinel.py
    (repo root, real .env loaded) or pytest (backend cwd, defaults). So we
    overlay the committed .env.example posture (canonical all-on SOC posture)
    onto settings, then apply the golden-runner no-live-deps pins on top
    (synthesis/guard/MCP-execution off) inside safe_runtime.
    """
    overlay: dict[str, Any] = {}
    for env_key, raw in _parse_env_example().items():
        attr = env_key.lower()
        if not hasattr(settings, attr):
            continue
        overlay[attr] = _coerce(getattr(settings, attr), raw)
    old_values = {attr: getattr(settings, attr) for attr in overlay}
    try:
        for attr, value in overlay.items():
            setattr(settings, attr, value)
        with safe_runtime():
            yield
    finally:
        for attr, value in old_values.items():
            setattr(settings, attr, value)


def load_sentinel_rows(path: Path = SENTINEL_SET_PATH) -> list[dict[str, Any]]:
    """Load all sentinel rows (105-registry and PowerGrid) with a unified key."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for row in payload["question_rows"]:
        rows.append({"key": row["question_ref"], **row})
    for row in payload["powergrid_rows"]:
        rows.append({"key": row["question_id"], **row})
    return rows


def capture_row(question: str) -> dict[str, Any]:
    """Run one question through the in-process chat pipeline; capture contract fields.

    Raises whatever the pipeline raises — callers decide how to record it.
    """
    with sentinel_runtime():
        response = chat(ChatRequest(message=question))
    payload = _model_to_dict(response)

    query_to_intent = payload.get("query_to_intent") or {}
    candidate_mappings = query_to_intent.get("candidate_mappings") or {}
    intent = query_to_intent.get("intent_classification") or {}
    evidence_plan = payload.get("evidence_plan") or {}
    route_adjudication = payload.get("route_adjudication") or {}
    severity_decision = payload.get("severity_decision") or {}
    execution = payload.get("execution") or {}
    spl_validation = payload.get("spl_validation") or {}
    candidate_spl = payload.get("candidate_spl") or {}
    answer_contract = payload.get("answer_contract") or {}
    render_sections = answer_contract.get("render_sections") or {}
    analyst_response = payload.get("analyst_response") or {}
    analyst_sections = analyst_response.get("render_sections") or {}
    draft_preview = analyst_response.get("spl_draft_preview") or {}

    return {
        "match_path": candidate_mappings.get("match_path"),
        "mapped_question_ref": candidate_mappings.get("question_ref"),
        "selected_skill": payload.get("selected_skill"),
        "intent_family": intent.get("intent_family"),
        "requires_clarification": intent.get("requires_clarification"),
        "answer_mode": evidence_plan.get("answer_mode"),
        "response_mode": payload.get("response_mode"),
        "route_final": route_adjudication.get("final_route"),
        "severity_label": (
            severity_decision.get("severity_label")
            if isinstance(severity_decision, dict)
            else None
        ),
        "execution_status": execution.get("status"),
        "candidate_spl_present": bool(candidate_spl),
        "execution_eligible": candidate_spl.get("execution_eligible"),
        "spl_approved": spl_validation.get("approved"),
        "spl_template_status": payload.get("spl_template_status"),
        "human_review_required": answer_contract.get("human_review_required"),
        "contract_answer_mode": answer_contract.get("answer_mode"),
        "enabled_sections": sorted(
            name for name, enabled in render_sections.items() if enabled
        ),
        # Analyst-facing card — the surface the user actually reads. This is
        # where the 105 lab-draft families render (draft_spl_preview), so the
        # happy-path gate must freeze it too.
        "analyst_enabled_sections": sorted(
            name for name, enabled in analyst_sections.items() if enabled
        ),
        "draft_spl_present": bool(draft_preview.get("draft_spl")),
        "draft_status": draft_preview.get("draft_status"),
        "mitre_answer_visible": answer_contract.get("mitre_answer_visible"),
        "mitre_technique_ids": sorted(answer_contract.get("mitre_technique_ids") or []),
    }


def run_sentinel(rows: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Capture every sentinel row. Pipeline exceptions become error records."""
    if rows is None:
        rows = load_sentinel_rows()
    captures: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            captures[row["key"]] = capture_row(row["question"])
        except Exception as exc:
            captures[row["key"]] = {"error": f"{type(exc).__name__}: {exc}"}
    return captures


def freeze_baseline(
    captures: dict[str, dict[str, Any]],
    path: Path = BASELINE_PATH,
) -> list[str]:
    """Write the baseline fixture. Refuses to freeze rows that errored."""
    errors = [key for key, row in captures.items() if "error" in row]
    if errors:
        return errors
    payload = {
        "schema_version": SCHEMA_VERSION,
        "note": (
            "Frozen sentinel happy-path baseline (plan rev 3 T-PRE.2). "
            "Regenerate only via scripts/eval_sentinel.py --freeze; re-freezing "
            "requires the diff review rule in the plan (additive sections only)."
        ),
        "rows": captures,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return []


def check_against_baseline(
    captures: dict[str, dict[str, Any]],
    path: Path = BASELINE_PATH,
) -> list[str]:
    """Compare captures with the frozen baseline; return human-readable diffs."""
    if not path.exists():
        return [f"baseline missing: {path} (run --freeze first)"]
    baseline = json.loads(path.read_text(encoding="utf-8"))["rows"]
    diffs: list[str] = []
    for key in sorted(set(baseline) | set(captures)):
        expected = baseline.get(key)
        actual = captures.get(key)
        if expected is None:
            diffs.append(f"{key}: not in baseline (sentinel set changed without re-freeze)")
            continue
        if actual is None:
            diffs.append(f"{key}: missing from run (sentinel set changed without re-freeze)")
            continue
        if "error" in actual:
            diffs.append(f"{key}: pipeline raised {actual['error']}")
            continue
        for field in sorted(set(expected) | set(actual)):
            if expected.get(field) != actual.get(field):
                diffs.append(
                    f"{key}.{field}: baseline={expected.get(field)!r} actual={actual.get(field)!r}"
                )
    return diffs
