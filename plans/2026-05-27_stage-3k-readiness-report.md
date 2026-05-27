# Stage 3K Readiness Report

Date: 2026-05-27

Scope: repo-truth inspection before starting Stage 3K for V.AI SOC / AI-SOC / OT-SOC. This report is based on current code, git state, and local verification commands, not only documentation.

## 1. Git State

Current branch:

```text
master
```

Current `git status --short`:

```text
 M backend/app/demo/scenarios.py
 M backend/app/lineage/builder.py
 M backend/app/tests/test_demo_scenarios_stage3jd.py
 M frontend/src/components/ChatInput.tsx
 M frontend/src/components/ChatPanel.tsx
 M frontend/src/pages/ChatPage.tsx
?? .claude/
```

Latest 12 commits:

```text
4ec8b03 Stage 3J-UI: Calm canvas, widen chat, cap prose, add favicon
7f53a58 Stage 3J-J.3: Show governed Foundation-sec outputs in Experience Center
59be234 Docs: sync CLAUDE.md, AGENTS.md, hooks.md to current stages
1e39456 Stage 3J-K0.1: Clean up LLM and MCP settings status UI
91f7b0e Stage 3J-J.2: Surface investigation lineage reveal in chat UI
05c95bc Stage 3J-K0: Govern LLM-assisted routing and tool selection
2fefd10 Calibrate Experience Center responses to governed LLM behavior
9ba7ab7 Stage 3J-I.3: Update LLM prompt contracts and role suitability
5cf271e Stage 3J-I.2: Add dormant semantic LLM guard rules
db37003 Stage 3J-I.1: Add guarded LLM adapter and active overrides
3088c31 Add MCP and LLM connection verification
9622358 Stage 3J-E/F: Add query, governance, lineage, and production metadata scaffolding
```

Readiness note: the working tree is dirty. Do not start Stage 3K implementation until the modified backend and frontend files are committed, reverted, or explicitly deferred. `.claude/` is local tool state and should remain untracked unless explicitly requested.

## 2. Stage 3J-J.3 Status

Status: implemented and committed.

Commit:

```text
7f53a588bccd6d2ed6f45d015d2136d5efadf91b
Stage 3J-J.3: Show governed Foundation-sec outputs in Experience Center
```

Files changed in the commit:

```text
backend/app/demo/foundation_sec_fixtures.py
backend/app/demo/scenarios.py
backend/app/schemas/responses.py
backend/app/tests/test_demo_scenarios_stage3jd.py
frontend/src/components/AnalystResponseCard.tsx
frontend/src/components/ChatBubble.tsx
frontend/src/types/api.ts
```

Fixture path:

```text
backend/app/demo/foundation_sec_fixtures.py
```

Backend schema fields/classes added:

- `FoundationSecCapturedOutput`
- `FoundationSecGovernanceOverride`
- `FoundationSecGovernedAnalysis`
- `FoundationSecGovernance`
- `PlaceholderResponse.foundation_sec_governance`

Frontend types added:

- `FoundationSecCapturedOutput`
- `FoundationSecGovernanceOverride`
- `FoundationSecGovernedAnalysis`
- `FoundationSecGovernance`
- optional `foundation_sec_governance`

UI rendering location:

- `frontend/src/components/AnalystResponseCard.tsx` renders `Foundation-sec governed analysis`.
- `frontend/src/components/AnalystResponseCard.tsx` renders collapsed `Model output governance`.
- `frontend/src/components/ChatBubble.tsx` passes `message.trace.foundation_sec_governance` to the analyst response card.

Tests:

- `backend/app/tests/test_demo_scenarios_stage3jd.py`
- Current working tree has 25 Stage 3J-J demo scenario tests after follow-up consistency fixes.

Experience Center LLM behavior:

- Experience Center does not call a live LLM.
- `backend/app/demo/scenarios.py` uses `foundation_sec_governance_for(scenario.scenario_id)`.
- `backend/app/demo/foundation_sec_fixtures.py` returns static captured fixture data with `live_llm_called=false`.
- The primary answer uses governed summaries and governance overrides. It does not expose full raw LLM output as the final answer.

Uncommitted follow-up currently present:

- `backend/app/demo/scenarios.py`
- `backend/app/lineage/builder.py`
- `backend/app/tests/test_demo_scenarios_stage3jd.py`

These appear to be Stage 3J-J.3 consistency/readiness fixes, not Stage 3K work. They align demo severity, selected use case, MCP discovery intent, and lineage wording with the governed Foundation-sec fixture story. They should be committed before Stage 3K or intentionally deferred.

## 3. Stage 3J-K0 Status

Status: implemented and committed.

Commit:

```text
05c95bc5e9f5704472bfb2c8749bc1b3d43a48ee
Stage 3J-K0: Govern LLM-assisted routing and tool selection
```

Files changed in the commit:

```text
CLAUDE.md
backend/app/api/routes_chat.py
backend/app/api/routes_settings.py
backend/app/config.py
backend/app/orchestration/evidence_mcp_mapping.py
backend/app/routing/governance.py
backend/app/routing/llm_planner.py
backend/app/routing/route_adjudicator.py
backend/app/routing/skill_router.py
backend/app/schemas/responses.py
backend/app/splunk/spl_services.py
backend/app/tests/test_evidence_mcp_mapping_stage3jk0.py
backend/app/tests/test_route_compare.py
backend/app/tests/test_routing_governance_stage3jk0.py
backend/app/tests/test_spl_optimization_stage3jk0.py
plans/2026-05-26_1955_stage-3j-k0-llm-assisted-routing-governance.md
```

Routing modes:

- `deterministic_only`
- `llm_shadow_only`
- `llm_assisted_semantic`
- `llm_primary_lab`

Default routing mode:

```text
llm_assisted_semantic
```

Feature flags / env-backed settings:

- `ROUTING_MODE`
- `ROUTING_LAB_LLM_PRIMARY_ENABLED`
- `ROUTING_DETERMINISTIC_THRESHOLD`
- `ROUTING_LLM_SHADOW_ENABLED`
- `ROUTING_COMPARE_LOGGING_ENABLED`

Route behavior:

- `deterministic_only`: deterministic route only; no LLM shadow/planner call.
- `llm_shadow_only`: deterministic result selected; LLM shadow called only when `routing_llm_shadow_enabled=true`.
- `llm_assisted_semantic`: deterministic router runs first; LLM semantic result is advisory; final values are normalized through deterministic registry/policy.
- `llm_primary_lab`: blocked unless lab/dev mode and explicit lab flag are enabled; still cannot grant execution authority.

Route decision learning metadata:

- Defined in `backend/app/routing/governance.py`.
- `RouteDecisionRecord` records deterministic result, LLM advisory candidates, selected result, disagreements, guard checks, evidence needs, deterministic tool mapping summary, learning flag, and timestamp.
- Added to `PlaceholderResponse.route_decision`.

Evidence-needs to MCP tool mapping:

- Implemented in `backend/app/orchestration/evidence_mcp_mapping.py`.
- `splunk_metadata_discovery` maps to `splunk_get_indexes` and `splunk_get_metadata`.
- `splunk_auth_evidence` maps to template/validator path and only then the gated `splunk_run_query` path.
- `saia_generate_spl` is candidate-only and requires validation.
- Raw LLM-suggested tools are advisory and ignored as final selected tools.
- Saved search hints are blocked by default unless policy explicitly allows them.

Tests:

- `backend/app/tests/test_routing_governance_stage3jk0.py`
- `backend/app/tests/test_evidence_mcp_mapping_stage3jk0.py`
- `backend/app/tests/test_spl_optimization_stage3jk0.py`
- `backend/app/tests/test_route_compare.py`

Latest backend test count from current tree:

```text
317 passed
```

## 4. Relevant Feature Flags And Defaults

LLM provider / registry:

- `llm_enabled=false`
- `llm_mode=mock`
- `llm_providers=""`
- `llm_default_provider=mock`
- `llm_router_provider=mock`
- `llm_synthesis_provider=mock`
- `llm_reasoning_provider=""`
- `llm_teacher_provider=""`
- `llm_tool_recommendation_enabled=false`
- `ai_soc_llm_enabled=false`
- `ai_soc_llm_mode=mock`
- `ai_soc_llm_allow_cloud=false`
- `ai_soc_llm_airgap_enforced=false`
- `ai_soc_llm_redact_secrets=true`
- Provider registry supports mock, OpenAI-compatible, Ollama, vLLM, SGLang, TGI, llama.cpp, Cisco-compatible, and custom HTTP provider types.
- `supports_tool_calling` remains false in status.

Final synthesis:

- `ai_soc_llm_final_synthesis_enabled=false`
- `/chat` returns `SynthesisStatus(enabled=false, status="disabled")`.
- Demo scenarios return a planned/not-run synthesis status.

Answer Guard:

- `ai_soc_llm_answer_guard_enabled=false`
- `/chat` returns `AnswerGuardStatus(enabled=false, guard_status="disabled")`.
- Demo scenarios return a planned/not-run Answer Guard status.

Routing:

- `routing_mode=llm_assisted_semantic`
- `routing_lab_llm_primary_enabled=false`
- `routing_deterministic_threshold=0.70`
- `routing_llm_shadow_enabled=true`
- `routing_compare_logging_enabled=true`

SAIA / Splunk MCP:

- `splunk_mcp_enabled=true`
- `splunk_mcp_discovery_mode=dynamic`
- `splunk_ai_assistant_mode=auto`
- `splunk_saia_tools_enabled=true`
- `splunk_use_saia_generate_spl=true`
- `splunk_use_saia_explain_spl=true`
- `splunk_use_saia_optimize_spl=true`
- `splunk_use_saia_ask_question=true`
- `splunk_saia_require_discovery=true`
- `splunk_run_query_require_validation=true`
- `splunk_metadata_discovery_allowed=true`
- `splunk_knowledge_object_discovery_allowed=true`
- `mcp_mode=mock`
- `mcp_global_execution_enabled=false`
- `mcp_default_server=splunk_soc`

Saved search execution:

- `splunk_allow_run_saved_search=false`
- `splunk_run_saved_search_require_hil=true`
- Saved searches are not selected unless explicitly allowed by policy and provider capability.

Remediation / write actions:

- Action capability policy allows only tier 1.
- `create_ticket`, `block_ip`, `disable_user`, and `isolate_endpoint` remain unavailable.
- Skill registry blocks remediation/admin/write tools.

Experience Center demo mode:

- No separate config flag found.
- Demo endpoints are mounted in `backend/app/main.py`.
- Demo responses identify `demo_mode=true`, `evidence_origin=coe_synthetic_fixture`, `no_live_customer_data=true`, and `demo_badge=COE scenario`.
- Demo Foundation-sec content comes from captured fixtures only.

RAG retrieval:

- `rag_mode=mock`
- `soc_kb_retrieval_enabled=false`
- `soc_kb_retrieval_mode=deterministic`
- `soc_kb_repository_backend=json`
- `soc_kb_vector_backend=none`
- `soc_kb_direct_to_llm=false`
- `soc_kb_llm_selection_enabled=false`
- `soc_kb_llm_ambiguity_assist_enabled=false`
- `soc_kb_reranker_enabled=false`
- Graph expansion and embedding indexing are false by default.

## 5. Backend Endpoints

Routes are mounted with and without `/api` prefix.

Chat:

- `POST /chat`
- `POST /api/chat`

Demo / scenarios:

- `GET /scenarios`
- `GET /api/scenarios`
- `GET /demo/scenarios`
- `GET /api/demo/scenarios`
- `POST /demo/scenarios/{scenario_id}/run`
- `POST /api/demo/scenarios/{scenario_id}/run`

Settings status:

- `GET /settings/status`
- `GET /api/settings/status`

LLM validation / test / model listing:

- `POST /settings/llm/check`
- `POST /settings/llm/validate`
- `POST /settings/llm/test`
- `POST /settings/llm/models`
- Same routes under `/api/settings/llm/...`

MCP validation / test / discovery:

- `POST /settings/mcp/validate`
- `POST /settings/mcp/test`
- `POST /settings/mcp/discover`
- Same routes under `/api/settings/mcp/...`

Provider status:

- `GET /settings/providers/status`
- `GET /api/settings/providers/status`
- `POST /settings/providers/check`
- `POST /api/settings/providers/check`

Investigation:

- `POST /investigate`
- `POST /api/investigate`

Knowledge:

- `GET /knowledge/collections`
- `GET /knowledge/documents`
- `GET /knowledge/documents/{doc_id}`
- `GET /knowledge/entries`
- `GET /knowledge/import/contract`
- `GET /knowledge/import/prompt-template`
- `GET /knowledge/retrieval/test`
- `POST /knowledge/import/validate`
- `POST /knowledge/import/save-draft`
- `POST /knowledge/import/publish`
- `POST /knowledge/documents/{doc_id}/retire`
- Same routes under `/api/knowledge/...`

Lineage / trace:

- No dedicated `/lineage` or `/trace` endpoint was found.
- `investigation_lineage` is embedded in `/chat` and demo scenario responses.

## 6. Schema And Model Locations

Query understanding:

- `backend/app/query_understanding/models.py`
- Parser: `backend/app/query_understanding/parser.py`

Use-case registry:

- `backend/app/use_cases/models.py`
- `backend/app/use_cases/registry.py`
- Catalog: `backend/app/use_cases/catalog.json`

Skill registry:

- `backend/app/skills/models.py`
- `backend/app/skills/registry.py`
- Catalog: `backend/app/skills/catalog.json`

RequestedOutputType:

- `backend/app/query_understanding/models.py`
- Values include `investigation`, `spl`, `sop`, `mitre_mapping`, `summary`, `note`, `action_plan`, `clarification`.

OutputTemplate:

- `backend/app/query_understanding/models.py`
- Values include `investigation_answer`, `spl_response`, `sop_response`, `mitre_mapping_response`, `clarification_response`, `note_response`.

SourceEvidence:

- Runtime builder: `backend/app/evidence/source_evidence.py`
- Response schema: `SourceEvidenceEnvelope` in `backend/app/schemas/responses.py`

StructuredContext:

- Runtime structurer: `backend/app/evidence/context_structurer.py`
- Sufficiency gate: `backend/app/evidence/context_sufficiency.py`
- Response schemas: `StructuredFact`, `StructuredContextPackage`, `ContextSufficiencyEnvelope` in `backend/app/schemas/responses.py`

Severity decision:

- `backend/app/risk/severity_policy.py`
- Matrix: `backend/app/risk/severity_matrix.json`

MITRE mapping / status:

- `backend/app/threat/mitre_kb.py`
- Local subset: `backend/app/threat/mitre_attack_subset.json`

Investigation lineage:

- `backend/app/lineage/models.py`
- `backend/app/lineage/builder.py`

Synthesis status:

- `backend/app/synthesis/models.py`

Answer Guard status:

- `backend/app/answer_guard/models.py`
- Dormant rules: `backend/app/answer_guard/rules.py`

Action capability tier:

- `backend/app/actions/capability_policy.py`

Governed Foundation-sec fixture / response block:

- Fixture: `backend/app/demo/foundation_sec_fixtures.py`
- Backend response schema: `backend/app/schemas/responses.py`
- Frontend render: `frontend/src/components/AnalystResponseCard.tsx`
- Frontend pass-through: `frontend/src/components/ChatBubble.tsx`
- Frontend types: `frontend/src/types/api.ts`

## 7. Test And Build Health

Backend tests:

```text
cd backend && python3 -m pytest
317 passed in 2.24s
```

Frontend build:

```text
cd frontend && npm run build
passed
```

Build note:

- Vite warns that one or more chunks are larger than 500 KB after minification. This is not a build failure.

Harness:

```text
python3 -m test_harness.harness.runner --json
overall_pass=true, 6/6 cases passed
```

Harness with telemetry disabled:

```text
TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
overall_pass=true, 6/6 cases passed
```

Diff hygiene:

```text
git diff --check
passed
```

No failing tests were observed in this audit.

## 8. Safety Verification From Code

Experience Center does not call live LLM:

- Demo scenarios use static `foundation_sec_governance_for(...)`.
- Fixture data has `live_llm_called=false`.
- Demo path does not call the LLM connector or synthesis adapter.

Raw LLM output is not final answer:

- Fixture stores captured summaries, useful contributions, observed limitations, and governed overrides.
- UI renders governed analysis and collapsed governance, not raw malformed model output.
- Tests assert forbidden raw artifacts and unsafe SPL fragments are absent.

Final synthesis is disabled by default:

- `ai_soc_llm_final_synthesis_enabled=false`.
- `/chat` emits disabled synthesis status.
- Demo scenarios mark synthesis as planned/not run.

Answer Guard execution is disabled by default:

- `ai_soc_llm_answer_guard_enabled=false`.
- `/chat` emits disabled Answer Guard status.
- Demo scenarios mark Answer Guard as planned/not run.

LLM / SAIA SPL cannot directly execute:

- SAIA and LLM-generated SPL remain candidate-only.
- SPL service metadata sets validation required and execution not eligible.
- MCP execution gate requires approved validation and non-null `normalized_spl`.
- Evidence MCP mapping ignores raw LLM tool names.

Saved searches are blocked/default-disabled:

- `splunk_allow_run_saved_search=false`.
- Saved-search hints are blocked by evidence mapping unless policy explicitly allows them.
- MCP execution gate blocks saved search execution when server policy disallows search execution.

Remediation/write actions are blocked:

- Action policy allows only inform/prepare tier behavior.
- Remediation/write/admin tools remain unavailable or blocked in policy/catalog.

Secrets are not returned by settings APIs:

- Settings APIs return configured booleans and redacted/safe status.
- Draft checks are not persisted and do not echo token/API key values.
- Model names and provider role names may be returned, but secret values are not.

## 9. Stage 3K.1 Readiness Recommendation

Recommendation: do not start Stage 3K implementation until the current working tree is cleaned.

Blockers before Stage 3K:

- Dirty backend files contain Stage 3J-J.3 consistency fixes that should be committed or explicitly deferred.
- Dirty frontend files appear to be chat UI changes and need classification before Stage 3K.
- `.claude/` should remain untracked local tool state.

Once the tree is clean, Stage 3K.1 can start.

Recommended first Stage 3K.1 slice:

- Add a dormant governed synthesis service behind `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=false`.
- Keep `/chat` default behavior unchanged.
- Use mock/provider abstraction only in tests unless the flag is explicitly enabled.
- Require context sufficiency before synthesis.
- Return structured synthesis metadata, not raw LLM output.
- Keep Answer Guard execution disabled; do not wire Stage 3L.

Likely files to touch:

- `backend/app/synthesis/models.py`
- New `backend/app/synthesis/service.py` or equivalent governed synthesizer module
- `backend/app/connectors/llm/base.py` if synthesis contract needs tightening
- `backend/app/connectors/llm/mock.py` for deterministic mock synthesis behavior
- `backend/app/api/routes_chat.py` only behind the disabled-by-default synthesis flag
- `backend/app/schemas/responses.py` if additional response metadata is needed
- `backend/app/tests/test_synthesis_stage3k1.py`
- Existing chat safety tests to assert default-disabled behavior

Tests to add:

- Final synthesis disabled by default.
- Synthesis service not called when flag is false.
- Synthesis blocked when context sufficiency is insufficient.
- Synthesis output must be structured and governance-tagged.
- Raw model text is not exposed as final answer without guard status.
- Answer Guard remains disabled and not executed.
- LLM-generated SPL remains candidate-only.
- MCP execution gates remain unchanged.

Things that must not be changed in Stage 3K.1:

- Do not enable live LLM calls by default.
- Do not enable final synthesis by default.
- Do not enable Answer Guard execution.
- Do not execute LLM-generated SPL.
- Do not weaken MCP execution gates.
- Do not allow saved-search execution by default.
- Do not add remediation/write actions.
- Do not let LLM select final MCP tools directly.
- Do not expose raw LLM output as final analyst answer.
- Do not change Experience Center captured-fixture behavior unless explicitly scoped.
