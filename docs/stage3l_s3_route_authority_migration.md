# Stage 3L-S3: Route Authority Migration

**Status:** Steps 1–2 implemented (shadow/compare only). Step 3+ gated on promoted `coverage_id`.

**S3 Steps 1–2 commit:** `b9ded3f` ([STAGE_3L_S0_TO_S8_SPINE.md](../plans/STAGE_3L_S0_TO_S8_SPINE.md))

**Prerequisites:** S1 (`db7072f`), S2A bridge (`7370595`), S2A-FOLLOWUP shadow wiring.

---

## Vocabulary (do not conflate)

| Field | Layer | Authority today |
|-------|--------|-----------------|
| `selected_skill` | Legacy `SKILL_ENUM` (four intents) | **Yes** — `/chat` router |
| `route_plan.primary_skill` | Runtime operation (ten skills) | Shadow/validator only |
| `intent_operation_bridge` | Compatibility matrix | Shadow/lineage only |
| `route_authority_compare` | Unified dual-run record | Shadow/lineage only |

Q1F shadow may label `deterministic_primary_skill` in code paths; that value is **legacy `selected_skill`**, not runtime `primary_skill`.

---

## Migration steps

| Step | Scope | Authority change | Gate |
|------|--------|------------------|------|
| **1** | Dual-run visible: `selected_skill` + `route_plan_shadow` | None | After S2A |
| **2** | `route_authority_compare` envelope + intent bridge status + 3J-K0 `comparison` | None | After S2A-FOLLOWUP |
| **3** | Operation-authoritative routing per `coverage_id` | **Yes** — per allowlist row | S1 + S5 + S6 promoted row |
| **4** | Consumer migration (harness, demo, workflow) | Per pattern | Step 3 for that id |

Steps 1–2 must **not** change `selected_skill`, analyst answer text, Experience Center, renderer, MCP/SPL execution.

---

## Configuration (Steps 1–2)

| Env / setting | Default | Meaning |
|---------------|---------|---------|
| `ROUTE_AUTHORITY_COMPARE_ENABLED` | `true` | Emit `route_authority_compare` on shadow |
| `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED` | `false` | Step 3+ kill-switch; must stay false until allowlisted |

Step 3 will add a per-`coverage_id` allowlist (promoted Q4 manifest rows only).

---

## Shadow fields

- `intent_operation_bridge` — S2A-FOLLOWUP (intent ↔ operation compatibility).
- `route_authority_compare` — S3 Steps 1–2 unified compare:
  - `selected_skill`, `route_plan_primary_skill_observed`
  - `legacy_skill_router_*` from 3J-K0 `comparison`
  - `intent_operation_bridge_status`, `intent_bridge_compatible`
  - `route_plan_shadow_disagreements` (Q1F operation-layer) vs `intent_bridge_disagreements` (S2A)
  - `authority_holder`: `legacy_selected_skill`
  - `operation_authoritative_enabled`: `false`

Lineage sub-stage `route_authority_compare` when block present.

---

## Critical path (Step 3+)

```text
S0-core → S1 → S5 → S6 (one promoted coverage_id) → S3 Step 3 for that id only
```

Do not enable operation-authoritative mode without a promoted coverage row.

---

## Trace review

See [stage3l_s3_trace_review_checkpoint.md](stage3l_s3_trace_review_checkpoint.md) (2026-05-29): Steps 1–2 verified; Step 3 held.

## Verification

```bash
cd backend && python3 -m pytest app/tests/test_route_authority_compare_stage3l_s3.py -q
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```
