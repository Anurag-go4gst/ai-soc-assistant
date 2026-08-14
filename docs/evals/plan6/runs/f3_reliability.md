# Plan 6 F3 — reliability, capacity, failure behaviour

Surface: VPS (`environment_identity=coe-vps`). Run **on the persisted F2 production profile** —
no env key was edited for any injection. Injections are transient and external to the app:
`systemctl stop llama-server`, or a stub bound to the same host port
(`host.docker.internal:8081`) the backend already points at.

Harness: `scripts/eval_plan6_f3_failure_classes.py` (+ `scripts/eval_plan6_vps_harness.py` for corpus).
Artifacts: `docs/evals/plan6/runs/f3/*.json`, `docs/evals/plan6/runs/20260814T031208Z/`,
`docs/evals/plan6/runs/20260814T045547Z/`, `docs/evals/plan6/runs/f3_live_mcp.md`.

Effective flags unchanged throughout: exec **OFF**, dispatch-v2 **ON**, T4 **OFF** (timeout 2.0s),
live capability enforcement **OFF**, `MCP_MODE=mock`.

## 1. Restart / recreate + representative corpus smoke

`docker compose up -d --force-recreate backend` → health **200**.
Full 12-row corpus re-run: `docs/evals/plan6/runs/20260814T031208Z/`.

| Check | Result |
|---|---|
| Harness exit | **0**, rows **12/12** |
| `missing_qualification_tier` | **none** |
| Route / `qualification_tier` / `resource_plan_fingerprint` drift vs Arm A (`20260813T114521Z`) | **0 rows** |
| `execution_enabled` | **false** on all 12 |
| `degrade_reason` | **null** on all 12 (exec OFF ⇒ no merge, no v2-wins downgrade) |
| `semantic_t4` | **null** on all 12 (T4 OFF) |
| `phase_names` | empty on all 12 |

Restart persistence holds: the recreated container reproduces the pre-restart routing and
schedule identity exactly.

## 2. Latency vs baseline

Arm A (`20260813T114521Z`) predates the harness `wall_ms` field, so the honest latency
baseline is the pre-recreate F0 run on the same arm and same flags.

| Run | n | p50 | p95 | min | max |
|---|---|---|---|---|---|
| F0 pre-recreate `20260813T183145Z` | 12 | 92,587 ms | 182,638 ms | 1,396 ms | 236,013 ms |
| **F3 post-recreate `20260814T031208Z`** | 12 | **92,931 ms** | **182,120 ms** | 1,858 ms | 235,992 ms |

Δp50 **+344 ms (+0.4 %)**, Δp95 **−518 ms**. Per-row deltas range −998 ms … +644 ms — inside
run-to-run noise. No extra LLM hop was introduced (T4 OFF, exec OFF).

Absolute latency (~92 s p50) is the known shared-VPS CPU-contention envelope for the 8B
on-prem model, not a Plan 6 regression. Not treated as a Plan 6 defect; carried to F5 as
performance context.

## 3. Failure classes

| # | Injected condition | Observed route / execution | HTTP / result | Fail-open vs fail-closed | Degrade reason | Recovery | Duplicate side effects | Latency | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| FC-1 | **LLM unavailable** — `systemctl stop llama-server`, nothing on :8081 | `attack_discovery`, `execution_enabled=false`, MCP `requires_human_review` (`precondition_eval_failed`), HIL `precondition_review` **required** | **200**, deterministic answer | **fail-closed** | `null` (no execution authority to degrade) | `systemctl start` exit 0 → `active` | none — 0 executed MCP events | **1,072 ms** | **PASS** |
| FC-2 | **Malformed LLM output** — stub on :8081 returns HTTP 200 with truncated JSON | `attack_discovery`, `execution_enabled=false`, MCP `requires_human_review`, HIL **required** | **200**, deterministic answer | **fail-closed** | `null` | stub torn down, `llama-server` `active` | none | **1,822 ms** | **PASS** |
| FC-3 | **LLM timeout** — stub on :8081 sleeps 180 s | `attack_discovery`, `execution_enabled=false`, MCP `requires_human_review`, HIL **required** | **200**, deterministic fallback; no hang, no 5xx | **fail-closed**, bounded | `null` | stub torn down, `llama-server` `active` | none | **181,754 ms** (bounded by the turn deadline, request still completed) | **PASS** |
| FC-4 | **Model-slot pressure** — 3 concurrent `/chat` on the LLM-narrating question, single-slot llama | all 3 `knowledge_recall`, `execution_enabled=false`, MCP `skipped` | 3 × **200**, exit 0 | **fail-closed** (degrades to deterministic, never fabricates) | `null` | n/a — no restart needed | 3 distinct trace_ids, 0 executed MCP events | 2,699 / 2,693 / **62,548** ms; wall **62,726** ms | **PASS** |
| FC-4b | **Model-slot pressure, HIL short path** — 3 concurrent on the alert question | all 3 `attack_discovery`, `execution_enabled=false`, HIL required | 3 × **200** | fail-closed | `null` | n/a | 3 distinct trace_ids | 3,460 / 3,531 / 3,634 ms | **PASS** |
| FC-5 | **DB failure + recovery** — `docker compose stop postgres` | `/chat` never reached: login **401**, chat **401** | health **200** with `readiness.database_migrations.ready=false` | **fail-closed** (session auth refuses, no unauthenticated answer) | n/a | `start postgres` → `ready=true` | none | — | **PASS** |
| FC-6 | **MCP / Splunk unavailable** | not exercisable live: `SPLUNK_MCP_BASE_URL` / `SPLUNK_MCP_TOKEN` empty, `MCP_MODE=mock` | — | fail-closed by contract: `block_reason=splunk_mcp_not_configured` | n/a | n/a | none | — | **`live_mcp_unproven`** — see `f3_live_mcp.md`. Deterministic fail-closed coverage: **47 passed** |

Concurrency ×2 and repeated-identical ×2 from the earlier F3 session
(`f3/concurrent_summary.json`, `f3/repeat_summary.json`) are retained: both concurrent turns
and both repeats returned `knowledge_recall` / `rag_only` / `execution_enabled=false` with
distinct trace_ids (91,549 ms and 91,927 ms on the repeats).

Note on FC-1/FC-2/FC-3: the `precondition_eval_failed` HIL is the deterministic gate refusing
to proceed without satisfied preconditions. In every case the answer degraded to deterministic
content — no fabricated live rows, no `execution_eligible` flip (`null` throughout), and the
human-review obligation was still raised.

## 4. Duplicate side effects

Window = the whole F3 session (5 h), read from the durable trace spine:

| Query | Result |
|---|---|
| `select count(*), count(distinct trace_id) from ai_trace_runs` | **21 / 21** — one run row per request |
| `mcp_execution_logs` by `event_type` | `mcp_execution_blocked` 8, `mcp_execution_requires_human_review` 1, `mcp_tool_discovery_started` 1, `mcp_tool_discovery_completed` 1, `mcp_tool_selection` 1 |
| executed / succeeded MCP events | **0** |
| `canonical_execution_idempotency` rows | **0** (no side-effecting step ran) |

No repeated request produced a second side-effecting execution. Nothing to deduplicate,
because nothing executed.

## 5. Recovery + final state

Post-injection recovery smoke: `docs/evals/plan6/runs/20260814T045547Z/` — 2 rows, exit **0**,
`p6.t1.knowledge` → `knowledge_recall` (`54643926bb51081e`) and `p6.spl.draft` →
`attack_discovery` (`99ccd9213e2f0b37`) — **both fingerprints identical to Arm A**;
`degrade_reason` null on both.

Final health after all injections:

```
status=ok  database_migrations.ready=true  telemetry.write_failures=0
systemctl is-active llama-server.service → active
```

## Verdict

**F3 PASS with `live_mcp_unproven`.** Every required failure class is recorded with an
observed outcome. No test was weakened to obtain a PASS: FC-6 is recorded as unproven rather
than satisfied with mock evidence, and the two long-latency rows are reported as measured.

Open item carried to F5: live Splunk/MCP investigation is **not** production-proven.
