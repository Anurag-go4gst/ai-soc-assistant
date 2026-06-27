# AGENTS.md

Guidance for coding agents working in this repository.

**Audience:** Cursor, Codex, Claude Code, and any other coding agent — treat this file as **canonical**. [`CLAUDE.md`](CLAUDE.md) adds Claude-specific entry context and links here; do not maintain conflicting rules in two places.

## Agent Execution Playbook

Cross-cutting rules learned from review cycles. These apply to **every** task, not only the current plan.

### Before writing code

1. **Read the repo, not just the plan.** Grep for existing loaders, tests, flags, and seam functions. Plans go stale; the tree is authoritative for what exists.
2. **Trace the full path you are changing.** For routing/intent work: `query → understand_query → build_query_to_intent → plan_evidence → route_adjudication → finalize`. Fixing one layer (e.g. `candidate_mappings` only) while leaving `intent_classification` or `evidence_plan` unchanged often produces **cosmetic** improvements with no analyst-visible effect.
3. **Identify downstream consumers.** Example: `planning_decision` trace metadata alone does not change live answers if `route_adjudication` reads `evidence_plan` instead.
4. **Prefer extend over recreate.** Add assertions to existing tests and entries to existing JSON maps; avoid parallel modules that drift.
5. **Scope one objective per change set.** Do not mix control-plane logic, connector readiness, UI polish, eval baseline refresh, and deployment in one commit unless explicitly asked.

### During implementation

6. **Preserve governance defaults.** MCP execution off, candidate SPL non-executable, LLM advisory-only, deterministic wins on conflict — unless the user explicitly approves a stage boundary change.
7. **Fail closed on ambiguity.** Missing slots, unverified registry rows, and off-scope queries → clarification or honest degrade — not fabricated indexes, SPL, or live MCP rows.
8. **Match existing conventions.** Read surrounding modules for naming, import style, Pydantic patterns, and test layout before adding helpers.
9. **No inline imports** unless a documented circular-dependency exception exists (see workspace rules).
10. **Security-sensitive writes need auth, validation, redaction, and limits.** Settings APIs, import/export, CSV upload, asset registry — enforce session/admin guards, size caps, formula-injection protection, and audit fields; never add public unauthenticated write endpoints.
11. **Authority precedence must be explicit.** When merging config (source profiles, slots, registry hints): COE/manual values win; RAG/session/MCP may **fill blanks only**, not override operator-configured security-sensitive fields.

### Validation (do not skip)

12. **Run targeted tests for every touched package**, then the relevant gate:
    - Control plane / intent: `pytest` on affected tests + `scripts/eval_out_of_set_intent_probe.py --check` when intent changes
    - Broad backend: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest`
    - Governance: `./scripts/run_stage3_governance_regression.sh` before claiming control-plane work done
    - Frontend: `cd frontend && npm run build` for any UI change; prod serves `frontend/dist` via Nginx (`postbuild` chmods `dist` so `www-data` can read — without it Nginx returns 403)
13. **Probe with novel queries**, not only in-catalog golden rows. In-set 105/120 passing can hide out-of-registry clarification dumps.
14. **Do not commit accidental eval baseline drift** (`soc_clean_answer_eval_*`, `langgraph_dual_parity_*`, etc.) unless the task was explicitly to refresh baselines.
15. **Report what you verified** (commands run, pass/fail counts). "Should work" is not verification.

### Review and handoff

16. **State repo-vs-plan deltas.** If the plan says "wire loader" but loader exists, say so and narrow remaining work — do not re-implement.
17. **Call out deferrals explicitly.** Trace-only wiring, COE-gated flags, and mock-only paths are not the same as production behavior.
18. **List known gaps** left for a follow-up PR instead of silently shipping partial behavior.
19. **Do not mark todos complete** in plan frontmatter unless the acceptance criteria in the plan (or addendum) are met and tested.

### Common agent mistakes (avoid)

| Mistake | Why it hurts | Do instead |
|---------|--------------|------------|
| Updating `candidate_mappings` but not `intent_classification` after promotion | Evidence plan and route stay on old family | Reconcile intent after promotion; test end-to-end |
| Treating `requires_hil=true` as unsafe veto for all advisory paths | Blocks Engine-3 rescue on guided floor | Veto only `primary_intent == human_review` (unsafe/run-SPL) |
| Letting `explicit_search_intent` fire before non-SOC guards | HR/policy queries draft SPL | Early `non_soc_or_out_of_scope` exit |
| Trace-only completeness floor | Planner trace says hybrid; answer stays rag-only | Wire floor into `plan_evidence` / honor in adjudication |
| Blanket Tier-2 SPL capabilities on all templates | Expands attack surface | Per-template `validation_rules`; test unused caps stay off |
| MCP discovery overriding COE slots | Wrong index/sourcetype in production SPL | COE/manual wins; MCP fills missing only |
| Metadata hygiene returning hunt SPL or fake live rows | Misleading analyst card | `planned` / `configured_unavailable` / live sanitized only when enabled |
| "Implement the plan" without reading code | Duplicates completed work | Grep + extend existing tests first |
| One giant commit mixing concerns | Hard review, easy regressions | Stage-scoped commits per Commit Hygiene below |
| Passing only in-set evals | Misses 29/50-style classification dumps | Use out-of-set probe harness + novel phrasing |
| `npm run build` without readable `dist` perms | Nginx 403 on cisco-vai.vnudge.com | Rely on `postbuild` in `frontend/package.json`; manual fix: `chmod -R a+rX frontend/dist` |

### Good prompts for the user to give agents

**Effective:**

- "Implement Batch 1 PR #1 from `plans/…` addendum §D only. Grep for existing Cisco loader first. Run governance regression + probe eval before done."
- "Fix the bug where X; add a regression test; do not change unrelated routing."
- "Review my implementation against AGENTS.md playbook items 1–3 and report gaps."

**Weak (agent will under-deliver or over-scoped):**

- "Implement the Cisco plan." (too broad; plan may be stale)
- "Make intent work better." (no acceptance criteria)
- "Fix everything in the review." (no priority or test gate)
- "Commit and push." (without specifying scope or excluding baseline noise)

### Documentation map

| File | Purpose |
|------|---------|
| [`AGENTS.md`](AGENTS.md) | **This file** — rules, safety, playbook, verification |
| [`hooks.md`](hooks.md) | Cursor hooks + optional Git pre-commit |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code entry — stack, gotchas, plan index (links here for rules) |
| [`plans/README.md`](plans/README.md) | Active work pointers |
| [`plans/`](plans/) | Versioned implementation specs |
| `.cursor/plans/` | Cursor-local plans — may be ahead of git; reconcile into `plans/` for shared truth |

## Active work (pointers)

- **Intent cascade:** Done — [`plans/2026-06-17_1730_intent-node-cascade-hardening.md`](plans/2026-06-17_1730_intent-node-cascade-hardening.md). Harness: `test_cisco_intent_distribution.py`, `scripts/eval_out_of_set_intent_probe.py`.
- **Cisco Environment KB + 50-Q catalogue:** Next — full spec in `.cursor/plans/environment_kb_cisco_catalogue_1eddd12f.plan.md`; read **Review Addendum §A–D** before Batch 1 (repo-state, phased eval gates, security). Loader/map largely exist — extend, do not recreate.
- **Master roadmap:** [`plans/AI_SOC_MASTER_PLAN.md`](plans/AI_SOC_MASTER_PLAN.md).

## Operating Rules

- Read the local code before changing behavior. Preserve the existing FastAPI + React/Vite structure.
- Keep changes stage-scoped. Do not mix workflow planning, connector readiness, execution, UI polish, and deployment edits in one commit unless explicitly requested.
- Do not commit secrets or `.env`.
- Do not expose Docker service ports publicly. Production-style access is via Nginx at `https://cisco-vai.vnudge.com`.
- Treat `.claude/` as local tool state unless the user explicitly asks to version it.

## Safety Boundaries

Current implementation is governed candidate generation and gated execution control:

- `/chat` returns routing results and a `workflow_plan`.
- Workflow steps stay `not_started`.
- Workflow `execution_enabled` stays `false`.
- Candidate SPL is generated through governed templates, lab draft preview, Stage 3C stub (legacy), or flag-gated LLM failover (`AI_SOC_LLM_SPL_FALLBACK_ENABLED`); all paths are candidate-only.
- SPL validation is deterministic; rejected SPL and lab-tier LLM SPL must have `normalized_spl=null`. Lab-tier exposure (`validate_spl_lab_candidate`) may show placeholder SPL to analysts with `spl_validation.approved=false`.
- `candidate_spl` must never be executed.
- Only `spl_validation.approved=true` and non-null `normalized_spl` may reach the MCP execution gate. `graph_node_spl_source_resolve` substitutes placeholders from config/RAG/session before re-validation.
- Structural SPL relevance gate (`app/spl/spl_relevance_check.py`) runs on non-template candidates; LLM failover retry defaults off (`AI_SOC_LLM_SPL_FAILOVER_RETRY_ENABLED=false`).
- MCP tool discovery, deterministic tool selection, human review, and mock gated execution are Stage 3D control-layer behavior.
- MCP execution defaults disabled globally and per server.
- Mock MCP execution is allowed only when explicitly enabled through `MCP_GLOBAL_EXECUTION_ENABLED=true` and `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`.
- Real Splunk MCP search adapter is implemented (`splunk_mcp.py`, async lifecycle). Live execution stays **default-off** until operator sets URL/token + execution flags per `CLAUDE.md` §Splunk MCP go-live.
- Governed RAG retrieval is wired: SOC KB results flow only through `SourceEvidence` and `StructuredContext`. There is no direct RAG-to-LLM path.
- The Context Sufficiency Gate (Stage 3J) classifies the evidence package into one answer mode and computes `synthesis_readiness`. `synthesis_allowed` stays `false`.
- No final LLM synthesis runs. `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` and `AI_SOC_LLM_ANSWER_GUARD_ENABLED` are inert config flags (Stage 3J-B), default false. Answer Guard execution stays disabled.
- The governed LLM layer (Stage 3J-B) is configuration/status/UI only and never calls a real LLM. `/settings/llm/check` validates drafts without persisting; secrets are never echoed.
- Intent hygiene (Stage 3J-C): SOP/playbook and MITRE prompts route to `knowledge_recall` (no SPL). A MITRE ask without alert context returns an `intent_clarification` human-review rather than generating SPL. The chat UI is analyst-first with the technical trace collapsed by default.
- Guarded LLM adapter (Stage 3J-I): `app/llm/adapter/` extracts the first balanced JSON object, validates role schemas, and applies active authority overrides — it always forces SPL `execution_eligible=false` and forces deterministic clarification, severity, MITRE status, SOP citation, and allowed actions on conflict, recording `warnings`/`disagreements`. Dormant semantic guards in `app/answer_guard/rules.py` (13 `guard.*` ids) are unit-tested only. Neither the adapter nor the guard rules are imported by `/chat` or the demo path; they never run on a live answer.
- Experience Center calibration (Stage 3J-J): demo golden answers in `app/demo/scenarios.py` mirror governed Foundation-sec behavior (valid template SPL, per-source distinct-user labels, explicit MITRE `Status`, P1–P4 priorities, no execution eligibility) and carry a collapsed investigation-lineage reveal. Answers stay deterministic `coe_synthetic_fixture`, not live-model output.
- Experience Center ↔ production parity (2026-06-15): EC mirrors the real `/chat` pipeline. EC SPL is sourced from the governed template registry via `_scoped_template_spl()` (no hardcoded SPL; edit `templates.json` and EC follows); success-after-failure is P2. EC surfaces the production LLM sidecars — `control_plane_trace.{mitre_risk_rationale,resource_plan_shadow}` + `llm_sidecars` + governance `llm_sidecar_panel` — built from real deterministic rationale, posture kept (`live_llm_called=false`, advisory, deterministic wins). Lineage/evidence/governance sections render from the shared builders, same as live. Scenarios: added `dns_beaconing_c2_hunt` (+`_run` mock MCP hop) and `guided_investigation_supply_chain` (out-of-catalog 5th-skill hunt); removed redundant `failed_login_playbook`. Demo progress UX (`investigationProgress.ts`, `InvestigationProgressPanel.tsx`): realistic MCP handshake (submit→poll→fetch with job sid), per-step jitter, live elapsed ticker to mask real latency. Prod frontend = Nginx serving `frontend/dist`; run `npm run build` in `frontend/` to publish UI changes (docker `frontend` is Vite dev only).
- LLM-assisted routing governance (Stage 3J-K0): routing modes `deterministic_only`, `llm_shadow_only`, `llm_assisted_semantic`, `llm_primary_lab`. LLM route suggestions are advisory, normalized through deterministic registries and clarification policy; final route selection stays deterministic. Evidence-need→MCP-tool mapping is a deterministic record only. The SPL optimizer field `execution_eligible` is renamed `revalidation_approved`; candidate SPL stays non-executable.
- The live `SKILL_ENUM` has five routes: `alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall`, and `guided_investigation`. The guided route applies only to out-of-registry SOC-investigation-shaped questions; it returns review-only hypotheses and evidence guidance, requires analyst validation, and never authorizes SPL or MCP execution.
- Splunk telemetry writes are disabled.
- LLMs must never call MCP directly.

Any change that violates these boundaries needs explicit user approval and a later-stage requirement.

## MCP / LLM Architecture

- MCP is a generic multi-server registry.
- Splunk MCP is one server type and the first target, not the entire MCP framework.
- Each MCP server has independent configured/available/implemented/error status.
- Global and per-server MCP execution flags must default false.
- MCP tool discovery must expose only redacted/safe tool metadata.
- Tool selection is deterministic. User-requested MCP server/tool values are preferences only, not authority.
- Search tools may be selectable only for `spl_search` after policy checks.
- SAIA/generative/assistant/write/admin tools must be discoverable in status but blocked.

- LLM is a provider/model registry.
- Cisco/Foundation-Sec is one model family, not the only option.
- Foundation-Sec instruct and reasoning roles should be separate configurable providers/models.
- Open-weight/local models should remain configurable through provider types such as `openai_compatible`, `ollama`, `vllm`, `sglang`, `tgi`, `llamacpp`, and `custom_http`.
- Provider fallback must be explicit, not silent.
- `supports_tool_calling` must remain false in this stage.
- `LLM_TOOL_RECOMMENDATION_ENABLED` defaults false. If enabled later, recommendations are advisory only and cannot override deterministic policy, validation, or execution flags.

## Verification

Canonical governance regression:

```bash
./scripts/run_stage3_governance_regression.sh
```

Baseline: [`docs/evals/regression_baseline.md`](docs/evals/regression_baseline.md).

For backend work only:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest
```

For frontend or shared type changes:

```bash
cd frontend
npm run build   # postbuild: chmod -R a+rX dist (Nginx www-data readability)
```

For harness independence:

```bash
PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
```

Expected baseline:

- Governance regression script PASS (0 failed pytest, harness 6/6).
- Frontend build passes.

## Commit Hygiene

Preferred grouping:

1. Workflow planning changes.
2. MCP/LLM readiness changes.
3. Documentation-only changes.

Recent stage commits:

- `911eed6` Fix SPL routing relevance bugs (Phase B)
- `ad29958` Wire LLM-primary SPL failover and relevance gate (Phase C)
- `35b42b0` Single SPL surface and ambiguous-route disambiguation (Phase C.2)
- `1b86da2` / `22cbbc3` Close catalogue SPL coverage (Phases D / D.2)
- `8f44eee` Complete SPL audit phases G/E/F/H (lab-tier exposure, simplifier, template audit, source resolve)
