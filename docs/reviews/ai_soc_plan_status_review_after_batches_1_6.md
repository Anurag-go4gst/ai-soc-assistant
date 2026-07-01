# AI SOC Assistant — Plan Status Review After Batches 1–6

**Date:** 2026-06-07  
**Type:** Review / audit only (Batch 7) — no runtime changes  
**Baseline:** `master` @ `84b77f8` (PR #6 + PR #7 merged) + Batch 6 docs commit `d1a7b24`  
**Canonical plan:** [`plans/AI_SOC_MASTER_PLAN.md`](../../plans/AI_SOC_MASTER_PLAN.md)

> **Post-2026-07-01 status note:** This review is a historical Batch 1–6 audit. Later work added a live `splunk_run_query` adapter and bounded search lifecycle, still default-off and COE-gated. Use [`docs/coe/COE_ROLLOUT_CONFIGURATION.md`](../coe/COE_ROLLOUT_CONFIGURATION.md) and [`docs/architecture/real_splunk_mcp_safety_contract.md`](../architecture/real_splunk_mcp_safety_contract.md) for current rollout posture.

---

## A. Executive summary

Batches **1–6** delivered the intended **governed hardening path** without replacing the four live skills, without loading GitHub `SKILL.md` into runtime, and without enabling real Splunk MCP or LLM-to-Splunk tool calling.

**What landed:**

| Area | Outcome |
|------|---------|
| HIL / mock MCP | Hardened labels and gates; mock execution still double-flagged |
| GitHub skills | All 7 mandatory references **accepted** (1 partial section reject); curated into `content_enrichment.json` |
| MITRE | Evidence-status vocabulary + pilot preconditions in runtime; legacy `_status_for()` still present in `mitre_kb.py` |
| SPL | Template-first governance; LLM fallback disabled by default; validation mandatory |
| Pipeline | Top-level visibility fields + finalize-time `node_trace` |
| Session | Structured pins, 30-min TTL, follow-ups; in-process only |
| Real MCP | **Docs-only** safety contract (Batch 6); execution still blocked |

**Largest remaining gaps before real Splunk MCP or broad skill expansion:**

1. COE-supplied connection details, signed schema, approval hardening, audit sink (Batch 6 contract gates).
2. A2 reconcile: remove `mitre_kb._status_for()` from live paths.
3. SPL templates for P4/P5/P3/P7 pilots still `planned` / `unavailable`.
4. Authoritative 105-question → use-case mapping: **1 / 105** curated (`q0.q062`).
5. Enrichment metadata not yet wired into runtime routing/planning nodes (C2/C3).

**Recommended next phase:** **Client-demo hardening** (see §M) — activates demo-critical SPL templates, expands defensible mappings for golden demo queries, and polishes visibility UX **without** crossing the real MCP boundary.

---

## B. Original intent vs actual outcome

| Question | Answer | Evidence |
|----------|--------|----------|
| Did we improve the existing system? | **Yes** | HIL hardening, MITRE/SPL governance, pipeline visibility, session context, quality ledger, governance regression green |
| Did we enrich skills using the GitHub cybersecurity skills repo? | **Yes (metadata only)** | 7 records in `github_skill_intake_register.json` → `content_enrichment.json` |
| Did we avoid blindly importing GitHub `SKILL.md` files? | **Yes** | Usage rule: reference/provenance only; no runtime markdown loading; scripts never executed |
| Did we preserve the 4 live skills? | **Yes** | `alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall` unchanged as live execution enum |
| Did we preserve `legacy_router_intent_hint` and `proposed_primary_skill`? | **Yes** | Coverage matrix + routing tests; dual-skill semantics documented in plan §A |
| Did we keep SPL template-first and validation-gated? | **Yes** | `validate_spl()` required; `AI_SOC_LLM_SPL_FALLBACK_ENABLED=false` default |
| Did we keep MITRE evidence-based? | **Mostly** | `mitre_decision.resolve_mitre_decision` + `mitre_evidence_preconditions`; legacy `_status_for()` still in `mitre_kb.map_mitre_for_use_case` |
| Did we avoid real Splunk MCP execution? | **Yes** | At this historical baseline, non-mock execution was blocked and execution flags defaulted false |
| Did we avoid LLM-to-Splunk direct tool calling? | **Yes** | `supports_tool_calling` false; deterministic tool selection; LLM never calls MCP |

---

## C. Batch-by-batch status

| Batch | Scope | Merged | Key commit(s) | Runtime? | Tests | Status |
|-------|-------|--------|---------------|----------|-------|--------|
| **1** | HIL hardening for mock MCP execution | PR #4 → `master` | `aaed1a9`, merge `7222937` | Yes | `test_hil_mock_execution_hardening.py` | **Done** |
| **2** | 7 SOC skill enrichment baseline (GitHub references) | PR #5 → `master` | `927c884`, merge `4e1a2f3` | Metadata only | `test_skill_content_enrichment_baseline.py` | **Done** |
| **2.1** | Defensible offline question→use-case mapping | PR #5 / follow-on | `4d002e5`, `b164cb2` | Tooling | `build_skill_coverage_matrix.py --check` | **Done** (1/105 curated) |
| **3** | MITRE evidence status + SPL template governance | PR #6 → `master` | `6564b37`, merge `9faac7c` | Yes | `test_mitre_spl_governance_batch3.py` | **Done** |
| **3.1** | Pilot evidence/output contract verification | PR #6 | `7f385e7` | Yes | `test_batch3_pilot_output_contracts.py` | **Done** |
| **4** | Pipeline visibility + guarded answer flow | PR #6 | `1c1b5c2` | Yes | `test_batch4_pipeline_trace_answer_guard.py` | **Done** |
| **5** | Lightweight investigation session context | PR #7 → `master` | `e3dcdb6`, merge `84b77f8` | Yes | `test_batch5_session_context.py` | **Done** |
| **6** | Real Splunk MCP safety contract | Direct on `master` | `d1a7b24` | **Docs only** | N/A (contract doc) | **Done** |
| **7** | Plan status review (this document) | Pending commit | — | Docs only | N/A | **In progress** |

Post-merge fix: `db02f20` — streamed `/clear` clears backend session pins.

---

## D. GitHub skills usage audit

**Reference repo:** `mukul975/Anthropic-Cybersecurity-Skills` @ `04450304` (754 skills; **7 reviewed** for batch 1).

| # | GitHub skill | Decision | Internal use case(s) | MITRE borrowed (conceptual) | Not copied (safety) |
|---|--------------|----------|----------------------|-------------------------------|---------------------|
| 1 | `detecting-rdp-brute-force-attacks` | **Accepted** | `auth_failed_login_spike`, `auth_success_after_failure` | T1021.001, T1110.001, T1110.003, T1078 | Offensive blocking scripts, arbitrary remote execution |
| 2 | `triaging-security-alerts-in-splunk` | **Accepted** (cross-cutting SOP) | P1, P2, `soc_incident_triage` | T1078, T1566 | Direct Splunk UI automation, write actions |
| 3 | `analyzing-email-headers-for-phishing-investigation` | **Accepted** | `email_phishing_header_review` (planned) | T1566.001/002, T1598.003 | External lookups, forensic scripts |
| 4 | `hunting-for-anomalous-powershell-execution` | **Accepted** | `edr_powershell_suspicious_command` | T1059, T1059.001 | Command execution, malware verdict language |
| 5 | `hunting-for-command-and-control-beaconing` | **Accepted** | `dns_beaconing_candidate` | T1071 | C2 infrastructure guidance; periodicity ≠ confirmed C2 |
| 6 | `triaging-security-incident-with-ir-playbook` | **Accepted** | `soc_incident_triage`, `soc_show_sop` | T1486, T1070, T1078 (alert-evidence only) | curl/TI auto-calls, destructive containment |
| 7 | `analyzing-ransomware-encryption-mechanisms` | **Partial accept** | `endpoint_ransomware_impact_review` (planned) | T1486, T1573, T1027 (defensive impact only) | Ghidra, RE, decryptor workflows (`rejected_github_skills.md`) |

**Rejected (full skill):** none among the 7 mandatory references.

**Deferred (backlog):** lateral movement (`BL-001`–`BL-003`), explicit phishing/ransomware 105-row mappings (`BL-005`, `BL-006`) pending authoritative sources.

**Tracking files:** `docs/skills/github_skill_intake_register.json`, `rejected_github_skills.md`, `pending_skill_enrichment_backlog.md`, `skill_enrichment_status_matrix.md`, `backend/app/use_cases/content_enrichment.json`.

---

## E. Current system behavior after all batches

### 1. HIL / execution governance

| Item | Detail |
|------|--------|
| **Files** | `mcp_execution_gate.py`, `connectors/mcp/mock.py`, `pipeline.py`, `config.py` |
| **Behavior** | Mock execution requires `MCP_GLOBAL_EXECUTION_ENABLED` + per-server flag; HIL/review labels on success paths hardened (Batch 1) |
| **Tests** | `test_hil_mock_execution_hardening.py`, `test_mcp_execution_gate.py` |
| **Status** | **Done** for mock; real blocked |
| **Gaps** | Durable approval store for normalized SPL hash; real adapter |

### 2. Skill enrichment

| Item | Detail |
|------|--------|
| **Files** | `use_cases/content_enrichment.json`, `use_cases/content_enrichment.py`, `catalog.json` |
| **Behavior** | 7 enrichment records; **not** loaded into LLM prompts or routing by default |
| **Tests** | `test_skill_content_enrichment_baseline.py` |
| **Status** | Metadata baseline complete |
| **Gaps** | Runtime enrichment load node (C3); catalog entries for P3/P6/P7 proposed use cases |

### 3. GitHub skill intake tracking

| Item | Detail |
|------|--------|
| **Files** | `docs/skills/*` |
| **Behavior** | Docs-only register, rejection log, backlog, status matrix |
| **Tests** | Generator/check scripts |
| **Status** | **Done** (slice 0 + Batch 2 linkage) |
| **Gaps** | D5 full matrix ↔ intake column sync for all 105 rows |

### 4. MITRE evidence status

| Item | Detail |
|------|--------|
| **Files** | `mitre_decision.py`, `mitre_evidence_preconditions.py`, `mitre_attack_subset.json`, `negative_evidence_extractor.py`, `pipeline_visibility.py` |
| **Behavior** | Runtime `evidence_statuses` on live path via `resolve_mitre_decision`; pilot evaluator for batch 3 |
| **Tests** | `test_mitre_spl_governance_batch3.py`, `test_mitre_decision_runtime.py`, `test_batch3_pilot_output_contracts.py` |
| **Status** | **Mostly done** |
| **Gaps** | `_status_for()` in `mitre_kb.py`; full ATT&CK mirror; more preconditions for P3–P7 |

### 5. SPL template governance

| Item | Detail |
|------|--------|
| **Files** | `spl/templates.json`, `template_registry.py`, `template_renderer.py`, `spl_validator.py`, `spl/llm_fallback.py`, `pipeline.py` |
| **Behavior** | Active templates for auth pilots + AWS samples; planned/unavailable surfaced as governed limitations |
| **Tests** | `test_mitre_spl_governance_batch3.py`, `test_llm_spl_fallback.py`, template stage tests |
| **Status** | **Done** for governance rules |
| **Gaps** | Active SPL for PowerShell, beaconing, phishing, ransomware pilots |

### 6. Pipeline visibility / node trace

| Item | Detail |
|------|--------|
| **Files** | `pipeline_visibility.py`, `control_plane_trace.py`, `schemas/responses.py`, frontend `AnalystResponseCard.tsx` |
| **Behavior** | Additive fields when control plane enabled; `node_trace` built at **finalize-time** |
| **Tests** | `test_batch4_pipeline_trace_answer_guard.py` |
| **Status** | **Done** |
| **Gaps** | Incremental trace during streaming; UI polish for collapsed trace |

### 7. Answer guard / final validation

| Item | Detail |
|------|--------|
| **Files** | `final_answer_validator.py`, `answer_guard/runner.py` (dormant LLM guard), `analyst_response_builder.py` |
| **Behavior** | Deterministic final validator runs on control-plane path; LLM Answer Guard **config-gated off** by default |
| **Tests** | `test_final_answer_validator.py`, `test_batch4_pipeline_trace_answer_guard.py` |
| **Status** | Final validator **active**; semantic LLM guard **dormant** |
| **Gaps** | A6 lab enablement for semantic guards |

### 8. Session context

| Item | Detail |
|------|--------|
| **Files** | `session_store.py`, `session_context.py`, `pipeline.py`, frontend `ChatPanel.tsx` |
| **Behavior** | Structured pins, TTL 30 min, follow-ups, gates re-run each turn |
| **Tests** | `test_batch5_session_context.py` (8 tests) |
| **Status** | **Done** (MVP) |
| **Gaps** | Durable/redis store; multi-worker; richer follow-up NLP |

### 9. Real MCP readiness documentation

| Item | Detail |
|------|--------|
| **Files** | `docs/architecture/real_splunk_mcp_safety_contract.md`, `splunk_mcp.py`, `mcp_execution_gate.py` |
| **Behavior** | **Docs only** — 15+ activation gates documented |
| **Tests** | Existing gate tests asserted non-mock execution stayed blocked |
| **Status** | **Contract done**; implementation **not started** |
| **Gaps** | COE connection, adapter, audit, approval workflow |

### 10. Coverage matrix / evaluation tracking

| Item | Detail |
|------|--------|
| **Files** | `docs/evals/skill_coverage_matrix.json`, `question_use_case_map.json`, `scripts/build_skill_coverage_matrix.py`, `quality/store.py` |
| **Behavior** | 105 rows monotonic; 1 curated mapping; quality ledger + golden runners |
| **Tests** | Governance regression, Tier 0 golden, expectation matrix |
| **Status** | **Scaffold done**; mapping sparse |
| **Gaps** | Authoritative mappings for demo/golden questions |

---

## F. Skill enrichment status

**Records in `content_enrichment.json`:** **7** (all tested at metadata level).

| Use case | Catalog status | SPL template | MITRE candidates | Evidence reqs | Answer rules | 105 mapping |
|----------|----------------|--------------|------------------|---------------|--------------|-------------|
| `auth_failed_login_spike` | **active** | **active** (`auth_failed_login_spike`) | T1110, T1110.001, T1110.003; conditional T1078 | Yes | Yes | `q0.q062` curated |
| `auth_success_after_failure` | **active** | **active** (`auth_success_after_failure`) | T1110.001, T1078 | Yes | Yes | None authoritative |
| `edr_powershell_suspicious_command` | **active** | **planned** (no `spl_text`) | T1059, T1059.001 | Yes | Yes | None |
| `dns_beaconing_candidate` | **active** | **planned** (`dns_beaconing_candidate` stub in templates.json) | T1071 | Yes | Yes | None |
| `email_phishing_header_review` | **planned** (proposed) | **planned** | T1566.* | Yes | Yes | Deferred (BL-005) |
| `soc_incident_triage` | **planned** (proposed) | **unavailable** | Per alert only | Yes | Yes | None |
| `endpoint_ransomware_impact_review` | **planned** (proposed) | **planned** | T1486, etc. | Yes | Yes | Deferred (BL-006) |

**Summary counts:**

- Active enrichment use cases: **4** (auth×2, PowerShell, beaconing)
- Planned/proposed: **3** (phishing, IR triage, ransomware)
- Active SPL templates (pilot-linked): **2** (auth failed spike, success-after-failure)
- Planned/unavailable SPL: **5+** pilot-related stubs
- Connected to 105 coverage with authoritative mapping: **1 / 105**
- `mitre_kb` updated from GitHub lists: **false** in intake register (`mitre_kb_updated: false` for all 7)

---

## G. MITRE status maturity

**Techniques in pilot subset:** expanded in `mitre_attack_subset.json` (auth, endpoint, DNS, phishing, ransomware families).

**Evidence-status aware (runtime):** `mitre_decision.evidence_statuses` via `evaluate_pilot_mitre_evidence_status` + `precondition_negated` for T1078, T1003, T1562.001, T1041, T1071, T1021.

**Typical outcomes by scenario:**

| Scenario | Typical status |
|----------|----------------|
| Failed-login spike with threshold | T1110.001 → `evidence_supported` or `candidate` (pilot rules) |
| Success-after-failure without misuse proof | T1078 → `candidate`; compromise language blocked |
| Beaconing periodicity only | T1071 → `candidate`; C2 confirmed blocked by final validator |
| Phishing header mismatch only | T1566 → `candidate` / `not_claimed` without full evidence |
| Ransomware without encryption evidence | T1486 → `not_claimed` / `requires_validation` |

**`_status_for()` usage:** Still defined and called in `mitre_kb.map_mitre_for_use_case` (`mitre_kb.py:73`). Separate `_status_for_server` / `_status_for_provider` in MCP/LLM registries (unrelated). **A2 reconcile pending.**

**`mitre_permitted`:** Coverage-matrix metadata (76 rows have entries); **not** treated as observed evidence in `resolve_mitre_decision`.

**Confirmed MITRE without evidence:** Blocked by answer contract, final validator (`final.candidate_described_as_confirmed`, unsafe-claim patterns), and precondition demotion.

**Pending MITRE gaps:** full ATT&CK mirror; lateral movement (BL-001); cloud techniques; phishing/ransomware planned paths; stronger T1078 evidence logic; sub-technique expansion for T1071/T1566.

---

## H. SPL governance maturity

**Active templates (status `active`):** 8 in `templates.json` — auth family (4), AWS CloudTrail (3), failed-login top users; pilot P1/P2 templates included.

**Enriched skills with active templates:** `auth_failed_login_spike`, `auth_success_after_failure` only.

**Planned/unavailable:** `dns_beaconing_candidate`, `edr_suspicious_process`, privileged/vpn/firewall stubs; `soc_incident_triage` → **unavailable** (SOP-only).

**Governed limitations:** Shown via `spl_template_status` + enrichment `limitations` when template missing/planned (`pipeline_visibility.resolve_spl_template_status`).

**LLM fallback bypass:** **No** — `ai_soc_llm_spl_fallback_enabled=false`; fallback output must pass `validate_spl()`; adapter forces non-executable.

**`validate_spl()` mandatory:** Yes before MCP execution gate.

**Blocked commands:** Still enforced in `spl_validator.py`.

**Real Splunk MCP:** **Disabled** at this historical baseline; see the post-2026-07-01 status note for current adapter posture.

---

## I. Pipeline / answer safety maturity

**Visibility fields (control-plane gated):** `mitre_evidence_status`, `spl_template_status`, `answer_guard_status`, `final_answer_safety_status`, `session_context_status`.

**`node_trace` stages:** `session_context`, `routing_live_skill_selection`, `planning_analytic_skill_resolution`, `enrichment_loading`, `evidence_planning`, `spl_template_status`, `spl_validation`, `execution_hil_decision`, `mitre_evidence_status`, `severity_decision`, `answer_contract`, `answer_guard`, `final_answer_validation`.

**Trace timing:** Assembled at **finalize-time** in `build_pipeline_node_trace()` — not incremental per streaming event.

**Answer guard:** LLM semantic guard (`AI_SOC_LLM_ANSWER_GUARD_ENABLED`) **off** by default; deterministic **final validator always on** when control plane builds analyst response.

**Final validator blocks (always when triggered):** blocked findings claimed; MITRE visible when suppressed; RAG override MITRE; SPL on RAG-only; candidate described as confirmed; SPL-only missing actions; unsafe account compromise / C2 / ransomware / malware claims; SPL executed claims; evidence_supported without status; containment without HIL.

---

## J. Session context maturity

| Topic | Detail |
|-------|--------|
| **Pins stored** | trace_id, alert_id, use_case_id, live/planning skills, entities, candidate_spl, spl validation/template status, mitre decision/status, context sufficiency, execution/HIL status |
| **Transcript** | **Not stored** |
| **TTL** | 30 minutes (`AI_SOC_SESSION_CONTEXT_TTL_MINUTES`) |
| **Follow-ups** | MITRE mapping, SPL refine, same alert, severity/summary/evidence phrasing |
| **Gate re-run** | MITRE, SPL validation, HIL re-run every turn |
| **Execution approval** | **Cannot** — pins inform planning only |
| **Limitations** | In-process dict; lost on restart/multi-worker; heuristic follow-up detection |

---

## K. Real MCP readiness (Batch 6 contract)

**Still blocks real implementation:**

1. No COE server URL, transport, auth, signed tool schema
2. `splunk_mcp.py` not implemented
3. No durable approval store bound to normalized SPL hash
4. No audit sink readiness gate
5. `UnconfirmedRealMcpResultAdapter` — real schema unverified
6. Global + per-server execution flags default false
7. Template status gate for enriched use cases not fully enforced at execution gate
8. Organizational approval workflow undefined

**Gates before live Splunk:** All rows in `real_splunk_mcp_safety_contract.md` §Activation Gates (15+).

**Approval model:** Human `approved_for_read_only_search` for exact normalized SPL; bound to trace/hash; LLM cannot approve.

**Audit trail:** Durable sink required before first live execution.

**Config/secrets:** Redacted status only; no secrets in repo; COE-managed credentials.

**Test harness:** Mock gate tests exist; need COE-signed fixture rows + adapter integration tests.

**Out of scope (initial):** SAIA tools, saved-search execution, writes, telemetry writeback, LLM tool calling.

---

## L. Remaining gaps and risks

| Priority | Category | Item |
|----------|----------|------|
| **P0** | Real MCP | COE adapter + signed schema + approval + audit (contract only today) |
| **P0** | MITRE | Remove `_status_for()` from `mitre_kb` live path (A2) |
| **P0** | Demo | Active SPL templates for PowerShell + beaconing minimum |
| **P1** | Demo | Expand authoritative `question_use_case_map.json` for golden/demo queries |
| **P1** | SPL | Promote `dns_beaconing_candidate` + `edr_powershell` templates to active |
| **P1** | Enrichment | Wire enrichment load into pipeline (C3) behind flag |
| **P1** | MITRE | Preconditions for T1566, T1486, T1059.001 pilots |
| **P2** | Skills | Catalog entries for P3/P6/P7 proposed use cases |
| **P2** | UI | Node trace + visibility UX polish |
| **P2** | Session | Durable session store for multi-worker |
| **P3** | Architecture | C2/C4/C5 node splits; skill enum unification deferred |
| **P3** | Skills | Lateral movement backlog BL-001–003 |

**Risks:** R4 session overclaim (mitigated by gate re-run); R5 MITRE overclaim (mitigated by final validator); R12 demo with planned-only SPL paths shows limitations not investigations.

---

## M. Recommended next phase

**Recommendation: 6 — Client-demo hardening**

**Reason:** Batches 1–6 established governance and documentation; the highest-value next step **without** real MCP is to make the Experience Center / live-chat demo paths **repeatable** for the seven pilot narratives: activate SPL templates for PowerShell and beaconing, add defensible mappings for a small set of golden questions beyond `q0.q062`, and polish visibility surfaces so analysts see MITRE/SPL/HIL status clearly. This directly addresses the largest user-visible gaps (planned templates, 1/105 mapping) while respecting Batch 6 deferral of real Splunk execution.

**Not recommended next:** Real Splunk MCP implementation (1) — blocked by COE and Batch 6 gates until approval model and adapter land.

---

## N. Action backlog

### Must fix before real Splunk MCP (P0)

- [ ] Implement COE Splunk MCP adapter (`splunk_mcp.py`)
- [ ] Signed real result schema + swap off `UnconfirmedRealMcpResultAdapter`
- [ ] Durable approval store (normalized SPL hash ↔ trace)
- [ ] Audit sink readiness gate
- [ ] Enforce template-status gate at execution gate for enriched use cases

### Must fix before client demo (P0–P1)

- [ ] Active SPL templates: `edr_powershell_suspicious_command`, `dns_beaconing_candidate`
- [ ] Curate 5–10 additional `question_use_case_map.json` entries with cited evidence
- [ ] UI: surface `spl_template_status` / `mitre_evidence_status` prominently on analyst card
- [ ] A2: reconcile `mitre_kb._status_for()` out of live path

### Skill enrichment expansion (P2)

- [ ] Promote P3/P6/P7 from proposed → catalog when demo-ready
- [ ] BL-005/BL-006 phishing/ransomware 105 mappings when authoritative source exists
- [ ] BL-001 lateral movement deferred review

### MITRE expansion (P1–P2)

- [ ] Extend `PRECONDITIONS` for T1566, T1486, T1059.001
- [ ] Expand `mitre_attack_subset.json` for pilot techniques
- [ ] Sub-technique rules for beaconing/phishing

### SPL template expansion (P1)

- [ ] `email_phishing_header_review` template (planned → active)
- [ ] `endpoint_ransomware_impact_review` impact-review template
- [ ] Keep `soc_incident_triage` SOP-only (`unavailable` SPL)

### UI / visibility (P2)

- [ ] Collapsed technical trace defaults + session context badge
- [ ] Streaming incremental trace (future)

### Testing / evaluation (P1)

- [ ] Golden cases for P4/P5 once templates active
- [ ] Tier 0 expansion for session + planned-template limitation paths

### Architecture cleanup (P3)

- [ ] C2 planning skill resolution node
- [ ] C3 enrichment-aware evidence planner
- [ ] C4 SPL node split

---

## Validation

- **Docs-only batch** — no code or runtime changes in this deliverable.
- Governance regression not required for doc commit.
- Review based on `master` tree inspection and merged PR history (PR #6 `9faac7c`, PR #7 `84b77f8`, Batch 6 `d1a7b24`).
