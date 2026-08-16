# COE production readiness runbook

**Audience:** COE operator qualifying this release on a COE host.  
**Branch / profile:** `feat/coe-production-readiness` with `AI_SOC_ENV_PROFILE=coe`.  
**This document does not declare production GO.** Human approval remains mandatory.

Reuse, do not replace:

- Deploy from Git: [`COE_GIT_DEPLOY_RUNBOOK.md`](COE_GIT_DEPLOY_RUNBOOK.md)
- Flag table: [`COE_ROLLOUT_CONFIGURATION.md`](COE_ROLLOUT_CONFIGURATION.md)
- Rollback (do **not** re-enable dispatch-v2): [`docs/evals/plan7/rollback_runbook.md`](../evals/plan7/rollback_runbook.md)
- T4 pack: [`docs/evals/t4_coe_qualification.md`](../evals/t4_coe_qualification.md)
- MCP contract: [`contracts/splunk_mcp_connection_contract.md`](../../contracts/splunk_mcp_connection_contract.md)
- Debug: [`docs/observability/debugging.md`](../observability/debugging.md)

Invariants for this run:

- `MCP_MODE=mock` until an explicit live MCP qualification window.
- Do not treat `/v1/models` HTTP 200 as inference health.
- Do not copy the VPS `120`s T4 bound as a COE SLO.
- Do not set `LIVE_MCP_PROVEN` or close F3 from mocks.
- Never restart Cisco Foundation-Sec from code or this runbook’s automation.

---

## 1. Deployment sequence

Run on the COE host from the repo root. Record `git rev-parse HEAD` before starting.

1. **Select COE profile** (secrets stay in `.env`, never git):

   ```bash
   ./scripts/select_env_profile.sh coe
   ```

   Confirm `.env` has `AI_SOC_ENV_PROFILE=coe`. Compose loads
   `env/profiles/coe.env.example` then `.env` (later wins).

2. **Supply T4 timeout explicitly** in `.env` (required; preflight/startup reject the `2.0`s code default):

   ```dotenv
   AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=<operator-supplied-seconds>
   ```

   Choose a measured COE value. Do **not** copy VPS `120` as an SLO.

3. **Preflight** (fails closed if COE T4 is on and timeout is unset/`2.0`):

   ```bash
   ./scripts/coe_preflight.sh --auto-port
   ```

   Expect `PREFLIGHT: OK`.

4. **Build and start** (application containers only; do not restart Cisco):

   ```bash
   ./scripts/coe_deploy_verify.sh
   ```

   Or: `docker compose up -d --force-recreate backend` after a first full `up`.
   Settings are process-start config — `restart` alone can leave a stale env.

5. **Read back application authority** (must match; live MCP is a later opt-in):

   | Flag | Required |
   |---|---|
   | `LANGGRAPH_ORCHESTRATION_ENABLED` | `true` |
   | `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | `true` |
   | `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | `false` |
   | `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | `true` |
   | `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | `false` |
   | `MCP_MODE` | `mock` |

   `MCP_GLOBAL_EXECUTION_ENABLED=true` on this mock lane is **not** live Splunk.

6. **Inference health** (bounded generation, not `/v1/models`):

   ```bash
   docker compose exec -T backend python3 - <<'PY'
   from app.llm.runtime_health import measure_runtime
   print(measure_runtime())
   PY
   ```

   If inference-unhealthy: **human** Cisco restart, then re-probe, then
   `record_manual_model_restart(inference_health_ok=True, …)` — see §9.

---

## 2. T4 live qualification

Does **not** close F3. Harness never sets `f3_closed=true`.

Static pack (no model call):

```bash
PYTHONPATH=backend:. python3 scripts/eval_t4_coe_qualification.py --emit-prompts \
  --out docs/evals/t4_coe_qualification.json --check
```

COE live (refuses the `2.0`s code default; does not change model/provider/timeout):

```bash
PYTHONPATH=backend:. python3 scripts/eval_t4_coe_qualification.py --live \
  --chat-smoke --out docs/evals/t4_coe_qualification_live.json
```

Record `serving.inference_health`, cold/warm, p50/p95, timeout/error rate, concurrency 1/2/3. Invent no SLO. A human must accept the table before F3 can be reconsidered.

---

## 3. MCP qualification

Keep `MCP_MODE=mock` until this section’s live window.

Config/contract only (no network, never claims `LIVE_MCP_PROVEN`):

```bash
PYTHONPATH=backend:. python3 scripts/eval_splunk_mcp_coe_qualification.py --check
```

Expect `STATUS=READY_FOR_COE_CONFIGURATION`, `LIVE_MCP_PROVEN=false`.

Operator fill (worksheet: [`docs/operations/splunk_mcp_coe_configuration_worksheet.md`](../operations/splunk_mcp_coe_configuration_worksheet.md)): endpoint, token file, `SPLUNK_MCP_TLS_VERIFY` (default true), CA path, allowlist. Write/remediation tools stay disallowed.

Live opt-in (COE only). The probe still **does not** mark proven; it lists required live steps:

```bash
AI_SOC_COE_LIVE_MCP_QUALIFICATION=1 PYTHONPATH=backend:. \
  python3 scripts/eval_splunk_mcp_coe_qualification.py --live
```

Then execute those steps on the COE Splunk MCP server, including one controlled
read-only `/chat` path: generate SPL → validate → HIL/RBAC/AUTH0 confirm →
allowlisted `splunk_run_query` → evidence. Negative tests (mutate SPL/time/tool
after grant; unauthorized tool; timeout; malformed result; no remediation tool)
must fail closed. Mock rows must not masquerade as live. Operator sign-off of
`schema_confirmed=true` is separate and remains `false` until that smoke.

---

## 4. Smoke pack (8)

After deploy, with `MCP_MODE=mock`. Copy `trace_id` from each `/chat` response.

| # | Do | Pass |
|---|---|---|
| S1 | `./scripts/coe_preflight.sh` | `PREFLIGHT: OK`; T4 timeout override printed |
| S2 | `curl -fsS http://127.0.0.1:<BACKEND_PORT>/health` | HTTP 200 JSON |
| S3 | UI login (`APP_AUTH_USER` / password) | session established |
| S4 | In-catalog query (e.g. failed-login / CVE lookup) | `control_plane_trace` present; `schedule.resource_plan_authority` not `degraded`; `execution_enabled=false` |
| S5 | *How should I investigate unusual outbound traffic from an OT host overnight?* | guided / hybrid path; MCP not executed |
| S6 | `GET /api/debug/traces/{trace_id}/bundle` (user with `debug_access`) | `explainability.debug_summary` has routing, `semantic_t4`, schedule, SPL, MCP block |
| S7 | Confirm `MCP_MODE=mock` and empty live URL/token | no live Splunk rows |
| S8 | Candidate SPL on an SPL-shaped ask | `spl_validation.approved` may be true; `execution_eligible` false / null; candidate not executed |

Do not treat S1–S8 as T4 serving proof or live MCP proof.

---

## 5. Observability (inspect)

Use [`docs/observability/debugging.md`](../observability/debugging.md).

| Signal | Where | Gap? |
|---|---|---|
| trace ID | `/chat` + `/api/debug/traces/{id}` | no |
| final RQC | `debug_summary.resolved_query` (redacted) | no |
| ResourcePlan authority | `debug_summary.schedule.resource_plan_authority` | no |
| T4 called/skipped/degraded | `semantic_t4.invoked/accepted/timed_out` | no |
| provider failure kind | `semantic_t4.failure_kind` | no |
| normalized SPL | presence boolean + hashes; not SPL text | by design |
| authorization result | MCP `allowed/status/block_reason` | AUTH0 grant fingerprint is **not** a `/debug` block |
| MCP result | status/block_reason | live rows **UNPROVEN** |
| EvidenceState | pipeline state only | **not** on ChatResponse or `/debug` |
| InvestigationOutcome | `/chat` payload | **not** in `debug_summary` |
| F1 DB degrade | `planning_outcome.status=persistence_failed`; schedule `resource_plan_authority=degraded` | closed in code |
| T4 circuit OPEN | sidecar notes / `human_action_required_model_restart` | **not** a first-class `/debug` field |
| latency | `duration_ms`, T4 `elapsed_ms`, run duration | COE p50/p95 **UNPROVEN** |

`/v1/models=200` is liveness only.

---

## 6. Performance

Do **not** invent SLOs. VPS Plan 7 D1 orch p50/p95 and VPS T4 latencies are **not** COE targets.

On COE, record (do not pass/fail against a number here): T4 cold/warm/p50/p95, T4 concurrency 1/2/3, inference-health tok/s, MCP connect/poll/fetch if live, end-to-end `/chat` with T4 on.

---

## 9. Rollback / recovery

Reuse [`docs/evals/plan7/rollback_runbook.md`](../evals/plan7/rollback_runbook.md) and [`COE_GIT_DEPLOY_RUNBOOK.md`](COE_GIT_DEPLOY_RUNBOOK.md) §7–8. **Never** roll back by setting `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=true` / `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=false` as a routine runtime switch. That pair is retired as normal authority.

### Backend restart

```bash
docker compose up -d --force-recreate backend
curl -fsS http://127.0.0.1:<BACKEND_PORT>/health
```

Application container only. Do **not** restart Cisco. Plan 7 D1: authority survived recreate.

### DB recovery

```bash
docker compose stop postgres
# /health may stay 200 with ready=false; /chat must not claim ResourcePlan authority
# Expect planning_outcome.status=persistence_failed and
# schedule.resource_plan_authority=degraded (F1).
docker compose start postgres
# Next turn: authority restored (not degraded).
```

Backup/restore: `COE_GIT_DEPLOY_RUNBOOK.md` §8 (`pg_dump` / `psql`). `docker compose down -v` destroys the volume.

### Human Cisco restart

Code must not restart the model (`request_human_model_restart` returns `restart_authorized=false`). Operator restarts Foundation-Sec out of band (host procedure, e.g. `systemctl restart llama-server` **on the model host**, never from this repo’s automation). Then inference-requalify.

### Inference requalification

1. `measure_runtime()` — not `/v1/models`.
2. If healthy, `record_manual_model_restart(inference_health_ok=True, evidence=…)`.
3. Circuit may enter HALF_OPEN only after that operator probe. A failed probe stays OPEN.

### MCP reconnect

Fail-closed: missing URL/token → `splunk_mcp_not_configured`; timeout/TLS → mapped error kinds; no mock fallback in `MCP_MODE=registry`. After network restore, retry the gated `/chat` confirm path. Live reconnect on COE is **UNPROVEN** until §3 live steps run.

To leave live MCP: set `MCP_MODE=mock` (and keep live URL unused). Do not “fix” live by flipping dispatch-v2.

### Release rollback

```bash
git log --oneline -10
# backup .env first
git checkout <last-fully-proven-commit>
docker compose up -d --build --force-recreate backend
```

Deploy that **release’s** profile, not a flag mash-up of the current tree. Postgres volume survives checkout. Do not restart Cisco as part of app rollback.

### Config rollback

`.env` wins over the tracked seed. To restore COE application authority without touching secrets: remove or comment overrides that disagree with `env/profiles/coe.env.example`, keep the T4 timeout override (required), `--force-recreate backend`, read back the six authority flags. Restoring Plan 6 `v2=true` / `ResourcePlan=false` is **not** approved config rollback.

---

## 10. Final GO matrix

Statuses: **PASS** / **FAIL** / **UNPROVEN** / **DEFERRED**.  
Live COE cells stay **UNPROVEN** until this runbook’s measurements exist. Do not mark them PASS from VPS mocks.

| Dimension | Status | Basis |
|---|---|---|
| Architecture | **PASS** | ResourcePlan + PhaseContract sole normal authority; v2 fenced; Plan 7 E2 / Plan 8 |
| COE configuration | **PASS** | Tracked `coe.env.example` reconstructs authority; T4 timeout fail-closed until operator override |
| T4 semantics | **PASS** | Plans 6–8; T4 cannot grant route/capability/tool |
| T4 serving / F3 | **UNPROVEN** | VPS serving not viable; COE `--live` not yet run; F3 stays open |
| Live Splunk MCP | **UNPROVEN** | `MCP_MODE=mock`; `LIVE_MCP_PROVEN` must stay false until §3 live `/chat` |
| End-to-end | **UNPROVEN** | COE host `/chat` + T4 + (optional) live MCP not executed in this doc |
| Security | **PASS** | TLS verify default on; write/remediation tools disallowed; LLM cannot mint AUTH0 grant; candidate SPL non-executable. COE public TLS / live MCP TLS still operator-supplied |
| Failure handling | **PASS** | D1 classes + F1 degraded-authority signal in code; live COE drill not a GO substitute |
| Observability | **PASS** | `/debug` bundle covers trace, RQC, authority, T4, failure_kind, SPL hashes, MCP block. Gaps: EvidenceState not on `/debug`; InvestigationOutcome not in `debug_summary`; AUTH0 fingerprint and T4 circuit not first-class debug fields |
| Performance | **UNPROVEN** | No COE SLO; VPS p50/p95 must not be treated as targets |
| Recovery / Rollback | **PASS** | Procedures above + Plan 7 runbook; v2 re-enable forbidden as routine rollback. Live COE rollback drill **UNPROVEN** |

```
PRODUCTION_GO_RECOMMENDATION = NO_GO
```

Human approval remains mandatory. F3 and live MCP are still required before GO can be reconsidered.

---

## Related docs

| Doc | Role |
|---|---|
| [`COE_GIT_DEPLOY_RUNBOOK.md`](COE_GIT_DEPLOY_RUNBOOK.md) | Clone → ports → stack |
| [`COE_ROLLOUT_CONFIGURATION.md`](COE_ROLLOUT_CONFIGURATION.md) | Flag table + older smoke list |
| [`COE_LIVE_TESTING_GUIDE.md`](COE_LIVE_TESTING_GUIDE.md) | EC / mock / registry layers |
| [`docs/evals/plan7/rollback_runbook.md`](../evals/plan7/rollback_runbook.md) | Authority rollback |
| [`docs/evals/plan7/e2_decision.md`](../evals/plan7/e2_decision.md) | `PRODUCTION_GO_LIVE = DEFERRED / NO-GO` |
