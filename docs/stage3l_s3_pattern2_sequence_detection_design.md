# Stage 3L-S3.8: Pattern #2 design — `sequence_detection` / `success_after_failure`

**Status:** Design only — **not implemented**, **not allowlisted**, **no observation window**.

**Explicit boundaries:**

- No `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED` change
- No entry on `ROUTE_AUTHORITY_OPERATION_COVERAGE_ALLOWLIST`
- No MCP/SPL execution
- No `selected_skill` authority change
- No manifest promotion in this stage

---

## Why pattern #2 after `cov.q046`

| Criterion | `cov.q046` (pilot #1) | Pattern #2 (`sequence_detection`) |
|-----------|----------------------|-----------------------------------|
| `primary_skill` | `aggregate_and_rank` | `sequence_detection` |
| Operation family | Top-N / rank | Ordered event sequence |
| SOC story | Excessive failed logins | Success after repeated failures (escalation-sensitive) |
| Manifest | Promoted + Step 7 closed | **No primary row today** — this design closes the S0 gap |

---

## Comparison: `sequence_detection` vs `threshold_anomaly` (deferred as #2)

| Criterion | `sequence_detection` | `threshold_anomaly` (e.g. `cov.q062`) |
|-----------|---------------------|--------------------------------------|
| vs cov.q046 | Different runtime family | Overlaps spike/count narrative with aggregate pilot |
| Fixture | New design closes gap | Row already in `pattern_coverage_v1.json` |
| Governance | Sample/template sequence; no live detection authority | Requires explicit `threshold_ref` / baseline policy |
| SOC fit | Success-after-failure correlation | Host/login spike thresholds |

**COE direction:** anchor pattern #2 on **sequence_detection**. Defer **threshold_anomaly** to a later pilot (pattern #3).

---

## Proposed coverage row (draft — do not commit to manifest until COE approves)

| Field | Value |
|-------|--------|
| **`coverage_id`** | `cov.q063.success_after_failed_logins_sample` |
| **`question_ref`** | `q0.q060` — “Which accounts had a successful login after repeated failures?” |
| **`pattern_id`** | `auth_success_after_failures` |
| **`primary_skill`** | `sequence_detection` |
| **`operation_type`** | `sequence_match` (per [`runtime_skill_catalog.py`](../backend/app/routing/runtime_skill_catalog.py)) |
| **`source_class`** | `okta_authentication_logs` |
| **`coverage_group`** | `template_only` (sample SPL; no vetted detection binding) |
| **`legacy_router_intent_hint`** | `attack_discovery` (bridge must be compatible) |

### Required slots

| Slot | Purpose |
|------|---------|
| `event_a` | Failed authentication events (predicate + metric) |
| `event_b` | Successful authentication after `event_a` |
| `join_entity` | `user` or `account` |
| `sequence_window` | Max gap between A and B (e.g. 1h) |
| `time_window` | Search window (e.g. last 24h) |

### Optional slots

`filters`, `exclusions`, `source_class` refinements.

### Evidence boundaries

- Auth index/sourcetype only (governed template).
- **No** `entity_context_lookup` / `notable_risk_lookup` as **primary**.
- **No** vetted `detection_ref` for sample pilot — use `sample_only` governance like cov.q046; catalog `vetted_sequence_detection_available` satisfied via **sample template + validator**, not live detection registry authority.

### Clarification triggers

- MITRE / playbook asks without alert or user context → `intent_clarification` (Stage 3J-C hygiene).
- Missing `join_entity` or `sequence_window` → `missing_required_slot` / human review.

### Fallback reasons

| Reason | When |
|--------|------|
| `missing_required_slot` | No user/account entity |
| `missing_sequence_window` | No bounded gap between fail and success |
| `validator_blocked` | Route plan fails S1 validator |
| `coverage_id_not_allowlisted` | Authority off or id not on allowlist (default) |
| `bridge_incompatible` | Legacy intent cannot map to `sequence_detection` |

---

## Observation input set (draft)

Mirror [`stage3l_s3_cov_q046_observation_inputs.json`](../backend/app/tests/fixtures/stage3l_s3_cov_q046_observation_inputs.json). Store draft under `docs/input/stage3l_s3_pattern2_observation_inputs.DRAFT.json` until COE opens a window.

### In-pattern (≥12)

Examples:

- “Which accounts had a successful login after repeated failures?”
- “Users who failed login then succeeded within an hour”
- “Show Okta accounts with success after multiple failed attempts today”
- “Correlate failed then successful authentication per user”

Expected route: `coverage_id` resolved, `primary_skill=sequence_detection`, `pattern_id=auth_success_after_failures`, `route_status=route_ready` (lab pilot only).

### Near-miss (≥3)

| Case | Why near-miss |
|------|----------------|
| Failed logins only (no success leg) | Missing `event_b` |
| Success without prior failure in window | Sequence order not satisfied |
| “Top users by failed logins” | Routes to aggregate pilot, not sequence |

### Missing-slot (≥3)

| Case | Expected blocker |
|------|------------------|
| “Success after failures” with no user scope | `missing_required_slot` / clarification |
| No time window | `missing_required_slot` |
| Ambiguous threshold without sequence | Clarification or threshold path — not in-pattern |

---

## COE approval gates (before any code authority)

| Gate | Requirement |
|------|-------------|
| G1 | This design doc reviewed |
| G2 | Draft observation inputs reviewed |
| G3 | Primary route-plan fixture + S1 validator tests for `sequence_match` |
| G4 | Bridge compatibility `attack_discovery` ↔ `sequence_detection` recorded in trace |
| G5 | **Separate** decision to add `coverage_id` to allowlist |
| G6 | **Separate** observation window (like cov.q046 Step 7) |
| G7 | **Separate** production authority cutover |

Pattern #1 (`cov.q046`) must complete enablement decision before G5–G7 for pattern #2.

---

## What this design does not do

- Add allowlist entry
- Enable operation authority
- Start observation runner in CI
- Change Experience Center golden answers
- Execute SPL or MCP

When live MCP arrives, pattern #2 should need **fixture + observation + allowlist decisions already on file** — not ad-hoc design under COE time pressure.
