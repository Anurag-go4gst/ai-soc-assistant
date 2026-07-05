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
- Intent hygiene: SOP/playbook/runbook and MITRE prompts route to `knowledge_recall` (no SPL); MITRE ask without alert context → `intent_clarification` human-review. Chat UI is analyst-first (summary card on top, technical trace collapsed).
- Guarded LLM adapter (`app/llm/adapter/`): validates role-specific schemas, forces deterministic overrides on conflict (SPL `execution_eligible=false`, clarification/severity/MITRE-status/SOP-citation/allowed-actions). Dormant semantic guards in `app/answer_guard/rules.py` (unit-tested only). Neither is wired into any live `/chat` or demo path yet.
- Experience Center demo answers (`app/demo/scenarios.py`) are deterministic/`coe_synthetic_fixture`, calibrated to governed behavior (valid template SPL, explicit MITRE status, `execution_eligible=false`), never produced by a live model. EC SPL is sourced from the governed template registry (`_scoped_template_spl`) — edit `templates.json` and EC follows, no drift. EC surfaces the same LLM-sidecar/lineage/governance builders as live (`live_llm_called=false`, advisory). Frontend is served in prod by Nginx from `frontend/dist` — run `npm run build` in `frontend/` to publish UI changes; the docker `frontend` service is Vite dev only.
- LLM-assisted routing: modes `deterministic_only`, `llm_shadow_only`, `llm_assisted_semantic`, `llm_primary_lab`. Route suggestions are advisory only, normalized through deterministic registries; final route selection stays deterministic. SPL optimizer field is `revalidation_approved`; candidate SPL stays non-executable.
- Five live router skills: `alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall`, `guided_investigation`. `guided_investigation` is a deterministic rescue for out-of-registry hunts — review-only guidance, MCP execution stays disabled.
- Dynamic resource planning (`plans/2026-07-02_1327_dynamic-resource-planning-out-of-catalogue.md`, **Done**): CanonicalFacts spine; grounding + evidence-summary floor; action lane (`/api/actions`) + `ProposedActionsPanel` when `AI_SOC_ACTION_LANE_LIVE_PROPOSALS_ENABLED=true` (default false). Tier-1 still discloses `create_ticket` unavailable.
- T2 out-of-catalogue answer quality (`plans/2026-06-19_1700_power-industry-query-to-solution-CONSOLIDATED.md`): behind default-off flags `AI_SOC_T2_ANSWER_SHAPE_ENABLED` / `_ANSWER_SURFACING_ENABLED` / `_RAG_SURFACING_ENABLED`; in-catalogue 105/50 stays byte-identical. Deterministic answer-shape router (`app/chat/answer_shape_router.py`) picks the template before any hunt fallback; LLM is advisory/producer, never authority.
- Dynamic resource planning (`plans/2026-07-02_1327_dynamic-resource-planning-out-of-catalogue.md`, **Done**): CanonicalFacts spine on `PlaceholderResponse.canonical_facts`; grounding assembler + evidence-summary floor for out-of-registry/near-105 paths; action lane (`/api/actions/{id}/approve|deny`) with optional live proposals on `/chat` when `AI_SOC_ACTION_LANE_LIVE_PROPOSALS_ENABLED=true` (default false); `ProposedActionsPanel` in chat UI. Tier-1 `action_capability` still lists `create_ticket` unavailable — proposals are mechanism-only until tier/policy changes.
- T2 LLM SPL producer is **plan-plus-compiler** (`app/spl/llm_plan_compiler.py`): LLM emits a small JSON detection plan, deterministic code compiles the SOC-STD SPL; flows through existing validate/quality/adapter gates unchanged.
- T2 execution hardening (default-OFF): unresolved placeholder slots block execution; live registry mode always requires per-call analyst confirmation (`ai_soc_require_spl_execution_confirmation`, default true). Source-tier never decides executability — guardrail-pass + full resolution + confirmation does.
- SPL generation: relevance-first — governed templates → LLM-primary failover (`AI_SOC_LLM_SPL_FALLBACK_ENABLED`, default off) → lab draft last resort. **Refined governance invariant (2026-07-03):** raw lab-tier LLM SPL is never directly executable — the raw candidate envelope always stays `approved=false`/`normalized_spl=null`/`execution_eligible=false` (`app.safeguards.spl_validator.validate_spl_lab_candidate`, pinned by `test_t2_governed_producer.py`/`test_llm_plan_compiler.py`). Only a **separate, derived artifact** may become execution-eligible, and only after the raw SPL passes adapter normalization, the real `validate_spl` (post slot-resolution, not the lab-candidate variant), source-slot resolution, and harmful-SPL vigilance risk classification (`app.spl.llm_lineage_vigilance.classify_llm_spl_risk`, item 2.4): **high** risk (validator rejection, injection, risky command, missing time bounds/result cap) is blocked before the MCP gate; **medium** risk requires the existing per-call HIL confirmation unchanged; **low** risk (every hard criterion holds, incl. relevance-gate pass) is auto-eligible — but auto-eligibility only ever relaxes confirmation in mock/non-live mode; live/registry-mode execution always requires per-call confirmation regardless of risk tier (`app.orchestration.mcp_execution_gate.evaluate_mcp_execution`'s `llm_lineage_auto_eligible` parameter never overrides `registry.mode == "registry"`). Unresolved source-profile slots always route to existing HIL clarification, never a lab-draft fallback. `graph_node_spl_source_resolve` fills placeholders from `AI_SOC_SOURCE_PROFILE_MAP`/RAG/session pins, else HIL clarification. See `docs/architecture/spl_generation_audit.md`.
- Live LLM synthesis (live chat only): may narrate analyst-summary prose with a real on-prem model when `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` + `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` are both true and an endpoint is configured. All facts (severity, MITRE, actions, SPL, `execution_eligible=false`) stay deterministic authority; model only rewrites prose; failure falls back to deterministic draft. EC fixture path never calls a live model. Model never calls MCP.
- Do not add Splunk telemetry writes, SAIA/Splunk AI Assistant SPL generation, or direct LLM-to-MCP tool calling unless explicitly scoped. Do not route live synthesis through the Experience Center path.
- Do not execute raw `candidate_spl`; never pass prompts, reasoning, credentials, RAG chunks, or raw workflow internals to MCP.
- Chat control plane (query-to-intent, evidence planning, route adjudication, SPL slot binding, MITRE decision, `control_plane_trace`) is implemented, gated by `CONTROL_PLANE_ENABLED` (default `false`). See `plans/2026-06-02_chat-control-plane-master.md`.
- COE observability: durable trace spine on live `/chat` (`ai_trace_runs`), read-only `/debug` API gated by `AI_SOC_DEBUG_API_ENABLED` + per-user `debug_access`, telemetry sink `db|file|none`. Redacted, best-effort, never breaks chat; EC path emits no traces. See `docs/observability/debugging.md`.

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

Full plan index + active-work table: [`plans/README.md`](plans/README.md). Master roadmap: [`plans/AI_SOC_MASTER_PLAN.md`](plans/AI_SOC_MASTER_PLAN.md). Logic hierarchy/rules/status tables: [`plans/STAGE_3K_Q1C_TO_Q4_SPINE.md`](plans/STAGE_3K_Q1C_TO_Q4_SPINE.md).

Most-relevant in-flight/recent plans:

| Plan | Status |
|------|--------|
| `plans/2026-07-04_1736_intent-mcp-tool-routing-hardening.md` | Draft (item 0 done: alias-dedupe/stale-comment/await_execution spine fixes, suite 3985 green) — Phase 1: playbook intent hints, data-silence advisory HIL, saved-search name allowlist + saved-search-first preference, kv_store surface-pending. Phase 2: governed evidence observation (`evidence_observer` reads bounded sanitized MCP rows, grounded claims, governed ReAct, 1-call/turn cap). Phase 3: canonical reference-knowledge path (CVE/ATT&CK/ATLAS registry, `reference_taxonomy` shape, `reference_finalize`, 10-probe contract incl. negatives, LLM shape advisor shadow, zero-hallucinated-ID quality evals) |
| `plans/2026-07-04_0428_intent-advisor-value-o5c-live-scorecard.md` | **Done** — consumer-gated intent advisor (`intent_advisory_no_consumer`), candidate-constrained advisory prompt (first live promotion, 13.1s), O5c live-trigger match-path fix, live scorecard: MCP 26.67% / LLM util 45% / CVE-MITRE 13.33% |
| `plans/2026-07-02_1327_dynamic-resource-planning-out-of-catalogue.md` | **Done** — LLM-primary planner, all-tier MCP eligibility, O5c multi-call, CVE/MITRE resources, CanonicalFacts spine + grounding, action lane + UI (`AI_SOC_ACTION_LANE_LIVE_PROPOSALS_ENABLED`), Batch A flag retirement, post-change scorecard in `docs/evals/out_of_catalogue_after_2026-07/` |
| `plans/2026-06-29_conditional-pipeline-canonical-dispatch.md` | In Progress (`feat/pipeline-dispatch-v2`) — all 12 phases done behind `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` (default false, flag-off byte-identical) |
| `plans/2026-07-01_1545_guided-readonly-mcp-discovery-lane.md` | Draft — read-only MCP discovery lane for `guided_investigation`, behind `AI_SOC_GUIDED_MCP_DISCOVERY_ENABLED` |
| `plans/2026-06-24_run-contract-canonical-state.md` | Done — RunContract/RouteContract canonical state, single authority for HIL/evidence/route (PR #32) |
| `plans/2026-06-16_1258_spl-cve-mitre-enhancement-plan.md` | Proposed — SPL/CVE/MITRE enrichment; T2 governance posture change needs COE sign-off (§13.5) |
| `plans/2026-06-15_1949_coe-observability-debugging.md` | Done — trace spine, `/debug` API, file sink, log correlation |
| `plans/2026-06-15_0821_wazuh-mcp-adoption-and-flagship-ec-scenario.md` | Done — Wazuh MCP answer-shapes, cyclic evidence loop (§5 items deferred by design) |
| `plans/2026-06-10_0356_skills-llm-mcp-utilization-and-paraphrase-readiness.md` | In Progress (rev 3) — WS0 Resource Planner done; WS1 paraphrase intake in progress |
| `plans/2026-06-02_chat-control-plane-master.md` | Done — phases 0–11, gated by `CONTROL_PLANE_ENABLED` (default false) |
| `/root/.cursor/plans/spl_generation_audit_30f60bc7.plan.md` | Done — relevance-first SPL audit Phases A–H (`8f44eee`) |
| `.cursor/plans/environment_kb_cisco_catalogue_1eddd12f.plan.md` | Done — Environment KB, Cisco 50 bank/eval, tiered SPL validator |
| `/root/.cursor/plans/guided_investigation_5th_skill_098a0cdf.plan.md` | Done — 5th route + air-gapped Splunk MCP 7-tool binding |

Older stage plans (`2026-05-24` through `2026-06-13`, Stage 3G.1/3J/3J-B/3J-C/3J-I/3J-J/3J-K0, SPL audit completion, MCP/LLM readiness, answer-quality ledger) are all **Done** — see `plans/README.md` and git log for detail rather than duplicating here.

## Agent skills (invoke these — do not re-derive the discipline)

Project skills in `.claude/skills/` (auto-listed in every Claude Code session here); user-level counterparts live in `~/.claude/skills/`:

- **`/execute-plan-item`** — executing any checklist item under `plans/`: anchor verification, verbatim Verify, Evidence recording, stop conditions. Use for every plan item; do not free-style plan execution.
- **`/invariant-check`** — REQUIRED before any commit touching pipeline/planner/SPL/MCP/LLM code: 7-group governance diff review (LLM↔MCP mediation, SPL executability, EC purity, redaction, state channels, flags, test honesty).
- **`/deep-think`** (user-level) — start of any non-trivial task: verify-before-trust protocol.
- **`/self-improve-loop`** (user-level) — metric-target quality pushes (e.g. scorecard improvements): evaluator-first, one-hypothesis iterations, KEEP/REVERT ledger.
- **`/handoff`** (user-level) — ending a session mid-plan: 7-section state note for the next agent.

## Git Notes

Recent stage split:
- `911eed6` Fix SPL routing relevance bugs (Phase B)
- `ad29958` Wire LLM-primary SPL failover and relevance gate (Phase C)
- `35b42b0` Single SPL surface and ambiguous-route disambiguation (Phase C.2)
- `1b86da2` Close catalogue SPL coverage via existing-family reuse (Phase D)
- `22cbbc3` Close the nine uncovered catalogue use cases with lab families (Phase D.2)
- `8f44eee` Complete SPL audit phases G/E/F/H for lab exposure and source resolve

Keep future changes similarly scoped. Do not combine workflow execution changes with connection-readiness or UI-only changes unless explicitly requested.
