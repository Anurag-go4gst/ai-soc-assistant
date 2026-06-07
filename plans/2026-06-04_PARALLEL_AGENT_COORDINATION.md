# Parallel agent coordination (2026-06-04 plans)

**Purpose:** Let Claude, Codex, and Cursor agents work in parallel without breaking the shipped control plane or governance baseline.

| Plan | File | Agent slot |
|------|------|------------|
| General SOC reasoning | [`2026-06-04_0703_general-soc-reasoning-answer-contract.md`](2026-06-04_0703_general-soc-reasoning-answer-contract.md) | **A** — **Done** (`f0346f0`…`63ff4d0` on `feat/deterministic-spl-llm-fallback`) |
| Answer quality ledger | [`2026-06-04_0720_answer-quality-golden-regression-and-feedback-ledger.md`](2026-06-04_0720_answer-quality-golden-regression-and-feedback-ledger.md) | **B** — **Done** (ledger, feedback, review API, Tier 0–2 golden, promote-golden, Quality dashboard) |
| E2E reference (read-only) | `.cursor/plans/query-to-answer_traversal_audit_4af31549.plan.md` | No implementation without stage approval |

**Canonical pipeline (complete):** [`2026-06-02_chat-control-plane-master.md`](2026-06-02_chat-control-plane-master.md)

## Merge gate (every PR)

```bash
./scripts/run_stage3_governance_regression.sh
```

CI must run with `CONTROL_PLANE_ENABLED` unset or `false` (production default). After Agent A changes:

```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_chat_control_plane_golden.py -q
```

## Shared artifact (mandatory)

```text
backend/app/evals/fixtures/control_plane_critical_flows.json
```

- `test_chat_control_plane_golden.py` → thin wrapper over this fixture.
- `golden_answer_runner --tier 0` → loads the same rows.
- **Forbidden:** two hand-written definitions of the seven critical flows.

## Serialize (one agent at a time)

- `backend/app/evals/fixtures/control_plane_critical_flows.json` (create + first population)
- `backend/app/tests/test_chat_control_plane_golden.py`
- `backend/app/chat/pipeline.py` — `graph_node_context_finalize` and MITRE finalize path
- `CONTROL_PLANE_ENABLED` default in `backend/app/config.py` and `.env.example` (must stay `false`)

## Safe in parallel

- Agent B **Phase 1** ledger: post-response hook only, fail-open, skip `/clear` and demo fixtures.
- Agent A Commits 1–2 while B works on migrations/API scaffolding that does not touch MITRE/builder.

## Implementation order

```text
1. Reconcile WIP (0703 plan header) on one branch or merge to master first
2. Agent A: General SOC Commits 1–5 (flag-gated)
3. Shared fixture (Commit 3 or Answer-quality Phase 4 — one owner)
4. Agent B: Phase 1 ledger (parallel OK after step 2 Commit 1 if no golden edits)
5. Agent B: Phase 4–5 Tier 0 runner — after shared fixture exists
6. Traversal B5 (use-case split) — separate PR; coordinate with Agent A Commit 1
```

## Never without explicit stage approval

- Live MCP execution, `candidate_spl` execution, LLM→MCP
- Flip `CONTROL_PLANE_ENABLED` default to `true`
- Live Foundation-sec final synthesis on `/chat`
- Experience Center / demo golden answer changes
