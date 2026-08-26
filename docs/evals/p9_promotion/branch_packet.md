# P9 promotion branch packet

**Candidate SHA:** `c109402d69956df455a780fd49a191fa173ab7ac`  
**Branch:** `ws/p9-execution`  
**P8 frozen SHA:** same (`c109402d…`) — P9 is evidence-only on the frozen tip  
**Measured:** 2026-08-26 (Mac darwin-arm64)  
**Live MCP:** OFF  
**Decision:** `P9_PARTIAL` / **NO-GO_FULL_PROMOTION**

## A. Mission result

P9 built the residual ledger and Mac gate matrix for one exact SHA. Zero unexplained regressions versus the P8 tip. Full promotion GO is blocked by (1) Linux exact-SHA attestation environment blocker and (2) three named residuals that need explicit operator adjudication.

## B. Artifacts

| Artifact | Path |
|---|---|
| Residual ledger | `docs/evals/p9_promotion/residual_failure_ledger_v1.json` |
| Gate matrix | `docs/evals/p9_promotion/gate_matrix_v1.json` |
| GO/NO-GO | `docs/evals/p9_promotion/go_nogo_v1.json` |
| This packet | `docs/evals/p9_promotion/branch_packet.md` |

## C. Mac gates (summary)

| Gate | Result |
|---|---|
| Full backend | **7109 passed, 0 failed** |
| Frontend tests / build | **119 passed** / **PASS** |
| RACES | **8 passed** |
| Protected baseline `--check` | **15/15** |
| Bank hash | **match** `5f78ccbe…` |
| 105-path `--check` | **105/105** |
| Routing truth absolute | **67/85** route_ok |
| Routing truth `--check` | **FAIL** — only `rt.para.011` (named) |
| Harness | **6/6** |
| Migration readiness | **7 passed, 2 skipped** |
| Integration (PG) | **1 passed, 35 skipped** |
| Clean-answer `--check` | **120/120** |
| Template audit | **19/19** |
| 105-shadow | **PASS** |
| Dual parity | **120 exact / 0 critical** |
| Cisco 50 | **50/0/0** |
| Dispatch matrix | **5/5** |
| Golden Tier 0 | **2 fails** (identical to P8 product tip `64c95798`) |
| Stage3 composite script | **FAIL** early at golden Tier 0 (named) |
| Linux exact-SHA | **ENVIRONMENT_BLOCKED** (Docker daemon down) |

## D. Named residuals requiring operator action

1. **H-PROMO-02 `rt.para.011`** — baseline `attack_discovery` / route_ok; candidate `knowledge_recall` / capability_inconsistent. Same at P6/T4/P8 tips. Plan 5 paraphrase residue / frozen-arm limit. **Ask:** accept carry without baseline refresh?
2. **GOLDEN_TIER0_BINDING_CLARIFICATION** + **GOLDEN_TIER0_AWS_SG** — identical fails at P8 product tip. **Ask:** accept as stale expectation, or return to Workstream B?
3. **H-PROMO-05 Linux** — Docker sock unavailable (`Cannot connect to the Docker daemon`). **Ask:** start Docker Desktop / run isolated Linux attestation at `c109402d…` and attach evidence.

## E. Closed residuals

| ID | Outcome |
|---|---|
| H-PROMO-03 GitHub clone factory | **CLOSED** — test removed by retirement |
| H-PROMO-04 migration | **CLOSED** — 7 passed, 2 skipped |
| H-PROMO-06 RACES freeze | **PASS** — 8/8; spot `test_races_freeze_files_unchanged_since_baseline` green |
| P4 handoff e2e pair | **CLOSED** — both probes **PASS** at candidate SHA |

## F. What was not done (by design)

- No baseline refresh  
- No push / merge / deploy  
- No live MCP  
- No product code changes on P9 branch (evidence + plan status only)  
- P10 not started  

## G. Operator next steps

1. Adjudicate residuals in §D (accept / fix-in-owning-stream / block).  
2. Start Docker and run exact-SHA Linux validation; attach attestation under `docs/evals/p9_promotion/`.  
3. On Linux PASS + residual adjudication → flip decision to `P9_COMPLETE` / GO → then P10 handoff only.  
4. Do **not** treat Mac-only green as production promotion GO.

## H. Suggested Linux attestation commands (when Docker is up)

```bash
cd /Users/aagarwal/Downloads/ai-soc-p9-execution
git rev-parse HEAD   # must be c109402d69956df455a780fd49a191fa173ab7ac
./scripts/coe_preflight.sh --auto-port
docker compose build && docker compose up -d
# inside Linux container or Linux host clone of same SHA:
cd backend && python3 -m pytest -q
TELEMETRY_MODE=none PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
./scripts/run_stage3_governance_regression.sh   # expect named golden Tier0 unless adjudicated
```
