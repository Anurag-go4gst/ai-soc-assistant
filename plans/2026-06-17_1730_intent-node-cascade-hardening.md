# Intent Node Cascade Hardening (graph_node_query_to_intent)

Date: 2026-06-17
Status: **Done** (Batch 0 + 0.1 + deferred §6–§7 closed 2026-06-17)
Scope: Make `graph_node_query_to_intent` route the full SOC question set correctly via a
deterministic match cascade with a Guided-Research floor and diagnosed-only clarification.
Companion to `/root/.cursor/plans/environment_kb_cisco_catalogue_1eddd12f.plan.md` (Cisco 50).

---

## 0. Why this plan (the systemic finding)

`graph_node_query_to_intent` is the upstream gate: **if it mis-classifies, every downstream
stage produces a weak answer.** An offline harness over the 50 Cisco questions (deterministic
`understand_query` + `build_query_to_intent`, no LLM) showed:

| intent_family | count | meaning |
|---------------|-------|---------|
| `clarification_required` | **29** | clear hunts **dumped** to a hollow clarification |
| `spl_generation_only` | 16 | OK (review-only SPL) |
| `live_investigation` | 3 | OK |
| `knowledge_only` | 2 | edge |

29/50 well-formed hunts ("Show any blocked connections…", "Detect any GOOSE burst…", "Flag
any MMS write…") fell to the **terminal clarification default** (`intent_classifier.py:552`,
reason "Insufficient deterministic intent signals") — not because they are ambiguous, but
because they are **out-of-105-registry / out-of-catalog** and matched no engine. This is the
root cause of the weak-answer class the user observed on novel queries.

**Non-negotiable principle (user):** no stop-gap keyword patches. Fix the cascade + the floor,
then register the catalogue for precision — do not hand-code 50 question shapes.

---

## 1. The cascade (target architecture)

```
Analyst query
  │
  ▼ Engine 1 — exact hash + regex  (match_question_runtime_entry / nearest_*)  ──► registry metadata
  │ miss
  ▼ Engine 2 — local semantic match (semantic_question_match, threshold+margin)──► registry metadata
  │ miss        └─ confused band (semantic_candidates) ─► "did you mean" hints into guided
  ▼ Engine 3 — small-LLM dual-hypothesis router (generate_llm_intent_advisory
  │            → adjudicate_llm_intent_advisory → llm_promoted_with_registry_validation) ──► registry route
  │ miss / not-promotable
  ▼ FLOOR — graph_node_query_to_intent terminal:
       • genuinely ambiguous (diagnosed)         → clarification_required  (TARGETED question)
       • off-topic / non-SOC                      → clarification_required  (honest out-of-scope)
       • SOC-shaped, actionable, unmatched        → guided_investigation    (Guided Research)
```

**Repo mapping (already exists — confirmed):**
- Engine 1: `understand_query` → `match_question_runtime_entry` + `nearest_question_runtime_entry`.
- Engine 2: `app/coverage/semantic_question_index.semantic_question_match` (word-token cosine;
  hash-mock embeddings — see §5; has unused `semantic_candidates` band).
- Engine 3: `app/chat/llm_intent_advisor.generate_llm_intent_advisory` +
  `adjudicate_llm_intent_advisory` → existing `llm_promoted_with_registry_validation` match_path.
- Floor: `intent_family="guided_investigation"` handled at `planning_decision.py:264`.

The architecture the user drew is **substantially implemented**; the gaps are the floor, the
catalogue registration, and Engine 2/3 inclusiveness — not a missing cascade.

---

## 2. The three gates to harden

### 2A. Intent gate (graph_node_query_to_intent)
- Keep Engines 1→2→3 in order; **ensure Engine 3 (advisory promotion) runs for out-of-set
  queries before any floor** (a crude floor that pre-empts it regressed
  `test_advisory_promotion` — see §3).
- **MANDATORY (the §10.2 gap):** Engine-3 promotion today updates `candidate_mappings.match_path`
  only — `intent_classification.intent_family` is returned **unchanged** (`intent_classifier.py:611`),
  so planning/evidence still read `clarification_required`. After `apply_advisory_promotion`,
  **reconcile `intent_family`** from the promoted/validated registry ref+use-case (e.g.
  `spl_generation_only`/`live_investigation`) so the promotion reaches `evidence_plan`/`path_type`,
  not just the trace. A promotion test must assert **intent_family**, not only `match_path`.
- Replace the terminal **generic clarification dump** with a 3-way decision (see cascade floor).

### 2B. Guided-Research gate (the floor)
- `guided_investigation` becomes the catch-all for **SOC-shaped, actionable, unmatched**
  queries — review-only guidance + candidate SPL/MITRE via `build_guided_hunt_grounding`
  (WS-F) + Environment-KB/asset hints (Cisco plan todo `guided-kb-grounding-wire`).
- Discriminator **hunt-shape vs genuine-ambiguity** (NOT a keyword allowlist): a query is
  "actionable hunt" when it has an imperative detection intent AND a security/telemetry
  subject AND no unresolved ambiguity flag. Prefer reusing/strengthening the existing
  `detect_soc_investigation_shape` (`soc_investigation_shaped`) rather than a new ad-hoc list;
  it currently under-fires on Cisco OT phrasings and must be widened with validation.

### 2C. Clarification gate (diagnosed-only)
- `clarification_required` must be **diagnosed**, never a dump. It is reached only when:
  1. a **targeted identifier** fired (`_ambiguity_flags`/`_clarification_question`):
     `mitre_mapping_requires_alert_context`, `question_registry_use_case_skill_conflict`,
     pipeline `spl_source_profile_clarification` (names missing slots), session-stale; **or**
  2. the query is **off-topic / non-SOC** (`non_soc_or_out_of_scope`).
- **Generalize the clarification identifier** so any genuine ambiguity names what is missing
  (target scope / time window / data source / entity), producing a real question — instead of
  the generic "insufficient signals" string. For SOC hunts, missing dimensions should be
  **defaulted** (time=24h, scope=all) and routed to guided, not asked — clarification stays rare.

---

## 3. Validation findings (crude floor — reverted)

A first attempt set the terminal default unconditionally to `guided_investigation` for any
non-`non_soc` query. Harness improved (clarification 29→0), **but governance failed:**

- **Broke Engine 3:** `test_advisory_promotion::test_end_to_end_promotion_through_build_query_to_intent`
  — the `llm_promoted_with_registry_validation` path is gated on the clarification outcome; the
  blanket floor pre-empted it. ⇒ Floor must sit **after** Engine 3 promotion.
- **Broke a designed clarification sentinel:** `pg.clar.001` (genuinely ambiguous) flipped
  `clarification → guided_investigation`; `q0.q045` severity shifted. ⇒ Floor must **not**
  convert genuinely-ambiguous queries; only actionable hunts.

**Conclusion:** the floor needs the hunt-shape-vs-ambiguity discriminator and correct cascade
ordering — not a blanket conversion. (Crude change reverted; tree clean.)

---

## 4. Catalogue registration (precision layer — Cisco 50)

Per the Cisco plan: register the 50 (+ paraphrases) so Engines 1–2 match them with a precise
`pattern_type`/skill instead of relying on the guided floor:
- `backend/app/coverage/cisco_question_runtime_map_v1.json` + loader (try 105 exact, then Cisco).
- `semantic_question_index` entries + paraphrase aliases (analyst wording).
- This converts most of the 29 guided-floor rows into **precise** spl_generation/attack_discovery
  routes (better than guided). Guided remains the floor for the genuinely-novel tail.

---

## 5. Engine 2 / Engine 3 enhancements

- **Engine 2 (semantic):** **functional** — `semantic_question_match` uses a deterministic
  **word-token cosine** (threshold + margin), intentionally bypassing the mock embeddings
  connector. It already handles word reorder, morphology, and typos (lexical paraphrase). Its
  limit is *deep conceptual* paraphrase (synonyms / different words, same meaning). The Cisco
  gap is **index coverage** (the 50 aren't registered), NOT a broken matcher — register them
  and the word-token cosine matches analyst rewordings.
  (a) Wire `semantic_candidates` "confused band" into the guided floor as "did you mean" hints
  (no silent landing). (b) Optional infra follow-on (COE): a real local embedding/cross-encoder
  to cover conceptual paraphrase + reach a true cosine `>0.82` — enhancement, not a blocker;
  the live instruct LLM (Engine 3) already covers semantic intent the word-token misses.
- **Engine 3 (LLM advisory):** keep advisory→adjudicate→promote. Make it run for out-of-set
  before the floor; when the LLM proposes a skill/route that validates against the registry,
  promote; otherwise fall to guided. Never authoritative — deterministic registry validates.

---

## 6. Completeness floor (planning_decision) — make it effective

**Status: done (2026-06-17).** `_apply_completeness_floor` is wired in
`evidence_planner.plan_evidence()` via `_maybe_apply_completeness_floor_to_plan`
(thin `rag_only` / SPL-less `live_investigation` → hybrid with `spl_allowed=true`).
`route_adjudication` no longer forces `knowledge_recall` when `needs_mitre` or
`needs_spl` is set. Runtime activation still gates curated context
(`get_runtime_curated_enrichment`).

The committed `_apply_completeness_floor` (8cbbe59) sets `planning_decision.path_type`, but
`route_adjudication` overrides from `evidence_plan` (`authority_source=evidence_plan_rag_only`),
so it is currently **cosmetic** (never changed a live answer in the 6-query probe). Wire the
escalation through `evidence_plan` (flip `needs_spl`/`spl_allowed`/`answer_mode`) or have
`route_adjudication` honor an escalated path_type so it actually takes effect.

---

## 7. Validation harness (headline metric = out-of-set)

1. **50-Cisco intent harness** (`backend/app/tests/test_cisco_intent_distribution.py`): assert hunt rows never `clarification_required` and ≥45/50 actionable.
2. **105 governance** (`run_stage3_governance_regression.sh`) — sentinels incl. `pg.clar.001` must stay green.
3. **Out-of-set probe eval** — `scripts/eval_out_of_set_intent_probe.py` + `docs/evals/intent_out_of_set_probes.json` (10 probes; `--check` against frozen baseline).
4. Run after **every** intent-node change.

---

## 8. Sequencing

1. **Engine-3-safe floor + shape widening** — terminal: ambiguity-diagnosed → clarification
   (targeted); non-SOC → clarification (out-of-scope); SOC-actionable-unmatched (after Engine 3
   miss) → guided. Shape via §10.3 class patterns (imperative verb + telemetry subject). Preserve
   advisory-promotion + clarification sentinels. Validate (50 + 105 + probes).
2. **Post-promotion intent reconcile (MANDATORY, §2A/§10.2)** — Engine-3 promotion upgrades
   `intent_family` (and thus `evidence_plan`/`path_type`), not only `match_path`. Promotion test
   asserts `intent_family`. **Without this, steps 4–5 improve traces but not answers.**
3. **Generalize clarification identifier** (named missing dimension; default-or-ask).
4. **Engine 2 candidate-band → guided hints.**
5. **Cisco registration** (runtime map + semantic + paraphrases) — precision.
6. **Completeness-floor route_adjudication wiring** (make §6 effective).
7. **Out-of-set probe eval** committed as a regression gate.

Each step: one commit, 105-validated, no sentinel drift.

### 8.1 Honest pass expectation (not a false "100%")

"100% intent pass" is the wrong target to claim. The realistic, validated profile after Batch 0
+ registration:
- **Registered Cisco 50 + lexical paraphrases:** precise route (spl/attack/live) via Engines 1–2
  → eval PASS. This is the ~"100%" for the committed catalogue.
- **Novel/out-of-set SOC tail:** Engine 3 (live LLM, when it validates) → precise; else
  **guided_investigation floor** → actionable review-only answer (NOT a hollow dump). Counts as a
  governed PASS under the eval rubric (artifact = checklist + candidate SPL/MITRE), not a precise
  template match.
- **Genuinely ambiguous:** diagnosed `clarification_required` with a targeted question.
- **Off-topic/non-SOC:** honest out-of-scope clarification.

So the guarantee is: **no SOC query produces a hollow clarification dump; every SOC query gets a
precise or guided actionable answer.** Precision (precise vs guided) rises with registration +
real embeddings; the floor guarantees the *quality floor*, not literal 100% precise matching.

---

## 10. Plan review (2026-06-17) — alignment with Cisco catalogue plan

**Verdict: Strong, should run as Batch 0 (before Cisco template waves).** Root-cause analysis is
accurate; crude-floor revert discipline is correct. Companion:
`/root/.cursor/plans/environment_kb_cisco_catalogue_1eddd12f.plan.md`.

### 10.1 Confirmed findings (code review)

| Claim in §0–§3 | Code evidence | Assessment |
|----------------|---------------|------------|
| 29/50 → `clarification_required` | `intent_classifier.py:552` terminal default | **Valid** |
| Cascade engines 1–3 exist | `understand_query`, `semantic_question_match`, `apply_advisory_promotion` | **Valid** |
| Crude floor broke promotion test | `test_advisory_promotion::test_end_to_end_promotion` | **Valid** |
| `soc_investigation_shaped` under-fires Cisco imperatives | `soc_investigation_shape.py` requires `hunt` OR (`anomaly` AND `network/ot`); *"Show blocked…SCADA"* has `scada` but not `unusual/suspicious/hunt` | **Valid root cause** |
| Guided intent path exists without router hint | `intent_classifier.py:130-147` (`out_of_registry` + shaped) | **Partial** — shape gate too narrow |
| Completeness floor cosmetic | `_apply_completeness_floor` vs `evidence_plan` / `route_adjudication` override | **Plausible** — verify in §6 impl |

### 10.2 Critical gap not explicit in §1–§5 (add to implementation)

**Engine 3 promotion updates `candidate_mappings` only — not `intent_classification`.**
`build_query_to_intent` runs `classify_intent` **before** `apply_advisory_promotion`; promoted
`match_path=llm_promoted_with_registry_validation` does not change `intent_family`. Meanwhile
`plan_evidence` short-circuits on `intent.requires_clarification` / `clarification_required`
(`evidence_planner.py:67`).

**Required fix (pick one, document in §2A):**

1. **Post-promotion intent reconcile** — after `apply_advisory_promotion`, if promoted ref/use-case
   validates, re-derive `intent_family` (`spl_generation_only` / `live_investigation`) from registry
   metadata; **or**
2. **Floor before terminal clarification** — in `classify_intent`, after catalog rescue branches,
   apply actionable-hunt floor → `guided_investigation` (Engine 3 runs later in
   `build_query_to_intent` but promotion must then upgrade intent, not only mappings).

Without (1) or (2), Engine 3 and Cisco registration improve **mappings** while **planning** still
reads clarification intent.

### 10.3 Shape discriminator (§2B) — recommended pattern

Widen `detect_soc_investigation_shape` (or add `detect_actionable_detection_intent`) with **class
patterns**, not per-question keywords:

- Imperative detection verbs: `show|list|identify|flag|detect|alert on|find any` …
- **AND** security telemetry subject: `connection|login|dns|goose|modbus|firewall|vlan|…`
- **AND NOT** `non_soc`, `unsafe_or_execution`, exact-105 (unchanged guards)

Validate against full Cisco 50 + 105 sentinels (`pg.clar.001` stays clarification).

### 10.4 Sequencing with Cisco plan (merged)

| Order | Workstream |
|-------|------------|
| **0** | This plan §8 steps 1–3 (floor + clarification + semantic hints) |
| **1** | Cisco plan Batch 1 (KB, bank, tiered SPL) — parallel OK |
| **2** | Cisco plan §3B registration (precision for 50) — this plan §4 |
| **3** | Cisco template waves + intent harness 48/50 |
| **4** | Cisco plan Part 15 weak-path LLM + `guided-kb-grounding-wire` (finalize enrichment) |
| **5** | Completeness-floor wiring (§6) + out-of-set probe eval (§7) |

Part 15 LLM enrichment in the Cisco plan is **downstream**; this plan fixes **upstream**
mis-classification. Both are needed.

### 10.5 Guardrails — agree / extend

- Agree: no keyword stop-gaps per question; no MCP execution; LLM advisory only.
- **Extend:** promoted LLM routes must update **intent + evidence_plan**, not mappings alone.
- **Extend:** commit `test_cisco_intent_distribution.py` (§7) to governance regression after Batch 0.

---

## 9. Guardrails
- No MCP execution enablement; review-only posture unchanged.
- LLM stays advisory; deterministic registry validates Engine-3 promotions.
- No keyword stop-gaps as the routing mechanism; shape detection must be validated against the
  full set + 105, not tuned to 1–2 questions.
- Experience Center path stays isolated.
