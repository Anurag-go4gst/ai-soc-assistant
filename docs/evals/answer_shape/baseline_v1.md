# Post-P10 convergence — baseline attestation (item 0.1)

**Attested_at_utc:** `2026-08-26T17:28:13Z`  
**Plan:** `plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md`  
**Item:** `0.1` — Re-attest release baseline

## Plan labels (authoritative)

| Label | SHA |
|---|---|
| VERIFIED_RELEASE_BASELINE_SHA | `6b63df610ff4a0994a593537ab46c71464afe570` |
| LAST_PRODUCT_CHANGE_SHA | `c109402d69956df455a780fd49a191fa173ab7ac` |

## Local checkouts

| Location | Branch | `git rev-parse HEAD` | Rel. to baseline |
|---|---|---|---|
| Cursor workspace (`…/ai-soc-assistant-t4-architecture-20260821`) | `feat/complete-or-abstain-t4-ux` | `c109402d69956df455a780fd49a191fa173ab7ac` | **Ancestor of baseline** (product tip). `merge-base --is-ancestor 6b63df61 HEAD` → **no**. Not a valid execution start alone. |
| Execution worktree (`…/ai-soc-wt-post-p10-convergence`) | `ws/post-p10-answer-tool-convergence` | `6b63df610ff4a0994a593537ab46c71464afe570` | **Equals** VERIFIED_RELEASE_BASELINE_SHA. `START_EQUALS_OR_DESCENDED=yes`. **Authoritative start for this plan.** |

Worktree created (plan precondition):

```bash
git worktree add /Users/aagarwal/Downloads/ai-soc-wt-post-p10-convergence \
  -b ws/post-p10-answer-tool-convergence \
  6b63df610ff4a0994a593537ab46c71464afe570
```

## Remote tips (after `git fetch origin`)

| Ref | SHA |
|---|---|
| `origin/master` | `6b63df610ff4a0994a593537ab46c71464afe570` |
| `origin/release/p10-final` | `6b63df610ff4a0994a593537ab46c71464afe570` |
| `origin/feat/complete-or-abstain-t4-ux` | `6b63df610ff4a0994a593537ab46c71464afe570` |

All three remotes match VERIFIED_RELEASE_BASELINE_SHA.

## Product vs docs delta

```text
c109402d..6b63df61  (docs/handoff only; product_code_delta = NONE per historical handoff meta)
6b63df61 docs(handoff): record P10 final evidence SHA in meta
4c38080a docs(handoff): prepare P10 PR/merge packet awaiting operator
09f02e46 docs(promotion): close P9 with Linux exact-SHA attestation
5854ad11 docs(promotion): record P9 Mac gate matrix and residual ledger
```

**LAST_PRODUCT_CHANGE_SHA** (`c109402d…`) remains the product-code tip for behaviour. Confirmed via `product_code_delta_c109402d_to_p10_final: NONE` in historical handoff meta (read-only; **not rewritten**).

## Historical handoff meta (point-in-time — not current ops truth)

Path (present on baseline worktree; absent on Cursor product-tip checkout):  
`docs/evals/p10_handoff/handoff_meta.json`

| Field | Value (historical) |
|---|---|
| `packet_id` | `p10_pr_merge_handoff_v1` |
| `decision` | `P10_COMPLETE` |
| `p10_product_baseline_sha` | `c109402d69956df455a780fd49a191fa173ab7ac` |
| `p10_final_sha` | `4c38080a52e459ee83b6ba12a91322f96b3fd668` |
| `push_performed` / `merge_performed` / `deploy_performed` | `false` / `false` / `false` (**point-in-time**; remotes now at `6b63df61`) |
| `next_phase_started` | `false` |
| `live_mcp` | `OFF` |
| `future_post_master_plan_gap` | investigation→…→conditional remediation→conditional email→HIL→send |

**Action:** file left unmodified.

## Runtime / VPS

| Check | Result |
|---|---|
| VPS / runtime checkout SHA | **Not validated this turn** — no runtime host probe. Recorded as unused for 0.1. Re-attest before any live browser/API gate that requires it. |
| Local `.env` (Cursor workspace, informational) | `AI_SOC_ENV_PROFILE=coe`; `AI_SOC_BACKEND_HOST_PORT=8012`; `AI_SOC_FRONTEND_HOST_PORT=3013` |

## Mismatch rule

Plan: *any mismatch stops the loop.*

| Check | Outcome |
|---|---|
| Cursor workspace HEAD vs baseline | **Mismatch** (ancestor only) — not used as execution root |
| Execution worktree HEAD vs baseline | **PASS** — equals `6b63df61…` |
| Remotes vs baseline | **PASS** |
| Product tip label | **PASS** — still `c109402d…` |
| handoff_meta rewrite | **PASS** — not rewritten |

**0.1 verdict:** **PASS** with execution root = worktree `ws/post-p10-answer-tool-convergence` @ `6b63df61…`. Loop may continue; product implementation must land on that worktree (or a descendant), not on the Cursor product-tip checkout alone.
