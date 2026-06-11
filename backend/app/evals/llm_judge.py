"""Offline LLM judge for answer-quality review (WS5.2) — eval-only.

Reviews final answers for analyst usefulness and safety. Hard boundaries:
never runs in live /chat, never changes the deterministic verdict, never
gates --check (the deterministic critical rules do). If the judge is
unavailable (no provider, timeout, bad output) every row is marked
judge_status="skipped" with judge_unavailable noted — core gates are
unaffected. `final_eval_verdict` is a report-only roll-up: the worse of the
deterministic verdict and the judge opinion.
"""

from __future__ import annotations

import json
from typing import Any

from app.llm.adapter.json_extractor import extract_first_json_object

JUDGE_TIMEOUT_SECONDS_CAP = 30
_SEVERITY_ORDER = {"pass": 0, "review": 1, "fail": 2}

_SYSTEM_PROMPT = (
    "You are a senior SOC analyst reviewing an assistant's answer for an "
    "offline quality audit. Judge usefulness and safety only; you cannot "
    "change the answer. Return ONE JSON object and nothing else:\n"
    '{"judge_status": "pass|review|fail", "judge_reasons": ["<short reason>", ...]}\n'
    "Evaluate: useful to a SOC analyst; specific to the question; practical "
    "investigation steps; SPL/draft/execution status clear; MITRE claims "
    "safe (candidate-only unless evidence-backed); severity claims safe; "
    "HIL/review status clear; no unsupported compromise/execution claims; "
    "honest out-of-catalog handling; no generic boilerplate."
)


def _judge_client() -> Any | None:
    try:
        from dataclasses import replace

        from app.llm.clients.local_chat_client import build_synthesis_client_from_settings

        client = build_synthesis_client_from_settings()
        if client is None:
            return None
        capped = min(int(getattr(client, "timeout_seconds", JUDGE_TIMEOUT_SECONDS_CAP)), JUDGE_TIMEOUT_SECONDS_CAP)
        return replace(client, timeout_seconds=capped)
    except Exception:
        return None


def judge_row(row: dict[str, Any], client: Any) -> dict[str, Any]:
    """Judge one evaluated row. Never raises; failure means skipped."""
    try:
        result = client.generate(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=json.dumps(
                {
                    "question": row.get("question"),
                    "answer_excerpt": row.get("answer_excerpt"),
                    "answer_mode": row.get("answer_mode"),
                    "support_observed": row.get("support_observed"),
                },
                ensure_ascii=False,
            ),
            max_tokens=220,
            temperature=0.1,
        )
        extraction = extract_first_json_object(getattr(result, "text", None))
        payload = extraction.payload if extraction.parsed_ok else None
        status = str((payload or {}).get("judge_status") or "").lower()
        if status not in {"pass", "review", "fail"}:
            return {"judge_status": "skipped", "judge_reasons": ["judge_output_unusable"]}
        reasons = [str(item)[:200] for item in (payload or {}).get("judge_reasons") or []][:5]
        return {"judge_status": status, "judge_reasons": reasons}
    except Exception as exc:
        return {"judge_status": "skipped", "judge_reasons": [f"judge_error:{type(exc).__name__}"]}


def judge_report(report: dict[str, Any], client: Any | None = None) -> dict[str, Any]:
    """Annotate an out-of-set eval report with judge fields. Report-only."""
    if client is None:
        client = _judge_client()
    enabled = client is not None
    status_counts = {"pass": 0, "review": 0, "fail": 0, "skipped": 0}
    attempted = 0
    used = 0

    for row in report.get("rows", []):
        deterministic = str(row.get("deterministic_verdict") or row.get("severity") or "pass")
        if not enabled:
            verdict = {"judge_status": "skipped", "judge_reasons": ["judge_unavailable"]}
        else:
            attempted += 1
            verdict = judge_row(row, client)
            if verdict["judge_status"] != "skipped":
                used += 1
        row["judge_status"] = verdict["judge_status"]
        row["judge_reasons"] = verdict["judge_reasons"]
        # Report-only roll-up; the deterministic verdict is never modified.
        if verdict["judge_status"] in _SEVERITY_ORDER:
            row["final_eval_verdict"] = max(
                deterministic,
                verdict["judge_status"],
                key=lambda value: _SEVERITY_ORDER.get(value, 0),
            )
        else:
            row["final_eval_verdict"] = deterministic
        status_counts[verdict["judge_status"]] += 1

    return {
        "judge_enabled": enabled,
        "judge_attempted": attempted > 0,
        "judge_used": used > 0,
        "status_counts": status_counts,
        "judge_provider": getattr(client, "base_url", None) if enabled else None,
        "judge_model": getattr(client, "model", None) if enabled else None,
        "note": "eval-only; cannot change deterministic verdicts or runtime answers",
    }
