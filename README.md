# AI SOC Assistant

Internal development scaffold for an AI-Augmented SOC Assistant for Splunk.

This project is intended to become a production-convertible assistant using FastAPI, React + TypeScript, LangGraph orchestration, a generic MCP registry with Splunk MCP as the first target server, PostgreSQL with pgvector, Agentic GraphRAG, multiple LLM provider/model backends, and deterministic safeguards.

## Architecture Summary

- FastAPI backend exposes health, chat, investigation, and scenario placeholder routes.
- React + TypeScript frontend provides a structured SOC cockpit using Tailwind CSS, shadcn-style local UI primitives, Radix patterns, and lucide-react icons.
- MCP, LangGraph, RAG, GraphRAG, LLM routing, and production safeguards are represented by clean placeholder interfaces only. Splunk MCP is one MCP server type, not the whole MCP framework.
- PostgreSQL is included in Docker Compose for later persistence work.

## Start

```bash
cd /var/www/ai-soc-assistant
cp .env.example .env
docker compose build
docker compose up -d
```

Local backend health:

```text
http://127.0.0.1:8010/health
```

Development frontend:

```text
http://127.0.0.1:3010
```

## Internal Nginx Access

Production-style access is through Nginx only. Docker ports for the backend, frontend dev server, and Postgres are bound to `127.0.0.1`.

Internal URL:

```text
https://cisco-vai.vnudge.com
```

Local backend health check:

```bash
curl -s http://127.0.0.1:8010/health
```

Nginx serves the production frontend from `frontend/dist`, proxies `/api/` and `/health` to the local FastAPI backend, and redirects HTTP to HTTPS. App-level login is handled by the FastAPI backend using credentials from `.env`.

The frontend visual system was adapted from the existing Support Buddy app as a read-only UI reference. No Support Buddy secrets, auth logic, HR data, ticket logic, or runtime configuration are used by this project.

## UI Pages

The React app now ships with these top-level routes (left sidebar):

- **Cockpit** — 3-column investigation workspace (alerts/scenario, chat, context tabs)
- **Chat** — focused chat workspace optimized for 100% browser zoom
- **Investigations** — mock case list (persistence comes later)
- **Scenarios** — demo scenario library
- **Knowledge** — read-only SOPs and graph context
- **Settings** — non-secret configuration surfaces (see below)
- **Debug** — planner / router / compare traces, SPL trace, raw mock JSON

Trace summary cards in Cockpit link to **Debug**; the full developer surface lives there, not inside Cockpit.

## Settings Surfaces

`Settings` exposes read-only status for:

- MCP (multi-server registry status, transport/auth configured booleans, discovered safe tool names, blocked execution tool names)
- RAG / governed SOC KB (knowledge vault path, lifecycle counts, deterministic retrieval flags, vector / hybrid / graph placeholders)
- LLM (multi-provider registry status, model family/role, router/synthesis/reasoning/teacher role mapping)
- Routing (mode, planner/shadow/compare flags, confidence thresholds)
- Safeguards (SPL validator, blocked commands, approval requirements)
- Observability (telemetry/trace flags, telemetry-write failure counter)

> **Telemetry storage:** `ai_soc` is this product's own namespace, not a Splunk
> product. AI-SOC runtime telemetry is stored in Postgres / the application
> database by default (`AI_SOC_TELEMETRY_SINK=db`). A Splunk telemetry connector
> is **deferred and not implemented** — setting `AI_SOC_TELEMETRY_SINK=splunk`
> or `both` makes the backend fail fast at startup with a clear configuration
> error. Set the sink to `none` to disable telemetry entirely.

The backing endpoint is `GET /api/settings/status` — it never returns tokens, passwords, usernames, bearer tokens, API keys, or session secrets, only `*_configured: bool` flags.

## Stage 3B Connection Readiness

Stage 3B prepares real-but-safe configuration surfaces only:

- `MCP_MODE=mock` keeps current mock behavior.
- `MCP_MODE=registry` parses named MCP servers from `MCP_SERVERS=splunk_soc,asset_inventory,ticketing`.
- Each MCP server has independent `configured`, `available`, `implemented`, and redacted `last_error` status.
- Splunk MCP targets the official Splunk MCP Server / Splunkbase App ID `7931` by default, but remains only one server type in the generic registry.
- MCP execution is disabled by both `MCP_GLOBAL_EXECUTION_ENABLED=false` and per-server `MCP_SERVER_<NAME>_EXECUTION_ENABLED=false`.
- Search/SPL execution tools and SAIA/SPL-generation tools are displayed as discovered but blocked.
- No MCP tool execution is implemented in this stage.
- The readiness layer uses a thin transport-agnostic adapter surface for `streamable_http`, `sse`, and `stdio`. If the official MCP Python SDK is added later, it should plug in behind this registry without changing environment variable names.

LLM readiness is provider/model based:

- `LLM_PROVIDERS` can list Foundation-Sec, local open-weight models, and enterprise gateways at the same time.
- Cisco/Foundation-Sec is one model family, not the only LLM option.
- Foundation-Sec Instruct and Foundation-Sec Reasoning are configured as separate providers/models when needed.
- Llama, Kimi, Qwen, Mistral, DeepSeek, and other open-weight models can be served through OpenAI-compatible gateways, vLLM, Ollama, SGLang, TGI, llama.cpp, or custom HTTP adapters.
- Workflow code resolves roles such as `router`, `synthesis`, `reasoning`, and `teacher` to configured providers; fallback must be explicit.
- `supports_tool_calling` is forced false in status because the AI-SOC backend controls MCP access. The LLM must never call MCP directly.
- LLM health canary completion is disabled by default with `LLM_HEALTH_CANARY_ENABLED=false`.

Current disabled work remains disabled unless a later stage flag explicitly enables its governed path: no real SPL execution, no real MCP tool execution, no final LLM synthesis, and no Splunk telemetry write. Stage 3C adds candidate SPL generation plus deterministic validation only.

## Stage 3C SPL Generation And Validation

Stage 3C introduces a safe SPL gate before any future execution:

- `attack_discovery` and `spl_generation` chat routes produce candidate SPL with the stub generator.
- Candidate SPL is validated deterministically before it can be considered for future MCP execution.
- Validator rejects by default unless the SPL is positively classified safe.
- Validator enforces allowed commands, blocked commands, time bounds, index and sourcetype allowlists, wildcard index blocking, macro/subsearch blocking, external-call blocking, credential/secret pattern blocking, and out-of-band result caps.
- Chat returns candidate SPL and validation status, then stops. It does not call Splunk or MCP.

Default SPL policy:

```env
SPL_VALIDATION_ENABLED=true
SPL_ALLOWED_INDEXES=pgcil_soc
SPL_ALLOWED_SOURCETYPES=pgcil:auth
SPL_DEFAULT_EARLIEST=-24h
SPL_DEFAULT_LATEST=now
SPL_MAX_RESULT_LIMIT=100
SPL_ALLOWED_COMMANDS=search,stats,where,table,fields,sort,dedup,rename,eval,timechart,bin,head
SPL_BLOCKED_COMMANDS=delete,collect,outputlookup,sendemail,script,map,rest,loadjob,inputlookup
```

Example approved candidate:

```spl
search index=pgcil_soc sourcetype=pgcil:auth earliest=-60m latest=now action=failure | stats count as fail_count by user | where fail_count > 50 | sort -fail_count | head 100
```

Example rejected candidate:

```spl
search index=* sourcetype=pgcil:auth earliest=-15m latest=now | outputlookup findings.csv
```

Reject reasons include `blocked_command:outputlookup`, `disallowed_index`, and `wildcard_index_not_allowed`.

## Stage 3D MCP Discovery, Selection, HIL, And Execution Gate

Stage 3D adds the first execution-control layer while keeping real execution disabled by default:

- MCP registry status classifies discovered/configured tools into safe capability categories such as `spl_search`, `metadata_lookup`, `knowledge_object_discovery`, `ticket_lookup`, `asset_lookup`, `unknown`, and `blocked`.
- Risky tools are blocked by deterministic policy, including SPL generation/assistant tools and write/admin patterns.
- `/chat` runs deterministic MCP tool selection after SPL validation. User-requested server/tool values are preferences only.
- Human review is returned whenever validation, connector configuration, tool selection, or execution policy prevents safe execution.
- `candidate_spl` is never sent to MCP. Only `spl_validation.normalized_spl` from an approved validation result may enter the execution gate.
- Mock mode can execute bounded deterministic rows only when `MCP_GLOBAL_EXECUTION_ENABLED=true` and `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`.
- Real MCP execution remains a `list_tools` / `call_tool(tool_name, {"query": normalized_spl})` adapter shape and returns `admin_action_required` until the real COE MCP server URL, transport, auth, tool names, and argument schema are supplied.

Stage 3D still does not add RAG retrieval, final LLM synthesis, Splunk telemetry writes, SAIA/Splunk AI Assistant generation, or LLM-to-MCP tool calling. `LLM_TOOL_RECOMMENDATION_ENABLED=false` by default; if later enabled, it is advisory only and cannot override deterministic policy.

## Stage 3F Governed SOC Knowledge Retrieval

Stage 3F adds governed multi-document SOC KB retrieval. In AI-SOC, RAG means approved SOC knowledge grounding, not open-ended vector search.

- Retrieval is deterministic over JSON-backed governed KB fixtures in `backend/app/knowledge/fixtures/`.
- Multiple collections are supported, including SOC SOPs, Splunk context, MITRE Enterprise grounding, escalation guidance, and MCP tool policy.
- Documents are version controlled with `doc_id`, `canonical_doc_id`, `version`, `revision`, lifecycle, approval, effective dates, supersession metadata, checksums, owners, and review notes.
- Runtime retrieval uses only current-version documents whose status is `active` or `published` and whose approval status is configured approved (`coe_reviewed` or `pgcil_approved` by default).
- Draft, rejected, retired, expired, superseded, wrong-environment, and wrong-allowed-use documents do not affect runtime retrieval.
- Entries inherit document eligibility and can also be individually draft/rejected/retired.
- Retrieval supports environment, collection, namespace, domain, document type, allowed use, skill, simple typo/synonym expansion, positive/negative examples, retrieval hints, fields, sourcetypes, indexes, MITRE IDs, MCP tools, confidence scoring, ambiguity status, and exclusion counts.
- Results become `SourceEvidence` with `source_type="rag"` and `tool_name="governed_soc_kb_retrieval"`, then contribute to `structured_context` fields such as `policy_context_refs`, `sop_action_hints`, `answer_constraints`, `prohibited_conclusions`, `mitre_grounding_refs`, `splunk_context_refs`, `tool_policy_refs`, and `environment_grounding_refs`.
- Human review can receive approved SOP reference, excerpt, reviewer role, and action hints. If no approved SOP is available, the safe message is: `Approved SOP guidance is unavailable for this scenario.`
- Future vector, hybrid, and graph retrieval are placeholders only (`embedding_ref`, `sparse_ref`, `graph_node_id`, `graph_edges`, and `retrieval_backend` metadata). No pgvector, Qdrant, Milvus, vector DB, reranker, or graph expansion is implemented in this stage.
- The Support-Buddy pattern is reused conceptually: governed schema, publish lifecycle, validation, deterministic retrieval, and no LLM source invention.

Default safety flags:

```env
SOC_KB_RETRIEVAL_ENABLED=false
SOC_KB_ENVIRONMENT=coe
SOC_KB_ALLOWED_STATUSES=active,published
SOC_KB_APPROVED_STATUSES=coe_reviewed,pgcil_approved
SOC_KB_INCLUDE_DRAFTS=false
SOC_KB_INCLUDE_SUPERSEDED=false
SOC_KB_MAX_RESULTS=5
SOC_KB_MIN_CONFIDENCE=0.35
SOC_KB_DIRECT_TO_LLM=false
SOC_KB_LLM_SELECTION_ENABLED=false
SOC_KB_HYBRID_PLACEHOLDER_ENABLED=true
SOC_KB_GRAPH_PLACEHOLDER_ENABLED=true
```

LLMs do not retrieve, select, or invent sources. If LLM candidate selection is added later, it may choose only among already retrieved deterministic candidates and cannot bypass lifecycle, status, approval, environment, allowed-use, or execution gates. Final synthesis remains disabled.

## Stage 3G Governed RAG Operations

Stage 3G completes the governed RAG layer short of real PDF/document-to-vector indexing. SOC KB remains deterministic-first and governed; runtime still uses only current approved `active` / `published` documents.

- A `KnowledgeRepository` abstraction now backs retrieval and admin operations. The current implementation is JSON-backed and DB-ready at the interface boundary.
- Admin APIs expose collections, documents, entries, import validation, publish, retire, and deterministic retrieval testing under `/api/knowledge/...`.
- Import batches support manual JSON and Support-Buddy-style LLM extraction proposals. LLM conversion is offline/admin only: proposed documents and entries are draft or ready-for-review until human validation and publish.
- Validation enforces required document and entry fields, supported document types and allowed uses, source excerpts for runtime entries, source refs for medium/high/critical risk, positive examples and test cases for high/critical risk, checksums for source-backed imports, no duplicate current published versions, and no runtime eligibility for draft/rejected content.
- Publishing a new current document version supersedes the older current version. Draft, ready-for-review, superseded, expired, retired, rejected, and unapproved documents do not affect runtime retrieval.
- Retrieval now begins with deterministic collection selection by skill, workflow stage, allowed use, environment, query signals, HIL state, and required sources. It does not blindly search every collection.
- Hybrid-ready stages are represented as `collection_selection`, `metadata_filter`, `deterministic_schema_search`, `keyword_search`, `dense_vector_search`, `sparse_vector_search`, `graph_expansion`, `rerank`, `policy_filter`, `ambiguity_check`, and `final_candidate_selection`.
- Deterministic schema/keyword retrieval is implemented. Vector backends are interface-only (`none` or bounded `mock`); graph expansion and reranking are safety-bounded placeholders. Rerankers may only reorder eligible candidates and cannot add sources.
- Graph metadata supports relationships such as `document_has_entry`, `entry_mentions_mitre`, `entry_mentions_sourcetype`, `entry_mentions_field`, `sop_requires_reviewer_role`, `scd_allows_index`, `detection_note_supports_spl_pattern`, `mcp_policy_allows_tool`, and `asset_policy_defines_criticality`.
- Ambiguity detection considers confidence margin, cross-domain/document-type conflicts, negative-example penalties, wrong allowed-use/skill penalties, and wrong-environment exclusion. If ambiguity reaches HIL, the safe message is: `Knowledge retrieval is ambiguous and requires analyst review.`
- The Knowledge page now shows collection/document lifecycle state, version/revision, checksums, statuses, validation output, and a retrieval test panel. It is intentionally not a PDF parser or rich KB editor yet.

Default Stage 3G model/readiness flags:

```env
SOC_KB_RETRIEVAL_MODE=deterministic
SOC_KB_VECTOR_BACKEND=none
SOC_KB_VECTOR_MODEL=BAAI/bge-m3
SOC_KB_RERANKER_MODEL=BAAI/bge-reranker-v2-m3
SOC_KB_EMBEDDING_INDEXING_ENABLED=false
SOC_KB_RERANKER_ENABLED=false
SOC_KB_GRAPH_EXPANSION_ENABLED=false
SOC_KB_LLM_AMBIGUITY_ASSIST_ENABLED=false
SOC_KB_DIRECT_TO_LLM=false
SOC_KB_LLM_SELECTION_ENABLED=false
```

Actual PDF parsing, embedding generation, vector indexing, external vector DB integration, graph database expansion, and real reranker model serving are deferred. RAG output continues to flow only through `SourceEvidence` and `StructuredContext`; there is no direct RAG-to-LLM path and no final synthesis.

## Stage 3H Splunk MCP, Splunk AI Assistant Availability, and AI-SOC Fallback

Splunk MCP is the first-class Splunk integration path. AI-SOC now distinguishes core `splunk_*` MCP tools from optional `saia_*` Splunk AI Assistant tools, because on-prem, OT-SOC, government, and air-gapped deployments cannot assume Splunk AI Assistant is available.

- Core Splunk MCP tools are used for Splunk data access, metadata, index context, user/context discovery, knowledge object discovery, and validated execution.
- `saia_*` tools are optional accelerators for candidate SPL generation, explanation, optimization, and Splunk-specific guidance.
- If `saia_*` tools are unavailable, disabled, undiscovered, or effectively disabled by `AI_SOC_ENVIRONMENT_MODE=air_gapped`, AI-SOC uses fallback SPL services: template/internal generation, rule-based explanation, rule-based optimization, and governed SCD/RAG guidance.
- SAIA outputs are never execution evidence. `saia_generate_spl` output is stored as `candidate_spl` only.
- Internal LLM/template fallback output is also `candidate_spl` only.
- All SPL must pass deterministic SPL validation before it can reach `splunk_run_query` / `run_splunk_query`.
- Optimized SPL is treated as a new candidate and must be revalidated.
- `splunk_run_saved_search` is detected as a beta execution capability but defaults disabled. If enabled later, it must be allowlisted or HIL-approved.
- Execution still requires validation, policy selection, global/server execution flags, selected allowlisted tool, and HIL where required.
- Splunk MCP results become `SourceEvidence` with `source_type="splunk_mcp"`. SAIA advisory outputs become `source_type="splunk_mcp_saia"` and are not treated as execution evidence.
- `StructuredContext` records capability profile reference, generation/explanation/optimization/guidance providers, fallback mode, execution provider, and source refs.

The Splunk capability profile reports:

- MCP availability and discovery mode
- discovered core `splunk_*` tools and discovered `saia_*` tools
- Splunk AI Assistant configured mode and usability
- fallback requirement
- saved search and run-query policy flags
- missing expected core/SAIA tools

Key Stage 3H environment flags:

```env
AI_SOC_ENVIRONMENT_MODE=coe
SPLUNK_MCP_ENABLED=true
SPLUNK_MCP_SERVER_ID=splunk_soc
SPLUNK_MCP_DISCOVERY_MODE=dynamic
SPLUNK_AI_ASSISTANT_MODE=auto
SPLUNK_SAIA_TOOLS_ENABLED=true
SPLUNK_USE_SAIA_GENERATE_SPL=true
SPLUNK_USE_SAIA_EXPLAIN_SPL=true
SPLUNK_USE_SAIA_OPTIMIZE_SPL=true
SPLUNK_USE_SAIA_ASK_QUESTION=true
SPLUNK_SAIA_REQUIRE_DISCOVERY=true
SPLUNK_ALLOW_RUN_SAVED_SEARCH=false
SPLUNK_RUN_SAVED_SEARCH_REQUIRE_HIL=true
SPLUNK_RUN_QUERY_REQUIRE_VALIDATION=true
SPLUNK_METADATA_DISCOVERY_ALLOWED=true
SPLUNK_KNOWLEDGE_OBJECT_DISCOVERY_ALLOWED=true
SPLUNK_ALLOWED_CORE_TOOLS=splunk_run_query,splunk_get_info,splunk_get_indexes,splunk_get_index_info,splunk_get_metadata,splunk_get_user_info,splunk_get_knowledge_objects
SPLUNK_ALLOWED_SAIA_TOOLS=saia_generate_spl,saia_explain_spl,saia_optimize_spl,saia_ask_splunk_question
```

Status and trace UI now show Splunk MCP capability, SAIA availability/usability, fallback active state, provider used for SPL generation/explanation/optimization/guidance, validation result, selected execution tool, HIL status, and SourceEvidence status. No tokens, credentialed URLs, passwords, API keys, headers, or secrets are exposed.

## Stage 3I Multi-Provider Context and Tool Framework Skeleton

Stage 3I adds a small provider abstraction for future non-Splunk integrations without enabling real firewall, router, EDR, remediation, write, or admin actions.

- `ProviderType` covers `splunk_mcp`, `generic_mcp`, `security_api`, `network_api`, `asset_inventory`, `ticketing`, `rag_knowledge`, and `manual_input`.
- `ProviderOperationCategory` covers discovery, lookup, candidate generation, explanation, optimization, execution, write, and admin operation classes.
- `ProviderCapabilityProfile` normalizes provider readiness, allowed/blocked operations, HIL requirements, evidence support, fallback state, and warnings.
- Existing Splunk capability profiles can be represented as provider profiles while preserving Stage 3H Splunk MCP behavior.
- A mock-only `mock_asset_inventory` provider supports read-only `asset_lookup` and returns `SourceEvidence`; it does not call an external API.
- Generic provider policy rejects unavailable providers, non-allowed operations, blocked operations, default write/admin operations, HIL-required operations without approval, and providers that cannot emit evidence.

All provider results must become `SourceEvidence` before entering structured context. Final synthesis, answer guards, real API integrations, OT use cases, and write/remediation actions remain deferred.

### Mock Mode Example

```env
MCP_MODE=mock
MCP_DEFAULT_SERVER=splunk_soc
MCP_GLOBAL_EXECUTION_ENABLED=false
LLM_MODE=mock
LLM_HEALTH_CANARY_ENABLED=false
TELEMETRY_MODE=db
AI_SOC_TELEMETRY_SINK=db
```

### COE Readiness Example

Use placeholder values only until COE provides real endpoints and credentials:

```env
MCP_MODE=registry
MCP_SERVERS=splunk_soc,asset_inventory,ticketing
MCP_DEFAULT_SERVER=splunk_soc
MCP_GLOBAL_EXECUTION_ENABLED=false

MCP_SERVER_SPLUNK_SOC_ENABLED=true
MCP_SERVER_SPLUNK_SOC_TYPE=splunk
MCP_SERVER_SPLUNK_SOC_TRANSPORT=streamable_http
MCP_SERVER_SPLUNK_SOC_URL=https://splunk-mcp.example.invalid/mcp
MCP_SERVER_SPLUNK_SOC_AUTH_MODE=bearer
MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN=replace-with-token
MCP_SERVER_SPLUNK_SOC_TOOL_ALLOWLIST=list_tools,splunk_get_indexes,splunk_search,saia_generate_spl
MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED=false
MCP_SERVER_SPLUNK_SOC_SPLUNK_APP_ID=7931
MCP_SERVER_SPLUNK_SOC_SPLUNK_PLATFORM=unknown

LLM_PROVIDERS=foundation_sec_instruct,foundation_sec_reasoning,llama_local,kimi_local,enterprise_gateway
LLM_DEFAULT_PROVIDER=foundation_sec_instruct
LLM_ROUTER_PROVIDER=foundation_sec_instruct
LLM_SYNTHESIS_PROVIDER=foundation_sec_instruct
LLM_REASONING_PROVIDER=foundation_sec_reasoning
LLM_TEACHER_PROVIDER=enterprise_gateway
LLM_GLOBAL_CONCURRENCY=4
LLM_TIMEOUT_SECONDS=30
LLM_HEALTH_CANARY_ENABLED=false

LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_ENABLED=true
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_TYPE=cisco_compatible
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_BASE_URL=https://foundation-sec-instruct.example.invalid/v1
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_API_KEY=replace-with-api-key
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_AUTH_MODE=api_key
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_MODEL=replace-with-instruct-model
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_MODEL_ROLE=instruct
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_FAMILY=foundation_sec
LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_SUPPORTS_TOOL_CALLING=false

LLM_PROVIDER_FOUNDATION_SEC_REASONING_ENABLED=true
LLM_PROVIDER_FOUNDATION_SEC_REASONING_TYPE=cisco_compatible
LLM_PROVIDER_FOUNDATION_SEC_REASONING_BASE_URL=https://foundation-sec-reasoning.example.invalid/v1
LLM_PROVIDER_FOUNDATION_SEC_REASONING_API_KEY=replace-with-api-key
LLM_PROVIDER_FOUNDATION_SEC_REASONING_AUTH_MODE=api_key
LLM_PROVIDER_FOUNDATION_SEC_REASONING_MODEL=replace-with-reasoning-model
LLM_PROVIDER_FOUNDATION_SEC_REASONING_MODEL_ROLE=reasoning
LLM_PROVIDER_FOUNDATION_SEC_REASONING_FAMILY=foundation_sec
LLM_PROVIDER_FOUNDATION_SEC_REASONING_SUPPORTS_TOOL_CALLING=false
```

### Status Shape Example

`GET /api/settings/status` redacts secrets and reports only booleans:

```json
{
  "mcp": {
    "mode": "registry",
    "default_server": "splunk_soc",
    "global_execution_enabled": false,
    "servers": [
      {
        "name": "splunk_soc",
        "type": "splunk",
        "url_configured": true,
        "auth_configured": true,
        "execution_enabled": false,
        "discovered_tools_safe_names": ["list_tools", "splunk_search"],
        "blocked_tools_safe_names": ["splunk_search"],
        "search_execution_allowed": false,
        "saia_spl_generation_allowed": false
      }
    ]
  },
  "llm": {
    "default_provider": "foundation_sec_instruct",
    "role_resolution": {
      "router": "foundation_sec_instruct",
      "reasoning": "foundation_sec_reasoning"
    },
    "providers": [
      {
        "name": "foundation_sec_instruct",
        "base_url_configured": true,
        "api_key_configured": true,
        "supports_tool_calling": false
      }
    ]
  }
}
```

## Stage 3J Context Sufficiency Gate

After governed RAG collection, the Context Sufficiency Gate classifies the `SourceEvidence` + `StructuredContext` package into one answer mode and computes a `synthesis_readiness` signal. Synthesis itself stays disabled (`synthesis_allowed=false`).

Modes: `full_answer`, `partial_answer`, `analyst_review_required`, `spl_review_only`, `knowledge_only_answer`, `blocked_by_policy`, `insufficient_evidence`.

Key rules: SAIA/candidate SPL alone is advisory (`spl_review_only`); RAG-only evidence supports SOP/knowledge guidance; structured facts without `source_refs` are insufficient; MITRE conclusions require MITRE grounding and asset-criticality claims require asset evidence (`analyst_review_required`); a sensitive leak blocks readiness (`blocked_by_policy`).

## Stage 3J-B Governed LLM Layer

A safe configuration/status/UI layer ahead of evidence-based synthesis. No real LLM is called.

- `AI_SOC_LLM_*` settings: `AI_SOC_LLM_MODE` is canonical (`mock|local|openai_compatible|cisco_foundation_sec|disabled`; `disabled` forces off). Air-gap enforcement overrides cloud allowance.
- `GET /api/settings/status` adds a `llm.governance` block: enabled/mode/cloud/airgap, default provider/model, the `final_synthesis_enabled` / `answer_guard_enabled` / `context_sufficiency_required` flags, limits, safety controls, provider readiness, and role mappings — all as `*_configured` booleans, never secrets.
- `POST /api/settings/llm/check` validates a settings draft without persisting and never echoes secrets.
- The Settings → LLM Registry tab shows the governance status and a draft editor (validate only).
- `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` and `AI_SOC_LLM_ANSWER_GUARD_ENABLED` are inert flags (default false). No synthesis or answer-guard code exists yet.

## Stage 3J-C Analyst Chat UX and Intent Hygiene

Analyst-first chat presentation plus three intent fixes. No final synthesis, answer guard, MCP execution change, or new providers.

- Each assistant response leads with an analyst summary card (status, execution state, evidence state, synthesis readiness, next recommended action) using human-readable labels. The Stage 3D technical trace is collapsed behind "Show technical trace"; raw codes stay inside it.
- SOP / playbook / runbook prompts route to `knowledge_recall` (governed guidance), not `attack_discovery`; no SPL is generated unless the user asks to investigate live data or generate SPL.
- "successful login after failures" generates a failure+success correlation SPL, not a failed-login-spike-only query.
- "Map this alert to MITRE" without alert context returns an `intent_clarification` human-review asking for the alert title / rule / notable / SPL; it does not generate SPL.
- Starter prompts are grouped: Investigate, Knowledge/SOP, Generate SPL, MITRE Mapping. Copy buttons exist for the trace ID and candidate SPL. The background was lightened from near-black.

## Warning

This is an internal Experience Center scaffold. Do not expose Docker service ports publicly and do not commit auth credentials or session secrets.
