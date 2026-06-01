# Plan — Query→Answer Readiness for Live MCP + LLM

Status: Proposed
Date: 2026-05-30
Author: COE review (Anurag + Claude)

## Context

COE review of the live `/chat` pipeline (not the demo path). Goal: make the system
produce a **grounded final answer** when MCP (Splunk) and the LLM go live — safely,
auditable, reviewable.

Today the pipeline is **evidence-complete but answer-incomplete**:

- `routes_chat.py:chat()` routes → plans → generates+validates candidate SPL →
  `evaluate_mcp_execution` → `_context_stage` (RAG → SourceEvidence → StructuredContext →
  sufficiency) → severity/MITRE/lineage → response.
- `mcp_execution_gate.py:72` **already calls** `get_mcp_connector().call_tool()` and threads
  results into evidence. The block is only `:164 registry.mode != "mock"` and `:77 NotImplementedError`.
- `routes_chat.py:114` hard-sets `SynthesisStatus(enabled=False)`; `synthesis_allowed=False`
  everywhere. So **no answer sentence is ever composed** — user gets rows + status + `human_review`.

Two walls block a real answer: **(1)** no real MCP adapter, **(2)** synthesis disabled.
Plus COE risks: prompt-injection via Splunk result fields, empty-result misclassification,
SPL coverage ceiling, cost/time-window controls, per-run approval, audit reproducibility.

This crosses the current CLAUDE.md stage boundary ("do not add final LLM synthesis / answer
guard / real LLM calls unless a later stage explicitly asks"). This plan **is** that staged
ask — each live-enabling phase stays behind an explicit flag and needs sign-off before merge.

---

## Phases (ordered by dependency + risk)

### Phase A — Pre-live hardening (no live deps; do first)

**A1. Empty-result correctness.**
Problem: `context_sufficiency.py:109` Rule 4 `if not collected → INSUFFICIENT_EVIDENCE`. A query
that *ran and returned 0 rows* is a valid negative answer ("no failed logins"), not insufficient
evidence. Must distinguish *query-didn't-run* from *query-ran-empty*.
- Verify `build_source_evidence` (`app/evidence/source_evidence.py`) marks executed-but-empty
  execution with `collection_status="collected"` and a `result_count=0` marker.
- Add sufficiency branch: collected execution evidence with 0 rows → `FULL_ANSWER`/`PARTIAL_ANSWER`
  carrying a `negative_result` reason, never `INSUFFICIENT_EVIDENCE`.
- Files: `app/evidence/source_evidence.py`, `app/evidence/context_sufficiency.py`.

**A2. Results→evidence injection defense (security-critical, pre-req for any synthesis).**
Real Splunk events carry attacker-controlled fields (`cmdline`, `url`, `user_agent`, `process`).
Today `data_minimizer` + `prompt_injection_filter` guard *user input*; they must also run on the
**MCP-results→evidence** path before any text can reach an LLM.
- Apply `app/safeguards/data_minimizer.py` + `app/safeguards/prompt_injection_filter.py` inside
  `splunk_result_adapter.adapt_mcp_search_payload` (or `build_source_evidence` ingest of execution).
- Result preview rows that fail the filter → `sensitivity_flags` set → sufficiency Rule 1
  (`:81`) already converts to `BLOCKED_BY_POLICY`. Confirm that path fires.
- Files: `app/connectors/mcp/splunk_result_adapter.py`, `app/evidence/source_evidence.py`.

**A3. Audit lineage hooks.**
Lineage already captures `executed_spl` + envelope + `route_plan_shadow`. Add placeholders for
LLM raw output + adapter overrides so Phase C/D fills them (reproducibility for SOC audit).
- Files: `app/lineage/builder.py`.

### Phase B — Real MCP adapter (Wall 1)

**B1. COE connection contract (gate; blocks B2).** Collect from COE before code:
server URL, transport, auth method, discovered tool names, **exact arg schema**, approval workflow.
Deliverable: a filled contract doc under `contracts/`.

**B2. Implement real `call_tool`.**
Gate passes `{"query": normalized_spl}` only — real Splunk MCP likely needs
`earliest`/`latest`/`output_mode`. Map validated SPL + time window into the real arg schema.
- `app/connectors/mcp/splunk_mcp.py` (real transport), `registry.py` (`mode=registry/live` path).
- Reuse `app/connectors/mcp/live_schema_capture.py` (discovery) + `discovery.py`.
- `mcp_execution_gate.py:164` real-mode branch flips from block → execute once adapter exists.

**B3. Cost + allowlist safety.**
- Enforce bounded `earliest/latest` (never silent all-time) + `SPL_MAX_RESULT_LIMIT` at
  `spl_validator.py` *before* execution.
- Align `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES` with the live Splunk deployment, else
  every real query rejects at validation. Files: `app/safeguards/spl_validator.py`, `.env`.

**B4. Per-run approval workflow.**
`_gate_review` already requires `soc_lead` approval. Define who approves + SLA + UI surface so live
queries don't stall. Files: gate review reasons + frontend HIL panel.

### Phase C — Synthesis stage (Wall 2; flag-gated, needs sign-off)

**C1. Wire the existing scaffold.** `synthesis/models.py:build_governed_synthesis_package` already
builds a governed package (precomputed aggregates, missing-evidence wording, permitted MITRE,
permitted actions, `SynthesisGuardConstraints`) but is **never called**. Wire it into `chat()`
after `_context_stage`.

**C2. Build synthesis stage.** Reads `GovernedSynthesisPackage` **only** (never raw events).
Runs only when `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` **and** sufficiency mode in
`_READY_MODES` (`full_answer`/`partial_answer`/`knowledge_only_answer`). Honors guard constraints
(no global aggregates, no absence-inference, MITRE from permitted set only, max action tier 1).

**C3. Answer guard.** `app/answer_guard/rules.py` (13 dormant `guard.*` ids) validates the generated
answer before return; gated by `AI_SOC_LLM_ANSWER_GUARD_ENABLED`. Reuse `app/llm/adapter/` for
schema + authority overrides.

**C4. Flags = kill switches.** Both flags default false. `AI_SOC_LLM_MODE=disabled` forces off;
air-gap overrides cloud allowance (existing governance).

### Phase D — Route-suggestion LLM exercise (testable now, lowest risk)

Validate routing governance with a user-supplied LLM route-plan JSON, no live model needed.
- Inject via `generate_llm_route_plan_candidate` (`app/routing/llm_route_plan_candidate.py`) test hook
  or `_route_plan_shadow_candidate` (`routes_chat.py:367`, currently returns None).
- Confirm: `validate_route_plan_candidate` normalizes → `deterministic_route_plan_wins=True` →
  `disagreements` recorded → deterministic skill still reaches user. Shadow only; no execution.

---

## Scope guardrails (per CLAUDE.md)

- One commit per concern; do not combine execution changes with connector-readiness or UI-only changes.
- Candidate SPL stays non-executable; only approved `normalized_spl` enters the gate.
- LLM never calls MCP directly; backend mediates.
- All MCP/LLM status output redacts secrets (`url_configured`/`auth_configured` booleans only).
- Phases C/D stay flag-gated and default-off until explicit sign-off.

## Verification (end-to-end)

- Governance regression: `./scripts/run_stage3_governance_regression.sh` → PASS, harness 6/6.
- Backend: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`.
- Frontend: `cd frontend && npm run build`.
- Per phase: A1 — unit test 0-row execution → `full_answer`+`negative_result`, not insufficient.
  A2 — feed event with injection string → `sensitivity_flags` → `BLOCKED_BY_POLICY`.
  B2 — mock real transport, assert arg schema mapping + executed envelope.
  C2/C3 — flag off = no synthesis (current behavior preserved); flag on in lab = guarded answer only.
  D — supplied route-plan JSON → deterministic wins + disagreement logged in trace.

## Plan housekeeping

- `plan-reviewer` subagent before executing any non-trivial phase; `validator` after each phase.
- Mirror of this plan also at `~/.claude/plans/purring-swinging-sunrise.md`.
