#!/usr/bin/env python3
"""T4 COE qualification pack — reuse production T4, do not parallel-implement it.

F3 disposition (this pack does not close F3):
  T4 semantic capability = proven (Plans 6–8).
  Current VPS serving = not production viable.
  F3 closure requires COE serving qualification.

Modes:
  --emit-prompts  Exact production prompts/inputs. Does not call the model.
  --live          Run the configured existing T4 provider (COE later).

Never changes model, provider, or timeout. Never restarts Cisco.
GET /v1/models HTTP 200 is liveness, not inference health.
T4 cannot grant route, capability, or tool authority.

Usage (host, not pytest — conftest blocks live LLM):

    PYTHONPATH=backend:. python3 scripts/eval_t4_coe_qualification.py --emit-prompts \\
        --out docs/evals/t4_coe_qualification.json

    PYTHONPATH=backend:. python3 scripts/eval_t4_coe_qualification.py --live \\
        --chat-smoke --out docs/evals/t4_coe_qualification_live.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for _path in (ROOT / "backend", ROOT):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from app.chat.contracts.resolved_query import ResolvedQueryContract  # noqa: E402
from app.chat.intent_classifier import build_query_to_intent  # noqa: E402
from app.chat.resolved_query_builder import (  # noqa: E402
    attach_understanding_authority,
    build_resolved_query_contract,
)
from app.chat.semantic_t4_understanding import (  # noqa: E402
    _SEMANTIC_T4_SYSTEM_PROMPT,
    _build_semantic_t4_user_prompt,
    _parse_proposal,
    maybe_enrich_t4_semantic, _permits_t4_call,
)
from app.config import settings  # noqa: E402
from app.config import t4_timeout_matches_code_default  # noqa: E402
from app.llm.clients.endpoint_resolver import resolve_local_primary_endpoint  # noqa: E402
from app.llm.sidecar_governance import (  # noqa: E402
    FAILURE_SLOT_BUSY,
    NOTE_LLM_SLOT_BUSY,
    request_human_model_restart,
    reset_t4_circuit,
    run_sidecar_llm_with_timeout,
)
from app.query_understanding.parser import understand_query  # noqa: E402

OUT_EMIT_DEFAULT = ROOT / "docs" / "evals" / "t4_coe_qualification.json"
OUT_LIVE_DEFAULT = ROOT / "docs" / "evals" / "t4_coe_qualification_live.json"
CHAT_BASE = os.environ.get("BASE", "http://127.0.0.1:8010")

# Recorded on every case. Live-only fields stay null under --emit-prompts.
CASE_RECORD_FIELDS: tuple[str, ...] = (
    "case_id",
    "class",
    "query",
    "source",
    "base_locked_fields",
    "unresolved_fields",
    "production_next_action",
    "t4_call_permitted",
    "exact_t4_prompt",
    "raw_proposal",
    "schema_valid",
    "proposed_fields",
    "accepted_fields",
    "rejected_fields",
    "rejected_reasons",
    "locked_fields_preserved",
    "clarification_result",
    "evidence_requirements",
    "direct_route_or_capability_widening",
    "latency_ms",
    "provider_failure_kind",
)

# Representative T4 cases. Queries are existing Plan 6/7/8 (or production few-shot)
# rows. This pack does not invent keyword routing rules.
CASES: tuple[dict[str, str], ...] = (
    {
        "case_id": "lateral_movement",
        "class": "lateral_movement",
        "query": "signs that something is moving sideways through the estate",
        "source": "plans 7 C3 / 8 U3",
    },
    {
        "case_id": "dga_dns_c2",
        "class": "dga_dns_c2",
        "query": "any domain lookups that look algorithmically generated",
        "source": "plans 6 para.003 / 7 C3 spl_capable_paraphrase / 8 U3",
    },
    {
        "case_id": "powershell_malicious_vs_admin",
        "class": "malicious_vs_administrative_powershell",
        "query": "endpoints where PowerShell ran in a way that looks off",
        "source": "plan 6 para.008 / routing truth set rt.para.008",
    },
    {
        "case_id": "identity_compromise",
        "class": "identity_compromise",
        "query": "repeated failed admin logons on a server then one that succeeded",
        "source": "production T4 few-shot A in semantic_t4_understanding.py",
    },
    {
        "case_id": "potential_exfiltration",
        "class": "potential_exfiltration",
        "query": "anyone shipping unusually large volumes of data outward",
        "source": "plan 6 para.007 / routing truth set rt.para.007",
    },
    {
        "case_id": "missing_referent_clarification",
        "class": "ambiguous_missing_referent_clarification",
        "query": (
            "compare this with what happened last week and tell me if it is getting worse"
        ),
        "source": "plans 7 C3 missing_context / 8 U3",
    },
    {
        "case_id": "insufficient_evidence_inconclusive",
        "class": "insufficient_evidence_inconclusive",
        "query": (
            "Is unusual DNS traffic from an OT server enough to confirm command and control?"
        ),
        "source": "docs/evals/powergrid_soc_question_bank.json / test_ws1_safety_grounding.py",
    },
    {
        "case_id": "competing_hypotheses",
        "class": "competing_hypotheses",
        "query": "powershell on endpoints talking to new domains",
        "source": "plans 7 C3 competing_hypotheses / 8 U3",
    },
)

F3_DISPOSITION: dict[str, Any] = {
    "t4_semantic_capability": "proven",
    "vps_serving": "not_production_viable",
    "f3_status": "open",
    "f3_closed": False,
    "closure_requires": "coe_serving_qualification",
    "harness_never_auto_closes_f3": True,
    "coe_pass_not_assumed": True,
}

def _jsonable(value: Any) -> Any:
    if isinstance(value, (frozenset, set)):
        return [_jsonable(item) for item in sorted(value, key=str)]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    return value


def _git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = (proc.stdout or "").strip()
    return sha or None


def _empty_live_fields() -> dict[str, Any]:
    return {
        "raw_proposal": None,
        "schema_valid": None,
        "proposed_fields": None,
        "accepted_fields": None,
        "rejected_fields": None,
        "rejected_reasons": None,
        "locked_fields_preserved": None,
        "clarification_result": None,
        "evidence_requirements": None,
        "direct_route_or_capability_widening": None,
        "latency_ms": None,
        "provider_failure_kind": None,
        "invoked": None,
        "accepted": None,
        "timed_out": None,
    }


def refuse_live_on_code_default_timeout() -> str | None:
    """Live qualification must not silently use the 2.0s code default."""
    if t4_timeout_matches_code_default(settings.ai_soc_t4_semantic_understanding_timeout_seconds):
        return (
            "REFUSING: T4 live qualification cannot use the code-default timeout "
            "(2.0s). Set AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS explicitly "
            "in .env. Do not copy the VPS 120s bound as a COE SLO."
        )
    return None


def _enable_t4_flag_only() -> dict[str, Any]:
    """In-process measurement enable. Does not persist, does not change timeout/model."""
    previous = bool(settings.ai_soc_t4_semantic_understanding_enabled)
    settings.ai_soc_t4_semantic_understanding_enabled = True
    return {
        "enabled_in_process": True,
        "previous_enabled": previous,
        "timeout_seconds_unchanged": float(
            settings.ai_soc_t4_semantic_understanding_timeout_seconds
        ),
        "timeout_not_modified_by_harness": True,
        "model_not_modified_by_harness": True,
        "provider_not_modified_by_harness": True,
    }


def _production_contract(query: str) -> ResolvedQueryContract:
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    base = build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier="T4",
        qualification_source="t4_coe_qualification",
        query_to_intent=q2i,
    )
    if base.understanding_sufficiency:
        return base
    return attach_understanding_authority(base)


def _measurement_contract(
    case: dict[str, str], production: ResolvedQueryContract
) -> tuple[ResolvedQueryContract, str]:
    """T4 hop contract.

    Hunt-shaped classes still need a CALL_T4 contract so COE can measure the hop.
    Missing-referent production now defers unresolved semantic referents to T4.
    This is not a keyword routing rule and does not change production /chat.
    """
    next_action = str((production.understanding_sufficiency or {}).get("next_action") or "")
    if next_action == "CALL_T4":
        return production, "production_call_t4"
    family = production.intent_family
    answer_goal = production.answer_goal
    if family == "clarification_required":
        family = "live_investigation"
    if answer_goal == "clarification":
        answer_goal = "live_results"
    overlay = production.model_copy(
        update={
            "intent_family": family,
            "answer_goal": answer_goal,
            "ambiguity_state": "clarification_required",
            "clarification_required": True,
            "clarification_reason": "measurement_overlay_semantic_referent",
            "qualification_tier": "T4",
            "locked_fields": {},
            "unresolved_fields": [],
            "understanding_sufficiency": None,
        }
    )
    attached = attach_understanding_authority(overlay)
    # Measurement-only pin: exact entity bindings must not cancel the ABSTAIN gap
    # (production would ACCEPT those; the harness still needs a permitted hop).
    from app.chat.contracts.staged_sufficiency import from_understanding_state

    locked = attached.locked_fields or {}
    sufficiency = from_understanding_state(
        required=["semantic_referent"],
        available=sorted(locked.keys()),
        missing=[],
        locked=sorted(locked.keys()),
        unresolved=["semantic_referent"],
        clarification_required=False,
        policy_blocked=False,
    )
    pinned = attached.model_copy(
        update={
            "clarification_required": False,
            "clarification_reason": None,
            "ambiguity_state": (
                "unambiguous"
                if attached.ambiguity_state == "clarification_required"
                else attached.ambiguity_state
            ),
            "unresolved_fields": ["semantic_referent"],
            "understanding_sufficiency": sufficiency.model_dump(mode="json"),
            "provenance": {
                **(attached.provenance or {}),
                "t4_owns_unresolved_semantic_referent": True,
            },
        }
    )
    return pinned, "c3_call_t4_measurement_overlay"


def _exact_prompt(query: str, contract: ResolvedQueryContract) -> dict[str, str]:
    user = _build_semantic_t4_user_prompt(query, contract)
    return {
        "system": _SEMANTIC_T4_SYSTEM_PROMPT,
        "user": user,
        "combined": f"{_SEMANTIC_T4_SYSTEM_PROMPT}\n\n{user}",
    }


def _prompt_pack(case: dict[str, str]) -> dict[str, Any]:
    query = case["query"]
    production = _production_contract(query)
    base, overlay_kind = _measurement_contract(case, production)
    production_next = str((production.understanding_sufficiency or {}).get("next_action") or "")
    hop_next = str((base.understanding_sufficiency or {}).get("next_action") or "")
    return {
        "case_id": case["case_id"],
        "class": case["class"],
        "query": query,
        "source": case["source"],
        "base_locked_fields": _jsonable(base.locked_fields or {}),
        "unresolved_fields": list(base.unresolved_fields or []),
        "production_next_action": production_next,
        "production_intent_family": production.intent_family,
        "measurement_overlay": overlay_kind,
        "t4_call_permitted": _permits_t4_call(base),
        "exact_t4_prompt": _exact_prompt(query, base),
        "intent_family": base.intent_family,
        "answer_goal": base.answer_goal,
        "ambiguity_state": base.ambiguity_state,
        "clarification_required": bool(base.clarification_required),
        "required_capabilities": sorted(base.required_capabilities),
        "prohibited_capabilities": sorted(base.prohibited_capabilities),
        "_base_contract": base,
    }


def _widening(base: ResolvedQueryContract, enriched: ResolvedQueryContract) -> dict[str, Any]:
    extra_caps = sorted(set(enriched.required_capabilities) - set(base.required_capabilities))
    dropped_prohibitions = sorted(
        set(base.prohibited_capabilities) - set(enriched.prohibited_capabilities)
    )
    return {
        "capability_widening": extra_caps,
        "prohibitions_weakened": dropped_prohibitions,
        "intent_family_changed": enriched.intent_family != base.intent_family,
        "route_or_skill_granted": False,
        "direct_widening": bool(extra_caps)
        or bool(dropped_prohibitions)
        or enriched.intent_family != base.intent_family,
    }


def _locked_preserved(base: ResolvedQueryContract, enriched: ResolvedQueryContract) -> bool:
    if base.intent_family != enriched.intent_family:
        return False
    if base.answer_goal != enriched.answer_goal and not (
        enriched.clarification_required and enriched.answer_goal == "clarification"
    ):
        return False
    if set(base.prohibited_capabilities) - set(enriched.prohibited_capabilities):
        return False
    locked = base.locked_fields or {}
    if "time_scope" in locked and enriched.time_scope != base.time_scope:
        return False
    return True


def _clarification_result(
    base: ResolvedQueryContract, enriched: ResolvedQueryContract
) -> dict[str, Any]:
    return {
        "base_clarification_required": bool(base.clarification_required),
        "post_clarification_required": bool(enriched.clarification_required),
        "base_reason": base.clarification_reason,
        "post_reason": enriched.clarification_reason,
        "cleared": bool(base.clarification_required) and not bool(enriched.clarification_required),
        "added": (not bool(base.clarification_required))
        and bool(enriched.clarification_required),
    }


def _record_from_enrichment(
    pack: dict[str, Any],
    enriched: ResolvedQueryContract,
    *,
    raw_proposal: str | None,
    wall_ms: int | None,
) -> dict[str, Any]:
    base: ResolvedQueryContract = pack["_base_contract"]
    trace = (enriched.provenance or {}).get("semantic_t4") or {}
    proposed = list(trace.get("proposed_fields") or [])
    accepted = list(trace.get("accepted_fields") or [])
    reasons = list(trace.get("rejected_reasons") or [])
    schema_valid: bool | None
    if raw_proposal is None and not trace.get("invoked"):
        schema_valid = None
    elif raw_proposal:
        schema_valid = _parse_proposal(raw_proposal)[0] is not None
    else:
        schema_valid = "schema_invalid" not in reasons and bool(proposed or accepted)
        if reasons and set(reasons) <= {"timed_out", "provider_unavailable", "empty_output", "circuit_open", "slot_busy"}:
            schema_valid = None
    widening = _widening(base, enriched)
    dumped = pack.copy()
    dumped.pop("_base_contract", None)
    dumped.update(
        {
            "raw_proposal": raw_proposal,
            "schema_valid": schema_valid,
            "proposed_fields": proposed,
            "accepted_fields": accepted,
            "rejected_fields": [name for name in proposed if name not in accepted],
            "rejected_reasons": reasons,
            "locked_fields_preserved": _locked_preserved(base, enriched),
            "clarification_result": _clarification_result(base, enriched),
            "evidence_requirements": {
                "base": list(base.evidence_requirements),
                "post": list(enriched.evidence_requirements),
                "added": [
                    item
                    for item in enriched.evidence_requirements
                    if item not in base.evidence_requirements
                ],
            },
            "direct_route_or_capability_widening": widening,
            "latency_ms": {
                "elapsed_ms": trace.get("elapsed_ms"),
                "wall_ms": wall_ms,
                "timeout_seconds": trace.get("timeout_seconds"),
            },
            "provider_failure_kind": trace.get("failure_kind"),
            "invoked": trace.get("invoked"),
            "accepted": trace.get("accepted"),
            "timed_out": trace.get("timed_out"),
            "human_action_required": bool(trace.get("human_action_required")),
            "circuit_state": trace.get("circuit_state"),
        }
    )
    return dumped


def emit_case_prompts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in CASES:
        pack = _prompt_pack(case)
        pack.pop("_base_contract", None)
        pack.update(_empty_live_fields())
        rows.append(pack)
    return rows


def run_live_cases_with_raw() -> list[dict[str, Any]]:
    """Live hop through production sidecar (slot + circuit), capturing raw text.

    Patches ``_live_single_hop_provider`` in place so ``maybe_enrich_t4_semantic``
    still uses ``run_sidecar_llm_with_timeout``. A ``raw_output_provider`` argument
    would take the injected path and skip slot pressure.
    """
    from app.chat import semantic_t4_understanding as t4

    original = t4._live_single_hop_provider
    rows: list[dict[str, Any]] = []
    try:
        for case in CASES:
            pack = _prompt_pack(case)
            base: ResolvedQueryContract = pack["_base_contract"]
            captured: dict[str, str | None] = {"raw": None}

            def _wrapped(query: str, contract: ResolvedQueryContract, _cap=captured) -> str:
                text = original(query, contract)
                _cap["raw"] = text
                return text

            t4._live_single_hop_provider = _wrapped
            started = time.monotonic()
            enriched = maybe_enrich_t4_semantic(base, query=case["query"])
            wall_ms = int((time.monotonic() - started) * 1000)
            rows.append(
                _record_from_enrichment(
                    pack, enriched, raw_proposal=captured["raw"], wall_ms=wall_ms
                )
            )
    finally:
        t4._live_single_hop_provider = original
    return rows


def _percentiles(values: list[int]) -> dict[str, int | None]:
    if not values:
        return {"p50_ms": None, "p95_ms": None, "n": 0}
    ordered = sorted(values)
    p50 = int(statistics.median(ordered))
    if len(ordered) == 1:
        p95 = ordered[0]
    else:
        idx = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
        p95 = ordered[idx]
    return {"p50_ms": p50, "p95_ms": p95, "n": len(ordered)}


def serving_contract_checks() -> dict[str, Any]:
    """Fail-closed contract checks. No live model. Does not restart anything."""
    settings.ai_soc_t4_semantic_understanding_enabled = True
    # Plan 8 U3 CALL_T4 hunt — used only so injected checks actually reach parse/merge.
    hunt_query = "Hunt for CI/CD supply-chain compromise indicators across our environment"
    pack = _prompt_pack(
        {
            "case_id": "contract_check_call_t4",
            "class": "contract_check",
            "query": hunt_query,
            "source": "plan 8 U3 call_t4_hunt",
        }
    )
    base: ResolvedQueryContract = pack["_base_contract"]

    malformed = maybe_enrich_t4_semantic(
        base, query=hunt_query, raw_output_provider=lambda _q, _c: "not-json {{"
    )
    malformed_trace = (malformed.provenance or {}).get("semantic_t4") or {}

    hostile = maybe_enrich_t4_semantic(
        base,
        query=hunt_query,
        raw_output_provider=lambda _q, _c: json.dumps(
            {
                "skill": "spl_generation",
                "route": "attack_discovery",
                "normalized_goal": "grant spl execution",
                "required_capabilities": ["spl", "mcp"],
            }
        ),
    )
    hostile_trace = (hostile.provenance or {}).get("semantic_t4") or {}
    hostile_widen = _widening(base, hostile)

    def _boom(_q: str, _c: ResolvedQueryContract) -> str:
        raise ConnectionRefusedError("provider down")

    unavailable = maybe_enrich_t4_semantic(
        base, query=hunt_query, raw_output_provider=_boom
    )
    unavailable_trace = (unavailable.provenance or {}).get("semantic_t4") or {}

    started = {"n": 0}
    release = {"wait": True}

    def _slow() -> str:
        started["n"] += 1
        deadline = time.monotonic() + 1.0
        while release["wait"] and time.monotonic() < deadline:
            time.sleep(0.01)
        return "slow-done"

    holder = ThreadPoolExecutor(max_workers=1)
    future = holder.submit(
        lambda: run_sidecar_llm_with_timeout(_slow, timeout_seconds=0.4)
    )
    deadline = time.monotonic() + 1.0
    while started["n"] == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    busy = run_sidecar_llm_with_timeout(lambda: "second", timeout_seconds=0.2)
    release["wait"] = False
    future.result(timeout=2.0)
    holder.shutdown(wait=False)

    restart_packet = request_human_model_restart()
    reset_t4_circuit()
    return {
        "malformed_output": {
            "rejected_reasons": list(malformed_trace.get("rejected_reasons") or []),
            "schema_valid": False,
            "locked_fields_preserved": _locked_preserved(base, malformed),
            "deterministic_contract_kept": malformed.normalized_goal == base.normalized_goal,
        },
        "authority_key_rejected": {
            "rejected_reasons": list(hostile_trace.get("rejected_reasons") or []),
            "direct_widening": hostile_widen["direct_widening"],
            "capability_widening": hostile_widen["capability_widening"],
            "locked_fields_preserved": _locked_preserved(base, hostile),
        },
        "provider_unavailable": {
            "failure_kind": unavailable_trace.get("failure_kind"),
            "rejected_reasons": list(unavailable_trace.get("rejected_reasons") or []),
            "human_action_required": bool(unavailable_trace.get("human_action_required")),
            "did_not_restart": True,
        },
        "slot_pressure_synthetic": {
            "failure_kind": busy.failure_kind,
            "notes": list(busy.notes or []),
            "expected_kind": FAILURE_SLOT_BUSY,
            "slot_busy_note": NOTE_LLM_SLOT_BUSY in list(busy.notes or []),
        },
        "human_restart_only": {
            "restart_authorized": restart_packet.get("restart_authorized"),
            "human_action_required": restart_packet.get("human_action_required"),
            "procedure_does_not_restart": "does not restart"
            in str(restart_packet.get("procedure") or ""),
        },
    }


def _models_liveness() -> dict[str, Any]:
    """GET /v1/models — liveness only, never inference health (Plan 7 F2 / Plan 8 REL0)."""
    endpoint = resolve_local_primary_endpoint(sidecar=True)
    if endpoint is None:
        return {
            "kind": "liveness_not_inference_health",
            "probe": "GET /v1/models",
            "reachable": False,
            "http_status": None,
            "note": "/v1/models=200 is liveness, not inference health",
        }
    url = endpoint.base_url.rstrip("/") + "/models"
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            status = int(resp.status)
            body = resp.read(200)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {
            "kind": "liveness_not_inference_health",
            "probe": "GET /v1/models",
            "reachable": False,
            "http_status": None,
            "error": type(exc).__name__,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "note": "/v1/models=200 is liveness, not inference health",
        }
    return {
        "kind": "liveness_not_inference_health",
        "probe": "GET /v1/models",
        "reachable": True,
        "http_status": status,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "body_prefix_len": len(body),
        "note": "/v1/models=200 is liveness, not inference health",
        "inference_health": False,
    }


def _inference_health() -> dict[str, Any]:
    from app.llm.runtime_health import measure_runtime

    measured = measure_runtime(timeout=45.0)
    return {
        "kind": "inference_health",
        "probe": "bounded_generation",
        "not": "/v1/models",
        **measured,
    }


def _concurrency_probe(workers: int) -> dict[str, Any]:
    eligible = [case for case in CASES if case["case_id"] in {"dga_dns_c2", "powershell_malicious_vs_admin", "potential_exfiltration"}]
    subset = eligible[:workers]
    started = time.monotonic()
    results: list[dict[str, Any]] = []

    def _one(case: dict[str, str]) -> dict[str, Any]:
        pack = _prompt_pack(case)
        base: ResolvedQueryContract = pack["_base_contract"]
        hop_started = time.monotonic()
        enriched = maybe_enrich_t4_semantic(base, query=case["query"])
        trace = (enriched.provenance or {}).get("semantic_t4") or {}
        return {
            "case_id": case["case_id"],
            "invoked": trace.get("invoked"),
            "accepted": trace.get("accepted"),
            "failure_kind": trace.get("failure_kind"),
            "timed_out": trace.get("timed_out"),
            "elapsed_ms": trace.get("elapsed_ms"),
            "wall_ms": int((time.monotonic() - hop_started) * 1000),
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, case) for case in subset]
        for future in as_completed(futures):
            results.append(future.result())
    return {
        "requested_concurrency": workers,
        "wall_ms": int((time.monotonic() - started) * 1000),
        "rows": results,
        "slot_busy_count": sum(1 for row in results if row.get("failure_kind") == FAILURE_SLOT_BUSY),
        "timeout_count": sum(1 for row in results if row.get("timed_out")),
        "accepted_count": sum(1 for row in results if row.get("accepted")),
    }


def _chat_smoke() -> dict[str, Any]:
    """One /chat turn through the running app. COE-only; not run on emit-prompts."""
    query = next(case for case in CASES if case["case_id"] == "dga_dns_c2")["query"]
    payload = json.dumps({"message": query, "session_id": "t4-coe-qualification"}).encode()
    url = CHAT_BASE.rstrip("/") + "/api/chat"
    started = time.monotonic()
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
            body = json.loads(resp.read().decode("utf-8"))
            status = int(resp.status)
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ran": True,
            "ok": False,
            "error": type(exc).__name__,
            "wall_ms": int((time.monotonic() - started) * 1000),
            "url": url,
        }
    cp = body.get("control_plane_trace") if isinstance(body, dict) else {}
    resolved = (cp or {}).get("resolved_query") if isinstance(cp, dict) else {}
    semantic = (resolved or {}).get("semantic_t4") if isinstance(resolved, dict) else {}
    workflow = body.get("workflow_plan") if isinstance(body, dict) else {}
    return {
        "ran": True,
        "ok": status == 200,
        "http_status": status,
        "wall_ms": int((time.monotonic() - started) * 1000),
        "route": (workflow or {}).get("skill"),
        "execution_enabled": (workflow or {}).get("execution_enabled"),
        "t4_invoked": bool((semantic or {}).get("invoked")),
        "t4_accepted": bool((semantic or {}).get("accepted")),
        "t4_failure_kind": (semantic or {}).get("failure_kind"),
        "t4_elapsed_ms": (semantic or {}).get("elapsed_ms"),
        "note": "application T4 integration via /chat; T4 still cannot grant route/capability",
    }


def serving_unmeasured() -> dict[str, Any]:
    return {
        "measured": False,
        "environment": "emit_prompts_or_not_coe",
        "f3_status": "open",
        "f3_closed": False,
        "coe_pass_not_assumed": True,
        "models_liveness": {
            "kind": "liveness_not_inference_health",
            "probe": "GET /v1/models",
            "note": "/v1/models=200 is liveness, not inference health",
            "measured": False,
        },
        "inference_health": {
            "kind": "inference_health",
            "probe": "bounded_generation",
            "not": "/v1/models",
            "measured": False,
        },
        "latency": {
            "cold_ms": None,
            "warm_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "measured": False,
        },
        "timeout_error_rate": {"timeouts": None, "errors": None, "n": None, "measured": False},
        "concurrency": {"n2": None, "n3": None, "measured": False},
        "slot_pressure": {"measured": False, "synthetic_contract": True},
        "application_t4_integration": {
            "seam": "app.chat.semantic_t4_understanding.maybe_enrich_t4_semantic",
            "chat_smoke": {"ran": False},
        },
        "human_restart_only": True,
        "no_automatic_cisco_restart": True,
    }


def serving_from_live(
    cases: list[dict[str, Any]],
    *,
    chat_smoke: bool,
) -> dict[str, Any]:
    invoked = [row for row in cases if row.get("invoked")]
    elapsed = [
        int(row["latency_ms"]["elapsed_ms"])
        for row in invoked
        if isinstance(row.get("latency_ms"), dict) and row["latency_ms"].get("elapsed_ms") is not None
    ]
    cold = elapsed[0] if elapsed else None
    warm = elapsed[1] if len(elapsed) > 1 else None
    timeouts = sum(1 for row in invoked if row.get("timed_out"))
    errors = sum(1 for row in cases if row.get("provider_failure_kind") not in {None, ""})
    n2 = _concurrency_probe(2)
    n3 = _concurrency_probe(3)
    chat = _chat_smoke() if chat_smoke else {"ran": False, "skipped": True}
    return {
        "measured": True,
        "environment": "live_configured_t4_provider",
        "f3_status": "open",
        "f3_closed": False,
        "coe_pass_not_assumed": True,
        "pass_fail_not_asserted_by_harness": True,
        "models_liveness": _models_liveness(),
        "inference_health": _inference_health(),
        "latency": {
            "cold_ms": cold,
            "warm_ms": warm,
            **_percentiles(elapsed),
            "samples_ms": elapsed,
        },
        "timeout_error_rate": {
            "invoked_n": len(invoked),
            "timeouts": timeouts,
            "errors": errors,
            "n": len(cases),
            "timeout_rate": (timeouts / len(invoked)) if invoked else None,
            "error_rate": (errors / len(cases)) if cases else None,
        },
        "concurrency": {"n2": n2, "n3": n3},
        "slot_pressure": {
            "n2_slot_busy": n2.get("slot_busy_count"),
            "n3_slot_busy": n3.get("slot_busy_count"),
        },
        "application_t4_integration": {
            "seam": "app.chat.semantic_t4_understanding.maybe_enrich_t4_semantic",
            "live_cases_used_production_merge": True,
            "chat_smoke": chat,
        },
        "human_restart_only": True,
        "no_automatic_cisco_restart": True,
    }


def build_report(*, mode: str, chat_smoke: bool = False) -> dict[str, Any]:
    flag = _enable_t4_flag_only()
    contract_checks = serving_contract_checks()
    if mode == "emit-prompts":
        cases = emit_case_prompts()
        serving = serving_unmeasured()
        serving["contract_checks"] = contract_checks
    elif mode == "live":
        cases = run_live_cases_with_raw()
        serving = serving_from_live(cases, chat_smoke=chat_smoke)
        serving["contract_checks"] = contract_checks
    else:
        raise ValueError(f"unknown mode: {mode}")
    return {
        "pack": "t4_coe_qualification",
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "f3_disposition": dict(F3_DISPOSITION),
        "invariants": {
            "reuses_production_t4": True,
            "prompt_builder": "app.chat.semantic_t4_understanding._build_semantic_t4_user_prompt",
            "system_prompt": "app.chat.semantic_t4_understanding._SEMANTIC_T4_SYSTEM_PROMPT",
            "schema": "app.chat.contracts.semantic_t4_proposal.SemanticT4Proposal",
            "merge": "app.chat.semantic_t4_understanding._merge_proposal",
            "t4_cannot_grant_route_capability_or_tool_authority": True,
            "v1_models_is_liveness_not_inference_health": True,
            "no_automatic_cisco_restart": True,
            "human_restart_only": True,
            "timeout_model_provider_unchanged": True,
        },
        "t4_flag": flag,
        "case_record_fields": list(CASE_RECORD_FIELDS),
        "cases": cases,
        "serving": serving,
    }


def assert_output_contract(report: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    cases = report.get("cases") or []
    if len(cases) != 8:
        failures.append(f"expected 8 cases, got {len(cases)}")
    expected_ids = [case["case_id"] for case in CASES]
    got_ids = [row.get("case_id") for row in cases]
    if got_ids != expected_ids:
        failures.append(f"case_ids={got_ids} expected={expected_ids}")
    for row in cases:
        for field in CASE_RECORD_FIELDS:
            if field not in row:
                failures.append(f"{row.get('case_id')}: missing {field}")
        prompt = row.get("exact_t4_prompt") or {}
        if prompt.get("system") != _SEMANTIC_T4_SYSTEM_PROMPT:
            failures.append(f"{row.get('case_id')}: system prompt is not production T4")
        if "Do not grant route, capability, SPL, MCP, RBAC, HIL" not in str(
            prompt.get("system") or ""
        ):
            failures.append(f"{row.get('case_id')}: production T4 authority rule missing")
    disposition = report.get("f3_disposition") or {}
    if disposition.get("f3_closed") is True:
        failures.append("harness must not close F3")
    if disposition.get("f3_status") != "open":
        failures.append("F3 must remain open until COE measurement passes")
    serving = report.get("serving") or {}
    liveness = serving.get("models_liveness") or {}
    if liveness.get("kind") != "liveness_not_inference_health":
        failures.append("/v1/models must be labelled liveness, not inference health")
    if serving.get("f3_closed") is True:
        failures.append("serving section must not close F3")
    invariants = report.get("invariants") or {}
    if not invariants.get("t4_cannot_grant_route_capability_or_tool_authority"):
        failures.append("missing T4 authority invariant")
    if not invariants.get("no_automatic_cisco_restart"):
        failures.append("missing human-restart invariant")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--emit-prompts", action="store_true")
    mode.add_argument("--live", action="store_true")
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--chat-smoke",
        action="store_true",
        help="With --live, also POST one /chat turn. Never used by --emit-prompts.",
    )
    parser.add_argument("--check", action="store_true", help="Validate output contract and exit.")
    args = parser.parse_args()
    selected = "live" if args.live else "emit-prompts"
    if selected == "emit-prompts" and args.chat_smoke:
        print("--chat-smoke requires --live", file=sys.stderr)
        return 2
    if selected == "live":
        refused = refuse_live_on_code_default_timeout()
        if refused:
            print(refused, file=sys.stderr)
            return 2
    out = Path(args.out) if args.out else (
        OUT_LIVE_DEFAULT if selected == "live" else OUT_EMIT_DEFAULT
    )
    report = build_report(mode=selected, chat_smoke=bool(args.chat_smoke))
    failures = assert_output_contract(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "mode": selected,
            "out": str(out),
            "cases": len(report["cases"]),
            "f3_status": report["f3_disposition"]["f3_status"],
            "f3_closed": report["f3_disposition"]["f3_closed"],
            "contract_failures": failures,
        },
        indent=2,
    ))
    if args.check or failures:
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
