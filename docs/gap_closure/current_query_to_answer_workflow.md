# Current Query-to-Answer Workflow

Verified state: `master` through Chat Control Plane Phase 10. This document describes what happens today when an analyst sends a `/chat` query under the full-throttle system-check profile.

## Control Plane Rollout Gate

Canonical planning runs unconditionally on `/chat`. The historical env gate `CONTROL_PLANE_ENABLED` was removed (non-runtime). The control plane path runs:

```text
User query
  -> query signals
  -> 105 / 42 candidate mapping
  -> IntentClassification
  -> EvidencePlan
  -> RouteAdjudication
  -> LLM advisory plan validation (JSON-only, no provider call)
  -> conditional RAG / SPL / MCP gates
  -> SPL slot binding validation
  -> runtime MITRE decision
  -> sufficiency
  -> response_mode / synthesis_mode
  -> control_plane_trace
```

Phase 10 added `backend/app/tests/test_chat_control_plane_golden.py`, seven flag-on golden queries with no xfail. COE may consider flipping the default only after those golden tests and `./scripts/run_stage3_governance_regression.sh` pass in the target environment.

## Current Full-Throttle Profile

The committed profile is `.env.live-full-throttle.example`.

Key enabled levers:

| Area | Setting | Current profile intent |
|------|---------|------------------------|
| Orchestration | `LANGGRAPH_ORCHESTRATION_ENABLED=true` | Run the same five chat stages through LangGraph parity |
| Routing | `ROUTING_MODE=llm_assisted_semantic` + `ROUTING_LLM_SHADOW_ENABLED=true` | QU-first skill selection; LLM advisory/trace (exact 105 keeps `query_understanding_105`) |
| Routing (lab) | `ROUTING_MODE=llm_primary_lab` + `ROUTING_LAB_LLM_PRIMARY_ENABLED=true` | Optional lab-primary override experiments |
| Route authority | `ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=true` | Operation authority only for manifest allowlisted coverage IDs (see `route_authority_allowlist.py`) |
| Legacy skill authority | `LEGACY_SELECTED_SKILL_AUTHORITY_ENABLED=false` | Prefer registry operation mirror when authority applies |
| OOD control | `ROUTE_PLAN_OPEN_OPERATIONS_ENABLED=true`, supporters/audit enabled | Allow governed OOD proposals to be reviewed, not executed |
| MCP | `MCP_MODE=mock`, global/mock execution enabled | Exercise mock MCP only |
| RAG | `RAG_MODE=mock`, `SOC_KB_RETRIEVAL_ENABLED=true` | Exercise governed SOC KB evidence path |
| MITRE | `AI_SOC_LLM_MITRE_CANDIDATE_MAPPING_ENABLED=true` | LLM candidate mapping is review-only |
| Synthesis | `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true` | Exercise P6 governed synthesis lab |
| Answer Guard | `AI_SOC_LLM_ANSWER_GUARD_ENABLED=true` | Exercise guard check on synthesis lab draft |

Important limitation: real LLM providers still require endpoint/API-key/model configuration. If `configured_providers=[]`, LLM governance and role mappings are enabled, but real provider calls will not run.

## End-to-End Flow

```text
User query
  -> /chat
  -> LangGraph or imperative five-stage pipeline
  -> deterministic query understanding
  -> query-to-intent control plane (flag on)
  -> evidence planning + route adjudication (flag on)
  -> query understanding (105 + 42) -> route_skill (4 skills) + LLM assisted advisory
  -> LLM advisory plan validator (JSON-only)
  -> route-plan shadow / known-vs-OOD split
  -> authority + preconditions
  -> workflow plan
  -> candidate SPL, if needed
  -> deterministic SPL validation
  -> SPL slot binding validation (flag on)
  -> precondition gate before MCP
  -> mock MCP and/or governed RAG evidence
  -> structured context + sufficiency
  -> runtime MITRE decision / severity / action policy
  -> P6 synthesis lab
  -> Answer Guard
  -> response_mode + synthesis_mode + final response + trace
```

## 1. Chat Entry

The user sends a message to `/chat`.

If `LANGGRAPH_ORCHESTRATION_ENABLED=true`, the request runs through LangGraph. The graph is parity-mode orchestration: it runs the same five logical stages as the imperative pipeline and should not change core behavior.

Pipeline stages:

1. Initialize routing.
2. Shadow enrichment.
3. Workflow + SPL.
4. Execution gate.
5. Context finalize.

## 2. Query Understanding

The system first runs deterministic query understanding.

It identifies:

| Item | Purpose |
|------|---------|
| normalized query | stable downstream matching |
| requested output type | investigation, SPL, SOP, MITRE, summary, action plan, clarification |
| entities | user, host, source IP, alert context, time window where available |
| clarification need | blocks context-dependent prompts such as “map this alert” without alert details |

This stage does not call MCP, does not call RAG, and does not execute SPL.

## 3. Intent and Skill Routing

The legacy `selected_skill` field remains one of four closed enum skills (`alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall`). Query understanding (105 registry + 42 catalog) drives routing; the four-keyword router is fallback only.

| Authority source | When |
|------------------|------|
| `query_understanding_105` | Verbatim or exact 105 registry match |
| `query_understanding_105_near` | Near 105 paraphrase (provisional; LLM may override in assisted/lab) |
| `query_understanding_catalog` | 42 catalog match with enum `primary_skill` |
| `query_understanding_catalog` + `collapsed_from` | Catalog row with non-enum skill (`action_planning`, `mitre_mapping`, …) collapsed to `knowledge_recall`; `requested_output_type` + `use_case_id` preserved on `routing_provenance` |
| `query_understanding_weak` | Out-of-registry or no valid legacy hint |
| `keyword_router_fallback` / `qu_parse_failed` | QU selection exhausted or `understand_query` raised |
| `deterministic_clarification` | MITRE/map-this without alert context (before QU paths) |
| `llm_advisory_validated` | Assisted/lab only, when uncertain and LLM candidate validates |

Routing flow:

1. `understand_query` once per request (pipeline try/except; on failure deterministic keyword failover — LLM not used on parse-failed path).
2. `select_route_from_understanding` picks skill from 105 / catalog / near / weak (not the keyword router on confident paths).
3. Context-clarification override when required.
4. LLM modes record shadow/advisory; override only when uncertain (not on exact 105).
5. `routing_provenance` on `routed` is the authoritative routing snapshot for trace/downstream (full QU fields forwarded).

“LLM primary lab” exercises the lab path for visibility; validated LLM candidates cannot bypass registry policy or expand `SKILL_ENUM`.

## 4. Route Plan Shadow and Known vs OOD

The route-plan sidecar builds a candidate operation shape. This may come from LLM sidecar output if a provider/callable exists, or from deterministic/test/mock paths.

The route plan is validated structurally before it can influence anything.

The system classifies the query path:

| Path | Meaning | Live behavior |
|------|---------|---------------|
| known registry | coverage/registry row is known | can proceed only through authority and precondition gates |
| known-compatible OOD | operation type is known, but no exact registry row | review/audit; no live execution until promoted |
| novel OOD | operation is not in governed catalog | audit + HIL only; no MCP execution |
| knowledge-only | SOP/MITRE/explanation path | RAG/knowledge evidence path; no SPL required |
| clarification | missing required context | asks user for details |

P6-add also adds `nearest_registry_row` as an advisory supporter. It can suggest the closest 105-question registry row, but it does not grant authority.

## 5. Authority and Preconditions

Authority happens before execution.

Known-path authority requires:

| Gate | Purpose |
|------|---------|
| route authority allowlist | only approved `coverage_id`s can apply operation authority |
| operation/intent bridge | checks compatibility between legacy skill and operation |
| precondition evaluation | checks template, lookup, detection, source, threshold, time-window readiness |
| SPL validation | only approved `normalized_spl` may proceed |
| MCP tool policy | deterministic tool selection; unsafe tools blocked |
| HIL policy | human review where required |

Precondition evaluation is now wired into MCP execution. If S7 fails, MCP is blocked before tool discovery/execution.

## 6. Workflow and SPL

The workflow planner creates a plan with steps and safety gates.

If the effective skill needs SPL:

1. Candidate SPL is generated.
2. Deterministic SPL validator runs.
3. Validator may reject unsafe or malformed SPL.
4. `candidate_spl` is never executed.
5. Only non-null approved `normalized_spl` can reach the MCP gate.

## 7. MCP

In full-throttle system-check mode:

```env
MCP_MODE=mock
MCP_GLOBAL_EXECUTION_ENABLED=true
MCP_SERVER_MOCK_EXECUTION_ENABLED=true
```

This exercises mock MCP execution only.

Real Splunk MCP is still blocked until COE supplies:

| Need | Status |
|------|--------|
| endpoint URL | required |
| auth mode/token | required |
| tool names | required |
| argument schema | required |
| HIL/approval workflow | required |
| readiness/smoke result | required |

LLMs never call MCP directly. MCP tool selection is deterministic.

## 8. RAG

In full-throttle system-check mode:

```env
RAG_MODE=mock
SOC_KB_RETRIEVAL_ENABLED=true
```

RAG retrieval can contribute SOC KB evidence. The boundary is strict:

```text
RAG result -> SourceEvidence -> StructuredContext -> Sufficiency/Synthesis
```

There is no direct RAG-to-LLM path. Draft/unapproved knowledge remains excluded by retrieval policy.

## 9. MITRE

MITRE mapping has deterministic and LLM-assisted layers. With canonical planning on, analyst-visible MITRE output is governed by `mitre_decision`, not raw registry metadata.

| Layer | Authority |
|-------|-----------|
| local MITRE KB / use-case mapping | deterministic mapping source |
| `mitre_permitted[]` | SOC-approved authority target |
| LLM MITRE candidate mapper | candidate/review-only |

LLM MITRE output cannot write authoritative `mitre_permitted[]`. If the LLM output has bad JSON, it is not automatically treated as a bad mapping; formatting/parsing failure is separated from semantic validation.

Runtime rules:

- Policy/RAG-only questions suppress analyst-visible MITRE even when registry candidates exist.
- Live investigation and explicit MITRE asks can show only registry-permitted/candidate techniques as candidate mappings.
- Blocked techniques never become visible mappings.
- Missing alert context returns clarification / trace-only metadata.

## Control Plane Dependencies

These do not block merged control-plane logic, but they do block production-quality answers:

| Dependency | Owner/gate | Current behavior |
|------------|------------|------------------|
| KB content for escalation/SOP/playbook answers | COE content | Golden tests allow `insufficient_evidence` / fail-closed when mock KB has no match |
| Slot-capable SPL templates | Detection engineering | Slot binding rejects candidate SPL when requested constraints are not encoded |
| Source/precondition readiness | COE + connector config | Preconditions and MCP gates block before execution |
| MITRE production review | COE | Registry metadata is promoted in repo; runtime decision controls visibility |
| Frontend trace polish | UI owner | Backend exposes `control_plane_trace`; UI can render collapsed technical trace later |

## 10. Context Sufficiency

The system then evaluates whether the evidence package is enough to answer.

It considers:

| Evidence | Examples |
|----------|----------|
| MCP evidence | mock Splunk rows, normalized SPL, result preview |
| RAG evidence | SOP/playbook excerpts |
| MITRE grounding | approved/ref evidence |
| source references | evidence IDs and origin labels |
| negative results | empty-result sufficiency and reasons |

The output includes answer readiness and missing evidence reasons.

## 11. LLM Usage Today

LLM is used only in governed roles:

| Role | Where | Authority |
|------|-------|-----------|
| intent / route advisory | routing sidecar / lab route plan | advisory or lab-primary normalized through policy |
| route-plan candidate generator | OOD/lab sidecar | candidate only |
| template match/render assist | SPL template support paths | advisory only |
| analyst summary narration | shadow/lab summary support | advisory/draft |
| MITRE candidate mapper | P5 sidecar | review-only |
| final synthesis lab | P6 | governed draft only |
| Answer Guard assistant | P6 | guard support; deterministic guard remains authority |

Current provider caveat:

```text
AI_SOC_LLM_ENABLED=true
AI_SOC_LLM_MODE=mock
configured_providers=[]
```

This means the feature flags and role mappings are enabled, but real LLM provider calls need real endpoint configuration such as:

```env
AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_BASE_URL=
AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_API_KEY=
AI_SOC_LLM_FOUNDATION_SEC_INSTRUCT_MODEL=Foundation-sec-8B-Instruct
AI_SOC_LLM_FOUNDATION_SEC_REASONING_BASE_URL=
AI_SOC_LLM_FOUNDATION_SEC_REASONING_API_KEY=
AI_SOC_LLM_FOUNDATION_SEC_REASONING_MODEL=Foundation-sec-8B-Reasoning
```

## 12. Synthesis and Answer Guard

If P6 flags are enabled:

1. Synthesis lab builds an evidence package.
2. It drafts a guarded analyst answer only if sufficiency and policy allow.
3. Answer Guard checks the draft against evidence, action policy, severity, and source constraints.
4. If guard fails, the draft is blocked and HIL is required.

The final response includes trace fields for synthesis status and guard status.

## 13. Final Response

The final `/chat` response can include:

| Field | Meaning |
|-------|---------|
| `selected_skill` | compatibility routing skill |
| `primary_operation` | registry/operation target when available |
| `coverage_id` | known registry coverage ID when resolved |
| `semantic_intent` | known/OOD/knowledge/clarification path details |
| `route_plan_shadow` | LLM/deterministic route-plan trace |
| `workflow_plan` | planned steps |
| `candidate_spl` / `spl_validation` | SPL generation and validation status |
| `execution` | MCP skipped/blocked/mock executed status |
| `source_evidence` | MCP/RAG evidence envelopes |
| `structured_context` | normalized evidence package |
| `context_sufficiency` | readiness and missing-evidence reasons |
| `mitre_mappings` | default flag-off legacy use-case KB mapping; control-plane flag-on can add registry `mitre_permitted[]` overlap until Phase 7 decisioning |
| `synthesis_status` | P6 synthesis lab status |
| `answer_guard` | guard result |
| `governance_trace` | consolidated trace panels |

## Practical Summary

When a user asks a query today, the system:

1. Parses the query deterministically (`understand_query`: 105, 42 catalog, near/out-of-registry).
2. Routes via `route_skill` into four legacy skills with `routing_provenance`; LLM assisted mode is advisory unless uncertain.
3. Splits known vs OOD.
4. Applies authority and precondition gates.
5. Generates and validates SPL only when needed.
6. Uses mock MCP and governed RAG for evidence in system-check mode.
7. Maps MITRE deterministically, with LLM candidates only for review.
8. Checks context sufficiency.
9. Runs guarded P6 synthesis lab and Answer Guard when enabled.
10. Returns the answer plus trace, never letting LLM bypass MCP/SPL/authority gates.
