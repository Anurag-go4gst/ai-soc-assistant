---
name: architecture-review-corrective-actions
overview: "Correct the canonical planning architecture review findings, stop specialist-report amplification, establish one tier authority, harden reference qualification, and make all four Resource Planner specialists meaningful without weakening SPL/MCP governance."
status: draft
date: 2026-08-08
canonical_plan: plans/2026-08-08_1824_architecture-review-corrective-actions.md
implementation_readiness: READY_FOR_EXECUTION
source_review: docs/architecture/architecture_review_2026-08-08.md
---

# Architecture Review Corrective Actions

## Objective

Close the confirmed and corrected findings from the 2026-08-08 canonical-planning architecture review. Done means: the live Resource Planner retains exactly four useful parallel specialists; specialist reports remain bounded and unique; MCP and SPL specialists publish deterministic, redacted plan-readiness reports; one canonical tier vocabulary drives routing and specialist reporting; fuzzy catalogue binding is reconciled into the canonical route without bypassing non-SOC or safety guards; reference qualification has bounded phrase semantics; answer-mode and telemetry policy are explicit; the large canonical lane function is decomposed without behavioural drift; and all targeted, parity, governance, backend, and documentation gates pass with recorded evidence.

This plan is corrective architecture work. It does **not** expand execution authority, enable MCP by default, make candidate SPL executable, or allow specialists to call an LLM/MCP connector.

## Source review corrections carried into this plan

| Review statement | Correct planning premise |
|---|---|
| `match_catalogue_tier()` is report-only | It also feeds `app/catalogue/live_router_bind.py`; production use must be migrated before any compatibility surface is retired. |
| Skill specialist is wrong for every reference-ID query | `Explain CVE-2024-3400` resolves canonically from initial T4 to T0 and already agrees with the T0 specialist report; the confirmed disagreement is reference-ID plus hunt/environment intent, such as `Hunt for T1059 execution in our estate`. |
| `fuzzy_alias_catalog` omission alone explains T3 drift | Alias matching independently returns T3, while the canonical match path can remain T4. The actual problem is the absence of one explicit binding-candidate-to-canonical-route contract. |
| The SPL ladder branch lacks a comment | `pipeline.py` already documents the branch. Only summaries such as `CLAUDE.md` need correction. |
| `run_canonical_planning` is about 690 lines | The seam is 35 lines; `graph_node_lane_and_canonical_planning` is the 569-line extraction target. |
| No higher-priority runtime defect exists | `specialist_reports` amplifies because every node returns full state into an `operator.add` channel. Measured 2026-08-08 via `run_resource_planner_graph`: **64 reports / 16x** (4 unique lanes) on rag_only, SPL and guided paths alike. The 8,192-16,384 figure is not reproducible at that entry point — treat 16x as the verified floor, not the ceiling. Still first priority. |

## Locked decisions

| ID | Decision |
|---|---|
| **D1** | The Resource Planner keeps **exactly four** permanent parallel specialists: `skill`, `knowledge`, `mcp`, and `spl`. MCP and SPL specialists must not be deleted, bypassed, serialized as no-op constants, or folded into another lane. |
| **D2** | Specialists are deterministic advisory/audit components. They may enrich blank arguments on an already-authorized, already-existing Resource Plan step through the validated merge; they may not add steps, change step status, remove policy checks, override non-blank arguments, or authorize execution. |
| **D3** | MCP specialist reads only the committed Evidence/Resource Plan plus redacted/cached MCP registry status. It performs no connector call, discovery network I/O, tool invocation, SPL selection, or execution-gate decision. |
| **D4** | SPL specialist reads only the committed Evidence/Resource Plan, resource registry, template registry, and bounded slot-readiness summaries. It generates no SPL text, calls no LLM, validates no candidate, and always reports `execution_eligible=false`. |
| **D5** | `initial_tier`, `resolved_tier`, and `binding_candidate_tier` are distinct. `catalogue_tier` on canonical/specialist surfaces means the final canonical `resolved_tier`, never a fresh recomputation. |
| **D6** | A validated bounded typo/alias match may promote the **effective canonical match path** to `fuzzy_alias_catalog` only after non-SOC, unsafe-command, exact-authority, and ambiguity guards pass. Parser output is preserved as observed provenance; it is not mutated in place. |
| **D7** | T0 is resolved only by canonical reference qualification. A bare reference-ID regex may extract an ID, but may not independently grant T0. |
| **D8** | `alert_summary` is an evidence-summary/no-SPL family. A contradictory `alert_summary + spl_artifact/spl_generation` contract fails closed as an internal planning contradiction; explicit SPL asks must classify into an SPL-capable family. |
| **D9** | Reference and parity baselines are immutable during ordinary checks. Updating a baseline requires explicit scope and is never the default behaviour of a verification command. |
| **D10** | Existing governance defaults remain: MCP global/server execution default-off; candidate SPL non-executable; only approved non-null `normalized_spl` may reach the MCP gate; LLM advisory-only and never calls MCP. |
| **D11** | The architecture page leads with two explicit active-path diagrams: `T1–T3 → known` and `T4 → reference qualification → T0`. Both planned paths visibly pass through all four specialists and the validated merge before dispatch. Do not communicate a path by dimming most of an all-branches diagram. |
| **D12** | Diagram labels are plain-language first and code identifiers second. Distinguish the pre-plan **Route Skill** (the selected work mode), the post-plan **Routing Contract Auditor** (`specialist_skill`), the **Knowledge Coverage Auditor** (`specialist_knowledge`), and the later **Knowledge Retrieval Worker** (RAG). “Skill” and “Knowledge” may not appear as unexplained duplicate actors. |
| **D13** | Presentation labels use four mutually exclusive dispatch branches: `D1 RAG-only`, `D2 composed step-walk`, `D3 SPL workflow`, and `D4 non-planned stop/finalize`. They are branches after the merge, not sequential stages. Runtime route names remain authoritative; these labels do not create a second dispatch contract. |

## Meaningful specialist report contracts

### MCP specialist — required report surface

The MCP report must remain redacted and bounded. It contains no endpoint, auth mode details beyond safe booleans, credentials, raw tool schemas, SPL, prompt, RAG text, or arbitrary exception strings.

| Field | Meaning / source |
|---|---|
| `plan_needs_mcp` | `EvidencePlan.needs_mcp` plus presence of existing MCP-owned steps. |
| `plan_mcp_allowed` | Copy of `EvidencePlan.mcp_allowed`; capability disclosure only, not execution authorization. |
| `discovery_allowed` | Copy of the bounded discovery policy flag. |
| `planned_hop_count` / compatibility `hop_count` | Count of existing `mcp_execution` / `mcp_discovery` steps, not a constant. |
| `registry_mode` | Safe enum such as `mock` or `registry`. |
| `global_execution_enabled` | Redacted boolean posture only. |
| `configured_server_count`, `available_server_count` | Counts from MCP registry status. |
| `candidate_server_ids` | Bounded safe server identifiers only. |
| `candidate_tool_names` | Bounded intersection of safe discovered names, registry resources, plan purpose, and deterministic capability policy. These are candidates, never a selected execution tool. |
| `execution_posture` | One of `not_needed`, `discovery_only`, `gate_required`, `blocked_by_plan`, `unavailable`. |
| `requires_execution_gate` | Always true when an execution hop exists. |
| `blockers` / `warnings` | Allowlisted reason codes only. |
| `proposals` | Fill-blank `execution_intent` / safe candidate-name metadata on an existing MCP-owned task only; never query text, normalized SPL, flags, or credentials. |

### SPL specialist — required report surface

The SPL report is planning/readiness metadata only. It never contains SPL text or claims that a candidate passed validation.

| Field | Meaning / source |
|---|---|
| `plan_needs_spl` | `EvidencePlan.needs_spl` plus presence of an existing `spl_artifact` step. |
| `plan_spl_allowed` | Copy of `EvidencePlan.spl_allowed`; not execution authority. |
| `planned_resource_id` | Existing SPL step resource ID. |
| `template_id`, `template_status`, `template_production_executable` | Governed template-registry posture when the plan binds a template. |
| `fallback_resource_id` | Existing Resource Plan `on_unavailable` target, if any. |
| `candidate_source_options` | Ordered bounded enums describing sources the downstream ladder may consider; it does not select or run them. |
| `spl_source` | Meaningful posture enum such as `not_needed`, `governed_template`, `review_only_fallback`, `blocked`, `unavailable`; no generic `template_or_fallback`. |
| `slot_binding_status` | `not_required`, `ready`, `missing_required_slots`, or `unknown`, derived from bounded canonical summaries. |
| `missing_required_slots` | Bounded slot names only, never values. |
| `validation_required` | True for every planned SPL artifact. |
| `execution_eligible` | Hard-coded/validated false on every specialist report. |
| `blockers` / `warnings` | Allowlisted reason codes only. |
| `proposals` | Fill-blank template/fallback/required-slot metadata on an existing `spl_artifact` task only; never SPL text, validator approval, or execution flags. |

## Stop conditions

- All checklist items are checked with observed Evidence and the final re-audit passes, **or**
- The same verification gate fails twice on one item, **or**
- Repo behaviour contradicts a locked decision or a required authority boundary, **or**
- A change would require new execution authority, a new default-on flag, baseline refresh, or a specialist to perform live I/O — stop and ask the user/COE.

Do not adapt silently. Record premise drift in the Drift log and stop before continuing past the affected item.

## Dependency order

`A0 → A1 → B0 → B1 → C0 → D0 → D1 → D2 → D3 → E0 → E1 → F0 → G0 → G1`

## Commit/change-set order

1. Probe tooling only (`A0`).
2. LangGraph state/reducer correctness (`A1`).
3. Canonical tier/binding contract (`B0–B1`).
4. Reference qualification (`C0`).
5. Specialist report contracts and MCP/SPL implementations (`D0–D3`).
6. Answer-mode and telemetry policy (`E0–E1`).
7. Canonical seam extraction (`F0`).
8. Documentation and final gates (`G0–G1`).

Do not combine these groups into one commit. Run `/invariant-check` before every commit that touches planner, pipeline, SPL, or MCP code.

## Checklist

- [ ] **P0 — Freeze the pre-change baseline and record the observed starting state**
  - **Do:** Capture the manifest of protected artifacts with `scripts/freeze_execution_baseline.py --capture` (13 artifacts: eval baselines, 105 golden answers, governed registries, and the three published copies of the architecture doc). Then record the *observed* starting numbers in this item's Evidence so every later item is compared against measurement rather than memory: full backend pytest counts, governance regression result, production parity exact/approved/critical, the 10 reference-probe rows, and the current `specialist_reports` cardinality per path. Do not fix anything in this item.
  - **Verify:** `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/exec-baseline.json && python3 scripts/freeze_execution_baseline.py --check --in /tmp/exec-baseline.json && PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/arch-corrective-p0-parity --check && ./scripts/run_stage3_governance_regression.sh && cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q`
  - **Depends on:** none
  - **Evidence:** _(fill when done; paste the captured manifest path, pytest pass/skip/xfail counts, harness N/6, parity exact/approved/critical, and the per-path specialist_reports cardinality)_

- [ ] **A0 — Make the reference probe gate non-destructive**
  - **Do:** Extend `scripts/audit_reference_probes.py` with a default non-mutating `--check` mode that loads and compares the frozen route rows while ignoring generated timestamps; add explicit `--out <path>` for scratch reports and an explicit `--update-baseline` operation that is never invoked by this plan. Add `backend/app/tests/test_reference_probe_audit_cli.py` (**NEW**) covering pass, drift/non-zero exit, scratch output, and unchanged baseline bytes. Do not refresh `docs/evals/reference_knowledge_baseline.md`.
  - **Verify:** `cd /var/www/ai-soc-assistant && sha256sum docs/evals/reference_knowledge_baseline.md > /tmp/reference-baseline-before.sha256 && PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check && sha256sum docs/evals/reference_knowledge_baseline.md > /tmp/reference-baseline-after.sha256 && diff -u /tmp/reference-baseline-before.sha256 /tmp/reference-baseline-after.sha256 && cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_reference_probe_audit_cli.py -q`
  - **Depends on:** P0
  - **Evidence:** _(fill when done; include 10-row PASS/DRIFT summary and unchanged SHA256)_

- [ ] **A1 — Stop additive specialist-report amplification**
  - **Do:** Replace the raw `operator.add` channel semantics for `ResourcePlannerGraphState.specialist_reports` with a deterministic, idempotent reducer keyed by `delegation_id` and `specialist_id`. Identical replay is deduplicated; conflicting reports for one delegation fail closed. Preserve the four-way `Send` fan-out. Add `backend/app/tests/test_resource_planner_specialist_report_cardinality.py` (**NEW**) and strengthen `test_resource_planner_graph_skeleton.py` from `>= 4` to exactly four unique reports in final state, `PlannerIteration`, and `WorkBundle` for T0, T1/T2, T4 guided, and fuzzy-alias probes.
  - **Anti-regression pins:** the new test must assert **exactly** 4 reports and 4 unique `specialist_id`s (observed today: 64 reports / 16x on rag_only, SPL and guided paths alike) — a `>=` assertion is what let this defect live, so it must not reappear. It must also assert that the *content* of each surviving report is unchanged from the pre-fix report for the same lane, so deduplication cannot quietly drop fields, and that all four `Send` branches remain in `resource_planner_graph_edges()`.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_specialist_report_cardinality.py app/tests/test_resource_planner_graph_skeleton.py app/tests/test_planner_hierarchy_contracts.py app/tests/test_resource_planner_validated_work_bundle.py -q && cd /var/www/ai-soc-assistant && python3 scripts/freeze_execution_baseline.py --check --in /tmp/exec-baseline.json`
  - **Depends on:** A0
  - **Evidence:** _(fill when done; record exact cardinality for every probe and confirm no specialist lane removed)_

- [ ] **B0 — Pin the canonical tier and binding-candidate contract with failing-first tests**
  - **Do:** Add `backend/app/tests/test_canonical_catalogue_tier_authority.py` (**NEW**) defining `initial_tier`, `resolved_tier`, `catalogue_tier`, `binding_candidate_tier`, parser `observed_match_path`, and canonical `effective_match_path`. Cover: pure CVE definition `T4→T0`; T1059 hunt stays `T4`; exact row T1; catalogue row T2; accepted bounded typo alias becomes effective `fuzzy_alias_catalog`/T3; non-SOC, unsafe action, ambiguous alias, and exact-authority negative controls are never promoted. Pin Skill specialist equality to canonical `catalogue_tier`.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_catalogue_tier_authority.py -q && cd /var/www/ai-soc-assistant && python3 scripts/freeze_execution_baseline.py --check --in /tmp/exec-baseline.json`
  - **Depends on:** A1
  - **Evidence:** _(fill when done; failing-first test IDs before implementation, then final pass)_

- [ ] **B1 — Establish one production tier authority and reconcile fuzzy aliases**
  - **Do:** Refactor `app/catalogue/match_tiers.py` / `live_router_bind.py` so production catalogue binding returns a typed binding candidate rather than independently granting T0–T4. Introduce a declared `effective_catalogue_match_path` state channel; preserve the parser path separately as observed provenance. Apply D6 guards before accepting `fuzzy_alias_catalog`; consume the effective path in canonical lane construction. Make `rp_node_specialist_skill` copy `canonical_planning_input.routing.catalogue_tier` and emit a warning/`None` when canonical routing is unavailable—never recompute. Keep a compatibility wrapper only while callers/tests are migrated; assert no production module outside the canonical binding seam imports the legacy tier classifier.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_catalogue_tier_authority.py app/tests/test_catalogue_bind_surface_agreement.py app/tests/test_catalogue_match_tiers.py app/tests/test_live_catalogue_router_probes.py app/tests/test_resource_planner_dry_runs.py app/tests/test_state_channel_parity.py app/tests/test_dual_runtime_lane_parity.py -q && cd /var/www/ai-soc-assistant && PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/architecture-corrective-tier-parity --check`
  - **Depends on:** B0
  - **Evidence:** _(fill when done; include import inventory, probe matrix, and parity exact/approved/critical counts)_

- [ ] **C0 — Correct bounded reference qualification and marker semantics**
  - **Do:** In `app/chat/reference_qualification.py`, replace raw substring scans with a shared boundary-aware phrase matcher. Replace bare environment-status words (`vulnerable`, `exposure`) with explicit phrases (`are we vulnerable`, `is our environment vulnerable`, `our exposure`, etc.). Use only allowlisted deterministic signals (`explicit_log_search`, `live_data_request`, `block_or_contain`, `run_execution`) to deny a knowledge-only T0 short circuit; an ID regex only extracts IDs. Extend existing reference tests with `four hours`, `hour ago`, `your team`, `flour`, definitional vulnerable-component wording, and positive environment/live-search controls. Preserve P1–P6/N1–N4 frozen behaviour through `--check`.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/ -k "reference_qualification or reference_registry or answer_shape" -q && cd /var/www/ai-soc-assistant && PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check`
  - **Depends on:** B1
  - **Evidence:** _(fill when done; include direct qualifier matrix and full 10-probe comparison)_

- [ ] **D0 — Expand specialist report contracts and proposal safety**
  - **Do:** Extend `McpSpecialistReport` and `SplSpecialistReport` in `app/planner/planner_hierarchy.py` with the required fields defined above while preserving compatibility fields. Add enum/bounds validators and forbidden-key validation. Strengthen `apply_specialist_reports()` to fill blanks only, reject cross-lane purposes, reject non-existing step proposals, and forbid specialist proposals from setting `candidate_spl`, `normalized_spl`, validator approval, `execution_enabled`, `execution_eligible`, policy checks/status, endpoint/auth/secret fields, or raw query/prompt/RAG content. Add `backend/app/tests/test_specialist_report_contracts.py` (**NEW**).
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_specialist_report_contracts.py app/tests/test_planner_hierarchy_contracts.py app/tests/test_resource_planner_validated_work_bundle.py app/tests/test_decision_record.py -q && cd /var/www/ai-soc-assistant && python3 scripts/freeze_execution_baseline.py --check --in /tmp/exec-baseline.json`
  - **Depends on:** C0
  - **Evidence:** _(fill when done; list rejected forbidden fields and fill-blank-only assertions)_

- [ ] **D1 — Implement the meaningful deterministic MCP specialist**
  - **Do:** Add `app/planner/mcp_specialist.py` (**NEW**, matching `knowledge_specialist.py` structure) with a pure `build_mcp_audit_report()` that reads the committed plan, redacted `load_mcp_registry_status()`, resource registry, and bounded capability metadata. Derive planned hop count, plan/discovery permissions, safe server/tool candidates, execution posture, blockers, and fill-blank proposals exactly per D3 and the MCP contract table. It must not call `select_mcp_tool`, any connector/discovery lifecycle, or the execution gate. Wire `rp_node_specialist_mcp` to this builder. Add `backend/app/tests/test_mcp_specialist_audit.py` (**NEW**) with not-needed, discovery-only, gate-required, plan-blocked, unavailable, blocked-tool, redaction, no-live-I/O, and merge cases.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_mcp_specialist_audit.py app/tests/test_specialist_registry.py app/tests/test_mcp_tool_planner.py app/tests/test_mcp_execution_gate.py app/tests/test_resource_planner_specialist_report_cardinality.py -q`
  - **Depends on:** D0
  - **Evidence:** _(fill when done; report one example for each execution_posture and prove connector call count zero)_

- [ ] **D2 — Implement the meaningful deterministic SPL specialist**
  - **Do:** Add `app/planner/spl_specialist.py` (**NEW**) with a pure `build_spl_audit_report()` that reads the committed plan, SPL/resource registries, canonical use-case/template provenance, and bounded slot/source-profile summaries. Derive template/fallback/source options, slot readiness, validation requirement, meaningful `spl_source`, blockers, and fill-blank proposals per D4 and the SPL contract table. Hard-validate `execution_eligible=false`; include no SPL text and call no LLM/renderer/validator. Wire `rp_node_specialist_spl` to this builder. Add `backend/app/tests/test_spl_specialist_audit.py` (**NEW**) for not-needed, active template, inactive/missing template, lab-review fallback, missing slots, source-profile gaps, forbidden SPL text, and merge cases.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_spl_specialist_audit.py app/tests/test_specialist_registry.py app/tests/test_spl_generation_stage.py app/tests/test_resource_planner_specialist_report_cardinality.py -q`
  - **Depends on:** D1
  - **Evidence:** _(fill when done; report source/slot matrix and prove LLM/validator call count zero and execution_eligible always false)_

- [ ] **D3 — Prove four-lane fan-in contributes useful, bounded information**
  - **Do:** Add end-to-end Resource Planner assertions that every planned turn yields exactly one report per permanent specialist; MCP/SPL constants are absent; useful fields agree with the committed Evidence/Resource Plan; only owned blank arguments are enriched; reports are bounded and redacted; `WorkBundle` parity prevents step/policy/status mutation. Update stable decision records to summarize posture with allowlisted codes rather than copying full reports. No specialist report becomes a new execution input outside the validated WorkBundle merge.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_resource_planner_specialist_report_cardinality.py app/tests/test_resource_planner_graph_skeleton.py app/tests/test_resource_planner_validated_work_bundle.py app/tests/test_mcp_specialist_audit.py app/tests/test_spl_specialist_audit.py app/tests/test_knowledge_specialist_audit.py -q`
  - **Depends on:** D2
  - **Evidence:** _(fill when done; include final four-report example and serialized-size/cardinality bound)_

- [ ] **E0 — Replace implicit answer-mode conditionals with an explicit ordered policy**
  - **Do:** Introduce an inspectable ordered answer-mode policy covering lane, answer goal, and intent family; do not reduce it to a family-only map. Preserve the current precedence for clarification, reference/knowledge, SPL, guided, alert-summary, and planner-decides cases. Encode D8: alert-summary remains `rag_only`, while contradictory alert-summary/SPL goals produce a typed fail-closed canonical planning error rather than silently opening a SPL lane. Add `backend/app/tests/test_canonical_answer_mode_policy.py` (**NEW**) and retain regression coverage for the prior catch-all bug.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_answer_mode_policy.py app/tests/test_canonical_planning_architecture.py app/tests/test_out_of_registry_security_log_investigation_routing.py app/tests/test_routing_summary_investigation.py app/tests/test_canonical_outcome_gate.py -q && cd /var/www/ai-soc-assistant && python3 scripts/freeze_execution_baseline.py --check --in /tmp/exec-baseline.json`
  - **Depends on:** D3
  - **Evidence:** _(fill when done; include the policy matrix and contradiction outcome)_

- [ ] **E1 — Fail closed on unclassified canonical telemetry events**
  - **Do:** Require every `emit_planning_event()` event to exist in the canonical telemetry catalog before it is logged or persisted. Add a static inventory test that discovers literal production emissions and compares them to the 8 audit-critical + 20 diagnostic catalog entries; unknown, duplicate-classified, and unclassified events fail. Preserve audit-critical persistence semantics and diagnostic degradation behaviour. Add/extend tests in `test_canonical_telemetry_coverage.py` and `test_telemetry_persistence_policy.py`.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_canonical_telemetry_coverage.py app/tests/test_telemetry_persistence_policy.py app/tests/integration/test_canonical_retention_purge.py -q && cd /var/www/ai-soc-assistant && python3 scripts/freeze_execution_baseline.py --check --in /tmp/exec-baseline.json`
  - **Depends on:** E0
  - **Evidence:** _(fill when done; include 8/20 partition and unknown-event rejection)_

- [ ] **F0 — Decompose the 569-line canonical lane function without behavioural drift**
  - **Do:** Refactor `graph_node_lane_and_canonical_planning` into named typed stages for handoff/resume preparation, lane+intent/detail resolution, canonical input/policy outcome construction, and plan persistence/commit. `run_canonical_planning` remains the sole shared entry seam, `plan_evidence_from_canonical` remains the sole plan creator, and no new orchestration flag or planning fork is introduced. Add static negative-control coverage that both production runtimes and shadow wrapper still call the same seam and no extracted stage independently composes a Resource Plan.
  - **Verify:** `cd /var/www/ai-soc-assistant/backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_dual_runtime_single_orchestration.py app/tests/test_canonical_architecture_complete.py app/tests/test_canonical_planning_architecture.py app/tests/test_resource_plan_authority.py app/tests/test_canonical_handoff_e2e_probes.py -q && cd /var/www/ai-soc-assistant && PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/architecture-corrective-seam-parity --check`
  - **Depends on:** E1
  - **Evidence:** _(fill when done; name extracted stages and record parity exact/approved/critical counts)_

- [ ] **G0 — Correct architecture and operator documentation**
  - **Do:** Update `docs/architecture/architecture_review_2026-08-08.md` with validated/corrected verdicts and the specialist amplification finding; correct the SPL ladder summary in `CLAUDE.md` without duplicating the existing branch comment. Rebuild both architecture HTML copies around D11–D13: show one uncluttered active-only `T1–T3` traversal and one active-only `T4→T0` traversal; route both through four explicit specialist audit cards, merge, and then a D1–D4 decision; remove the incorrect T0 bypass around specialists/merge. Use these primary labels (implementation names may appear as smaller secondary text or in the detailed section): Stage 1 “Receive the question and carry forward conversation context”; Stage 2 “Recognize what kind of SOC request this is”; Stage 3 “Decide whether to answer, ask for missing information, or stop”; Stage 4 “Run four independent plan-readiness checks”; Stage 5 “Combine the reports without changing the approved plan”; Stage 6 “Choose exactly one work path”; Stage 7 “Prepare and validate a safe search, bind its data source, then require the execution gate”; Stage 8 “Check evidence and safety, decide what may be claimed, require human review when needed, build the analyst card, and validate it.” Rename the specialist cards in plain language to **Routing Contract Auditor**, **Knowledge Coverage Auditor**, **MCP Readiness Auditor**, and **SPL Readiness Auditor**, with one-sentence inputs/outputs and “does not” boundaries; separately label downstream RAG as **Knowledge Retrieval Worker**. Replace the nine-node governance row whose captions overlap with a readable stacked or 3×3 checklist. Fix colour semantics so deterministic T0/reference work does not use the LLM-only iris colour. At 390 px, primary flow groups must reflow without horizontal scrolling, clipping, or sub-12px primary labels. Add `backend/app/tests/test_architecture_details_flow_contract.py` (**NEW**) to assert both HTML copies are identical, both requested traversals and D1–D4 mapping exist, specialist role names/boundaries exist, the obsolete D0 label and T0 bypass are absent, and accessible group names/descriptions summarize the actual decisions. Document `alert_summary` no-SPL policy, telemetry closed catalog, meaningful MCP/SPL report fields, and specialist no-I/O/no-authority boundaries. Do not change eval baselines. Build the frontend because `frontend/public` changes are production-served through `frontend/dist`.
  - **Verify:** `cd /var/www/ai-soc-assistant && cmp -s docs/architecture/details.html frontend/public/docs/architecture/details.html && PYTHONPATH=backend:. python3 -m pytest backend/app/tests/test_architecture_details_flow_contract.py -q && rg -n "Routing Contract Auditor|Knowledge Coverage Auditor|MCP Readiness Auditor|SPL Readiness Auditor|Knowledge Retrieval Worker|D4.*non-planned|planned_hop_count|candidate_tool_names|slot_binding_status|binding_candidate_tier" docs/architecture/architecture_review_2026-08-08.md docs/architecture/details.html frontend/public/docs/architecture/details.html CLAUDE.md && cd frontend && npm run build`
  - **Depends on:** F0
  - **Note:** G0 legitimately changes the published doc mirrors. After the frontend build, re-run `python3 scripts/freeze_execution_baseline.py --capture --out /tmp/exec-baseline.json` so G1 checks against the intended post-doc state, and record in Evidence that the only changed group was `published_doc_mirrors`.
  - **Evidence:** _(fill when done; list corrected review claims, frontend build result, the re-capture diff scope, and attach accepted Playwright screenshots at 1440×1000 and 390×844 proving both active paths, readable governance labels, and zero primary-diagram horizontal overflow)_

- [ ] **G1 — Final invariant, regression, backend, parity, and plan re-audit gate**
  - **Do:** Re-walk every completed item against its Verify field, inspect the complete diff for baseline noise/secrets/authority expansion, run `/invariant-check`, then run targeted combined tests, canonical governance regression, full backend pytest, reference `--check`, and production parity. Record exact counts. Do not mark the plan done if any item lacks Evidence or if any baseline changed.
  - **Verify:** `cd /var/www/ai-soc-assistant && .cursor/hooks/audit-plan-discipline.sh plans/2026-08-08_1824_architecture-review-corrective-actions.md && PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check && PYTHONPATH=backend:. python3 scripts/run_production_parity_eval.py --out-dir /tmp/architecture-corrective-final-parity --check && python3 scripts/freeze_execution_baseline.py --check --in /tmp/exec-baseline.json && ./scripts/run_stage3_governance_regression.sh && cd backend && PYTHONPATH=../backend:.. python3 -m pytest && cd ../frontend && npm run build`
  - **Depends on:** G0
  - **Evidence:** _(fill when done; include invariant verdict, audit 0 gaps, pytest counts, harness 6/6, parity 120/0/0, reference 10-row result, frontend build, and clean baseline diff)_

## Protected artifacts — must not change during execution

Captured by `scripts/freeze_execution_baseline.py` in **P0** and re-checked after every behaviour-changing item. A verification run must never rewrite the thing it is verifying.

| Group | Why it is frozen |
|---|---|
| Eval baselines (`reference_knowledge_baseline.md`, `regression_baseline.md`, `paraphrase_baseline.md`, probe JSONs) | These are the comparison points. `scripts/audit_reference_probes.py` currently rewrites its own baseline on every run (no argparse, unconditional `OUT.write_text()`), which is exactly what A0 fixes. |
| 105 golden answers (`question_105_golden.jsonl`) | The in-catalogue contract. Byte-identical output is the regression signal. |
| Governed registries (`use_cases/catalog.json`, `skills/catalog.json`, `spl/templates.json`) | 65 / 19 / template governance. A refactor has no reason to touch these; if one does, the refactor changed behaviour. |
| Published doc mirrors (`docs/`, `frontend/public/`, `frontend/dist/`) | Must stay byte-identical to each other — the guard asserts mutual equality, not just individual stability. G0 re-captures deliberately after documentation edits. |

Drift is a **stop condition**, not a warning. If a change is intentional, say so explicitly and re-capture; never refresh as a side effect.

## Required invariants during implementation

- Four `Send` branches remain visible in `resource_planner_graph_edges()` and the specialist registry continues to validate exactly four descriptors.
- Specialist reports are advisory or proposed-validated metadata only; final Resource Plan, SPL validator, and MCP execution gate remain authorities.
- MCP/SPL specialist builders are pure with respect to external systems: zero connector, LLM, renderer, validator, persistence, or execution calls.
- All report names/lists are bounded; only safe identifiers and reason codes are emitted.
- COE/manual config precedence remains unchanged; registry/session/RAG may fill blanks only.
- Candidate SPL never becomes evidence or execution input; `execution_eligible` remains false in the specialist layer.
- A candidate MCP tool name is not a selected tool. Deterministic selection and RBAC stay at the existing execution-gate stage after SPL validation.
- Non-planned canonical outcomes retain no edge to SPL generation or MCP execution.
- No new inline imports except an already-documented circular dependency site.
- No eval baseline refresh or accidental `frontend/dist` permission regression.

## Verification gaps

None at authoring time. Every checklist item has an exact test or gate. Tests marked **NEW** are created by the corresponding item before its Verify command is run.

## Drift log

| Date | Note |
|---|---|
| 2026-08-08 | Plan created from review of `docs/architecture/architecture_review_2026-08-08.md` against `master@1681f90`. |
| 2026-08-08 | User directive locked: MCP and SPL specialists remain critical permanent fan-out lanes and must be made meaningful; removal/collapse is prohibited. |
| 2026-08-08 | Plan-discipline audit passed with 14 checklist items, 14 Verify fields, and 0 gaps; plan is ready for execution. |
| 2026-08-08 | Removed the separate loop-runner at user direction. This canonical plan is the sole implementation source. |
| 2026-08-08 | Live Playwright audit confirmed the current diagrams are not an adequate target: the requested T4→T0 traversal is only a note, the SVG bypasses specialists/merge for T0, the two walkthrough SVGs differ mainly by dimming, governance captions overlap at 1440 px, and 390 px diagrams clip horizontally. D11–D13 and G0 now pin plain-language, role-distinct, responsive replacement diagrams. |
| 2026-08-08 | User-authorized page correction implemented the G0 visual contract early with an accessible responsive architecture SVG (separate desktop/mobile layouts) backed by semantic plain-language HTML. The page explicitly labels MCP/SPL as fixed markers today; it does not claim D1/D2 specialist backend work is complete. G0 remains unchecked until its documentation and full verification gates are satisfied. |
| 2026-08-08 | Anti-regression hardening added: new **P0** freezes a SHA256 manifest of 13 protected artifacts via `scripts/freeze_execution_baseline.py` (**NEW**, drift-tested in both directions) and records observed starting counts; `--check` appended to A1/B0/C0/D0/E0/E1 Verify commands; new "Protected artifacts" section; G0 re-captures after its intentional doc-mirror change; G1 checks the manifest before the governance regression. A0 now depends on P0. |
| 2026-08-08 | Audit vs live code: all six source-review correction premises verified correct against `master@1681f90`. Referenced scripts/tests exist except `app/tests/test_mcp_tool_selector.py`, which does not exist — D1 Verify corrected to `test_mcp_tool_planner.py` (`select_mcp_tool` is additionally covered by `test_mcp_execution_gate.py`, already listed). |
| 2026-08-08 | A1 premise re-measured: amplification mechanism confirmed (`specialist_reports: Annotated[list, operator.add]` at `resource_planner_graph.py:143` + every node returning full state via `_record`), and `test_resource_planner_graph_skeleton.py:118` masks it with `>=`. Observed 64 reports / 16x, not 8,192-16,384; magnitude claim corrected in the premise table. |
| 2026-08-08 | A0 premise confirmed: `scripts/audit_reference_probes.py` has no argparse and calls `OUT.write_text()` unconditionally, so it rewrites `docs/evals/reference_knowledge_baseline.md` on every run. A non-mutating `--check` is genuinely required before C0/G1 can use it as a gate. |
| 2026-08-08 | Existing dirty-worktree files belong to the user and are outside plan authoring scope: `.claude/settings.local.json`, `backend/app/chat/detail_tools/__init__.py`, both architecture HTML copies, and the untracked architecture review. Execution must preserve/reconcile them rather than overwrite unrelated edits. |
