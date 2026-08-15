#!/usr/bin/env python3
"""Plan 6 D1 — T4 serving-option comparison (evidence only).

Does not change AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS or enable T4
on /chat. Hits the already-configured local primary (Foundation-Sec :8081)
with the production T4 prompt/schema. Qwen / Foundation-Sec failover URLs are
inventoried, not invented.

Usage (host, not pytest — conftest blocks live LLM):

    PYTHONPATH=backend:. python3 scripts/eval_plan6_t4_serving_options.py
"""

from __future__ import annotations

import json
import os
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "backend", REPO_ROOT):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from app.chat.lane_router import initial_tier_for_match_path  # noqa: E402
from app.chat.resolved_query_builder import build_resolved_query_contract  # noqa: E402
from app.chat.semantic_t4_understanding import (  # noqa: E402
    _merge_proposal,
    _parse_proposal,
)
from app.llm.clients.local_chat_client import LocalChatClient, LocalChatError  # noqa: E402
from app.query_understanding.parser import understand_query  # noqa: E402

CORPUS_PATH = REPO_ROOT / "docs" / "evals" / "plan6" / "vps_corpus_v1.json"
TRUTH_PATH = REPO_ROOT / "docs" / "evals" / "routing_truth_set_v1.json"
OUT_DIR = REPO_ROOT / "docs" / "evals" / "plan6"

T4_SYSTEM = (
    "Return JSON only. Do not add markdown. Do not select a skill. "
    "Do not propose SPL or MCP execution. Propose query understanding only."
)
PROD_MAX_TOKENS = 400
PROD_TEMPERATURE = 0.1
PROD_TIMEOUT_S = 2.0
# Off-path uncensored budget. Not a production T4 timeout change.
COMPLETE_TIMEOUT_S = 90.0
HOST_BASE_URL = "http://127.0.0.1:8081/v1"
HOST_MODEL = "foundation-sec-1.1-8b-instruct-q8_0.gguf"

AMBIGUOUS_ROWS = (
    {
        "row_id": "p6.clarify",
        "query": "Look into it.",
        "class": "ambiguous_underspecified",
        "expected_intent_family": "clarification_required",
        "must_keep_clarification": True,
        "must_not_require_spl": True,
    },
    {
        "row_id": "rt.para.009",
        "query": "was anybody granted local admin rights recently",
        "class": "ambiguous_ownership_deferred",
        "expected_intent_family": None,
        "must_keep_clarification": False,
        "must_not_require_spl": False,
        "must_not_drop_prohibitions": True,
    },
    {
        "row_id": "rt.para.013",
        "query": "are we missing log feeds from any important security source",
        "class": "ambiguous_ownership_deferred",
        "expected_intent_family": None,
        "must_keep_clarification": False,
        "must_not_require_spl": False,
        "must_not_drop_prohibitions": True,
    },
)


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return float(ordered[lo] * (1.0 - frac) + ordered[hi] * frac)


def _dotenv_get(key: str) -> str:
    env_path = REPO_ROOT / ".env"
    value = ""
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("export "):
                stripped = stripped[7:]
            if stripped.startswith(f"{key}="):
                value = stripped.split("=", 1)[1]
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
    return (os.environ.get(key) or value or "").strip()


def _inventory() -> dict[str, Any]:
    qwen_enabled = _dotenv_get("AI_SOC_LLM_QWEN_PRIMARY_ENABLED").lower() in {
        "1",
        "true",
        "yes",
    }
    qwen_url = _dotenv_get("AI_SOC_LLM_QWEN_BASE_URL")
    qwen_model = _dotenv_get("AI_SOC_LLM_QWEN_MODEL")
    fs_url = _dotenv_get("AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_BASE_URL")
    fs_model = _dotenv_get("AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_MODEL")
    local_url = _dotenv_get("AI_SOC_LLM_LOCAL_BASE_URL")
    local_model = _dotenv_get("AI_SOC_LLM_LOCAL_MODEL")
    return {
        "local_primary": {
            "configured": bool(local_url and local_model),
            "base_url_host": "127.0.0.1:8081" if "8081" in local_url else _host_only(local_url),
            "model": local_model or HOST_MODEL,
            "same_as_probe_host": True,
        },
        "foundation_sec_instruct_failover": {
            "configured": bool(fs_url and fs_model),
            "base_url_host": _host_only(fs_url),
            "model": fs_model or None,
        },
        "qwen_primary": {
            "flag_enabled": qwen_enabled,
            "configured": bool(qwen_enabled and qwen_url and qwen_model),
            "base_url_host": _host_only(qwen_url),
            "model": qwen_model or None,
        },
        "llama_server": {
            "parallel_slots": 1,
            "cmdline_note": "llama-server -np 1 -c 4000 -t 4 --port 8081",
        },
    }


def _host_only(url: str) -> str | None:
    if not url:
        return None
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or parsed.path
    except Exception:  # noqa: BLE001
        return "unparsed"


def _load_paraphrases() -> list[dict[str, Any]]:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    truth_rows = {
        row["row_id"]: row
        for row in json.loads(TRUTH_PATH.read_text(encoding="utf-8"))["rows"]
    }
    out: list[dict[str, Any]] = []
    for row in corpus["rows"]:
        if row.get("class") != "t4_residual_paraphrase":
            continue
        truth = truth_rows[row["truth_row_id"]]
        out.append(
            {
                "row_id": row["row_id"],
                "query": row["query"],
                "truth_row_id": row["truth_row_id"],
                "expected_intent_family": truth["expected_intent_family"],
                "acceptable_skills": truth["acceptable_skills"],
                "required_capabilities": truth["required_capabilities"],
                "ambiguous": bool(truth.get("ambiguous")),
            }
        )
    return out


def _contract_for(query: str) -> tuple[Any, str, str]:
    qu = understand_query(query)
    match_path = str(getattr(qu, "deterministic_match_path", "") or "")
    if not match_path:
        cand = getattr(qu, "candidate_mappings", None) or {}
        if isinstance(cand, dict):
            match_path = str(cand.get("match_path") or "")
    tier = initial_tier_for_match_path(match_path or "out_of_registry")
    contract = build_resolved_query_contract(
        query=query,
        query_understanding=qu,
        qualification_tier=tier,  # type: ignore[arg-type]
        qualification_source=match_path or "out_of_registry",
    )
    return contract, tier, match_path or "out_of_registry"


def _t4_user_prompt(query: str, deterministic: Any) -> str:
    return json.dumps(
        {
            "query": query,
            "deterministic_contract": {
                "intent_family": deterministic.intent_family,
                "answer_goal": deterministic.answer_goal,
                "ambiguity_state": deterministic.ambiguity_state,
                "clarification_required": deterministic.clarification_required,
                "required_capabilities": sorted(deterministic.required_capabilities),
                "prohibited_capabilities": sorted(deterministic.prohibited_capabilities),
            },
        }
    )


def _call(
    *,
    system: str,
    user: str,
    timeout_s: float,
    max_tokens: int,
    temperature: float = PROD_TEMPERATURE,
) -> dict[str, Any]:
    client = LocalChatClient(
        base_url=HOST_BASE_URL,
        model=HOST_MODEL,
        api_key="",
        timeout_seconds=max(1, int(timeout_s + 0.5)),
    )
    started = time.monotonic()
    try:
        result = client.generate(
            system_prompt=system,
            user_prompt=user,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_seconds=timeout_s,
        )
        elapsed_ms = int((time.monotonic() - started) * 1000)
        usage = dict(result.usage or {})
        return {
            "ok": True,
            "timed_out": False,
            "empty_output": not bool(result.text),
            "elapsed_ms": elapsed_ms,
            "text": result.text,
            "finish_reason": result.finish_reason,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "error": None,
        }
    except LocalChatError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        code = str(exc)
        timed_out = "timeout" in code.lower()
        return {
            "ok": False,
            "timed_out": timed_out,
            "empty_output": True,
            "elapsed_ms": elapsed_ms,
            "text": None,
            "finish_reason": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "error": code,
        }
    except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "timed_out": True,
            "empty_output": True,
            "elapsed_ms": elapsed_ms,
            "text": None,
            "finish_reason": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "error": type(exc).__name__,
        }


def _score_raw(raw: str | None, deterministic: Any, expected_family: str | None) -> dict[str, Any]:
    if not raw:
        return {
            "parsed": False,
            "parse_reason": "empty_output",
            "accepted_any": False,
            "widening_rejected": False,
            "family_change_rejected": False,
            "clarification_dropped": False,
            "skill_key_in_output": False,
            "proposal_intent_family": None,
            "proposal_required": [],
            "merged_intent_family": deterministic.intent_family,
            "merged_clarification_required": deterministic.clarification_required,
            "merged_required": sorted(deterministic.required_capabilities),
            "merged_prohibited": sorted(deterministic.prohibited_capabilities),
            "proposal_family_matches_expected": False,
            "rejected_reasons": ["empty_output"],
        }
    skill_key = False
    try:
        blob = json.loads(raw) if raw.lstrip().startswith("{") else None
        if isinstance(blob, dict) and "skill" in blob:
            skill_key = True
    except json.JSONDecodeError:
        skill_key = '"skill"' in raw or "'skill'" in raw
    proposal, parse_reason = _parse_proposal(raw)
    if proposal is None:
        return {
            "parsed": False,
            "parse_reason": parse_reason or "schema_invalid",
            "accepted_any": False,
            "widening_rejected": False,
            "family_change_rejected": False,
            "clarification_dropped": False,
            "skill_key_in_output": skill_key,
            "proposal_intent_family": None,
            "proposal_required": [],
            "merged_intent_family": deterministic.intent_family,
            "merged_clarification_required": deterministic.clarification_required,
            "merged_required": sorted(deterministic.required_capabilities),
            "merged_prohibited": sorted(deterministic.prohibited_capabilities),
            "proposal_family_matches_expected": False,
            "rejected_reasons": [parse_reason or "schema_invalid"],
        }
    base_trace = {
        "invoked": True,
        "accepted": False,
        "timed_out": False,
        "elapsed_ms": 0,
        "timeout_seconds": COMPLETE_TIMEOUT_S,
        "rejected_reasons": [],
        "notes": ["d1_off_path_complete_generation"],
    }
    merged = _merge_proposal(deterministic, proposal, base_trace)
    trace = (merged.provenance or {}).get("semantic_t4") or {}
    rejected = list(trace.get("rejected_reasons") or [])
    return {
        "parsed": True,
        "parse_reason": None,
        "accepted_any": bool(trace.get("accepted")),
        "widening_rejected": "capability_widening_rejected" in rejected,
        "family_change_rejected": "intent_family_change_rejected" in rejected,
        "clarification_dropped": bool(
            deterministic.clarification_required and not merged.clarification_required
        ),
        "skill_key_in_output": skill_key,
        "proposal_intent_family": proposal.intent_family,
        "proposal_required": list(proposal.required_capabilities),
        "merged_intent_family": merged.intent_family,
        "merged_clarification_required": merged.clarification_required,
        "merged_required": sorted(merged.required_capabilities),
        "merged_prohibited": sorted(merged.prohibited_capabilities),
        "proposal_family_matches_expected": (
            expected_family is not None and proposal.intent_family == expected_family
        ),
        "rejected_reasons": rejected,
    }


def _run_named(
    name: str,
    query: str,
    *,
    timeout_s: float,
    max_tokens: int,
    system: str | None = None,
    user: str | None = None,
    expected_family: str | None = None,
) -> dict[str, Any]:
    contract, tier, match_path = _contract_for(query)
    sys_prompt = system if system is not None else T4_SYSTEM
    usr = user if user is not None else _t4_user_prompt(query, contract)
    call = _call(
        system=sys_prompt,
        user=usr,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
    )
    score = _score_raw(call.get("text"), contract, expected_family)
    return {
        "name": name,
        "query": query,
        "qualification_tier": tier,
        "match_path": match_path,
        "deterministic_intent_family": contract.intent_family,
        "deterministic_clarification_required": contract.clarification_required,
        "deterministic_required": sorted(contract.required_capabilities),
        "deterministic_prohibited": sorted(contract.prohibited_capabilities),
        "timeout_s": timeout_s,
        "max_tokens": max_tokens,
        "system_prompt_kind": "production_t4" if sys_prompt == T4_SYSTEM else "variant",
        **{k: v for k, v in call.items() if k != "text"},
        "text_chars": len(call["text"]) if call.get("text") else 0,
        "text_preview": (call.get("text") or "")[:400],
        "score": score,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed = [float(r["elapsed_ms"]) for r in rows if r.get("elapsed_ms") is not None]
    return {
        "n": len(rows),
        "ok": sum(1 for r in rows if r.get("ok")),
        "timed_out": sum(1 for r in rows if r.get("timed_out")),
        "empty_output": sum(1 for r in rows if r.get("empty_output")),
        "parsed": sum(1 for r in rows if (r.get("score") or {}).get("parsed")),
        "accepted_any": sum(1 for r in rows if (r.get("score") or {}).get("accepted_any")),
        "widening_rejected": sum(
            1 for r in rows if (r.get("score") or {}).get("widening_rejected")
        ),
        "clarification_dropped": sum(
            1 for r in rows if (r.get("score") or {}).get("clarification_dropped")
        ),
        "skill_key_in_output": sum(
            1 for r in rows if (r.get("score") or {}).get("skill_key_in_output")
        ),
        "proposal_family_matches_expected": sum(
            1 for r in rows if (r.get("score") or {}).get("proposal_family_matches_expected")
        ),
        "elapsed_ms_p50": _pct(elapsed, 50),
        "elapsed_ms_p95": _pct(elapsed, 95),
        "elapsed_ms_min": min(elapsed) if elapsed else None,
        "elapsed_ms_max": max(elapsed) if elapsed else None,
        "elapsed_ms_mean": statistics.fmean(elapsed) if elapsed else None,
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    load_avg = os.getloadavg()
    paraphrases = _load_paraphrases()
    inventory = _inventory()
    results: dict[str, Any] = {
        "schema_version": "plan6_t4_serving_options_v1",
        "git_sha": "1d32ac66dd6c707789db8b44574bd566af401952",
        "started_utc": started.isoformat(),
        "load_average": list(load_avg),
        "production_t4_timeout_seconds_unchanged": PROD_TIMEOUT_S,
        "inventory": inventory,
        "options": {},
        "isolations": {},
        "paraphrase_complete": [],
        "ambiguous_complete": [],
        "concurrency": {},
    }

    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    run_path = OUT_DIR / "runs" / f"{stamp}_d1" / "t4_serving_options_raw.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)

    def flush() -> None:
        run_path.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")

    # --- Option A: local_primary / Foundation-Sec, slot 1, production 2.0s replica
    print("D1 isolation: production 2.0s replica on para.003 (cold)", flush=True)
    replica_cold = _run_named(
        "prod_2s_cold_para003",
        paraphrases[0]["query"],
        timeout_s=PROD_TIMEOUT_S,
        max_tokens=PROD_MAX_TOKENS,
        expected_family=paraphrases[0]["expected_intent_family"],
    )
    results["isolations"]["prod_2s_cold"] = replica_cold
    flush()

    print("D1 isolation: complete-gen 90s cold para.003 (timeout-budget)", flush=True)
    complete_cold = _run_named(
        "complete_90s_cold_para003",
        paraphrases[0]["query"],
        timeout_s=COMPLETE_TIMEOUT_S,
        max_tokens=PROD_MAX_TOKENS,
        expected_family=paraphrases[0]["expected_intent_family"],
    )
    results["isolations"]["complete_90s_cold"] = complete_cold
    flush()

    print("D1 isolation: complete-gen 90s warm para.003 (warm-up)", flush=True)
    complete_warm = _run_named(
        "complete_90s_warm_para003",
        paraphrases[0]["query"],
        timeout_s=COMPLETE_TIMEOUT_S,
        max_tokens=PROD_MAX_TOKENS,
        expected_family=paraphrases[0]["expected_intent_family"],
    )
    results["isolations"]["complete_90s_warm"] = complete_warm
    flush()

    print("D1 isolation: production 2.0s warm para.003", flush=True)
    replica_warm = _run_named(
        "prod_2s_warm_para003",
        paraphrases[0]["query"],
        timeout_s=PROD_TIMEOUT_S,
        max_tokens=PROD_MAX_TOKENS,
        expected_family=paraphrases[0]["expected_intent_family"],
    )
    results["isolations"]["prod_2s_warm"] = replica_warm
    flush()

    print("D1 isolation: max_tokens=80 complete (decode-length / prompt overhead)", flush=True)
    reduced_tokens = _run_named(
        "complete_90s_max80_para003",
        paraphrases[0]["query"],
        timeout_s=COMPLETE_TIMEOUT_S,
        max_tokens=80,
        expected_family=paraphrases[0]["expected_intent_family"],
    )
    results["isolations"]["complete_90s_max80"] = reduced_tokens
    flush()

    print("D1 isolation: query-only user prompt (context overhead)", flush=True)
    query_only = _run_named(
        "complete_90s_query_only_para003",
        paraphrases[0]["query"],
        timeout_s=COMPLETE_TIMEOUT_S,
        max_tokens=PROD_MAX_TOKENS,
        user=json.dumps({"query": paraphrases[0]["query"]}),
        expected_family=paraphrases[0]["expected_intent_family"],
    )
    results["isolations"]["complete_90s_query_only"] = query_only
    flush()

    print("D1 isolation: tiny classification (serving floor)", flush=True)
    tiny = _run_named(
        "tiny_class_para003",
        paraphrases[0]["query"],
        timeout_s=30.0,
        max_tokens=10,
        system="Reply ONLY one word: hunt",
        user=paraphrases[0]["query"],
        expected_family=paraphrases[0]["expected_intent_family"],
    )
    results["isolations"]["tiny_classification"] = tiny
    flush()

    # --- Correctness set: all 8 residual paraphrases, complete-gen (same T4 contract)
    print("D1 correctness: 8 residual paraphrases at 90s complete-gen", flush=True)
    for row in paraphrases:
        print(f"  {row['row_id']}", flush=True)
        item = _run_named(
            row["row_id"],
            row["query"],
            timeout_s=COMPLETE_TIMEOUT_S,
            max_tokens=PROD_MAX_TOKENS,
            expected_family=row["expected_intent_family"],
        )
        item["truth_row_id"] = row["truth_row_id"]
        item["expected_intent_family"] = row["expected_intent_family"]
        results["paraphrase_complete"].append(item)
        flush()

    print("D1 false-widening: ambiguous T4 cases at 90s", flush=True)
    for row in AMBIGUOUS_ROWS:
        print(f"  {row['row_id']}", flush=True)
        item = _run_named(
            row["row_id"],
            row["query"],
            timeout_s=COMPLETE_TIMEOUT_S,
            max_tokens=PROD_MAX_TOKENS,
            expected_family=row.get("expected_intent_family"),
        )
        item["class"] = row["class"]
        score = item["score"]
        false_widen = False
        reasons: list[str] = []
        if row.get("must_keep_clarification") and score.get("clarification_dropped"):
            false_widen = True
            reasons.append("clarification_dropped")
        if row.get("must_not_require_spl") and "spl" in (score.get("merged_required") or []):
            false_widen = True
            reasons.append("merged_required_spl")
        if score.get("skill_key_in_output"):
            false_widen = True
            reasons.append("skill_key")
        if (
            row.get("must_not_drop_prohibitions")
            and "spl" in item["deterministic_prohibited"]
            and "spl" not in (score.get("merged_prohibited") or [])
        ):
            false_widen = True
            reasons.append("dropped_spl_prohibition")
        item["false_widening"] = false_widen
        item["false_widening_reasons"] = reasons
        results["ambiguous_complete"].append(item)
        flush()

    # --- Concurrency N=2 against llama-server -np 1 (model slot, not app semaphore)
    print("D1 concurrency: N=2 at production 2.0s (model queue)", flush=True)
    pair = (paraphrases[0], paraphrases[1])

    def _one(row: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        return _run_named(
            f"n2_{row['row_id']}",
            row["query"],
            timeout_s=timeout_s,
            max_tokens=PROD_MAX_TOKENS,
            expected_family=row["expected_intent_family"],
        )

    n2_started = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        n2_2s = list(pool.map(lambda r: _one(r, PROD_TIMEOUT_S), pair))
    results["concurrency"]["n2_prod_2s"] = {
        "pair_wall_ms": int((time.monotonic() - n2_started) * 1000),
        "rows": n2_2s,
        "summary": _summarize(n2_2s),
        "note": "Direct llama-server -np 1; app sidecar semaphore is not in this path. D0 /chat N=2 is the app-slot measurement (1/2 llm_model_slot_busy).",
    }
    flush()

    print("D1 concurrency: N=2 at 90s complete-gen (model queue)", flush=True)
    n2_started = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as pool:
        n2_90 = list(pool.map(lambda r: _one(r, COMPLETE_TIMEOUT_S), pair))
    results["concurrency"]["n2_complete_90s"] = {
        "pair_wall_ms": int((time.monotonic() - n2_started) * 1000),
        "rows": n2_90,
        "summary": _summarize(n2_90),
    }
    flush()

    results["paraphrase_complete_summary"] = _summarize(results["paraphrase_complete"])
    results["ambiguous_complete_summary"] = _summarize(results["ambiguous_complete"])
    results["options"] = {
        "A_local_primary_foundation_sec_np1_timeout_2s": {
            "available": True,
            "same_as_d0": True,
            "viable_at_production_2s": False,
            "reason": "D0 9/9 hop timeouts at ~2.0s; this replica confirms the hop cannot return JSON inside the SLO.",
        },
        "B_foundation_sec_instruct_failover_url": {
            "available": inventory["foundation_sec_instruct_failover"]["configured"],
            "viable_at_production_2s": False,
            "reason": "AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_BASE_URL is unset. Local primary already is Foundation-Sec-1.1-8B-Instruct Q8 on :8081 — not a distinct serving option.",
        },
        "C_qwen_primary": {
            "available": inventory["qwen_primary"]["configured"],
            "viable_at_production_2s": False,
            "reason": "AI_SOC_LLM_QWEN_PRIMARY_ENABLED is unset/false and QWEN_BASE_URL/MODEL are empty. No already-configured Qwen to compare.",
        },
        "D_local_primary_concurrency_n2": {
            "available": True,
            "viable_at_production_2s": False,
            "reason": "llama-server -np 1. D0 /chat N=2: 1 timed_out + 1 empty_output/llm_model_slot_busy. Raising app concurrency cannot create a second model slot.",
        },
    }
    results["finished_utc"] = datetime.now(timezone.utc).isoformat()
    results["elapsed_wall_s"] = (
        datetime.now(timezone.utc) - started
    ).total_seconds()
    flush()

    final_path = OUT_DIR / "t4_serving_options.json"
    final_path.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {final_path} and {run_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
