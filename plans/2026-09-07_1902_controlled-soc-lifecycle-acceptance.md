---
name: controlled-soc-lifecycle-acceptance
overview: "Prove approved investigation → discovered read → SourceEvidence → LLM reasoning → PlanDelta → InvestigationOutcome → P11 action on the existing authority path, without architecture.md changes or production bypasses."
status: active
date: 2026-09-07
canonical_plan: plans/2026-09-07_1902_controlled-soc-lifecycle-acceptance.md
loop_runner: plans/LOOP_RUNNER_TEMPLATE.md
---

# Controlled SOC full-lifecycle acceptance

## Objective

Prove the unproven product path: approved investigation → legitimate discovered read capability → SourceEvidence → LLM evidence reasoning → bounded PlanDelta if needed → InvestigationOutcome → remediation plan → P11 governed action → ActionEvidence → final combined status. `architecture.md` stays byte-identical. No production test bypass, no second connector/planner/registry.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- `architecture.md` READ ONLY
- LLM may reason over governed evidence; LLM may NOT admit SourceEvidence or call MCP
- No `if test_query` / `if golden_test` / `if localhost_mock` in production
- External MCP test server may return fixture telemetry (test infrastructure)
- RecordingEmailTransport is the only write adapter for this acceptance
- Do not merge, push, deploy, or tag until the journey and regression gates pass

## Phase 0 checkpoint (recorded 2026-09-07)

| Field | Value |
|---|---|
| BASE_SHA | `9ebbaa6559ee5c7c6c54e23e4236befa27bdb5af` (`master` / compound-investigation) |
| CODEX_CHECKPOINT_SHA | `1f68ee48a42eee704233dc1e9c3cd92f9a2811b0` (`fix/investigation-loop-plan-convergence`) |
| WORKING_TREE | dirty — 13 files from Codex investigation-loop continuation (not committed) |
| architecture.md hash | `a67c1236d53b1b94316b29fe04edb009c5bce5a5` |
| P1 compiler freeze | `f27b363dc854b64411104b34698cca82544e9f85b4f6bf1986b2adfbf4693ef8` |
| P2 compiler freeze | `97b84cdf8e4aaecfc4a49825f5913d79959d6da1ca7489b0f4ce1ffcad1b8e1c` |
| P3 compiler freeze | `0bed5774228536dc771475418724980b643326f1a4468f133157b0d8df755f15` |
| P4 compiler freeze | `a4d195beecd85bd8e57e90b4d6ce71b437c12426bb8e7bf7a3b3dd14ba635eb8` |
| P11 tag | `p11-live-verified-vps-stable-2026-09-07` → `9f018564b8ba938d66939a2c13669515a282d78d` |
| MCP flags (.env) | `MCP_GLOBAL_EXECUTION_ENABLED=false`, `MCP_SERVER_MOCK_EXECUTION_ENABLED=false`, `SPLUNK_MCP_ENABLED=false`, profile `coe` |
| Branch | `fix/investigation-loop-plan-convergence` (2 commits ahead of master) |

## Phase 1 audit (independent verification of Codex)

| Role | SourceEvidence exists? | What reaches the LLM | Intentionally excluded | Unnecessarily lost |
|---|---|---|---|---|
| Investigation planner (`guided_investigation_plan_llm._build_user_prompt`) | No — hop runs before collection | Untrusted query + deterministic plan context + capability ids | Evidence rows, credentials, raw SPL | N/A (correct) |
| PlanDelta (`investigation_plan_delta_reasoner.propose_plan_delta`) | Yes — after READ #1 in RP graph | `missing_evidence_categories` + `allowed_read_only_capabilities` + envelope_version only | Raw telemetry, entities, tool output (docstring) | **Admitted SourceEvidence summary** |
| Answer synthesis (`synthesis/live_narration.py`) | Yes | GovernedSynthesisPackage facts / InvestigationOutcome aggregates | Raw event text, source_evidence rows | Bounded; not this defect |
| Remediation planner (`remediation_plan_reasoner._build_prompt`) | Yes | disposition + investigation_status + capability ids | Raw evidence, entities, tool output, SPL | **Governed findings / admitted-evidence rationale** |
| Missing-evidence sidecar | Partial | AnswerContract missing/required lists + redacted SOC-KB snippets via `GovernedContextPackage` | Raw MCP rows (package never reads SourceEvidence) | Environment evidence still not projected as admitted summaries |

**Verdict:** Codex finding is genuine. Fix the existing projection seam (`GovernedContextPackage` callers pass already-redacted strings). Do not create a second evidence model.

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14`

## Checklist

- [x] **0** — Checkpoint record
  - **Do:** Record BASE_SHA, CODEX_CHECKPOINT_SHA, architecture.md hash, P1–P4 hashes, P11 state, MCP flags, working tree. Do not merge/push/tag.
  - **Verify:** `git rev-parse HEAD master; git hash-object architecture.md; git status -sb`
  - **Depends on:** none
  - **Evidence:** HEAD `1f68ee48`; master `9ebbaa65`; architecture.md `a67c1236d53b1b94316b29fe04edb009c5bce5a5`; dirty 13 files; P11 tag `9f018564`

- [x] **1** — Residual LLM evidence-context audit
  - **Do:** Independently trace planner / PlanDelta / synthesis / remediation input contracts.
  - **Verify:** `grep -n "missing_evidence_categories\\|Send only bounded vocabulary" backend/app/chat/investigation_plan_delta_reasoner.py`; `grep -n "No raw evidence" backend/app/chat/remediation_plan_reasoner.py`; confirm `GovernedContextPackage` never reads SourceEvidence payloads
  - **Depends on:** 0
  - **Evidence:** PlanDelta prompt is missing-categories-only; remediation prompt is disposition+capability-ids; package docstring: "never reaches into SourceEvidence payloads itself". Gap is genuine.

- [x] **2** — Project admitted SourceEvidence into reasoning context
  - **Do:** Add `app/evidence/governed_reasoning_context.py` projector over existing SourceEvidence. Extend `GovernedContextPackage` with `admitted_environment_evidence` (redacted strings, caller-supplied). Wire PlanDelta + remediation reasoners. LLM still cannot admit evidence.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_governed_reasoning_context.py app/tests/test_p7_bounded_plan_delta.py app/tests/test_p10_remediation_planning.py app/tests/test_governed_context_package_full.py -q`
  - **Depends on:** 1
  - **Evidence:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_governed_reasoning_context.py app/tests/test_p7_bounded_plan_delta.py app/tests/test_p10_remediation_planning.py app/tests/test_governed_context_package_full.py -q` → **49 passed**. Projector excludes user claims / failed tools; PlanDelta and remediation prompts carry admitted environment summaries without raw SPL/secrets.

- [x] **3** — Local external MCP test server
  - **Do:** Add `tools/controlled_mcp_server/` JSON-RPC `initialize`/`tools/list`/`tools/call` server using the existing Splunk MCP wire contract. Fixture telemetry lives only here. No production bypass.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_mcp_server.py -q`
  - **Depends on:** 2
  - **Evidence:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_mcp_server.py -q` → **3 passed**. Handshake lists `splunk_run_query`; live Splunk transport discovers it.

- [x] **4** — Fixture scenario (process → persistence/network)
  - **Do:** First `splunk_run_query` returns suspicious process-only rows (insufficient). Second returns persistence + external network correlation. Owned by the test MCP.
  - **Verify:** Same test file asserts call 1 vs call 2 row families; production tree has no query-specific fixture branch (`grep -R "if test_query\\|if golden_test\\|if localhost_mock" backend/app --include='*.py'` empty)
  - **Depends on:** 3
  - **Evidence:** Call 1 process-only (`powershell.exe` / `WS-14`); call 2 adds `scheduled_task_created` + `198.51.100.88`. Insufficient mode never supplies dest/correlation. `rg` over `backend/app --glob '*.py'` found no production `if test_query`/`if golden_test`/`if localhost_mock` branch (only a negative assertion string in the lifecycle test).

- [x] **5** — Real product journey through `/chat` pipeline
  - **Do:** Drive `build_live_chat_response` with HIL flags, registry MCP pointed at the external server, normal discovery handshake → snapshot → capability → exact-call. Natural analyst query permitting remediation after approval.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_soc_lifecycle_acceptance.py -q`
  - **Depends on:** 4
  - **Evidence:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_soc_lifecycle_acceptance.py -q` → **6 passed**. Path is `run_chat_via_resource_planner_graph` (langgraph ON), registry MCP against `tools/controlled_mcp_server`, discovery handshake → snapshot. No production `if test_query` branch.

- [x] **6** — Investigation approval + READ #1 SourceEvidence
  - **Do:** Approve via existing HIL; assert immutable envelope, execution_requested, server_present, exact-call, SourceEvidence admission. User claims stay separate; RAG distinct.
  - **Verify:** Same test: envelope + source_evidence[0] collected environment rows; no user-claim promotion
  - **Depends on:** 5
  - **Evidence:** First turn `investigation_approval.status=awaiting_approval`; run+confirm → `approved` + `execution.status=executed`. READ #1 `source_type=splunk_mcp` collected rows include `powershell.exe` / `WS-14`. User-claim source_types are not in the collected environment set.

- [x] **7** — LLM evidence reasoning + PlanDelta + READ #2
  - **Do:** After READ #1, PlanDelta prompt contains admitted environment summary; DET validates; second exact-call; second SourceEvidence.
  - **Verify:** Same test captures PlanDelta prompt + second evidence_id
  - **Depends on:** 6
  - **Evidence:** PlanDelta prompt JSON includes non-empty `admitted_environment_evidence` (`trust_class=environment`, powershell/WS-14) plus envelope entity scope. DET accepted a bounded delta (`generation_mode=validated_plan_delta`). External MCP `search_calls>=2`. Second SourceEvidence contains `scheduled_task_created` and `198.51.100.88`. Two evidence ids on the outcome refs.

- [ ] **8** — InvestigationOutcome + synthesis + remediation plan
  - **Do:** Outcome findings reference admitted evidence; synthesis uses canonical context; remediation plan visible, not auto-executed.
  - **Verify:** Same test: outcome.evidence_refs, remediation_approval awaiting, zero writes
  - **Depends on:** 7
  - **Evidence:** STOP — outcome refs admitted evidence (`ev_*` ids) but `disposition=inconclusive` and run_status stays `incomplete` (missing catalogue keys `endpoint`/`auth`/`rag`/`spl` never clear from collected MCP rows). `remediation_plan_eligible` requires `investigation_status=completed` and `disposition=suspicious`; remediation HIL was **not** offered. Visible message was empty or the generic guided pack, not evidence-backed synthesis. Zero writes (correct given ineligibility). Do not weaken disposition policy to force P11.

- [ ] **9** — Controlled P11 write + ActionEvidence + idempotency
  - **Do:** Approve remediation via existing HIL using RecordingEmailTransport. Assert envelope fingerprint, exact-call, one logical write, ActionEvidence, replay idempotency. EXECUTED != VERIFIED.
  - **Verify:** Same test + existing `app/tests/test_p11_remediation_connectors.py -k idempotency -q`
  - **Depends on:** 8
  - **Evidence:** _(fill when done)_

- [ ] **10** — Control cases A–F
  - **Do:** Insufficient fixture; recommend-but-do-not-execute; MCP unavailable; edit; cancel; replay.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_soc_lifecycle_acceptance.py -k "insufficient or do_not_execute or unavailable or edit or cancel or replay" -q`
  - **Depends on:** 9
  - **Evidence:** _(fill when done)_

- [ ] **11** — Golden journeys two-pass
  - **Do:** SSH, MFA, DNS/firewall, process/persistence/network — twice, fresh sessions.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_investigation_loop_journeys.py app/tests/test_compound_investigation_semantics.py -q`
  - **Depends on:** 10
  - **Evidence:** _(fill when done)_

- [ ] **12** — Targeted then full regression
  - **Do:** Backend targeted, frontend build, SOC E2E, P-series, P11, Tier0, RACES, protected, SPL freeze, parity, dispatch, governance. Inherited sentinel drift vs this checkpoint = PRE_EXISTING_BASELINE_DRIFT, do not silent-refresh.
  - **Verify:** listed gates in item Evidence
  - **Depends on:** 11
  - **Evidence:** _(fill when done)_

- [ ] **13** — architecture.md + authority uniqueness
  - **Do:** Confirm architecture.md hash unchanged; no second planner/router/registry/MCP framework; LLM_DIRECT_MCP=NO; LLM_EVIDENCE_AUTHORITY=NO; LLM_REASONING_OVER_GOVERNED_EVIDENCE=YES.
  - **Verify:** `git hash-object architecture.md` equals Phase 0 hash; `git diff -- architecture.md` empty
  - **Depends on:** 12
  - **Evidence:** _(fill when done)_

- [ ] **14** — Final acceptance report
  - **Do:** Fill CONTROLLED_SOC_FULL_LIFECYCLE_ACCEPTANCE. READY_FOR_MANUAL_USER_ACCEPTANCE=YES only if the lifecycle was observed on the normal product path.
  - **Verify:** report fields complete; no YES without observed journey
  - **Depends on:** 13
  - **Evidence:** _(fill when done)_

## Verification gaps (flag before coding)

- Live llama-server reasoning on Docker `/chat` (8012) is optional extra observation; pytest blocks live LLM unless `AI_SOC_TESTS_ALLOW_LIVE_LLM=1`. The lifecycle test uses the real pipeline + real HTTP MCP + advisory-role test doubles that must consume the governed evidence prompt. A live Docker probe is recorded in item 5 Evidence if the stack is up.

## Drift log

- Working tree was already dirty on Codex investigation-loop continuation (13 files). This plan layers the evidence-context + external-MCP journey on that branch; it does not revert those files.
- In-process `MockMcpConnector` is **not** the controlled read source. Registry-mode live transport against the external test MCP is required so mock rows cannot be admitted (`mock_result_forbidden_as_live_evidence`).
- PlanDelta ran before `graph_node_context_finalize` built SourceEvidence, so the projector saw `admitted_environment_evidence=[]`. Fix: `admit_execution_source_evidence()` on `rp_node_context_sufficiency` using the existing builder; merge preserves READ #1 when the execution object is replaced.
- Confirm resume must accept handoff status `plan_committed` as well as `investigation_approved` (`maybe_resume_approved_investigation_execution`).
- `graph_node_rag_early` treated `execution is None` (PlanDelta clears it) as present; now only dict execution is used.
- `_workflow_spl_from_plan_delta` re-RQC now uses envelope entities (same contract as DET). `validated_plan_delta` skips review-only postprocessor mutation so DET-approved SPL is not rewritten into placeholders.
- Item 8 blocked: InvestigationOutcome disposition stays `inconclusive` unless live-result language AND obtained evidence AND P1/P2 severity. Collected MCP rows do not clear envelope `required_evidence_keys` such as `rag`/`spl`. Remediation planner correctly refuses. Not a test-bypass candidate.
- Full backend pytest 2026-09-08: **9 failed, 7542 passed, 45 skipped, 6 xfailed**. New from this work: `test_inventory_covers_every_remaining_record_shape` (PlanDelta `inputs_ref` now includes `source_evidence`; inventory updated). `test_races_freeze_files_not_in_working_tree` fails on this dirty tree (expected). Sentinel / in-catalogue / 105-path / control-plane golden not re-run on a clean `1f68ee48` tree — do not silent-refresh; classify only after a clean-checkpoint gate.
