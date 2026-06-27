---
name: Operator closure checklist
overview: "Operator-only actions after consolidated handoff/T2 closure (Batches 0–F). No automatic runtime behavior."
status: active
date: 2026-06-27
supersedes: none
related_plan: plans/2026-06-27_handoff-t2-completion-consolidated.md
---

# Operator Closure Checklist

**Audience:** COE / platform operators. **Not** agent-executable without explicit sign-off.

**Code closure baseline:** `master` @ `ca3249b` (PRs #40, #39, #41–#45 merged). Implementation batches A–F are complete; this document covers production rollout only.

---

## 1. COE promotion apply (`q0.q046` pilot)

**Tool:** `scripts/apply_promotion_status_review.py` (dry-run by default).

### Dry-run interpretation

```bash
# 1) Read current row revision
python3 scripts/apply_promotion_status_review.py promote q0.q046 \
  --show-revision --operator-id coe.reviewer --review-ticket COE-XXXX

# 2) Dry-run (default; no --apply)
python3 scripts/apply_promotion_status_review.py promote q0.q046 \
  --operator-id coe.reviewer \
  --review-ticket COE-XXXX \
  --row-revision <revision-from-step-1> \
  --pack-id q0.q046 \
  --golden-passed \
  --golden-run-ref "<CI-or-manual-run-id>" \
  --json
```

- **`dry_run=true` / `applied=false`:** expected for default invocation; inspect `blockers` and `before_status` / `after_status`.
- **`already_in_target_status`:** row already at target tier; no write needed.
- **`s3_authority_ready_required`:** authority preconditions not met; fix upstream data or defer apply.
- **Audit:** successful applies append to `docs/evals/out/promotion_status_audit.jsonl` (gitignored).

### When to use `--apply`

Only when **all** are true:

1. Governance regression PASS on target commit (`./scripts/run_stage3_governance_regression.sh`).
2. Golden / targeted probes green for the row (`q0.q046` pack + row-authority report).
3. COE ticket records operator-id, review-ticket, row-revision, golden-run-ref.
4. Dry-run shows `allowed=true` with no blockers.

```bash
python3 scripts/apply_promotion_status_review.py promote q0.q046 \
  --operator-id <coe-id> \
  --review-ticket <ticket> \
  --row-revision <revision> \
  --pack-id q0.q046 \
  --golden-passed \
  --golden-run-ref <run-ref> \
  --apply \
  --json
```

**Rollback:** demote via same CLI with `demote` action + `--reviewed-reason`; re-run row-authority report `--refresh` if catalogue inputs changed. Runtime `/chat` never auto-writes `promotion_status`.

---

## 2. Row-authority report refresh

**Policy:** [`docs/evals/ARTIFACT_REFRESH_POLICY.md`](../docs/evals/ARTIFACT_REFRESH_POLICY.md)

```bash
python3 scripts/build_row_authority_report.py --check
python3 scripts/build_row_authority_report.py --refresh   # intentional only
```

Commit `row_authority_report.json` / `.md` only when runtime-map or catalogue authority inputs changed and COE reviewed the diff.

---

## 3. Eval baseline refresh policy

**Do not** commit accidental drift from local governance runs:

- `docs/evals/soc_clean_answer_eval_*`
- `docs/evals/langgraph_dual_parity_*`
- `docs/evals/llm_template_audit_report.md`

Refresh only when explicitly requested for a release milestone; restore with `git checkout -- docs/evals/` after local verification.

---

## 4. Production flags

| Flag | Default | Production guidance |
|------|---------|---------------------|
| `CONTROL_PLANE_ENABLED` | `false` | Enable only after CP-on matrix green in staging |
| `route_authority_operation_authoritative_enabled` | `false` | Enable only after Batch B row-authority matrix sign-off |
| `MCP_GLOBAL_EXECUTION_ENABLED` | `false` | See live MCP section |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | `false` | Mock execution for lab only |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | `false` | Narration only; facts stay deterministic |

**Rollback:** revert env to defaults above; restart backend; confirm `/health` and one `/chat` smoke per [`scripts/ask_chat.sh`](../scripts/ask_chat.sh).

---

## 5. Live Splunk MCP go-live

**Canonical docs:**

- [`contracts/splunk_mcp_connection_contract.md`](../contracts/splunk_mcp_connection_contract.md)
- [`plans/2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md`](2026-05-30_1845_query-to-answer-live-mcp-llm-readiness.md)
- [`.env.splunk-live.example`](../.env.splunk-live.example)
- MCP live-readiness checklist (merged via PR #39)

**Checklist summary:**

1. Set `SPLUNK_MCP_BASE_URL` + `SPLUNK_MCP_TOKEN` (never commit).
2. Align `SPL_ALLOWED_INDEXES` / `SPL_ALLOWED_SOURCETYPES`.
3. Keep global + per-server execution flags **off** until staging smoke passes.
4. One approved search through `/chat` with analyst SPL confirmation.
5. Run `./scripts/run_stage3_governance_regression.sh`.
6. Set `schema_confirmed=true` in contract doc after operator sign-off.

**Rollback:** set execution flags false; remove or rotate token; Nginx continues serving UI without live MCP.

---

## 6. Architecture boundaries (unchanged by operator actions)

- **RouteContract** — final route authority after adjudication.
- **EvidencePlan** — planning snapshot; does not authorize execution.
- **ResourcePlan** — composed steps; MCP steps may be `blocked_policy`; does not override route.
- **FinalEvidenceGate** — evidence-derived HIL, live-language, MITRE/severity caps.
- **RunContract** — finalize-only public posture for render, SPL lifecycle, MCP posture.

No operator flag should bypass FinalEvidenceGate or execute `candidate_spl` directly.

---

## 7. Verification before production promotion

```bash
./scripts/run_stage3_governance_regression.sh
cd backend && CONTROL_PLANE_ENABLED=false PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_handoff_healthy_contradiction.py \
  app/tests/test_canonical_handoff_e2e_probes.py \
  app/tests/test_run_contract_builder.py \
  app/tests/test_final_evidence_gate_cross_stream.py -q
cd frontend && npm run build
```

Restore any generated `docs/evals/` drift before committing operator-only doc updates.
