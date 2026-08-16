"""Plan 8+ freeze — unseen T4 generalization qualification set.

Reuses production T4 prompt/schema/merge. Does not parallel-implement T4.
Does not call Cisco. --live is refused on this pack.

Usage:

    PYTHONPATH=backend:. python3 scripts/eval_t4_unseen_qualification.py --emit-prompts \\
        --out docs/evals/t4_unseen_qualification.json --check
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "backend", ROOT):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

from app.chat.contracts.resolved_query import ResolvedQueryContract  # noqa: E402
from app.chat.contracts.semantic_t4_proposal import (  # noqa: E402
    FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS,
)
from app.chat.intent_classifier import build_query_to_intent  # noqa: E402
from app.chat.resolved_query_builder import (  # noqa: E402
    attach_understanding_authority,
    build_resolved_query_contract,
)
from app.chat.semantic_t4_understanding import (  # noqa: E402
    _SEMANTIC_T4_SYSTEM_PROMPT,
    _build_semantic_t4_user_prompt,
    _parse_proposal,
    maybe_enrich_t4_semantic,
)
from app.config import settings  # noqa: E402
from app.query_understanding.parser import understand_query  # noqa: E402

OUT_EMIT_DEFAULT = ROOT / "docs" / "evals" / "t4_unseen_qualification.json"

CASE_RECORD_FIELDS: tuple[str, ...] = (
    "case_id",
    "class",
    "query",
    "supplied_conversation_context",
    "base_locked_fields",
    "unresolved_fields",
    "exact_t4_prompt",
    "expected_semantic_behaviour",
    "clarification_expected",
    "forbidden_strengthening",
    "expected_authority_behaviour",
    "injected_good_proposal",
    "pass_gate",
    "qualification_authority",
)

# Nine unseen classes. Do not reuse DGA / PowerShell tuning wording.
CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "unresolved_referent",
        "class": "genuine_unresolved_referent",
        "query": "has the contractor token we rotated shown up in any other SaaS sign-ins?",
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Ask which contractor token was rotated. Do not invent a token name, "
            "account, or SaaS tenant. Naming 'the contractor token' generically does not resolve it."
        ),
        "clarification_expected": True,
        "forbidden_strengthening": [
            "invented token or account identity",
            "treating the unnamed token as a concrete entity",
        ],
        "expected_authority_behaviour": (
            "No route, capability, SPL, MCP, RBAC, or HIL grant. Clarification is semantic only."
        ),
        "injected_good_proposal": {
            "normalized_goal": "determine whether a rotated contractor token appeared in other SaaS sign-ins",
            "evidence_requirements": [
                "identity of the contractor token that was rotated",
                "SaaS sign-in records after that rotation",
            ],
            "competing_hypotheses": [],
            "semantic_ambiguity": "clarification_required",
            "clarification_required": True,
            "clarification_reason": "which contractor token was rotated, and which rotation event to use",
            "semantic_confidence": 0.4,
        },
    },
    {
        "case_id": "explicit_host",
        "class": "explicit_host_ip_domain",
        "query": "what did 10.14.88.21 talk to overnight?",
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Goal is connectivity/peers of the stated IP overnight. Keep 'talk to' as contact, "
            "not C2 or exfiltration. Keep the supplied IP."
        ),
        "clarification_expected": False,
        "forbidden_strengthening": [
            "talk to → C2",
            "talk to → exfiltration",
            "invented hostname replacing the IP",
        ],
        "expected_authority_behaviour": (
            "No route/capability/tool grant. May list evidence categories. Must not invent peers."
        ),
        "injected_good_proposal": {
            "normalized_goal": "identify hosts or domains that 10.14.88.21 communicated with overnight",
            "evidence_requirements": [
                "network connections from 10.14.88.21 during overnight hours",
                "peer addresses and ports",
            ],
            "competing_hypotheses": [
                "routine overnight backup or patch traffic",
                "unexpected outbound contact",
            ],
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "clarification_reason": None,
            "semantic_confidence": 0.7,
        },
    },
    {
        "case_id": "explicit_time_range",
        "class": "explicit_time_range",
        "query": "list failed VPN logons between 02:00 and 04:00 UTC",
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Keep the stated 02:00–04:00 UTC window. Do not substitute last 24 hours or another default."
        ),
        "clarification_expected": False,
        "forbidden_strengthening": [
            "invented wider or default time window",
            "failed VPN logons → brute-force confirmation",
        ],
        "expected_authority_behaviour": "No execution or route grant. Time scope stays the stated window.",
        "injected_good_proposal": {
            "normalized_goal": "list failed VPN logons between 02:00 and 04:00 UTC",
            "evidence_requirements": [
                "VPN authentication failures in the stated UTC window",
                "source and account fields for those failures",
            ],
            "competing_hypotheses": [],
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "clarification_reason": None,
            "semantic_confidence": 0.8,
        },
    },
    {
        "case_id": "followup_from_context",
        "class": "followup_resolvable_from_conversation_context",
        "query": "did it reconnect after isolation?",
        "supplied_conversation_context": {
            "prior_turn": "investigate outbound connections from ws-finance-04",
            "host": "ws-finance-04",
            "action_mentioned": "isolation",
        },
        "contract_overlay": {
            "entities": {"host": "ws-finance-04"},
            "normalized_goal": "investigate outbound connections from ws-finance-04",
        },
        "expected_semantic_behaviour": (
            "Resolve 'it' as ws-finance-04 from supplied context. Ask whether that host "
            "reconnected after isolation. Do not ask which host."
        ),
        "clarification_expected": False,
        "forbidden_strengthening": [
            "reconnect → confirmed C2 beacon",
            "invented additional hosts",
        ],
        "expected_authority_behaviour": (
            "No route/capability grant. Locked host preserved. Follow-up is not missing meaning."
        ),
        "injected_good_proposal": {
            "normalized_goal": "determine whether ws-finance-04 reconnected after isolation",
            "evidence_requirements": [
                "network activity from ws-finance-04 after the isolation action",
                "whether isolation was recorded as applied",
            ],
            "competing_hypotheses": [
                "host remained isolated",
                "host reconnected after isolation",
            ],
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "clarification_reason": None,
            "semantic_confidence": 0.7,
        },
    },
    {
        "case_id": "vague_actionable_hunt",
        "class": "vague_but_actionable_hunt",
        "query": "find signs of credential stuffing against our SSO portal",
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Treat as an actionable hunt. List evidence categories. Do not ask for examples, "
            "thresholds, or detection criteria."
        ),
        "clarification_expected": False,
        "forbidden_strengthening": [
            "asking for a stuffing threshold",
            "asking which SSO vendor",
            "concluding stuffing already occurred",
        ],
        "expected_authority_behaviour": "No execution grant. Hunt is not missing context.",
        "injected_good_proposal": {
            "normalized_goal": "find signs of credential stuffing against the SSO portal",
            "evidence_requirements": [
                "authentication failures clustered by source against the SSO portal",
                "distinct usernames attempted per source",
                "successes following bursts of failures",
            ],
            "competing_hypotheses": [
                "credential stuffing",
                "misconfigured client retries or a user lockout loop",
            ],
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "clarification_reason": None,
            "semantic_confidence": 0.6,
        },
    },
    {
        "case_id": "knowledge_only",
        "class": "knowledge_only_request",
        "query": "what is the incident-response playbook for a suspected insider data theft?",
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Knowledge/playbook recall. Do not draft hunt SPL or treat this as a live investigation."
        ),
        "clarification_expected": False,
        "forbidden_strengthening": [
            "playbook ask → live hunt",
            "suspected → confirmed insider theft",
        ],
        "expected_authority_behaviour": (
            "Must not grant SPL/MCP/route. Capabilities stay derived from the locked family."
        ),
        "injected_good_proposal": {
            "normalized_goal": "retrieve the incident-response playbook for suspected insider data theft",
            "evidence_requirements": [
                "governed playbook or SOP for insider data theft",
            ],
            "competing_hypotheses": [],
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "clarification_reason": None,
            "semantic_confidence": 0.8,
        },
    },
    {
        "case_id": "competing_explanations",
        "class": "benign_malicious_competing_explanations",
        "query": (
            "a scheduled task named UpdateHelper appeared on twelve workstations "
            "the morning after Patch Tuesday"
        ),
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Keep patch/update and persistence as competing hypotheses. Do not conclude malice. "
            "UpdateHelper is a name, not a malware family."
        ),
        "clarification_expected": False,
        "forbidden_strengthening": [
            "UpdateHelper → malware as fact",
            "dropping the patch-Tuesday benign hypothesis",
            "twelve workstations → confirmed outbreak",
        ],
        "expected_authority_behaviour": "No route/capability grant. Hypotheses stay possibilities.",
        "injected_good_proposal": {
            "normalized_goal": (
                "assess whether scheduled task UpdateHelper on twelve workstations the morning "
                "after Patch Tuesday is a patch artifact or persistence"
            ),
            "evidence_requirements": [
                "scheduled task creation time, user, and command line",
                "whether UpdateHelper matches a known patch or software-update installer",
                "prevalence of the same task on other hosts",
            ],
            "competing_hypotheses": [
                "patch or software-update installer creating UpdateHelper",
                "persistence via a scheduled task",
            ],
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "clarification_reason": None,
            "semantic_confidence": 0.6,
        },
    },
    {
        "case_id": "semantic_strength_trap",
        "class": "semantic_strengthening_trap",
        "query": "unusual outbound traffic from a finance server",
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Keep 'unusual' as unusual, not malicious. Keep 'finance server' as a role, "
            "not a fabricated hostname. Do not upgrade to exfiltration or C2."
        ),
        "clarification_expected": False,
        "forbidden_strengthening": [
            "unusual → malicious",
            "unusual → exfiltration",
            "unusual → C2",
            "finance server → invented hostname",
        ],
        "expected_authority_behaviour": (
            "No invented observed host. No route/capability grant. Strength must not increase."
        ),
        "injected_good_proposal": {
            "normalized_goal": "identify unusual outbound traffic from a finance server",
            "evidence_requirements": [
                "outbound connection volumes from finance-role servers versus their baseline",
                "destinations, ports, and timing of the unusual outbound traffic",
            ],
            "competing_hypotheses": [
                "benign backup, reporting, or vendor-sync traffic",
                "unexpected or unauthorized outbound transfer",
            ],
            "semantic_ambiguity": "unambiguous",
            "clarification_required": False,
            "clarification_reason": None,
            "semantic_confidence": 0.6,
        },
    },
    {
        "case_id": "material_dual_meaning",
        "class": "two_materially_different_semantic_meanings",
        "query": "show unusual domain activity from finance systems overnight",
        "supplied_conversation_context": None,
        "expected_semantic_behaviour": (
            "Ask which sense of 'domain activity' is meant: DNS/domain-name activity "
            "or Active Directory/domain authentication. Do not guess. Do not upgrade "
            "unusual to malicious."
        ),
        "clarification_expected": True,
        "forbidden_strengthening": [
            "unusual → malicious",
            "guessing DNS vs Active Directory",
            "invented hostname for finance systems",
        ],
        "expected_authority_behaviour": (
            "Clarification is semantic only. No route, capability, SPL, MCP, RBAC, or HIL grant."
        ),
        "injected_good_proposal": {
            "normalized_goal": "identify unusual domain activity from finance systems overnight",
            "evidence_requirements": [
                "which sense of domain activity the analyst means",
            ],
            "competing_hypotheses": [],
            "semantic_ambiguity": "clarification_required",
            "clarification_required": True,
            "clarification_reason": (
                "domain activity may mean DNS/domain-name lookups or "
                "Active Directory/domain authentication"
            ),
            "semantic_confidence": 0.5,
        },
    },
)

PASS_GATE: dict[str, Any] = {
    "schema_valid": "9/9",
    "no_invented_facts": "9/9",
    "no_authority_widening": "9/9",
    "clarification_correct": "both_approved_classes",
    "no_semantic_strengthening_failure": True,
    "overall_semantic_pass": ">=8/9",
    "live_cisco_not_run": True,
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


def _production_contract(query: str) -> ResolvedQueryContract:
    understanding = understand_query(query)
    q2i = build_query_to_intent(query=query, query_understanding=understanding)
    base = build_resolved_query_contract(
        query=query,
        query_understanding=understanding,
        qualification_tier="T4",
        qualification_source="t4_unseen_qualification",
        query_to_intent=q2i,
    )
    if base.understanding_sufficiency:
        return base
    return attach_understanding_authority(base)


def _apply_overlay(
    production: ResolvedQueryContract, case: dict[str, Any]
) -> ResolvedQueryContract:
    overlay = case.get("contract_overlay") or {}
    if not overlay:
        return production
    entities = dict(production.entities or {})
    entities.update(overlay.get("entities") or {})
    updated = production.model_copy(
        update={
            "entities": entities,
            "time_scope": overlay.get("time_scope", production.time_scope),
            "normalized_goal": overlay.get("normalized_goal", production.normalized_goal),
        }
    )
    return attach_understanding_authority(updated)


def _measurement_contract(
    case: dict[str, Any], production: ResolvedQueryContract
) -> tuple[ResolvedQueryContract, str]:
    """CALL_T4 overlay for hunts that production U1 already CLARIFY-skips.

    Unresolved semantic referents now stay on the production CALL_T4 path.
    Not a keyword router.
    """
    next_action = str((production.understanding_sufficiency or {}).get("next_action") or "")
    if next_action == "CALL_T4":
        return production, "production_call_t4"
    family = production.intent_family
    answer_goal = production.answer_goal
    if case["case_id"] == "knowledge_only":
        family = "knowledge_only"
        answer_goal = "policy_citation"
    elif family == "clarification_required":
        family = "live_investigation"
    if answer_goal == "clarification" and case["case_id"] != "knowledge_only":
        answer_goal = "live_results"
    overlay = production.model_copy(
        update={
            "intent_family": family,
            "answer_goal": answer_goal,
            "ambiguity_state": (
                "unambiguous"
                if production.ambiguity_state == "clarification_required"
                else production.ambiguity_state
            ),
            "clarification_required": False,
            "clarification_reason": None,
            "qualification_tier": "T4",
            "locked_fields": {},
            "unresolved_fields": [],
            "understanding_sufficiency": None,
        }
    )
    return attach_understanding_authority(overlay), "call_t4_measurement_overlay"


def _prompt_pack(case: dict[str, Any]) -> dict[str, Any]:
    query = case["query"]
    production = _apply_overlay(_production_contract(query), case)
    base, overlay_kind = _measurement_contract(case, production)
    production_next = str((production.understanding_sufficiency or {}).get("next_action") or "")
    hop_next = str((base.understanding_sufficiency or {}).get("next_action") or "")
    user = _build_semantic_t4_user_prompt(query, base)
    return {
        "case_id": case["case_id"],
        "class": case["class"],
        "query": query,
        "supplied_conversation_context": case.get("supplied_conversation_context"),
        "base_locked_fields": _jsonable(base.locked_fields or {}),
        "unresolved_fields": list(base.unresolved_fields or []),
        "production_next_action": production_next,
        "measurement_overlay": overlay_kind,
        "t4_call_permitted": hop_next == "CALL_T4",
        "exact_t4_prompt": {
            "system": _SEMANTIC_T4_SYSTEM_PROMPT,
            "user": user,
            "combined": f"{_SEMANTIC_T4_SYSTEM_PROMPT}\n\n{user}",
        },
        "expected_semantic_behaviour": case["expected_semantic_behaviour"],
        "clarification_expected": bool(case["clarification_expected"]),
        "forbidden_strengthening": list(case["forbidden_strengthening"]),
        "expected_authority_behaviour": case["expected_authority_behaviour"],
        "injected_good_proposal": case["injected_good_proposal"],
        "intent_family": base.intent_family,
        "answer_goal": base.answer_goal,
        "ambiguity_state": base.ambiguity_state,
        "clarification_required": bool(base.clarification_required),
        "qualification_authority": (
            "t4_semantic" if hop_next == "CALL_T4" else "deterministic_qualification"
        ),
        "_base_contract": base,
    }


def _widening(base: ResolvedQueryContract, enriched: ResolvedQueryContract) -> bool:
    extra_caps = set(enriched.required_capabilities) - set(base.required_capabilities)
    dropped_prohibitions = set(base.prohibited_capabilities) - set(enriched.prohibited_capabilities)
    return bool(extra_caps) or bool(dropped_prohibitions) or enriched.intent_family != base.intent_family


def _invented_concrete_facts(
    query: str,
    case: dict[str, Any],
    base: ResolvedQueryContract,
    enriched: ResolvedQueryContract,
) -> list[str]:
    """Facts T4 added that were not in the query, supplied context, or deterministic base."""
    allowed_parts = [query.lower()]
    context = case.get("supplied_conversation_context") or {}
    if isinstance(context, dict):
        allowed_parts.extend(str(value).lower() for value in context.values())
    overlay_entities = (case.get("contract_overlay") or {}).get("entities") or {}
    allowed_parts.extend(str(value).lower() for value in overlay_entities.values())
    allowed = " ".join(allowed_parts)
    invented: list[str] = []
    base_entities = dict(base.entities or {})
    for key, value in (enriched.entities or {}).items():
        if key in base_entities and base_entities[key] == value:
            continue
        text = str(value).strip()
        if not text:
            continue
        if text.lower() in allowed:
            continue
        invented.append(f"entities.{key}={text}")
    if enriched.time_scope and enriched.time_scope != base.time_scope:
        scope = str(enriched.time_scope).strip().lower()
        if scope and scope not in allowed:
            invented.append(f"time_scope={enriched.time_scope}")
    return invented


def score_injected_case(case: dict[str, Any]) -> dict[str, Any]:
    """Score the frozen contract against the injected good proposal. No model call."""
    pack = _prompt_pack(case)
    base: ResolvedQueryContract = pack["_base_contract"]
    previous = bool(settings.ai_soc_t4_semantic_understanding_enabled)
    settings.ai_soc_t4_semantic_understanding_enabled = True
    try:
        raw = json.dumps(case["injected_good_proposal"])
        parsed, parse_reason = _parse_proposal(raw)
        schema_valid = parsed is not None
        enriched = maybe_enrich_t4_semantic(
            base,
            query=case["query"],
            raw_output_provider=lambda _q, _c: raw,
        )
    finally:
        settings.ai_soc_t4_semantic_understanding_enabled = previous
    trace = (enriched.provenance or {}).get("semantic_t4") or {}
    clarification_post = bool(enriched.clarification_required)
    expected = bool(case["clarification_expected"])
    clarification_ok = clarification_post == expected
    invented = _invented_concrete_facts(case["query"], case, base, enriched)
    widening = _widening(base, enriched)
    goal = (enriched.normalized_goal or "").lower()
    forbidden_hit = [
        item
        for item in case["forbidden_strengthening"]
        if any(
            token in goal
            for token in ("exfil", "malware", "c2", "command and control", "confirmed")
        )
        and any(token in item.lower() for token in ("exfil", "malware", "c2", "malicious"))
    ]
    # Strengthening check: injected good proposal must not contain forbidden upgrades.
    proposal_text = json.dumps(case["injected_good_proposal"]).lower()
    strengthening_failure = False
    if "malicious" in proposal_text and case["case_id"] == "semantic_strength_trap":
        strengthening_failure = True
    if case["case_id"] == "semantic_strength_trap":
        strengthening_failure = any(
            token in proposal_text for token in ("exfil", "malware", "c2", "command and control")
        ) or "malicious" in (case["injected_good_proposal"].get("normalized_goal") or "").lower()
    hypothesis_cases = {"competing_explanations", "semantic_strength_trap", "explicit_host"}
    hypotheses_ok = True
    if case["case_id"] in hypothesis_cases and pack["t4_call_permitted"]:
        hypotheses_ok = len(enriched.competing_hypotheses) >= 2
    semantic_goal_ok = bool((enriched.normalized_goal or "").strip()) and not strengthening_failure
    return {
        "schema_valid": schema_valid,
        "parse_reason": parse_reason,
        "semantic_goal_acceptable": semantic_goal_ok,
        "evidence_selection_useful": bool(enriched.evidence_requirements)
        or case["case_id"] in {"unresolved_referent", "material_dual_meaning"}
        or not pack["t4_call_permitted"],
        "hypotheses_preserved": hypotheses_ok,
        "clarification_correct": clarification_ok,
        "semantic_strength_preserved": not strengthening_failure,
        "no_invented_observed_facts": invented == [],
        "invented_facts": invented,
        "no_authority_widening": not widening,
        "clarification_post": clarification_post,
        "t4_invoked": bool(trace.get("invoked")),
        "accepted": bool(trace.get("accepted")),
        "rejected_reasons": list(trace.get("rejected_reasons") or []),
        "forbidden_hit": forbidden_hit,
    }


def emit_case_prompts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in CASES:
        pack = _prompt_pack(case)
        pack.pop("_base_contract", None)
        pack["raw_proposal"] = None
        pack["live_scores"] = None
        pack["pass_gate"] = dict(PASS_GATE)
        rows.append(pack)
    return rows


def build_report(*, mode: str) -> dict[str, Any]:
    if mode != "emit-prompts":
        raise ValueError("this pack is emit-prompts only; do not call Cisco on this VPS")
    previous = bool(settings.ai_soc_t4_semantic_understanding_enabled)
    settings.ai_soc_t4_semantic_understanding_enabled = True
    try:
        cases = emit_case_prompts()
        injected = [score_injected_case(case) for case in CASES]
    finally:
        settings.ai_soc_t4_semantic_understanding_enabled = previous
    for row, score in zip(cases, injected, strict=True):
        row["injected_scores"] = score
    return {
        "pack": "t4_unseen_qualification",
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "frozen_proposal_fields": list(FROZEN_SEMANTIC_T4_PROPOSAL_FIELDS),
        "invariants": {
            "reuses_production_t4": True,
            "prompt_builder": "app.chat.semantic_t4_understanding._build_semantic_t4_user_prompt",
            "schema": "app.chat.contracts.semantic_t4_proposal.SemanticT4Proposal",
            "merge": "app.chat.semantic_t4_understanding._merge_proposal",
            "t4_cannot_grant_route_capability_or_tool_authority": True,
            "no_live_cisco": True,
            "no_case_specific_few_shots": True,
            "no_keyword_routing": True,
        },
        "pass_gate": dict(PASS_GATE),
        "case_record_fields": list(CASE_RECORD_FIELDS),
        "cases": cases,
        "injected_contract_scores": injected,
    }


def assert_output_contract(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("mode") != "emit-prompts":
        errors.append("mode")
    if report.get("pack") != "t4_unseen_qualification":
        errors.append("pack")
    cases = report.get("cases") or []
    if len(cases) != 9:
        errors.append("case_count")
    ids = [row.get("case_id") for row in cases]
    expected_ids = [case["case_id"] for case in CASES]
    if ids != expected_ids:
        errors.append("case_ids")
    for row in cases:
        for field in CASE_RECORD_FIELDS:
            if field not in row:
                errors.append(f"missing:{field}:{row.get('case_id')}")
        prompt = row.get("exact_t4_prompt") or {}
        if prompt.get("system") != _SEMANTIC_T4_SYSTEM_PROMPT:
            errors.append(f"system_prompt:{row.get('case_id')}")
        if row.get("raw_proposal") is not None:
            errors.append(f"raw_proposal_not_null:{row.get('case_id')}")
    if report.get("invariants", {}).get("no_live_cisco") is not True:
        errors.append("no_live_cisco")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-prompts", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_EMIT_DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.live:
        print("refused: unseen qualification pack must not call Cisco on this VPS", file=sys.stderr)
        return 2
    if not args.emit_prompts:
        parser.error("use --emit-prompts (this pack does not call the model)")
    report = build_report(mode="emit-prompts")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    errors = assert_output_contract(report) if args.check else []
    if errors:
        print("contract check failed:", ", ".join(errors), file=sys.stderr)
        return 1
    print(json.dumps({"out": str(args.out), "cases": len(report["cases"]), "mode": "emit-prompts"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
