# P9 promotion branch packet

**Candidate / product SHA:** `c109402d69956df455a780fd49a191fa173ab7ac`  
**Branch:** `ws/p9-execution`  
**PRODUCT_CODE_CHANGED_IN_P9:** NO  
**Measured:** 2026-08-26 (Mac darwin-arm64 + Docker Desktop Linuxkit)  
**Live MCP:** OFF  
**Decision:** `P9_COMPLETE` / **GO_FULL_PROMOTION=YES**  
**P10_ELIGIBLE_TO_START:** YES (not started)

## A. Mission result

P9 promotion evidence is complete for one exact product SHA on Mac and Linux. Zero unexplained regressions. Three inherited residuals are operator-accepted and remain recorded as `ACCEPTED_INHERITED_RESIDUAL` (not PASS).

## B. Artifacts

| Artifact | Path |
|---|---|
| Residual ledger | `docs/evals/p9_promotion/residual_failure_ledger_v1.json` |
| Gate matrix | `docs/evals/p9_promotion/gate_matrix_v1.json` |
| GO/NO-GO | `docs/evals/p9_promotion/go_nogo_v1.json` |
| Linux attest log | `docs/evals/p9_promotion/linux_backend_attest.txt` |
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
| Routing truth `--check` | **ACCEPTED_INHERITED_RESIDUAL** (`rt.para.011`) |
| Harness | **6/6** |
| Migration readiness | **7 passed, 2 skipped** |
| Integration (PG) | **1 passed, 35 skipped** |
| Clean-answer `--check` | **120/120** |
| Template audit | **19/19** |
| 105-shadow | **PASS** |
| Dual parity | **120 exact / 0 critical** |
| Cisco 50 | **50/0/0** |
| Dispatch matrix | **5/5** |
| Golden Tier 0 | **ACCEPTED_INHERITED_RESIDUAL** (×2) |

## D. Linux exact-SHA attestation

| Field | Value |
|---|---|
| ATTESTED_SOURCE_SHA | `c109402d69956df455a780fd49a191fa173ab7ac` |
| LINUX_SOURCE_SHA | `c109402d69956df455a780fd49a191fa173ab7ac` |
| Container | `ai-soc-assistant-local-backend-1` |
| Image | `ai-soc-assistant-local-backend` (`sha256:a6d87476…`) |
| Result | **7109 passed, 0 failed, 45 skipped, 6 xfailed** |
| Start/End | `2026-08-26T13:54:44Z` → `2026-08-26T14:00:27Z` |

Notes for reproducibility: clean `env -i` (compose `.env` flag pollution causes false fails); `PYTHONPYCACHEPREFIX=/tmp/p9_pycache` (Mac host `__pycache__` embeds `/Users/...` co_filenames invisible in Linux); workspace temporarily RW for freeze durability probe; `git` installed in container for RACES probes.

## E. Operator adjudication (accepted inherited)

| ID | Status |
|---|---|
| `rt.para.011` | `accepted_inherited_residual` |
| `tier0.top_failed_login_spl_missing_binding_clarification` | `accepted_inherited_residual` |
| `tier0.aws_security_group_modifications_spl_only` | `accepted_inherited_residual` |

Reason: pre-existing at accepted baseline / not introduced by P9 / owning stream deferred.

## F. Product baseline

- `PRODUCT_PROMOTION_SHA = c109402d69956df455a780fd49a191fa173ab7ac`
- `PRODUCT_CODE_CHANGED_IN_P9 = NO`
- P9 commits are audit/evidence only

## G. Next

P10 is eligible; **do not start P10** until operator requests it.
