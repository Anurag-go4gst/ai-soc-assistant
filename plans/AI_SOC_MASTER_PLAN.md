# AI SOC Assistant — Master Plan

**Document:** `plans/AI_SOC_MASTER_PLAN.md` — **single canonical plan** for hardening, skill enrichment, pipeline/LangGraph, and GitHub skill intake tracking.
**Date:** 2026-06-06 (amended 2026-07-01)
**Status:** **§O acceptance loop CLOSED (2026-07-01).** Batches 1–6 + consolidated handoff/T2 closure complete (`ca3249b`, PRs #38–#45, Batches 0–F). Guided Hybrid Investigation Orchestrator complete ([`plans/2026-07-01_1545_guided-readonly-mcp-discovery-lane.md`](2026-07-01_1545_guided-readonly-mcp-discovery-lane.md)). **Forward roadmap §P / §K / §R remains open** — next slice requires explicit scope approval (see [`docs/reviews/ai_soc_plan_status_review_after_batches_1_6.md`](../docs/reviews/ai_soc_plan_status_review_after_batches_1_6.md)).
**Canonical for:** Tracks A–D, pilot enrichments P1–P7, execution order, tracking table (§P)

> **Single plan only.** Do not use `plans/2026-06-06_*.md` drafts (removed). All amendments live here.

### Table of contents

| § | Section |
|---|---------|
| — | [Planning acceptance](#planning-acceptance-this-document) |
| A | [Executive recommendation](#a-executive-recommendation) |
| B | [Four-track roadmap](#b-updated-four-track-roadmap) |
| C | [GitHub reference repo](#c-external-github-soc-skill-references-inspected) |
| D | [Architecture constraints](#d-current-architecture-constraints) |
| E | [Track A — Hardening](#e-track-a--existing-system-hardening) |
| F | [Track B — Enrichment](#f-track-b--skill-content-enrichment) |
| G | [Track C — Pipeline / LangGraph](#g-track-c--langgraph--pipeline-node-improvement) |
| H | [Track D — Skill intake & tracking](#h-track-d--skill-intake-review-rejection-and-implementation-tracking) |
| I | [Pilot skills P1–P7](#i-seven-pilot-enriched-soc-skill-records) |
| J | [Dependency map](#j-dependency-map-a--b--c--d) |
| K | [Execution order](#k-recommended-execution-order) |
| L | [First implementation slice](#l-first-implementation-slice-post-planning) |
| M | [Deferred items](#m-deferred-items) |
| N | [Risk register](#n-risk-register) |
| O | [Acceptance criteria](#o-acceptance-criteria) |
| P | [Tracking table](#p-proposed-tracking-table) |
| Q | [Review findings](#q-review-findings--bugs-and-fixes) (amendments applied to body) |

### Tracking files

| File | Track | Status |
|------|-------|--------|
| `docs/skills/github_skill_intake_register.json` | D1 | **Done** (slice 0) |
| `docs/skills/rejected_github_skills.md` | D2 | **Done** (slice 0) |
| `docs/skills/pending_skill_enrichment_backlog.md` | D3 | **Done** (slice 0) |
| `docs/skills/skill_enrichment_status_matrix.md` | D4 | **Done** (slice 0) |
| `docs/skills/README.md` | D6 | **Done** (slice 0) |
| `docs/evals/skill_coverage_matrix.json` | D5 / B9 | **BL-004 closed (S1c)** — 41/105 mapped; 64 genuine gaps |

### External GitHub reference repository (read-only — not installed in runtime)

| Field | Value |
|-------|-------|
| **GitHub URL** | `https://github.com/mukul975/Anthropic-Cybersecurity-Skills` |
| **Local clone path** | `/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills` |
| **Clone command used** | `mkdir -p /tmp/ai-soc-references && cd /tmp/ai-soc-references && git clone https://github.com/mukul975/Anthropic-Cybersecurity-Skills.git` |
| **Pinned commit (inspection)** | `04450304b12645cb2b974ab96d28c0664758a88d` (2026-06-01 — `chore: auto-update index.json`) |
| **Skill count** | 754 directories under `skills/` |
| **Format** | agentskills.io `SKILL.md` per skill; optional `references/`, `scripts/`, `assets/` |
| **Index / coverage** | `index.json`, `ATTACK_COVERAGE.md`, `mappings/`, `mappings/mitre-attack/README.md` |
| **Usage rule** | **Reference and provenance only.** Not copied into repo runtime. Not loaded into LLM prompts. Scripts in repo are **never executed** by AI SOC Assistant. |

> **Note:** `/tmp/ai-soc-references/` is ephemeral on the host. For durable provenance, record `repo_commit` in `docs/skills/github_skill_intake_register.json` per skill. Re-clone when reviewing new skills.

---

## Planning acceptance (this document)

- [x] Four tracks defined (A Hardening, B Enrichment, C Pipeline/LangGraph, **D Skill Intake & Tracking**)
- [x] All 7 mandatory GitHub reference skills included
- [x] Optional lateral-movement enrichment candidates identified
- [x] LangGraph / pipeline node improvement section (Track C)
- [x] Skill intake / rejection / implementation tracking layer (Track D)
- [x] Coverage matrix path and schema proposed (`docs/evals/skill_coverage_matrix.json`)
- [x] Defensive-conversion checklist included
- [x] Dual skill semantics preserved: `live_execution_skill` vs `planning_or_analytic_skill`
- [x] GitHub repo location, clone path, and pinned commit documented
- [x] A2 MITRE vocabulary + compatibility mapping locked (additive, not breaking)
- [x] P3/P6/P7 enrichment-without-new-105-rows policy locked
- [x] Slice 0 (D1/D7 docs) complete — see `docs/skills/`
- [x] Initial planning completed
- [x] Batch 2 skill enrichment baseline completed
- [x] Batch 2.1 defensible offline mappings completed
- [x] Batch 3 MITRE evidence status + SPL governance completed
- [x] Batch 3.1 pilot output contracts completed
- [x] Batch 4 pipeline trace + guarded answer visibility completed
- [x] Batch 5 lightweight backend session context completed
- [x] Batch 6 real Splunk MCP safety contract (docs only) completed
- [x] Batch 7 plan status review and gap audit completed

### Batch implementation status (Batches 1–6)

| Batch | Status | Merged/PR | Runtime Change | Key Outcome | Remaining Gap |
| ----- | ------ | --------- | -------------- | ----------- | ------------- |
| **1** — HIL mock MCP hardening | **Done** | PR #4 (`7222937`) | Yes | HIL labels + mock execution gates hardened | Durable approval store for real MCP |
| **2** — 7 SOC skill enrichment baseline | **Done** | PR #5 (`4e1a2f3`) | Metadata only | `content_enrichment.json` + intake register linked | Runtime enrichment load (C3) not wired |
| **2.1** — Offline question→use-case mapping | **Done** | PR #5 / `b164cb2` | Tooling | `question_use_case_map.json` + matrix generator | **1 / 105** authoritative mappings |
| **3** — MITRE evidence + SPL governance | **Done** | PR #6 (`9faac7c`) | Yes | Evidence-status vocabulary + template governance | Expand preconditions beyond pilots (A2 §P forward); O3 shim removed on this branch |
| **3.1** — Pilot output contracts | **Done** | PR #6 | Yes | Contract tests + `pilot_evidence_contracts_batch3_1.md` | More pilots need golden cases |
| **4** — Pipeline visibility + answer guard | **Done** | PR #6 | Yes | Top-level visibility + finalize-time `node_trace` + final validator | Incremental streaming trace; UI polish |
| **5** — Session context | **Done** | PR #7 (`84b77f8`) | Yes | Structured pins, TTL, follow-ups, `session_context_status` | In-process only; not multi-worker durable |
| **6** — Real Splunk MCP safety contract | **Done** | `d1a7b24` on `master` | **Docs only** | `real_splunk_mcp_safety_contract.md` — 15+ activation gates | COE adapter, audit, approval workflow |
| **7** — Plan status review | **Done** | This doc commit | Docs only | Gap audit + recommended next phase | Implementation of backlog items |

Full audit: [`docs/reviews/ai_soc_plan_status_review_after_batches_1_6.md`](../docs/reviews/ai_soc_plan_status_review_after_batches_1_6.md).

### Recent shipments (2026-06-27 — updated 2026-07-01)

| Work | Status | Reference |
|------|--------|-----------|
| PR #38 — T2 SPL-native / handoff stabilization | **Merged** (`master` @ `e5a4d40`) | `feat/llm-lab-direct-ask` |
| Post-PR #38 prod smoke — near-105 route + unsafe containment | **Merged** (`d04c083`, PR #40) | `fix/post-pr38-smoke-routing`; see consolidated handoff §Batch 0 |
| Operator-reviewed promotion writes + row-authority refresh | **Merged** (PR #39) | Batch 0 |
| Destructive containment paraphrase → unsafe | **Merged** (`809d3b6`, PR #50) | `query_signals.py` + `test_unsafe_action_paraphrase_lexicon.py`; aligns with P6/P7 no-destructive-containment policy |
| Full canonical handoff Phases 2–10 | **Shipped / Superseded** | [`2026-06-27_handoff-t2-completion-consolidated.md`](2026-06-27_handoff-t2-completion-consolidated.md) (`ca3249b`, PRs #40–#45); prior [`2026-06-26_full-canonical-handoff-t0-t1-t2-mcp.md`](2026-06-26_full-canonical-handoff-t0-t1-t2-mcp.md) `status: superseded` |


---

## A. Executive recommendation

Improve the AI SOC Assistant in **four coordinated tracks** without replacing the current architecture:

| Track | Purpose |
|-------|---------|
| **A — Existing System Hardening** | Safer HIL, evidence-based MITRE, SPL governance, session pins, answer guard |
| **B — Skill Content Enrichment** | Richer use-case metadata + RAG + MITRE KB, GitHub as **provenance only** |
| **C — LangGraph / Pipeline Nodes** | Clearer graph state, node split, traceability, additive response fields |
| **D — Skill Intake & Tracking** | Register, accept/reject/defer GitHub skills; link to use cases, MITRE, SPL, tests |

**Non-negotiables:**

- Keep the **4 live execution skills** (`alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall`).
- Keep **dual skill semantics**: `legacy_router_intent_hint` → live skill; `proposed_primary_skill` → planning/analytic intent.
- Do **not** load GitHub `SKILL.md` into runtime LLM prompts.
- Do **not** unify skill enums in phase 1.
- SPL remains **template-first + `validate_spl()`**; MCP remains **gated**; real Splunk MCP **deferred**.
- **`spl_generation`** stays a live execution skill for template/candidate SPL workflow only (not LLM-generated SPL). No P1–P7 pilot maps to it by design; pilots use `attack_discovery` / `knowledge_recall` / `alert_summary`.

**Recommended first implementation slice:** see **§L** (canonical order). Summary: D1/D7 → C1/C9 → A1 → B9/D5 → B1/P1–P7 → A2 → pipeline splits → A6 → A5.

---

## B. Updated four-track roadmap

```mermaid
flowchart TB
  subgraph TrackD [Track D - Intake and Tracking]
    D1[intake register]
    D2[rejection log]
    D3[pending backlog]
    D4[enrichment status matrix]
    D5[coverage matrix master]
    D6[decision workflow]
  end
  subgraph TrackA [Track A - Hardening]
    A1[HIL]
    A2[MITRE evidence status]
    A3[SPL governance]
    A4[MCP safety plan]
    A5[Session memory]
    A6[Answer guard]
  end
  subgraph TrackB [Track B - Enrichment]
    B1[content_enrichment schema]
    B7[answer rules]
    B9[coverage matrix]
    P1[P1-P7 pilots]
    B3[MITRE precondition wiring]
    B6[SPL templates]
  end
  subgraph TrackC [Track C - Pipeline]
    C1[Graph state]
    C2[Route vs planning skill]
    C3[Evidence plan]
    C4[SPL nodes]
    C5[MITRE node]
    C8[Answer nodes]
    C9[Trace]
  end
  D6 --> D1
  D1 --> B1
  D1 --> D4
  D4 --> D5
  B1 --> A2
  B6 --> A3
  B1 --> C3
  C1 --> C2
  A1 --> A4
  A2 --> A6
  B7 --> A6
  D5 --> B9
```

| Phase | Weeks (est.) | Tracks | Deliverable |
|-------|--------------|--------|-------------|
| 0 | 0 | Plan, **D** | This document; intake register schema; first-batch D7 entries |
| 0b | 0–1 | **D1–D4** | `github_skill_intake_register.json`, rejection log, backlog, status matrix (docs) |
| 1 | 1–2 | C1, C9, A1 | Explicit HIL; trace field plan |
| 2 | 2–3 | B9, B1, B4, B5, **D5** | Coverage matrix JSON; enrichment schema; intake ↔ matrix links |
| 3 | 3–5 | P1–P7, A2, B3, **D4** | Pilot enrichment (sidecar shipped); MITRE precondition wiring + `_status_for()` removal (B3/A2 partial); update D4 implementation status |
| 4 | 5–7 | C2–C5, C4, B6, A3 | Node split; templates active/planned |
| 5 | 7–9 | C8, A6, A5 | Guard + session pins |
| 6 | 10+ | A4 | COE Splunk MCP (if approved) |

---

## C. External GitHub SOC skill references inspected

### Repository details (local inspection snapshot)

```
Host path:     /tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
Remote:        https://github.com/mukul975/Anthropic-Cybersecurity-Skills.git
Commit SHA:    04450304b12645cb2b974ab96d28c0664758a88d
Commit date:   2026-06-01T10:15:47Z
Skills count:  754
```

**Top-level layout:**

| Path | Purpose |
|------|---------|
| `skills/<skill-id>/SKILL.md` | Primary skill document (YAML frontmatter + Markdown) |
| `skills/<skill-id>/references/` | Optional reference docs (do not import wholesale) |
| `skills/<skill-id>/scripts/` | **Do not execute** — offensive/tool scripts may exist |
| `skills/<skill-id>/assets/` | Optional assets |
| `index.json` | Skill index (auto-updated by repo) |
| `ATTACK_COVERAGE.md` | ATT&CK coverage summary |
| `mappings/` | Crosswalks including MITRE mappings |

**Standard skill format:** `skills/<name>/SKILL.md` — frontmatter fields commonly include `name`, `description`, `domain`, `subdomain`, `tags`, `mitre_attack`, `nist_csf`, `version`, `license`.

**Example local path (P1 reference):**

`/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills/skills/detecting-rdp-brute-force-attacks/SKILL.md`

### Mandatory reference skills (7)

| # | Skill | Path | Domain / subdomain | MITRE (frontmatter) | Defensive value for us |
|---|-------|------|-------------------|---------------------|------------------------|
| 1 | `detecting-rdp-brute-force-attacks` | `skills/detecting-rdp-brute-force-attacks/` | cybersecurity / threat-detection | T1021.001, T1110.001, T1110.003, T1078 | Failed-login correlation, threshold evidence, success-after-failure pivot |
| 2 | `triaging-security-alerts-in-splunk` | `skills/triaging-security-alerts-in-splunk/` | cybersecurity / soc-operations | T1078, T1566 | Notable triage, disposition, governed SPL patterns (reference only) |
| 3 | `analyzing-email-headers-for-phishing-investigation` | `skills/analyzing-email-headers-for-phishing-investigation/` | cybersecurity / digital-forensics | T1566.001, T1566.002, T1598.003 | SPF/DKIM/DMARC, header chain — **no forensic script execution** |
| 4 | `hunting-for-anomalous-powershell-execution` | `skills/hunting-for-anomalous-powershell-execution/` | cybersecurity / threat-hunting | T1046, T1057, T1003, … | Event 4104 patterns, encoded commands — map to log fields |
| 5 | `hunting-for-command-and-control-beaconing` | `skills/hunting-for-command-and-control-beaconing/` | cybersecurity / threat-hunting | T1071, … | Frequency/jitter, filter known-good, candidate C2 wording |
| 6 | `triaging-security-incident-with-ir-playbook` | `skills/triaging-security-incident-with-ir-playbook/` | cybersecurity / incident-response | T1486, T1070, T1078 | Severity/escalation **guidance only** — strip curl/TI auto-calls |
| 7 | `analyzing-ransomware-encryption-mechanisms` | `skills/analyzing-ransomware-encryption-mechanisms/` | cybersecurity / malware-analysis | T1486, T1573, T1027 | Impact evidence fields — **no reverse-engineering steps in product** |

### Optional enrichment candidates (lateral movement)

| Skill | Path | Notes |
|-------|------|-------|
| `detecting-lateral-movement-with-splunk` | `skills/detecting-lateral-movement-with-splunk/` | Maps to existing `edr_lateral_movement_candidate` use case |
| `detecting-pass-the-hash-attacks` | `skills/detecting-pass-the-hash-attacks/` | T1550.002 — high sensitivity; evidence-only |
| `hunting-for-dcom-lateral-movement` | `skills/hunting-for-dcom-lateral-movement/` | WMI/DCOM pivots — defensive hunt fields only |
| `detecting-rdp-brute-force-attacks` | (also T1021.001) | Remote services context |

### Defensive-conversion checklist (required for every GitHub-inspired enrichment)

1. Is it defensive SOC investigation guidance?
2. Is it evidence-based?
3. Is it compatible with SPL template governance?
4. Does it avoid offensive execution steps?
5. Does it avoid arbitrary shell/curl/tool execution?
6. Does it avoid unsupported MITRE claims?
7. Does it include limitations / not_claimed language?
8. Does it preserve HIL and validation gates?
9. Does it avoid importing long external markdown into runtime LLM context?
10. Does it separate reference/provenance from runtime authority?

---

## D. Current architecture constraints

> **Path convention:** Runtime code lives under `backend/app/`. Shared harness contracts live at repo root `contracts/`. Cite full paths below.

| Layer | Location | Constraint |
|-------|----------|------------|
| Live skill enum (4) | `contracts/skill_enum.py` | `SKILL_ENUM` — closed set; imported by `backend/app/routing/skills.py` |
| `validate_skill()` | `backend/app/routing/skills.py` | Validates against `SKILL_ENUM` |
| `plan_workflow()` | `backend/app/orchestration/workflow_planner.py` | Workflow skeleton per skill |
| MCP execution (2) | `backend/app/orchestration/mcp_tool_selector.py` | `attack_discovery`, `spl_generation` only — template/candidate SPL path; not LLM-generated SPL (see §Q2.4) |
| Skill catalog (18) | `backend/app/skills/catalog.json` | Governance; `mitre_mapping` collapsed in routing |
| Shadow/planning (~10) | `backend/app/routing/runtime_skill_catalog.py` | Route-plan shadow; mirrors to legacy when control plane on |
| Use cases | `backend/app/use_cases/catalog.json` | Templates, `mitre_registry`, routing patterns |
| 105 questions | `backend/app/coverage/question_runtime_map_v1.json` | `legacy_router_intent_hint` + `proposed_primary_skill` |
| MITRE KB | `backend/app/threat/mitre_attack_subset.json` | **98 techniques** (`curated-subset-v4`); **8** `curated_use_case_mappings` in metadata (includes pilot ids P3/P6/P7) |
| MITRE runtime | `backend/app/threat/mitre_kb.py`, `mitre_decision.py`, `mitre_evidence_preconditions.py` | Pilots: precondition resolver; non-pilot: fail-closed `requires_validation` (§O O3). Full A2 expansion → §P |
| Pipeline | `backend/app/chat/pipeline.py` | Imperative graph nodes; `ChatPipelineState` TypedDict |
| LangGraph | `backend/app/graph/chat_workflow.py` | Wrapper parity; `langgraph_orchestration_enabled=false` default |
| SPL | `backend/app/spl/templates.json`, stub generator, `llm_fallback` (disabled) | Template/stub-first |
| MCP gate | `backend/app/orchestration/mcp_execution_gate.py` | `evaluate_mcp_execution()`; mock HIL when `AI_SOC_REQUIRE_HIL_FOR_MOCK_EXECUTION=true` (Batch 1 + O2) |
| Memory | `ChatRequest.message` only | Frontend `ChatPanel` holds history client-side |
| Answer | `backend/app/chat/final_answer_validator.py`, `backend/app/answer_guard/` (flag off) | `backend/app/chat/contracts/answer_contract.py` |

**Dual skill semantics (must preserve):**

| Field | Meaning | Authority |
|-------|---------|-----------|
| `legacy_router_intent_hint` / `routed.skill` | **live_execution_skill** | Workflow, SPL, MCP gates |
| `proposed_primary_skill` | **planning_or_analytic_skill** | Evidence plan, enrichment, trace, golden shadow expectations |

---

## E. Track A — Existing System Hardening

### A1 — HIL hardening

**Objective:** Human review explicit across mock and real execution paths.

**Current issue:** `evaluate_mcp_execution()` returns `no_human_review()` after successful mock execution (`backend/app/orchestration/mcp_execution_gate.py`, symbol `no_human_review` — verify line at implementation time).

**Files:** `backend/app/orchestration/mcp_execution_gate.py`, `backend/app/orchestration/human_review.py`, `backend/app/config.py`, `backend/app/schemas/responses.py`, `backend/app/chat/pipeline.py`, `frontend/src/components/.../AnalystResponseCard.tsx`

**Target behavior:**

- Valid SPL ≠ autonomous execution.
- Mock success → explicit `execution_status_label=executed_mock_evidence` **or** `human_review.required=true` outside demo.
- Response shows: evidence source (mock/live/unavailable), execution status, analyst review requirement.

**Proposed config flag:**

```env
AI_SOC_REQUIRE_HIL_FOR_MOCK_EXECUTION=true
```

(Pattern matches existing `AI_SOC_*` / `MCP_*` style in `backend/app/config.py` and `.env.example`.)

**Demo / EC path (§Q2.1):** Experience Center returns canned responses at `backend/app/api/routes_chat.py` (`ai_soc_live_chat_ec_parity_enabled` + `run_demo_scenario`) **before** the live pipeline reaches the MCP gate. Do **not** add `AI_SOC_ALLOW_MOCK_EXECUTION_WITHOUT_HIL_IN_DEMO` unless a live-path demo predicate is defined. Precedence when implemented: `REQUIRE_HIL_FOR_MOCK` applies to any path that reaches `evaluate_mcp_execution()`; EC fixture path is out of scope.

**Tests:**

| Case | Expected |
|------|----------|
| Valid SPL + mock MCP + live path | `human_review.required=true` (or explicit mock-executed label + review) |
| Valid SPL + EC fixture path | No MCP gate invocation; canned response only |
| Invalid SPL | `review_type=spl_revision` |
| Real MCP / not implemented | `admin_action_required` |

---

### A2 — MITRE evidence-status hardening

**Objective:** Route MITRE status through `mitre_decision.resolve_mitre_decision` + `mitre_evidence_preconditions` (shipped 2026-06-04). Do **not** invent a parallel status mechanism; extend `TechniquePrecondition` rows for pilot techniques.

**§O O3 (done, 2026-07-01):** Removed legacy `_status_for()` / `_legacy_evidence_status_for()` from `mitre_kb.py`; pilots use `evaluate_pilot_mitre_evidence_status`; non-pilot mappings fail closed to `requires_validation`. **§P forward:** B3/B4 expand preconditions to all use cases; C5 dedicated MITRE node.

**Files:** `backend/app/threat/mitre_kb.py`, `mitre_decision.py`, `mitre_evidence_preconditions.py`, `mitre_attack_subset.json`, `use_cases/catalog.json`, `question_runtime_map_v1.json`

**Authoring rule (§Q1.1/Q1.2):** Enrichment authors (`content_enrichment.json`) **`technique_id` + `required_evidence` (+ thresholds)** only. Status strings are **emitted at runtime** in the vocabulary below — never stored in enrichment records or `catalog.json`.

**Target status vocabulary (runtime output only):**

| Status | Meaning |
|--------|---------|
| `candidate` | Registry-permitted; insufficient evidence to strengthen |
| `evidence_supported` | Required positive evidence present per preconditions |
| `requires_validation` | Partial signals; analyst review needed |
| `not_claimed` | Evidence precondition failed or technique blocked |
| `ruled_out` | Explicit negative evidence contradicts technique |

**Rules:**

- No “confirmed MITRE” in analyst-facing text without `evidence_supported` + policy allow.
- Success-after-failure: T1110.001 → `evidence_supported` when failure threshold met; T1078 → `candidate` unless account-abuse evidence.
- Status from **structured evidence**, not query text alone.

**Pilot MITRE expansion (not full ATT&CK):**

`T1110`, `T1110.001`, `T1110.003`, `T1078`, `T1059`, `T1059.001`, `T1566`, `T1566.001`, `T1566.002`, `T1071` (+ sub-techniques only when evidence supports), `T1486`, optional `T1490`, `T1021` (lateral pilot)

**Compatibility mapping (locked):** Target statuses (`evidence_supported`, `ruled_out`, `requires_validation`, etc.) are for the improved evidence-status layer. **Do not** blindly replace the current `mitre_decision.py` output schema. Implement A2 as:

| Layer | Behavior |
|-------|----------|
| **Current** | Mostly `candidate` + `not_claimed` lists on `MitreDecision` |
| **Target** | Evidence-precondition-driven status vocabulary (table above) |
| **Transition** | Preserve existing response fields; add richer status **additively** (internal trace / new optional fields) via a compatibility-aware mapping layer |

A2 = reconciliation + additive hardening, **not** a breaking schema replacement.

**Tests:** Per pilot P1–P7 MITRE scenarios (§O O3 verified). Regression: `rg '_status_for\\(' backend/app/threat/mitre_kb.py` returns zero.

---

### A3 — SPL template governance

**Objective:** Template-first; LLM fallback cannot bypass policy.

**Files:** `spl/templates.json`, `spl/generator.py`, `spl/llm_fallback.py`, `splunk/spl_services.py`, `safeguards/spl_validator.py`, `chat/pipeline.py` (`_candidate_spl_stage`)

**Rules:**

- Each enriched use case declares `allowed_spl_templates` + status (`active`/`planned`/`unavailable`).
- No template → governed limitation message (not silent stub).
- `AI_SOC_LLM_SPL_FALLBACK_ENABLED=false` outside lab.
- Lab fallback: template-family approval + `validate_spl()` + HIL.

**Tests:** Template pass/fail; fallback disabled; fallback SPL cannot execute without approval.

---

### A4 — Splunk MCP execution safety — **Done (Batch 6 planning contract)**

**Objective:** Document COE requirements; defer implementation.

**Files:** `connectors/mcp/splunk_mcp.py`, `mcp_execution_gate.py`, `splunk_result_adapter.py`, `splunk/capabilities.py`

**Contract:** `docs/architecture/real_splunk_mcp_safety_contract.md`

**COE checklist (document only):** server URL, auth, allowed tools (read-only search), timeouts, result caps, audit trail, approval workflow, air-gap policy.

**Batch 6 result:** Real Splunk MCP remains disabled/not implemented. The contract requires `validate_spl()` approval, active allowed template, read-only SPL, HIL approval bound to normalized SPL hash/trace, global + per-server execution flags, allowlisted `spl_search` tool, confirmed real result schema, and audit readiness before live execution.

---

### A5 — Lightweight backend session memory — **Done (Batch 5)**

**Objective:** SOC follow-ups without full chat history storage.

**Files:** `backend/app/schemas/requests.py`, `backend/app/schemas/responses.py`, `backend/app/chat/session_store.py`, `backend/app/chat/session_context.py`, `backend/app/chat/pipeline.py`, `backend/app/chat/pipeline_visibility.py`, `frontend/src/api/client.ts`, `frontend/src/components/ChatPanel.tsx`, `frontend/src/lib/chatProgressStream.ts`

**Request:** optional `session_id` on `ChatRequest`.

**Response:** additive `session_context_status` (`used_previous_context`, `staleness`, `used_fields`, `clarification_required`).

**Server session store (structured pins only, TTL default 30 min, no transcript):**

- `last_trace_id`, `last_alert_id`, `last_use_case_id`, `last_selected_live_execution_skill`, `last_planning_or_analytic_skill`
- `last_entities`, `last_candidate_spl`, `last_spl_validation_status`, `last_spl_template_status`
- `last_mitre_decision`, `last_mitre_evidence_status`, `last_context_sufficiency`, `last_execution_status`, `last_human_review_status`

**Follow-ups supported:** “now map it to MITRE”, “refine that SPL”, “same alert”, “show evidence”, “severity?”, “analyst summary”

**Safety:** Fresh pins only; stale/missing context triggers clarification; SPL refine re-runs `validate_spl()`; MITRE/HIL/SPL gates re-run each turn; `node_trace` includes `session_context` stage.

**Tests:** `backend/app/tests/test_batch5_session_context.py`

**Stacked PR:** `feat/ai-soc-session-context` targets PR #6 head (`feat/ai-soc-mitre-spl-governance`), not mixed into PR #6.

---

### A6 — Answer guard / final response hardening

**Objective:** Reduce overclaiming in governed summaries.

**Files:** `backend/app/answer_guard/runner.py`, `backend/app/answer_guard/rules.py`, `backend/app/chat/final_answer_validator.py`, `backend/app/chat/contracts/answer_contract.py`, `backend/app/chat/pipeline.py`, `backend/app/config.py`

**Rules:** Enable guard in lab/demo first; separate facts / assumptions / candidate MITRE / evidence_supported MITRE / limitations / HIL / SPL review status.

**Tests:** Block unsupported compromise; block confirmed MITRE without evidence; allow candidate wording with limitations.

---

## F. Track B — Skill Content Enrichment

### B1 — Content enrichment schema

**Shipped location (Batch 2, PR #5):** Pilot enrichment lives in **`backend/app/use_cases/content_enrichment.json`** — a sidecar keyed by `use_case_id`, loaded by `load_skill_enrichment(use_case_id)` without changing routing. `use_cases/catalog.json` owns routing (`mitre_registry`, `default_spl_template`, `primary_skill`, patterns); it has **no** inline `content_enrichment` blocks (0 occurrences by design).

**Why sidecar (not in-catalog):**

- Keeps the routing catalog stable while enrichment grows (7 pilot records shipped; P3/P6/P7 **catalog routing rows** deferred per B8).
- Use cases already own `mitre_registry`, `default_spl_template`, `primary_skill`, RAG collections in `catalog.json`.
- `skills/catalog.json` stays execution-governance (18 skills); no duplicate authority.

**Schema:**

```json
{
  "content_enrichment": {
    "domain": "identity-access-management",
    "subdomain": "authentication-security",
    "tags": ["brute-force", "windows-auth", "splunk", "mitre-attack"],
    "github_reference_skills": [
      {
        "repo": "mukul975/Anthropic-Cybersecurity-Skills",
        "path": "skills/detecting-rdp-brute-force-attacks/SKILL.md",
        "usage": "defensive workflow reference only"
      }
    ],
    "planning_or_analytic_skill": "threshold_anomaly",
    "mitre_candidates": [
      {
        "technique_id": "T1110.001",
        "required_evidence": ["failed_login_count", "user", "src", "time_window"]
      }
    ],
    "evidence_requirements": {
      "required": ["user", "src", "host", "fail_count", "time_window"],
      "optional": ["first_failure", "last_failure"],
      "thresholds": {"fail_count_gte": 25}
    },
    "investigation_workflow": [
      {"step": 1, "action": "confirm_scope"},
      {"step": 2, "action": "select_governed_spl_template"},
      {"step": 3, "action": "validate_spl"},
      {"step": 4, "action": "evaluate_mitre_evidence_status"},
      {"step": 5, "action": "decide_severity"},
      {"step": 6, "action": "produce_summary_with_limitations"},
      {"step": 7, "action": "hil_if_execution_or_insufficient_evidence"}
    ],
    "analyst_checklist": [],
    "allowed_spl_templates": [
      {"template_id": "auth_failed_login_spike", "status": "active"}
    ],
    "answer_rules": [],
    "limitations": [],
    "rag_doc_ids": ["SOC-SOP-AUTH-001"]
  }
}
```

Add optional Pydantic model: `UseCaseContentEnrichment` in `backend/app/use_cases/models.py` (implementation phase).

**MITRE in enrichment:** No `not_claimed_defaults`, `status_default`, or free-form status strings. Not-claimed behavior comes from `mitre_evidence_preconditions.py` when required evidence is absent. New pilot techniques → add `TechniquePrecondition` rows, not catalog strings.

---

### B2 — Domain / subdomain taxonomy

| Domain | Subdomains (examples) |
|--------|----------------------|
| `soc-operations` | alert-triage, incident-triage, analyst-workflow |
| `identity-access-management` | authentication-security, account-abuse |
| `endpoint-security` | edr-hunting, suspicious-command-execution |
| `threat-hunting` | beaconing-review, pattern-anomaly |
| `phishing-defense` | email-header-analysis |
| `network-security` | dns-analysis, firewall-correlation |
| `incident-response` | containment-guidance, escalation |
| `ransomware-defense` | impact-assessment |

Map from GitHub `domain`/`subdomain` but use our catalog `category` as secondary label.

---

### B3 — MITRE precondition wiring (technique corpus shipped)

**Current tree:** `mitre_attack_subset.json` carries **98 techniques** (`curated-subset-v4`) with **8** `curated_use_case_mappings` (includes P3/P6/P7 ids). Pilot anchor techniques (T1059.001, T1566*, T1071, T1486, etc.) are **already present** — bulk import is closed.

**Remaining work:** extend `mitre_evidence_preconditions.py` for pilot-specific rows; remove `_status_for()` call site in `mitre_kb.py` (pairs with **A2**). Sync `mitre_registry` keys where catalog rows exist.

Do **not** claim full ATT&CK coverage. Document version in subset metadata (`curated-subset-v4`), not a separate pilot-only file.

---

### B4 — Evidence requirements

Per enriched skill: required fields, optional fields, thresholds, missing-evidence behavior, allowed conclusions, prohibited conclusions.

See pilot records (section H) for field lists per domain.

---

### B5 — Investigation workflows

Short ordered steps (8 max) in `content_enrichment.investigation_workflow` — no long prose. Long SOP text → RAG (`soc_kb_entries.json`).

---

### B6 — SPL template activation

Per use case: `allowed_spl_templates[]` with `status`: `active` | `planned` | `unavailable`, plus `required_slots`, `validation_policy`, `execution_mode`: `review_only` | `gated_read`.

Current gaps:

- `dns_beaconing_candidate` — `planned`, `spl_text: null`
- `edr_powershell_suspicious_command` — no template
- `edr_lateral_movement_candidate` — no template

---

### B7 — Analyst answer rules

Per use case in `content_enrichment.answer_rules`:

- MITRE candidate vs evidence_supported phrasing
- Limitations and not_claimed defaults
- When to ask for alert context
- When HIL required
- SPL always review-only unless explicit COE + flags

---

### B8 — 105-question compatibility

**Do not overwrite `proposed_primary_skill`.**

Coverage matrix columns:

- `question_id`, `query`, `use_case_id`
- `live_execution_skill` (from `legacy_router_intent_hint`)
- `planning_or_analytic_skill` (from `proposed_primary_skill`)
- `enriched_skill_available`, `mitre_candidates`, `spl_template_status`, `evidence_requirements`, `github_reference_skill_path`, `test_coverage_status`

Golden tests may continue to assert `planning_or_analytic_skill` in shadow fields while live `selected_skill` stays on 4-skill enum.

**New use cases (P3/P6/P7) — locked:** Phishing (`email_phishing_header_review`), IR playbook (`soc_incident_triage`), and ransomware (`endpoint_ransomware_impact_review`) **do not require new 105-question rows immediately**. Ship enrichment by mapping to:

1. Existing 105 questions when a matching row exists
2. Existing catalog use cases when close enough
3. Planned/proposed use case ids when no exact runtime path exists yet

New `question_id` rows and new routable catalog entries may follow later. **Preserve:** 4 live skills, `legacy_router_intent_hint`, `proposed_primary_skill`. Enrichment and Track D status tracking are additive — no runtime routing break.

---

### B9 — Skill coverage matrix (P0)

**Path:** `docs/evals/skill_coverage_matrix.json`

**Generator (implementation phase):** script merging `backend/app/coverage/question_runtime_map_v1.json` + `use_cases/catalog.json` + enrichment status.

**CI:** **Monotonic** on `question_id` set — ≥ 105 rows, **no existing `question_id` dropped**. Corpus = 105-question runtime map (not the separate 46-case answer-quality expectation matrix in `docs/evals/`).

---

## G. Track C — LangGraph / Pipeline Node Improvement

**Current state:**

- Imperative path: `build_live_chat_response()` in `pipeline.py` calls nodes sequentially.
- LangGraph path: `graph/chat_workflow.py` wraps **same functions** when `langgraph_orchestration_enabled=true`.
- `ChatPipelineState` TypedDict (~30 keys) in `pipeline.py`; `graph/state.py` has separate stub `InvestigationState` (unused by chat).

### C1 — Graph state model

**Propose `ChatPipelineState` v2 (additive fields):**

| Field | Purpose |
|-------|---------|
| `session_id` | Session memory key |
| `session_pins` | Structured prior-turn pins |
| `live_execution_skill` | Mirror of `routed.skill` (explicit name) |
| `planning_or_analytic_skill` | From 105 map / enrichment |
| `skill_enrichment` | Loaded `content_enrichment` block |
| `spl_template_status` | active/planned/unavailable |
| `mitre_evidence_status` | Aggregated status map per technique |
| `execution_decision` | Gate outcome before envelope |
| `answer_guard_result` | Guard output |
| `final_answer_validation` | Validator output |
| `node_trace` | List of per-node trace records |

**Rule:** Session pins inform planning only; every gate re-runs.

---

### C2 — Separate routing and enrichment nodes

**Proposed split (implementation refactors existing logic, does not change authority):**

| Node | Function | Responsibility |
|------|----------|----------------|
| `graph_node_route_live_skill` | refactor from `init_routing` tail | Select 1 of 4 live skills via `route_skill()` |
| `graph_node_resolve_planning_skill` | new | Resolve `proposed_primary_skill` from QU / 105 map / use case |
| `graph_node_load_skill_enrichment` | new | Load local `content_enrichment` by `use_case_id`; **never** read GitHub markdown |

Keep `graph_node_init_routing` as orchestrator or deprecate gradually behind flag `PIPELINE_SPLIT_ROUTING_NODES` — defaults **`false`** (monolith path) until LangGraph/imperative parity tests pass, then flip to `true`.

---

### C3 — Evidence planning node

**Formalize `graph_node_build_evidence_plan`** (extends `graph_node_evidence_planning`):

**Inputs:** use_case, planning skill, `content_enrichment`, session pins
**Outputs:** required/optional/missing evidence, SPL template candidates, RAG doc candidates, MITRE candidates, `hil_required_if_missing`

Uses existing `chat/evidence_planner.py` + enrichment fields.

---

### C4 — SPL planning and validation nodes

| Node | Responsibility |
|------|----------------|
| `graph_node_select_spl_template` | Pick allowed template; return planned/unavailable |
| `graph_node_bind_spl_slots` | Bind alert_id, host, user, time_window (`validate_spl_slot_bindings`) |
| `graph_node_validate_spl` | Mandatory `validate_spl()` |
| `graph_node_prepare_execution_decision` | `evaluate_mcp_execution()` + HIL rules |

Today combined in `graph_node_workflow_spl` + `graph_node_execution`.

---

### C5 — MITRE decision node

**`graph_node_resolve_mitre_evidence_status`** (extract from `graph_node_context_finalize` / `_mitre_outputs_for_finalize`):

**Inputs:** enrichment MITRE candidates, `structured_context`, preconditions, sufficiency
**Outputs:** per-technique status in vocabulary §A2

---

### C6 — Severity decision node

**`graph_node_decide_severity`** — formalize existing `decide_severity()` call:

**Inputs:** `severity_policy`, metrics, sufficiency — **not** raw MITRE alone
**Rule:** Insufficient evidence → conservative / review-required severity

---

### C7 — RAG/SOP node

**`graph_node_retrieve_sop_context`** — formalize `graph_node_rag_early`:

**Inputs:** `rag_doc_ids` from enrichment, query intent
**Outputs:** SOP snippets, escalation guidance, limitations
**Rule:** RAG = reference prose; skills = workflow metadata; deterministic rules decide execution.

---

### C8 — Synthesis and answer guard nodes

| Node | Existing analogue |
|------|-------------------|
| `graph_node_build_answer_contract` | `build_answer_contract()` in finalize |
| `graph_node_generate_governed_summary` | `run_governed_synthesis_lab` |
| `graph_node_run_answer_guard` | `run_answer_guard_lab` |
| `graph_node_validate_final_answer` | `validate_final_answer()` |
| `graph_node_build_response_envelope` | `PlaceholderResponse` assembly |

---

### C9 — Observability / trace

Each node emits:

```json
{
  "node_name": "graph_node_validate_spl",
  "input_summary": {"template_id": "auth_failed_login_spike"},
  "output_summary": {"approved": true},
  "decision_reason": "deterministic policy pass",
  "guardrail_status": "pass",
  "human_review_required": false
}
```

Append to `control_plane_trace` / new `node_trace` on response.

**Tests:** Unit tests per node with fixture state; LangGraph parity test (`test_langgraph_parity`).

---

### C10 — Backward compatibility

**Keep existing `PlaceholderResponse` fields.** Additive only:

- `selected_live_execution_skill` (alias of `selected_skill` initially)
- `planning_or_analytic_skill`
- `skill_enrichment` (redacted safe subset in API)
- `evidence_plan` (already partial)
- `mitre_evidence_status`
- `spl_template_status`
- `session_context_status`

Frontend: continue using `trace: response` in `ChatPanel.tsx`; surface new fields in technical trace first.

---

## H. Track D — Skill Intake, Review, Rejection, and Implementation Tracking

**Objective:** Structured tracking for every GitHub skill inspected — what was reviewed, accepted, rejected, deferred, implemented, and tested — so enrichment stays governed and auditable.

**Principle:** GitHub repo at `/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills` is **never** runtime authority. Track D files are **documentation and governance only** (no runtime skill loading, no prompt import).

### D1 — GitHub skill intake register

**Primary file (recommended):** `docs/skills/github_skill_intake_register.json`

**Bootstrap alternative:** `docs/skills/github_skill_intake_register.md` if JSON tooling is not ready — migrate to JSON in phase 0b.

**Schema per record:**

```json
{
  "github_skill_id": "detecting-rdp-brute-force-attacks",
  "repo": "mukul975/Anthropic-Cybersecurity-Skills",
  "path": "skills/detecting-rdp-brute-force-attacks/SKILL.md",
  "local_clone_path": "/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills/skills/detecting-rdp-brute-force-attacks/SKILL.md",
  "repo_commit": "04450304b12645cb2b974ab96d28c0664758a88d",
  "domain": "soc-operations",
  "subdomain": "authentication-security",
  "mitre_from_github": ["T1110.001", "T1110.003", "T1078", "T1021.001"],
  "review_status": "accepted_for_enrichment",
  "decision": "accept",
  "decision_reason": "Useful defensive brute-force workflow; offensive parts not imported.",
  "internal_use_cases": ["auth_failed_login_spike", "auth_success_after_failure"],
  "mapped_live_execution_skill": "attack_discovery",
  "mapped_planning_or_analytic_skill": "threshold_anomaly",
  "reuse_type": "workflow_reference",
  "safety_review": {
    "defensive_only": true,
    "offensive_steps_removed": true,
    "no_arbitrary_commands": true,
    "no_runtime_markdown_loading": true,
    "no_direct_tool_execution": true
  },
  "implementation_status": {
    "content_enrichment_added": false,
    "mitre_kb_updated": false,
    "evidence_requirements_added": false,
    "spl_template_bound": false,
    "rag_doc_added": false,
    "answer_rules_added": false,
    "tests_added": false
  },
  "priority": "P0",
  "owner": "TBD",
  "reviewed_date": "2026-06-06",
  "notes": ""
}
```

**`review_status` values:** `not_reviewed` | `review_in_progress` | `accepted_for_enrichment` | `deferred` | `rejected` | `implemented` | `tested`

**`decision` values:** `accept` | `reject` | `defer` | `needs_review`

**`reuse_type` values:** `workflow_reference` | `mitre_reference` | `evidence_reference` | `sop_reference` | `rejected`

---

### D2 — Rejection log

**File:** `docs/skills/rejected_github_skills.md`

Every rejected skill gets a row so it is not re-reviewed without cause.

| GitHub Skill | Path | Decision | Rejection Reason | Safety Concern | Future Revisit? | Notes |
| ------------ | ---- | -------- | ---------------- | -------------- | --------------- | ----- |

**Rejection reason codes:**

| Code | Meaning |
|------|---------|
| `offensive_only` | Primary purpose is attack/offense, not defensive investigation |
| `unsafe_execution_steps` | Requires steps unsafe for governed assistant |
| `arbitrary_shell_or_curl` | Depends on arbitrary shell/curl/API execution at runtime |
| `not_relevant_to_soc_assistant` | Outside SOC analyst assistant scope |
| `duplicate_of_existing_skill` | Redundant with accepted skill or internal use case |
| `too_tool_specific` | Tied to unavailable vendor/tool we do not support |
| `too_token_heavy` | Body too large to curate into bounded enrichment |
| `requires_unavailable_data_source` | Needs telemetry we do not model |
| `no_clear_evidence_model` | Cannot map to evidence fields / preconditions |
| `not_suitable_for_client_demo` | Unsafe or inappropriate for experience center |
| `future_phase` | Valid later; not current pilot scope |

**D8 — Rejection examples (policy):**

```text
Rejected:
- Any skill whose primary purpose is exploit execution, credential theft,
  persistence creation, malware deployment, C2 setup, or evasion.
- Any skill that requires arbitrary shell execution in runtime.
- Any skill that cannot be converted into defensive investigation guidance.
```

**Partial accept:** Skills like `analyzing-ransomware-encryption-mechanisms` may be **accepted for enrichment** with `reuse_type=evidence_reference` while specific body sections (Ghidra RE, decryptor tooling) are logged in rejection notes as `offensive_only` / `unsafe_execution_steps` — not imported.

---

### D3 — Pending skill enrichment backlog

**File:** `docs/skills/pending_skill_enrichment_backlog.md`

| Backlog ID | GitHub Skill / Topic | SOC Domain | Internal Use Case Candidate | MITRE Candidate | Priority | Dependency | Status |
| ---------- | -------------------- | ---------- | --------------------------- | --------------- | -------- | ---------- | ------ |

**Status values:** `not_reviewed` | `review_in_progress` | `accepted_for_enrichment` | `deferred` | `blocked` | `implemented` | `tested` | `rejected`

**Seed backlog entries (optional pilots beyond batch 1):**

| Backlog ID | GitHub Skill | Use Case Candidate | Priority | Status |
|------------|--------------|-------------------|----------|--------|
| BL-001 | `detecting-lateral-movement-with-splunk` | `edr_lateral_movement_candidate` | P2 | `deferred` |
| BL-002 | `detecting-pass-the-hash-attacks` | `edr_lateral_movement_candidate` | P3 | `not_reviewed` |
| BL-003 | `hunting-for-dcom-lateral-movement` | `edr_lateral_movement_candidate` | P3 | `not_reviewed` |

---

### D4 — Implementation status matrix

**File:** `docs/skills/skill_enrichment_status_matrix.md`

Tracks **internal use case** implementation progress (one row per use case; may reference multiple GitHub skills).

| Internal Use Case | GitHub Reference | Live Skill | Planning Skill | MITRE Added | Evidence Added | SPL Template | Workflow Added | Answer Rules | RAG Added | Tests Added | Status |
| ----------------- | ---------------- | ---------- | -------------- | ----------- | -------------- | ------------ | -------------- | ------------ | --------- | ----------- | ------ |

**Status values:** `not_started` | `designed` | `content_added` | `mitre_added` | `spl_bound` | `tests_added` | `accepted` | `blocked`

---

### D5 — Coverage matrix remains master control

**Central file:** `docs/evals/skill_coverage_matrix.json`

Answers: *“Are we improving coverage or just adding content randomly?”*

**Each row connects:**

| Column | Source |
|--------|--------|
| `question_id` | `coverage/question_runtime_map_v1.json` |
| `use_case_id` | `use_cases/catalog.json` |
| `live_execution_skill` | `legacy_router_intent_hint` |
| `planning_or_analytic_skill` | `proposed_primary_skill` |
| `github_reference_skill` | `github_skill_intake_register.json` → `github_skill_id` |
| `github_intake_decision` | Track D `decision` |
| `mitre_candidates` | enrichment + KB |
| `evidence_requirements` | `content_enrichment` |
| `spl_template_status` | `active` / `planned` / `unavailable` |
| `implementation_status` | D4 status |
| `test_status` | pytest / golden / harness |

**Hierarchy:**

```
github_skill_intake_register.json  (what we reviewed about GitHub)
        ↓ maps to
skill_enrichment_status_matrix.md  (use-case implementation progress)
        ↓ rolls up into
skill_coverage_matrix.json         (105-question coverage truth)
```

---

### D6 — Decision workflow for every GitHub skill

```mermaid
flowchart LR
  inspect[1 Inspect SKILL.md locally] --> register[2 Record in intake register]
  register --> checklist[3 Defensive-conversion checklist]
  checklist --> decide{4 Decision}
  decide -->|reject| rej[5a rejected_github_skills.md]
  decide -->|defer| backlog[5b pending backlog]
  decide -->|accept| map[6 Map use case skills MITRE evidence SPL]
  map --> status[7 skill_enrichment_status_matrix.md]
  status --> coverage[8 skill_coverage_matrix.json]
  coverage --> tests[9 Tests after implementation only]
```

1. Inspect GitHub `SKILL.md` at local clone path (never execute `scripts/`).
2. Record in `github_skill_intake_register.json` with `repo_commit`.
3. Apply defensive-conversion checklist (§C).
4. Decide: `accept` | `reject` | `defer` | `needs_review`.
5. If rejected → `rejected_github_skills.md`. If deferred → `pending_skill_enrichment_backlog.md`.
6. If accepted → map to internal use case, live skill, planning skill, MITRE, evidence, SPL status.
7. Update `skill_enrichment_status_matrix.md`.
8. Update `skill_coverage_matrix.json` rows for affected questions.
9. Add tests **only after** enrichment is implemented in Track B.

---

### D7 — First batch tracking (7 mandatory GitHub skills)

**Slice 0 (2026-06-06):** Batch-1 **seven mandatory skills** recorded in [`docs/skills/github_skill_intake_register.json`](../docs/skills/github_skill_intake_register.json) (**12 records** total as of later intake growth). Summary table below covers the mandatory seven; `implementation_status` flags remain `false` until Track B runtime wiring (C3).

Planning-time status for batch 1:

| GitHub Skill ID | Decision | Review Status | Internal Use Case(s) | Live Skill | Planning Skill | MITRE (curated) | Evidence Model | SPL Template | Safety Notes | Impl. Status |
|-----------------|----------|---------------|----------------------|------------|----------------|-----------------|----------------|--------------|--------------|--------------|
| `detecting-rdp-brute-force-attacks` | **accept** | `accepted_for_enrichment` | `auth_failed_login_spike`, `auth_success_after_failure` | `attack_discovery` | `threshold_anomaly` / `sequence_detection` | T1110, T1110.001, T1110.003, T1078 (candidate) | **designed** in plan §I P1/P2 | `auth_failed_login_spike` active; `auth_success_after_failure` active | Defensive log correlation only; no blocking scripts | `not_started` |
| `triaging-security-alerts-in-splunk` | **accept** | `accepted_for_enrichment` | Cross-cutting: P1, P2, P6 + all Splunk use cases | varies | `alert_triage` (proposed shadow name) | Context-dependent | **designed** — triage/disposition fields | N/A (SOP/workflow) | Splunk UI steps → governed SPL references only | `not_started` |
| `analyzing-email-headers-for-phishing-investigation` | **accept** | `accepted_for_enrichment` | `email_phishing_header_review` (**proposed**) | `attack_discovery` or `knowledge_recall` | `phishing_triage` | T1566, T1566.001, T1566.002 | **designed** §I P3 | `planned` | No forensic script execution; header fields only | `not_started` |
| `hunting-for-anomalous-powershell-execution` | **accept** | `accepted_for_enrichment` | `edr_powershell_suspicious_command` | `attack_discovery` | `suspicious_command_execution` | T1059, T1059.001 | **designed** §I P4 | `planned` | Map to Event 4104 fields; no malware verdict without evidence | `not_started` |
| `hunting-for-command-and-control-beaconing` | **accept** | `accepted_for_enrichment` | `dns_beaconing_candidate` | `attack_discovery` | `beaconing_pattern_review` | T1071 (+ sub if evidenced) | **designed** §I P5 | `planned` | Periodicity alone ≠ C2 confirmed | `not_started` |
| `triaging-security-incident-with-ir-playbook` | **accept** | `accepted_for_enrichment` | `soc_incident_triage` (**proposed**) | `alert_summary` / `knowledge_recall` | `incident_triage_playbook` | Per alert evidence only | **designed** §I P6 | N/A | Strip curl/TI auto-calls; no destructive containment | `not_started` |
| `analyzing-ransomware-encryption-mechanisms` | **accept** (partial) | `accepted_for_enrichment` | `endpoint_ransomware_impact_review` (**proposed**) | `attack_discovery` | `ransomware_impact_review` | T1486; optional T1490/T1489 | **designed** §I P7 | `planned` | **Reject** RE/decryptor sections (`offensive_only`); impact evidence only | `not_started` |

**Reuse type summary:**

| Skill | `reuse_type` |
|-------|----------------|
| detecting-rdp-brute-force-attacks | `workflow_reference` + `evidence_reference` |
| triaging-security-alerts-in-splunk | `sop_reference` + `workflow_reference` |
| analyzing-email-headers-for-phishing-investigation | `evidence_reference` + `workflow_reference` |
| hunting-for-anomalous-powershell-execution | `evidence_reference` + `mitre_reference` |
| hunting-for-command-and-control-beaconing | `evidence_reference` + `workflow_reference` |
| triaging-security-incident-with-ir-playbook | `sop_reference` |
| analyzing-ransomware-encryption-mechanisms | `evidence_reference` (partial; malware-analysis sections rejected) |

---

### How Track D connects to Track B and the 105-question matrix

| Track D artifact | Feeds | Consumed by |
|------------------|-------|-------------|
| `github_skill_intake_register.json` | Provenance + accept/reject decision | `content_enrichment.github_reference_skills[]` in Track B |
| `skill_enrichment_status_matrix.md` | Per use-case build status | PR checklist; pilot P1–P7 |
| `pending_skill_enrichment_backlog.md` | Future candidates | Quarterly enrichment planning |
| `rejected_github_skills.md` | Avoid rework | Security review; onboarding |
| `skill_coverage_matrix.json` | 105-question truth | Golden tests; governance regression; “are we improving coverage?” |

**Track B** implements accepted skills into **`content_enrichment.json`** records (keyed by `use_case_id`). Catalog routing rows in `use_cases/catalog.json` are updated separately when a pilot needs a new routable `use_case_id` (P3/P6/P7 catalog rows deferred per B8).
**Track D** never writes to runtime — it records decisions and links GitHub `github_skill_id` → `use_case_id` → `question_id`.
When a pilot moves to `content_added`, update D4 row, D1 `implementation_status`, and B9 matrix `implementation_status` / `test_status` together.

---

## I. Seven pilot enriched SOC skill records

### P1 — Failed login / brute force

```yaml
use_case_id: auth_failed_login_spike
domain: identity-access-management
subdomain: authentication-security
live_execution_skill: attack_discovery
planning_or_analytic_skill: threshold_anomaly
github_reference_skills:
  - skills/detecting-rdp-brute-force-attacks/SKILL.md
  - skills/triaging-security-alerts-in-splunk/SKILL.md
mitre_candidates:
  - {technique_id: T1110, required_evidence: [failed_login_count, user, src, time_window]}
  - {technique_id: T1110.001, required_evidence: [failed_login_count, user, src, time_window], thresholds: {fail_count_gte: 25}}
  - {technique_id: T1110.003, required_evidence: [failed_login_count, distinct_user_gte]}
  - {technique_id: T1078, required_evidence: [successful_login]}
# runtime status via mitre_evidence_preconditions — not authored here
evidence_required: [user, src, host, fail_count, time_window, first_failure, last_failure]
allowed_spl_templates:
  - {id: auth_failed_login_spike, status: active}
answer_rules:
  - Do not claim account compromise from failures alone
  - Brute force evidence_supported only if threshold met
  - execution_eligible=false; HIL before any execution
limitations:
  - Failed logins alone do not prove Valid Accounts
```

### P2 — Successful login after failures

```yaml
use_case_id: auth_success_after_failure
live_execution_skill: attack_discovery
planning_or_analytic_skill: sequence_detection  # or correlate_sequence if added to shadow catalog
github_reference_skills:
  - skills/detecting-rdp-brute-force-attacks/SKILL.md
  - skills/triaging-security-alerts-in-splunk/SKILL.md
mitre_candidates:
  - {technique_id: T1110.001, required_evidence: [failed_login_count, success_count, user, src]}
  - {technique_id: T1078, required_evidence: [successful_login, post_login_activity]}
evidence_required: [user, src, host, fail_count, success_count, first_failure, last_success]
allowed_spl_templates:
  - {id: auth_success_after_failure, status: active}
answer_rules:
  - State "successful login after failures observed"
  - Do not state "compromised account" without MFA/session/post-login evidence
```

### P3 — Phishing email investigation

```yaml
use_case_id: email_phishing_header_review  # PROPOSED — not in catalog today; map from 105 Q later
live_execution_skill: attack_discovery  # or knowledge_recall if query is SOP-only
planning_or_analytic_skill: phishing_triage  # shadow catalog name TBD
github_reference_skills:
  - skills/analyzing-email-headers-for-phishing-investigation/SKILL.md
mitre_candidates:
  - {technique_id: T1566, required_evidence: [spf_result, dkim_result, dmarc_result, urls_or_domains]}
  - {technique_id: T1566.001, required_evidence: [urls_or_domains, spf_result]}
  - {technique_id: T1566.002, required_evidence: [attachment_hash]}
evidence_required: [sender, return_path, reply_to, spf_result, dkim_result, dmarc_result, urls_or_domains]
allowed_spl_templates:
  - {id: email_phishing_header_review, status: planned}
answer_rules:
  - Distinguish suspicious vs evidence-supported phishing
  - Do not confirm from sender display name alone
limitations:
  - Header analysis alone does not prove user clicked link
```

### P4 — Suspicious PowerShell execution

```yaml
use_case_id: edr_powershell_suspicious_command
live_execution_skill: attack_discovery
planning_or_analytic_skill: suspicious_command_execution
github_reference_skills:
  - skills/hunting-for-anomalous-powershell-execution/SKILL.md
mitre_candidates:
  - {technique_id: T1059, required_evidence: [command_line, event_id]}
  - {technique_id: T1059.001, required_evidence: [command_line, script_block_text, event_id]}
evidence_required: [host, user, command_line, script_block_text, event_id, parent_process, encoded_command_flag]
allowed_spl_templates:
  - {id: edr_powershell_suspicious_command, status: planned}
answer_rules:
  - Do not classify as malware without malware evidence
  - State suspicious execution + required pivots (network, auth)
```

### P5 — C2 beaconing

```yaml
use_case_id: dns_beaconing_candidate
live_execution_skill: attack_discovery
planning_or_analytic_skill: beaconing_pattern_review
github_reference_skills:
  - skills/hunting-for-command-and-control-beaconing/SKILL.md
mitre_candidates:
  - {technique_id: T1071, required_evidence: [network_telemetry, periodicity, dest]}
  - {technique_id: T1071.004, required_evidence: [dns_query_count, domain, periodicity]}
evidence_required: [src, dest, domain, periodicity, jitter, bytes_out, dns_query_count, rare_domain_indicator]
allowed_spl_templates:
  - {id: dns_beaconing_candidate, status: planned}
answer_rules:
  - Do not claim C2 confirmed from periodicity alone
  - Require multiple signals for evidence_supported
```

### P6 — Incident triage / IR playbook

```yaml
use_case_id: soc_incident_triage  # PROPOSED — or extend soc_show_sop for triage variant
live_execution_skill: alert_summary  # or knowledge_recall for playbook-only
planning_or_analytic_skill: incident_triage_playbook
github_reference_skills:
  - skills/triaging-security-incident-with-ir-playbook/SKILL.md
  - skills/triaging-security-alerts-in-splunk/SKILL.md
mitre_candidates: []  # assign per alert evidence only
evidence_required: [alert_type, affected_asset, user, severity_policy_inputs, prior_related_alerts]
allowed_spl_templates: []
answer_rules:
  - SOP/escalation guidance only
  - No destructive containment without HIL
  - No curl/TI auto-execution
```

### P7 — Ransomware / impact review

```yaml
use_case_id: endpoint_ransomware_impact_review  # PROPOSED
live_execution_skill: attack_discovery
planning_or_analytic_skill: ransomware_impact_review
github_reference_skills:
  - skills/analyzing-ransomware-encryption-mechanisms/SKILL.md  # defensive fields only
  - skills/triaging-security-incident-with-ir-playbook/SKILL.md
mitre_candidates:
  - {technique_id: T1486, required_evidence: [file_rename_count, extension_pattern, encryption_behavior]}
  - {technique_id: T1490, required_evidence: [shadow_copy_deletion_indicator]}
  - {technique_id: T1489, required_evidence: [service_stop_event]}
evidence_required: [host, user, file_rename_count, extension_pattern, affected_paths, process_name, shadow_copy_deletion_indicator]
allowed_spl_templates:
  - {id: endpoint_ransomware_impact_review, status: planned}
answer_rules:
  - Do not claim ransomware from file changes alone
  - HIL for containment/remediation guidance
limitations:
  - No reverse-engineering or decryptor steps in assistant output
```

### Optional P8 — Lateral movement (deferred pilot)

```yaml
use_case_id: edr_lateral_movement_candidate  # EXISTS in catalog
planning_or_analytic_skill: lateral_movement_review
github_reference_skills:
  - skills/detecting-lateral-movement-with-splunk/SKILL.md
  - skills/detecting-pass-the-hash-attacks/SKILL.md  # evidence-only, high scrutiny
mitre_candidates:
  - {id: T1021, default: candidate}
```

---

## J. Dependency map (A × B × C × D)

| Item | Depends on |
|------|------------|
| **D1 intake register** | GitHub clone + defensive checklist |
| **D4 status matrix** | D1 accepted skills |
| **D5 / B9 coverage matrix** | D1, D4, `question_runtime_map_v1.json` |
| B1 enrichment schema | D1 accepted skills (provenance paths) |
| A2 MITRE | B3, B4, P1–P7, D7 MITRE mapping |
| A3 SPL | B6, C4 |
| A4 MCP | A1, A3, C4 |
| A5 Memory | C1, B5 workflows |
| A6 Answer guard | B7, C8 |
| B9 Matrix | B1 schema + **D5** intake links |
| C3 Evidence plan | B1, B4, A5 pins, D1 evidence_reference |
| C5 MITRE node | A2, B3 |
| C2 Planning skill | B8 (105 semantics) |
| C4 SPL nodes | A3, B6 |
| P1–P7 pilots | D7 accept decision + B1 schema |
| P3/P6/P7 new use cases | B1 schema + catalog entry + D1 mapping |

---

## K. Recommended execution order

**Canonical sequence: §L.** This section only notes Track D parallelism:

**Track D (docs-only)** runs alongside phases 0–2: D1/D7 → D2–D4 → D5 ↔ B9.

Track C phase 0 (C1/C9) precedes behavior changes so trace fields exist before HIL/MITRE shifts.

---

## L. First implementation slice (post-planning)

| Order | ID | Deliverable |
|-------|-----|-------------|
| 0 | **D1, D7** | `docs/skills/github_skill_intake_register.json` + 7 batch-1 records — **Done** |
| 0b | **D2–D4** | Rejection log, pending backlog, enrichment status matrix — **Done** (docs stubs) |
| **2** | **Batch 2** | Tracked SOC skill enrichment baseline from GitHub references — **Done** |
| **2.1** | **Batch 2.1** | Defensible offline question-to-use-case mappings — **Done** |
| **3** | **Batch 3** | MITRE evidence status + SPL template governance — **Done** |
| **3.1** | **Batch 3.1** | Pilot evidence contracts doc + output verification tests — **Done** |
| **4** | **Batch 4** | Pipeline trace + guarded answer visibility — **Done** |
| **5** | **Batch 5** | Lightweight backend session memory (structured pins, TTL, follow-ups) — **Done** |
| **5.x** | **Post-Batch 5 review** | Streamed `/clear` now clears backend session pins; governance regression PASS — **Done** |
| **6** | **Batch 6** | Real Splunk MCP safety contract (docs only) — **Done** |
| **7** | **Batch 7** | Plan status review and gap audit — **Done** |
| 1 | C1, C9 | State field spec + `node_trace` schema in docs — **Done** (Batch 4 runtime) |
| 2 | A1 | HIL for mock MCP + response labels |
| 3 | B9, **D5** | `skill_coverage_matrix.json` (≥105 monotonic `question_id`s) linked to intake register |
| 4 | B1 | Pydantic model + 2 pilot enrichments (P1, P2); update D4 status |
| 5 | A2 | Remove `_status_for()`; expand KB for P1/P2 techniques |
| 6 | C2, C3 | Split planning skill resolution + enrichment load (flag-gated) |
| 7 | B6, A3 | Mark templates planned/active; PowerShell/beacon stubs |
| 8 | P3–P7 | Remaining pilots + proposed use cases; sync D1 impl flags |
| 9 | C4, C5, C8 | SPL + MITRE + answer node split |
| 10 | A6 | Answer guard lab flag |
| 11 | A5 | Session pins MVP |

---

## M. Deferred items


### M.1 Canonical handoff + T2 closure (2026-06-27) — **COMPLETE**

**SSOT:** [`2026-06-27_handoff-t2-completion-consolidated.md`](2026-06-27_handoff-t2-completion-consolidated.md). **Operator rollout:** [`2026-06-27_operator_closure_checklist.md`](2026-06-27_operator_closure_checklist.md).

**Merged to `master` @ `ca3249b`:** PRs #40, #39 (Batch 0); #41 (A+B); #42 (C); #43 (E); #44 (D); #45 (F).

| Item | Status | Notes |
|------|--------|-------|
| Canonical graph handoff (EvidencePlan → ResourcePlan → FinalEvidenceGate → RunContract) | **Shipped** | PR #38 core + Batches A–F; no parallel architecture |
| Operator-reviewed `promotion_status` write path | **Shipped** | PR #39; dry-run default; `--apply` operator-only |
| Row-authority report refresh policy | **Shipped** | PR #39; `docs/evals/ARTIFACT_REFRESH_POLICY.md` |
| Wineventlog shift-hour trace + T1 meta | **Shipped** | PR #39 trace + Batch E (PR #43) |
| MCP live-readiness checklist | **Shipped** | PR #39 docs; execution flags default-off |
| Answer-pack coverage (WS7) | **Shipped** | Batch D (PR #44); ≥5 weak-known packs |
| SPL degrade-chain trace projection | **Shipped** | Batch D; trace-only `spl_artifact_handoff_summary` |
| Frontend authority tiers (WS5) | **Shipped** | Batch F (PR #45); diagnostic UI only |
| COE `q0.q046` promotion `--apply` | **Operator-only** | See operator checklist |
| Live Splunk MCP activation | **Operator-only** | Checklist + contract; flags stay off until COE |
| `route_authority_operation_authoritative_enabled` prod | **Operator-only** | After staging matrix sign-off |
| Eval baseline refresh | **Operator-only** | Explicit request only; no accidental drift commits |

### M.2 Original deferred list

- Full skill enum unification
- Importing 754 GitHub skills
- Loading `SKILL.md` into prompts
- Real Splunk MCP implementation (until COE)
- LLM SPL fallback in production
- LLM → Splunk tool calling
- Full ATT&CK mirror
- Phishing/IR/ransomware catalog routing rows (P3/P6/P7 **enrichment shipped** in `content_enrichment.json`; `catalog.json` entries deferred per B8)
- P8 lateral movement enrichment (optional — see D3 backlog BL-001–BL-003)
- `graph/state.py` `InvestigationState` merge (separate investigation graph stub)
- Bulk import of 754 skills into intake register (review incrementally via D6 workflow)

---

## N. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| R1 | GitHub offensive content leaks into RAG | Med | Critical | Defensive checklist + human review of enrichments |
| R2 | Dual-skill confusion in UI/tests | High | Med | Explicit field names; matrix documents both |
| R3 | Node split breaks LangGraph parity | Med | High | Parity tests; feature flags per node |
| R4 | Session memory overclaim | Med | High | Pins only; re-validate gates each turn |
| R5 | MITRE `evidence_supported` without thresholds | Med | High | Precondition keys + tests per pilot |
| R6 | New use cases (P3/P6/P7) expand scope | Med | Med | Propose as catalog additions in same PR as enrichment schema |
| R7 | Golden 105 expects shadow skill in `selected_skill` | High | Low | Golden asserts `planning_or_analytic_skill` separately |
| R8 | Lost track of reviewed GitHub skills | High | Med | Track D intake register + rejection log mandatory before accept |
| R9 | Re-reviewing rejected skills repeatedly | Med | Low | `rejected_github_skills.md` + reason codes |
| R10 | `/tmp` clone lost on host rebuild | Med | Low | Pin `repo_commit` in D1; document re-clone procedure in §C |

---

## O. Acceptance criteria

### §O closeout summary (2026-07-01)

| Area | Status | Evidence |
|------|--------|----------|
| §O acceptance loop | **Complete** | O1–O11 below (single checklist; no duplicate summary) |
| Governance regression | **Pass** | `./scripts/run_stage3_governance_regression.sh` |
| Backend pytest | **Pass** | `cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q` |
| Sentinel | **Pass** | `scripts/eval_sentinel.py --check` → 17/17 |
| Tier-D answer quality | **Pass** | `scripts/eval_answer_quality.py --check` → 17/17 |
| OT probe | **Pass** | `scripts/eval_out_of_catalog_ot_probe.py --check` → 6/6 |
| Guided hybrid orchestrator | **Complete** | P13 `d1b78da`; P14 docs `347ca18`; plan [`2026-07-01_1545_guided-readonly-mcp-discovery-lane.md`](2026-07-01_1545_guided-readonly-mcp-discovery-lane.md) |
| O3 MITRE status reconcile | **Complete** | `rg '_status_for\(' backend/app/threat/mitre_kb.py` → zero on closeout branch; batch3 + mitre_decision tests |
| Forward roadmap §P / §K / §R | **Open** | Tracking table below; not closed by this acceptance loop |

**Do not confuse with forward work:** §O is closed. **BL-004 offline mapping closed (S1c).** **S2–S6d engineering complete (2026-07-01).** Next: COE rollout config ([`docs/coe/COE_ROLLOUT_CONFIGURATION.md`](../docs/coe/COE_ROLLOUT_CONFIGURATION.md)), corpus curation (64 gaps), operator-only MCP, QA decision on split-routing flag.

### Planning (this document)

- [x] Four tracks documented (A–D)
- [x] Seven GitHub reference skills included
- [x] Track C LangGraph section complete
- [x] Track D intake / rejection / implementation tracking defined
- [x] GitHub repo URL, local path, commit SHA documented
- [x] Proposed tracking files: D1–D5 paths and schemas
- [x] First-batch D7 table for 7 skills with accept/defer/partial decisions
- [x] Rejection reason codes and examples (D8)
- [x] D6 decision workflow documented
- [x] Coverage matrix path proposed (`docs/evals/skill_coverage_matrix.json`)
- [x] Defensive checklist included
- [x] Dual skill semantics preserved
- [x] No code changes; no runtime skill loading

### §O implementation loop (O1–O11) — CLOSED 2026-07-01

> **Single source of truth** for runtime acceptance. Do not maintain a parallel unchecked bullet list — that caused two-writers-one-fact drift vs this block.

**Stop conditions:** all items checked with evidence, same gate fails twice on one item, or explicit scope/COE decision needed.

**Dependency order:** O6 → O5 → O7 → O8 → O2/O4 → O3 → O9/O10/O11 → O1 (governance gate last).

- [x] **O1** — Governance regression green
  - **Do:** Keep sentinel + pytest + harness gates passing on branch
  - **Verify:** `./scripts/run_stage3_governance_regression.sh` exits 0
  - **Depends on:** O2–O11 stable
  - **Evidence:** 2026-07-01 — `stage3_governance_regression: PASS`; backend pytest 3621 passed; sentinel 17/17; Tier-D 17/17; OT probe 6/6; soc_clean 120/120; PowerGrid 50/50.

- [x] **O2** — Mock MCP HIL or explicit mock label outside demo
  - **Do:** Mock success path requires HIL when `AI_SOC_REQUIRE_HIL_FOR_MOCK_EXECUTION=true`
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_hil_mock_execution_hardening.py -q`
  - **Depends on:** none
  - **Evidence:** 2026-07-01 — 5/5 passed.

- [x] **O3** — MITRE statuses from evidence preconditions only
  - **Do:** Remove non-pilot `_status_for()` call sites; route all use cases through `evaluate_pilot_mitre_evidence_status` / preconditions (A2)
  - **Verify:** `rg '_status_for\\(' backend/app/threat/mitre_kb.py` returns zero; `pytest app/tests/test_mitre_decision_runtime.py app/tests/test_mitre_spl_governance_batch3.py -q`
  - **Depends on:** B3/B4 pilot preconditions
  - **Evidence:** 2026-07-01 — removed legacy `_status_for` / `_legacy_evidence_status_for`; non-pilot fail-closed to `requires_validation`; pilot resolver spy + fail-closed tests green; mitre decision runtime 20/20 passed.

- [x] **O4** — SPL template-first; LLM fallback off in prod
  - **Do:** Runtime default `AI_SOC_LLM_SPL_FALLBACK_ENABLED=false`; template path wins unless flag on
  - **Verify:** `python3 -c "from app.config import Settings; assert Settings.model_fields['ai_soc_llm_spl_fallback_enabled'].default is False"`; `pytest app/tests/test_mitre_spl_governance_batch3.py::test_llm_fallback_cannot_bypass_validation -q`
  - **Depends on:** none
  - **Evidence:** 2026-07-01 — `config.py` default false; batch3 bypass test green. **Drift:** `env/profiles/coe.env.example` may enable fallback for lab — COE profile override, not prod default.

- [x] **O5** — Seven pilots have `content_enrichment` + GitHub provenance
  - **Do:** P1–P7 records in `content_enrichment.json` with `github_reference_skills` (catalog routing rows for P3/P6/P7 deferred per B8)
  - **Verify:** `python3 -c "import json; r=json.load(open('backend/app/use_cases/content_enrichment.json'))['records']; pilots=['auth_failed_login_spike','auth_success_after_failure','email_phishing_header_review','edr_powershell_suspicious_command','dns_beaconing_candidate','soc_incident_triage','endpoint_ransomware_impact_review']; assert all(p in r for p in pilots)"`
  - **Depends on:** B1 schema (Batch 2 sidecar)
  - **Evidence:** 2026-07-01 — assert passed (all 7 pilot keys present in sidecar).

- [x] **O6** — GitHub intake register batch-1 (≥7 skills) with `repo_commit`
  - **Do:** D7 records in `docs/skills/github_skill_intake_register.json`
  - **Verify:** `python3 -c "import json; d=json.load(open('docs/skills/github_skill_intake_register.json')); print(len(d['records']), d['repo_commit'])"` → ≥7 records + pinned commit
  - **Depends on:** D1 (slice 0)
  - **Evidence:** 2026-07-01 — 12 records, `repo_commit=04450304b126`.

- [x] **O7** — `skill_enrichment_status_matrix.md` reflects pilot progress
  - **Do:** D4 matrix lists all seven pilots with enrichment/SPL/test columns
  - **Verify:** `grep -c 'auth_failed_login_spike\\|auth_success_after_failure\\|edr_powershell\\|dns_beaconing\\|email_phishing\\|soc_incident_triage\\|endpoint_ransomware' docs/skills/skill_enrichment_status_matrix.md` → ≥7
  - **Depends on:** O5, O6
  - **Evidence:** 2026-07-01 — matrix documents 4 active + 3 staged pilots with implementation columns.

- [x] **O8** — Skill coverage matrix (B9 baseline)
  - **Do:** Offline generator emits exactly 105 monotonic rows; GitHub join where BL-004 mapping exists
  - **Verify:** `python3 scripts/build_skill_coverage_matrix.py --check`; `python3 -c "import json; assert len(json.load(open('docs/evals/skill_coverage_matrix.json')))==105"`
  - **Depends on:** O6, B9 generator
  - **Evidence:** 2026-07-01 — `--check ok` (105 rows). **Deferral:** full `github_reference_skill` on all 105 rows blocked on BL-004 `question_use_case_map.json` curation (104 `missing_authoritative_mapping` warnings).

- [x] **O9** — LangGraph parity with imperative path when flag on
  - **Do:** Dual-parity eval matches imperative `/chat` on parity corpus
  - **Verify:** `python3 scripts/run_langgraph_dual_parity_eval.py --check`; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_langgraph_dual_parity_phase13.py -q`
  - **Depends on:** Track C phases
  - **Evidence:** 2026-07-01 — dual_parity_eval 120/120 match; phase13 tests in governance regression.

- [x] **O10** — Final answer separates facts, assumptions, MITRE status, SPL status, HIL
  - **Do:** `AnswerContract` + `validate_final_answer` enforce section ownership and fail-closed conflicts
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_answer_contract.py app/tests/test_final_answer_validator.py -q`
  - **Depends on:** C8, A6
  - **Evidence:** 2026-07-01 — 27/27 passed (`spl_status`, `hil_status`, `assumptions`, render_sections gates).

- [x] **O11** — Session follow-up re-validates; no gate bypass
  - **Do:** Batch 5 session context re-validates SPL/MITRE on follow-up turns
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_batch5_session_context.py -q`
  - **Depends on:** A5, C1
  - **Evidence:** 2026-07-01 — 8/8 passed (`test_follow_up_spl_refine_revalidates_previous_spl`, `test_follow_up_mitre_uses_fresh_session_context`).

---

## P. Proposed tracking table

| ID | Track | Work Item | Current State | GitHub Reference | Proposed Change | Files | Priority | Dependency | Tests Required | Status |
| -- | ----- | --------- | ------------- | ---------------- | --------------- | ----- | -------- | ---------- | -------------- | ------ |
| D1 | D | GitHub skill intake register | **Done** (slice 0) | All inspected skills | JSON register with provenance + decision + impl flags | `docs/skills/github_skill_intake_register.json` | P0 | — | JSON schema validation | **Done** |
| D2 | D | Rejection log | **Done** (slice 0) | Rejected skills | Markdown table + reason codes | `docs/skills/rejected_github_skills.md` | P0 | D1 | — | **Done** |
| D3 | D | Pending enrichment backlog | **Done** (slice 0) | Deferred / future skills | Markdown backlog table | `docs/skills/pending_skill_enrichment_backlog.md` | P1 | D1 | — | **Done** |
| D4 | D | Enrichment status matrix | **Done** (slice 0) | Accepted → use cases | Per use-case implementation columns | `docs/skills/skill_enrichment_status_matrix.md` | P0 | D1, D7 | — | **Done** |
| D5 | D | Coverage matrix master link | B9 + BL-004 S1a–S1c | 105 questions | Runtime enrichment joins (S3+) | `docs/evals/skill_coverage_matrix.json` | P0 | D1, B9 | `build_skill_coverage_matrix.py --check` | **Done** (41/105 mapped; 64 gaps documented) |
| D6 | D | Intake decision workflow | Informal | N/A | Document 9-step process in plan + README stub | `docs/skills/README.md` (optional) | P0 | D1 | — | Proposed |
| D7 | D | First batch (7 skills) | **Done** (slice 0) | 7 mandatory skills | Populate D1 with accept/partial + mappings | `github_skill_intake_register.json` | P0 | D1 | — | **Done** |
| C1 | C | Graph state model v2 | `ChatPipelineState` partial | N/A | Add session, dual skill, enrichment, node_trace fields | `pipeline.py`, `schemas/responses.py` | P0 | — | Schema unit tests | Proposed |
| C9 | C | Node-level trace | `control_plane_trace` partial | N/A | Per-node input/output/decision in trace | `control_plane_trace.py`, `pipeline.py` | P0 | C1 | Trace snapshot tests | Proposed |
| A1 | A | HIL mock MCP hardening | Batch 1 shipped | `triaging-security-alerts-in-splunk` disposition | Durable approval store for real MCP (forward) | `mcp_execution_gate.py`, `config.py`, `pipeline.py` | P0 | — | HIL matrix tests | **Done** (O2) |
| B9 | B | Skill coverage matrix | S1a–S1c landed | `ATTACK_COVERAGE.md` pattern | S3 runtime enrichment wiring | `docs/evals/skill_coverage_matrix.json` + generator | P0 | — | `--check` 105 rows | **Done** (BL-004 closed) |
| B1 | B | content_enrichment schema | **Sidecar shipped** (7 pilots in `content_enrichment.json`) | SKILL.md frontmatter | Pydantic model + loader validation; optional catalog rows for P3/P6/P7 | `content_enrichment.json`, `models.py` | P0 | — | Enrichment schema/loader test | **Partial** |
| B2 | B | Domain taxonomy | `category` only | GitHub domain/subdomain | Normalize domains for pilots | `content_enrichment.json`, `catalog.json` | P1 | B1 | — | Proposed |
| B3 | B | MITRE precondition wiring | **98 techniques** shipped (`curated-subset-v4`); T1059.001/T1566*/T1071/T1486 present | Reference skills | Extend `mitre_evidence_preconditions` + remove `_status_for()` (pairs with A2) — **not** bulk technique import | `mitre_kb.py`, `mitre_evidence_preconditions.py` | P1 | B1, A2 | `test_mitre_decision_runtime.py` | **Partial** |
| B4 | B | Evidence requirements | Partial preconditions | Prerequisites sections | Per-use-case required/optional/thresholds in sidecar | `content_enrichment.json`, `mitre_evidence_preconditions.py` | P0 | B1 | `test_negative_evidence_extractor.py` | Proposed |
| B5 | B | Investigation workflows | Generic blueprints only | Workflow sections | 8-step workflow arrays in enrichment sidecar | `content_enrichment.json` | P1 | B1 | Demo scenario tests | Proposed |
| B6 | B | SPL template activation | planned/null templates | Splunk/beacon/PS skills | active/planned/unavailable per template | `spl/templates.json` | P1 | B1 | `test_spl_generation_stage.py` | Proposed |
| B7 | B | Analyst answer rules | Demo fixtures only | Expected Output | answer_rules + limitations per pilot in sidecar | `content_enrichment.json`, `answer_contract.py` | P1 | B1 | `test_answer_contract.py` | Proposed |
| B8 | B | 105 dual-skill compatibility | Golden misalignment risk | N/A | Matrix columns; don't overwrite proposed_primary_skill | `question_runtime_map_v1.json`, matrix JSON | P1 | B9 | `test_golden_answer_runner.py` | Proposed |
| A2 | A | MITRE evidence status | O3 legacy shim removed | Reference skills | B3/B4 expand preconditions to all use cases | `mitre_kb.py`, `mitre_decision.py` | P0 | B3, B4, P1-P7 | Pilot MITRE tests | **Partial** (O3) |
| A3 | A | SPL governance | LLM fallback disabled | Splunk triage skill | Template-family + lab-only fallback | `spl_validator.py`, `llm_fallback.py` | P1 | B6, C4 | `test_llm_spl_fallback.py` | Proposed |
| A4 | A | Splunk MCP safety plan | NotImplementedError | N/A | COE checklist doc only | `splunk_mcp.py`, docs | P3 | A1, A3 | — | Deferred |
| A5 | A | Session memory | Batch 5 pins shipped | N/A | Durable multi-worker session store (§P) | `session_store.py`, `pipeline.py` | P2 | C1, B5 | `test_batch5_session_context.py` | **Partial** (O11) |
| A6 | A | Answer guard lab | Flag off | Limitations sections | Enable in lab; HIL on block | `answer_guard/runner.py`, `config.py` | P1 | B7, C8 | `test_p6_guarded_synthesis_lab.py` | Proposed |
| C2 | C | Split route vs planning | Mixed in init_routing | N/A | `route_live_skill` + `resolve_planning_skill` nodes | `pipeline.py`, `chat_workflow.py` | P1 | B8, C1 | Parity tests | Proposed |
| C3 | C | Evidence plan node | Basic planner exists | N/A | Enrichment-aware evidence plan + runtime load (§P) | `evidence_planner.py`, `pipeline.py` | P1 | B1, B4 | `test_control_plane_behavior_matrix.py` | **Partial** |
| C4 | C | SPL node split | Combined workflow_spl | N/A | select/bind/validate/execution_decision | `pipeline.py` | P1 | A3, B6 | SPL stage tests | Proposed |
| C5 | C | MITRE evidence node | Inside context_finalize | N/A | `resolve_mitre_evidence_status` node | `mitre_decision.py`, `pipeline.py` | P1 | A2 | MITRE pilot tests | Proposed |
| C6 | C | Severity node formalize | `decide_severity()` inline | N/A | Explicit node; conservative on missing evidence | `severity_policy.py`, `pipeline.py` | P2 | C3 | Severity tests | Proposed |
| C7 | C | RAG/SOP node | `graph_node_rag_early` | IR playbook (SOP only) | `retrieve_sop_context` with rag_doc_ids | `soc_kb_retriever.py` | P1 | B1 | `test_soc_kb_*` | Proposed |
| C8 | C | Answer node split | finalize monolith | N/A | contract → summary → guard → validate → envelope | `pipeline.py`, `analyst_response_builder.py` | P1 | A6, B7 | Final answer validator tests | Proposed |
| C10 | C | Backward compat | PlaceholderResponse stable | N/A | Additive fields only | `responses.py`, `api.ts` | P0 | C1 | Frontend build | Proposed |
| P1 | B | Pilot auth_failed_login_spike | Catalog + enrichment shipped | detecting-rdp-brute-force + splunk triage | Full enrichment §I P1; update D4 | `content_enrichment.json`, `catalog.json`, templates | P0 | B1, B4, D7 | Behavior matrix auth | **Partial** |
| P2 | B | Pilot auth_success_after_failure | Catalog + enrichment shipped | Same | Full enrichment §I P2; update D4 | `content_enrichment.json`, `catalog.json` | P0 | P1, D7 | MITRE success-after-failure tests | **Partial** |
| P3 | B | Pilot phishing | **Enrichment landed**; catalog row deferred | email-headers skill | Add `email_phishing_header_review` to `catalog.json` when B8 routing ready | `content_enrichment.json`, catalog, templates | P1 | B1, B8 | New routing tests | **Partial** |
| P4 | B | Pilot PowerShell | Catalog + enrichment shipped | anomalous-powershell skill | Enrichment + planned template | `content_enrichment.json`, `catalog.json`, templates | P1 | B6 | SPL tests | **Partial** |
| P5 | B | Pilot beaconing | Catalog + enrichment shipped | c2-beaconing skill | Enrichment + planned template | `content_enrichment.json`, `catalog.json`, templates | P1 | B6 | SPL tests | **Partial** |
| P6 | B | Pilot IR triage | **Enrichment landed**; catalog row deferred | ir-playbook skill | Add `soc_incident_triage` to `catalog.json` when B8 routing ready | `content_enrichment.json`, catalog, RAG | P1 | B1, B8 | Demo + knowledge tests | **Partial** |
| P7 | B | Pilot ransomware | **Enrichment landed**; catalog row deferred | ransomware-encryption skill | Add `endpoint_ransomware_impact_review` to `catalog.json` when B8 routing ready | `content_enrichment.json`, catalog, templates | P1 | B1, B8 | MITRE T1486 tests | **Partial** |
| P8 | B | Optional lateral movement | `edr_lateral_movement_candidate` exists | detecting-lateral-movement-with-splunk | Optional enrichment | catalog | P3 | P1-P7 | — | Deferred |
| G1 | A+B+C+D | Governance regression | Baseline green | N/A | No regressions after each phase | `scripts/run_stage3_governance_regression.sh` | P0 | All | Full regression | Proposed |

### Proposed Track D tracking files (summary)

| File | Purpose |
|------|---------|
| `docs/skills/github_skill_intake_register.json` | One record per GitHub skill reviewed |
| `docs/skills/rejected_github_skills.md` | Permanent rejection log |
| `docs/skills/pending_skill_enrichment_backlog.md` | Deferred / not-yet-reviewed candidates |
| `docs/skills/skill_enrichment_status_matrix.md` | Internal use-case implementation progress |
| `docs/evals/skill_coverage_matrix.json` | **Master control** — 105 questions ↔ use cases ↔ GitHub refs |

---

## What not to change yet

- Unify all skills into one runtime enum
- Remove the 4 live skills or `legacy_router_intent_hint` / `proposed_primary_skill`
- Import all GitHub skills or load `SKILL.md` into prompts
- Execute scripts from the GitHub reference clone
- Auto-sync intake register from GitHub (manual review via D6 only)
- Enable real Splunk MCP or production LLM SPL fallback
- Allow LLM to call Splunk tools
- Claim confirmed MITRE, account compromise, or execution without evidence/HIL

---

*End of master plan. No application code was modified.*

---

## Q. Review findings — bugs and fixes

> **Added 2026-06-06.** Plan-level review (no application code changed). Load-bearing claims verified against the current tree. Each finding tagged **High / Med / Low**.
>
> **Amendments:** Findings Q1.1–Q2.4 and Q3.1–Q3.5 were applied to the plan body above (§A, §B, §C, §D, §I, §K, mermaid). §Q remains the audit record.

### Q.1 — Critical / load-bearing

**Q1.1 — `not_claimed_defaults` (B1) and §I pilot status strings reintroduce removed hardcoding. [High]** — **Applied §B1, §I.**

- **Evidence:** `backend/app/threat/mitre_evidence_preconditions.py` docstring states it *"Replaces per-use-case 'not claimed' hardcoding (`_DEFAULT_NOT_CLAIMED`, `_not_claimed_for_context`)"* with a data-driven rule covering authentication, DNS/DGA, phishing, malware, network, exfiltration, and lateral movement — i.e. the exact P1–P7 domains. The 2026-06-04 general SOC reasoning plan (CLAUDE.md: **Done**) is what landed this.
- **Bug:** B1's schema field `"not_claimed_defaults": ["T1078"]` and the §I pilot YAML strings (`default: not_claimed_without_spray_pattern`, `default: not_claimed_without_successful_login`, `default: not_claimed_without_dns_tunneling_fields`, etc.) re-encode per-technique not-claimed logic inline in the catalog. This is the same per-use-case hardcoding the preconditions module deleted. Two competing sources of truth → drift, and the inline strings bypass the data-driven negation path.
- **Fix:** Delete `not_claimed_defaults` from the B1 schema. Express each pilot technique as `{technique_id, required_evidence:[...]}` only; "not claimed" is **derived** (absent required evidence → not claimed with the module's stable reason). Where a pilot needs a new technique/reason, add a `TechniquePrecondition` row to `mitre_evidence_preconditions.py`, not a string in `catalog.json`. This makes B3/B4 an **extension of the shipped module**, not a parallel mechanism.

**Q1.2 — MITRE status represented three incompatible ways. [High]** — **Applied §A2, §B1, §I** (runtime-only status vocabulary).

- **Bug:** A2 defines a 5-value controlled vocabulary (`candidate`, `evidence_supported`, `requires_validation`, `not_claimed`, `ruled_out`). B1 uses `{status_default: "candidate", evidence_required: [...]}`. §I pilots invent free-form compound strings (`not_claimed_without_spray_pattern`, `evidence_supported_when: [fail_count_gte_threshold]`). An implementer has no single shape to code against.
- **Fix:** Pick one representation — recommend: status is **never** authored, only the A2 vocabulary is emitted at runtime by `resolve_mitre_decision`; the catalog authors only `technique_id` + `required_evidence` (+ optional `thresholds`). Replace every `default:`/`status_default:`/`evidence_supported_when:` form in §I and B1 with that single shape. Add a catalog-validation test asserting no enrichment row carries a status string outside the A2 enum.

**Q1.3 — `_status_for()` cleanup = reconcile, not rebuild. [High]** — **Applied §A2, §D.**

- **Evidence:** `backend/app/threat/mitre_kb.py:72` still defines `_status_for(use_case_id, technique_id)` and `mitre_kb.py:56` still calls it. So hardcoded status **and** the data-driven precondition module currently coexist (the D-table "Mixed hardcoded + preconditions" note is accurate).
- **Fix:** A2 should explicitly state its job is to **remove the remaining `_status_for()` call site** and route through `mitre_decision.resolve_mitre_decision` / `mitre_evidence_preconditions`, not to author a new vocabulary from scratch (the vocabulary largely exists). Add a regression test that `_status_for` is unreferenced after the change.

**Q1.4 — Mis-attributed file paths; an implementer cannot resolve them. [High]**

- **Evidence:**
  - §D table (original) cited `contracts/skill_enum.py` for `validate_skill()` / `plan_workflow()`. **`contracts/skill_enum.py` exists** at repo root (harness enum), but **`validate_skill`** → `backend/app/routing/skills.py` and **`plan_workflow`** → `backend/app/orchestration/workflow_planner.py`.
  - A6/B7 cited `contracts/answer_contract.py`. Real path: `backend/app/chat/contracts/answer_contract.py`.
  - Many entries dropped the `backend/app/` root (e.g. `mitre_kb.py`, `pipeline.py`, `config.py`).
- **Fix (applied §D):** Split enum vs function locations; normalize paths with `backend/app/` or `frontend/src/` prefix. Sanity check: `test -f <path>` from repo root.

**Q1.5 — A5 must not reuse `quality/store.py`. [High]** — **Applied §A5** (`session_store.py`).

- **Evidence:** `backend/app/quality/store.py` is the answer-quality ledger (`record_chat_turn`, `record_feedback`, `record_review`, `mark_golden_candidate`, CSV export). A5 lists it as a file for the session-pins store.
- **Bug:** Session pins (ephemeral, TTL ~30 min, 5-turn cap) and the durable quality/feedback ledger are different lifecycles and different authority. Co-locating them violates separation of concerns (and the user's own "data layer / business logic apart" principle).
- **Fix:** New module `backend/app/chat/session_store.py` (or `app/session/`) for pins, with its own TTL eviction. Quality ledger stays untouched. A5 file list should drop `quality/store.py`.

### Q.2 — Should-fix

**Q2.1 — A1 demo-relaxation flag has no execution path to relax. [Med]** — **Applied §A1:** dropped `AI_SOC_ALLOW_MOCK_EXECUTION_WITHOUT_HIL_IN_DEMO`; EC path documented as gate-bypass; single `AI_SOC_REQUIRE_HIL_FOR_MOCK_EXECUTION` flag for live path.

- **Evidence:** `backend/app/api/routes_chat.py` EC branch (`ai_soc_live_chat_ec_parity_enabled` + `run_demo_scenario`) returns before `build_live_chat_response` reaches the MCP gate.

**Q2.2 — New use cases vs 105-row CI gate. [Med]** — **Applied §B8/B9:** monotonic `question_id` CI; P3/P6/P7 may enrich without new question rows initially.

**Q2.3 — `C2` flag default self-contradictory. [Med]** — **Applied §C2:** `PIPELINE_SPLIT_ROUTING_NODES` defaults **false**.

**Q2.4 — `spl_generation` not used by pilots. [Med]** — **Applied §A non-negotiables + §D:** intentional; template/candidate SPL path only.

### Q.3 — Minor / hygiene (applied)

- **Q3.1 [Low]** §A links to §L as canonical order; §K defers to §L. **Applied.**
- **Q3.2 [Low]** §K no longer duplicates numbered slice (defers to §L). **Applied.**
- **Q3.3 [Low]** Mermaid: `B7`, `D6` declared in subgraphs. **Applied.**
- **Q3.4 [Low]** Line refs → symbol names + "verify at implementation". **Applied §A1, §D.**
- **Q3.5 [Low]** B9 CI corpus = 105-question runtime map, not 105+46 expectation matrix. **Applied §B9.**

### Q.4 — Verification log (this review)

| Claim checked | Result |
|---------------|--------|
| Mock success returns `no_human_review()` | **Confirmed** — `mcp_execution_gate.py:140` |
| `_status_for()` still live | **Confirmed** — `mitre_kb.py:72` (called at `:56`) |
| Preconditions module replaced not-claimed hardcoding | **Confirmed** — module docstring |
| `contracts/skill_enum.py` exists | **Confirmed** — repo root; but `validate_skill` is in `backend/app/routing/skills.py` |
| `answer_contract.py` path | **Corrected** — `backend/app/chat/contracts/answer_contract.py` |
| `quality/store.py` is the answer-quality ledger | **Confirmed** |
| EC path early-returns before gate | **Confirmed** — `routes_chat.py` EC branch vs `build_live_chat_response` |
| MITRE subset technique count = 4 | **Stale** — subset is **98 techniques** (`curated-subset-v4`), **8** `curated_use_case_mappings`; see §D MITRE KB row |
| `EXECUTION_ELIGIBLE_SKILLS` = {attack_discovery, spl_generation} | **Confirmed** — `mcp_tool_selector.py:10` |

---

## R. Way forward — execution protocol

> **Added 2026-06-06.** How to move ahead from "docs landed (D1–D4, §Q applied)" to a governed, reviewable, incremental build. **One slice per PR-sized commit.** Every slice ends green on `./scripts/run_stage3_governance_regression.sh` before the next starts. No slice combines a docs change with a runtime-behavior change (per CLAUDE.md scope discipline).

### R.1 — Slice ladder (canonical order; supersedes §L for sequencing)

| Slice | ID | Type | Runtime risk | Gate before merge |
|-------|-----|------|--------------|-------------------|
| **S0** | D1–D4, README | docs | none | files valid; **DONE** |
| **S1a** | B9 | docs/JSON + generator script | none (read-only generator) | matrix covers full 105 corpus; generator deterministic; no backend import |
| **S1b** | C1/C9 | docs (state v2 + node_trace spec) | none | spec only; zero code touched |
| **S2** | A1 | **runtime** (HIL on mock MCP) | **behavior change** | governance regression green; HIL matrix tests pass |
| **S3** | B1 + P1/P2 | runtime (enrichment schema + 2 pilots) | additive | catalog validation test; preconditions-driven (no `not_claimed_defaults`) |
| **S4** | A2 | runtime (MITRE reconcile) | additive | `_status_for` unreferenced; pilot MITRE tests |
| **S5** | C2/C3 | runtime (node split, flag-gated default off) | flagged | LangGraph parity test |
| **S6+** | B6/A3, P3–P7, C4/C5/C8, A6, A5 | runtime | per §L | per-item tests + regression |

**S1a and S1b are independent and docs-only → parallelizable now.** S2 onward is serial (each depends on prior runtime state) and each needs explicit go-ahead since it changes behavior.

### R.2 — Per-slice definition of done

1. Deliverable on disk (file/JSON/test).
2. `./scripts/run_stage3_governance_regression.sh` → PASS (harness 6/6, 0 pytest failures).
3. Frontend build green **if** frontend touched.
4. Review pass (self-review diff + advisor on runtime slices).
5. Scoped commit, co-author trailer, conventional-commit subject.
6. Plan status table + this ladder updated (slice → DONE).

### R.3 — Agent assignment

| Slice | Agent | Boundary |
|-------|-------|----------|
| S1a B9 | general-purpose | Build `docs/evals/skill_coverage_matrix.json` + `scripts/build_skill_coverage_matrix.py`. **Read-only** against backend catalogs; never import runtime; never modify `backend/app`. |
| S1b C1/C9 | general-purpose | Write `docs/architecture/` spec only. Touch **no** `.py`. |
| Runtime slices | implementer (or inline) + validator | One defect class per commit; validator runs regression. |

### R.4 — Guardrails (do not violate while executing)

- No `not_claimed_defaults` / inline status strings — derive from `mitre_evidence_preconditions.py` (§Q1.1).
- B9 generator is read-only; it must not be importable by `/chat` (docs/eval tool only).
- Preserve 4 live skills + dual skill semantics; additive response fields only.
- Real Splunk MCP, production LLM SPL fallback, LLM→MCP: **deferred** (§M).
- Commit docs slices separately from runtime slices.

### R.5 — Immediate next action

Execute **S1a (B9)** and **S1b (C1/C9)** in parallel (docs-only, zero governance risk), review, commit as two scoped commits. Then stop for go-ahead on **S2 (A1)** — first behavior change.

### R.6 — Execution log + findings (2026-06-06)

**S1a (B9) — landed.** `scripts/build_skill_coverage_matrix.py` (offline, read-only, no `app.*` import, `--check` for CI) + `docs/evals/skill_coverage_matrix.json` (exactly **105 rows**, idempotent). Columns carrying real per-row signal today: `live_execution_skill` (attack_discovery ×89 / alert_summary ×8 / knowledge_recall ×8), `planning_or_analytic_skill`, `spl_template_status` (active ×10, unavailable ×95), `query`.

> **🟡 Track D data gap (surfaced S1a, BL-004 partially closed):** there is **no precomputed, offline question→`use_case_id` mapping** in any non-runtime source — the 105 questions and 46 catalog use cases are different corpora (0 exact `example_queries` matches). Question→use_case resolution otherwise happens only at runtime inside the router (`app.*`, forbidden to import). The generator deliberately does **not** reconstruct the router to fake a join.
>
> **BL-004 closeout (S1c, 2026-07-01):** offline mapping layer closed at **41 / 105** mapped rows (**64** `missing_authoritative_mapping` warnings remain as documented corpus gaps). Commits: `bf98c56` (S1a+S1a.1), `b454b9f` (S1b), `278a12b` (S1c). Report: `docs/evals/bl004_coverage_closeout_report.md`.
>
> **Forward roadmap S2–S6d (2026-07-01) — engineering complete.** Commits: `b365f1e` … `f3484f2`, `96d35d3` (plan closeout). **COE rollout configuration:** [`docs/coe/COE_ROLLOUT_CONFIGURATION.md`](../docs/coe/COE_ROLLOUT_CONFIGURATION.md). Remaining work is **not** all COE-driven — see classification below.

### Post-roadmap status classification (2026-07-01)

| Category | Items |
|----------|--------|
| **Engineering complete** | Guided hybrid; runtime enrichment loader; `node_trace` / state v2; MITRE preconditions; SPL template metadata; P3–P7 pilots; Answer Guard lab flag; session store file backend |
| **Corpus curation open** | **64** BL-004 `missing_authoritative_mapping` rows (`docs/evals/bl004_coverage_closeout_report.md`) |
| **COE rollout config** | Enable safe flags in `env/profiles/coe.env.example` — see COE rollout doc §2 |
| **Operator-only** | Live Splunk MCP activation, credentials, network, staging smoke |
| **Engineering / QA decision** | `AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED=true` after parity review |
| **COE sign-off required** | `email_phishing_header_review` / `endpoint_ransomware_impact_review` template `enabled=true` against real COE data |

**S1b (BL-004 detection-family anchors) — landed (`b454b9f`).** Four sample-only detection anchors + 30 curated mappings. Warnings **94 → 64**; mapped **11 → 41**.

**S1c (BL-004 closeout) — landed (`278a12b`).** Offline mapping closed at **41/105** mapped; **64** genuine corpus gaps documented in `docs/evals/bl004_coverage_closeout_report.md`.

**S2 (C1/C9 graph state v2 + node_trace) — landed (`b365f1e`).** `NodeTraceRecord` schema, `project_chat_pipeline_state_v2`, additive `ChatPipelineState` keys; flag-off byte-identical.

**S3 (B1/C3 runtime enrichment) — landed (`c25e145`).** `AI_SOC_RUNTIME_ENRICHMENT_ENABLED`, `UseCaseContentEnrichment` alias, `load_skill_enrichment()`.

**S4 (A2/B3/B4 MITRE preconditions) — landed (`0ef892a`).** `T1190`, `T1046` global preconditions; pilot behavior preserved.

**S5 (C2/C3 split routing) — landed (`463ce01`).** `AI_SOC_PIPELINE_SPLIT_ROUTING_NODES_ENABLED`, trace-only `routing_skill_nodes.py`.

**S6a (A3/B6 SPL templates) — landed (`3d87de9`).** Planned metadata for phishing + ransomware templates; governance tests.

**S6b (P3–P7 pilots) — landed (`aedc01c`).** Output-contract tests for pilot enrichment blocks.

**S6c (A6 answer guard lab) — landed (`2e23961`).** `AI_SOC_ANSWER_GUARD_LAB_ENABLED` alias OR-path.

**S6d (A5 session store) — landed (`f3484f2`).** File-backed pin store (`AI_SOC_SESSION_STORE_BACKEND=file`).

**COE rollout (docs, 2026-07-01):** [`docs/coe/COE_ROLLOUT_CONFIGURATION.md`](../docs/coe/COE_ROLLOUT_CONFIGURATION.md) — flag table, smoke checklist, classification. Canonical profile: `env/profiles/coe.env.example`. Code defaults in `config.py` remain safe/off; COE enables selected flags only via profile.

**S1b (C1/C9 spec, §R legacy id) — landed.** `docs/architecture/chat_pipeline_state_v2_and_node_trace.md` (spec only). Reconciliation findings vs the plan's C1/C9 text (all verified against code):

- `ChatPipelineState` has **62 fields**, not "~30" or the earlier **38** (`pipeline.py:282–345`; verify at implementation).
- Node sequence is **9 nodes with an `rag_only` branch**, not linear; LangGraph wrapper mirrors the same 9 functions for parity (`graph/chat_workflow.py`), gated by `langgraph_orchestration_enabled` (default false).
- `answer_guard_result` (C1) **duplicates** the existing `answer_guard` field — drop it.
- `final_answer_validation` already exists as a response field (`responses.py:393`); only its promotion to a state key is new.
- Per-node `node_trace` (C9) is **genuinely new** — current `control_plane_trace` is a single post-hoc assembly in finalize, not per-node emission. Spec recommends nesting `node_trace` under `control_plane_trace` to reuse its existing flag-gate + redaction path.
- `execution_decision` / `mitre_evidence_status` / `live_execution_skill` overlap existing fields — treat as derived/aliases to avoid two-writers-one-fact drift.
