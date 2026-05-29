# Stage 3L-S3 Trace Review Checkpoint

**Date:** 2026-05-29  
**Checkpoint commit:** `df11095` ([STAGE_3L_S0_TO_S8_SPINE.md](../plans/STAGE_3L_S0_TO_S8_SPINE.md))  
**Scope:** Review `intent_operation_bridge` and `route_authority_compare` after `b9ded3f` (S2A-FOLLOWUP + S3 Steps 1–2).  
**Verdict:** Safe to hold **S3 Step 3** until per-`coverage_id` gate design is written. No unexpected incompatible mappings in reviewed cases.

---

## Stage status (reviewer alignment)

| Stage | Status |
|-------|--------|
| S2A-FOLLOWUP | Done (`b9ded3f`) |
| S3 Step 1 | Done — dual-run shadow infrastructure |
| S3 Step 2 | Done — compare metadata on shadow + lineage |
| S3 Step 3 | **Not started** (correct) |
| S2B | **Not started** (correct) |

**Safe defaults confirmed:**

- `ROUTE_AUTHORITY_COMPARE_ENABLED=true` — observe/compare only
- `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false` — no authority migration

---

## How to inspect (production `/chat`)

1. POST `/api/chat` with representative `message`.
2. Expand `route_plan_shadow.intent_operation_bridge` and `route_plan_shadow.route_authority_compare`.
3. In `investigation_lineage.stages`, open `intent_operation_bridge` and `route_authority_compare` (`technical_output`).

When live LLM route-plan shadow is disabled and no test hook supplies a candidate, `primary_skill` is often `null` → `bridge_status: not_evaluated` (expected; not a false incompatibility).

---

## Case review matrix

| # | Scenario | `selected_skill` | `primary_skill` observed | `bridge_status` | `operation_authoritative_enabled` | Pass? |
|---|----------|------------------|---------------------------|-----------------|-----------------------------------|-------|
| 1a | Aggregate/ranking (live router, no shadow candidate) | `attack_discovery` | `null` | `not_evaluated` | `false` | Yes |
| 1b | Aggregate/ranking (mock valid route plan) | `attack_discovery` | `aggregate_and_rank` | `compatible` | `false` | Yes |
| 2a | Detection binding query (mock valid plan; preflight blocks missing vetted detection) | `attack_discovery` | `null` | `not_evaluated` | `false` | Yes — preflight `cannot_route_missing_detection` before candidate surfaces |
| 2b | Detection binding (validator-only; plan with `detection_ref`) | — | `behavioral_detection_binding` | `compatible` (if shadow applied) | — | Validator passes; shadow apply blocked by preflight on DGA-style query |
| 3a | Knowledge/SOP (live, no candidate) | `knowledge_recall` | `null` | `not_evaluated` | `false` | Yes |
| 3b | Knowledge/SOP (mock `metadata_discovery`) | `knowledge_recall` | `metadata_discovery` | `compatible` | `false` | Yes |
| 4a | SPL generation (live, no candidate) | `spl_generation` | `null` | `modifier_only` | `false` | Yes |
| 4b | SPL generation (mock underlying op) | `spl_generation` | `aggregate_and_rank` | `modifier_only` | `false` | Yes — `output_artifacts_deferred_to_s2b`, no op restriction |
| 5 | Experience Center demo | `attack_discovery` | N/A (`route_plan_shadow` **null**) | N/A | N/A | Yes |
| — | **Negative:** attack_discovery + metadata_discovery shadow | `attack_discovery` (unchanged) | `metadata_discovery` | `incompatible` | `false` | Yes — 1 bridge disagreement; no route rewrite |

**No rewrite observed:** `selected_skill` and shadow `primary_skill` inputs unchanged by bridge/compare; incompatible case keeps `selected_skill=attack_discovery`.

**Disagreement separation:** Q1F `route_plan_shadow.disagreements` stays separate from `intent_bridge_disagreements` in `route_authority_compare`.

---

## Observations

1. **`not_evaluated` is common on live `/chat`** when `candidate_available=false` (LLM route-plan shadow off / no hook). This is correct: do not treat as incompatibility.
2. **`spl_generation` → `modifier_only`** even without observed `primary_skill` (live case 4a). Modifier path does not require runtime op pairing.
3. **Detection binding** requires a validator-passing plan (`detection_ref` slot); coverage row `cov.q007.dga_detection_binding` is detection-dependent and not Step 3 pilot material without registry + promotion work.
4. **Experience Center** unchanged: `route_plan_shadow=null`, `demo_mode=true`.

---

## Unexpected incompatible mappings

**None** in reviewed matrix. The only `incompatible` case was intentional (legacy `attack_discovery` vs shadow `metadata_discovery`).

---

## S3 Step 3 — pilot `coverage_id` recommendation

**Do not enable Step 3 yet.** When designing the per-`coverage_id` gate, prefer a row that already has:

| Criterion | Suggested pilot |
|-----------|-----------------|
| Promoted Q4 manifest row | `cov.q046.excessive_failed_logins_sample` |
| `primary_skill` | `aggregate_and_rank` |
| Primary route-plan fixture | Yes (`test_route_plan_stage3k_r2` / R1 aggregate plan) |
| Bridge with `attack_discovery` | `compatible` (mocked) |
| S1 validator | Exercised in CI |
| Post-enrichment only lookups | `notable_risk_lookup` in post_enrichment — **not** primary |

**Explicitly not Step 3-ready (fixture gate):**

| `primary_skill` | Bridge-allowed | Step 3 authority |
|-----------------|----------------|------------------|
| `entity_context_lookup` | Yes | **No** — no primary fixture |
| `notable_risk_lookup` | Yes | **No** — post-enrichment only today |

**Defer:** `cov.q007.dga_detection_binding` until detection registry + vetted `detection_ref` path is stable for authority migration.

---

## Step 3 gate checklist (design next — no implementation)

Before `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=true` for any `coverage_id`:

- [ ] Allowlist contains exactly one pilot `coverage_id` (recommend `cov.q046.excessive_failed_logins_sample` pending COE sign-off)
- [ ] Primary route-plan fixture + validator test exists for that row’s `primary_skill`
- [ ] Bridge `compatible` for expected legacy intent pairing
- [ ] Fallback to `selected_skill` on block/incompatible
- [ ] Harness + Experience Center regression for non-pilot ids
- [ ] No authority for `entity_context_lookup` / `notable_risk_lookup` as primary until fixtures exist

---

## Next move

1. **COE / analyst:** Spot-check 5–8 live queries in UI technical trace (same fields as table above).
2. **Engineering:** Write `docs/stage3l_s3_step3_coverage_gate_design.md` (per-`coverage_id` allowlist + fallback semantics) — **not** Step 3 code.
3. Leave unstaged: `stage3l_s2_output_artifacts_design.md`, `.gitkeep`, `.claude/`, `docs/input/`.

---

## Verification commands (re-run locally)

```bash
cd backend && python3 -m pytest app/tests/test_intent_operation_bridge_shadow_stage3l_s2a1.py app/tests/test_route_authority_compare_stage3l_s3.py -q
cd backend && python3 -m pytest -q
python3 -m test_harness.harness.runner --json
```
