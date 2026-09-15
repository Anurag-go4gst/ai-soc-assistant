---
name: investigation-outcome-remediation-closure
overview: "Narrow continuation: SourceEvidence → correct sufficiency → InvestigationOutcome → evidence-backed synthesis → existing remediation eligibility → P11 controlled write. architecture.md read-only. Do not weaken remediation policy."
status: active
date: 2026-09-08
canonical_plan: plans/2026-09-08_1355_investigation-outcome-remediation-closure.md
loop_runner: plans/LOOP_RUNNER_TEMPLATE.md
---

# Investigation outcome → remediation closure

## Objective

Preserve the already-proven controlled SOC lifecycle (discovery, envelope HIL, READ #1, SourceEvidence, LLM-over-governed-evidence, bounded PlanDelta, READ #2). Fix only the remaining closure: evidence sufficiency → InvestigationOutcome → synthesis → existing remediation eligibility → P11 recording write → combined summary. No second planner/router/registry/evidence model. No architecture.md change. No query-specific PowerShell/WS-14/198.51.100.88 branches.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- `architecture.md` READ ONLY (hash must stay `a67c1236d53b1b94316b29fe04edb009c5bce5a5`)
- P1–P4 compiler freeze hashes unchanged
- P11 authority unchanged; RecordingEmailTransport only; EXECUTED ≠ VERIFIED
- LLM may reason over governed evidence; LLM may NOT admit SourceEvidence or call MCP
- Do not loosen `remediation_plan_eligible` (completed + suspicious + evidence_refs)
- Do not merge / push / deploy / tag
- Predecessor: [`plans/2026-09-07_1902_controlled-soc-lifecycle-acceptance.md`](2026-09-07_1902_controlled-soc-lifecycle-acceptance.md) item 8 STOPPED on inconclusive/incomplete leftovers

## Phase 0 checkpoint (recorded 2026-09-08)

| Field | Value |
|---|---|
| START_SHA | `1f68ee48a42eee704233dc1e9c3cd92f9a2811b0` |
| CHECKPOINT_SHA | `1147647ec6f8905cd7de7835614c8a010b4f95f3` |
| Branch | `fix/investigation-loop-plan-convergence` (clean after checkpoint) |
| architecture.md hash | `a67c1236d53b1b94316b29fe04edb009c5bce5a5` |
| architecture.md in checkpoint diff | empty |
| P1 compiler freeze | `f27b363dc854b64411104b34698cca82544e9f85b4f6bf1986b2adfbf4693ef8` |
| P2 compiler freeze | `97b84cdf8e4aaecfc4a49825f5913d79959d6da1ca7489b0f4ce1ffcad1b8e1c` |
| P3 compiler freeze | `0bed5774228536dc771475418724980b643326f1a4468f133157b0d8df755f15` |
| P4 compiler freeze | `a4d195beecd85bd8e57e90b4d6ce71b437c12426bb8e7bf7a3b3dd14ba635eb8` |
| P11 tag | `p11-live-verified-vps-stable-2026-09-07` → `9f018564b8ba938d66939a2c13669515a282d78d` |

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18`

Item 4 (CASE A mapping) and item 5 (CASE B extra PlanDelta) are mutually exclusive after item 2. Execute only the branch item 2 selects. Item 6+ require the selected branch done.

## Checklist

- [x] **0** — Local checkpoint commit
  - **Do:** Local commit of current controlled-lifecycle work. No merge/push/deploy/tag. Record START_SHA, CHECKPOINT_SHA, architecture.md hash, P1–P4 hashes, P11 state.
  - **Verify:** `git rev-parse HEAD`; `git hash-object architecture.md`; `git diff 1f68ee48 1147647e -- architecture.md` empty
  - **Depends on:** none
  - **Evidence:** START_SHA `1f68ee48`; CHECKPOINT_SHA `1147647e`; architecture.md `a67c1236d53b1b94316b29fe04edb009c5bce5a5`; checkpoint diff vs architecture.md empty. Working tree clean after commit.

- [x] **1** — Reproduce controlled journey (no product code)
  - **Do:** Fresh session through existing `test_controlled_full_lifecycle_read_reason_delta_outcome_p11`. Dump approved envelope, EvidencePlan, ResourcePlan, READ #1/#2, SourceEvidence, PlanDelta prompt, sufficiency, InvestigationOutcome in/out, missing keys, disposition/status/severity, remediation eligibility. Do not change production modules.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase1_lifecycle_dump.py -q` writes `/tmp/phase1_lifecycle_dump.json` and the existing lifecycle test still passes
  - **Depends on:** 0
  - **Evidence:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase1_lifecycle_dump.py app/tests/test_controlled_soc_lifecycle_acceptance.py::test_controlled_full_lifecycle_read_reason_delta_outcome_p11 -q` → **2 passed in 4.05s**. Dump `/tmp/phase1_lifecycle_dump.json`. READ #1+#2 `search_calls=2`. READ #2 rows: WS-14/jdoe/`scheduled_task_created`/`powershell.exe` then dest `198.51.100.88:443`. Outcome `incomplete`/`inconclusive`; missing `endpoint,auth,process_execution,approved_sop_guidance,rag:sop,rag,spl`; PlanDelta missing_categories=`["rag"]`; `remediation_plan_eligible=false`. P1–P4 freeze **2 passed**. architecture.md hash unchanged.

- [x] **2** — CASE A vs CASE B from dump + contract
  - **Do:** From dump + canonical envelope + admitted SourceEvidence, fill EVIDENCE_COLLECTED / CLAIMS_SUPPORTED / CLAIMS_NOT_SUPPORTED / ACTUAL_REQUIRED_EVIDENCE / LEGACY_REQUIRED_KEYS / WHY_OUTCOME_IS_INCONCLUSIVE / CORRECT_NEXT_BEHAVIOR. Do not decide from making tests green.
  - **Verify:** Case section in this plan is filled; CORRECT_NEXT_BEHAVIOR is COMPLETE or PLANDELTA; no product code yet
  - **Depends on:** 1
  - **Evidence:** CASE A. Environment legs are collected. Remaining "gaps" are catalogue/enrichment labels that SourceEvidence never emits (`mcp` vs `endpoint`). Another PlanDelta for `rag` is not a material environment question.

- [x] **3** — Sufficiency / disposition / presentation authority audit
  - **Do:** Classify every required key (REQUIRED_ENVIRONMENT_EVIDENCE / OPTIONAL_ENVIRONMENT_EVIDENCE / ENRICHMENT / EXECUTION_ARTIFACT / PROVENANCE/CONTROL / NOT_APPLICABLE). Trace owners of required evidence, completion, disposition, severity, remediation eligibility. Confirm presentation (`allow_live_result_language`, answer wording) does not manufacture InvestigationOutcome.
  - **Verify:** Audit table in this plan; `rg "allow_live_result_language" backend/app/chat/contracts/investigation_outcome.py`; `rg "needs_rag|needs_spl" backend/app/evidence/minimal_evidence_state.py`
  - **Depends on:** 2
  - **Evidence:** See audit table. `_disposition` currently requires `allow_live_result_language` ∧ obtained ∧ P1/P2 (`investigation_outcome.py`). `needs_rag`/`needs_spl` unconditionally append `rag`/`spl` (`minimal_evidence_state.py`). `attach_investigation_observation` uses `sufficiency.get("missing") or ...` so an empty missing list falls through to stale plan keys.

- [x] **4** — CASE A: generic sufficiency mapping (skip if CASE B)
  - **Do:** Smallest generic fix so InvestigationOutcome sufficiency uses the current approved investigation/evidence contract, not unrelated catalogue keys (`rag`, `spl` artifact, `auth` on a process investigation, SOP guidance). No fixture special-case. Tests across AUTH / ENDPOINT / NETWORK families proving irrelevant keys cannot block completion.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_minimal_evidence_state.py app/tests/test_investigation_outcome.py app/tests/test_p8_investigation_outcome_v2.py app/tests/test_resource_planner_evidence_sufficiency.py app/tests/test_compound_investigation_semantics.py app/tests/test_phase8_sufficiency_families.py -q`
  - **Depends on:** 3
  - **Evidence:** Mapping + families + compound + RP sufficiency included in focused run **77 passed**. Empty sufficiency `missing=[]` no longer inherits SOP keys (`test_empty_sufficiency_missing_does_not_inherit_enrichment_keys`). Checklist "unusual network use" requires `network_flows` only (process-only rows leave that leg open). Controlled lifecycle after mapping: `completed` / `suspicious` / leftover `rag`/`spl`/SOP absent.

- [x] **5** — CASE B: extra bounded PlanDelta read (skip if CASE A)
  - **Do:** Do not change sufficiency to pass. PlanDelta prompt must ask the remaining material question; DET validates; READ #3 via Resource Planner/MCP; admit SourceEvidence #3; re-evaluate. Bound by existing hop/budget policy. No hardcoded third search.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_soc_lifecycle_acceptance.py app/tests/test_p7_bounded_plan_delta.py -q`
  - **Depends on:** 3
  - **Evidence:** N/A — CASE A. After two reads the environment contract is complete; a third search for `rag` is not a material environment question.

- [x] **6** — InvestigationOutcome contract
  - **Do:** Once sufficient: status=completed; disposition evidence-supported; findings cite SourceEvidence; correlations explicit; missing_evidence only material gaps; severity from existing severity policy; recommended actions from findings. No user-claim findings. No RAG-as-environment-evidence.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_investigation_outcome.py app/tests/test_p8_investigation_outcome_v2.py app/tests/test_controlled_soc_lifecycle_acceptance.py::test_controlled_full_lifecycle_read_reason_delta_outcome_p11 -q`
  - **Depends on:** 4 or 5
  - **Evidence:** `test_controlled_full_lifecycle_read_reason_delta_outcome_p11` **PASS**. Turn-4 dump: status=`completed`, disposition=`suspicious`, `MISSING_EVIDENCE=[]`. Severity remains existing policy ("Not assigned from this question alone"), not invented P1/P2.

- [x] **7** — Evidence-backed synthesis
  - **Do:** LLM synthesis receives InvestigationOutcome + SourceEvidence summary + correlations + remaining gaps + governed guidance. Reject generic pack / empty narrative / catalogue boilerplate replacing evidence reasoning.
  - **Verify:** Same lifecycle test asserts non-empty evidence-bound analyst narrative; `rg "generic guided" backend/app/chat/t2_answer_surfacing.py backend/app/chat/rag_answer_surfacing.py` shows pack cannot override completed investigation outcome
  - **Depends on:** 6
  - **Evidence:** Completed InvestigationOutcome now gets the existing deterministic lab draft even when live-synthesis flags stay off (live narration still flag-gated). Lifecycle test asserts PowerShell/process, persistence/task, dest/network, suspicious; **PASS**. `generic guided` not in narrative.

- [x] **8** — Remediation eligibility uses existing policy
  - **Do:** Do not change `remediation_plan_eligible` rule. If outcome legitimately is completed+suspicious, continue P11 lane. If not, keep blocked.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_p10_remediation_planning.py app/tests/test_controlled_soc_lifecycle_acceptance.py -q`; `git diff CHECKPOINT_SHA -- backend/app/chat/remediation_runtime.py` shows no weakening of completed+suspicious
  - **Depends on:** 7
  - **Evidence:** `remediation_plan_eligible` still requires completed + suspicious + evidence_refs. Lifecycle asserts rem status in offered/awaiting/approved. Docstring-only note in `remediation_runtime.py`; gate not loosened.

- [x] **9** — Remediation plan HIL + P11 recording write
  - **Do:** User-permit path: proposal → DET validate → visible plan → Approve. Immutable ApprovedRemediationEnvelope, exact fingerprint, exact-call, registered adapter, one logical write, ActionEvidence, idempotency, replay. EXECUTED ≠ VERIFIED.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_soc_lifecycle_acceptance.py::test_controlled_full_lifecycle_read_reason_delta_outcome_p11 app/tests/test_p11_remediation_connectors.py -k idempotency -q`
  - **Depends on:** 8
  - **Evidence:** Lifecycle test requires `recording.sent` length 1 after approve, idempotent replay, `verified` not true. **PASS** (3.11s). P11 idempotency filter **1 passed**.

- [ ] **10** — Negative controls A–F
  - **Do:** A insufficient; B recommend-no-execute; C benign; D source unavailable; E failed second tool call; F RAG without telemetry.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_controlled_soc_lifecycle_acceptance.py app/tests/test_phase15_negative_controls.py -q`
  - **Depends on:** 9
  - **Evidence:** Covered in `test_controlled_soc_lifecycle_acceptance.py` (insufficient fixture, recommend-no-execute zero write, source unavailable) + `test_plan_delta_eligibility.py` (HIL wait BLOCKED, pending BLOCKED, sufficient NOT_RUN, terminal failure ALLOWED, no capability stops). `test_phase15_negative_controls.py` does not exist. Not a full A–F dedicated file.

- [x] **11** — Genericity AUTH / ENDPOINT / NETWORK
  - **Do:** One controlled sufficiency test per family. Do not require remediation in all three.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_phase8_sufficiency_families.py -q`
  - **Depends on:** 4 or 5
  - **Evidence:** `test_phase8_sufficiency_families.py` included in **77 passed** focused run.

- [ ] **12** — Golden journeys twice
  - **Do:** SSH, MFA, DNS_FIREWALL, PROCESS_PERSISTENCE_NETWORK — two fresh-session passes. Judge visible plan/execution/evidence/outcome/synthesis/write prohibition, not route flags.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_investigation_loop_journeys.py app/tests/test_compound_investigation_semantics.py -q` run twice
  - **Depends on:** 10, 11
  - **Evidence:** _(fill when done)_

- [ ] **13** — Full regression with clean-checkpoint classification
  - **Do:** Backend, frontend, SOC E2E, P-series, P11, Tier0, RACES, protected, SPL freeze, parity, dispatch, governance. Classify every backend failure vs clean CHECKPOINT worktree. Do not silent-refresh sentinels/goldens/protected hashes.
  - **Verify:** listed gates in Evidence; dirty-tree RACES rerun from CHECKPOINT if freeze files dirty
  - **Depends on:** 12
  - **Evidence:** _(fill when done)_

- [ ] **14** — architecture.md + authority uniqueness
  - **Do:** architecture.md hash unchanged; P1–P4 unchanged; P11 authority unchanged; no second planner/router/registry/evidence model; no LLM→MCP; no LLM evidence admission; no query-specific conditions.
  - **Verify:** `git hash-object architecture.md` equals `a67c1236d53b1b94316b29fe04edb009c5bce5a5`; `git diff -- architecture.md` empty; `rg "if test_query|if golden_test|if localhost_mock" backend/app --glob '*.py'` empty of production branches
  - **Depends on:** 13
  - **Evidence:** _(fill when done)_

- [ ] **15** — Final acceptance report
  - **Do:** Fill INVESTIGATION_OUTCOME_REMEDIATION_FINAL_ACCEPTANCE. READY_FOR_MANUAL_USER_ACCEPTANCE=YES only if the full read→reason→outcome→P11 journey was observed and evidence justifies remediation.
  - **Verify:** report section complete; YES only with observed journey
  - **Depends on:** 14
  - **Evidence:** _(fill when done)_

## CASE A vs CASE B (filled after item 2)

EVIDENCE_COLLECTED:
- READ #1: `splunk_mcp` collected (`ev_b62b4288145ac318`, result_count=1, admitted as environment in PlanDelta prompt).
- READ #2: `splunk_mcp` collected (`ev_b62b4288145ac318:262ff6126638`): host=WS-14, user=jdoe, `scheduled_task_created` / task_exec=powershell.exe @ 12:04:18Z; dest=198.51.100.88:443 @ 12:05:02Z.

CLAIMS_SUPPORTED:
- Same-host process/persistence: powershell.exe on WS-14 and a scheduled task executing powershell.exe as jdoe.
- Same-host/user/time network: outbound 198.51.100.88:443 ~44s later.
- Correlation keys present in telemetry: host, user, `_time`.

CLAIMS_NOT_SUPPORTED:
- WINWORD.EXE as parent process (not in returned fields).
- Whether 198.51.100.88 is "unfamiliar" vs baseline (no baseline evidence).
- Authentication failure/success/MFA (not in rows; not the analyst's environment question).

ACTUAL_REQUIRED_EVIDENCE:
- Endpoint/process execution for the reported host (envelope checklist + `endpoint`/`process_execution`).
- Persistence/subsequent activity on that host (checklist; collected as scheduled task + dest).
- Host/user/time correlation (collected).

LEGACY_REQUIRED_KEYS:
- `auth` — copied from `post_login_activity` domain categories because "subsequent activity" matched that domain; this is not an authentication investigation.
- `rag`, `rag:sop`, `approved_sop_guidance` — enrichment / Stage 3J SOP, not live environment evidence.
- `spl` as a distinct missing key — means executed search result (`_required_key_semantics`); MCP rows already are that result, keyed as `mcp`.

WHY_OUTCOME_IS_INCONCLUSIVE:
- Required keys are domain labels (`endpoint`/`auth`/`process_execution`) plus `rag`/`spl`/`approved_sop_guidance`. Obtained keys are `mcp` + field names. They never intersect, so sufficiency stays PARTIAL/INSUFFICIENT.
- PlanDelta then sees only `rag` missing, cannot propose a read, stops `no_valid_plan_delta_proposal`.
- Independently, `_disposition` requires P1/P2 plus `allow_live_result_language`; severity is "Not assigned from this question alone".

CORRECT_NEXT_BEHAVIOR:
COMPLETE

CASE:
A_SUFFICIENCY_MAPPING_DEFECT

## Sufficiency key audit (filled after item 3)

| Key | Classification | Owner |
|---|---|---|
| endpoint | REQUIRED_ENVIRONMENT_EVIDENCE | envelope `approved_evidence_categories` / `categories_for_domains(endpoint_process)` |
| process_execution | REQUIRED_ENVIRONMENT_EVIDENCE | same |
| auth | NOT_APPLICABLE | catalogue leftover from `post_login_activity` on a process/persistence ask; not an auth contract |
| identity | NOT_APPLICABLE unless auth investigation | neighbour of auth in `plan_domain_scope` |
| mcp | REQUIRED_ENVIRONMENT_EVIDENCE (satisfied) | SourceEvidence `source_type=splunk_mcp` → `_record_key` = `mcp` |
| rag / rag:sop / approved_sop_guidance | ENRICHMENT | `needs_rag=True` always in P5 compiler; context_structurer SOP check |
| spl | EXECUTION_ARTIFACT (satisfied by executed MCP search) | `needs_spl` → required `spl`; semantics = executed SPL result, not the draft artifact |
| collected_source_evidence | PROVENANCE/CONTROL | context_structurer; already satisfied by collected rows |
| allow_live_result_language | PROVENANCE/CONTROL (presentation) | FinalEvidenceGate; must not manufacture disposition |
| severity P1/P2 | independent axis | existing severity policy; must not be required solely to mark suspicious |

Owners: required environment keys = approved investigation envelope + evidence legs. Completion = EvidenceState usable ∩ those keys. Disposition = what admitted evidence indicates (architecture.md §InvestigationOutcome). Severity = existing severity policy. Remediation eligibility = unchanged `completed` + `suspicious` + evidence_refs.

## Verification gaps (flag before coding)

- Item 1 dump file is test-only observation; production modules must stay untouched until item 2 records CASE.
- Item 4 vs 5: only one is executed.
- `test_phase8_sufficiency_families.py` and `test_phase15_negative_controls.py` are NEW after CASE is decided; they do not exist until the selected branch starts.

## Drift log

- Predecessor plan item 8 already observed leftover catalogue keys (`endpoint`/`auth`/`rag`/`spl`) after READ #2 collected process + persistence + dest. Item 1 must re-measure on CHECKPOINT_SHA rather than inherit that conclusion.
- Dirty-worktree RACES freeze failures are not product regressions; classify against this checkpoint.

## INVESTIGATION_OUTCOME_REMEDIATION_FINAL_ACCEPTANCE

_(filled at item 15)_
