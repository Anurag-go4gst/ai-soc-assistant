# Stage 3L-S2: Intent-to-Operation Bridge — Design Note

**Status:** **S2A implementation complete** (2026-05-29) — library + tests landed; shadow/lineage wiring deferred. **S2B** remains unsigned (separate review).

**Prerequisite:** [S1 complete](stage3l_s1_validator_spec.md) (`db7072f`) — runtime operation validator v2; `operation_type` authority in `runtime_skill_catalog.py`.

---

## Scope split (do not bundle casually)

| Sub-stage | Focus | Touches `/chat`? | Touches renderer? |
|-----------|--------|------------------|-------------------|
| **S2A** | Intent → allowed `primary_skill`(s) bridge (validation, lineage, explainability) | No change to `selected_skill` authority | No |
| **S2B** | `output_artifacts` vocabulary and consumer map (e.g. `candidate_spl_visible`) | No unless explicitly approved later | Design only — **not signed off** |

S1 explicitly excluded output/renderer changes. **S2B is a separate gate** from S2A implementation.

---

## Standing rules (carry from S1 into S2+)

1. **No `operation_type` drift** — manifest, taxonomy, tests, and docs may only use tokens from per-skill `allowed_operation_types` in [`runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py). No global `OperationType` enum yet.
2. **`spl_generation` is an output-mode modifier in S2A** — does not restrict runtime operation compatibility; does not implement `candidate_spl_visible` (S2B). See [Q2 / `spl_generation` S2A behavior](#q2-spl_generation--output-modifier-not-operation-family).
3. **`entity_context_lookup` / `notable_risk_lookup`** — post-enrichment in current coverage is **intended**; do not add primary fixtures unless product requires standalone lookup questions.
4. **`hard_preconditions`** — remain S7.
5. **Bridge vocabulary** — use exact `primary_skill` IDs from `runtime_skill_catalog.py`; no shorthand (`aggregate`, `threshold`, etc.).

---

## Design questions (signed answers for S2A)

### Q1. Bridge role: advisory, validating, or authoritative?

**S2A:** Validating + lineage only.

- Bridge records compatibility between legacy intent (`SKILL_ENUM`) and normalized `route_plan.primary_skill`.
- Does **not** replace `selected_skill` (S3 per `coverage_id` only).
- Invalid combinations → **disagreement recorded**, not silent rewrite.

| Mode | S2A? | S3+? |
|------|-------|------|
| Advisory (shadow compare) | Yes | Yes |
| Validating (intent↔operation compatibility) | Yes | Optional |
| Authoritative (`selected_skill` / route choice) | **No** | Per `coverage_id` allowlist only |

### Q2. `spl_generation` — output modifier, not operation family

**S2A does not restrict** which runtime `primary_skill` values are valid when `selected_skill` / routed intent is `spl_generation`.

Compatibility is determined by the **underlying** `route_plan.primary_skill` after S1 validation, not by narrowing `spl_generation` to a small operation subset.

**S2A records (bridge metadata only — no renderer / output_artifacts implementation):**

| Field | Value |
|-------|--------|
| `intent_modifier` | `candidate_spl_requested` |
| `output_artifact_hint` | `candidate_spl_visible` *(deferred — S2B owns tokens)* |
| `underlying_operation` | `route_plan.primary_skill` after validator |
| `spl_generation_modifier_detected` | `true` when intent is `spl_generation` |
| `output_artifacts_deferred_to_s2b` | `true` |

S2A must **not** implement `candidate_spl_visible` or touch renderer/response shape. S2B defines artifact tokens and consumers.

### Q3. Allowed `primary_skill` per legacy intent (exact IDs)

Canonical mapping for `intent_to_operation_bridge.py` and tests. All values must match [`RuntimeSkill`](../backend/app/routing/route_plan_models.py) / `runtime_skill_catalog.py`.

| Legacy intent (`SKILL_ENUM`) | Allowed `primary_skill` values |
|------------------------------|------------------------------|
| `attack_discovery` | `aggregate_and_rank`, `threshold_anomaly`, `sequence_detection`, `lookup_correlation`, `behavioral_detection_binding`, `multi_signal_correlation`, `entity_timeline` |
| `spl_generation` | **No `allowed_primary_skills` restriction in S2A** — see Q2; `underlying_operation` = validated `route_plan.primary_skill` |
| `knowledge_recall` | `metadata_discovery`, `entity_context_lookup`, `notable_risk_lookup` |
| `alert_summary` | `notable_risk_lookup`, `entity_context_lookup`, `entity_timeline` |

**MITRE / SOP prompts:** Today deterministic routing sends MITRE asks to `knowledge_recall` (Stage 3J-C). Bridge documents that; do not fold into `attack_discovery`.

**Unknown intent** → reject. **Unknown `primary_skill`** → reject (validator already blocks; bridge records incompatibility).

#### Addendum — primary fixture gate

`entity_context_lookup` and `notable_risk_lookup` may be **bridge-permitted** as primary operations for compatibility analysis (see Q3 matrix), but they are **fixture-absent** as standalone primary route plans today (post-enrichment-only in current coverage).

They remain **non-authoritative for S3 migration** until each has a valid primary route-plan fixture and passing validator test. This mirrors the S1 `sequence_detection` primary gate and prevents bridge permission from being mistaken for operation-authoritative readiness.

| `primary_skill` | Bridge-allowed (S2A) | Primary route-plan fixture | S3 authority-ready |
|-----------------|----------------------|---------------------------|--------------------|
| `sequence_detection` | Yes | **Required in S1** — gate met (`db7072f`) | After S3 allowlist + coverage row |
| `entity_context_lookup` | Yes | **Absent** — do not treat as gap to “fix” in S2A | No — fixture + validator test first |
| `notable_risk_lookup` | Yes | **Absent** — intentional post-enrichment today | No — fixture + validator test first |

### Q4. Where does bridge output appear?

`route_plan_shadow` / lineage / debug trace only — not analyst answer text, not Experience Center golden fields.

Prefer **no** `routes_chat.py` changes in the first S2A commit unless strictly shadow/lineage metadata; default is **no chat route changes**.

### Q5. Block or record disagreement?

**Record disagreement** only (same posture as Q1F / 3J-K0).

### Q6. `/chat` `selected_skill`?

**No change.**

### Q7. Experience Center?

**No change** to `expected_skill` or demo golden fields.

### Q8. Output artifacts?

**S2B only** — see [`stage3l_s2_output_artifacts_design.md`](stage3l_s2_output_artifacts_design.md). Unsigned.

---

## S2A implementation boundary (first commit)

**In scope:**

- [`backend/app/routing/intent_to_operation_bridge.py`](../backend/app/routing/intent_to_operation_bridge.py)
- [`backend/app/tests/test_intent_to_operation_bridge_stage3l_s2a.py`](../backend/app/tests/test_intent_to_operation_bridge_stage3l_s2a.py)
- This design doc (status + any behavioral addendum)
- [`plans/STAGE_3L_S0_TO_S8_SPINE.md`](../plans/STAGE_3L_S0_TO_S8_SPINE.md) (status / commit hash when landed)

**Out of scope for first S2A commit:**

- `routes_chat.py` (unless later commit adds shadow-only lineage fields — prefer defer)
- Response schemas / renderer / `output_artifacts` execution
- `SKILL_ENUM` removal, harness, Experience Center, MCP/SPL execution

---

## S2A tests must prove

- [x] All four legacy intents (`SKILL_ENUM`) covered in bridge map
- [x] Unknown legacy intent rejected
- [x] Unknown `primary_skill` rejected or recorded incompatible
- [x] Valid intent → `primary_skill` pairs pass compatibility check
- [x] Invalid intent → `primary_skill` pairs return **disagreement**, not rewrite
- [x] `spl_generation`: modifier flags set; **no** operation-family restriction; `output_artifacts_deferred_to_s2b=true`
- [x] No `/chat` `selected_skill` behavior change (unit-level; no route integration test required in S2A if bridge is library-only)
- [x] No Experience Center `expected_skill` change
- [x] No MCP/SPL execution path change

---

## S2 sign-off

| Reviewer | S2A approved | S2B approved | Date |
|----------|--------------|--------------|------|
| Anurag / review | ☑ | ☐ | 2026-05-29 |

**Notes:** S2A approved after exact-ID matrix, `spl_generation` modifier behavior (Q2), and primary fixture gate addendum. S2B pending separate review (output artifacts only — do not sign S2B when approving S2A).

---

## Verification (after S2A implementation)

```bash
cd backend && python3 -m pytest app/tests/test_intent_to_operation_bridge_stage3l_s2a.py -q
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```

| Check | Result (2026-05-29) |
|-------|---------------------|
| S2A pytest | 10 passed |
| Backend pytest | 540 passed |
| Harness | 6/6 |
| `/chat` / Experience Center / MCP | Unchanged (library-only) |

Harness and demo skill expectations unchanged in S2A.
