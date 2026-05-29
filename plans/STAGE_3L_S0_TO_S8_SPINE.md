# Stage 3L — S0 → S8 Spine

Canonical index for runtime operation governance (post Stage 3K Q4/Q4A).  
**Substrate (immutable):** [STAGE_3K_Q1C_TO_Q4_SPINE.md](STAGE_3K_Q1C_TO_Q4_SPINE.md) Section 1.

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

## Checkpoint judgment (2026-05-29)

| Stage | Verdict |
|-------|---------|
| **3L-S0** | Done / signed off |
| **3L-S1** | Done — runtime operation validator v2; safety preserved; execution disabled; router authority unchanged |
| **Next** | COE gate review sign-off ([S3.3 review](docs/stage3l_s3_step3_coe_gate_review.md)); S2B — **no Step 3 code** until blockers cleared |

## Stage index

| Code | Focus | Spec / audit | Status | Commit |
|------|-------|--------------|--------|--------|
| S0-core | Contract field audit + `operation_type` canon | [docs/stage3l_s0_runtime_operation_contract_audit.md](../docs/stage3l_s0_runtime_operation_contract_audit.md) | Done / signed off | `db7072f` |
| S1 | Validator v2 per S0 | [docs/stage3l_s1_validator_spec.md](../docs/stage3l_s1_validator_spec.md) | Done | `db7072f` |
| S2A | Intent↔operation bridge | [docs/stage3l_s2_intent_bridge_design.md](../docs/stage3l_s2_intent_bridge_design.md) | Done — library (`7370595`) + shadow follow-up | `7370595` |
| S2A.1 | Bridge on `route_plan_shadow` | same | Done | `b9ded3f` |
| S2B | Output artifacts design | [docs/stage3l_s2_output_artifacts_design.md](../docs/stage3l_s2_output_artifacts_design.md) | Design — pending review (not signed) | — |
| S3 | Route authority migration | [docs/stage3l_s3_route_authority_migration.md](../docs/stage3l_s3_route_authority_migration.md) | Steps 1–2 done; Step 3 design only | `b9ded3f` |
| S3.3 | Step 3 coverage gate (design) | [docs/stage3l_s3_step3_coverage_gate_design.md](../docs/stage3l_s3_step3_coverage_gate_design.md) | Design + [COE gate review](../docs/stage3l_s3_step3_coe_gate_review.md) — **not ready** | `e412c7c` |
| S3 trace | Steps 1–2 trace review | [docs/stage3l_s3_trace_review_checkpoint.md](../docs/stage3l_s3_trace_review_checkpoint.md) | Done | `df11095` |
| S4 | Layered skill registry | — | Proposed | — |
| S5 | Q4A promotion workflow | [tools/coverage_authoring/README.md](../tools/coverage_authoring/README.md) | Q4A done (`0e2cd30`) | — |
| S6 | 105-Q mapping + manifest promotion | [docs/soc_question_taxonomy_stage3k_q0.md](../docs/soc_question_taxonomy_stage3k_q0.md) | Proposed | — |
| S7 | `hard_preconditions` runtime enforcement | — | Proposed | — |
| S8 | Governance readiness freeze | — | Proposed | — |

**Commit hash rule:** Update the Commit column when the stage lands (same pattern as Stage 3K Section 9).

## Standing rules (S2 onward)

- No manifest or taxonomy `operation_type` token outside `runtime_skill_catalog.py` per-skill allowlists.
- `spl_generation`: S2A modifier only (`candidate_spl_requested`); no operation restriction; artifacts deferred to S2B.
- Do not add primary fixtures for `entity_context_lookup` / `notable_risk_lookup` unless product requires standalone lookup (post-enrichment-only is intentional today).
- `hard_preconditions` catalog enforcement remains **S7** (`source_available`, `lookup_freshness`, `detection_vetted`, `template_available`, `evidence_contract_available`, etc.).

## Critical path (first operation-authoritative pattern)

```text
S0-core sign-off → S1 → S5 → S6 (one promoted coverage_id) → S3 Step 3 for that id only
```

S3 Steps 1–2 (shadow/compare) may run after S2A without a manifest row.

## S0-core vs S0-parallel

| Track | Blocks S1? |
|-------|------------|
| S0-core audit + enum decision | Yes |
| This spine, dual-run inventory, consumer lists | No |

## S1 verification (recorded)

| Check | Result |
|-------|--------|
| Backend pytest | 554 pass (post S3 Steps 1–2) |
| Harness default | 6/6 |
| `/chat` `selected_skill` | Unchanged |
| MCP / SPL execution | Disabled |

## Required verification (every implementation stage)

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```
