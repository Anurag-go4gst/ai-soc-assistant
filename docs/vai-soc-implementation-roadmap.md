# V.AI SOC Implementation Roadmap

## Executive Summary

V.AI SOC should evolve into two aligned operating modes that share one response contract:

- Experience Center / demo mode: deterministic, scenario-backed, polished, architecture-faithful, and safe for customer demonstrations.
- Production replication mode: live evidence-backed, source-cited, guarded, and action-gated.

Both modes must return the same analyst-facing schema. The Experience Center uses controlled scenario evidence; production uses live `SourceEvidence`, governed RAG, local MITRE mappings, deterministic severity policy, guarded LLM synthesis, and validated action tiers.

The immediate implementation priority is to formalize the control plane before Stage 3K synthesis:

1. Query understanding and use-case registry.
2. Skill registry and skill-chain selection.
3. Production-grade Splunk MCP path and SPL template library.
4. Governed RAG and local MITRE KB.
5. Deterministic severity matrix.
6. Investigation lineage.
7. Evidence-based LLM synthesis.
8. Answer Guard.
9. Action capability tiers.
10. Production replication using the same response schema as Experience Center.

## Reviewer Corrections Incorporated

The following implementation corrections are binding for this roadmap:

- Use JSON registries for the first implementation. Do not introduce YAML unless a separate dependency, loader, schema validation, and malformed-file tests are added.
- Keep the existing router `SKILL_ENUM` unchanged initially. Add a separate skill registry with `routable` and `pipeline_stage` flags, then adapt the current router gradually.
- Make query understanding and the use-case registry the long-term source of truth for intent patterns. Do not duplicate keyword logic between router rules and catalog rules.
- Add all new top-level API fields as optional/nullable. Backend fields should default to `None`; frontend fields should be `field?: Type | null`.
- Keep SPL validation strict. Move toward template/SCD-driven policy instead of globally loosening indexes, sourcetypes, fields, or commands.
- Define canonical failed-login result fields as `failed_logins`, `distinct_users`, `first_seen`, `last_seen`, `src`, `host`, and `action`. Keep temporary aliases such as `fail_count` only during a deliberate migration.
- MITRE mappings must use explicit status values: `confirmed`, `supported`, `candidate`, and `requires_validation`. Failed-login spikes alone should not be marked confirmed.
- Answer Guard v1 must pass, block, or route to analyst review. It must not auto-correct generated answers.
- PGCIL / OT-adjacent production defaults should enforce air-gapped local/offline LLM use. Cloud LLM use is explicit opt-in for approved non-production or approved exception cases.
- MITRE KB must be local, versioned, release-dated, checksummed, and curated for initial use cases. Do not fetch MITRE live at runtime.
- Ticketing must remain provider-abstract. Do not hardcode ServiceNow into core ticketing or action-planning logic.
- Centralize time-window parsing in one utility.
- Add an Experience Center invariant: scenario lineage must not claim `current_mode_source=live` unless live scenario mode is explicitly enabled.
- Preserve the SAIA invariant: SAIA output is candidate-only, never execution evidence, and always requires AI-SOC validation before MCP execution.
- Add requested-output and output-template enums early to avoid schema/catalog/UI drift.
- Every phase must include verification: backend tests, frontend build when touched, harness default, harness with `TELEMETRY_MODE=none`, and `git diff --check`.

## Rationale

The current application already has the right safety shape: governed RAG flows through `SourceEvidence` and `StructuredContext`, SPL is validated deterministically, MCP execution is gated, SAIA is candidate-only, and final synthesis/answer guard are inert. The remaining risk is architectural drift: demo scenarios already render polished analyst responses while production chat returns evidence/context but no final analyst response.

This plan prevents drift by making demo and production share one schema, one lineage model, one evidence path, and one action model. Demo data stays deterministic; production swaps in live evidence and guarded synthesis without changing the UI contract.

## Expected End Result

When complete, V.AI SOC will support this production path:

```text
User query
-> query understanding / intent analysis
-> entity extraction
-> use-case classification
-> skill discovery / skill-chain selection
-> workflow planning
-> Splunk context / SCD check
-> candidate SPL generation or template selection
-> SPL validation
-> MCP tool selection
-> execution gate
-> Splunk MCP search
-> SourceEvidence
-> governed RAG / SOC KB retrieval
-> MITRE mapping
-> asset / CMDB enrichment
-> identity / IAM enrichment where available
-> StructuredContext
-> Context Sufficiency
-> evidence-based LLM synthesis
-> Answer Guard
-> final analyst response
-> action capability / next action
```

Experience Center will run the same shape with scenario evidence instead of live evidence:

```text
scenario evidence -> StructuredContext -> deterministic analyst_response
```

Production will run:

```text
live evidence -> StructuredContext -> LLM synthesis -> Answer Guard -> analyst_response
```

## Current State Assessment

| Capability | Current status | Production status | Next action |
|---|---|---|---|
| FastAPI + React/Vite app | Implemented | Usable scaffold | Preserve structure |
| `/chat` routing | Deterministic + LLM shadow comparison | Partial | Add `QueryUnderstandingResult` and use-case mapping |
| Skills | Four skills: `alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall` | Partial | Add formal registry and chains |
| Workflow plan | Implemented; steps stay `not_started`; execution false | Partial | Bind to use cases and skill chains |
| Stage 3C SPL generation | Stub/template-like generator | Demo/limited | Replace with governed SPL template library |
| SPL validation | Deterministic validator implemented | Partial | Add template rules and field allowlist enforcement |
| Splunk MCP discovery/tool selection | Implemented with gating | Partial | Add production decision record and evidence packaging |
| MCP execution | Disabled by default; mock gated execution possible | Real production execution not implemented | Keep gated until COE details are supplied |
| SAIA handling | Optional candidate-only/fallback policy | Advisory only | Preserve candidate-only boundary |
| Governed RAG | Wired into `SourceEvidence` and `StructuredContext` | Partial | Add retrieval record schema and MITRE/local KB strategy |
| Context Sufficiency Gate | Implemented; `synthesis_allowed=false` | Ready gate, no synthesis | Feed Stage 3K |
| LLM registry/settings UI | Inert config/status only | Not executing | Wire only in Stage 3K |
| Analyst response UI | Demo scenarios return `analyst_response` | Production chat does not yet | Make schema shared |
| Technical evidence path | Implemented/in progress | Partial | Separate from lineage and developer trace |
| Answer Guard | Config flag only | Missing | Stage 3L |
| Real remediation/actions | Not implemented | Missing | Keep blocked until action tiers/HIL exist |

Current safety guarantees to preserve:

- No final synthesis unless explicitly enabled later.
- No answer guard behavior exists yet.
- No real remediation.
- MCP execution stays gated.
- Candidate SPL is never executed unless validated and gate-approved.
- Rejected SPL has `normalized_spl=null`.
- RAG remains governed through `SourceEvidence` and `StructuredContext`.
- SAIA remains candidate/advisory only.
- LLMs never call MCP directly.
- `SourceEvidence` and `StructuredContext` remain the evidence boundary.

## Experience Center vs Production Architecture

### Shared Response Schema

Both modes should return one response envelope containing:

- `query_understanding`
- `selected_use_case`
- `selected_skill_chain`
- `workflow_plan`
- `candidate_spl`
- `spl_validation`
- `execution`
- `source_evidence`
- `structured_context`
- `context_sufficiency`
- `investigation_lineage`
- `analyst_response`
- `answer_guard`
- `action_capability`

All new fields must be optional/nullable until every producer and consumer has been migrated. Do not add a required top-level field unless `/chat`, demo scenarios, tests, harness fixtures, and frontend types are updated in the same commit.

### Experience Center

- Uses deterministic scenario evidence and fixtures.
- Produces polished `analyst_response`.
- Shows a clean technical evidence path.
- Keeps developer trace hidden/collapsed by default.
- Shows scenario source only inside lineage/evidence path, not as the main answer headline.
- Makes no real external calls unless explicitly enabled.
- Does not run final LLM synthesis or Answer Guard until later stages intentionally enable them.
- Must not claim `current_mode_source=live` in lineage unless a scenario is explicitly configured for live mode.

### Production

- Uses live Splunk MCP evidence after SPL validation and execution gates.
- Uses governed RAG from approved/current KB.
- Uses local/offline MITRE KB.
- Adds asset/CMDB/IAM enrichment when providers are configured.
- Applies deterministic severity matrix.
- Runs evidence-based LLM synthesis only after Context Sufficiency readiness and the synthesis flag allow it.
- Runs Answer Guard before returning visible analyst output.
- Uses the same UI and response schema as Experience Center.
- Defaults to air-gapped local/offline LLM providers for PGCIL / OT-adjacent deployments. Cloud providers require explicit approved opt-in.

## Phase 0 — Baseline Checkpoint

Implementation instructions:

- Record the baseline before behavior changes.
- Confirm current implemented commits/stages in project docs or PR description:
  - `c3d13cc` Stage 3J-B LLM registry settings/status UI.
  - `bc62e38` Stage 3J-C analyst UX and intent hygiene.
  - `8a17133` Stage 3J-D demo scenario harness.
  - `0dec248` scenario analyst response improvements.
  - `5e0af3c` analyst chat/evidence path polish.
- Capture current gaps:
  - production chat lacks final `analyst_response`.
  - formal query-understanding/use-case registry is missing.
  - skill registry is currently flat and incomplete.
  - SPL templates are not production-grade.
  - MITRE KB is not implemented as local structured data.
  - severity matrix is missing.
  - investigation lineage is missing.
  - final synthesis and answer guard are inert.
- Preserve `.claude/` as local tool state unless explicitly asked to version it.

Deliverable:

- Baseline table in docs or PR description.
- No runtime behavior change.

## Phase 1 — Query Understanding + Use-Case Registry

Before skill selection, the system must understand the query.

Add model: `QueryUnderstandingResult`

Fields:

- `raw_query`
- `normalized_query`
- `primary_intent`
- `secondary_intents`
- `requested_output_type`
- `entities`
- `ambiguity_flags`
- `confidence`
- `clarification_needed`
- `clarification_question`
- `mapped_use_case_ids`

Add enums:

- `RequestedOutputType`: `investigation`, `spl`, `sop`, `mitre_mapping`, `summary`, `note`, `action_plan`, `clarification`
- `OutputTemplate`: `investigation_answer`, `spl_response`, `sop_response`, `mitre_mapping_response`, `clarification_response`, `note_response`

Entity fields:

- `asset`
- `host`
- `user`
- `source_ip`
- `destination_ip`
- `time_window`
- `index`
- `sourcetype`
- `alert_id`
- `event_type`

Add files:

- `backend/app/query_understanding/models.py`
- `backend/app/query_understanding/parser.py`
- `backend/app/query_understanding/time_window.py`
- `backend/app/use_cases/models.py`
- `backend/app/use_cases/catalog.json`
- `backend/app/use_cases/registry.py`

Implementation instructions:

- Start with deterministic parsing.
- Make LLM-assisted parsing advisory only in a later stage.
- Ambiguous MITRE asks without alert context must ask clarification and must not generate SPL.
- SOP/playbook prompts must route to knowledge recall and not generate SPL.
- Use case mapping must happen before skill-chain selection.
- Centralize time-window parsing and normalization in `time_window.py`; do not parse relative dates separately in router, SPL rendering, and UI code.
- Use the registry as the future source of truth for intent patterns. The first implementation should adapt existing router behavior rather than rewrite it.

Before Stage 3K:

- This phase is must-have.

## Phase 2 — Skill Registry + Skill Chain Selection

Do not replace the current flat router enum in the first implementation. Keep the existing deterministic routing subset stable and add formal registry models alongside it.

Add models:

- `SkillRegistry`
- `SkillDefinition`
- `SkillSelectionResult`
- `SkillChain`

Initial skills:

1. `query_understanding`
2. `attack_discovery`
3. `spl_generation`
4. `spl_validation`
5. `knowledge_recall`
6. `mitre_mapping`
7. `alert_summary`
8. `investigation_notes`
9. `evidence_collection`
10. `asset_enrichment`
11. `identity_enrichment`
12. `network_enrichment`
13. `context_sufficiency`
14. `synthesis`
15. `answer_guard`
16. `action_planning`
17. `ticket_drafting`
18. `out_of_scope`

Classify registry entries with:

- `routable: true/false`
- `pipeline_stage: true/false`

Initial routable skills:

- `attack_discovery`
- `spl_generation`
- `knowledge_recall`
- `mitre_mapping`
- `alert_summary`
- `investigation_notes`
- `out_of_scope`

Initial non-routable pipeline stages:

- `query_understanding`
- `spl_validation`
- `evidence_collection`
- `context_sufficiency`
- `synthesis`
- `answer_guard`
- `action_planning`

Each skill should define:

- `skill_id`
- `display_name`
- `purpose`
- `input_contract`
- `output_contract`
- `allowed_tools`
- `blocked_tools`
- `required_evidence`
- `supported_use_cases`
- `default_workflow`
- `hil_policy`
- `action_tier_allowed`

Example chains:

- Failed login spike:
  `query_understanding -> attack_discovery -> spl_generation -> spl_validation -> evidence_collection -> knowledge_recall -> mitre_mapping -> asset_enrichment -> context_sufficiency -> synthesis -> answer_guard -> action_planning`
- SOP request:
  `query_understanding -> knowledge_recall -> context_sufficiency`
- Generate SPL:
  `query_understanding -> spl_generation -> spl_validation`

Implementation instructions:

- Skill selection should use query understanding and selected use case.
- Record rejected alternatives and why they were rejected.
- Expose selected chain in investigation lineage.
- Keep LLM-assisted selection advisory-only and unable to override deterministic policy.
- Ambiguous queries should return clarification state.
- Add an adapter from the registry to existing router/workflow behavior. Do not expand `SKILL_ENUM` directly until routing tests and workflow tests are migrated.

Before Stage 3K:

- This phase is must-have.

## Phase 3 — Production-Grade Splunk MCP Path + SPL Template Library

Production Splunk behavior must be governed by the Splunk Context Document.

Controls:

- Allowed indexes.
- Allowed sourcetypes.
- Field mappings.
- Action values.
- User/asset/source fields.
- Saved searches.
- Macros/lookups/data models.
- Explicit exclusions.

Runtime rules:

- Runtime does not freely inspect the live Splunk environment.
- SPL is template-selected or generated from approved use-case context.
- SPL is always validated before execution.
- SAIA is candidate-only/advisory.
- Internal SPL template fallback is deterministic.
- Saved searches require allowlist and HIL.
- Only validated `normalized_spl` can reach the MCP execution gate.
- Do not loosen global SPL validation to support new template families.
- Each template must declare its own allowed indexes, sourcetypes, required fields, allowed commands, required time bounds, result limits, and validation expectations.
- A new template is not complete unless its SCD/allowlist extension and validator tests are included in the same commit.
- Templates for firewall, DNS, EDR, VPN, and OT use cases remain `planned` until their SCD values exist.

Add SPL templates:

- `auth_failed_login_spike`
- `auth_success_after_failure`
- `auth_new_source_ip`
- `auth_account_lockout_trend`
- `privileged_account_failure`
- `after_hours_login_critical_asset`
- `vpn_failure_spike`
- `firewall_deny_spike`
- `dns_beaconing_candidate`
- `edr_suspicious_process`

Each template should define:

- `template_id`
- `use_case_id`
- `required_entities`
- `default_time_window`
- `spl_text`
- `returned_fields`
- `validation_rules`
- `result_limits`
- `severity_inputs`
- `answer_sections_supported`

For failed-login spike, production SPL must return:

- `host`
- `src`
- `failed_logins`
- `distinct_users`
- `first_seen`
- `last_seen`
- `action`

Canonical failed-login fields are:

- `failed_logins`
- `distinct_users`
- `first_seen`
- `last_seen`
- `src`
- `host`
- `action`

Migration rule:

- If existing fixtures or harness expectations use `fail_count`, either migrate all templates, fixtures, SourceEvidence preview rows, visible UI, and harness expectations in one commit, or provide temporary compatibility aliases such as `fail_count -> failed_logins`.

Add `McpToolDecisionRecord`:

- `selected_server`
- `available_tools`
- `selected_tool`
- `why_selected`
- `input_summary`
- `policy_result`
- `latency`
- `response_summary`
- `result_count`
- `fields_returned`
- `source_evidence_ref`

Before Stage 3K:

- This phase is must-have for production parity.

## Phase 4 — Governed RAG + Local MITRE KB Strategy

### Governed RAG

Every retrieval record should include:

- `collection`
- `query`
- `filters`
- `selected_doc_id`
- `title`
- `version`
- `approval_status`
- `status`
- `source_refs`
- `section`
- `excerpt`
- `allowed_use`
- `why_selected`
- `used_answer_sections`

Rules:

- Only approved/current KB entries may support visible answers.
- Draft and superseded content must not reach synthesis unless explicitly allowed by policy.
- RAG still flows only through `SourceEvidence` and `StructuredContext`.

### MITRE

MITRE must be local/offline for air-gapped deployment.

Add files:

- `backend/app/threat/mitre_kb.py`
- `backend/app/threat/mitre_attack_subset.json`
- later: `backend/app/threat/mitre_attack_ics_subset.json`

Metadata must include:

- ATT&CK domain, initially `enterprise`.
- ATT&CK version.
- release date.
- checksum.
- curated use-case mappings.

MITRE KB fields:

- `technique_id`
- `name`
- `tactic`
- `description`
- `detection_patterns`
- `evidence_requirements`
- `candidate_vs_confirmed_rules`
- `related_use_cases`
- `recommended_pivots`

Failed-login rules:

- `T1110.001 Password Guessing` is `supported` or high-confidence `candidate` when repeated failed authentication evidence exists.
- `T1110.001` becomes `confirmed` only when validation clears likely benign causes such as scanner activity, misconfiguration, expired credentials, or approved automation.
- `T1078 Valid Accounts` is `candidate` unless success-after-failure or other valid-account evidence exists.

MITRE mapping statuses:

- `confirmed`
- `supported`
- `candidate`
- `requires_validation`

Before Stage 3K:

- Local MITRE grounding is must-have.

## Phase 5 — Severity Matrix / Risk Policy

Add deterministic severity.

Models:

- `SeverityPolicy`
- `SeverityDecision`

File:

- `backend/app/risk/severity_matrix.json`

Fields:

- `scenario` / `use_case`
- `severity_levels`
- `thresholds`
- `evidence_conditions`
- `escalation_conditions`
- `why_not_higher`
- `matched_rules`
- `missing_evidence`

Example: `auth_failed_login_spike`

P1 Critical:

- `success_after_failure=true`
- `privileged_account_impacted=true`
- `critical_asset=true`
- `confirmed_success=true`

P2 High:

- `failed_logins >= 50`
- `distinct_sources >= 2`
- `distinct_users >= 3`

P3 Medium:

- `failed_logins >= 10`
- `distinct_sources >= 1`

P4 Low:

- `known_benign_source=true`

Implementation instructions:

- Severity matrices should be per use case.
- Severity decision must be visible in lineage.
- Answer Guard must validate visible severity against the matrix.
- Recommended actions should derive priority from severity.
- Severity must degrade gracefully when enrichment is missing.
- If required evidence for P1/P2 is absent, cap severity, record `missing_evidence`, and populate `why_not_higher`.
- Demo P1 scenarios must include grounded scenario asset, identity, session, or post-login evidence. Do not infer criticality, privilege, or success evidence.
- The current failed-login spike P2 posture is appropriate unless success-after-failure, privileged-account, critical-asset, or post-login malicious activity evidence exists.

Before Stage 3K:

- This phase is must-have because the LLM must not invent severity.

## Phase 6 — Investigation Lineage / Production Path Explanation

Add a new analyst-readable section: "How this answer was produced".

This must be separate from:

- Technical evidence path: clean tool/evidence audit.
- Developer trace: raw internals.

Add `InvestigationLineage` fields:

- `lineage_id`
- `query_understanding`
- `selected_use_case`
- `selected_skill_chain`
- `workflow_summary`
- `splunk_context`
- `spl_generation`
- `spl_validation`
- `mcp_tool_decision`
- `mcp_response_summary`
- `source_evidence_summary`
- `rag_decision`
- `mitre_mapping_decision`
- `severity_decision`
- `asset_context_decision`
- `structured_context_summary`
- `context_sufficiency_summary`
- `llm_synthesis_status`
- `answer_guard_status`
- `final_response_mapping`
- `action_capability`

Each stage includes:

- `status`: `complete`, `partial`, `skipped`, `planned`, `blocked`
- `visible_label`
- `explanation`
- `technical_output`
- `produced_answer_sections`
- `current_mode_source`: `live`, `scenario`, `config`, `derived`, `planned`
- `production_equivalent`

UI instructions:

- Collapsed by default.
- Stepper/timeline layout.
- Status icons.
- Source refs.
- Produced answer sections.
- Demo scenario source appears only inside lineage/evidence path.
- Developer trace remains hidden/collapsed.

Before Stage 3K:

- This phase is must-have for demo/production alignment.

## Phase 7 — Evidence-Based LLM Synthesis / Stage 3K

Do not implement Stage 3K until Phases 1-6 are stable.

LLM input may include only:

- `StructuredContext`
- `SourceEvidence` summaries
- approved RAG excerpts
- MITRE candidates
- severity decision
- context sufficiency result
- missing evidence
- prohibited claims
- output schema

LLM input must not include:

- raw unrestricted Splunk dumps
- secrets
- credentials
- draft/unapproved RAG docs
- hidden developer trace

LLM output schema under `analyst_response`:

- `severity_label`
- `finding_title`
- `lead`
- `splunk_results_table`
- `mitre_mappings`
- `retrieved_playbook`
- `foundation_sec_analysis`
- `recommended_actions`
- `missing_evidence`
- `used_source_refs`
- `unsupported_claims`

Implementation instructions:

- Select synthesis role from LLM settings.
- Support Foundation-Sec instruct and local/openai-compatible providers.
- Air-gapped mode allows only local/offline configured providers.
- If disabled, return deterministic fallback response using scenario/template response mapping.
- Do not let the LLM call tools.
- Do not let the LLM override SPL validation, severity policy, MITRE support, or action policy.

Synthesis may run only when:

- final synthesis flag is enabled.
- context sufficiency readiness is true.
- source refs exist.
- no sensitive leak flags exist.
- provider is allowed by environment mode.
- output schema validation passes.

## Phase 8 — Answer Guard / Stage 3L

Answer Guard runs after synthesis and before visible answer.

Checks:

- IPs in answer exist in `SourceEvidence`.
- Counts match evidence.
- Users/hosts exist in evidence.
- SOP citations exist and are approved.
- MITRE technique is supported by MITRE decision.
- Severity matches severity matrix.
- Recommendations do not claim uncollected evidence.
- No banned internal terms appear in visible answer.
- No unsupported asset/CMDB/IAM claims appear.
- No unsafe action recommendation exceeds the allowed tier.

Output:

- `guard_status`
- `passed_checks`
- `failed_checks`
- `blocked_reason`
- `analyst_review_required`

Default behavior:

- If guard fails, block or require analyst review.
- Do not silently return unsupported claims.
- Do not auto-correct in Answer Guard v1. Guarded rewrite/correction can be considered only as a later Stage 3L-B with strict claim preservation and its own guard pass.

## Phase 9 — Action Capability Tiers

Define what chat can do.

Tiers:

- Tier 0 Inform: summarize, explain, map MITRE, show SOP.
- Tier 1 Prepare: generate SPL, draft investigation note, draft ticket, draft containment plan.
- Tier 2 Human-approved execute: run saved search, create ticket, assign case, enrich alert.
- Tier 3 Controlled remediation: block IP, disable user, isolate endpoint; requires RBAC + HIL + policy + audit.
- Tier 4 Not allowed: destructive or irreversible action without approval.

Current supported target:

- Tier 0 partial.
- Tier 1 partial for SPL generation and guidance.
- Tier 2 mock/gated only.
- Tier 3 and Tier 4 not implemented.

Add models:

- `ActionCapability`
- `ActionCapabilityTier`
- `ActionPolicyDecision`
- `HumanApprovalRequirement`

UI instructions:

- Show currently available tier.
- Show why higher tiers are unavailable.
- Show required provider/config/HIL/audit for future tiers.

## Phase 10 — Production Replication With Same Response Schema

Replication principle:

- Experience Center: `scenario evidence -> analyst_response`
- Production: `live evidence -> StructuredContext -> LLM synthesis -> Answer Guard -> analyst_response`

Same across modes:

- UI
- response schema
- evidence path sections
- lineage model
- action model

Different across modes:

- data source
- evidence source
- model execution
- guard result

Implementation instructions:

- Add schema drift tests comparing scenario-backed and production-shaped responses.
- Keep demo scenario payloads production-shaped.
- Keep production response renderable by the same `AnalystResponseCard`.
- Do not create a demo-only schema branch.

## Proposed Backend Models and Files

Add:

- `backend/app/query_understanding/models.py`
- `backend/app/query_understanding/parser.py`
- `backend/app/query_understanding/time_window.py`
- `backend/app/use_cases/models.py`
- `backend/app/use_cases/catalog.json`
- `backend/app/use_cases/registry.py`
- `backend/app/skills/models.py`
- `backend/app/skills/catalog.json`
- `backend/app/skills/selector.py`
- `backend/app/spl/templates.json`
- `backend/app/spl/template_renderer.py`
- `backend/app/spl/template_registry.py`
- `backend/app/threat/mitre_kb.py`
- `backend/app/threat/mitre_attack_subset.json`
- `backend/app/risk/severity_matrix.json`
- `backend/app/risk/severity_policy.py`
- `backend/app/lineage/models.py`
- `backend/app/lineage/builder.py`
- `backend/app/synthesis/models.py`
- `backend/app/synthesis/evidence_prompt.py`
- `backend/app/answer_guard/models.py`
- `backend/app/answer_guard/guard.py`
- `backend/app/actions/models.py`
- `backend/app/actions/capability_policy.py`

Extend:

- `backend/app/schemas/responses.py`
- `backend/app/api/routes_chat.py`
- `backend/app/demo/scenarios.py`
- `backend/app/evidence/context_structurer.py`
- `backend/app/evidence/source_evidence.py`
- `backend/app/orchestration/workflow_planner.py`
- `backend/app/orchestration/mcp_tool_selector.py`

## Proposed Frontend Components and Pages

Add:

- `InvestigationLineagePanel`
- `LineageTimeline`
- `UseCaseBadge`
- `SkillChainStepper`
- `SeverityDecisionPanel`
- `MitreMappingPanel`
- `ActionCapabilityPanel`
- `AnswerGuardPanel`
- `ProductionEvidenceSummary`
- `ScenarioEvidenceSummary`

Extend:

- `AnalystResponseCard` to render production and demo `analyst_response`.
- `EvidencePanel` for RAG/MITRE/severity/source refs.
- `Stage3DTracePanel` into a cleaner split:
  - analyst lineage
  - technical evidence path
  - developer trace
- `SettingsPage` to show synthesis, answer guard, and action tiers as disabled/planned until implemented.

## Use-Case Registry Proposal

Each use case defines:

- `use_case_id`
- `display_name`
- `category`
- `intent_patterns`
- `example_queries`
- `required_entities`
- `optional_entities`
- `default_time_window`
- `primary_skill`
- `secondary_skills`
- `required_sources`
- `optional_sources`
- `default_spl_template`
- `rag_collections`
- `mitre_candidates`
- `severity_policy`
- `action_capability_tier`
- `output_template`

Initial catalog:

| ID | Display name | Category | Primary skill | Default template |
|---|---|---|---|---|
| `auth_failed_login_spike` | Failed login spike | Authentication | `attack_discovery` | `auth_failed_login_spike` |
| `auth_success_after_failure` | Successful login after failures | Authentication | `attack_discovery` | `auth_success_after_failure` |
| `auth_new_source_ip_login` | New source IP login | Authentication | `attack_discovery` | `auth_new_source_ip` |
| `auth_impossible_travel` | Impossible travel | Authentication | `attack_discovery` | later |
| `auth_privileged_login_anomaly` | Privileged account login anomaly | Authentication | `attack_discovery` | `privileged_account_failure` |
| `auth_service_account_abnormal_login` | Service account abnormal login | Authentication | `attack_discovery` | later |
| `auth_account_lockout_trend` | Account lockouts over time | Authentication | `spl_generation` | `auth_account_lockout_trend` |
| `auth_mfa_failure_spike` | MFA failure spike | Authentication | `attack_discovery` | later |
| `auth_disabled_account_login` | Login from disabled account | Authentication | `attack_discovery` | later |
| `auth_after_hours_critical_asset` | After-hours login to critical asset | Authentication | `attack_discovery` | `after_hours_login_critical_asset` |
| `net_firewall_deny_spike` | Firewall deny spike | Network | `attack_discovery` | `firewall_deny_spike` |
| `net_new_outbound_destination` | New outbound destination | Network | `attack_discovery` | later |
| `net_port_scanning` | Suspicious port scanning | Network | `attack_discovery` | later |
| `net_east_west_anomaly` | East-west traffic anomaly | Network | `attack_discovery` | later |
| `net_blocked_region_connection` | Connection to blocked country/region | Network | `attack_discovery` | later |
| `net_repeated_critical_asset_connections` | Repeated connection attempts to critical asset | Network | `attack_discovery` | later |
| `net_vpn_login_anomaly` | VPN login anomaly | Network | `attack_discovery` | `vpn_failure_spike` |
| `dns_unusual_query_volume` | Unusual DNS query volume | Network | `attack_discovery` | later |
| `dns_tunneling_candidate` | DNS tunneling candidate | Network | `attack_discovery` | later |
| `dns_beaconing_candidate` | Beaconing pattern candidate | Network | `attack_discovery` | `dns_beaconing_candidate` |
| `edr_suspicious_process` | Suspicious process execution | Endpoint | `attack_discovery` | `edr_suspicious_process` |
| `edr_powershell_suspicious_command` | PowerShell suspicious command | Endpoint | `attack_discovery` | later |
| `edr_new_service_creation` | New service creation | Endpoint | `attack_discovery` | later |
| `edr_scheduled_task_creation` | Scheduled task creation | Endpoint | `attack_discovery` | later |
| `edr_lateral_movement_candidate` | Lateral movement candidate | Endpoint | `attack_discovery` | later |
| `edr_credential_dumping_signal` | Credential dumping signal | Endpoint | `attack_discovery` | later |
| `edr_malware_alert_summary` | Malware alert summarization | Endpoint | `alert_summary` | later |
| `edr_isolation_recommendation` | Endpoint isolation recommendation | Endpoint | `action_planning` | none |
| `soc_show_sop` | Show SOP/playbook | SOC Workflow | `knowledge_recall` | none |
| `soc_generate_spl` | Generate SPL | SOC Workflow | `spl_generation` | selected by target use case |
| `soc_explain_spl` | Explain SPL | SOC Workflow | `knowledge_recall` | none |
| `soc_optimize_spl` | Optimize SPL | SOC Workflow | `spl_generation` | selected by SPL |
| `soc_map_alert_mitre` | Map alert to MITRE | SOC Workflow | `mitre_mapping` | none |
| `soc_create_investigation_note` | Create investigation note | SOC Workflow | `investigation_notes` | none |
| `soc_summarize_alert_evidence` | Summarize alert evidence | SOC Workflow | `alert_summary` | none |
| `soc_recommend_next_pivots` | Recommend next pivots | SOC Workflow | `action_planning` | none |
| `soc_draft_ticket` | Draft ticket | SOC Workflow | `ticket_drafting` | none |
| `soc_compare_past_incidents` | Compare current alert with past incidents | SOC Workflow | `knowledge_recall` | none |
| `ot_unexpected_command` | Unexpected command to OT/grid asset | OT | `attack_discovery` | later |
| `ot_it_to_ot_auth_anomaly` | IT-to-OT authentication anomaly | OT | `attack_discovery` | later |
| `ot_critical_asset_after_hours` | Critical asset after-hours access | OT | `attack_discovery` | later |
| `ot_protocol_anomaly` | OT protocol anomaly | OT | `attack_discovery` | later |

## Skill Registry Proposal

Use `backend/app/skills/catalog.json`.

Minimum entry shape:

- `skill_id`
- `display_name`
- `purpose`
- `routable`
- `pipeline_stage`
- `input_contract`
- `output_contract`
- `allowed_tools`
- `blocked_tools`
- `required_evidence`
- `supported_use_cases`
- `default_workflow`
- `hil_policy`
- `action_tier_allowed`

Selection rules:

- Query understanding maps to use-case candidates.
- Use case selects primary skill and optional secondary skills.
- Skill selector records alternatives and rejection reasons.
- LLM-assisted selection may be added later as advisory-only.
- Ambiguity returns `clarification_needed=true` and does not generate SPL/action.
- Existing router rules should be imported from or adapted to registry patterns over time so intent logic has one source of truth.

## SPL Template Library Proposal

Use `backend/app/spl/templates.json`.

Template fields:

- `template_id`
- `use_case_id`
- `required_entities`
- `default_time_window`
- `spl_text`
- `returned_fields`
- `validation_rules`
- `result_limits`
- `severity_inputs`
- `answer_sections_supported`

Validation additions:

- Per-template policy declares allowed indexes, sourcetypes, fields, and commands.
- Assert all template fields are SCD-allowlisted.
- Assert all returned fields are declared.
- Assert result limits and time bounds exist.
- Assert rejected SPL has `normalized_spl=null`.
- Assert candidate-only SAIA output never enters execution evidence.

## MITRE KB Proposal

Rules:

- No runtime internet.
- Local files include version/date/checksum.
- Technique support states: `confirmed`, `supported`, `candidate`, `requires_validation`, `not_supported`.
- MITRE mappings must cite evidence refs and MITRE KB refs.
- `T1110.001` is supported/high-confidence candidate for failed-login spike unless benign alternatives are cleared.
- `T1078` is not confirmed without success evidence.

## Severity Matrix Proposal

Decision output:

- `severity_label`
- `matched_rules`
- `why_not_higher`
- `missing_evidence`
- `source_refs`
- `recommended_priority`
- `allowed_action_tier`

Answer Guard must compare visible severity to `SeverityDecision`.

## Investigation Lineage Proposal

Lineage is analyst-readable and collapsed by default.

Production lineage shows:

- actual live tool calls
- model used
- source refs
- guard result

Lineage must not expose:

- secrets
- raw prompts
- credentials
- raw unrestricted logs

## LLM Synthesis Plan

Stage 3K implementation order:

1. Define `SynthesisInput` and `SynthesisOutput`.
2. Build deterministic synthesis fallback from `StructuredContext`.
3. Add provider resolution from existing LLM registry.
4. Add prompt/input minimization and prohibited-claims section.
5. Add disabled-mode behavior preserving current safety.
6. Add `analyst_response.used_source_refs` and `unsupported_claims`.
7. Keep `synthesis_allowed=false` until flag, readiness, and safety checks pass.

## Answer Guard Plan

Stage 3L implementation order:

1. Schema/shape guard.
2. Evidence claim guard for IP/user/host/count/time fields.
3. SOP/RAG citation guard.
4. MITRE support guard.
5. Severity matrix guard.
6. Action tier guard.
7. Visible-answer language guard.
8. Block-or-review behavior.

## Action Capability Plan

Add action tier policy and UI display.

Current implementation target:

- Tier 0 and Tier 1 only.
- Tier 2 only for explicitly gated saved searches/ticket drafts later.
- Tier 3 remediation remains planned/blocked.

## Testing Strategy

Backend tests:

- Query understanding for varied phrasing and entity extraction.
- Time-window parsing for relative and absolute windows, including deployment timezone handling.
- Use-case registry loading and required fields.
- Skill chain selection examples.
- Ambiguous MITRE request asks clarification.
- SOP/playbook routes to `knowledge_recall`, no SPL.
- SPL template rendering and validation.
- Failed-login template returns required UI fields.
- Rejected SPL has `normalized_spl=null`.
- MCP tool decision record blocks unsafe/user-requested tools.
- SAIA remains candidate-only.
- RAG retrieval records include approval/version/source refs.
- MITRE offline lookup works without internet.
- `T1110.001` is supported/candidate for failed-login spike until benign alternatives are cleared.
- `T1078` is not confirmed without success evidence.
- Severity matrix decisions and `why_not_higher`.
- Lineage stage statuses for demo and production-shaped responses.
- Experience Center lineage never reports `current_mode_source=live` unless live scenario mode is explicitly enabled.
- SAIA candidate-only invariants remain green when templates are added.
- Synthesis disabled by default.
- Answer Guard claim mismatch failures.
- Scenario schema equals production schema shape.

Frontend tests/build:

- `npm run build`
- Analyst response renders with demo and production-shaped payloads.
- Lineage collapsed by default.
- Technical evidence path separate from developer trace.
- Action capability displays disabled/planned states.
- Long labels/fields do not overlap.

Harness:

- `python3 -m test_harness.harness.runner --json`
- `TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json`
- Preserve expected 6/6 baseline unless intentionally expanded.

Diff hygiene:

- `git diff --check`

Backend regression:

```bash
cd backend
python3 -m pytest
```

Frontend regression:

```bash
cd frontend
npm run build
```

## Commit Breakdown

Recommended commits:

1. Baseline/schema planning foundation.
2. Query understanding + use-case registry.
3. Skill registry + chain selection.
4. SPL template library + SCD binding.
5. MITRE KB + severity policy.
6. Investigation lineage.
7. Experience Center schema alignment.
8. Production evidence path parity.
9. Stage 3K synthesis.
10. Stage 3L Answer Guard.
11. Action capability tiers.

Do not mix deployment, connector readiness, UI polish, and synthesis execution in one commit.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Demo and production drift | Shared response schema and schema parity tests |
| LLM invents severity or facts | Severity matrix, evidence-only synthesis, Answer Guard |
| SAIA output treated as evidence | Keep `splunk_mcp_saia` candidate-only |
| Live Splunk metadata overreach | Use frozen SCD; no runtime free discovery |
| MITRE internet dependency | Local/offline MITRE KB with checksum/version |
| Sensitive fields leak to LLM | Field allowlist, masking, SourceEvidence summaries only |
| Ambiguous request triggers SPL | Query-understanding clarification gate |
| Action tiers creep into remediation | Tier model, HIL, default blocked Tier 3 |
| Frontend exposes raw internals | Separate lineage, technical evidence, developer trace |

## Open Questions

Deferred with defaults:

- Exact production Splunk MCP URL, transport, auth, tool names, and argument schema.
- COE-approved SCD values beyond current placeholders.
- Exact asset/CMDB/IAM provider interfaces.
- Preferred MITRE Enterprise/ICS version to freeze.

Default assumptions:

- Use local/offline MITRE.
- Use deterministic rule-first selection.
- Keep synthesis and answer guard disabled until explicitly enabled.
- Keep remediation out of scope until after Stage 3L.
- Use abstract `ProviderType=ticketing`; ServiceNow can be a later provider implementation, not core logic.
- Enforce air-gapped local/offline LLM defaults for PGCIL / OT-adjacent production.

## Recommended Immediate Next Implementation Step

Implement first: Phase 1 plus minimal Phase 2 foundation.

Concrete first slice:

- Add `QueryUnderstandingResult`.
- Add `use_cases/catalog.json` with the use cases above.
- Add deterministic query parser for authentication/SOP/SPL/MITRE examples.
- Add formal skill registry models without changing execution behavior or expanding `SKILL_ENUM`.
- Return query understanding and selected use case in `/chat` and demo scenario payloads.
- Add tests for varied query phrasing, clarification behavior, and no-SPL SOP/MITRE hygiene.

This gives Stage 3K a stable, auditable intent/use-case/skill-chain foundation without enabling synthesis, answer guard, real execution, or remediation.
