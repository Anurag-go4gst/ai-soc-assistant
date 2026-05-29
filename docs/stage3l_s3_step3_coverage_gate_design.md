# Stage 3L-S3 Step 3: Per-`coverage_id` Operation Authority Gate — Design Only

**Status:** **Design only — no implementation, no authority enablement.**  
**Design commit:** `e412c7c` ([STAGE_3L_S0_TO_S8_SPINE.md](../plans/STAGE_3L_S0_TO_S8_SPINE.md))  
**Prerequisite:** [S3 trace review checkpoint](stage3l_s3_trace_review_checkpoint.md) (`df11095`).  
**Parent:** [stage3l_s3_route_authority_migration.md](stage3l_s3_route_authority_migration.md) (Steps 1–2 done at `b9ded3f`).

> **This document does not approve operation-authoritative behavior.** It specifies how Step 3 *would* be gated when COE explicitly approves a pilot.

---

## What Step 3 would change (when implemented later)

Today:

- `selected_skill` = legacy `SKILL_ENUM` intent (authoritative for `/chat`).
- `route_plan.primary_skill` = runtime operation (shadow/validator only).
- `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false` globally.

Step 3 (future code) would allow **one allowlisted `coverage_id`** to treat a **validated** `route_plan.primary_skill` as authoritative for routing/planning **for matching questions only**, with mandatory fallback to `selected_skill` on block, incompatibility, or missing plan.

**Out of scope for Step 3 design / implementation in this stage:**

- Experience Center golden-field changes without explicit parallel update
- Harness `expected_skill` changes for non-pilot ids
- MCP/SPL execution
- Final LLM synthesis / Answer Guard
- `output_artifacts` / S2B renderer work

---

## Candidate pilot (not approved)

| Field | Value |
|-------|--------|
| **`coverage_id`** | `cov.q046.excessive_failed_logins_sample` |
| **Disposition** | **Candidate pilot for gate design and future COE review only** |
| **NOT** | Approved operation-authoritative behavior |

**Why this row is a reasonable design candidate:**

| Criterion | `cov.q046` |
|-----------|------------|
| Promoted Q4 manifest row | Yes — [`pattern_coverage_v1.json`](../backend/app/coverage/pattern_coverage_v1.json) |
| `primary_skill` | `aggregate_and_rank` |
| `pattern_id` | `top_failed_okta_login_users` |
| Primary route-plan fixture | Yes — R1/R2 aggregate tests (`_valid_route_plan_candidate`) |
| S1 validator | Exercised in CI for `aggregate_and_rank` / `top_n` |
| Legacy intent bridge | `attack_discovery` + `aggregate_and_rank` → **compatible** (trace review) |
| Post-enrichment | May include `notable_risk_lookup` — **post-enrichment only**, not primary authority |

**COE must explicitly sign off** before any allowlist entry is enabled in config. Until then, `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED` stays `false`.

---

## Explicitly blocked from Step 3 allowlist (design)

These must **not** appear on `ROUTE_AUTHORITY_COVERAGE_ALLOWLIST` (or equivalent) until blockers are cleared and COE re-approves.

### Primary skills — fixture gate

| `primary_skill` | Block reason | Step 3 |
|-----------------|--------------|--------|
| `entity_context_lookup` | No primary route-plan fixture; post-enrichment-only today | **Blocked** |
| `notable_risk_lookup` | No primary route-plan fixture; post-enrichment-only today | **Blocked** |

Bridge may mark these as bridge-permitted for S2A; that does **not** imply operation-authoritative readiness.

### Coverage rows — dependency / preflight gate

| `coverage_id` | Block reason | Step 3 |
|---------------|--------------|--------|
| `cov.q007.dga_detection_binding` | Detection-dependent; live preflight `cannot_route_missing_detection` / missing vetted detection path | **Blocked** |
| (extend list) | Any row without promoted manifest + S1-valid primary fixture + passing bridge for expected legacy intent | **Blocked** |

Related deferred row: `cov.q008.beaconing_detection_binding` — same detection-dependent class; treat like q007 until registry + preflight story is stable.

---

## Proposed gate model (implementation deferred)

### Global kill-switch (unchanged until COE pilot)

```text
ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false   # default; only true in approved pilot env
```

### Per-`coverage_id` allowlist (design shape)

```text
ROUTE_AUTHORITY_COVERAGE_ALLOWLIST=cov.q046.excessive_failed_logins_sample
```

- Closed-world: only listed ids may enter operation-authoritative path.
- Empty list + global false = current production behavior.

### Per-request decision record (shadow + lineage)

Extend `route_authority_compare` (or sibling block) when Step 3 is implemented:

| Field | Meaning |
|-------|---------|
| `coverage_id_resolved` | Matched manifest row, if any |
| `operation_authority_eligible` | Allowlist + gates passed |
| `operation_authority_applied` | Actually used `primary_skill` for planning |
| `authority_fallback_reason` | e.g. `bridge_incompatible`, `validator_blocked`, `not_on_allowlist`, `global_disabled` |
| `authority_holder` | `legacy_selected_skill` \| `route_plan_primary_skill` |

### Gate chain (all required for `operation_authority_applied=true`)

```text
1. ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED == true
2. coverage_id in ROUTE_AUTHORITY_COVERAGE_ALLOWLIST
3. coverage_id NOT in explicit denylist (entity_context / notable_risk primary; q007; …)
4. route_plan validated (route_ready, S1 contract satisfied)
5. intent_operation_bridge.bridge_status == compatible
6. primary_skill matches manifest row primary_skill for that coverage_id
7. Fallback: any failure → selected_skill unchanged, log authority_fallback_reason
```

### Consumer impact (Step 3 implementation only)

Before enabling pilot for `cov.q046`:

- [ ] Harness: add parallel expectation or pilot-only case — do not change global `expected_skill` until COE agrees
- [ ] Experience Center: no change unless demo scenario bound to `cov.q046`
- [ ] `workflow_planner` / tool_plan: document whether `primary_skill` drives tool_plan or legacy intent only
- [ ] UI: show `authority_holder` in technical trace when Step 3 runs

---

## Relationship to S3 Steps 1–2

| Step | Behavior |
|------|----------|
| 1–2 (done) | Observe `selected_skill` vs `primary_skill`; bridge + compare; **no authority change** |
| 3 (this design) | Optional allowlist-driven authority for one manifest row after COE sign-off |
| 4 | Broader consumer migration per pattern |

Steps 1–2 remain sufficient for ongoing trace review until COE approves pilot implementation.

---

## COE gate review (required before Step 3 code)

Checklist review: [stage3l_s3_step3_coe_gate_review.md](stage3l_s3_step3_coe_gate_review.md) (2026-05-29). **Verdict: NOT READY** — COE approval + fallback tests required.

## Sign-off (required before Step 3 code)

| Reviewer | Pilot `cov.q046` approved for **implementation** | Step 3 gate design approved | Date |
|----------|--------------------------------------------------|----------------------------|------|
| COE / Anurag | ☐ (candidate only today) | ☐ | |

**Notes:**

- Approving **this design** is not approving **operation-authoritative runtime behavior**.
- Implementing Step 3 requires a separate commit series and regression plan (harness, trace, fallback tests).

---

## Verification (design phase only)

No new runtime tests for Step 3 until implementation.

```bash
# Regression for Steps 1–2 only
cd backend && python3 -m pytest app/tests/test_intent_operation_bridge_shadow_stage3l_s2a1.py app/tests/test_route_authority_compare_stage3l_s3.py -q
```
