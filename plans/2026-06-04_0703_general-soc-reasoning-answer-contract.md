# General SOC Reasoning & Answer-Goal Validation Layer

**Date:** 2026-06-04
**Branch:** `feat/deterministic-spl-llm-fallback` (~333 lines uncommitted across the same files this plan edits — `pipeline.py`, `analyst_response_builder.py`, `mitre_decision.py`, `query_signals.py`, `control_plane_trace.py`, `responses.py`, FE). **Reconcile first** (memory: parallel-chats-reconcile-first): commit or stash the WIP before Commit 1. The WIP already adds the `query_signals` plumbing Commit 1 consumes — confirm it isn't duplicating intended Commit 3 builder work before squashing into Commit 1.
**Gate:** all new behavior runs only under `CONTROL_PLANE_ENABLED` (default `false`). Do **not** flip the default.
**Saved at:** `plans/2026-06-04_0703_general-soc-reasoning-answer-contract.md`. Add a row to the `CLAUDE.md` Plans table once approved.
**Status:** Proposed — awaiting review.
**Coordination:** [`2026-06-04_PARALLEL_AGENT_COORDINATION.md`](2026-06-04_PARALLEL_AGENT_COORDINATION.md)

---

## Context

The SOC engine currently encodes reasoning **per question/pattern**, not as reusable rules. Concretely, negative-evidence reasoning (e.g. "failed logins but no successful login → do not claim T1078 Valid Accounts") is hardcoded in three places:

- `backend/app/threat/mitre_decision.py:16` — `_DEFAULT_NOT_CLAIMED = ("T1003","T1078","T1562.001")`, applied at `:80` and `:124`.
- `backend/app/chat/analyst_response_builder.py:177-190` — `_NOT_CLAIMED_DETAILS` dict mapping those same three techniques to fixed prose.
- `backend/app/chat/analyst_response_builder.py:230-244` — `_governed_summary` literal string match on `"no successful login" and "no endpoint telemetry" and "no evidence of credential dumping"`.

This only works for the failed-login scenario. It does not generalize to DNS/DGA, phishing, malware, network, exfiltration, or lateral movement, and it forces a new patch per question.

**Goal:** replace per-question patches with a general, data-driven reasoning + answer-goal validation layer so the engine answers prudently across use cases by *reason*, not by pattern. This is **consolidation + generalization of existing fragments**, not a new architecture.

**Already exists (reuse, do not duplicate):**
- Negative-evidence signal extraction — `query_signals.py:66-77` (`negative_successful_login`, `negative_endpoint_telemetry`, `negative_cred_dumping`). Extend to also read RAG/evidence; do not re-implement.
- Authority deciders — `IntentClassification` (`answer_goal`, `intent_family`), `EvidencePlan` (`spl_allowed`/`mcp_allowed`/`policy_context_required`/`action_mode`), `MitreDecision` (permitted/candidate/blocked/`not_claimed`), `SeverityDecision`, `ContextSufficiency` (7 modes), `StructuredContextPackage.allowed_conclusions`/`prohibited_conclusions`, action policy / `blocked_actions`.
- Validator output shapes — `answer_guard/models.py` `AnswerGuardStatus` (status `disabled|passed|blocked|skipped`) and `GuardResult` (severity `info|warning|blocking_candidate`). Reuse these so the trace already renders.

## Authority principle (load-bearing)

The **AnswerContract is a deterministic projection / read-model — it makes zero new decisions.** Every field must source from an existing decider. If a field has no source, the missing rule belongs **in the relevant decider** (MitreDecision, EvidencePlan, severity), never invented in the contract. This keeps it from becoming a sixth conflicting authority.

The deterministic **final_answer_validator is the backstop; the builder is the primary enforcer.** A blocked finding surfacing as a positive claim is a *builder bug* — the validator catches it and **fails closed** (routes to `analyst_review_required` / `human_review`, records `blocking_candidate` in trace). It does **not** silently repair, which would mask the upstream defect.

Gating disambiguation: the deterministic contract + validator run whenever `CONTROL_PLANE_ENABLED` is on. They are **not** gated by `AI_SOC_LLM_ANSWER_GUARD_ENABLED` — that flag governs the separate dormant *LLM-draft* semantic guard (`answer_guard/rules.py`), which stays as-is.

---

## Commit sequence (5 commits, one defect-class each)

### Commit 1 — Generalize negative-evidence → blocked findings (lead with the de-hardcode)

**Naming (avoid collision):** the control plane already uses "precondition" for MCP precondition shadow (`precondition_evaluation` in trace). Name the new module **`mitre_evidence_preconditions.py`** and use the phrase **"MITRE evidence precondition"** in docs/trace keys.

**New:** `backend/app/threat/mitre_evidence_preconditions.py` — data-driven table mapping MITRE techniques to required-evidence preconditions and the negative-evidence signal that negates them. Keyed to the signal vocabulary, generalizes beyond auth:

```
T1078     requires successful_login          ; negated by no_successful_login
T1003     requires credential_dumping_evidence; negated by no_credential_dumping
T1562.001 requires endpoint_telemetry        ; negated by no_endpoint_telemetry
T1041/exfil requires outbound_transfer       ; negated by no_outbound_transfer
... (extend per tactic: command_execution, lateral_movement, malware, privileged_account)
```

**v1 tactic scope:** ship auth (the 3 existing signals) + exfil as worked examples; sketch the rest as table rows with `requires_evidence` but no live signal yet (they activate as signals/RAG land). State this explicitly so reviewers know what's wired vs stubbed.

**New:** `backend/app/chat/negative_evidence_extractor.py` — `extract_negative_evidence(query_signals, source_evidence, structured_context) -> NegativeEvidence`. Aggregates absence signals with explicit **precedence: query signals → structured_context → RAG excerpts**. Reuses the `query_signals.py` flags as the query source — do not re-parse the query. RAG `prohibited_conclusions` (e.g. `soc_kb_entries.json:299` `"valid account abuse confirmed"`) both **block techniques** (when they map to a technique precondition) **and constrain prose** — spell out both effects.

**Plumbing reality (corrected):** `_query_signals_from_state` exists (`pipeline.py:1157`) but WIP threads `query_signals` **only into the SPL path** (`_candidate_spl_stage`, `:344`). The MITRE call `_mitre_outputs_for_finalize` (`:451`) does **not** pass `query_signals`, and `resolve_mitre_decision` (`mitre_decision.py:34`) still swallows extras via `**_kwargs` — nothing on the finalize path feeds signals to the MITRE decision yet. Commit 1 must: **add `query_signals` + `source_evidence` + `structured_context` to `_mitre_outputs_for_finalize` and `resolve_mitre_decision`** (`source_evidence`/`structured_context` are available from `_context_stage` at `:397`, before the MITRE call), run them through the extractor, and compute `not_claimed`/`rejected_techniques` from `mitre_evidence_preconditions × NegativeEvidence` instead of static `_DEFAULT_NOT_CLAIMED`.

**Delete `_DEFAULT_NOT_CLAIMED`** (`:16`) and **both** uses (`:80`, `:124`).

**HIL/clarification policy (do not change accidentally):** today `_DEFAULT_NOT_CLAIMED` is also applied in the `requires_alert_context` branch (`:80`), not only the visible/candidate path. Decide and document: in clarification/HIL paths, populate `not_claimed` **only from extracted negative evidence** (not a blanket default) so HIL semantics don't silently shift. If no negative evidence present in an HIL turn → empty `not_claimed`, matching intent.

**`CONTROL_PLANE_ENABLED=false`:** Commit 1 edits `resolve_mitre_decision`, which is only reached on the control-plane path; the legacy `map_mitre_for_use_case` finalize path stays unchanged.

**Tests:** `test_negative_evidence_extractor.py` + extend `test_mitre_decision_runtime.py` — assert the *same* failed-login negative-evidence outcome now comes from the general engine, plus one non-auth case. Note: the exfil example (`no_outbound_transfer → T1041`) has **no query signal yet** — drive that test via `structured_context`/RAG `prohibited_conclusions`, or add the signal in this commit; state which.

### Commit 2 — AnswerContract projection

**New:** `backend/app/chat/contracts/answer_contract.py` — Pydantic `AnswerContract` built by `build_answer_contract(...)`. Fields and their **single source**:

| Field | Source decider |
| ----- | -------------- |
| `user_goal` / `answer_goal[]` | `IntentClassification.answer_goal` |
| `allowed_findings` / `candidate_findings` / `blocked_findings` | `MitreDecision` (visible/candidate/rejected) + `StructuredContextPackage.allowed_conclusions` |
| `not_claimed` / `must_not_claim` | `MitreDecision.not_claimed` + `prohibited_conclusions` + negative-evidence (Commit 1) |
| `evidence_status` / `rag_status` / `mcp_status` / `spl_status` | execution, `soc_kb_retrieval`, `EvidencePlan`, `spl_validation` |
| `response_sections_required` | derived from `answer_goal` (e.g. `analyst_action_guidance` → actions section required) |

**Finding-vocabulary mapping (MitreDecision → contract, stable, no re-deciding):**

- `allowed_findings` ← `MitreDecision.techniques` where status visible/candidate AND `answer_visible`
- `candidate_findings` ← `MitreDecision.registry_candidates` / candidate-status techniques
- `blocked_findings` ← `rejected_techniques ∪ not_claimed`, each carrying a stable reason code from the precondition table
- Never merge `blocked_findings` back into `techniques`.

Pure read-model: no keyword re-parsing, no new MITRE/severity decisions. `build_answer_contract` runs only when `CONTROL_PLANE_ENABLED=true`; the builder accepts `answer_contract=None` on the legacy path.

**Tests:** `test_answer_contract.py` — one per intent_family, asserting every field traces to its source decider.

### Commit 3 — Builder consumes the contract (primary enforcer)

Refactor `analyst_response_builder.build_analyst_response_for_live` to take `answer_contract` and assemble the answer **from it**: blocked findings appear only in `not_claimed`; candidate findings are labeled candidate (never confirmed); actions come from `allowed`/`blocked_actions`. The contract is the input to **both** the deterministic builder and the gated LLM-narration path ("build from contract" holds regardless of synthesis mode — LLM may phrase, but only over allowed/candidate findings).

**Delete the per-pattern hardcoding:** `_NOT_CLAIMED_DETAILS` (`:177-190`, replaced by precondition-table rationale strings) and the literal three-negative match in `_governed_summary` (`:230-244`, replaced by contract-driven prose). `_not_claimed_rows` reads contract `not_claimed` with general reasons.

**Summary-text risk:** removing the `T1110 + three-negative` literal block in `_governed_summary` may shift golden summary prose. The "failed-login card unchanged" bar applies to the summary too — assert on stable summary substrings (candidate-event framing, T1110.001 rationale), not only MITRE rows.

**Tests:** extend `test_chat_control_plane_golden.py` — failed-login card (MITRE rows **and** summary substrings) unchanged; add a non-auth card proving generality.

### Commit 4 — final_answer_validator (fail-closed backstop)

**New:** `backend/app/chat/final_answer_validator.py` — `validate_final_answer(draft, answer_contract, evidence_plan, mitre_decision) -> AnswerGuardStatus`. Deterministic checks (reuse `GuardResult`/`AnswerGuardStatus`):

- No `blocked_findings`/`must_not_claim` item appears as a positive claim.
- No live results when MCP unavailable / `mcp_allowed=false`.
- No answer-visible MITRE when intent suppresses it (`answer_visible=false`).
- No SPL/MCP artifacts on `rag_only`.
- No SPL-only answer when `answer_goal` includes `analyst_action_guidance`.
- Candidate findings not described as confirmed.
- RAG content does not override `MitreDecision`.

On `blocking_candidate`: route to `analyst_review_required` / `human_review`. Wire as a node in `pipeline.graph_node_context_finalize` **after** the answer is assembled, gated on `control_plane_enabled`. The validator runs on the assembled `analyst_response` envelope (what the user sees), **not** the synthesis-lab draft — so its rules match the rendered answer.

**Trace key (distinct from LLM guard):** add under a new key **`final_answer_validation`** (or `answer_contract_validation`) in `control_plane_trace.py` — do **not** nest under or reuse the existing `answer_guard` key (that's the dormant LLM-draft guard).

**Interaction with the 7 sufficiency modes:** specify the contract. On `blocking_candidate`, force `context_sufficiency.status = analyst_review_required` **and** set `human_review.required = true` with the validator's blocking reason — do not leave them inconsistent. Document this alongside the Stage 3J mode list.

**Tests:** `test_final_answer_validator.py` — one failing draft per rule → `blocked` + both `analyst_review_required` mode and `human_review.required` set.

### Commit 5 — Behavior-matrix eval pack

**New:** `backend/app/tests/test_control_plane_behavior_matrix.py` — 30+ cases using the `test_chat_control_plane_golden.py` template (autouse `control_plane_enabled=True` fixture, `_chat()` helper). Categories: policy/RAG-only, live investigation, hybrid, MITRE mapping, **negative evidence** (across auth/DNS-DGA/phishing/malware/network/exfil/lateral movement), SPL-only, MCP unavailable. Asserts contracts (modes, gates, not-claimed presence, no over-claim) — **not** brittle counts/strings, per the LLM-app quality loop.

**CI cost:** the matrix runs under plain `pytest` (so it's in `run_stage3_governance_regression.sh`'s `pytest -q`). If runtime grows the baseline noticeably, mark it `@pytest.mark.matrix` and add an opt-in target rather than bloating the canonical regression — decide at implementation time based on measured duration.

---

## Plan compatibility & multi-agent execution

**Sibling plan:** [`2026-06-04_0720_answer-quality-golden-regression-and-feedback-ledger.md`](2026-06-04_0720_answer-quality-golden-regression-and-feedback-ledger.md) (ledger + golden runner). **Canonical pipeline:** [`2026-06-02_chat-control-plane-master.md`](2026-06-02_chat-control-plane-master.md) (Phases 0–11 complete). **E2E map / bugs:** `.cursor/plans/query-to-answer_traversal_audit_4af31549.plan.md` (read-only reference; do not duplicate MCP/synthesis work here). **Coordination hub:** [`2026-06-04_PARALLEL_AGENT_COORDINATION.md`](2026-06-04_PARALLEL_AGENT_COORDINATION.md).

### Non-contradiction (load-bearing)

| Rule | This plan | Sibling plan |
|------|-----------|--------------|
| Production default | `CONTROL_PLANE_ENABLED=false` — **do not flip** | Same; golden cases use `true` only in tests |
| Runtime authority | `AnswerContract` is a **read-model**; no sixth decider | Feedback is **not** authority; ledger is fail-open |
| Golden tests | Extend / share fixtures; do **not** fork seven critical flows | Tier 0 must **import** shared fixture (see below) |
| MCP / synthesis / demo | Out of scope (hard boundaries below) | Out of scope |
| CI | Behavior matrix may be `@pytest.mark.matrix` if slow | Tier 0 in governance script **only after** shared fixture + this plan's Commit 3 stable |

### Shared golden fixture (mandatory before parallel agents diverge)

Create **one** source of truth (implement in **either** plan's first golden-touch commit; prefer **Commit 3 here** or **Answer-quality Phase 4**):

```text
backend/app/evals/fixtures/control_plane_critical_flows.json
```

- `test_chat_control_plane_golden.py` and `golden_answer_runner` Tier 0 **must load the same rows**.
- **Forbidden:** two hand-written lists of the seven critical flows.
- When this plan changes MITRE/summary prose (Commit 3), update **fixture expected substrings** in that single file only.

### Implementation order (do not invert)

```text
1. Reconcile WIP on feat/deterministic-spl-llm-fallback (or merge to master) — see header
2. Agent A: General SOC Commits 1–5 (this plan), flag-gated only
3. Shared fixture module (if not done in step 2 Commit 3)
4. Agent B: Answer-quality Phase 1 (ledger) — may start after step 2 Commit 1 if no golden edits
5. Agent B: Answer-quality Phase 4–5 (Tier 0 runner) — only after step 3
6. Traversal B5 (use-case split) — separate PR; coordinate with Commit 1 MITRE plumbing
```

### Agent ownership (Claude / Codex / Cursor)

| Agent | Owns | Must not touch without coordination |
|-------|------|-------------------------------------|
| **Agent A (this plan)** | `mitre_evidence_preconditions.py`, `negative_evidence_extractor.py`, `contracts/answer_contract.py`, `final_answer_validator.py`, `analyst_response_builder.py` (flag-on), `mitre_decision.py` (flag-on path), `test_control_plane_behavior_matrix.py` | DB migrations, `routes_chat` feedback APIs, `golden_answer_runner.py`, `.env` default flags |
| **Agent B (0720 plan)** | `chat_turn_store.py`, DB tables, `POST /chat/feedback`, `golden_answers/*.jsonl`, `golden_answer_runner.py`, FE feedback UI | `mitre_decision.py`, `analyst_response_builder` contract logic, routing/adjudication |
| **Either (read-only)** | Traversal audit B1–B3 live MCP/synthesis | Requires explicit stage approval per `AGENTS.md` |

**Merge gate (both agents):** `./scripts/run_stage3_governance_regression.sh` PASS with `CONTROL_PLANE_ENABLED` **unset/false** in CI env (baseline). Flag-on: `pytest app/tests/test_chat_control_plane_golden.py -q` PASS after Agent A changes.

### Safe parallelism

- **Safe in parallel:** Agent B Phase 1 (ledger hook in `pipeline.py` / `routes_chat.py` **post-response only**) while Agent A does Commits 1–2 — if ledger hook is append-only and fail-open.
- **Serialize:** Any edit to `test_chat_control_plane_golden.py`, `pipeline.graph_node_context_finalize`, or shared fixture — **one agent at a time** or single branch.
- **Before opening PR:** `git pull --rebase`; run governance script; confirm no change to `CONTROL_PLANE_ENABLED` default in `config.py` / `.env.example`.

### What "improve" means (acceptance)

- Flag **off:** byte-for-byte behavior unchanged vs pre-PR for `/chat` (except optional `turn_id` if ledger merged — must be additive).
- Flag **on:** failed-login negative-evidence outcome preserved via general engine; policy/SOP routing fixes are **out of scope** unless separate adjudication PR (master §3.2 priority 3).
- No new xfail on baseline tests; do not "fix" baseline by weakening assertions.

---

## Hard boundaries (every commit)

Do not enable live MCP, do not execute `candidate_spl`, do not enable live Foundation-Sec final synthesis, no LLM→MCP. Do not touch Experience Center / demo golden answers. Registry MITRE stays metadata-not-evidence. No per-question fixes — rules must apply across all tactics. Where any commit touches narration hooks, restate the spine §5 universal LLM boundary (LLM phrases prose only; facts stay deterministic authority) in the commit message.

## Doc alignment (update when shipped)

- **Chat control plane master** is marked complete (Phases 0–11). This is logically **post-11** — add a short **"Phase 12 (proposed) — General SOC reasoning & answer-contract validation"** subsection to the master plan (not only the `CLAUDE.md` table) so agents don't treat it as ad-hoc drift.
- **STAGE_3K spine §5:** no conflict (stays deterministic, no LLM→MCP). Footnote that this "deterministic answer-contract validator" is distinct from Q1G shadow narration.
- **Experience Center:** out of scope, unchanged.

## Verification

```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_negative_evidence_extractor.py \
  app/tests/test_answer_contract.py \
  app/tests/test_final_answer_validator.py \
  app/tests/test_control_plane_behavior_matrix.py \
  app/tests/test_mitre_decision_runtime.py \
  app/tests/test_chat_control_plane_golden.py -v
./scripts/run_stage3_governance_regression.sh   # must stay PASS (0 pytest failures, harness 6/6)
cd frontend && npm run build                    # only if response schema fields are surfaced in UI
```

Manual: with `CONTROL_PLANE_ENABLED=true`, run a non-auth negative-evidence case and confirm the exfil technique lands in **Not Claimed** with a general reason — proving the engine reasons, not pattern-matches. The exact input depends on the Commit 1 path chosen: if a `negative_outbound_transfer` query signal is added, use a query phrasing it ("…no outbound transfer observed"); if not, use a query that retrieves a RAG `prohibited_conclusions` entry covering exfil.
