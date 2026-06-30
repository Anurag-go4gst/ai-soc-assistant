# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Agent instructions (read first)

**Canonical rules for all coding agents:** [`AGENTS.md`](AGENTS.md)

Claude Code must follow `AGENTS.md` in full — especially **Agent Execution Playbook** (repo-first research, end-to-end tracing, **plan discipline**, validation gates, common mistakes, and prompt patterns). This file adds project context, stack, gotchas, and plan index; it does not override safety boundaries or operating rules in `AGENTS.md`.

**Active work:** see [`plans/README.md`](plans/README.md) and the **Active work** section in `AGENTS.md`.

## Plan discipline (all agents)

Canonical rules: [`AGENTS.md` § Plan discipline](AGENTS.md#plan-discipline-authoring-and-execution). Applies when **creating** or **executing** any plan under `plans/`.

1. **Decompose** prose into atomic checklist items with **Do / Verify / Depends on / Evidence** — template: [`.cursor/templates/plan-checklist-template.md`](.cursor/templates/plan-checklist-template.md).
2. **Audit** before coding: `.cursor/hooks/audit-plan-discipline.sh plans/<file>.md` — fix every `GAP:`.
3. **Execute loop:** implement → verify → check off with evidence → next item; stop on decision-needed, gate fails twice, or all items done.
4. **Re-audit** all checkmarks before declaring the plan complete.

**To start execution**, user says: `loop-asap — execute plans/<file>.md` (or use [`plans/LOOP_RUNNER_TEMPLATE.md`](plans/LOOP_RUNNER_TEMPLATE.md)).

**Cursor-only automation:** [`.cursor/rules/plan-discipline.mdc`](.cursor/rules/plan-discipline.mdc) + hooks in [`hooks.md`](hooks.md) (`loop-asap` follow-up, plan-edit reminders). Claude Code follows the same discipline manually from `AGENTS.md`.

**Post-code verification (Cursor):** type **`test this`** in the prompt to arm verify + deploy handoff ([`hooks.md`](hooks.md)).

## Project

AI SOC Assistant — internal experience-center scaffold for an AI-augmented SOC dashboard. FastAPI backend + React/TypeScript frontend + Postgres. The app currently supports skill routing, workflow planning, candidate SPL generation, deterministic SPL validation, MCP discovery/tool selection, human-in-the-loop gates, optional explicitly-enabled mock MCP execution, a generic multi-MCP readiness registry, a multi-LLM provider/model readiness registry, governed SOC-KB RAG retrieval into `SourceEvidence`/`StructuredContext`, a Context Sufficiency Gate (Stage 3J), a governed LLM configuration/status layer (Stage 3J-B), telemetry/status surfaces, and deterministic safeguards. Production access goes through Nginx at `https://cisco-vai.vnudge.com`; Docker service ports are bound to `127.0.0.1` and must never be exposed publicly.

## Stack

- Backend: Python 3.12, FastAPI, Uvicorn, SQLAlchemy, pytest
- Frontend: React 18 + TypeScript, Vite, Tailwind CSS, Radix UI, lucide-react, shadcn-style local primitives
- DB: PostgreSQL 16 (pgvector-capable)
- Orchestration: Docker Compose (primary dev path)

## Current Stage Boundaries

- `/chat` performs routing, returns a `workflow_plan`, can generate candidate SPL for eligible skills, validates SPL deterministically, evaluates MCP tool selection/execution gates, and returns `human_review` when execution cannot safely proceed.
- Workflow steps are `not_started` and `execution_enabled=false`.
- Candidate SPL is never executable. Only an approved validation result with non-null `normalized_spl` may enter the MCP execution gate.
- MCP is a generic multi-server registry. Splunk MCP is the first target MCP server type, not the whole framework.
- MCP execution is disabled by default globally and per server. Mock execution requires both `MCP_GLOBAL_EXECUTION_ENABLED=true` and `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`.
- **Live Splunk MCP search is implemented** (`splunk_mcp.py` + `splunk_search_lifecycle.py`, Steps 0–3 on `spl-generation-audit`). Default posture stays off; activation is env + credentials only. Wire framing (`_StreamableHttpSearchTransport`) is verified at first connect — see **Splunk MCP go-live** below.
- Tool selection is deterministic; user-requested MCP server/tool values are preferences only. LLM recommendations are disabled by default and advisory only if later enabled.
- LLM is a provider/model registry. Cisco/Foundation-Sec is one family, not the only supported LLM option.
- Open-weight/local models are configured through provider types such as `openai_compatible`, `ollama`, `vllm`, `sglang`, `tgi`, `llamacpp`, and `custom_http`.
- The AI-SOC backend controls MCP access. The LLM must never call MCP directly.
- Governed SOC-KB RAG retrieval is wired (Stage 3G.1) and flows only through `SourceEvidence`/`StructuredContext`; there is no direct RAG-to-LLM path.
- The Context Sufficiency Gate (Stage 3J) classifies the evidence package into one of seven answer modes (`full_answer`, `partial_answer`, `analyst_review_required`, `spl_review_only`, `knowledge_only_answer`, `blocked_by_policy`, `insufficient_evidence`) and computes `synthesis_readiness`. `synthesis_allowed` stays `false`.
- The governed LLM layer (Stage 3J-B) is `AI_SOC_LLM_*` config + a `llm.governance` status block + the LLM Registry settings UI. It never calls a real LLM. `AI_SOC_LLM_MODE` is canonical (`disabled` forces off); air-gap enforcement overrides cloud allowance. `/settings/llm/check` validates drafts without persisting and never echoes secrets.
- `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` and `AI_SOC_LLM_ANSWER_GUARD_ENABLED` are inert flags (default false); no final synthesis runs and Answer Guard execution stays disabled.
- Intent hygiene (Stage 3J-C): SOP/playbook/runbook and MITRE prompts route to `knowledge_recall` (no SPL); a MITRE ask without alert context returns an `intent_clarification` human-review asking for the alert; success-after-failures prompts generate a failure+success correlation SPL, not a failed-spike-only query. The chat UI is analyst-first: an analyst summary card on top with the Stage 3D technical trace collapsed behind "Show technical trace".
- Guarded LLM adapter (Stage 3J-I): `app/llm/adapter/` extracts the first balanced JSON object, validates role-specific schemas, and applies active authority overrides (forces SPL `execution_eligible=false`, forces deterministic clarification/severity/MITRE-status/SOP-citation/allowed-actions on conflict, records `warnings`/`disagreements`). Dormant semantic guards live in `app/answer_guard/rules.py` (13 stable `guard.*` ids, unit-tested only). Adapter and guard rules are NOT imported by any `/chat` or demo response path; they never run on a live answer yet.
- Experience Center calibration (Stage 3J-J): demo golden answers in `app/demo/scenarios.py` are calibrated to governed Foundation-sec behavior — valid template SPL, per-source "Distinct users by source" (no summed global count), explicit MITRE `Status`, P1–P4 action priorities, `execution_eligible=false`. Each answer carries an investigation-lineage reveal ("How this answer was produced") collapsed by default in the chat UI. Answers are deterministic/`coe_synthetic_fixture`, not produced by a live model.
- Experience Center ↔ production parity (2026-06-15): EC must mirror the real `/chat` pipeline, not drift. EC SPL is sourced from the governed template registry via `_scoped_template_spl(template_id, host=)` (no hardcoded SPL); edit `templates.json` and EC follows. Success-after-failure is P2. EC surfaces the production LLM sidecar hops: `control_plane_trace.{mitre_risk_rationale,resource_plan_shadow}` + top-level `llm_sidecars` + governance `llm_sidecar_panel` (frontend "LLM sidecars (advisory)" panel), built from real deterministic rationale (`build_deterministic_severity_rationale` + the governed MITRE decision); EC posture kept (`live_llm_called=false`, advisory, deterministic wins). Sections (13-stage lineage "How this answer was produced", technical evidence path, governance panels) already render from the shared `build_investigation_lineage`/`build_control_plane_trace`/`build_governance_trace` builders, same as live. Scenario set: added `dns_beaconing_c2_hunt` + `dns_beaconing_c2_hunt_run` (mock MCP execution hop on a non-auth case) and `guided_investigation_supply_chain` (out-of-catalog 5th-skill hunt); removed redundant `failed_login_playbook`. Progress UX (`frontend/src/lib/investigationProgress.ts`, `InvestigationProgressPanel.tsx`): staged demo playback with a realistic MCP handshake (registry resolve → TLS/bearer → tools/list → submit job sid → poll 1/3..2/3 → DONE), per-step duration jitter, and a live elapsed ticker that masks real latency during the hold-until-resolved wait. Frontend is served in prod by Nginx from `frontend/dist` (cisco-vai.vnudge.com) — run `npm run build` in `frontend/` to publish UI changes; the docker `frontend` service is Vite dev only.
- LLM-assisted routing governance (Stage 3J-K0): routing modes `deterministic_only`, `llm_shadow_only`, `llm_assisted_semantic`, `llm_primary_lab`. LLM route suggestions are advisory only, normalized through deterministic registries and clarification policy; final route selection stays deterministic. Evidence-need→MCP-tool mapping is a deterministic record only (no execution). The SPL optimizer field `execution_eligible` is renamed `revalidation_approved`; candidate SPL remains non-executable.
- Five live router skills are available: `alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall`, and `guided_investigation`. `guided_investigation` is a deterministic rescue only for out-of-registry SOC hunt questions; it provides review-only guidance with an out-of-catalog notice and keeps MCP execution disabled.
- T2 / out-of-happy-path answer quality (2026-06, plan `plans/2026-06-19_1700_power-industry-query-to-solution-CONSOLIDATED.md`): three-layer fix on the out-of-catalogue path, all behind default-off T2 flags (`AI_SOC_T2_ANSWER_SHAPE_ENABLED` / `_ANSWER_SURFACING_ENABLED` / `_RAG_SURFACING_ENABLED`) with in-catalogue 105/50 byte-identical bypass. **WS-0 answer-shape router** (`app/chat/answer_shape_router.py`, deterministic, precedence: ir_containment_advisory > regulatory_knowledge > process_aware_ot > supply_chain_firmware_integrity > insider_dlp > timeline > ti_advisory > source_health > baselining > hunt) decides the answer template before any hunt template; only `hunt` falls through to **WS-1 signal-class generator** (`app/chat/signal_class_guidance.py`, entity-aware, OT-protocol terms). **WS-2/WS-7 surfacing** force the SPL artifact + populate envelope arrays from prose; RAG/playbook body on knowledge turns; entity-bound checklist + T1 headline. **WS-4 multi-leg** (`app/chat/multi_leg_evidence.py`) = deterministic 2+-domain legs + join key + causality warning (planning metadata only). Containment **decision-support** ("should we isolate/cut the link…") → staged `ir_containment_advisory`; genuine enforcement commands still refuse. The LLM is advisory/producer, never authority; shape selection is deterministic.
- T2 LLM SPL producer = **plan-plus-compiler** (`app/spl/llm_plan_compiler.py`): the LLM emits a small detection plan (compact `json_schema`, fixed `seed`), deterministic code compiles SOC-STD-compliant SPL (placeholders, time bound, coalesce stats, strftime-after-stats, sort, head 100), which flows through the existing validate/quality/adapter/lab-tier gates unchanged. Primary T2 producer in `graph_node_workflow_spl` (free-form fallback). Proven 10/10 lab-tier + seeded-repeatable on the on-host 8B; activates only when the LLM is enabled with a reachable endpoint. JSON robustness: `response_format=json_schema` (server honors it; `json_object` is ignored) + tolerant parser + decoupled SPL token floor `max(640, min(setting, 768))`. `scripts/llm_health_guard.py` restarts a degraded llama-server.
- T2 execution hardening (still default-OFF): unresolved placeholder slots (`<…>`) block execution (`spl_source_slots_unresolved`); live registry mode ALWAYS requires per-call analyst confirmation (`ai_soc_require_spl_execution_confirmation`, default true). Source-tier does not decide executability — guardrail-pass + full slot resolution + confirmation does. Probe quality gates: `scripts/run_power_industry_probe{,_v2,_v3}.py --check` (run as a non-gating observation in the governance regression). No-COE completion playbook for the remaining items is in §18 of the consolidated plan.
- SPL generation audit (2026-06-13, **Done**): relevance-first path — governed templates (10 active) → LLM-primary failover when `AI_SOC_LLM_SPL_FALLBACK_ENABLED=true` (default off) → lab draft last resort. R5 `spl_relevance_check` gate on all non-template candidates. Lab-tier LLM SPL (`validate_spl_lab_candidate`) exposes placeholder index/sourcetype for analyst review with `approved=false` and `normalized_spl=null`; MCP gate unchanged. `graph_node_spl_source_resolve` substitutes placeholders from `AI_SOC_SOURCE_PROFILE_MAP`, SOC-KB RAG, and session pins → `normalized_spl` when fully resolved; HIL `spl_source_profile_clarification` for missing slots. Post-validation `spl_simplifier` in `optimize_spl()`. Offline template QA: `scripts/llm_template_audit.py`. See `docs/architecture/spl_generation_audit.md` and `plans/2026-06-13_spl-generation-audit-completion.md`.
- Live LLM synthesis (live chat only): the live `/chat` path may narrate the analyst-summary prose with a real on-prem model (llama.cpp Foundation-Sec) when `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` and `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` are both true and a `local`/`openai_compatible` endpoint is configured. All facts (severity, MITRE+status, actions, SPL, `execution_eligible=false`) stay deterministic authority; the model only rewrites prose; any failure falls back to the deterministic draft. The Answer Guard (`AI_SOC_LLM_ANSWER_GUARD_ENABLED`) runs on the resulting draft. The Experience Center fixture path (`coe_synthetic_fixture`) is isolated by the demo-scenario early-return in `routes_chat.py` and never calls a live model. The model never calls MCP; no raw events reach the prompt.
- Do not add Splunk telemetry writes, SAIA/Splunk AI Assistant SPL generation, or direct LLM-to-MCP tool calling unless a later stage explicitly asks for it. Do not route live synthesis through the Experience Center path.
- Do not execute raw `candidate_spl`; never pass prompts, reasoning, credentials, RAG chunks, or raw workflow internals to MCP.
- Chat control plane (phases 0–11) is implemented: query-to-intent, evidence planning, RAG-only branching, route adjudication, SPL slot binding, flag-gated MITRE decision, `control_plane_trace`. Gated by `CONTROL_PLANE_ENABLED` (default `false`). See `plans/2026-06-02_chat-control-plane-master.md`. Forward work: `plans/AI_SOC_MASTER_PLAN.md`.
- COE observability/debugging: durable trace spine on live `/chat` (`ai_trace_runs` + steps/routing/SPL/MCP/LLM/RAG events, per-node `duration_ms`, LLM `latency_ms`/outcome), read-only `/debug` API (trace list, timeline, repro bundle, `/debug/readiness`) gated by `AI_SOC_DEBUG_API_ENABLED` + per-user `debug_access`, telemetry sink `db|file|none` (file = air-gapped NDJSON), `trace_id`-stamped logs. All redacted; best-effort (never breaks chat); EC fixture path emits no traces. See `docs/observability/debugging.md`.

## Run / Build

Primary path is Docker Compose, not bare uvicorn/npm:

```bash
docker compose build
docker compose up -d
```

Ports (all bound to 127.0.0.1):
- Backend: `http://127.0.0.1:8010` (uvicorn `--reload`, entry `app.main:app`)
- Frontend dev: `http://127.0.0.1:3010` (Vite)
- Postgres: `127.0.0.1:5434`

Frontend-only commands (run inside `frontend/`):
- `npm run dev` — Vite dev server on 3010
- `npm run build` — `tsc` + Vite build to `frontend/dist` (Nginx serves this in production); `postbuild` runs `chmod -R a+rX dist` so `www-data` can read the static files
- `npm run preview` — preview prod build

Backend bare-run (outside Docker, rare): `uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload` from `backend/`.

## Tests

Canonical governance regression (pytest, harness 6/6, audits, cov.q046 closure, 105-Q eval):

```bash
./scripts/run_stage3_governance_regression.sh
```

See [`docs/evals/regression_baseline.md`](docs/evals/regression_baseline.md) for expected green counts.

Backend tests only:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest
```

Frontend build:

```bash
cd frontend
npm run build   # postbuild chmods dist for Nginx (avoids 403 Forbidden)
```

Independent harness:

```bash
PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
TELEMETRY_MODE=none PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
```

Expected current baseline:
- Governance regression script: PASS (0 pytest failures, harness 6/6).
- Frontend build: passes.

## Layout

Monorepo, backend + frontend split:

```
backend/
  app/
    api/           # routes: health, chat, investigations, scenarios, auth
    auth/          # FastAPI session login (replaced prior nginx basic auth)
    schemas/       # Pydantic request/response models
    graph/         # LangGraph workflow state & orchestration (stub)
    orchestration/ # workflow planner skeleton; planning only, no execution
    safeguards/    # data minimizer, prompt injection filter, SPL validator, output validator
    routing/       # deterministic + shadow LLM routing, route comparison
    connectors/    # MCP, LLM, RAG, embeddings, telemetry connector surfaces
    mcp/           # legacy Splunk MCP client + mock client placeholders
    rag/           # RAG interface (stub)
    llm/           # LLM routing schema/prompts placeholders
    db/            # SQLAlchemy models + session
    knowledge_graph/, audit/, telemetry/
  pyproject.toml   # `pip install -e .` in Docker
  Dockerfile

frontend/
  src/
    components/    # UI primitives (shadcn-style), debug components
    pages/, api/, types/, lib/
  vite.config.ts   # alias @ -> ./src
  tsconfig.json    # strict, ES2020, Bundler resolution
  tailwind.config.ts, postcss.config.js, components.json

docker-compose.yml
.env.example
```

## Required Env Vars

Copy `.env.example` to `.env` before first `docker compose up`. Keys split into:
- App: `APP_ENV`, `BACKEND_PORT`, `FRONTEND_PORT`, `DATABASE_URL`, `DEBUG_TRACE_ENABLED`
- MCP readiness: `MCP_MODE`, `MCP_SERVERS`, `MCP_DEFAULT_SERVER`, `MCP_GLOBAL_EXECUTION_ENABLED`, and `MCP_SERVER_<NAME>_*`
- MCP mock execution: `MCP_SERVER_MOCK_EXECUTION_ENABLED` (must stay false unless explicitly testing mock execution)
- LLM readiness: `LLM_PROVIDERS`, role provider vars, concurrency/timeout/canary vars, `LLM_TOOL_RECOMMENDATION_ENABLED`, and `LLM_PROVIDER_<NAME>_*`
- SPL policy: `SPL_VALIDATION_ENABLED`, `SPL_ALLOWED_INDEXES`, `SPL_ALLOWED_SOURCETYPES`, `SPL_DEFAULT_EARLIEST`, `SPL_DEFAULT_LATEST`, `SPL_MAX_RESULT_LIMIT`, `SPL_ALLOWED_COMMANDS`, `SPL_BLOCKED_COMMANDS`
- Legacy placeholders retained for current mock connectors: `SPLUNK_MCP_ENABLED`, `SPLUNK_MCP_BASE_URL`, `SPLUNK_MCP_TOKEN`, `LLM_ENABLED`, `FOUNDATION_SEC_INSTRUCT_URL`, `FOUNDATION_SEC_REASONING_URL`, `REASONING_ENABLED`
- Routing: `ROUTING_MODE`, `ROUTING_DETERMINISTIC_THRESHOLD`, `ROUTING_LLM_SHADOW_ENABLED`, `ROUTING_COMPARE_LOGGING_ENABLED`
- AI-SOC telemetry: `TELEMETRY_MODE`, `AI_SOC_TELEMETRY_SINK`
- App login (replaces nginx basic auth): `APP_AUTH_ENABLED`, `APP_AUTH_USER`, `APP_AUTH_PASSWORD`, `APP_AUTH_SESSION_SECRET`

Never commit `.env` or session secrets. Postgres dev creds in `docker-compose.yml` (`ai_soc` / `ai_soc_dev_password`) are dev-only — do not reuse in production.

## Gotchas

- Auth migration is recent: app-level FastAPI session login replaces the old Nginx basic auth. Don't reintroduce basic-auth assumptions.
- CORS origin is hardcoded to `http://127.0.0.1:3010` in the FastAPI middleware — update when deploying or changing dev ports.
- `MCP_MODE=mock` must keep mock behavior. It may execute bounded deterministic mock rows only when both execution flags are explicitly enabled.
- `MCP_MODE=registry` with `SPLUNK_MCP_BASE_URL` + `SPLUNK_MCP_TOKEN` routes to the live Splunk connector when execution flags are on. Without credentials it fails closed (`splunk_mcp_not_configured`). Mock mode unchanged.
- All MCP and LLM settings/status output must redact secrets. Expose only booleans such as `url_configured`, `auth_configured`, `api_key_configured`.
- Splunk MCP App ID `7931` is the first target. Splunk search tools can only be selected for `spl_search` after deterministic policy checks; SAIA/generative/assistant/write/admin tools must remain blocked.
- LLM `supports_tool_calling` must remain false for now because direct LLM-to-MCP access is not allowed.
- Frontend visual system was adapted from a separate Support Buddy app as a read-only UI reference. No Support Buddy secrets, auth logic, or runtime config are reused — don't import them.
- Production traffic goes through Nginx at `cisco-vai.vnudge.com` serving `frontend/dist` and proxying `/api/` + `/health` to the backend. Don't expose Docker ports.
- After `npm run build`, `postbuild` must leave `frontend/dist` world-readable (`chmod -R a+rX dist`). A restrictive umask (files `600`, dirs `700`) causes Nginx `403 Forbidden` because it runs as `www-data`.

## Splunk MCP go-live (when endpoint is available)

**Canonical docs:** [`contracts/splunk_mcp_connection_contract.md`](contracts/splunk_mcp_connection_contract.md), [`plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md`](plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md), [`.env.splunk-live.example`](.env.splunk-live.example).

### What is already built (no code change at connect time)

- Async search lifecycle inside the connector: submit → bounded poll → fetch; gate calls `call_tool` once.
- Gate: live provenance (`evidence_source: live`), real envelope adapter, honest failed/timeout/denied outcomes.
- Per-call SPL confirmation (B4), SPL validation/allowlist, injection defense, broaden-on-empty orchestration.
- Poll bounds: `MCP_MAX_POLLS_PER_CALL`, `MCP_SEARCH_JOB_TIMEOUT_MS`, `MCP_SEARCH_POLL_INTERVAL_MS`.

### Operator steps (config only)

1. `cp .env.splunk-live.example .env` (or merge live flags into existing `.env`).
2. Set `SPLUNK_MCP_BASE_URL` and `SPLUNK_MCP_TOKEN` (bearer service account).
3. Align `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES` to the deployment.
4. `docker compose up -d` (or restart backend).
5. Staging smoke — one approved search through `/chat` (confirm SPL → verify rows or honest empty).
6. Set `schema_confirmed=true` in the contract doc after smoke passes (operator sign-off).
7. Run `./scripts/run_stage3_governance_regression.sh`.

### What must be verified at first live connect (may need a small transport patch)

The lifecycle/gate/envelope layers are production-ready. **Only `_StreamableHttpSearchTransport` in `splunk_mcp.py` assumes:**

| Assumption | Current code | If wrong at connect |
|------------|--------------|---------------------|
| Endpoint | `{BASE_URL}/mcp` | Change URL path in transport only |
| Protocol | JSON-RPC `tools/call` with `name: splunk_run_query` | Adjust method/params in transport only |
| Response shape | Inline rows in `result.rows` / `results` / `structuredContent` | Extend `_rows_from_mcp_result` or add job-id poll transport |
| Auth | `Authorization: Bearer <token>` | Adjust headers in transport only |

If the server uses a **true job protocol** (submit returns `job_id`, separate poll/fetch endpoints), replace only `_StreamableHttpSearchTransport` — `splunk_search_lifecycle.py`, gate, and evidence paths stay unchanged.

### What you can test **now** (no live MCP)

| Test | How |
|------|-----|
| Lifecycle state machine | `pytest app/tests/test_splunk_mcp_transport.py` (FakeTransport) |
| Full gate live path | Same file — `test_gate_live_run_*` (injected transport) |
| Result shape tolerance | `test_rows_from_mcp_result_tolerates_shapes` |
| Governance regression | `./scripts/run_stage3_governance_regression.sh` |

**Optional before connect:** add httpx-mocked unit tests for `_StreamableHttpSearchTransport` using a recorded JSON-RPC fixture (paste from staging or vendor docs into `backend/app/tests/fixtures/splunk_mcp/`). Script `scripts/capture_stage3m_s5_live_mcp_schema.py` accepts `STAGE3M_S5_RAW_FIXTURE_PATH` to normalize a captured payload offline.

### What **requires** a live MCP endpoint

- Confirm `/mcp` path, auth, and JSON-RPC framing.
- Confirm inline vs job-based search semantics.
- End-to-end `/chat` smoke with real Splunk rows.
- Flip `schema_confirmed=true` only after that smoke.

Until staging smoke passes, live envelopes carry `real_schema_unverified` (adapter warning) — evidence still flows, but operator has not signed off the wire contract.

## Plans

**Canonical plans (read these first):**

| Plan | Role |
|------|------|
| `plans/2026-06-02_chat-control-plane-master.md` | **Done** — chat control plane implementation (phases 0–11 on `master`). `CONTROL_PLANE_ENABLED=false` remains rollout default until COE approves. |
| `plans/AI_SOC_MASTER_PLAN.md` | **Active implementation roadmap** — hardening, skill enrichment, pipeline/LangGraph, GitHub skill intake (Tracks A–D); Batches 2–5 completed, next batch requires explicit scope approval. |
| `plans/STAGE_3K_Q1C_TO_Q4_SPINE.md` | Logic hierarchy, rules, status tables — agents read for Q1C→Q4 spine context. |
| `plans/2026-06-17_1730_intent-node-cascade-hardening.md` | **Done** — intent cascade floor, Engine-3 reconcile, Cisco 50 intent harness, completeness floor wiring, out-of-set probe eval |
| `/root/.cursor/plans/guided_investigation_5th_skill_098a0cdf.plan.md` | Done — guided investigation fifth route plus confirmed air-gapped Splunk MCP seven-tool binding; discovery remains planned-only and execution-gated. |
| `.cursor/plans/environment_kb_cisco_catalogue_1eddd12f.plan.md` | **Done** — Environment KB, Cisco 50 bank/eval (50/50 deterministic, in governance gate), tiered SPL Tier-1/Tier-2 validator. Wave-3 Tier-2 templates closed review-only (allowlist signed in `.env.example`, capability-valid, `enabled=false` until physical Splunk lookup CSVs exist). Google-25 closed as testing ground (`docs/evals/ot_powergrid_question_bank.json` 15/25, +6 paraphrase fixes). MCP exec off. |
| `/root/.cursor/plans/spl_generation_audit_30f60bc7.plan.md` | **Done** — relevance-first SPL audit (Phases A–H). Final: 105 100/102 deterministic (102/102 with `--llm-mock`), catalogue 31/31, governance green. G: lab-tier LLM exposure; E: `spl_simplifier`; F: offline template audit; H: `graph_node_spl_source_resolve`. Completion review: `plans/2026-06-13_spl-generation-audit-completion.md`. Commit `8f44eee`. |
| `/root/.cursor/plans/llm_lab-tier_spl_exposure_0c7c3c33.plan.md` | **Done** — merged into SPL audit close (`8f44eee`). Lab-tier exposure + H0–H4 source resolve; H2 MCP discovery scaffold only until COE. |

**All plans:**

| Plan | Status |
|------|--------|
| `plans/2026-05-24_1045_stage-3g1-governed-rag-completion.md` | Done |
| `plans/2026-05-24_1232_stage-3j-context-sufficiency-gate.md` | Done |
| `plans/2026-05-24_1811_stage-3j-b-llm-registry-settings.md` | Done |
| `plans/2026-05-24_1900_stage-3j-c-analyst-chat-ux-intent-hygiene.md` | Done |
| `plans/2026-05-26_1835_stage-3j-i-1-llm-adapter.md` | Done |
| `plans/2026-05-26_1842_stage-3j-i-2-dormant-semantic-guards.md` | Done |
| `plans/2026-05-26_1849_stage-3j-i-3-prompt-contracts-role-suitability.md` | Done |
| `plans/2026-05-26_1924_stage-3j-j-experience-center-llm-calibration.md` | Superseded — lighter calibration shipped in `2fefd10`; lineage reveal in `91f7b0e` |
| `plans/2026-05-26_1955_stage-3j-k0-llm-assisted-routing-governance.md` | In Progress — routing backend landed (`05c95bc`); governance settings UI uncommitted |
| `plans/2026-06-02_chat-control-plane-master.md` | **Done** — phases 0–11 (intent → evidence plan → route adjudication → SPL/MITRE/trace/golden). Rollout gated by `CONTROL_PLANE_ENABLED` (default `false`). Next: COE rollout review. |
| `plans/STAGE_3K_Q1C_TO_Q4_SPINE.md` | Canonical — logic hierarchy, rules, status tables |
| `plans/2026-05-28_0523_stage-3k-q1c-q4-roadmap.md` | Proposed — Q1C→Q4 roadmap index |
| `plans/2026-05-28_0523_stage-3k-q1c-route-plan-template-match.md` | Proposed |
| `plans/2026-05-28_0523_stage-3k-q1d-sample-template-spl-render.md` | Proposed |
| `plans/2026-05-28_0523_stage-3k-q1e-evidence-contract-lineage.md` | Proposed |
| `plans/2026-05-28_0523_stage-3k-q1f-llm-route-plan-shadow.md` | Proposed — LLM route-plan candidate (Instruct only, shadow) |
| `plans/2026-05-28_0523_stage-3k-q1g-llm-narrated-analyst-summary-shadow.md` | Proposed — LLM analyst summary narration (shadow only) |
| `plans/2026-05-28_0523_stage-3k-q2-local-ioc-lookup.md` | Proposed |
| `plans/2026-05-28_0523_stage-3k-q3-vetted-detection-binding.md` | Proposed |
| `plans/2026-05-28_0523_stage-3k-q4-pattern-coverage-pack.md` | Proposed |
| `plans/2026-06-13_spl-generation-audit-completion.md` | **Done** — closure review for SPL audit Phases A–H; metrics, deferrals (H2 COE, template promotion), verification commands |
| `plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md` | **Done (Steps 0–3)** — live Splunk MCP credential drop-in; wire framing verified at first connect. See §Splunk MCP go-live. |
| `plans/2026-06-03_1609_local-llama-instruct-synthesis-client.md` | In Progress — live-chat narration (P2/P3) landed: real client + summary narration, EC isolated, guard on, deterministic fallback. P4 latency UX + P5 live-MCP-into-prompt pending |
| `plans/2026-06-04_0703_general-soc-reasoning-answer-contract.md` | Done — general SOC reasoning layer (Agent A): data-driven MITRE evidence-preconditions (replaces per-use-case not-claimed hardcoding), AnswerContract read-model wired into finalize, contract-driven builder, fail-closed final-answer validator, 32-case behavior matrix. Flag-gated; suite + governance regression green |
| `plans/2026-06-04_0720_answer-quality-golden-regression-and-feedback-ledger.md` | Done — answer-quality ledger, feedback API, review queue, promote-golden, expectation matrix (105+46), Tier 0–2 golden JSONL + runner (Tier 0 in governance regression), Quality page summary |
| `plans/AI_SOC_MASTER_PLAN.md` | **Active** — single master plan for Tracks A–D (hardening, enrichment, pipeline, GitHub intake register). Supersedes `2026-06-06_*` drafts. Tracking: §P + `docs/skills/*` (proposed, not created yet). |
| `plans/2026-06-08_0717_planner-led-plan-completion-review.md` | **Review** — completion review of the `.cursor` planner-led plan. Phases 0–9 done (commits recorded) and governance-green behind default-off flags; legacy/parity runtime remains default; planner-led LangGraph fan-out/fan-in topology not yet built; Phases 10–11 + Knowledge-surfaces-sync pending. |
| `plans/2026-06-09_1827_105-path-honoring-smb-analytics.md` | **Done** — exact-105 analytics path honoring (q0.q010 SMB top talkers): registry-first analytics intent bridge, analytics severity guard ("Not assigned from this question alone"), boundary-label overmatch fix, `network_smb_top_talkers` lab draft family, AnswerContract built for every classified answer (section-ordered card), Tier A tests + Tier B `scripts/eval_105_path_honoring.py --check`. Hunt-pattern bridge extends honoring to 95/105 questions (10 deferred: lookup/TI/asset-context/source-health classes need their own answer shapes). 14 draft families added (auth threshold, top talkers, IOC match, DNS beaconing, rarity, threshold, PowerShell, exfil volume, lateral movement, persistence, multi-signal, notable/risk review, identity privileged activity, source health) — full-105 real-pipeline run: 101/105 carry an SPL artifact or lab draft, 0 P3-without-policy severities; remaining 4 need entity/asset context by design. Governed templates and active use-case severity policies keep authority. `.env.example` aligned to all-on SOC posture; MCP execution flags remain false. PowerGrid 50 deterministic eval 50/50. |
| `plans/2026-06-10_0356_skills-llm-mcp-utilization-and-paraphrase-readiness.md` | **In Progress (rev 3, executable playbook)** — Done: WS-PRE sentinel infra + definitive verdicts (PR #9), Order 2 T4.1/T4.2/T5.1 + AQ-001 content-driven limitations (PR #12), WS0 Resource Planner T0.1–T0.5 (PR #13; LLM plan bridge moved off the blocking live path after PowerGrid latency incident — llama-server memory thrash diagnosed and restarted), curated privileged-login checklist enrichment staged metadata-only for WS2 T2.3 (PR #14). In progress: WS1 paraphrase/out-of-set intake. Next: WS2 skills, WS3 scorecard/narration, WS4c/d MCP adapter + contract doc, WS5.2/5.3. — planner-node-centric: WS0 Resource Planner node (capability registry over MCP tools/RAG/analytics/LLM roles/skills, composed ResourcePlan with degrade chains, deterministic composer as main orchestration, LLM-proposed-deterministically-validated plans for out-of-set questions), WS1 paraphrase/out-of-set robustness (semantic tier, advisory promotion, paraphrase eval, honest fallback), WS2 skills as answer-shaping resources (contracts into planner, knowledge into RAG, skill-derived answer sections, targeted intake), WS3 LLM role scorecard + narration coverage, WS4 MCP go-live (Phase A hardening now; contract pre-filled from livehybrid/splunk-mcp tool schema — `search_splunk(search_query, earliest_time, latest_time, max_results)` etc.; Splunkbase 8747 AI Workbench noted; 7931-vs-livehybrid binding = COE decision), WS5 answer-quality evals (grounding/completeness/actionability/honesty rubric, Tier-D deterministic + Tier-L LLM-judge, out-of-set corpus as headline metric). No new flags; MCP execution flags stay false until COE. |
| `plans/2026-06-15_0821_wazuh-mcp-adoption-and-flagship-ec-scenario.md` | **Done** (PR #31, branch `cp-cyclic-evidence-loop`; §5 items deferred by design). Deterministic adoption of third-party Wazuh MCP (`sb-siem-mcp`) answer-shapes + safety — never the LLM-drives-MCP loop. **§3** flagship EC scenario `critical_alerts_mitre_cve_review` (Splunk-native, `future_state_preview=false`, CVE leg = honest `vulnerability_source: not_onboarded` degrade). **§4A** air-gapped tool posture (7 `splunk_*` enabled + RBAC-governed; 4 `saia_*` conditional+blocked), `mcp_tool_playbook.json`, chronology reviewer, `mcp_rbac_policy.json` (viewer/analyst/soc_lead, fail-closed), advisory tool-plan shadow (`/chat` + EC parity). **§4B** governed cyclic evidence-collection loop (`app/chat/evidence_loop.py`): `evidence_planning` HUB, read-only `mcp_call` discovery hops, single `MAX_MCP_HOPS=6` bound, requirement↔deliverable assessor, decision-B broaden deferral, CP-gated cyclic LangGraph + imperative-twin loop; collected discovery hops merge into `source_evidence`→`structured_facts`; LLM chronology stays off the blocking path (deterministic default unless advisory flag). **§2** A1 evidence secret-value sanitizer (`_safe_text` + envelope rows + `to_prompt_block`), A2–A4 `analysis/soc_aggregates.py`; detection-gap card on the Knowledge page (`build_detection_coverage()` + `GET /knowledge/detection-coverage`). **§5 deferred:** Wazuh connector / 2nd MCP server (COE N4), live CVE/vuln onboarding, active-response/confirmation-token gate (N2), Experience-Center detection-gap card. |
| `plans/2026-06-15_1949_coe-observability-debugging.md` | **Done** — COE debuggability, all phases. Phase 0 trace spine (`start_trace`/`end_trace` on live `/chat`, error runs). Phase 1 LLM/RAG capture + per-node `duration_ms` (`node.*` steps) + LLM `latency_ms`/outcome. Phase 2 read-side `/debug` API (`/debug/traces`, `/traces/{id}`, `/traces/{id}/bundle`) + Debug UI; trace-id validation, event caps (500/200). Phase 3 file/NDJSON sink for air-gap (`AI_SOC_TELEMETRY_SINK=file` + `AI_SOC_TELEMETRY_FILE_DIR`, read_store file backend). Phase 4 log↔trace correlation (contextvar + `LogRecordFactory` stamps `trace_id` on `ai_soc.*`). Phase 5 `/debug/readiness` (LLM+MCP+RAG+sink) + per-turn/LLM counters in `metrics`/`/health`. Phase 6 dead-stub cleanup (removed `app/telemetry/`, `app/audit/`) + `docs/observability/debugging.md`. Gated `AI_SOC_DEBUG_API_ENABLED` + per-user `debug_access`; redaction reused; EC isolated. |
| `plans/2026-06-16_1258_spl-cve-mitre-enhancement-plan.md` | **Proposed** — SPL/CVE/MITRE enrichment + ATLAS raw intake. §13 **tiered LLM utilization decision** (grounded in live 8B capability probe): T1 in-catalogue/105 = deterministic authority + repo-asset enrichment from CVE/MITRE/ATLAS, LLM narrate-only; T2 out-of-catalogue/guided-hunt = LLM primary answer-shaper fed by a deterministic skill-grounding assembler (WS-F), candidate SPL validated, MITRE candidate-only, unverified banner. §13.5 ⚠️ **governance posture change requires COE sign-off** — source-tier no longer decides SPL executability (guardrail-pass + full resolution + extra HIL does); global MCP exec flag stays off. Until COE approves, T2 ships review-only. WS-A CVE air-gapped snapshot ingestion, WS-E ATLAS raw-first+duplicate gate. **Shipped:** MITRE catalogue LLM audit (`scripts/llm_mitre_catalogue_audit.py`; COE report `docs/evals/llm_mitre_catalogue_audit_coe_report.md` — 11 contradictions/30 gaps/97 expansion candidates), ATLAS comparison (`scripts/atlas_vs_catalogue_compare.py`), ATLAS coverage-gap lane (`build_atlas_coverage_gap()` + `/knowledge/atlas-coverage` + Knowledge card; posture/roadmap only — 170 AML do NOT reach live chat), WS-F grounding scaffold (`app/chat/grounding_assembler.py`, NOT wired). **§15 WS-G** = complete plan for offline mitreattack-python STIX resolver (validate 97 candidates → promote/drop, supply ATT&CK/ATLAS names; import-isolated, air-gapped; NOT built — interface slot only). **Audit disposition (2026-06-16, `docs/evals/mitre_audit_disposition.md`):** reviewed all 5 buckets. Bucket 1 gaps — 14/30 promoted to **candidate** tier in the two enrichment DRAFTs (T1110 brute-force parents, T1059.001 PowerShell subs, T1071 outbound-C2 hunts) with `candidate_provenance` stamp; 16/30 no-map (SOC meta-ops + wrong-domain/OT/auth mis-attributions). **COE strict corrections:** all mappings labelled `candidate_mitre_anchors` not `confirmed_mitre_technique` (ATT&CK = behavior, not analytics); dropped T1110.003 from q0.q089 + auth_failed_login_spike (MFA-failure/volume ≠ password spray), dropped T1059.001 from edr_malware_alert_summary (summary ≠ PowerShell), T1621 MFA-fatigue noted as WS-G bundle-expansion candidate (missing). Bucket 4 over-map (3) = candidate anchors valid-with-evidence (not "confirmed"); side-finding T1048/T1071.004 (+T1621) missing from `mitre_attack_subset.json` bundle. Bucket 2 contradictions (11, all T1078) → keep blocks; q086 don't-unblock-by-default, q096 candidate-with-evidence only (COE). Bucket 3 expansion (97) → WS-G G3→G5. Bucket 5 llm_empty (23): 5a (14) true no-map, 5b (9) candidate anchors only (registry already statuses candidate/needs_review, never confirmed). MITRE tests 178 passed; MCP exec unchanged. |
| `plans/2026-06-24_run-contract-canonical-state.md` | **Done** — RunContract/RouteContract canonical state for every live `/chat` turn (CP-on + CP-off). Kills competing-truths bugs: single authority for preview, HIL (`action_capability.hil == governance_trace.effective_hil == run_contract.effective_hil`), source evidence (`collected_evidence_count` from collected telemetry only; collected/review/candidate artifacts separated), lineage render gates, and route authority (shadow `route_authority_compare`/`routing_skill_resolution`/`response.route_authority` re-projected to `canonical_run_contract`, raw audit under `raw_shadow_compare`). Governance/honesty fixes: MITRE tier caps to `requires_validation` MCP-off; analytics severity sentinel preserved; severity gate tightened for knowledge/guidance. Phase 5 authority-read sweep certified clean. 11 demo captures normalized; EC parity. Suite 2898 passed; governance PASS. PR #32 (7 commits `dc7c6b8`..`052d699`). |
| `plans/2026-06-29_conditional-pipeline-canonical-dispatch.md` | **In Progress** (branch `feat/pipeline-dispatch-v2`) — two-stage mid-pipeline dispatch authority (IntentDispatchDecision pre-2C + PipelineDispatchContract post-evidence; `stage_schedule`+`llm_hops` sole routing surface), mandatory SPL postprocessor on all sources, LLM SPL plan input/output preservation (`detection_plan`→`SplCandidateStageResult`→`persist_llm_spl_plan`), pre-SPL MCP discovery, debug final-output trace. Behind `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` (default false). **All 12 phases done** (0→0.5→1A→2A→3→4→2B→2C→5→6→7→8), behind `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` (default false; flag-off byte-identical, governance PASS 120/120·50/50·16/16 every phase). Stage-1 `IntentDispatchDecision` (pre-2C, table-driven 2C prompt modes) + Stage-2 `PipelineDispatchContract` (`stage_schedule`+`llm_hops`, request_mode table, discovery-vs-execution split, CP-off fallback). Mandatory review-only SPL postprocessor (hash trace, governed-template byte-identity). LLM SPL input/output preservation: compiler grounding inputs + `detection_plan`→`persist_llm_spl_plan`→downstream `consumed_by`; dual spl_plan_compiler telemetry. Pre-SPL MCP discovery node (cursor-driven). Phase-6 cursor progression + ordered parity (full LangGraph node extraction deferred — shadow path). Phase-7 SCADA/Cisco T2-native retired under flag (enabled-template promotion deferred to live Splunk schema). Phase-8 dispatch matrix F–J + `scripts/eval_pipeline_dispatch_matrix.py` (non-gating in governance). Debug `final_output` trace + dispatch surfaces. Commits `df3eaac`..(phase8) on `feat/pipeline-dispatch-v2`. Deferrals closed: (1) `_candidate_from_llm_fallback` now returns tuple-unpackable `SplCandidateStageResult` (`85f3b27`); (2) cursor-driven LangGraph routing wired in edges (`7dca623`) — dedicated compiled spl_postprocessor/pre_spl nodes design-superseded (inline single-applier, shadow path, double-apply risk); (3) SCADA/Cisco authored as tenant-portable TOKEN SPL (placeholders+coalesce+analyst-guiding fallback, resolves via source-resolve chain) + tenant-aware allowlist `load_spl_policy(tenant_id)` from `AI_SOC_TENANT_SOURCETYPE_MAP` (`da08c50`); remaining boundary = wiring tenant_id from auth/Env-KB (not present in single-tenant deployment). All behind `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` (flag-off byte-identical). |

## Git Notes

Recent stage split:
- `911eed6` Fix SPL routing relevance bugs (Phase B)
- `ad29958` Wire LLM-primary SPL failover and relevance gate (Phase C)
- `35b42b0` Single SPL surface and ambiguous-route disambiguation (Phase C.2)
- `1b86da2` Close catalogue SPL coverage via existing-family reuse (Phase D)
- `22cbbc3` Close the nine uncovered catalogue use cases with lab families (Phase D.2)
- `8f44eee` Complete SPL audit phases G/E/F/H for lab exposure and source resolve

Keep future changes similarly scoped. Do not combine workflow execution changes with connection-readiness or UI-only changes unless explicitly requested.
