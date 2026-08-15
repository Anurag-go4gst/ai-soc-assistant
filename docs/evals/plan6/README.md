# Plan 6 evidence directory

Artifacts for [plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md](../../../plans/2026-08-13_1440_production-activation-t4-serving-and-governance-readiness.md).

Loop runner already exists at [plans/LOOP_RUNNER_production-activation-t4-serving-and-governance-readiness.md](../../../plans/LOOP_RUNNER_production-activation-t4-serving-and-governance-readiness.md) — do not recreate it here.

## Contents

| Path | Item | Purpose |
|---|---|---|
| `P0_BASELINE.md` | P0 | Frozen SHA, defaults, targeted pytest |
| `flag_matrix.md` | P0.1 | Repo vs COE vs live VPS (UNKNOWN until A4) |
| `execution_path_map.md` | P0.1 | v2-wins ladder + paths that never hit the seam |
| `env_capture.schema.json` | P0.2 | Redacted env capture; rejects `token\|password\|secret\|api_key` keys |
| `vps_corpus_v1.json` | A2 | VPS query corpus |
| `runs/` | A4+ | Redacted harness output (no secrets) |
| `t4_serving_baseline.md` | D0 | T4 hop at production 2.0s (9/9 timeout, 0 accepted) |
| `t4_serving_options.md` | D1 | In-env serving comparison; all options non-viable at 2.0s |
| `t4_paraphrase_accuracy.md` | D2 | 0/8 accepted T4 contracts; L3–L5 residue; 0 widening |
| `execution_off_on_comparison.md` | B2 | Arm A/B/C comparison; merge vs v2-wins vs not-reachable |
| `c0_d3_stop_decisions.md` | C0 + D3 | Combined STOP: exec KEEP OFF (v2 N/A); T4 KEEP 2.0s/DEFAULT-OFF |
| `production_flag_profile.md` | C1 + D4 | Approved intended profile (not F2 persist, not F5 go-live) |
| `seam_equivalence.md` | C2 | KEEP OFF reachability refresh; 0 seams adopted; no fallback retirement |
| `c3_stop_decision.md` | C3 | KEEP 0 ADOPTED; deferred seam follow-up, not a production blocker |
| `mitre_11row_promotion_delta.md` | E1 | Offline 11-row DRAFT promotion analyst-visible delta; promoter not run |
| `e2_stop_decision.md` | E2 | KEEP DEFERRED; retain `DEFERRED_SEPARATE_GOVERNED_PROMOTION`; no promoter / ledger / map / catalog / recapture |
| `e3_stale_report_inventory.md` | E3 | Inventory of the six stale governance reports |
| `e3_stop_decision.md` | E3 | CONTINUE PRESERVING; policy unchanged; no regen/gitignore/harness redesign |
| `e4_protected_artifact_review.md` | E4 | Keep 15/15; no Plan 6 evidence files added to PROTECTED |
| `vps_safety_invariants.md` | F1 | F0 `/debug` invariants all PASS |
| `runs/integrated_vps.md` | F0 | 12-row intended-profile corpus; equivalent to Arm A; not go-live |
| `runs/f2_persistence.md` | F2 | Persist KEEP-OFF profile; recreate; 4-row smoke |

## Secrets

Env capture and run logs must **fail closed** if a key matches `token`, `password`, `secret`, or `api_key` (case-insensitive). Validator: `backend/app/evals/plan6_env_capture.py`. Allowed: flag **names** and booleans, model endpoint **host/role** without tokens, DB reachability boolean, MCP mode + connectivity boolean.
