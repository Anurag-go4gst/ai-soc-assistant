"""P8-C — governed production /chat journey quality. Live LLM, no live MCP."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = ROOT / "docs/evals/p8_c/journey_bank_v1.json"
REPORT_DIR = ROOT / "docs/evals/p8_c"

EXECUTED_CLAIM_RE = re.compile(
    r"\b(blocked|isolated|disabled|deleted|contained|ticket created|remediation executed)\b",
    re.I,
)
EC_LEAK_RE = re.compile(r"\b(experience center|scenario simulation|demo mode|simulated execution)\b", re.I)


def _bootstrap() -> None:
    sys.path.insert(0, str(ROOT / "backend"))
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    from eval_p8_l3_live import apply_compose_like_env

    apply_compose_like_env()


def _text_blob(payload: dict[str, Any]) -> str:
    parts = [
        str(payload.get("analyst_summary") or ""),
        str(payload.get("message") or ""),
        json.dumps(payload.get("investigation_outcome") or {}, default=str),
        json.dumps(payload.get("human_review") or {}, default=str),
        json.dumps(payload.get("remediation_approval") or {}, default=str),
        json.dumps(payload.get("proposed_actions") or {}, default=str),
    ]
    return "\n".join(parts)


def _execution_status(payload: dict[str, Any]) -> str:
    execution = payload.get("execution") or {}
    return str(execution.get("status") or "")


def _score_turn(journey: dict[str, Any], payload: dict[str, Any], turn_idx: int) -> dict[str, Any]:
    expect = journey.get("expect") or {}
    blob = _text_blob(payload)
    execution = _execution_status(payload)
    outcome = payload.get("investigation_outcome") or {}
    plan = payload.get("validated_investigation_plan")
    approval = payload.get("investigation_approval") or {}
    review = payload.get("human_review")
    remediation = payload.get("remediation_approval") or {}
    candidate = payload.get("candidate_spl") or {}
    summary = str(payload.get("analyst_summary") or "")
    skill = str(payload.get("selected_skill") or "")
    evidence_overclaims = []
    execution_overclaims = []
    if execution == "executed" or candidate.get("execution_eligible") is True:
        execution_overclaims.append("executed_or_eligible")
    if EXECUTED_CLAIM_RE.search(blob) and execution != "executed":
        execution_overclaims.append("prose_claims_completed_action")
    if EC_LEAK_RE.search(blob):
        evidence_overclaims.append("ec_leakage")

    dimensions: dict[str, str] = {}
    dimensions["REQUEST_UNDERSTANDING"] = "PASS" if summary.strip() or review else "FAIL"
    if expect.get("clarification_required"):
        clarified = bool(
            payload.get("clarification_required")
            or (isinstance(review, dict) and review)
            or "clarif" in summary.lower()
            or skill in {"", "knowledge_recall"}
        )
        dimensions["REQUEST_UNDERSTANDING"] = "PASS" if clarified else "FAIL"
        dimensions["PLAN_QUALITY"] = "PASS"
        dimensions["EVIDENCE_REQUIREMENT_QUALITY"] = "PASS"
    elif expect.get("investigation_shaped"):
        dimensions["PLAN_QUALITY"] = "PASS" if (plan or payload.get("investigation_planning_trace") or payload.get("workflow_plan")) else "FAIL"
        needs = False
        if isinstance(plan, dict) and (plan.get("evidence_needed") or plan.get("hypotheses")):
            needs = True
        if payload.get("evidence_plan"):
            needs = True
        dimensions["EVIDENCE_REQUIREMENT_QUALITY"] = "PASS" if needs or plan or review else "PARTIAL"
    else:
        dimensions["PLAN_QUALITY"] = "PASS"
        dimensions["EVIDENCE_REQUIREMENT_QUALITY"] = "PASS"

    dimensions["TOOL/SOURCE_SELECTION_QUALITY"] = "PASS"
    dimensions["BOUNDEDNESS"] = "FAIL" if payload.get("live_mcp_called") else "PASS"
    obtained = False
    if isinstance(outcome, dict) and outcome.get("evidence_refs"):
        obtained = True
    dimensions["EVIDENCE_TRUTH"] = "FAIL" if evidence_overclaims else "PASS"
    if obtained is False and "benign" in blob.lower() and "confirmed benign" in blob.lower():
        dimensions["EVIDENCE_TRUTH"] = "FAIL"
        evidence_overclaims.append("empty_as_benign")

    dimensions["ANALYSIS_QUALITY"] = "PASS" if (len(summary.strip()) >= 40 or review) else "PARTIAL"
    dimensions["CONCLUSION_QUALITY"] = "PASS" if (outcome or summary or review) else "FAIL"
    limitation = False
    if isinstance(outcome, dict) and str(outcome.get("investigation_status") or "") in {"incomplete", "inconclusive", "limited"}:
        limitation = True
    if any(tok in blob.lower() for tok in ("limited", "insufficient", "not executed", "review-only", "cannot confirm")):
        limitation = True
    dimensions["LIMITATION_TRANSPARENCY"] = "PASS" if (limitation or expect.get("clarification_required") or expect.get("knowledge")) else "PARTIAL"
    planning = payload.get("planning_outcome") if isinstance(payload.get("planning_outcome"), dict) else {}
    review_reason = review.get("reason") if isinstance(review, dict) else None
    next_action = payload.get("recommended_next_action") or planning.get("next_action") or review_reason
    dimensions["NEXT_STEP_QUALITY"] = "PASS" if (next_action or review or approval or expect.get("knowledge")) else "PARTIAL"

    rec_ok = True
    if expect.get("remediation_justified") is False and expect.get("may_recommend_remediation") is not True:
        if isinstance(remediation, dict) and remediation.get("status") in {"offered", "approved"}:
            if expect.get("knowledge"):
                rec_ok = False
    if expect.get("must_not_claim_executed") and execution_overclaims:
        rec_ok = False
    dimensions["REMEDIATION_APPROPRIATENESS"] = "PASS" if rec_ok and not execution_overclaims else "FAIL"
    hil_ok = True
    if approval and str(approval.get("status") or "") not in {"", "none"}:
        # Plan approval exists; execution must remain a separate object.
        if execution == "executed":
            hil_ok = False
    dimensions["HIL_POSTURE"] = "PASS" if hil_ok else "FAIL"
    dimensions["FOLLOWUP_CONTINUITY"] = "N/A"
    if expect.get("followup") and turn_idx == 1:
        stale = expect.get("stale_host")
        corrected = expect.get("corrected_host")
        restated = bool(stale) and stale in summary and (not corrected or corrected not in summary)
        dimensions["FOLLOWUP_CONTINUITY"] = "FAIL" if restated else "PASS"
    readable = "```json" not in summary and not summary.strip().startswith("{")
    dimensions["ANSWER_READABILITY"] = "PASS" if readable else "FAIL"

    major = []
    if execution_overclaims:
        major.append("execution_overclaim")
    if evidence_overclaims:
        major.append("evidence_overclaim")
    if dimensions.get("REQUEST_UNDERSTANDING") == "FAIL":
        major.append("understanding")
    return {
        "dimensions": dimensions,
        "execution_status": execution,
        "selected_skill": skill,
        "has_plan": bool(plan),
        "has_human_review": bool(review),
        "has_investigation_approval": bool(approval),
        "has_remediation_approval": bool(remediation),
        "live_mcp_called": bool(payload.get("live_mcp_called")),
        "execution_overclaims": execution_overclaims,
        "evidence_overclaims": evidence_overclaims,
        "major_defects": major,
        "summary_prefix": summary[:240],
    }


def main() -> int:
    _bootstrap()
    from app.chat.pipeline import build_live_chat_response
    from app.llm.policy.eval_arm import prompt_eval_arm
    from app.schemas.requests import ChatRequest

    assert prompt_eval_arm() == "active"
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    for journey in bank["journeys"]:
        session_id = None
        turns_out = []
        print(f"P8-C {journey['journey_id']} {journey['title']}", flush=True)
        for idx, turn in enumerate(journey["turns"]):
            payload = build_live_chat_response(
                ChatRequest(message=turn["message"], session_id=session_id)
            ).model_dump(mode="json")
            status = payload.get("session_context_status") or {}
            if isinstance(status, dict) and status.get("session_id"):
                session_id = status["session_id"]
            scored = _score_turn(journey, payload, idx)
            turns_out.append({"message": turn["message"], **scored})
        last = turns_out[-1]
        failed_dims = [k for k, v in last["dimensions"].items() if v == "FAIL"]
        results.append(
            {
                "journey_id": journey["journey_id"],
                "title": journey["title"],
                "ec_reference": journey.get("ec_reference"),
                "turns": turns_out,
                "failed_dimensions": failed_dims,
                "major_defects": last["major_defects"],
                "result": "FAIL" if last["major_defects"] or failed_dims else "PASS",
            }
        )

    passed = [row for row in results if row["result"] == "PASS"]
    failed = [row for row in results if row["result"] == "FAIL"]
    exec_over = sum(len(row["turns"][-1]["execution_overclaims"]) for row in results)
    evid_over = sum(len(row["turns"][-1]["evidence_overclaims"]) for row in results)
    scorecard = {
        "phase": "P8-C",
        "prompt_arm": "active",
        "live_mcp_used": False,
        "journey_bank_count": len(results),
        "journeys_executed": len(results),
        "journeys_passed": len(passed),
        "journeys_failed": len(failed),
        "execution_overclaims": exec_over,
        "evidence_overclaims": evid_over,
        "results": results,
        "remediation_positive_case": next(row["result"] for row in results if row["journey_id"] == "J6"),
        "remediation_negative_case": next(row["result"] for row in results if row["journey_id"] == "J7"),
        "followup_continuity": next(row["result"] for row in results if row["journey_id"] == "J8"),
        "major_journey_defects": [row["journey_id"] for row in results if row["major_defects"]],
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "journey_scorecard.json"
    path.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(path), "passed": len(passed), "failed": len(failed), "execution_overclaims": exec_over}, indent=2))
    return 0 if exec_over == 0 and evid_over == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
