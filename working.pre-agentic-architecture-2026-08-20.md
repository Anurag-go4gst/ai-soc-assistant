# T4 path (not T1–T3): architecture vs live `/chat`

**Date:** 2026-08-20  
**Sources:** frozen `architecture.md` (Plan 8, freeze 2026-08-15) and live code on this tree.  
**Related:** `docs/ai/t4_semantic_prompting_playbook.md` (read before any T4 prompt/schema/few-shot/merge change). Do not call Cisco on this VPS to iterate prompts.

This is a working note, not a change to `architecture.md`. The freeze says implementation gaps remain gaps.

---

## 0. Two different “T4”s — do not mix them

| Name | What it means | Where it is decided |
|---|---|---|
| **Catalogue T4** | No T0–T3 catalogue bind. Parser match path is `out_of_registry` (also `semantic_out_of_registry`, `query_understanding_weak`, empty). | `lane_router.py`: `initial_tier=T4`, processing lane **`guided`**. |
| **Semantic T4 hop** | Optional bounded LLM meaning-completer. Role `semantic_t4` → local Foundation-Sec 8B. | `maybe_enrich_t4_semantic()` in `backend/app/chat/semantic_t4_understanding.py`. Runs only if flag on **and** `qualification_tier==T4` **and** UNDERSTANDING sufficiency `next_action==CALL_T4`. |

Architecture §2.2 / §9 uses “T4” for the **LLM hop**. Code first uses “T4” as **out of catalogue**. A turn can be catalogue-T4 and still **never call the model** (flag off, timeout, no CALL_T4, circuit OPEN, or fail-closed clarification).

T0 is a later promotion, not a parser path: a T4-shaped question that qualifies as a CVE/MITRE/ATLAS id can become `resolved_tier=T0` / lane `knowledge_short_circuit`. That is **not** remaining on T4.

**How you accidentally leave T4:** a substring bind (historically `"playbook"` → `soc_show_sop` @ 0.91) is a **T2 catalogue bind**, not T4. Current tree: negation (`"no … playbook"`), `soc_show_sop` exclusion patterns, and `should_apply_catalogue_bind` skipping `binding_candidate_tier == "T4"`. Eval row `rt.neg.001` is catalogue T4, not proof the semantic hop succeeded.

**Experience Center S4** (zero-day / no-playbook fixtures) is **not** production `/chat` T4.

---

## 1. Architecture intended order (`architecture.md` §2.3 / §5)

```text
Request + session [DET]
  → PHASE 1  T1–T3 deterministic understanding
  → UNDERSTANDING sufficiency
       ├─ sufficient ──────────────────────────────┐
       └─ unresolved meaning → PHASE 2 T4 [LLM]    │
                              → PHASE 3 merge [DET]┘
  → PHASE 4  FINAL ResolvedQueryContract
  → clarification OR final owner
  → PHASE 5  ResourcePlan   (must consume FINAL RQC)
  → PHASE 6  compiler + PhaseRegistry / PhasePolicy / PhaseContract
  → PHASE 7  Resource Planner execution hub
  → EvidenceState
  → PHASE 8  EVIDENCE sufficiency
  → InvestigationOutcome (governed structured result)
  → PHASE 9  narration [LLM, facts stay DET]
  → final validation
  → PHASE 10 post-synthesis actions (ticket/email) only if requested + policy
  → FINAL USER RESPONSE
  → PHASE 11 session continuity
```

Hard invariants from the freeze:

- T1–T3 first. T4 only for **unresolved meaning**. T4 must not pick skill, grant capabilities, call MCP, set HIL/RBAC, or override locked facts (§2.2, §9).
- **Do not commit ResourcePlan from a provisional interpretation, then adjudicate route after** (§2.3). This is also known correction **#1** in §24.
- Clarify → **no plan**. Persist handoff; next message re-enters Phase 0/1 (§12).
- `primary_skill` is ownership, not a capability veto (§2.4). Example D investigation may be Knowledge → SPL → validate → MCP → reason (§14).
- Candidate SPL is never executable. Only approved non-null `normalized_spl` may reach MCP (§17). Authorization is **exact-call** (normalized SPL / args hash), not “MCP server access” (§17, correction #11).
- LLMs never call MCP. Restart of the model is human-only (§10).
- `PlanDelta`, multi-round evidence refinement, and Phase 10 ticket/email/CRM/remediation connectors are **§25 extensions — not automatic current work**.
- Production GO remains deferred. **F3** (`T4_SEMANTICALLY_VIABLE_BUT_VPS_SERVING_BLOCKER`) is still a critical blocker. Live MCP is unproven.

Architecture §23 intended Plan 7/8 VPS posture:

```text
LANGGRAPH_ORCHESTRATION_ENABLED=true
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=true
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=false
```

Timeout is environment-specific, not an architectural constant. Repo **code defaults** for the T4 hop are still **flag false / 2.0s** — the 120s + flag-on values live in the development/COE profile, not in `Settings` defaults.

---

## 2. Live HTTP: request and response

**Entry:** `POST /chat` → `backend/app/api/routes_chat.py::chat` → `_chat_impl`.

On this host (`AI_SOC_ENV_PROFILE=development`, `LANGGRAPH_ORCHESTRATION_ENABLED=true`):

```text
ChatRequest
  → persist_chat_admission(trace_id)     # before pipeline work
  → run_chat_via_resource_planner_graph(request, session_role)
  → post_chat_response(PlaceholderResponse)
```

Unhandled exceptions log `trace_id` and return a sanitized HTTP 500. Producer/LLM failure inside the pipeline is supposed to degrade to a deterministic 200, not a stub.

### Request (`ChatRequest`)

```text
message                  required analyst text
session_id               optional
requested_mcp_server     preference only, not authority
requested_mcp_tool       preference only, not authority
llm_spl_draft_mode       bool, default false
source_profile_slots     optional COE index/sourcetype map
execution_review_action  optional HIL handshake
analyst_provided_spl     optional
```

Auth: FastAPI session (`require_auth`). Trace: client `X-Request-ID` (UUID) becomes the turn `trace_id` and is echoed as `X-Trace-ID`.

EC parity short-circuit (`AI_SOC_LIVE_CHAT_EC_PARITY_ENABLED`) can divert to a demo fixture **before** the RP graph. That is **not** production T4.

### Two different “plans” in the response

| Object | What it is | T4 meaning |
|---|---|---|
| **ResourcePlan** | Canonical work: RAG/SPL/MCP/narration steps, committed in planning | Authority for what work is required |
| **`workflow_plan`** | Inert UI/orchestration skeleton | Steps stay `not_started`, `execution_enabled=false`. ResourcePlan execution ON does **not** make this object executable |

### Response (`PlaceholderResponse`)

Analyst-visible: `message`, `trace_id`, `user_query`, skill/use-case, inert `workflow_plan`, `human_review`, `spl_validation`, `control_plane_trace`, lineage/governance panels, optional `canonical_facts` / investigation diagnostics.

Facts (severity, MITRE, actions, SPL, `execution_eligible`) stay deterministic. Any LLM prose is narration only.

---

## 3. Resource Planner graph — node map

Compiled in `backend/app/graph/resource_planner_graph.py`. Entry: `bootstrap`.

```text
bootstrap
  → route_resolution                         [shadow tail; adjudication already in canonical planning]
  → resource_planner_delegate
  → specialist_skill ∥ specialist_knowledge ∥ specialist_mcp ∥ specialist_spl
  → resource_planner_merge                   [WorkBundle; fill blanks only]
  → _rp_dispatch_route:
        not planned          → non_planned_finalize → finalize
        answer_mode=rag_only → prepare_rag_only → rag_early → (governance or spl_source_resolve)
        has composed plan    → composed_dispatch → spl_validate → …
        else                 → workflow_spl → rag_early | spl_source_resolve
  → governance chain:
        spl_validate                         [forces execution_eligible=false if not approved]
        → mcp_execution_gate                 [evaluate_mcp_execution; AUTH0 if a call exists]
        → context_sufficiency
        → decide_facts                       [TRACE STUB]
        → answer_guard                       [TRACE STUB]
        → human_review
        → policy_veto
        → finalize                           [real EvidenceState, InvestigationOutcome, Answer Guard, synthesis]
        → validate_final_answer
        → END
```

Typical **catalogue-T4 guided** (`answer_mode=guided_investigation`, ResourcePlan committed): **`composed_dispatch`**.

Inside `execute_plan_dispatch`, guided is treated as rag-only for the **hook schedule** (`path_type == guided_investigation` → `prepare_rag_only` + `rag_early`). The graph **names** it `composed_dispatch`; the executor still runs RAG hooks, not SPL/MCP.

If the locked family is `knowledge_only` / policy (skill often `knowledge_recall`), `_rp_dispatch_route` may take **`rag_only`** instead (`answer_mode==rag_only`).

`dispatch-v2` cannot win when ResourcePlan execution is on (`legacy_dispatch_v2_authority_enabled` is false). That is Plan 7 A6, aligned with architecture §23.

---

## 4. Complete path when the question is not T1–T3

Assume: `match_use_cases` returns `[]`, no exact-105 / near-105 / fuzzy-alias bind, no T0 reference id. Catalogue bind is **skipped** because `binding_candidate_tier == "T4"` (`live_router_bind.py::should_apply_catalogue_bind`).

### 4.1 Phase 0 — session

`run_resource_planner_graph` calls `resolve_session_context(request)`:

- `effective_query`
- pins / prior redacted RQC / optional `last_investigation_outcome_ref`
- optional clarification `handoff_resume`

Previous assistant prose is **not** trusted evidence (architecture §2.8, `NON_AUTHORITATIVE_GENERATED_CONTENT`).

Follow-up: `apply_session_continuity` only folds prior RQC for `follow_up_kind == "scope_delta"`. Generic phrase catalogues are not the continuity mechanism (architecture correction #6). Evidence from a prior turn is **not** automatically reusable; applicability is evaluated against the **new** RQC (architecture §18).

### 4.2 `rp_node_bootstrap` — understanding + planning

Two sequential calls:

1. `graph_node_init_routing` (`pipeline.py`)
2. `run_canonical_planning` (`canonical_planning_orchestrator.py`)

#### A. `understand_query`

Deterministic query understanding. Unbound questions typically get `deterministic_match_path=out_of_registry`.

#### B. `route_skill` / `select_route_from_understanding` → `_route_out_of_registry`

Order matters. First matching floor wins:

| Floor | Result skill |
|---|---|
| Unsafe contain / run | **not** guided |
| T2 shape `reference_taxonomy` | `knowledge_recall` |
| Command-mode SPL | `spl_generation` |
| T2 answer-shape floor when `shape != "hunt"` | `guided_investigation` |
| Investigation-request markers and not live-data | `guided_investigation` |
| Detection family / explicit SPL / live-data and not guidance | `spl_generation` |
| `soc_investigation_shaped` and not live-data | `guided_investigation` |
| else | **`LOW_CONFIDENCE_ROUTE`** = `knowledge_recall` @ 0.20 |

So “lands on T4” (catalogue) does **not** mean the primary skill is always `guided_investigation`. Weak hunt wording (“Determine whether we are exposed…”) often falls through to `knowledge_recall` unless hunt/investigate markers or live-data signals fire. `"assess whether"` is an investigation marker; `"Determine whether"` is not.

#### C. Catalogue bind

`apply_live_catalogue_bind` records `catalogue_tier=T4` in routing provenance and **does not** apply a use-case / template.

#### D. Route-plan shadow

Deterministic candidate only on this path. LLM route suggestions are advisory; Plan 4 D3: they cannot replace a floor-resolved skill.

#### E. `run_canonical_planning`

```text
graph_node_lane_and_canonical_planning
  → enforce_canonical_outcome_invariant
  → if route_adjudication missing:
        graph_node_route_resolution
        graph_node_route_contract
  → planning_decision projection
```

**Lane for T4 match path:** `initial_tier=T4`, `resolved_tier=T4` (unless T0 promotion), `processing_lane=guided`.

**T4 / guided branch** (`_resolve_lane_intent_and_details` else-arm):

1. `build_query_to_intent` — **deterministic**. The RP graph does **not** run `graph_node_query_to_intent`, so the **intent-advisor LLM hop does not fire** on this path.
2. Intent classifier last rung can still be `clarification_required` / `knowledge_recall` if signals are weak. That family is **locked before T4**.
3. `qualify_reference_query` — CVE/MITRE/ATLAS id → T0 short-circuit (leave this note).
4. Else: `processing_lane=guided`, `run_guided_detail_resolution`.
5. Post-guided completeness: if still missing user-only fields, family is rewritten to `clarification_required`.

**Then RQC + optional semantic T4:**

```text
build_resolved_query_contract(...)
  → apply_session_continuity(...)          # scope_delta only
  → maybe_enrich_t4_semantic(...)          # Phase 2+3 in one function
```

`attach_understanding_authority` (inside the hop prep):

- Locks `intent_family`, `answer_goal`, `qualification_tier`, `ambiguity_state`, prohibitions, concrete entities, time_scope.
- For T4, **does not** lock `normalized_goal` (T4 may fill it).
- If T4 would have clarified only for “insufficient signals” (not policy/unsafe), it **defers** clarification to the hop: `clarification_required=false` on the pre-hop contract, `unresolved_fields` includes `semantic_goal` (and `semantic_referent` / `investigation_target` when applicable). Provenance may set `t4_owns_unresolved_semantic_referent`.
- Sufficiency `next_action=CALL_T4` when UNDERSTANDING is PARTIAL/INSUFFICIENT with unresolved fields and not already CLARIFY/BLOCK. EVIDENCE sufficiency **cannot** request CALL_T4.

**Then:**

- Policy block → outcome `policy_blocked`, **no EvidencePlan**.
- RQC / gap / post still clarify → `_persist_clarification_outcome` (durable handoff: `handoff_id`, unresolved fields, original skill/goal), **no ResourcePlan**. Dispatch later is `non_planned_finalize`.
- Else `_commit_planned_outcome` → `plan_evidence_from_canonical` → `compose_resource_plan` → persist `plan_committed`.

**Order gap vs architecture §2.3 / correction #1:** ResourcePlan is committed **inside** `graph_node_lane_and_canonical_planning` from **intent family + provisional `lane.routed`**. `run_canonical_planning` may then run `graph_node_route_resolution` **after** that commit.

### 4.3 Semantic T4 hop (Phase 2) — LLM request / response

File: `backend/app/chat/semantic_t4_understanding.py`.  
Contract: `backend/app/chat/contracts/semantic_t4_proposal.py` (`extra="forbid"`).

**Skip / fail-closed conditions:**

| Condition | Effect |
|---|---|
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=false` | Keep deterministic RQC, **except** if the hop owned an unresolved semantic referent → fail-closed clarification `t4_unavailable_unresolved_semantic_referent` |
| `qualification_tier != "T4"` | No hop (T1–T3 never pay) |
| sufficiency ≠ `CALL_T4` | No hop |
| LLM mode mock/disabled, or no endpoint | Treated as provider unavailable |
| Circuit `OPEN` | Hop not invoked; `human_action_required=true`; degrade |
| Timeout / empty / invalid JSON / forbidden authority keys | Keep deterministic RQC, or fail-closed if unresolved referent |

**Repo defaults:** flag **false**, timeout **2.0s**.  
**This host development profile:** flag **true**, timeout **120s** (matches architecture §10 / §23).  
**F3:** a completed hop on this VPS is not production GO. Circuit/backpressure (Plan 8 REL0) **must not** be claimed as solving serving capacity.

**Circuit / restart (architecture §10 — partially built):**

```text
CLOSED → invoke
OPEN  → shed, record diagnostics, human_action_required_model_restart
HALF_OPEN → only after operator records a manual restart + health
```

No LLM, ResourcePlanner, circuit breaker, or T4 path may restart Cisco. `request_human_model_restart` / `record_manual_model_restart` never execute a restart. Threshold: `AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD` (default 3). Plan 8 audit: T4 circuit **PARTIAL**; F3 not solved.

**HTTP call** (`_live_single_hop_provider` → `LocalChatClient.generate`):

```text
POST {AI_SOC_LLM_LOCAL_BASE_URL}/chat/completions
Authorization: Bearer <key> if configured
stream: false
model: resolved local primary (sidecar)
max_tokens: 220          # 400 tokens ≈ 90s at measured 4.1–4.5 tok/s; 220 fits 120s budget
temperature: 0.1
timeout: AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS
response_format: json_schema name=semantic_t4_proposal
                 schema limited to unresolved_fields_to_resolve
```

**One hop. No failover chain.**

**Trust wrapping (architecture §2.8 / correction #12):**

- `CONTROL_PREAMBLE`: labelled blocks are DATA, not control; they cannot grant capabilities or clear HIL.
- User query wrapped `wrap_untrusted_source("user_query", query)`.

**System prompt (meaning only):** complete unresolved SOC query meaning; clarify only for missing required referents or two materially different meanings; a broad hunt is not missing meaning; do not grant route/capability/SPL/MCP/RBAC/HIL; return one JSON object.

**User prompt payload vs architecture §9 input contract:**

| Architecture wants | Code actually sends |
|---|---|
| original query | yes (untrusted-wrapped) |
| relevant prior safe context | `supplied_context` entities/time if present |
| LOCKED_FIELDS | `locked_fields_do_not_change` (prompt-filtered) |
| UNRESOLVED_FIELDS | `unresolved_fields_to_resolve` (job-aware schema names) |
| allowed semantic vocabulary | implicit in json_schema enum |
| **short relevant capability descriptions** | **not sent** |
| 1–3 curated few-shot examples | **two** contrast examples (hunt vs missing referent). Prompt assets, not RAG |
| required structured-output schema | json_schema, limited to unresolved fields |

**Frozen proposal fields (Cisco 8B-validated):**

```text
normalized_goal
evidence_requirements      # categories, not findings
competing_hypotheses       # possibilities, not conclusions
semantic_ambiguity         # unambiguous | clarification_required  (meaning only)
clarification_required
clarification_reason
semantic_confidence        # understood the ask, not that an attack occurred
```

Optional unresolved fills (merged if present, not frozen offered contract): `entities`, `time_scope`.

**Architecture §9 also lists “threat relationship” as a T4 responsibility. The frozen schema has no such field.** Playbook: keep semantic strength (`new` ≠ newly registered; `unusual` ≠ malicious).

**Forbidden in payload (fail whole hop):** skill, route, SPL, MCP, execute, RBAC, HIL, `execution_eligible`, approved, verdict, etc.

**Clarification from the model is allowed ONLY for (playbook):**

1. Unresolved required referent (unnamed this/that host/alert/prior turn).
2. Two materially different semantic meanings of the *ask*.

Not allowed: missing logs, examples, thresholds, detection criteria.

**Merge (Phase 3, deterministic):**

- T4 may fill unresolved meaning fields only.
- Cannot change locked `intent_family`.
- Cannot grant / widen capabilities; extra required capabilities accepted only if the **already-accepted family** already requires them. `guided_investigation` is **not** in `_INTENT_REQUIRED_CAPABILITIES` (that table only lists SPL/MCP families). So T4 cannot add `spl`/`mcp` to a guided T4 RQC.
- Cannot override locked facts.
- New entities / time_scope must already appear in the query or locked/supplied context.
- Unknown non-authority keys are dropped; unknown **authority** keys fail the hop.

After a successful hop that **does not** ask: RQC may be non-clarifying, but **locked family can still be `clarification_required`**. EvidencePlan then still plans as clarification. T4 cannot promote `clarification_required` → `guided_investigation` / `spl_generation`.

### 4.4 Phase 5 — EvidencePlan + ResourcePlan (when planned)

`plan_evidence()` keys off **intent family**, not catalogue tier. Catalogue T4 can therefore produce four different plans:

| Locked family / skill floors | EvidencePlan | Dispatch |
|---|---|---|
| `guided_investigation` | RAG-only guidance, SPL/MCP off, HIL, `recommend_only` | `composed_dispatch` → RAG hooks |
| `knowledge_only` / policy (skill often `knowledge_recall`) | `answer_mode=rag_only` | graph `rag_only` |
| `spl_generation_only` / `live_investigation` (floors fired) | needs_spl / maybe needs_mcp | `workflow_spl` or composed with SPL steps |
| `clarification_required` | no RAG/SPL/MCP | `non_planned_finalize` |

**Family `guided_investigation` (the architecture Example D “investigation” case in code):**

```text
answer_mode: guided_investigation
rag_phase: rag_only
needs_rag: true
needs_spl: false
needs_mcp: false
spl_allowed: false
mcp_allowed: false
requires_hil / needs_hil: true
action_mode: recommend_only
reasons: out_of_registry_guided_investigation
```

Hybrid flag `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED` (dev: true) can add:

```text
discovery_allowed: true
investigation_planning_enabled: true
spl_review_allowed: true
safe_spl_execution_allowed: false
freeform_spl_execution_allowed: false
mcp_action_allowed: false
```

That is **advisory discovery / review**, not live Splunk search.

RQC overlay in `plan_evidence_from_canonical`: if `required_capabilities` contains `spl` / `mcp` and not prohibited, set `needs_spl` / `needs_mcp`. T4 merge **will not add** those capabilities for guided, so overlay almost never upgrades a guided T4 plan to live SPL.

**Composer** (`compose_resource_plan`) for guided:

```text
rag          (needs_rag)
evidence     skill:evidence_collection   metadata_only, analyst_validation_required
sufficiency  skill:context_sufficiency
narration    llm_role:narration          answer_guard, deterministic_fallback_on_failure
```

No SPL step. No MCP step. Provenance `committed=true`.

Plan 8 C0 comment in the composer: primary skill is ownership, not a capability veto — **SPL/MCP steps still follow EvidencePlan**. Guided EvidencePlan never asks for them, so C0 does not produce Example D on this path.

**Fail-closed capability compatibility (Plan 3 B2):** if intent wanted SPL but skill forbids it, capability is denied; the turn does not error. Contradiction never **widens** capability.

### 4.5 `rp_node_route_resolution`

Calls `graph_node_shadow_tail` only. Real route adjudication usually already happened inside `run_canonical_planning`. This node is mostly **shadow / trace**.

### 4.6 Specialists (parallel, advisory)

Exactly four, permanent:

| Specialist | What it does | What it must not do |
|---|---|---|
| skill | Records `skill_id` + catalogue_tier | No route change |
| knowledge | Audit report from intent + EvidencePlan | No RAG I/O |
| mcp | Audit: candidate names, hop count, posture | No connector, no tool call, no execution grant. A candidate tool name is **not** a selected tool |
| spl | Audit: source, slots, `execution_eligible=false` | No SPL text, no validator run |

Merge: `WorkBundle` may fill **blank** arguments on already-authorized steps. Cannot add steps, remove policy checks, override non-blank args, or authorize execution.

Architecture §16 hub diagram shows Knowledge / SPL / MCP / LLM as **execution** spokes. In code those four nodes are **auditors**, not executors. Execution is `composed_dispatch` / `workflow_spl` / RAG hooks.

### 4.7 Dispatch + governance (Phases 6–8)

**Planned guided T4:**

```text
composed_dispatch = execute_plan_dispatch
  → ResourcePlan walk (flag-on) or rag_only hook schedule
  → graph_node_prepare_rag_only
  → graph_node_rag_early          governed SOC-KB → SourceEvidence / StructuredContext
                                  (no direct RAG-to-LLM path)
```

Then:

- `rp_node_spl_validate` — if validation exists and not approved, force `execution_eligible=false`. Does **not** itself call `validate_spl`. Guided typically has no candidate.
- `rp_node_mcp_execution_gate` — `evaluate_mcp_execution`. Guided: `mcp_allowed=false` → skip/block. Candidate SPL never executes. If a call *were* authorized, AUTH0 binds `canonical_arguments_hash` / normalized SPL fingerprint (architecture correction #11). Guided T4 never gets there. Live MCP still default-off / unproven. LLM cannot mint a grant.
- `rp_node_context_sufficiency` — `attach_evidence_sufficiency` (EVIDENCE stage). Cannot request CALL_T4.
- `rp_node_decide_facts` / `rp_node_answer_guard` — **trace stubs** (`*_pending_finalize`). Real MITRE/severity/Answer Guard run in `graph_node_context_finalize`.
- `human_review` / `policy_veto` — guided HIL + `spl_allowed=false` / `mcp_allowed=false`.
- `finalize` = `graph_node_context_finalize`.
- `validate_final_answer` (grounding/policy/format; patches `control_plane_trace`).

Phase 6 PhaseContract merge exists (`planner/phase_schedule_merge.py`). Lifecycle phases are mandatory-when-applicable. Guided has little SPL/MCP contract work to merge. A compiler downgrade must not silently erase applicable lifecycle work (architecture §15); guided simply has none applicable.

`AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` remains **default false** (architecture §23). Route-level “one skill must grant everything” was rejected (Plan 5 B5, `cisco.ot.029`).

### 4.8 Finalize / Phase 8–9 / Phase 10

`graph_node_context_finalize` (the real Phase 7–9 seam) builds, in order:

1. SourceEvidence + StructuredContext  
2. **FinalEvidenceGate** — single cross-stream authority for evidence classification  
3. **RunContract**  
4. **CanonicalFacts** spine  
5. **minimal EvidenceState** (`derive_minimal_evidence_state`) — derived view, not a database  
6. EVIDENCE sufficiency vs final RQC required evidence  
7. MITRE / severity — **no claim without evidence**; MITRE ask without alert context stays clarification/knowledge, not invented technique  
8. **InvestigationOutcome** (`derive_investigation_outcome`) — projection from existing packages (`CanonicalFacts`, gate, sufficiency, structured facts with `source_refs`). `llm_proposal_accepted` stays false unless a validated proposal exists. LLM-proposed findings are non-authoritative until that happens.  
9. Governed synthesis lab / optional live narration (both synthesis flags)  
10. Answer Guard lab if enabled (`run_answer_guard_lab`) — repo default off; a `blocked` verdict raises `answer_guard_blocked` HIL  
11. `PlaceholderResponse`

Guided T4 typically has **missing live evidence**. Outcome disposition is often `inconclusive`; missing_evidence is populated; no P1/P2 without evidence; recommended actions stay `recommend_only` / non-execution.

**LLM hops that can still fire after planning (flag-dependent):**

| Hop | When | Authority |
|---|---|---|
| Guided / governed composer | guided path + composer eligible | Narration; facts DET |
| Missing-evidence reasoner | hybrid role plan | Advisory |
| Live synthesis | `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` **and** `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` | Narration only; failure → deterministic draft; EC never calls a live model |
| SPL LLM fallback | only if `needs_spl` | Lab-tier raw SPL never executable; only a derived artifact after validate + slots + vigilance |
| Intent advisor / route shadow | not on RP T4 canonical path / not final route | Advisory |
| Specialists | never | No LLM |

Guided visible text often `build_shaped_guidance` → hunt default → `build_signal_class_guidance`. Unmapped class → generic hunt skeleton (“no live query… no MITRE/severity”).

**Phase 10:** architecture ticket/email after InvestigationOutcome. Guided T4 is `recommend_only`. No auto ticket / isolate / write MCP. §25 lists Phase 10 connectors as **not automatic current work** unless separately approved. Action lane (`/api/actions/{id}/approve|deny`) exists elsewhere and is flag-gated; it is not this T4 default.

**Phase 11:** next message re-enters Phase 0/1 with safe prior contract/pins. Historical evidence may be marked `OUT_OF_SCOPE` / `STALE` against the new RQC; it is not deleted.

---

## 5. Two terminals on a real T4 turn

```text
                    catalogue T4 (out_of_registry)
                                │
                    semantic hop? (flag + CALL_T4 + circuit CLOSED)
                     /                    \
               timeout / fail / OPEN     success
               + deferred referent       no ask
                     │                      │
              RQC clarify              RQC maybe clear
              persist handoff          still: locked family?
              NO ResourcePlan               │
                     │                 family still clarification_required
              non_planned_finalize          → clarification plan, no RAG
              generic “Please provide: family guided_investigation
              semantic_goal, …”             → ResourcePlan RAG+guidance
                                            composed_dispatch
                                            no live SPL/MCP
                                       family knowledge_only
                                            → rag_only dispatch
                                       family already SPL/live-data
                                            → SPL lifecycle (still catalogue T4)
```

Clarification question builder (`build_clarification_question`): known keys are host/user/alert/time/index/sourcetype/ip. Unresolved T4 fields `semantic_goal` / `semantic_referent` / `investigation_target` are **not** in `_FIELD_QUESTIONS` → generic “Please provide: …”. Architecture §12 wants a focused analyst question. If no unresolved list exists, code injects `investigation_scope` so the handoff is resumable.

---

## 6. LLM hops — compact inventory for T4

| Role | Wired on RP T4 path? | Request | Response | Authority |
|---|---|---|---|---|
| `semantic_t4` | Yes, if flag + CALL_T4 + circuit allows | One `/chat/completions`, json_schema, 220 tokens | `SemanticT4Proposal` JSON | Meaning only; merge-gated |
| Intent advisor | **No** (RP uses `build_query_to_intent` without that hop) | — | — | — |
| Route LLM shadow | Shadow only; cannot replace floor-resolved skill | — | advisory | DET wins (Plan 4 D3) |
| Shape advisor | Optional in some init paths; T2 shape flag | bounded | may promote reference_taxonomy skill | not T4 meaning |
| Guided composer | Yes if eligible | bounded | prose | narration |
| Live synthesis | Dev profile both flags true; repo default false | bounded | prose | narration |
| SPL producer | Only if needs_spl | plan JSON | compiled SPL | never raw-executable |
| Answer Guard | Finalize, flag-gated | — | verdict | can raise HIL if blocked |
| Four specialists | Always after plan | none | audit JSON | no LLM |

---

## 7. Architecture.md vs code — gaps

These are implementation gaps against the **frozen** architecture. Several are already listed as §24 “known minimum authority corrections.”

| # | Architecture | Code | Why it matters on T4 |
|---|---|---|---|
| 1 | §2.3 / correction #1: Final RQC → owner → ResourcePlan. Never commit plan then adjudicate route. | `plan_evidence_from_canonical` commits inside lane+canonical planning from intent family + provisional `lane.routed`; `graph_node_route_resolution` may run after. | Provisional skill/family can freeze the plan. T4 cannot repair family. |
| 2 | §2.4 / Example D / correction #4: investigation ResourcePlan may include Knowledge + SPL + MCP. Primary skill must not veto capabilities. | Guided EvidencePlan hardcodes `needs_spl=false`, `needs_mcp=false`. Composer adds no SPL/MCP steps. Overlay cannot add SPL unless RQC already required it; T4 cannot grant it (`guided_investigation` not in `_INTENT_REQUIRED_CAPABILITIES`). | Catalogue-T4 hunts get **review-only RAG + checklist**, not live search, even when the ask is “are we exposed”. Architecture §22 full VPN example is **not** this path unless family/live-data already required SPL **and** policy/HIL pass. |
| 3 | §16 hub: Knowledge / SPL / MCP / LLM as execution spokes. | Four specialist nodes are advisory auditors. Real work is dispatch hooks. | Reading the graph as “specialists execute” is wrong. |
| 4 | §9 T4 is the semantic phase of understanding. §23 wants flag on / 120s. | Semantic hop is **optional**, repo-default **off**, 2.0s timeout. F3 still a production blocker. Host profile matches §23; `Settings` defaults do not. | Many T4 turns never get a model completion; contract stays deterministic. |
| 5 | §11 derived capabilities recomputed from **final** understanding (correction #5). | `intent_family` locked **before** T4; merge will not change it. Insufficient-signals classify → T4 cannot promote to hunt/SPL. | Meaning-complete T4 + wrong locked family → still clarification or knowledge_recall plan. |
| 6 | §12 clarify with a real analyst question; no plan. | Unresolved T4 field names missing from `_FIELD_QUESTIONS` → generic prompt. Handoff is persisted (aligned). | Bad HIL UX on timeout/fail-closed. |
| 7 | `_rp_dispatch_route` vs imperative `_uses_rag_only_path`. | RP graph special-cases only `answer_mode==rag_only`; guided goes `composed_dispatch`. Imperative treats `path_type==guided_investigation` as rag_only. Executor then still schedules RAG hooks. | Same RAG outcome, different graph node names. Dual-runtime parity cares; operators tracing nodes can misread. |
| 8 | §9 T4 input includes capability descriptions; T4 may determine “threat relationship”. | Prompt has no capability descriptions. Frozen schema has no threat-relationship field. | Architecture input contract is wider than the 8B-validated freeze. Playbook wins for schema changes. |
| 9 | §10 full health / backpressure / HALF_OPEN. | Circuit CLOSED/OPEN/HALF_OPEN exists; OPEN sheds; no auto restart (aligned). Serving F3 unproven. Audit: circuit **PARTIAL**. | Architecture depends on 8B completing; code degrades honestly. |
| 10 | Phase 9/10 InvestigationOutcome then actions. | InvestigationOutcome **exists** as a finalize projection (aligned in role). Guided `recommend_only`; Phase 10 connectors are §25 not-current-work. `decide_facts` / `answer_guard` RP nodes are stubs; real work in finalize. | Graph trace names overstate those nodes. Architecture §22 ticket/email is aspirational on guided T4. |
| 11 | Intent LLM as understanding adjacent. | Intent advisor lives on `graph_node_query_to_intent`, **not** an RP graph node. T4 lane uses deterministic `build_query_to_intent`. | Extra LLM on T4 is the semantic hop + optional narration, not intent. |
| 12 | Vocabulary: architecture “T4” = LLM hop. | Code “lands on T4” first = out_of_registry / guided lane. | Confusion in reviews and evals (`rt.neg.001`). |
| 13 | Live MCP in Phase 7 / Example D. | Live Splunk MCP implemented but **unproven**; defaults off; guided plan forbids MCP anyway. AUTH0 exists for when a call is authorized. | Example D cannot happen on guided T4 without a family that already requires SPL/MCP. |
| 14 | `rp_node_spl_validate` as validation. | Forces `execution_eligible=false` if not approved; does not run `validate_spl`. | Name vs behavior. |
| 15 | Correction #8/#9 EvidenceState + InvestigationOutcome. | Both **exist** as derived projections in finalize (substantially aligned). Guided T4 often `inconclusive` + missing live evidence. | Role exists; content is honest empty/partial, not a live investigation outcome. |
| 16 | §23 `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=false`. | Default false (aligned). | Live route-level capability enforcement is not what makes T4 guided skip SPL. The EvidencePlan does. |

**Aligned (not gaps):** T1–T3 before T4; T4 cannot set skill/MCP/HIL/RBAC; candidate SPL non-executable; RAG through SourceEvidence; clarify → no plan + persisted handoff; PlanDelta not on main path; specialists cannot authorize execution; EC path isolated from production `/chat` if you stay on this graph; exact-call AUTH0 seam exists; trust delimiters on the T4 prompt; no automatic model restart; `workflow_plan.execution_enabled=false`; dispatch-v2 fenced when RP execution is on.

---

## 8. Flags that change T4 (this host vs repo default)

| Flag | Repo default | `development.env.example` | Effect on T4 |
|---|---|---|---|
| `LANGGRAPH_ORCHESTRATION_ENABLED` | true | true | `/chat` uses RP graph |
| `AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED` | false | true | RP execution contract vs flag-off identity |
| `AI_SOC_PIPELINE_DISPATCH_V2_ENABLED` | false | false | Must stay fenced when RP execution is on |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED` | **false** | **true** | Semantic hop may run |
| `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS` | **2.0** | **120** | 8B can finish on this VPS |
| `AI_SOC_T4_CIRCUIT_FAILURE_THRESHOLD` | 3 (env) | — | OPEN after N failures |
| `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED` | false | false | Not the guided-SPL veto |
| `AI_SOC_T2_ANSWER_SHAPE_ENABLED` | — | true | Out-of-registry shape floors |
| `AI_SOC_GUIDED_HYBRID_INVESTIGATION_ENABLED` | — | true | Advisory discovery/review; still no live search |
| `AI_SOC_GUIDED_LLM_ENABLED` | — | true | Guided composer budget |
| `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` + `FINAL_SYNTHESIS` | false | true | Narration only |
| `AI_SOC_LLM_ANSWER_GUARD_ENABLED` | false | may enable | Finalize, not the stub graph node |
| MCP global / mock / Splunk live | false | operator | Guided T4 still `mcp_allowed=false` |

Read the deployment profile before reasoning about a live turn.

---

## 9. What the analyst typically sees (successful guided T4)

Not a T2 SOP card. Not live Splunk rows. Not a ticket. Not architecture §22.

Typical:

- Skill ownership: `guided_investigation` (or `knowledge_recall` if floors missed hunt language).
- Catalogue: out of registry / T4.
- Message: hunt / exposure **guidance** (checklist, hypotheses, “no live query”, “no MITRE/severity without evidence”).
- `human_review` / HIL: analyst must validate.
- `workflow_plan.execution_enabled=false`.
- Optional RAG citations if SOC-KB matched.
- InvestigationOutcome often `inconclusive` with `missing_evidence`.
- If semantic hop ran: `resolved_query_contract.provenance.semantic_t4` with `invoked` / `accepted` / `timed_out` / `elapsed_ms` / `circuit_state` / `human_action_required`.
- If hop failed with deferred referent: clarification handoff, **no** ResourcePlan.

---

## 10. Key files

| File | Role |
|---|---|
| `architecture.md` | Frozen target; §2.2–2.4, §5, §9–17, Example D, §22–25 |
| `docs/ai/t4_semantic_prompting_playbook.md` | Frozen T4 schema/few-shot/merge rules |
| `backend/app/api/routes_chat.py` | HTTP `/chat` |
| `backend/app/graph/resource_planner_graph.py` | RP nodes and edges |
| `backend/app/chat/pipeline.py` | `graph_node_init_routing`, finalize, RAG/SPL hooks |
| `backend/app/chat/canonical_planning_orchestrator.py` | Lane, T4 RQC, plan commit vs clarify handoff |
| `backend/app/chat/semantic_t4_understanding.py` | Hop + merge |
| `backend/app/chat/contracts/semantic_t4_proposal.py` | Frozen proposal fields |
| `backend/app/chat/resolved_query_builder.py` | Locked vs unresolved; CALL_T4; session continuity |
| `backend/app/chat/contracts/staged_sufficiency.py` | UNDERSTANDING vs EVIDENCE |
| `backend/app/chat/contracts/investigation_outcome.py` | Finalize projection |
| `backend/app/evidence/minimal_evidence_state.py` | Derived EvidenceState |
| `backend/app/chat/lane_router.py` | Match path → T4 / guided |
| `backend/app/catalogue/live_router_bind.py` | Skip bind on T4 |
| `backend/app/routing/select_route_from_understanding.py` | `_route_out_of_registry` |
| `backend/app/chat/evidence_planner.py` | Guided plan: no SPL/MCP |
| `backend/app/chat/plan_evidence_from_canonical.py` | Commit ResourcePlan |
| `backend/app/chat/skill_intent_compatibility.py` | Capability fail-closed; no widen |
| `backend/app/planner/composer.py` | Steps from EvidencePlan |
| `backend/app/planner/executor.py` | `execute_plan_dispatch` / rag_only schedule |
| `backend/app/orchestration/splunk_call_authorization.py` | AUTH0 exact-call (not reached on guided T4) |
| `backend/app/llm/clients/local_chat_client.py` | `/chat/completions` |
| `backend/app/llm/sidecar_governance.py` | Timeout, circuit, human-restart notes |
| `backend/app/safeguards/trust_boundary.py` | CONTROL_PREAMBLE + untrusted wrap |
| `env/profiles/development.env.example` | This host’s T4-on profile |

---

## 11. One-line summary

**When a question misses T1–T3, code labels it catalogue T4 and takes the guided planning lane. Architecture then wants a bounded meaning-only LLM hop, a final RQC, then a composable ResourcePlan that may include SPL and MCP. Live code often skips or times out the hop (F3), cannot let T4 change the locked intent family or grant SPL/MCP, commits a guided plan with RAG-only / no live search, and runs that plan through the Resource Planner graph as `composed_dispatch` whose executor still executes RAG hooks — specialists audit, they do not execute; InvestigationOutcome is a honest partial/inconclusive projection; Phase 10 actions do not fire.**
