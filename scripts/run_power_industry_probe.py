#!/usr/bin/env python3
"""Run Power Industry Probe Bank (10) through live in-process /chat pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.insert(0, _text)

from app.api.routes_chat import chat  # noqa: E402
from app.evals.golden_answer_runner import _model_to_dict  # noqa: E402
from app.evals.sentinel_eval import sentinel_runtime  # noqa: E402
from app.schemas.requests import ChatRequest  # noqa: E402
from app.chat.answer_shape_router import classify_answer_shape  # noqa: E402
from app.chat.signal_class_guidance import classify_signal_class  # noqa: E402
from scripts.power_industry_probe_quality import collect_violations  # noqa: E402

BANK_PATH = REPO_ROOT / "docs" / "evals" / "power_industry_probe_bank.json"
OUT_JSON = REPO_ROOT / "docs" / "evals" / "power_industry_probe_results.json"
OUT_MD = REPO_ROOT / "docs" / "evals" / "power_industry_probe_report.md"


def _first_lines(text: str, n: int = 6) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines[:n])


def _extract(payload: dict[str, Any]) -> dict[str, Any]:
    analyst = payload.get("analyst_response") or {}
    contract = payload.get("answer_contract") or {}
    routing = payload.get("routing") or {}
    spl = payload.get("candidate_spl") or {}
    validation = payload.get("spl_validation") or {}
    human = payload.get("human_review") or {}
    scorecard = payload.get("answer_scorecard") or {}
    trace = payload.get("control_plane_trace") or {}
    preview = payload.get("spl_draft_preview") or {}

    summary_parts: list[str] = []
    for key in ("summary", "headline", "analyst_summary", "message"):
        val = analyst.get(key) or payload.get(key)
        if isinstance(val, str) and val.strip():
            summary_parts.append(val.strip())
    if not summary_parts:
        msg = payload.get("message")
        if isinstance(msg, str):
            summary_parts.append(msg.strip())

    actions = (
        analyst.get("recommended_actions")
        or analyst.get("investigation_steps")
        or analyst.get("actions")
        or []
    )
    checklist = (
        analyst.get("analyst_checklist")
        or analyst.get("investigation_checklist")
        or analyst.get("checklist")
        or analyst.get("initial_assessment")
        or []
    )

    # Substance is judged on the analyst-visible message prose, not only the
    # envelope arrays — WS-0/WS-2/WS-7 enrich the message (direct_answer_summary)
    # which the old checklist_count/action_count heuristic could not see.
    full_message = "\n".join(summary_parts)
    message_markers = (
        "checklist",
        "hypotheses",
        "evidence to collect",
        "objective:",
        "asset-scoped",
        "review steps",
        "draft spl",
        "signal class:",
        "soc review checklist",
    )
    lowered_message = full_message.lower()
    message_substantive = len(full_message.strip()) >= 280 or any(
        marker in lowered_message for marker in message_markers
    )

    payload_spl = bool(
        spl.get("spl")
        or spl.get("query")
        or spl.get("candidate_spl")
        or preview.get("draft_spl")
        or validation.get("normalized_spl")
    )
    card_spl = bool(
        analyst.get("draft_spl_code")
        or analyst.get("spl_code")
        or analyst.get("spl_draft_preview")
        or contract.get("render_sections", {}).get("spl_artifact")
        or "draft spl" in lowered_message
        or "candidate spl" in lowered_message
    )
    return {
        "selected_skill": routing.get("skill") or payload.get("skill"),
        "answer_mode": contract.get("answer_mode") or payload.get("answer_mode"),
        "support_status": contract.get("support_status") or payload.get("support_status"),
        "has_candidate_spl": payload_spl,
        "payload_has_spl": payload_spl,
        "card_has_spl": card_spl,
        "spl_approved": validation.get("approved"),
        "execution_eligible": spl.get("execution_eligible") or validation.get("execution_eligible"),
        "human_review_required": bool(human),
        "human_review_kind": human.get("kind") or human.get("review_type"),
        "scorecard_verdict": scorecard.get("verdict"),
        "scorecard_issues": scorecard.get("issues") or [],
        "mitre_status": (analyst.get("mitre") or {}).get("status") if isinstance(analyst.get("mitre"), dict) else None,
        "guided_grounding": bool(trace.get("guided_hunt_grounding")),
        "summary_excerpt": _first_lines("\n\n".join(summary_parts), 8),
        "action_count": len(actions) if isinstance(actions, list) else 0,
        "checklist_count": len(checklist) if isinstance(checklist, list) else 0,
        "message_substantive": message_substantive,
        "message_len": len(full_message.strip()),
        "limitations": analyst.get("limitations") or [],
    }


def run_probe(bank_path: Path = BANK_PATH) -> dict[str, Any]:
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []

    with sentinel_runtime():
        for entry in bank["entries"]:
            question = entry["question"]
            try:
                response = chat(ChatRequest(message=question, session_id=f"pi-probe-{uuid.uuid4()}"))
                payload = _model_to_dict(response)
                observed = _extract(payload)
                entities = getattr(payload.get("query_understanding"), "entities", None)
                observed["answer_shape"] = classify_answer_shape(question).primary_shape
                observed["signal_class"] = classify_signal_class(
                    question,
                    entities.model_dump() if hasattr(entities, "model_dump") else None,
                )
                rows.append({**entry, "status": "ok", "observed": observed})
            except Exception as exc:
                rows.append({**entry, "status": "error", "error": str(exc)})

    quality_flags = {
        "thin_answer": 0,
        "no_spl_no_checklist": 0,
        "human_review_only": 0,
        "scorecard_fail": 0,
        "guided_path": 0,
    }
    for row in rows:
        if row.get("status") != "ok":
            continue
        obs = row["observed"]
        if obs.get("scorecard_verdict") == "fail":
            quality_flags["scorecard_fail"] += 1
        if obs.get("selected_skill") == "guided_investigation":
            quality_flags["guided_path"] += 1
        if obs.get("human_review_required") and not obs.get("has_candidate_spl") and obs.get("checklist_count", 0) < 2:
            quality_flags["human_review_only"] += 1
        envelope_thin = (
            not obs.get("has_candidate_spl")
            and obs.get("checklist_count", 0) < 2
            and obs.get("action_count", 0) < 2
        )
        if envelope_thin and not obs.get("message_substantive"):
            quality_flags["thin_answer"] += 1
        if envelope_thin:
            quality_flags["no_spl_no_checklist"] += 1

    result = {"bank": bank["name"], "total": len(rows), "quality_flags": quality_flags, "rows": rows}
    result["quality_violations"] = collect_violations(result)
    return result


def write_markdown(result: dict[str, Any], path: Path) -> None:
    lines = ["# Power Industry Probe Report", "", f"Bank: **{result['bank']}** | Questions: **{result['total']}**", "", "## Quality flags (heuristic)", ""]
    for key, val in result["quality_flags"].items():
        lines.append(f"- `{key}`: {val}")
    lines.extend(["", "## Per-question results", ""])
    for row in result["rows"]:
        lines.append(f"### {row['question_id']} — {row.get('topic', '')}")
        lines.append(f"**Tier:** {row.get('tier', 'n/a')} | **Stress:** {row.get('stress_axis', 'n/a')}")
        lines.append(f"\n> {row['question']}\n")
        if row.get("status") == "error":
            lines.append(f"**ERROR:** {row.get('error')}\n")
            continue
        obs = row["observed"]
        lines.append(f"- Skill: `{obs.get('selected_skill')}` | Mode: `{obs.get('answer_mode')}` | Support: `{obs.get('support_status')}`")
        lines.append(f"- SPL: {obs.get('has_candidate_spl')} (approved={obs.get('spl_approved')}) | Checklist: {obs.get('checklist_count')} | Actions: {obs.get('action_count')}")
        lines.append(f"- Human review: {obs.get('human_review_required')} ({obs.get('human_review_kind')}) | Scorecard: `{obs.get('scorecard_verdict')}`")
        if obs.get("scorecard_issues"):
            lines.append(f"- Scorecard issues: {obs['scorecard_issues']}")
        lines.append("\n**Summary excerpt:**\n")
        lines.append(obs.get("summary_excerpt") or "(empty)")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Exit non-zero on answer-shape, boilerplate, or SPL-card regressions")
    args = parser.parse_args(argv)
    result = run_probe()
    if not args.check:
        OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
        write_markdown(result, OUT_MD)
    summary = {"total": result["total"], "quality_flags": result["quality_flags"], "quality_violations": result["quality_violations"]}
    print(json.dumps(summary, indent=2))
    if args.check and result["quality_violations"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
