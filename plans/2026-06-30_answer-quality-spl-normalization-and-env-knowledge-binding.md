---
name: Answer quality — SPL normalization (paraphraser) + Environment-Knowledge index binding
status: Proposed
owner: unassigned
created: 2026-06-30
related:
  - plans/2026-06-29_conditional-pipeline-canonical-dispatch.md (dispatch canonicalization — DONE/merged)
  - wide-sweep-routing-gap (memory)
  - spl-eval-vs-live-env-drift (memory)
---

# Answer quality: SPL normalization + Environment-Knowledge binding + routing coverage

Tracks the answer-quality gaps found in live COE verification (2026-06-30). The
canonical-dispatch plumbing is correct and safe (fail-closed, review-only); these
are **content/relevance** gaps, separate from dispatch. Curated evals pass
(soc_clean 120/120, cisco 50/50); free-text phrasings expose the gaps below.

## Root-cause analysis (from live traces)

### Finding A — non-SOC-STD deterministic skeleton is rejected, not normalized (P1)
Query: "Which users have excessive failed logins across Windows hosts in the last hour".
- `generation_mode = deterministic_user_bound_skeleton`,
  `selected_candidate_spl_provider = use_case_catalog_default_raw_template`.
- Candidate SPL: `search (index=*) | eval event_code_norm=... | where event_code_norm IN (4625) | table ... | head 100`.
- `reject_reasons`: `disallowed_command:eval,table`, `disallowed_index`,
  `missing_aggregation`, `missing_binding:group_by_user`, `wildcard_index_not_allowed`,
  `missing_sourcetype`, ... (9 total) → HIL `intent_clarification`/"source profile missing".

**Root cause:** the catalog *default raw template* (skeleton builder) emits a
non-SOC-STD query (wildcard index, `eval`/`table`, no `stats` aggregation, no
group-by on the asked entity `user`). It hits the validator **raw** and is
rejected. There is no normalization/repair step between skeleton generation and
validation. The same gap applies to free-form LLM SPL.

### Finding B — index/sourcetype not bound from Environment Knowledge (P1)
- `spl_source_resolve = {}` (empty) on the failing turn — the COE Environment
  Knowledge map was never consulted for this candidate, so `index=*` stayed a
  wildcard and was rejected instead of being bound to the tenant's configured
  index/sourcetype (or a `<placeholder>` → COE-HIL).

**Root cause:** the skeleton/raw-template path does not flow through
`resolve_spl_source_profile` (the COE `coe_env` tier). Index/sourcetype binding
is only wired on the governed-template / token-SPL paths, not the
`use_case_catalog_default_raw_template` skeleton.

### Finding C — "explain X" over-routes to SPL; MITRE not auto-mapped (P2)
Query: "Explain MITRE T1110 brute force and how to detect it in Splunk" →
`selected_skill = spl_generation` (not `knowledge_recall`); a clean SPL draft is
produced but the conceptual explanation is thin and `mitre_decision.status = None`
even though T1110 is named in the query.

**Root cause:** "detect ... in Splunk" trips the SPL intent over the knowledge
intent; MITRE technique IDs named in the query are not auto-mapped into
`mitre_mappings` for knowledge turns.

## Target behavior (user direction)

1. **Once the producer (LLM or skeleton) emits SPL, normalize it via the
   deterministic paraphraser to SOC-STD** — never surface/reject raw non-compliant
   SPL. Repair: `eval`/`table` → allowed projection, inject `stats` aggregation +
   group-by on the asked entity, strip wildcard index, enforce time bound + head.
2. **All index/sourcetype values come from Environment Knowledge (COE map)** via
   `resolve_spl_source_profile` on every SPL path. If a required slot is unmapped,
   leave the COE `<placeholder>` and raise the `spl_source_profile_clarification`
   HIL — never `index=*`, never a fabricated index.

---

## Workstreams (atomic; Do / Verify / Depends / Evidence)

### WS1 — Mandatory SPL normalization (paraphraser) before validation
- [ ] **Do:** route every candidate SPL (skeleton + free-form LLM) through
      `deterministic_spl_repair.repair_spl_candidate` (or the
      `llm_plan_compiler` plan→compile shape) BEFORE `validate_spl`, so output is
      SOC-STD by construction (allowed commands, coalesce `stats` aggregation,
      group-by asked entity, strftime-after-stats, time bound, `head 100`).
      **Verify:** the failed-logins-windows query yields an approved/clean SPL (or
      a placeholder-only lab draft), not 9 reject reasons. `pytest` new case +
      live re-probe trace shows `generation_mode` normalized, 0 `disallowed_command`.
      **Depends:** none. **Evidence:** _____.
- [ ] **Do:** keep normalization deterministic + review-only; never flip
      `execution_eligible`. **Verify:** `execution_eligible=false` retained;
      governance byte-identical on curated evals. **Evidence:** _____.

### WS2 — Environment-Knowledge index/sourcetype binding on ALL SPL paths
- [ ] **Do:** wire `resolve_spl_source_profile` (COE `coe_env` tier) into the
      `use_case_catalog_default_raw_template` skeleton path (currently
      `spl_source_resolve={}`). Replace `index=*`/fabricated index with the
      COE-resolved value or a `<stem>` placeholder.
      **Verify:** failing turn shows non-empty `spl_source_resolve` with
      `tiers_used` incl `coe_env`/`policy_env`; no `wildcard_index_not_allowed`.
      **Evidence:** _____.
- [ ] **Do:** when a required index/sourcetype stem is unmapped in the COE map,
      raise `spl_source_profile_clarification` HIL (not a wildcard, not a reject).
      **Verify:** unmapped → HIL with the specific missing slot named.
      **Evidence:** _____.

### WS3 — Skeleton/raw-template quality (or retire in favor of compiler)
- [ ] **Do:** make `use_case_catalog_default_raw_template` emit SOC-STD shape, OR
      route catalog-class questions to the governed template / plan-compiler before
      the raw skeleton. **Verify:** catalogue-class phrasings (failed logins by
      user, top talkers, etc.) produce governed/normalized SPL, not raw skeleton.
      **Evidence:** _____.

### WS4 — Knowledge-vs-SPL routing + MITRE auto-mapping (P2)
- [ ] **Do:** "explain/what is <technique>" routes to `knowledge_recall` even with
      "detect in Splunk"; attach the detection SPL as a secondary artifact, not the
      primary answer. **Verify:** T1110 explain query → knowledge_recall +
      explanation + optional SPL. **Evidence:** _____.
- [ ] **Do:** auto-map MITRE technique IDs named in the query into
      `mitre_mappings` (candidate tier, never confirmed without evidence).
      **Verify:** T1110 query → `mitre_decision`/`mitre_mappings` includes T1110
      (candidate). **Evidence:** _____.

### WS5 — Eval coverage (headline metric = free-text, not curated)
- [ ] **Do:** add a free-text answer-quality probe set (out-of-eval phrasings:
      paraphrases of the 105 + power-grid) scoring relevance/normalization/binding/
      honesty; non-gating first. **Verify:** `scripts/eval_*` reports per-class
      pass; track baseline. **Evidence:** _____.

## Out of scope
- Changing dispatch canonicalization (done/merged; this is content/relevance only).
- Live MCP execution (stays off; review-only).
- New flags / multi-tenant (single global COE Env Knowledge map).

## Validation gates (every PR)
```
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_t1_spl_native_routing.py app/tests/test_spl_slot_binding_validator.py app/tests/test_review_only_spl_postprocessor.py
./scripts/run_stage3_governance_regression.sh   # must stay PASS (120/120, 50/50, 18/18)
# live re-probe failing phrasings; trace must show normalized SPL + coe_env source binding
```
