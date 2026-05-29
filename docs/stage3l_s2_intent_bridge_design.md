# Stage 3L-S2: Intent-to-Operation Bridge — Design Note

**Status:** Design only — **no implementation** until this document is reviewed and signed off (same pattern as S0-core).

**Prerequisite:** [S1 complete](stage3l_s1_validator_spec.md) — runtime operation validator v2; `operation_type` authority in `runtime_skill_catalog.py`.

---

## Scope split (do not bundle casually)

| Sub-stage | Focus | Touches `/chat`? | Touches renderer? |
|-----------|--------|------------------|-------------------|
| **S2A** | Intent → allowed `primary_skill`(s) bridge (validation, lineage, explainability) | No change to `selected_skill` authority | No |
| **S2B** | `output_artifacts` vocabulary and consumer map (e.g. `candidate_spl_visible`) | No unless explicitly approved later | Design only first — maps which modules would read artifacts |

S1 explicitly excluded output/renderer changes. **S2B is a separate gate** from S2A implementation.

---

## Standing rules (carry from S1 into S2+)

1. **No `operation_type` drift** — manifest, taxonomy, tests, and docs may only use tokens from per-skill `allowed_operation_types` in [`runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py). No global `OperationType` enum yet.
2. **`spl_generation` is not a normal SOC operation family** — treat as output-mode / modifier unless this design explicitly decides otherwise (see Q2).
3. **`entity_context_lookup` / `notable_risk_lookup`** — post-enrichment in current coverage is **intended**; do not add primary fixtures unless product requires standalone lookup questions (e.g. privileged-user lookup as primary vs aggregate + enrichment).
4. **`hard_preconditions`** — remain S7; S2 does not enforce catalog preconditions.

---

## Design questions (answer before coding S2A)

### Q1. Bridge role: advisory, validating, or authoritative?

**Recommendation (initial):** **Validating + lineage only** in S2A.

- Bridge records `intent → allowed_operations[]` compatibility with normalized `route_plan.primary_skill`.
- Does **not** replace `selected_skill` or become routing authority (reserved for S3 pattern allowlist).
- Invalid combinations → recorded disagreement / validation finding, not silent rewrite.

| Mode | S2A? | S3+? |
|------|-------|------|
| Advisory (shadow compare) | Yes | Yes |
| Validating (block invalid intent↔operation pairs in shadow envelope) | Yes | Optional |
| Authoritative (`selected_skill` / route choice) | **No** | Per `coverage_id` allowlist only |

### Q2. Is `spl_generation` an intent or an output-format modifier?

**Recommendation (initial):** **Modifier** (output artifact), not a sole operation mapper.

- “Show me / generate candidate SPL” → `output_artifacts` includes `candidate_spl_visible` (or equivalent).
- Underlying SOC work may still be `aggregate_and_rank`, `threshold_anomaly`, `lookup_correlation`, etc.
- Bridge carries **two dimensions:**
  - `intent → allowed_operations[]`
  - `intent → output_artifacts[]`
- Do **not** map `spl_generation` → only two operations in S2A without explicit sign-off.

### Q3. Which operations are allowed under each legacy intent?

Draft matrix for review (not implementation):

| Legacy intent (`SKILL_ENUM`) | Allowed `primary_skill` (multi) | Notes |
|----------------------------|----------------------------------|--------|
| `attack_discovery` | aggregate, threshold, sequence, lookup, behavioral, multi_signal, entity_timeline | Investigation-shaped |
| `spl_generation` | *(via underlying operation)* + output modifier | See Q2 |
| `knowledge_recall` | metadata_discovery, entity_context_lookup, notable_risk_lookup | No SPL-as-primary |
| `alert_summary` | notable_risk_lookup, entity_context_lookup, entity_timeline | Evidence/summary shaped |

Refine in S2A sign-off; MITRE today routes to `knowledge_recall` (Stage 3J-C) — document, do not fold into `attack_discovery`.

### Q4. Where does bridge output appear?

**Recommendation:** `route_plan_shadow` / lineage / debug trace only — not analyst-visible answer text, not Experience Center golden fields.

### Q5. Block invalid combinations or only record disagreement?

**Recommendation:** **Record disagreement** in S2A (same as Q1F / 3J-K0). Deterministic route plan validator remains authority for plan shape; bridge adds intent↔operation compatibility layer.

### Q6. Will S2 touch `/chat` `selected_skill`?

**No.**

### Q7. Will S2 touch Experience Center?

**No** for S2A. Demo `expected_skill` stays on legacy four until S3 per-pattern migration.

### Q8. Output artifacts in S2 or S2B?

**S2B** — separate design doc section or follow-on file [`stage3l_s2_output_artifacts_design.md`](stage3l_s2_output_artifacts_design.md) (create when Q2–Q5 approved). Consumers to name: template renderer, evidence contract, context sufficiency, chat assembly — **no code in S2B until consumer map signed off**.

---

## S2A implementation sketch (after design sign-off)

- Module: `backend/app/routing/intent_to_operation_bridge.py`
- Tests: bridge completeness, invalid pairs, `spl_generation` modifier path
- Docs: `docs/stage3l_s2_intent_to_operation_bridge.md` (behavioral spec)
- Non-goals: SKILL_ENUM removal, harness/demo skill expectation changes, MCP/LLM execution

---

## S2 sign-off (empty until review)

| Reviewer | S2A approved | S2B approved | Date |
|----------|--------------|--------------|------|
| | ☐ | ☐ | |

---

## Verification (after S2A implementation only)

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```

Harness and demo skill expectations unchanged in S2A.
