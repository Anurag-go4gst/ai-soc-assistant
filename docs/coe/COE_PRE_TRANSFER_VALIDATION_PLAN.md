# COE Pre-Transfer Validation Plan

Generated: 2026-06-25

This plan validates the code before transfer to the COE environment where MCP will be available. In the current repo environment, MCP is expected to remain unavailable or disabled; passing behavior is honest review-only planning, not live execution.

## Gate 1 - Known and Catalogue Questions

Run the existing catalogue, clean-answer, and out-of-set probes. Passing means known/catalogue questions return useful governed answers, catalogue-adjacent questions route to the correct skill family, and out-of-catalogue questions degrade according to request shape:

- Live data retrieval -> review-only SPL / source-profile clarification.
- Procedural investigation -> guided review-only investigation.
- Unclear question -> bounded clarification.

Required checks:

- `./scripts/run_stage3_governance_regression.sh`
- `PYTHONPATH=backend:. python3 scripts/run_cisco_powergrid_question_eval.py --check`
- `PYTHONPATH=backend:. python3 scripts/eval_out_of_set_intent_probe.py --check`

## Gate 2 - Resource Planning

For every COE probe question, inspect `control_plane_trace`, `planning_decision.resource_plan_summary`, and `evidence_plan.resource_plan.provenance.resource_decisions` when available.

Pass criteria:

- RAG, SPL, MCP, MITRE, CVE, GitHub, and LLM roles are marked used, skipped, or unavailable with a reason.
- MCP is planned or unavailable, never silently treated as live in this repo.
- For live-data requests, distinguish "MCP needed for live answer" from "MCP allowed/executed".
- COE/manual/source-profile authority is not overridden by RAG, MCP, or LLM hints.
- `resource_plan_shadow` is present when the sidecar is configured; deterministic planning remains authoritative.

## Gate 3 - T2 Review-Only SPL Renderer

Use `docs/evals/coe_india_powergrid_probe_25_bank.json`, especially `coe_in_pg_005` and `coe_in_pg_006`.

Pass criteria:

- `analyst_response.direct_answer_summary` is a short summary only.
- Draft SPL appears only in the SPL/draft section fields, not duplicated inside the summary.
- Limitations and review package text appear in their owned sections, not repeatedly in the summary.
- `candidate_spl`, `spl_validation`, and `run_contract` continue to show execution disabled unless COE explicitly enables MCP execution.

## Gate 3A - Final Renderer Section Ownership

For review-only SPL answers, validate that exactly one renderer owns each visible section.

Required section ownership:

- Title / direct answer: `direct_answer_summary` only.
- Review-only warning: `limitations` or `review_notice` only.
- SOC checklist: `analyst_action_guidance` or checklist section only.
- Draft SPL: `draft_spl` / `candidate_spl` section only.
- Assumptions/placeholders: assumptions section only.
- Production/debug trace: debug/provenance section only.

Pass criteria:

- `direct_answer_summary` must not contain draft SPL.
- `direct_answer_summary` must not contain the full checklist.
- `direct_answer_summary` must not contain repeated limitations.
- Draft SPL must appear only once.
- SOC checklist must appear only once.
- Review-only / lab-only warning must appear only once.
- Investigation plan must not duplicate analyst workflow.
- P1/P2/P3 prefixes must not appear unless incident severity is actually assigned.
- "live-backed" must appear only when `execution_status=executed` and `collected_evidence_count > 0`.
- For `execution_status=skipped`, provenance label must be "review-only / no live execution".

Renderer regression probe:

`Show me all external connections or remote access sessions currently mapping to the substation networks.`

Required visible-answer assertions:

- Contains "Review-only SPL draft - no live query was executed".
- Contains severity as "Not assigned from this question alone".
- Contains one SOC review checklist only.
- Contains one draft SPL block only.
- Contains one assumptions/placeholders section only.
- Does not contain duplicate "SOC review checklist".
- Does not contain duplicate "Lab-only draft SPL preview".
- Does not contain both "Investigation steps" and "Investigation plan" if they repeat the same checklist.
- Does not contain "P2Confirm" or any P2-prefixed checklist item.
- Does not contain "live-backed".
- Does contain "review-only / no live execution".
- Does not contain `splunk_results_table`.

## Gate 4 - Telemetry and Debuggability

For each probe turn, record trace id and verify the debug view or telemetry connector contains:

- Admission record and terminal run status.
- Node timings for routing, intent, evidence planning, SPL, source resolve, execution, and finalization.
- LLM call ledger entries with role, provider label, outcome, latency, and fallback status.
- `control_plane_trace`, `llm_sidecars`, `narration_visibility`, `answer_scorecard`, and `final_answer_validation`.
- MCP status as planned, skipped, unavailable, blocked, mock, or live; no ambiguous blank state.
- `run_contract` with `canonical_skill`, `legacy_skill`, `legacy_authoritative`, `authority_holder`, `execution_status`, `collected_evidence_count`, `source_evidence_available`, `allow_live_result_language`, `allow_results_table`, and `effective_hil_required`.

## Gate 5 - Final Answer Quality

Score each answer against the analyst contract:

- Useful first answer: directly addresses the question.
- Honest grounding: no live rows, no execution, no confirmed compromise, no confirmed MITRE, and no severity claim unless evidence supports it.
- Operational next step: gives analyst checklist or review-only SPL where appropriate.
- Clear limitations: missing evidence is stated in analyst language.
- No renderer duplication: no repeated review summary, draft SPL guidance, analyst workflow, investigation plan, and trace prose in one visible blob.

## Gate 6 - Skill Efficiency

The 25-question bank intentionally exercises skill use:

- CVE: `coe_in_pg_015`, `coe_in_pg_016`
- MITRE: `coe_in_pg_004`, `coe_in_pg_013`, `coe_in_pg_014`, `coe_in_pg_018`
- GitHub: `coe_in_pg_017`, `coe_in_pg_018`
- OT guided investigation: `coe_in_pg_007` to `coe_in_pg_012`, `coe_in_pg_019` to `coe_in_pg_025`
- Known/catalogue: `coe_in_pg_001` to `coe_in_pg_004`

Pass criteria: skills contribute evidence requirements, checklists, or status labels only when relevant. They must not leak implementation references, GitHub skill-source text, or ungrounded claims into the final answer.

## Gate 7 - LLM Use Without Closed-System Behavior

Enable LLM sidecars in the intended lab configuration and rerun the bank. Passing behavior:

- LLM calls appear in telemetry with role-level outcomes.
- Novel questions receive substantive guided reasoning rather than only known-question answers.
- LLM output does not override deterministic route, severity, MITRE status, SPL approval, source profile, or MCP execution gates.
- LLM-generated prose is passed through the same section-ownership and no-duplicate renderer rules as deterministic prose.
- On timeout or guard block, deterministic answer remains complete and safe.

## COE Transfer Stop Conditions

Do not transfer as "ready" if any of these occur:

- `candidate_spl` or `draft_spl_code` is represented as executed.
- MCP unavailable is hidden from the answer or trace.
- T2 review-only answers duplicate SPL and workflow content in `direct_answer_summary`.
- MITRE is confirmed without collected source evidence.
- Severity is assigned for out-of-catalogue guided hunts without policy-backed evidence.
- Resource planner does not explain why MCP, RAG, SPL, LLM, CVE, MITRE, or GitHub were used or skipped.
- Visible answer repeats the same checklist, SPL warning, or draft SPL block more than once.
- "How this answer was produced" says live-backed when `execution_status != executed`.
- P1/P2/P3 prefixes appear in checklist items when severity is not assigned.
- `run_contract` is missing from any live `/chat` turn.
- Displayed route authority contradicts `run_contract.routing.authority_holder`.
