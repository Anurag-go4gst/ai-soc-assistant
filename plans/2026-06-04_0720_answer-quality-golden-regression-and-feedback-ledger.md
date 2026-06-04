# Answer Quality Golden Regression and Feedback Ledger Plan

**Created:** 2026-06-04  
**Status:** Plan saved for review; implementation not started  
**Canonical for:** golden-answer regression across 105-question runtime map + use-case catalog, durable chat-turn logging, analyst feedback loop  
**Coordination:** [`2026-06-04_PARALLEL_AGENT_COORDINATION.md`](2026-06-04_PARALLEL_AGENT_COORDINATION.md)  
**Related:** [`plans/2026-06-02_chat-control-plane-master.md`](2026-06-02_chat-control-plane-master.md), [`docs/evals/regression_baseline.md`](../docs/evals/regression_baseline.md), [`backend/app/coverage/question_runtime_map_v1.json`](../backend/app/coverage/question_runtime_map_v1.json), [`backend/app/use_cases/catalog.json`](../backend/app/use_cases/catalog.json)

## Objective

Build a reviewable answer-quality system that lets the team:

1. Run deterministic golden-answer regression for the 105 mapped SOC questions and current use-case catalog.
2. Save every live chat turn with enough non-secret context to reproduce and review answer quality.
3. Let users flag unsatisfactory answers in chat with optional remarks.
4. Convert flagged production questions into golden regression cases so fixes stay fixed.

This plan is intentionally separate from live MCP execution and final LLM synthesis. It evaluates and improves the governed answer surface without changing execution authority.

## Current State

### What Exists

| Area | Current status |
|------|----------------|
| 105 question map | Present at `backend/app/coverage/question_runtime_map_v1.json`; 105 rows with runtime and MITRE metadata |
| Use-case catalog | Present at `backend/app/use_cases/catalog.json`; currently 46 use cases |
| Registry exports | Frontend downloads added under Knowledge -> Mapping Exports; CSV and JSON |
| Structural eval | `stage3l_105_shadow_eval.py` checks routing/governance structure for 105 map |
| Focused chat golden tests | `test_chat_control_plane_golden.py` covers selected high-risk flows |
| Telemetry | DB telemetry can store traces, steps, RAG/LLM/MCP logs, SPL validation, harness results |

### What Is Missing

| Gap | Impact |
|-----|--------|
| No full golden-answer suite for all 105 + catalog use cases | Regressions in final answer wording, MITRE visibility, SPL status, and clarification behavior can slip through |
| No durable chat-turn ledger | Hard to compare actual user questions and final answers over time |
| No user feedback capture | Analysts cannot flag poor answers in-product |
| No review workflow | Flagged answers do not become actionable engineering work |
| No feedback-to-golden promotion path | Fixed issues can recur without a regression row |

## Relationship To Existing Tests

This plan adds a new layer. It does not replace the existing structural and control-plane suites.

| Layer | Artifact | What it proves |
|-------|----------|----------------|
| Structural 105 | `backend/app/evals/stage3l_105_shadow_eval.py` | 105-question map/governance consistency and shadow route classification |
| Control-plane E2E | `backend/app/tests/test_chat_control_plane_golden.py` | Flag-on pipeline behavior for seven critical flows |
| Answer-quality | `backend/app/evals/golden_answers/*.jsonl` + `golden_answer_runner.py` | Scaled and feedback-driven final-answer regression |

Tier 0 must avoid duplicating the seven deep control-plane cases in two independent places. The implementation should either:

1. wrap/import the same seven expectations from a shared fixture module; or
2. make the JSONL golden rows the shared fixture source and have `test_chat_control_plane_golden.py` consume those rows for overlapping cases.

Do not maintain two separate hand-written definitions for the same seven critical flows.

## Principles

1. **Correctness is not always an answer.** For many catalog rows, the correct response is clarification, insufficient evidence, or gated SPL, not a confident investigation answer.
2. **Do not exact-match long prose by default.** Golden tests should assert stable facts, statuses, inclusions, exclusions, and governed decisions. Exact text should be reserved for short safety-critical phrases.
3. **Store enough context to review, not secrets.** Save normalized answer artifacts and trace decisions; rely on existing telemetry redaction/minimization for sensitive payloads.
4. **User feedback is evidence, not authority.** A thumbs-down opens review; it does not automatically change catalog mappings or prompts.
5. **Every production fix should produce or update a golden case.** This is the loop that turns live dissatisfaction into regression coverage.

## Plan compatibility & multi-agent execution

**Sibling plan:** [`2026-06-04_0703_general-soc-reasoning-answer-contract.md`](2026-06-04_0703_general-soc-reasoning-answer-contract.md) (negative-evidence + `AnswerContract` + `final_answer_validator`). **Canonical pipeline:** [`2026-06-02_chat-control-plane-master.md`](2026-06-02_chat-control-plane-master.md). **E2E reference:** `.cursor/plans/query-to-answer_traversal_audit_4af31549.plan.md`. **Coordination hub:** [`2026-06-04_PARALLEL_AGENT_COORDINATION.md`](2026-06-04_PARALLEL_AGENT_COORDINATION.md).

### Non-contradiction (load-bearing)

| Rule | This plan | Sibling plan |
|------|-----------|--------------|
| Production default | Do not set `CONTROL_PLANE_ENABLED=true` globally | Same |
| Pipeline authority | Observe and record; **never** auto-change catalog/routing from feedback | Contract/validator only when flag on; no routing edits |
| Golden expectations | Structured fields + phrases; not full prose unless deterministic | May change flag-on MITRE/summary — **update shared fixture**, not duplicate tests |
| Governance CI | Add Tier 0 to `run_stage3_governance_regression.sh` **only after** Agent A Commit 3 + shared fixture | Agent A adds behavior matrix — opt-in `@pytest.mark.matrix` if slow |

### Shared golden fixture (mandatory)

Same as sibling plan:

```text
backend/app/evals/fixtures/control_plane_critical_flows.json
```

- `test_chat_control_plane_golden.py` → thin wrapper over fixture.
- `golden_answer_runner --tier 0` → loads same rows.
- **Do not** snapshot known-bad routing (e.g. "escalation policy" → `auth_failed_login_spike`) as Tier 0 truth until routing fix or case tagged `routing_wrong` / `expected_behavior_user_education`.

### Implementation order (do not invert)

```text
1. Agent A: General SOC Commits 1–3 + shared fixture (0703 plan)
2. Agent B: Phase 1 ledger (this plan) — parallel OK if post-response only, fail-open
3. Agent B: Phase 2 feedback API + FE
4. Agent B: Phase 4–5 Tier 0 golden runner — after step 1 fixture exists
5. Agent B: Phase 6 full 105+46 — shallow route/mode first; deep MITRE/SPL only when expectation matrix says eligible
6. Add Tier 0 to governance script — same commit as stable Tier 0 green
```

### Agent ownership (Claude / Codex / Cursor)

| Agent | Owns | Must not touch without coordination |
|-------|------|-------------------------------------|
| **Agent B (this plan)** | `quality/chat_turn_store.py`, migrations, `/chat/feedback`, `/quality/*`, `evals/golden_answers/`, `golden_answer_runner.py`, FE feedback | `mitre_decision.py`, `answer_contract.py`, `final_answer_validator.py`, `analyst_response_builder` contract assembly |
| **Agent A (0703 plan)** | See sibling plan table | DB schema, feedback routes, ledger |

**Merge gate:** governance script PASS (flag-off baseline); `npm run build` if FE touched; ledger tests prove **chat succeeds when DB write fails**.

### Safe parallelism

- **Start Phase 1 first** (recommended in this plan) — does not require golden suite.
- **Defer Phase 4–6** until Agent A lands shared fixture + stable flag-on golden.
- **Serialize:** `pipeline.py` finalize section — coordinate with Agent A; prefer ledger hook at **end** of `build_live_chat_response` / graph return, not inside MITRE/validator nodes.

### Recording flag-on vs flag-off turns

Store `control_plane_enabled` (or derive from trace) on each `chat_turns` row so reviewers can separate legacy vs control-plane behavior during rollout.

## Target Architecture

```text
User /chat request
  -> normal governed chat pipeline
  -> PlaceholderResponse
  -> ChatTurnLedger.record_turn(...)
       - question
       - final answer fields
       - route/evidence/MITRE/SPL decisions
       - source refs and redacted trace
  -> UI displays answer + feedback controls
       - satisfied
       - not satisfied
       - optional remarks
  -> /chat/feedback records feedback
  -> Quality review queue
       - triage root cause
       - assign fix
       - promote to golden case
  -> golden-answer runner prevents recurrence
```

## Data Model

### New Table: `chat_turns`

Purpose: one durable row per answered chat turn.

Recommended columns:

| Column | Type | Notes |
|--------|------|-------|
| `turn_id` | UUID/text primary key | Generated by backend |
| `trace_id` | text indexed | Links existing telemetry |
| `created_at` | timestamptz | Server time |
| `user_id` | text nullable | Auth username or anonymous/system |
| `session_id` | text nullable | Future browser/session correlation |
| `user_query` | text | Original user question |
| `normalized_query` | text | Lowercase whitespace-normalized |
| `selected_skill` | text nullable | Response selected skill |
| `selected_use_case_id` | text nullable | From selected use case |
| `question_ref` | text nullable | Exact/near 105-map match when available |
| `answer_mode` | text nullable | Evidence plan answer mode |
| `response_mode` | text nullable | Response synthesis/gating mode |
| `final_message` | text nullable | Top-level message shown to user |
| `analyst_summary` | text nullable | If present |
| `analyst_response` | jsonb | Full analyst card, redacted/minimized |
| `candidate_spl` | text nullable | Candidate or normalized SPL, never execution result secrets |
| `spl_validation` | jsonb | Validator result |
| `mitre_decision` | jsonb | Runtime decision including rejected/not-claimed |
| `mitre_mappings` | jsonb | Visible mappings |
| `source_evidence_refs` | jsonb | IDs, types, counts, refs; no raw sensitive rows beyond preview already exposed |
| `control_plane_trace` | jsonb | Redacted trace |
| `execution_status` | text nullable | `blocked`, `not_attempted`, `executed_mock`, etc. |
| `llm_used` | bool | Derived |
| `rag_used` | bool | Derived |
| `mcp_used` | bool | Derived |
| `quality_status` | text | `unreviewed`, `accepted`, `flagged`, `in_review`, `fixed`, `wont_fix` |
| `golden_candidate` | bool | Mark for promotion to regression |

Size policy:

- Keep `chat_turns` denormalized enough for review screens.
- Heavy trace blobs may be minimized snapshots; the full step-level history remains joinable through `trace_id` in telemetry.
- Apply explicit byte caps to `analyst_response` and `control_plane_trace` JSON before insert.
- Default retention target: 90 days for raw live chat-turn rows unless COE/customer policy requires a different period.

### New Table: `chat_answer_feedback`

Purpose: allow multiple feedback events per turn.

| Column | Type | Notes |
|--------|------|-------|
| `feedback_id` | UUID/text primary key | Generated by backend |
| `turn_id` | text indexed | References `chat_turns.turn_id` |
| `trace_id` | text indexed | Convenience |
| `created_at` | timestamptz | Server time |
| `user_id` | text nullable | Auth username |
| `rating` | text | `up`, `down`, `neutral` |
| `remark` | text nullable | Optional analyst comment |
| `category` | text nullable | Optional UI/reviewer category |
| `review_status` | text | `new`, `triaged`, `fixed`, `wont_fix` |

Duplicate feedback policy:

- Default: one feedback row per `(turn_id, user_id)`.
- Submitting feedback again updates the existing row (`upsert`) and appends an audit event in the review history.
- A later thumbs-up after thumbs-down is allowed, but the old negative remark remains visible in review history.
- `remark` must be capped in both API validation and DB constraint. Initial cap: 2000 characters.

### New Table: `answer_quality_reviews`

Purpose: internal reviewer decisions and fix linkage.

| Column | Type | Notes |
|--------|------|-------|
| `review_id` | UUID/text primary key | Generated by backend |
| `turn_id` | text indexed | Reviewed turn |
| `created_at` | timestamptz | Server time |
| `reviewer_id` | text | Reviewer username |
| `root_cause` | text | See root-cause taxonomy below |
| `review_notes` | text | Human notes |
| `recommended_action` | text | What should change |
| `linked_issue` | text nullable | Ticket/issue |
| `linked_pr` | text nullable | PR/commit |
| `golden_case_id` | text nullable | Regression case created/updated |
| `status` | text | `open`, `fixed`, `wont_fix` |

### Root-Cause Taxonomy

Use a closed enum so analytics is useful:

- `routing_wrong`
- `use_case_missing`
- `catalog_mapping_wrong`
- `mitre_decision_wrong`
- `rag_missing_or_wrong`
- `spl_template_missing`
- `spl_template_wrong`
- `llm_fallback_wrong`
- `answer_wording_wrong`
- `frontend_display_wrong`
- `insufficient_user_context`
- `source_unavailable`
- `expected_behavior_user_education`

### Status Source Of Truth

Avoid three divergent status fields:

- `chat_answer_feedback.review_status` tracks the individual feedback item.
- `answer_quality_reviews.status` tracks a reviewer action record.
- `chat_turns.quality_status` is a derived/convenience rollup updated from latest feedback + latest review:
  - any new negative feedback -> `flagged`
  - active review -> `in_review`
  - latest completed review -> `fixed` or `wont_fix`
  - positive feedback with no negative history -> `accepted`
  - no feedback/review -> `unreviewed`

## API Plan

### Chat Turn Logging

Record after every non-clear `/chat` response.

Implementation:

- Add `backend/app/quality/chat_turn_store.py`
- Add a single `post_chat_response(response, request, *, entrypoint, user)` helper.
- Call the helper from every chat entrypoint:
  - sync `/chat` final response
  - LangGraph wrapper final response
  - streaming final event path when streaming is enabled
  - any future direct pipeline entrypoint
- Return `turn_id` in `PlaceholderResponse` so frontend can attach feedback.
- Do not fail chat if logging fails; increment telemetry failure counter or local quality write failure metric.
- Explicitly skip `/clear`.
- Exclude or tag Experience Center/demo responses (`demo_mode=true`, `coe_synthetic_fixture=true`) so production quality metrics are not polluted by synthetic fixtures.

Do not put the only ledger hook in `routes_chat.chat()` if another path can return a chat answer before that function reaches `build_live_chat_response()`. The hook must be centralized enough that sync chat, streaming, and LangGraph all attach `turn_id` consistently.

### Feedback API

Add routes:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat/feedback` | Save user rating and optional remark |
| `GET` | `/quality/chat-turns` | Review queue, filters |
| `GET` | `/quality/chat-turns/{turn_id}` | Full review detail |
| `PATCH` | `/quality/chat-turns/{turn_id}/review` | Reviewer status/root cause/action |
| `POST` | `/quality/chat-turns/{turn_id}/promote-golden` | Create draft golden case |

Initial implementation may only expose `POST /chat/feedback`; review endpoints can follow once ledger is stable.

Auth and authorization:

- `POST /chat/feedback` may use the same authenticated analyst session as `/chat`.
- `/quality/*` review APIs require an explicit gate before exposure:
  - preferred: `quality_reviewer` role or env allowlist; or
  - minimum: `QUALITY_REVIEW_ENABLED=true` plus audit logging of every review read/update.
- Do not expose `/quality/chat-turns` to every logged-in analyst by default.

### Export API

Later enhancement:

- `GET /quality/chat-turns/export?format=csv`
- `GET /quality/feedback/export?format=csv`

Exports must use the same redaction rules as `control_plane_trace` redaction and must not include secrets, tokens, raw credentials, or unrestricted source rows.

## Frontend Plan

### Chat Feedback Controls

Add to each assistant answer:

- thumbs up button
- thumbs down button
- optional remark text area when thumbs down selected
- submit state: `saved`, `failed`, `already submitted`

UX constraints:

- Keep compact; do not distract from SOC answer.
- Do not ask for feedback before answer is complete.
- Tie feedback to `turn_id`; fallback to `trace_id` only if needed.
- Streaming clients must receive `turn_id` on the SSE final event so feedback can be submitted without a second request.
- Add `turn_id` and feedback request/response types to `frontend/src/types/api.ts`.

### Quality Review Page

Add later under a protected/admin section:

- list flagged turns
- filters by status, root cause, selected skill, use case, question ref
- show question + final answer + analyst response + MITRE decision + SPL validation + control trace
- reviewer fields: root cause, notes, recommended action, status
- button: “Create golden candidate”

## Golden Dataset Design

### Directory

```text
backend/app/evals/golden_answers/
  README.md
  question_105_golden.jsonl
  use_case_catalog_golden.jsonl
  flagged_regressions.jsonl
```

### Golden Case Schema

```json
{
  "case_id": "q0.q046",
  "source": "question_runtime_map",
  "query": "Which users have excessive failed logins?",
  "tags": ["auth", "failed_login", "mitre"],
  "expected": {
    "selected_skill": "attack_discovery",
    "selected_use_case_id": "auth_failed_login_spike",
    "answer_mode": "hybrid",
    "response_mode": "deterministic_knowledge_or_routing",
    "candidate_spl": {
      "required": true,
      "approved": true,
      "must_include": ["index=pgcil_soc", "sourcetype=pgcil:auth"],
      "must_not_include": ["delete", "outputlookup"]
    },
    "mitre": {
      "visible": ["T1110.001"],
      "not_visible": ["T1078"],
      "not_claimed": []
    },
    "answer_text": {
      "must_include": ["failed login"],
      "must_not_include": ["confirmed compromise", "executed in Splunk"]
    },
    "required_env": {
      "CONTROL_PLANE_ENABLED": "true",
      "MCP_GLOBAL_EXECUTION_ENABLED": "false",
      "AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED": "false"
    },
    "execution": {
      "allowed": false,
      "expected_status": "blocked"
    }
  }
}
```

### Case Tiers

| Tier | Scope | Purpose |
|------|-------|---------|
| Tier 0 | 10-20 critical flows | CI blocking immediately |
| Tier 1 | all answerable 105 rows | Broader routing/answer-mode checks |
| Tier 2 | all 46 use-case catalog rows | Catalog-to-chat behavior |
| Tier 3 | flagged live regressions | Production feedback prevention |

### Case Categories

Each case must declare one expected outcome:

- `answer`
- `spl_candidate`
- `rag_policy`
- `mitre_mapping`
- `clarification`
- `unsupported`
- `source_unavailable`

This avoids treating safe clarification as failure.

## Golden Runner

Add:

`backend/app/evals/golden_answer_runner.py`

Responsibilities:

1. Load JSONL cases.
2. Apply per-case `required_env` metadata, with safe defaults:
   - `CONTROL_PLANE_ENABLED=true`
   - `MCP_GLOBAL_EXECUTION_ENABLED=false`
   - `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=false`
   - no live MCP
   - no direct LLM-to-MCP
3. Convert response to a compact observed record.
4. Apply deterministic assertions.
5. Emit JSON and Markdown reports.

Live synthesis nondeterminism:

- The runner must force final synthesis/live narration off unless a case explicitly opts into authority-field-only assertions.
- Phrase checks against `final_message`, `analyst_summary`, or `analyst_response.one_sentence_finding` are allowed only when `synthesis_mode` is deterministic.
- When live synthesis is enabled, assert authority fields only: `mitre_decision`, `spl_validation`, `execution`, `response_mode`, `answer_mode`, and visible/not-claimed technique sets.

Commands:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --tier 0 --json
PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --all --json
```

Output:

```text
docs/evals/out/golden_answer_eval.json
docs/evals/out/golden_answer_eval.md
```

## Assertion Types

Use a small deterministic assertion engine:

| Assertion | Example |
|-----------|---------|
| `equals` | `selected_skill == attack_discovery` |
| `in_set` | `response_mode in [...]` |
| `present` | `candidate_spl.normalized_spl` present |
| `absent` | no `execution.executed_spl` |
| `contains_all` | answer contains required phrases |
| `contains_none` | answer excludes unsafe phrases |
| `techniques_visible` | visible MITRE exactly/at least expected |
| `techniques_not_claimed` | rejected techniques appear only in not-claimed |
| `json_path_equals` | precise nested field |

Avoid broad exact matching of full answers unless the answer is intentionally fixed text.

## Phased Implementation

### Phase 0 — Baseline Audit

Deliverables:

- Document current eval/logging coverage.
- Export current 105 + 46 maps to `docs/evals/out/`.
- Identify which rows are answerable, clarification-required, source-dependent, or unsupported.
- Create the explicit expectation matrix:
  - `docs/evals/out/answer_expectation_matrix.json`
  - `docs/evals/out/answer_expectation_matrix.md`

The matrix is the source for Phase 6 expansion. It must include, per 105 row and per catalog row:

- row id (`question_ref` or `use_case_id`)
- query/display name
- expected outcome category: `answer`, `clarification`, `spl_candidate`, `source_unavailable`, `unsupported`, `rag_policy`, `mitre_mapping`
- dependency class
- deep-assertion eligible: `true`/`false`
- reason when deep assertions are not currently eligible

Verification:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_question_runtime_map_stage3l_s6.py app/tests/test_stage3l_105_shadow_eval.py -q
```

### Phase 1 — Chat Turn Ledger

Deliverables:

- DB migration for `chat_turns`.
- `chat_turn_store.py`.
- Add `turn_id` to `PlaceholderResponse`.
- Record turn after `/chat` response.
- Redaction/minimization tests.
- Add `turn_id` to streaming final event shape if streaming route is active.

Tests:

- chat still succeeds if ledger write fails
- turn row includes question, final answer, selected skill, use case, MITRE decision, SPL validation
- secrets are redacted/minimized

### Phase 2 — User Feedback Capture

Deliverables:

- DB migration for `chat_answer_feedback`.
- `POST /chat/feedback`.
- frontend thumbs up/down + optional remarks.
- feedback attached to `turn_id`.

Tests:

- valid feedback saved
- unknown `turn_id` rejected or stored as orphan only if explicitly allowed
- duplicate feedback follows the upsert policy and preserves review history
- remarks length capped

### Phase 3 — Quality Review API

Deliverables:

- `answer_quality_reviews` migration.
- Review queue endpoints.
- Root-cause enum validation.
- CSV export for review queue.

Tests:

- list flagged turns
- update review status
- root-cause enum rejects unknown values

### Phase 4 — Golden Case Schema and Tier 0

Deliverables:

- `golden_answers/README.md`
- JSON schema/model for golden cases.
- Tier 0 cases for critical flows:
  - the same seven critical control-plane flows from `test_chat_control_plane_golden.py`, imported from/shared with one fixture source
  - any additional feedback-derived critical flow approved for Tier 0

Tests:

- schema validation
- runner passes Tier 0

### Phase 5 — Golden Runner

Deliverables:

- `golden_answer_runner.py`
- JSON/Markdown reports.
- pytest wrapper for Tier 0.
- optional non-blocking command for all cases.

Tests:

- intentionally bad fixture fails with clear reason
- runner records observed answer summary
- reports include pass/fail by category and source

### Phase 6 — Expand to 105 + 46

Deliverables:

- Generate draft golden rows from current exports.
- Consume `docs/evals/out/answer_expectation_matrix.json`.
- Add deterministic expectations for every row.
- Mark source-dependent rows as expected clarification until connectors/content exist.

Acceptance:

- all 105 rows have at least route/answer-mode expectations
- all 46 catalog rows have at least use-case/skill/expected outcome expectations
- critical rows have deeper MITRE/SPL/RAG assertions

### Phase 7 — Feedback to Golden Promotion

Deliverables:

- `promote-golden` endpoint creates a draft JSONL case from a flagged turn.
- Reviewer can edit expectations before committing.
- Link review row to `golden_case_id`.

Tests:

- flagged turn converts to draft case
- draft case includes observed fields and empty expected fields for reviewer completion

### Phase 8 — Dashboard

Deliverables:

- Quality review page.
- Coverage summary:
  - total turns
  - flagged rate
  - unresolved flagged turns
  - golden coverage for 105 and catalog
  - failing golden cases

This can be after backend capability; do not block Phase 1-7.

## Data Sufficiency Review

### Enough Today

Current response and trace objects contain enough for:

- selected skill
- use case
- candidate SPL and validation
- execution gating status
- RAG/source evidence previews
- MITRE runtime decision
- control-plane trace
- analyst response card

### Not Enough Today

Current telemetry is not enough for:

- durable final answer history
- user satisfaction tracking
- reviewer notes/root cause
- linking bad answers to fixes
- measuring quality trend over time
- comparing answer before/after a fix for the same query

### Must Preserve in Ledger

For answer-quality review, every saved turn should include:

- exact user query
- final top-level message
- full analyst response card
- response mode and answer mode
- selected use case and question ref if matched
- candidate SPL and validation result
- MITRE decision and visible/not-claimed techniques
- source evidence refs and summary
- control-plane trace after redaction
- whether LLM/RAG/MCP participated

Do not store raw secrets, provider tokens, or full sensitive source rows beyond the preview already exposed in the answer.

## Privacy And Retention

User queries and feedback remarks may contain customer identifiers, usernames, IP addresses, hostnames, ticket IDs, or incident details.

Requirements:

- cap feedback remarks at 2000 characters;
- cap/minimize stored JSON blobs;
- redact using the same secret-minimization approach used for telemetry/control-plane trace;
- default retention target: 90 days for raw turn/feedback rows;
- keep aggregate quality metrics longer only after removing raw query/remark text;
- document any customer-specific retention override before production rollout;
- export endpoints must apply redaction and support scoped review access only.

## Governance Boundaries

This plan must not:

- enable real MCP execution
- execute candidate SPL
- let LLM call MCP
- silently make LLM fallback authoritative
- use user feedback to auto-edit catalog data
- expose secrets in quality exports
- convert source-dependent rows into confident answers

## Rollout Gates

| Gate | Required before |
|------|-----------------|
| Ledger write fail-open test | enabling ledger in dev |
| Feedback API auth test | exposing feedback button |
| Tier 0 golden suite green | merging golden runner |
| Redaction/minimization test | storing trace/answer JSON |
| Privacy retention policy documented | enabling production ledger |
| CSV/JSON export no-secret test | enabling review exports |
| Tier 0 added to governance script | making answer-quality runner blocking |
| Full backend pytest + frontend build | deploy |

Canonical regression integration:

- Keep flag-off baseline + 105 shadow eval as-is.
- Add flag-on Tier 0 answer-quality runner to `./scripts/run_stage3_governance_regression.sh` only after Tier 0 is stable.
- Update `docs/evals/regression_baseline.md` counts and expected checks in the same commit.
- Keep full 105+46 answer-quality suite available as a separate non-blocking report until row expectations are reviewed.

## Verification Commands

Phase-scoped:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_chat_control_plane_golden.py -q
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_question_runtime_map_stage3l_s6.py app/tests/test_stage3l_105_shadow_eval.py -q
```

Full:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest -q

cd frontend
npm run build
```

Golden runner after implementation:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --tier 0 --json
PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --all --json
```

## Self-Review

### Strengths

- Keeps answer-quality work separate from execution enablement.
- Treats clarification and source unavailability as valid expected outcomes.
- Uses deterministic assertions instead of brittle full-paragraph matching.
- Creates a closed feedback loop from user dissatisfaction to regression coverage.
- Stores enough context to debug final answer quality without depending only on low-level telemetry.

### Risks

| Risk | Mitigation |
|------|------------|
| Golden rows become too shallow | Tier critical rows; require deep assertions for Tier 0 and all flagged regressions |
| Golden rows become too brittle | Prefer structured fields and phrase exclusions over full exact text |
| Ledger stores sensitive data | Reuse telemetry minimization/redaction; add explicit no-secret tests |
| Feedback volume grows without review | Add review queue statuses and root-cause taxonomy early |
| Source-dependent rows falsely fail | Classify expected outcome as `source_unavailable` or `clarification` until source readiness exists |
| Review UI delays backend value | Implement backend ledger and feedback first; UI review dashboard later |

### Plan Quality Decision

This plan is satisfactory to save because it:

- addresses both requested tracks: golden regression and user feedback logging;
- explicitly reviews whether current observations are sufficient;
- keeps governance boundaries intact;
- defines concrete tables, endpoints, frontend behavior, runner shape, and phased tests;
- avoids claiming all 105 + 46 can have high-confidence final answers before source/content readiness exists.

## Recommended Next Step

Implement **Phase 1 — Chat Turn Ledger** first. It creates the durable dataset needed for both live feedback review and future golden-case generation. Do not start with the full 151-case golden suite; without real flagged/live observations, that would create many shallow expectations and high maintenance cost.
