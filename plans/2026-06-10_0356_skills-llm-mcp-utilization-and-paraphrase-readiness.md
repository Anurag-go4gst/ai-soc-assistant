# Plan — Skills / LLM / MCP Utilization, Resource Planner Node, Answer-Quality Evals

Status: Proposed (rev 3 — executable playbook; per-task pass/fail, tests, git/build protocol)
Date: 2026-06-10
Author: Anurag + Claude

---

## Part 0 — Operating principles (set by Anurag, 2026-06-10)

1. **Deterministic is the main orchestration layer, not the sole layer.** Deterministic
   policy keeps authority (severity, MITRE status, allowed actions, execution gates,
   allowlists). LLM, RAG, MCP, and skills operate *inside* that envelope — but they must
   actually operate, not just be logged.
2. **The resource-planning node is the most important node.** After intent is understood,
   one node decides which resources answer the question: MCP tools, RAG corpora, APIs,
   deterministic analytics, LLM roles, skills. Today it is a static lookup table.
3. **This is an AI SOC assistant, not a 105+50-question answering machine.** Registries
   are calibration anchors and eval baselines, not the boundary of capability.
4. **Evals must give definitive answers.** Every eval exits 0 (PASS) or 1 (FAIL) with a
   one-line verdict and machine-readable JSON. No fuzzy "scores reported" without a
   threshold. LLM-judge output is also binary per dimension, with low-confidence rows
   flagged for human review — never silently averaged away.
5. **Never break the happy path.** The exact-105 + PowerGrid-50 behavior is frozen by
   parity fixtures before any planner change. Full 105+50 runs are too slow for the inner
   loop — a frozen **sentinel set** (12+5 questions, <2 min) is the per-task gate; full
   runs happen only at workstream completion and pre-merge.

---

## Part A — Objective and rationale

**Objective.** Convert the system from "registry-honoring answer machine with idle
resources" into a governed AI SOC assistant where one planner node composes every
available resource (MCP tools, RAG, deterministic analytics, LLM roles, skills, future
APIs) per question — deterministic authority intact — and where evals certify the
*quality of the final answer*, not just the route it took.

**Rationale per workstream:**

| WS | Objective | Rationale (evidence from review) |
|----|-----------|------------------------------------|
| WS-PRE | Fast, definitive eval infrastructure | Full 105+50 too slow per-task; current evals check paths, not answers; small-model execution needs binary gates |
| WS0 | Resource Planner node | `plan_evidence()` is a static intent-family→boolean table (`backend/app/chat/evidence_planner.py`); no resource registry, no composition, no degrade chains; violates Principle 2 |
| WS1 | Paraphrase / out-of-set intake | Matching is lexical-only (0.62 token overlap); LLM advisor (`llm_intent_advisor.py`) annotates but can never promote; out-of-registry = degraded generic answer |
| WS2 | Skills as answer-shaping resources | 7–8 catalog skills reach final answer as a string label only (`analyst_summary_skeleton.py`); `allowed_tools`/`required_evidence`/`default_workflow` unused by planner; skill knowledge absent from RAG |
| WS3 | LLM utilization closure | Six LLM roles live/shadow, signals logged, almost never adjudicated into outcomes |
| WS4 | MCP go-live readiness | `splunk_mcp.py` connector = `NotImplementedError`; tool schema now known (livehybrid/splunk-mcp); pre-live security hardening (result-injection defense) not started |
| WS5 | Answer-quality evals | Existing evals = path honoring + severity leaks; no grounding/completeness/actionability verdicts |

**Splunk MCP references (captured 2026-06-10):**

- `https://github.com/livehybrid/splunk-mcp` (Apache-2.0) — adapter target schema:
  `search_splunk(search_query: str, earliest_time?: str, latest_time?: str, max_results?: int)`,
  `list_indexes`, `get_index_info(index_name)`, `indexes_and_sourcetypes`,
  `list_saved_searches`, `health_check`, `ping`, `current_user`, `list_users`,
  `list_tools`, KV store `list/create/delete_kvstore_collection(collection_name)`.
  Transport: SSE (`/sse`, default), STDIO, REST (`/api/v1`). Auth: `SPLUNK_TOKEN`
  (precedence) or `SPLUNK_USERNAME`/`SPLUNK_PASSWORD`; `SPLUNK_HOST`/`SPLUNK_PORT` (8089),
  `VERIFY_SSL`.
- Splunkbase App **8747 "AI Workbench"** (Eduard Lekanne, v1.3.2) — workbench *consumer*
  that registers MCP servers; reference for host-side surface and tool naming, not the
  server contract.
- CLAUDE.md names App ID **7931** as first target. Contract doc records all three;
  **binding choice = COE decision** (escalate, do not pick).

---

## Part B — Execution protocol (binding for any executor, sized for a small model)

### B1. Golden rules

1. **One task = one branch slice = one commit.** Never combine tasks in a commit.
2. **Never edit these without escalation (E-rule below):** severity policy, MITRE status
   logic, execution gates (`mcp_execution_gate`), `.env` flags, anything under
   `app/safeguards/` except where a task explicitly names the file, any existing test's
   expected values.
3. **Additive-first:** new modules and new fields over edits to existing functions. When
   an existing function must change, preserve its signature and existing return keys.
4. **No new env flags, no new profiles.** Reuse existing settings only.
5. **Candidate SPL never executable; `execution_eligible=false` stays; LLM never calls
   MCP; MCP execution flags stay false.**

### B2. Escalation rules (when to stop and ask Anurag / a senior model)

Stop and ask ONLY when one of these fires — otherwise proceed:

- **E1:** A required test fails twice after your own fix attempt.
- **E2:** Task requires touching a Golden-rule-2 file not named in the task spec.
- **E3:** Parity/sentinel gate fails and the diff is not obviously caused by your change.
- **E4:** Contract ambiguity — two plausible schemas/behaviors and the task spec doesn't
  decide it.
- **E5:** Anything involving COE decisions (MCP binding target, flag flips, live reads).

When escalating: report task id, exact command run, full failing output, one-paragraph
hypothesis. Do not "fix" by loosening an assertion.

### B3. Standard loop per task

```bash
# 0. setup (once per workstream)
cd /var/www/ai-soc-assistant
git checkout master && git pull --ff-only
git checkout -b feat/<ws-id>-<slug>        # e.g. feat/ws0-resource-planner

# 1. implement task (files listed in task spec)

# 2. fast tests — task-specific (named in task spec), then touched-area suite
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/<task_test_file>.py -q

# 3. sentinel gate (happy-path protection, <2 min) — required before every commit
cd /var/www/ai-soc-assistant
PYTHONPATH=backend:. python3 scripts/eval_sentinel.py --check        # built in T-PRE.2

# 4. full backend pytest — required before every commit
cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q

# 5. commit (only if 2–4 all green)
git add <only files you touched>
git commit -m "<type>: <task title>"        # type ∈ feat|fix|test|docs|chore
```

### B4. Heavy gates (NOT per task)

| Gate | When | Command | Pass |
|------|------|---------|------|
| Governance regression | End of each workstream + before PR | `./scripts/run_stage3_governance_regression.sh` | exit 0, harness 6/6 |
| Full 105 path honoring | End of WS0, WS1 + before PR | `PYTHONPATH=backend:. python3 scripts/eval_105_path_honoring.py --check` | exit 0 |
| PowerGrid 50 | End of WS0, WS1 + before PR | `python3 scripts/run_powergrid_soc_question_eval.py` (deterministic mode) | 50/50 |
| Frontend build | Only if `frontend/` touched | `cd frontend && npm run build` | exit 0 |
| Docker build | Before PR | `docker compose build` | exit 0 |

**Do NOT run full 105+50 per task.** Sentinel set is the inner-loop gate.

### B5. PR

Use the `git-commit-and-pr` skill at workstream completion. PR per workstream, base
`master`. PR description: tasks completed, gates table (B4) with actual outputs pasted.

---

## Part C — Workstreams and tasks

Task template: **Objective / Files / Steps / New tests / Pass / Fail-means / Commit**.
"Fail-means" tells the executor how to interpret a red gate before touching anything.

---

### WS-PRE — Definitive eval infrastructure (do first; everything else gates on it)

#### T-PRE.1 — Sentinel set definition

- **Objective:** Freeze a 17-question fast subset (12 of 105 + 5 PowerGrid) covering
  every match path and answer class, so every later task has a <2 min happy-path gate.
- **Files:** new `docs/evals/sentinel_set.json`; new `scripts/build_sentinel_set.py`.
- **Steps:**
  1. `build_sentinel_set.py` selects deterministically (sorted, seeded — no randomness)
     from `backend/app/coverage/question_runtime_map_v1.json`: 2× exact-analytics
     (incl. q0.q010 SMB top talkers), 2× hunt-pattern-bridge, 1× knowledge/SOP,
     1× MITRE, 1× clarification-required, 2× lab-draft families, 2× deferred classes
     (lookup/TI), 1× severity-policy-active; plus 5 PowerGrid ids spanning its classes.
  2. Write selection with `question_ref`, `question`, `expected_match_path`,
     `selection_reason` per row. Script supports `--check` (regenerate, diff, exit 1 on
     drift) like the other generators in `run_stage3_governance_regression.sh`.
- **New tests:** none (generator `--check` is the test).
- **Pass:** file exists, 17 rows, `--check` exits 0 on second run.
- **Fail-means:** selection nondeterministic — fix sort/seed, never hand-edit the JSON.
- **Commit:** `feat: add frozen sentinel eval set (12+5) with deterministic builder`

#### T-PRE.2 — Sentinel runner + parity fixture (happy-path freeze)

- **Objective:** One command that runs the 17 sentinel questions through the real
  pipeline and verdicts PASS/FAIL against a frozen fixture. This is the per-commit gate.
- **Files:** new `scripts/eval_sentinel.py`; new fixture
  `backend/app/evals/fixtures/sentinel_baseline.json`.
- **Steps:**
  1. Reuse the invocation pattern of `scripts/eval_105_path_honoring.py` (it already
     drives the real pipeline; copy its setup, not new plumbing).
  2. For each sentinel question capture: `deterministic_match_path`, routed skill,
     template/lab-draft family, severity label, answer-mode, `execution_eligible`,
     AnswerContract section list. **Contract fields only — no prose, no timestamps, no
     trace ids** (smoke asserts contracts, not values).
  3. `--freeze` writes the baseline fixture; `--check` compares and prints
     `RESULT: PASS (17/17)` or `RESULT: FAIL (k/17)` + per-row diff, exit code matches.
  4. Freeze baseline from current `master` behavior BEFORE any WS0 change.
- **New tests:** `backend/app/tests/test_eval_sentinel_runner.py` — runner is
  deterministic across two runs; `--check` against fresh `--freeze` passes.
- **Pass:** `eval_sentinel.py --check` exits 0 on unmodified master; runtime < 2 min.
- **Fail-means:** captured field is unstable (timestamp/order) — stabilize capture,
  do not widen tolerance to prose.
- **Commit:** `feat: add sentinel eval runner with frozen happy-path baseline`

#### T-PRE.3 — Definitive-verdict convention for all eval scripts

- **Objective:** Every eval gives a definitive answer (Principle 4).
- **Files:** `scripts/eval_105_path_honoring.py`, `scripts/run_powergrid_soc_question_eval.py`
  (verdict line only — do not change their checks); new `docs/evals/EVAL_CONTRACT.md`.
- **Steps:** ensure each prints final `RESULT: PASS|FAIL (n/m)` and exits accordingly;
  document the contract (exit codes, JSON shape, threshold source) in `EVAL_CONTRACT.md`.
  Add `--refs q0.q001,q0.q010` subset filter to `eval_105_path_honoring.py` for targeted
  debugging.
- **Pass:** both scripts emit verdict line; `--refs` runs only named rows; full-run
  results unchanged vs before (same n/m).
- **Fail-means:** if n/m changed, you altered a check — revert, verdict line only.
- **Commit:** `feat: standardize definitive PASS/FAIL verdicts and subset filter for evals`

---

### WS0 — Resource Planner node (centerpiece)

#### T0.1 — Resource Capability Registry

- **Objective:** Single deterministic registry enumerating every answerable resource so
  the planner can choose among them.
- **Files:** new `backend/app/planner/__init__.py`, `backend/app/planner/resource_registry.py`,
  new data file `backend/app/planner/resource_registry_v1.json`.
- **Steps:**
  1. Descriptor (pydantic): `resource_id`, `kind` (`mcp_tool|rag_corpus|deterministic_analytic|spl_template_family|spl_lab_draft_family|llm_role|api|skill`),
     `capabilities: list[str]`, `input_contract: dict`, `cost_class` (`free|cheap|expensive`),
     `availability` (`available|fixture_only|not_implemented|blocked`), `policy_tier: int`,
     `fallback_of: str|None`.
  2. Seed JSON from existing facts only — do not invent: MCP tools from §A schema
     (all `availability=not_implemented` except mock), RAG corpus `soc_kb`,
     template + lab-draft families (from the 14 draft families + governed templates),
     LLM roles (intent_advisory, route_plan, narration, mitre_candidate, spl_fallback,
     guard, judge), the skills from `backend/app/skills/catalog.json` (their
     `allowed_tools` become capability links). Future TI/asset APIs as
     `not_implemented` placeholders.
  3. Loader with cache + `clear_cache()`, mirroring `question_runtime_map.py` pattern.
     Validation on load: unique ids, `fallback_of` refers to existing id, kind-specific
     required fields present.
- **New tests:** `backend/app/tests/test_planner_resource_registry.py` — loads, unique
  ids, every skill in catalog.json has a registry entry, every `fallback_of` resolves,
  every MCP-tool entry that mutates (kvstore create/delete) has `availability=blocked`.
- **Pass:** new tests green; sentinel gate green (registry is inert — nothing consumes it yet).
- **Fail-means:** sentinel red is impossible from this task → your environment is dirty (E3).
- **Commit:** `feat: add planner resource capability registry (data + loader)`

#### T0.2 — ResourcePlan contract (additive to EvidencePlan)

- **Objective:** Plans become ordered steps with fallbacks; existing booleans preserved
  as projections so nothing downstream breaks.
- **Files:** `backend/app/chat/contracts/evidence_plan.py` (additive),
  new `backend/app/planner/resource_plan.py`.
- **Steps:**
  1. `PlanStep`: `step_id`, `resource_id`, `purpose`, `args_template: dict`,
     `on_unavailable: str|None` (step_id of fallback), `policy_checks: list[str]`.
  2. `ResourcePlan`: `steps: list[PlanStep]`, `plan_source`
     (`deterministic|llm_proposed_validated`), `provenance: dict`.
  3. `EvidencePlan` gains optional field `resource_plan: ResourcePlan|None = None`
     (default None). Add pure function `project_booleans(plan: ResourcePlan) -> dict`
     returning the existing boolean keys (`needs_rag`, `needs_spl`, `needs_mcp`,
     `needs_mitre`, `spl_allowed`, `mcp_allowed`) derived from step kinds. Do NOT change
     how existing booleans are set yet.
- **New tests:** `backend/app/tests/test_resource_plan_contract.py` — projection
  correctness per kind; `EvidencePlan` without `resource_plan` serializes exactly as
  before (snapshot of `model_dump()` keys vs a literal list).
- **Pass:** new tests + full pytest + sentinel green.
- **Fail-means:** an existing test red ⇒ you changed a default — make field optional/None.
- **Commit:** `feat: add ResourcePlan step contract with boolean projections`

#### T0.3 — Deterministic plan composer behind parity

- **Objective:** Compose `ResourcePlan` for every question; registry-matched questions
  reproduce today's behavior exactly.
- **Files:** new `backend/app/planner/composer.py`;
  `backend/app/chat/evidence_planner.py` (one insertion point in `plan_evidence`).
- **Steps:**
  1. `compose_resource_plan(intent, registry_entry, use_case, skill_definition, registry)`
     — pure function. Mapping rule: existing family branch in `plan_evidence` →
     equivalent step list (e.g. `needs_rag=True` branch → step `rag:soc_kb`;
     spl branches → `spl_template_family:<family>` with `on_unavailable` →
     `spl_lab_draft_family:<family>`; narration step appended where live synthesis runs
     today). Skill contract consumed: `default_workflow` orders steps,
     `required_evidence` recorded as `policy_checks`, `blocked_tools` filtered out.
  2. In `plan_evidence`, after the existing branch picks the `EvidencePlan`, attach
     `resource_plan=compose_resource_plan(...)` and assert (in tests, not runtime)
     `project_booleans(resource_plan) == existing booleans`.
  3. Surface `resource_plan` summary (step resource_ids + plan_source) in
     `control_plane_trace`.
- **New tests:** `backend/app/tests/test_planner_composer_parity.py` — for each of the
  17 sentinel questions: booleans projected from composed plan == booleans the legacy
  branch produced (drive `plan_evidence` directly, no full pipeline).
- **Pass:** parity test green; sentinel `--check` green (frozen baseline untouched —
  contract fields unchanged); full pytest green. **Heavy gate here:** full 105 honoring
  + PowerGrid 50 (B4) once at task end.
- **Fail-means:** projection mismatch = your mapping rule wrong for that family — fix
  composer, never the legacy branch. Sentinel red on severity/route = E3 escalate.
- **Commit:** `feat: compose deterministic ResourcePlan with boolean parity in evidence planner`

#### T0.4 — Plan execution loop (degrade chains)

- **Objective:** Pipeline walks plan steps; unavailable resource falls back along
  `on_unavailable`; every step result lands in evidence with provenance.
- **Files:** new `backend/app/planner/executor.py`; `backend/app/chat/pipeline.py`
  (wire after evidence-planning node, replacing only the *dispatch* of already-existing
  stage calls — RAG stage, SPL stage, MCP gate stage — with a loop over steps that calls
  the same stage functions).
- **Steps:**
  1. Executor iterates steps; per step: registry availability check → if not
     `available`/`fixture_only`, follow `on_unavailable`; record
     `plan_step_ref`, `status` (`executed|fallback_taken|skipped_unavailable|blocked_policy`)
     into state + lineage.
  2. MCP-kind steps MUST still route through `evaluate_mcp_execution` /
     `mcp_execution_gate` unchanged — executor calls the existing gate, never the
     connector. SPL steps through existing validator path. RAG steps through existing
     retriever. **No stage logic moves; only dispatch order is generalized.**
  3. `SourceEvidence` items gain optional `plan_step_ref`.
- **New tests:** `backend/app/tests/test_planner_executor.py` — fallback chain taken when
  primary `not_implemented`; blocked step never calls gate; step statuses recorded;
  plus one full-pipeline test for one sentinel question asserting identical
  AnswerContract sections vs baseline.
- **Pass:** new tests + full pytest + sentinel green. Heavy gate: governance regression
  (end of WS0) — exit 0, harness 6/6.
- **Fail-means:** sentinel diff in answer-mode/sections ⇒ dispatch-order bug — compare
  per-step statuses against the legacy stage order for that question.
- **Commit:** `feat: execute composed resource plans with governed degrade chains`

#### T0.5 — LLM-assisted planning for unmatched questions (advisory → validated plan)

- **Objective:** Out-of-registry questions get an LLM-*proposed*, deterministically
  *validated* plan instead of generic fallback.
- **Files:** `backend/app/routing/llm_planner.py`, `llm_plan_validator.py`,
  `planner_policy_validator.py` (extend, signatures preserved); new
  `backend/app/planner/llm_plan_bridge.py`.
- **Steps:**
  1. Trigger only when `deterministic_match_path in {"out_of_registry","near_105_question"}`
     and `settings.ai_soc_llm_intent_advisor_enabled` (existing flag — no new flag).
  2. Prompt contract: model returns JSON steps referencing **resource_ids from the
     registry only**; reuse `app/llm/adapter/` balanced-JSON extraction + schema
     validation.
  3. Deterministic validation per step: resource exists; `policy_tier` allowed for
     intent's `action_mode`; `availability != blocked`; SPL args pass `spl_validator`;
     time windows bounded by `SPL_DEFAULT_EARLIEST/LATEST`. Invalid steps dropped with
     reasons recorded. Empty validated plan → WS1.4 honest fallback.
  4. `plan_source="llm_proposed_validated"`; full raw proposal + per-step verdicts into
     lineage + `control_plane_trace`.
  5. Deterministic-failure fallback: any LLM error/timeout → behave exactly as today
     (legacy out-of-registry path). LLM unreachable must never 500.
- **New tests:** `backend/app/tests/test_llm_plan_bridge.py` — fake client fixture
  (captured-shape responses, no live model in tests): valid proposal → validated plan;
  proposal with unknown resource_id → step dropped + reason; proposal with kvstore
  mutation → blocked; client exception → legacy path, response identical to a no-LLM
  run (assert key-level equality).
- **Pass:** new tests + full pytest + sentinel green (sentinel rows are all registry-
  matched, so this path must not touch them — assert `plan_source=deterministic` on all 17).
- **Fail-means:** sentinel row shows `llm_proposed_validated` ⇒ trigger condition bug.
- **Commit:** `feat: validate LLM-proposed resource plans for out-of-registry questions`

---

### WS1 — Paraphrase & out-of-set intake

#### T1.1 — Semantic match tier

- **Objective:** Paraphrases land on the right registry row without verbatim overlap.
- **Files:** new `backend/app/coverage/semantic_question_index.py`;
  `backend/app/query_understanding/parser.py` (one new ladder rung);
  `backend/app/coverage/question_runtime_map.py` untouched.
- **Steps:**
  1. Build embedding index of the 105 questions via `get_embeddings_connector()`
     (`LocalEmbeddingsConnector`; mock connector path must work for tests). Cache
     vectors in-process; build lazily on first call.
  2. New rung between `near_105_question` and `out_of_registry`:
     cosine ≥ **0.80** with margin ≥ **0.05** over runner-up → match path
     `semantic_105_question`, score recorded (`_semantic_match_score`), provenance
     `question_runtime_map_105_semantic`. Thresholds as module constants.
  3. Selected row is a registry row — downstream identical to `near_105_question`
     handling.
- **New tests:** `backend/app/tests/test_semantic_question_match.py` — with mock
  embeddings: synthetic paraphrase matches; ambiguous twin (margin < 0.05) → no match;
  empty query → no match; exact-match queries never reach semantic rung (ladder order).
- **Pass:** new tests + full pytest + sentinel green (sentinel = verbatim ⇒ all rows
  still `exact_*` paths — assert in sentinel capture).
- **Fail-means:** sentinel row flipped to `semantic_105_question` ⇒ ladder-order bug.
- **Commit:** `feat: add semantic 105-question match tier with ambiguity margin`

#### T1.2 — Paraphrase eval corpus + runner (definitive)

- **Objective:** Measurable, binary paraphrase robustness; baseline before promotion work.
- **Files:** new `docs/evals/paraphrase_105.jsonl` (start: 3 paraphrases × the 17
  sentinel-source questions = 51 rows — NOT all 105, keep it fast); new
  `scripts/eval_paraphrase.py`.
- **Steps:**
  1. Paraphrase rows hand-reviewed (Anurag approves the JSONL in PR), fields:
     `question_ref`, `paraphrase`, `class` (`synonym|reorder|shorthand|typo`).
  2. Runner: query-understanding only (no full pipeline — fast), asserts landed
     `question_ref` == expected. `RESULT: PASS|FAIL (n/m)` with threshold
     `--min-rate 0.90`; `--json` report per row.
  3. Record baseline number in `docs/evals/paraphrase_baseline.md` (pre-T1.1 number from
     a master checkout is fine to capture once for the delta story).
- **Pass:** runner deterministic; post-T1.1 rate ≥ 0.90 → exit 0. If < 0.90: NOT a code
  failure — record rate, escalate E4 with per-class breakdown (threshold vs threshold
  tuning is Anurag's call).
- **Fail-means:** rate regression after later tasks = those tasks broke matching.
  Add `scripts/eval_paraphrase.py --check` to governance regression at WS1 end.
- **Commit:** `feat: add paraphrase eval corpus (51 rows) with definitive runner`

#### T1.3 — Advisory promotion rule

- **Objective:** LLM advisory may select a route only where deterministic has nothing —
  with deterministic veto.
- **Files:** `backend/app/chat/llm_intent_advisor.py` (`adjudicate_llm_intent_advisory`),
  `backend/app/chat/intent_classifier.py` (consume adjudication result).
- **Steps:**
  1. Promotion iff ALL: deterministic path == `out_of_registry`; advisor candidate is an
     exact id in question registry or use-case catalog; advisor confidence ≥ **0.75**;
     semantic tier (T1.1) agrees or abstained. Result recorded as
     `match_path="llm_promoted_with_registry_validation"`.
  2. Veto: candidate conflicts with clarification policy or catalog skill mapping →
     no promotion, reason recorded.
  3. `near_105_question` ambiguity ties (margin < 0.08): advisory may break tie between
     the top-2 only.
- **New tests:** extend `backend/app/tests/test_llm_intent_advisor_phase2.py` — promotion
  happy case; each veto branch; never fires when deterministic path is any `exact_*`/
  `use_case_catalog`; LLM error → identical-to-today annotation-only behavior.
- **Pass:** new+existing advisor tests, full pytest, sentinel green
  (all 17 deterministic — assert no promotion fired).
- **Fail-means:** existing advisor test red ⇒ you changed annotation behavior — promotion
  must be additive.
- **Commit:** `feat: promote validated LLM intent advisory for out-of-registry queries`

#### T1.4 — Honest out-of-set answer contract

- **Objective:** No silent generic answers. Out-of-catalog = say so + nearest candidates
  + knowledge-only fallback when RAG suffices.
- **Files:** AnswerContract builder (`backend/app/chat/` contract-driven builder —
  locate via `grep -rn "AnswerContract" backend/app/chat`), `final_answer` validator.
- **Steps:** when validated plan empty AND no promotion: AnswerContract gets section
  `out_of_catalog_notice` (states limitation), `nearest_questions` (top-3 semantic
  scores from T1.1 index), answer-mode `knowledge_only_answer` if RAG retrieval returned
  governed content else `insufficient_evidence`. Fail-closed validator: out-of-registry
  answers missing the notice section → validator rejects.
- **New tests:** `backend/app/tests/test_out_of_catalog_answer.py` — out-of-set query →
  notice + 3 suggestions; with RAG hit → `knowledge_only_answer`; without →
  `insufficient_evidence`; registry-matched query → section absent.
- **Pass:** new tests + full pytest + sentinel green. Heavy gates at WS1 end (B4 + paraphrase eval).
- **Commit:** `feat: add honest out-of-catalog answer contract with nearest-question suggestions`

---

### WS2 — Skills as answer-shaping resources

#### T2.1 — Skill contracts into the composer

- **Objective:** `allowed_tools`/`blocked_tools`/`required_evidence`/`default_workflow`
  actually constrain and seed plans. (Partly done in T0.3 — this task completes + tests it.)
- **Files:** `backend/app/planner/composer.py`.
- **New tests:** `backend/app/tests/test_skill_contract_planning.py` — per catalog skill:
  composed plan contains no step whose resource maps to a `blocked_tools` entry;
  `required_evidence` appears in `policy_checks`; workflow order respected.
- **Pass:** new tests + full pytest + sentinel green.
- **Commit:** `feat: enforce skill capability contracts in plan composition`

#### T2.2 — Skill knowledge into governed RAG

- **Objective:** The 7 accepted GitHub skills + `content_enrichment.json` content become
  retrievable governed KB.
- **Files:** new `scripts/import_skill_knowledge_to_kb.py`; KB docs under the existing
  SOC-KB corpus location (find via `backend/app/knowledge/soc_kb_retriever.py` config);
  no retriever code changes.
- **Steps:** generate one KB doc per accepted skill: triage steps, evidence checklist,
  detection rationale; frontmatter `skill_id`, `repo_commit`, `license`, `intake_batch`.
  Provenance stays frontmatter/lineage — `governed_answer_composer.py` `_GITHUB_MARKERS`
  guard unchanged (prose must stay clean; if composed prose ever includes a marker the
  existing guard already fails it — that is the test).
- **New tests:** `backend/app/tests/test_skill_kb_import.py` — import idempotent
  (`--check` mode, stale-diff exit 1); each doc retrievable through
  `soc_kb_retriever` query for its skill topic; composed answer using such evidence
  passes the marker guard.
- **Pass:** new tests + full pytest + sentinel green.
- **Commit:** `feat: import accepted GitHub skill knowledge into governed SOC-KB`

#### T2.3 — Skill-derived answer sections

- **Objective:** Answers show skill substance: triage checklist + evidence checklist
  sections, deterministic content from enrichment data.
- **Files:** AnswerContract builder; `backend/app/use_cases/content_enrichment.py`
  (read-only use).
- **Steps:** when selected use case is runtime-active and enrichment has checklist data:
  AnswerContract gains `triage_checklist`, `evidence_checklist` sections (deterministic
  text from enrichment JSON; LLM may narrate around, never inside them).
- **New tests:** `backend/app/tests/test_skill_answer_sections.py` — active use case →
  sections present with enrichment content; inactive → absent; sections survive
  narration fallback path.
- **Pass:** new tests + full pytest + **sentinel re-freeze required**: this
  intentionally changes AnswerContract sections for some sentinel rows → run
  `eval_sentinel.py --check`, review diff is ONLY added sections (no removals, no
  severity/route changes), then `--freeze` with the diff pasted into the commit body.
  Any non-section diff = E3.
- **Commit:** `feat: add skill-derived triage and evidence checklist answer sections`

#### T2.4 — Targeted intake batches (10 deferred classes)

- **Objective:** Each deferred class (lookup/TI/asset-context/source-health) gets ≥1
  accepted skill + registry descriptor.
- **Files:** `docs/skills/*` register/backlog/matrix (existing format),
  `backend/app/planner/resource_registry_v1.json` descriptors.
- **Steps:** follow `docs/skills/github_skill_intake_playbook.md` per batch; re-clone
  source repo to `/tmp/ai-soc-references` (record `repo_commit`); **do not execute any
  script from the cloned repo** (offensive tooling may exist). Generators `--check`
  (`build_github_skill_discovery_index.py` etc.) must stay green.
- **Pass:** governance regression generator sections green; register row count grows;
  each new record names its deferred class.
- **Commit (per batch):** `docs: intake batch <n> — skills for <class> deferred classes`

---

### WS3 — LLM utilization closure

#### T3.1 — LLM role scorecard (definitive rollup)

- **Objective:** Promotion thresholds cite data. Binary health verdict per role.
- **Files:** new `scripts/build_llm_role_scorecard.py`; output
  `docs/evals/llm_role_scorecard.md` + `.json`.
- **Steps:** parse per-turn telemetry JSONL (locate sink via `AI_SOC_TELEMETRY_SINK`);
  per role emit: invocation count, agreement rate vs deterministic, fallback rate,
  validation pass rate (T0.5), guard disagreement ids. Verdict per role:
  `HEALTHY` (fallback < 10%, agreement ≥ 70%) / `DEGRADED` / `INSUFFICIENT_DATA`
  (< 20 samples). `RESULT:` line + exit code (`INSUFFICIENT_DATA` = exit 0 with warning).
- **New tests:** `backend/app/tests/test_llm_role_scorecard.py` against fixture JSONL.
- **Pass:** tests green; script runs against live telemetry without error.
- **Commit:** `feat: add definitive LLM role scorecard rollup`

#### T3.2 — Narration coverage for knowledge-only / out-of-set answers

- **Objective:** Most-robotic answers get live narration; same guard + deterministic fallback.
- **Files:** live synthesis call site in `backend/app/chat/pipeline.py` (locate via
  `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` usage) — extend eligible answer modes with
  `knowledge_only_answer` and the T1.4 out-of-catalog mode.
- **New tests:** extend live-synthesis tests (`test_live_chat_ec_parity.py` area) —
  narration invoked for new modes with fake client; failure → deterministic draft
  byte-identical to no-LLM run; Answer Guard runs on result; EC fixture path untouched
  (existing parity test must stay green).
- **Pass:** new + existing parity tests, full pytest, sentinel green.
- **Fail-means:** EC parity test red = you leaked narration into Experience Center path — E3, revert.
- **Commit:** `feat: extend live narration to knowledge-only and out-of-catalog answers`

---

### WS4 — MCP go-live readiness

#### T4.1 — Empty-result correctness (Phase A1)

- **Objective:** Query-ran-empty = valid negative answer, never `insufficient_evidence`.
- **Files:** `backend/app/evidence/source_evidence.py`,
  `backend/app/evidence/context_sufficiency.py`.
- **Steps:** executed-with-0-rows evidence keeps `collection_status="collected"` +
  `result_count=0`; sufficiency branch: collected execution evidence with 0 rows →
  `full_answer`/`partial_answer` with reason `negative_result`.
- **New tests:** `backend/app/tests/test_negative_result_sufficiency.py` — 0-rows-executed
  → not insufficient; query-never-ran → unchanged behavior (regression case).
- **Pass:** new tests + full pytest + sentinel green (sentinel never executes — must be untouched).
- **Commit:** `fix: classify executed-but-empty results as negative answers, not insufficient evidence`

#### T4.2 — Result-injection defense (Phase A2, security-critical)

Note: this is a security control; write tests before implementation.

- **Objective:** Attacker-controlled Splunk fields (`cmdline`, `url`, `user_agent`,
  `process`) cannot reach the LLM or the analyst answer unfiltered.
- **Files:** `backend/app/connectors/mcp/splunk_result_adapter.py` (apply
  `app/safeguards/data_minimizer.py` + `app/safeguards/prompt_injection_filter.py` on
  every row before envelope emission); `backend/app/evidence/source_evidence.py`
  (verify sensitivity flag propagation).
- **New tests:** `backend/app/tests/test_mcp_result_injection_defense.py` — fixture rows
  containing prompt-injection strings ("ignore previous instructions", role markers,
  jailbreak patterns from the existing filter's pattern set) → row flagged, sufficiency
  → `blocked_by_policy`; clean rows pass unmodified; flagged text never appears in
  AnswerContract prose nor narration input.
- **Pass:** new tests + existing safeguard tests + full pytest + sentinel green.
- **Fail-means:** any flagged string reaching prose = blocker; do not merge anything
  until green (E1 after two attempts).
- **Commit:** `fix: run minimizer and injection filter on MCP results before evidence ingest`

#### T4.3 — Connection contract doc

- **Objective:** COE hand-off = fill-in exercise.
- **Files:** new `contracts/splunk_mcp_connection_contract.md`.
- **Steps:** pre-fill from §A (livehybrid tools/args/transport/auth as hypothesis,
  every field `schema_confirmed=false`); sections: binding-target decision
  (7931 vs livehybrid vs 8747-hosted — COE), URL/auth/sample-payload blanks, tool
  allowlist (read-only only; KV mutations + admin blocked), approval workflow, S5
  first-read checklist.
- **Pass:** doc exists; no secrets; review by Anurag.
- **Commit:** `docs: add Splunk MCP connection contract (schema unconfirmed, COE blanks)`

#### T4.4 — Real adapter behind existing gates

- **Objective:** `SplunkMcpConnector` implemented against livehybrid schema; still
  unreachable while execution flags false.
- **Files:** `backend/app/connectors/mcp/splunk_mcp.py`;
  `backend/app/connectors/mcp/registry.py` (real-branch wiring);
  reuse `splunk_result_envelope.py`, `live_schema_capture.py`.
- **Steps:**
  1. `call_tool`/`execute_validated_spl`: map `normalized_spl` → `search_query`;
     `earliest_time`/`latest_time` from validated bounds (never absent — default
     `SPL_DEFAULT_EARLIEST/LATEST`); `max_results` = `SPL_MAX_RESULT_LIMIT`.
  2. Transport: REST `/api/v1` first (simplest), token auth via existing
     `MCP_SERVER_<NAME>_*` settings (no new env keys; map onto existing url/auth fields).
     Timeouts + typed errors (`local_chat_errors.py` pattern). All responses →
     `SplunkResultEnvelope` with `schema_confirmed=false`,
     `schema_confirmed_reason="real_schema_unverified"`.
  3. `health()` reports `configured` from settings, `available` from reachability probe
     — but probe only when `MCP_GLOBAL_EXECUTION_ENABLED` is true; otherwise
     `available=false, detail="execution_disabled"`. **Read-only tools only**; reject
     any tool name outside the allowlist at the connector boundary too (defense in depth).
- **New tests:** `backend/app/tests/test_splunk_mcp_adapter.py` — all HTTP mocked
  (`httpx` MockTransport or equivalent — zero network in tests): arg mapping exact;
  envelope flags set; tool outside allowlist → rejected; flags-false → gate still blocks
  end-to-end (extend `test_mcp_execution_gate.py` case); timeout → typed error → gate
  records failure, no crash.
- **Pass:** new + existing MCP tests, full pytest, sentinel green, governance regression
  green (WS4 end). `docker compose build` green.
- **Fail-means:** any test needing a real network/socket = test design wrong, mock it.
- **Commit:** `feat: implement Splunk MCP adapter against livehybrid schema behind execution gates`

#### T4.5 — S5 controlled first read (COE-gated — DO NOT execute without E5 sign-off)

- **Objective:** First live read validates schema; documented checklist.
- **Pre-conditions:** T4.2 + T4.4 merged; contract doc signed by COE; Anurag present.
- **Steps:** per `docs/stage3m_s0_mcp_readiness_design.md` S5: flip flags in `.env` only
  (never `.env.example`), run `capture_stage3m_s5_live_mcp_schema.py`, validate envelope,
  record sample payloads into contract doc, flip flags back, then COE decides
  `schema_confirmed`.
- **Pass:** captured schema matches adapter mapping; any mismatch → adapter fix task, not ad-hoc patch.

---

### WS5 — Answer-quality evals (definitive)

#### T5.1 — Tier-D deterministic quality checks

- **Objective:** Binary quality verdicts per answer, in CI.
- **Files:** new `backend/app/quality/answer_quality_checks.py`; new
  `scripts/eval_answer_quality.py`.
- **Steps:** checks per answer (each → pass/fail + reason):
  `grounding_no_orphan_claims` (severity/MITRE/counts in prose must exist in contract
  fields — reuse answer-guard rule ids where they exist), `completeness_sections`
  (required AnswerContract sections per question class, from the expectation matrix),
  `actionability_priorities` (P1–P4 present where severity policy active),
  `honesty_limitations` (not-executed/candidate-only/out-of-catalog statements where
  applicable), `no_forbidden_claims` (existing guard regexes: executed-SPL claims,
  compromise-confirmed, GitHub markers). Runner = sentinel 17 + out-of-set corpus
  (T5.3); `RESULT: PASS|FAIL`, exit code, per-row JSON. **Not the full 105+50.**
- **New tests:** `backend/app/tests/test_answer_quality_checks.py` — each check: one
  passing + one failing synthetic answer.
- **Pass:** tests green; runner on current master sentinel = PASS (if any row fails on
  master: that's a finding — record, escalate E4, do not weaken the check).
- **Commit:** `feat: add deterministic answer-quality checks with definitive runner`

#### T5.2 — Tier-L LLM-judge (binary, advisory-to-CI, definitive per row)

- **Objective:** Grounding/actionability/clarity judged by local model with binary
  verdicts; calibrated against analyst feedback ledger.
- **Files:** new `scripts/eval_answer_quality_llm.py`; prompt under
  `backend/app/llm/prompts.py` conventions; judge role already registered in resource
  registry (T0.1).
- **Steps:** per answer × dimension → `PASS|FAIL|UNCERTAIN` + one-sentence reason
  (JSON-schema'd via `app/llm/adapter/`); `UNCERTAIN` rows queue for human review via
  existing feedback API; corpus verdict: FAIL iff fail-rate > 10% on decided rows AND
  ≥ 20 decided rows; else report-only. Never in `run_stage3_governance_regression.sh`
  (live model dependency) — runs on demand + scorecard cadence.
- **New tests:** fake-client tests for parsing/verdict aggregation only.
- **Pass:** runner produces stable verdicts on two consecutive runs against fixed
  fixture answers (temperature 0.0/0.1 per existing settings).
- **Commit:** `feat: add binary LLM-judge answer-quality eval with human-review queue`

#### T5.3 — Out-of-set corpus (the "AI SOC assistant" eval)

- **Objective:** Headline metric for Principles 3. ~30 questions deliberately outside
  both registries: 10 deferred-class asks, 10 general SOC asks (triage advice, log
  source questions, TI lookups), 10 paraphrase-beyond-threshold mutations.
- **Files:** new `docs/evals/out_of_set_corpus.jsonl` (Anurag reviews rows in PR);
  runner = `eval_answer_quality.py --corpus out_of_set`.
- **Pass criteria (definitive):** 100% of rows produce a planned answer or honest
  out-of-catalog contract (zero silent-generic — checked structurally); Tier-D pass-rate
  ≥ 90%; zero severity-without-policy leaks; zero `execution_eligible=true`.
- **Commit:** `feat: add out-of-set eval corpus with structural no-silent-generic gate`

---

## Part D — Sequencing

| Order | Tasks | Heavy gates at end |
|-------|-------|--------------------|
| 1 | T-PRE.1 → T-PRE.2 → T-PRE.3 | sentinel baseline frozen on master |
| 2 | T4.1, T4.2 (security first), T5.1 | governance regression |
| 3 | T0.1 → T0.2 → T0.3 → T0.4 | full 105 + PowerGrid 50 + governance regression |
| 4 | T1.1 → T1.2 (baseline) → T1.3 → T1.4 | paraphrase eval ≥0.90 + full 105 + governance |
| 5 | T0.5 (needs T1.4 fallback + T3.1 data) | governance regression |
| 6 | T2.1 → T2.2 → T2.3 (sentinel re-freeze) → T2.4 | governance regression |
| 7 | T3.1 → T3.2; T5.2 → T5.3 | out-of-set corpus gate |
| 8 | T4.3 → T4.4 | docker build + governance regression |
| 9 | T4.5 | COE sign-off (E5) |

## Part E — Global pass/fail summary

**The whole plan passes when:**
- Sentinel 17/17 + parity green continuously; final re-freeze diffs are additive sections only.
- Full 105 honoring ≥ 95/105 (no regression from current), PowerGrid 50/50, governance
  regression exit 0 + harness 6/6, frontend + docker builds green.
- Paraphrase eval ≥ 0.90; out-of-set corpus: 0 silent-generic, Tier-D ≥ 0.90, 0 severity
  leaks, 0 `execution_eligible=true`.
- T4.2 injection tests green (hard blocker).
- Every answer carries `plan_source` + step provenance; 100% of executed LLM-proposed
  steps passed deterministic validation.
- MCP execution flags still false in `.env.example` and defaults; no new env flags
  introduced (verify: `git diff master -- .env.example` shows no new keys).

**Any of these = stop the line (E3/E1):** sentinel severity/route diff; EC parity test
red; injection string in prose; existing test expectation edited to pass; eval threshold
loosened without Anurag sign-off.
