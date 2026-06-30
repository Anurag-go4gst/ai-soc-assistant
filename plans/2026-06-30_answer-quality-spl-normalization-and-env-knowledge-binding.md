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

### Finding A — template-incompatible degrade BYPASSES the LLM compiler (P1, the real bug)
Query: "Which users have excessive failed logins across Windows hosts in the last hour".
Evidence (`spl_binding_trace.template_compatibility`):
- Correct template MATCHED: `auth_failed_login_spike`.
- `compatible: false`, `incompatible_reasons: ["drops_explicit_event_code:4625"]`
  — template is `action=failure` (generic auth); the user asked Windows event
  `4625`, which the rigid template would drop → flagged incompatible.
- `use_user_bound_skeleton: true` → degraded to a LEGACY deterministic skeleton
  builder → `search (index=*) | eval ... | where event_code_norm IN (4625) | table ... | head 100`.
- Validator rejected (9 reasons: `disallowed_command:eval,table`,
  `wildcard_index_not_allowed`, `missing_aggregation`, `missing_binding:group_by_user`,
  `missing_sourcetype`, ...) → HIL.

**Root cause (NOT "needs more deterministic"):** when a governed template matches
but is incompatible with the user's explicit constraints
(`check_template_compatibility.use_user_bound_skeleton=true`), the code falls to a
**legacy deterministic user-bound skeleton** in `_candidate_from_default_template`
(`customize_template_spl_with_trace(force_user_skeleton=True)`). This fires
**before** the LLM plan-compiler — even though dispatch already scheduled the
`spl_plan_compiler` hop. So the LLM SPL path (built in the canonical-dispatch
work) is **bypassed for exactly the queries that need it** (template-incompatible),
and a non-SOC-STD skeleton is surfaced+rejected instead. Non-template queries DO
reach the LLM (verified live: outbound-exfil → `llm_spl_advisory_fallback`
`candidate_ready`), so the LLM works; the **precedence is wrong**.

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

### WS1 — Route template-incompatible to the LLM compiler (not the legacy skeleton)
- [ ] **Do:** in `_candidate_from_default_template`, when
      `check_template_compatibility.use_user_bound_skeleton` is true, do NOT emit
      the legacy deterministic skeleton. Instead route to the LLM plan-compiler
      (`generate_llm_spl_via_plan`, already scheduled via the `spl_plan_compiler`
      hop) with the user's explicit constraints (e.g. event_code 4625, group-by
      user) in the plan inputs. **Verify:** failed-logins-windows trace shows
      `spl_path=llm_spl_advisory_fallback` (or plan-compiler), NOT
      `used_user_bound_skeleton=true`. **Depends:** none. **Evidence:** _____.
- [ ] **Do:** retire / fence the `force_user_skeleton` deterministic builder so it
      can never surface non-SOC-STD SPL (it currently emits `index=*`+`eval/table`).
      **Verify:** no candidate path produces `disallowed_command`/`wildcard_index`.
      **Evidence:** _____.
- [ ] **Do:** normalize the LLM/compiler output via the deterministic paraphraser
      (`deterministic_spl_repair` / plan-compile shape) before `validate_spl` so it
      is SOC-STD by construction; review-only, never flip `execution_eligible`.
      **Verify:** approved/clean or placeholder lab draft, 0 reject reasons;
      `execution_eligible=false`; governance byte-identical on curated evals.
      **Evidence:** _____.

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
