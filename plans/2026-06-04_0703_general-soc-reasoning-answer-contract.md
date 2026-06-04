# General SOC Reasoning & Answer-Goal Validation Layer

**Date:** 2026-06-04
**Branch:** `feat/deterministic-spl-llm-fallback` (has uncommitted edits to `pipeline.py`, `analyst_response_builder.py`, `mitre_decision.py`, `query_signals.py` — this work builds on top; reconcile/commit those first or rebase before starting).
**Gate:** all new behavior runs only under `CONTROL_PLANE_ENABLED` (default `false`). Do **not** flip the default.
**Saved at:** `plans/2026-06-04_0703_general-soc-reasoning-answer-contract.md`. Add a row to the `CLAUDE.md` Plans table once approved.
**Status:** Proposed — awaiting review.

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

**New:** `backend/app/threat/technique_preconditions.py` — data-driven table mapping MITRE techniques to required-evidence preconditions and the negative-evidence signal that negates them. Keyed to the signal vocabulary, generalizes beyond auth:

```
T1078     requires successful_login          ; negated by no_successful_login
T1003     requires credential_dumping_evidence; negated by no_credential_dumping
T1562.001 requires endpoint_telemetry        ; negated by no_endpoint_telemetry
T1041/exfil requires outbound_transfer       ; negated by no_outbound_transfer
... (extend per tactic: command_execution, lateral_movement, malware, privileged_account)
```

**New:** `backend/app/chat/negative_evidence_extractor.py` — `extract_negative_evidence(query_signals, source_evidence, structured_context) -> NegativeEvidence`. Aggregates absence signals from query + RAG + structured evidence (only query+RAG carry content today; live MCP stays off). Reuses the `query_signals.py` flags as the query source — do not re-parse the query.

**Wire into `mitre_decision.resolve_mitre_decision`:** compute `not_claimed`/`rejected` from `technique_preconditions` × extracted negative evidence, instead of the static `_DEFAULT_NOT_CLAIMED`. **Delete `_DEFAULT_NOT_CLAIMED`** (`:16`) and its two uses (`:80`, `:124`). Add `intent_classification`/`source_evidence` flow so the extractor's output reaches the decision.

**Tests:** `test_negative_evidence_extractor.py` + extend `test_mitre_decision_runtime.py` — assert the *same* failed-login negative-evidence outcome now comes from the general engine, plus at least one non-auth case (e.g. exfil with `no_outbound_transfer` blocks T1041).

### Commit 2 — AnswerContract projection

**New:** `backend/app/chat/contracts/answer_contract.py` — Pydantic `AnswerContract` built by `build_answer_contract(...)`. Fields and their **single source**:

| Field | Source decider |
|-------|----------------|
| `user_goal` / `answer_goal[]` | `IntentClassification.answer_goal` |
| `allowed_findings` / `candidate_findings` / `blocked_findings` | `MitreDecision` (visible/candidate/rejected) + `StructuredContextPackage.allowed_conclusions` |
| `not_claimed` / `must_not_claim` | `MitreDecision.not_claimed` + `prohibited_conclusions` + negative-evidence (Commit 1) |
| `evidence_status` / `rag_status` / `mcp_status` / `spl_status` | execution, `soc_kb_retrieval`, `EvidencePlan`, `spl_validation` |
| `response_sections_required` | derived from `answer_goal` (e.g. `analyst_action_guidance` → actions section required) |

Pure read-model: no keyword re-parsing, no new MITRE/severity decisions.

**Tests:** `test_answer_contract.py` — one per intent_family, asserting every field traces to its source decider.

### Commit 3 — Builder consumes the contract (primary enforcer)

Refactor `analyst_response_builder.build_analyst_response_for_live` to take `answer_contract` and assemble the answer **from it**: blocked findings appear only in `not_claimed`; candidate findings are labeled candidate (never confirmed); actions come from `allowed`/`blocked_actions`. The contract is the input to **both** the deterministic builder and the gated LLM-narration path ("build from contract" holds regardless of synthesis mode — LLM may phrase, but only over allowed/candidate findings).

**Delete the per-pattern hardcoding:** `_NOT_CLAIMED_DETAILS` (`:177-190`, replaced by precondition-table rationale strings) and the literal three-negative match in `_governed_summary` (`:230-244`, replaced by contract-driven prose). `_not_claimed_rows` reads contract `not_claimed` with general reasons.

**Tests:** extend `test_chat_control_plane_golden.py` — failed-login card unchanged in output; add a non-auth card proving generality.

### Commit 4 — final_answer_validator (fail-closed backstop)

**New:** `backend/app/chat/final_answer_validator.py` — `validate_final_answer(draft, answer_contract, evidence_plan, mitre_decision) -> AnswerGuardStatus`. Deterministic checks (reuse `GuardResult`/`AnswerGuardStatus`):

- No `blocked_findings`/`must_not_claim` item appears as a positive claim.
- No live results when MCP unavailable / `mcp_allowed=false`.
- No answer-visible MITRE when intent suppresses it (`answer_visible=false`).
- No SPL/MCP artifacts on `rag_only`.
- No SPL-only answer when `answer_goal` includes `analyst_action_guidance`.
- Candidate findings not described as confirmed.
- RAG content does not override `MitreDecision`.

On `blocking_candidate`: route to `analyst_review_required` / `human_review`. Wire as a node in `pipeline.graph_node_context_finalize` **after** the answer is assembled, gated on `control_plane_enabled`. Add results to `control_plane_trace.py` via a new `_answer_contract_trace` helper (alongside existing `answer_guard` entry).

**Tests:** `test_final_answer_validator.py` — one failing draft per rule → `blocked` + review routing.

### Commit 5 — Behavior-matrix eval pack

**New:** `backend/app/tests/test_control_plane_behavior_matrix.py` — 30+ cases using the `test_chat_control_plane_golden.py` template (autouse `control_plane_enabled=True` fixture, `_chat()` helper). Categories: policy/RAG-only, live investigation, hybrid, MITRE mapping, **negative evidence** (across auth/DNS-DGA/phishing/malware/network/exfil/lateral movement), SPL-only, MCP unavailable. Asserts contracts (modes, gates, not-claimed presence, no over-claim) — **not** brittle counts/strings, per the LLM-app quality loop.

---

## Hard boundaries (every commit)

Do not enable live MCP, do not execute `candidate_spl`, do not enable live Foundation-Sec final synthesis, no LLM→MCP. Do not touch Experience Center / demo golden answers. Registry MITRE stays metadata-not-evidence. No per-question fixes — rules must apply across all tactics.

## Verification

```bash
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_negative_evidence_extractor.py app/tests/test_answer_contract.py app/tests/test_final_answer_validator.py app/tests/test_control_plane_behavior_matrix.py -v
./scripts/run_stage3_governance_regression.sh   # must stay PASS (0 pytest failures, harness 6/6)
cd frontend && npm run build                    # only if response schema fields are surfaced in UI
```

Manual: with `CONTROL_PLANE_ENABLED=true`, run a non-auth negative-evidence query (e.g. exfil-suspected with "no outbound transfer observed") and confirm the exfil technique lands in **Not Claimed** with a general reason — proving the engine reasons, not pattern-matches.
