# AI SOC Assistant — Canonical Architecture

**Supersedes:** `architecture.plan8-frozen-2026-08-15.md`  
**Architecture decision date:** 2026-08-20

**Reason:**  
Production architecture is being evolved from one-pass guided/recommend-only investigation toward governed LLM-assisted planning, bounded iterative investigation, capability discovery, user-approved investigation/remediation plans, and deterministic tool execution.

---

## Architecture status

**CANONICAL — 2026-08-20**

This document is the current production-target architecture. The Plan 8 freeze (2026-08-15) is historical and lives unmodified at `architecture.plan8-frozen-2026-08-15.md`. Diff those two files for the exact delta.

Meaning:

- New production `/chat` investigation work must conform to this architecture, not to the Plan 8 freeze.
- Implementation convenience is not authority to modify the architecture.
- Implementation gaps remain gaps; newly approved roles do not exist in production until they are built and proven.
- The ongoing T1–T3 catalogue/matching patch is a separate workstream and must not be disturbed by this architecture evolution.
- Architecture changes still require measured contradictory evidence and explicit approval.

Experience Center remains a behavioral UX reference only. Do not copy EC fixtures into production `/chat`.

Status vocabulary used in this document:

```text
TARGET ARCHITECTURE     required by this document; may not exist in code yet
CURRENTLY IMPLEMENTED   verified on production /chat as of 2026-08-20
IMPLEMENTATION GAP      required by the target and missing, vetoed, or misplaced in production
```

This file describes the **approved target**. It does not claim that production `/chat` already provides investigation envelopes, PlanDelta, CapabilitySnapshot, domain agents, or remediation planning.

---

## 0. What changed from the Plan 8 architecture **[NEW 2026-08-20]**

### Still valid — do not weaken

These Plan 8 invariants remain authoritative:

```text
deterministic authority over routing, clarification, capability authorization,
  PhasePolicy / PhaseContract, SPL validation, RBAC, HIL, MCP invocation,
  side-effect authorization, retry/fallback, final validation
T1–T3 before T4; T4 only for unresolved meaning
Final ResolvedQueryContract before authoritative planning
primary_skill is ownership, not a capability veto
candidate SPL is never executable
only approved non-null normalized_spl may reach MCP
exact-call authorization for every material MCP/tool invocation
  (normalized tool identity + arguments; Splunk also binds normalized_spl)
LLMs never call MCP; LLMs never acquire execution authority
EvidenceState is a derived view, not a new database
InvestigationOutcome precedes narration and action
trust classes: evidence and generated text are not control authority
RBAC / HIL remain deterministic
no uncontrolled autonomous planning/execution loop
circuit breaking / backpressure may degrade instruct and reasoning roles; restart is human-only
Resource Planner graph remains the sole execution hub
no second planner, capability database, agent mesh, or orchestration framework
production GO remains deferred; F3 T4 serving and live MCP remain unproven
```

### Newly approved — Plan 8 freeze → this document

| # | Change | Plan 8 | This architecture |
|---|---|---|---|
| D1 | Freeze | `architecture.md` read-only for Plan 8 | This file is canonical; freeze archive is unmodified |
| D2 | Investigation product | One-pass guided / recommend-only was an implementation gap against Example D | Governed LLM-assisted planning, bounded iteration, user-approved envelopes |
| D3 | `guided_investigation` | Ownership in principle; catalogs/EvidencePlan still vetoed SPL/MCP | Owner of broad investigation; **must not** veto composable RAG + SPL + MCP |
| D4 | T4 vs planning | T4 was the only named semantic LLM hop | T4 stays meaning-only. Investigation / PlanDelta / domain / remediation planning are **different reasoning roles** |
| D5 | Capability view | Read-only join allowed; richer snapshot was §25 extension | `CapabilitySnapshot` records **need × availability** (two independent axes). It does not decide per-call execution eligibility. No new service |
| D6 | Investigation plan | ResourcePlan from DET EvidencePlan; LLM plan rails retired | `InvestigationPlanProposal` → DET `ValidatedInvestigationPlan` → user approval → DET compiler → authoritative ResourcePlan + PhaseContract. Do not revive `llm_plan_bridge` |
| D7 | User plan approval | SPL confirm + action-lane ticket mock only | Investigation: Run / Edit / Cancel on the validated plan. Remediation: Approve / Edit / Cancel. Approved plans are **immutable versions** |
| D8 | Iteration | `PlanDelta` was §25 / `NOT_REQUIRED_FOR_CURRENT_SCOPE` | Bounded PlanDelta is in scope, **read-only**, append-only revisions. Writes cannot enter the investigation loop |
| D9 | Repeated tools | Composable in principle; not first-class on guided path | Same capability may run many times. Each material MCP/tool call needs a **new** exact-call grant |
| D10 | Domain agents | Four specialists are advisory auditors | Optional **reasoning workers** that return proposals with evidence refs. RP hub executes. Role-scoped snapshot views. No agent mesh |
| D11 | Remediation | Phase 10 connectors were §25 unless separately approved | If the user already requested contingent action, do not re-ask "Create remediation plan?". Always require Approve/Edit/Cancel before writes |
| D12 | Model roles | `semantic_t4` / narration = instruct | Instruct: T4, concise transform, narration. Reasoning: investigation planner, evidence reasoner, PlanDelta reasoner, domain-agent reasoning, remediation planner |
| D13 | Dual dispatch | Imperative hybrid vs RP `composed_dispatch` | One hub. Bounded loop lives inside the Resource Planner execution hub |
| D14 | T1–T3 workstream | Not called out | Catalogue matching / T2 commit hygiene remains a **separate** in-flight patch and is out of scope here |

Review corrections after the first 2026-08-20 draft (same decision; do not treat the first draft wording as canonical):

```text
CapabilitySnapshot is need × availability, not per-call executability
need and availability are independent (recommended + unavailable is valid)
authoritative ResourcePlan + PhaseContract exist only after user approval + DET compile
investigation is read-only; writes belong to remediation
domain agents are reasoning workers, not execution workers
approved plans are immutable versions; PlanDelta is append-only
user plan edits that change Final RQC re-enter understanding
exact-call authorization applies to all MCP/tools
LLM health/backpressure covers instruct and reasoning roles
raw chain-of-thought is never evidence or control
domain agents receive role-scoped capability views
InvestigationOutcome.blocked is investigation status, not a security disposition
```

### Not claimed by this decision

```text
production GO
F3 T4 serving solved
live Splunk MCP proven
Agilius / SOAR / firewall / email connectors exist
Experience Center fixtures become production
T1–T3 matcher redesign
unbounded ReAct
LLM-invented tools
one exact-call grant covering many queries
```

---

## 1. Purpose

This document defines the intended architecture and authority boundaries of the AI SOC Assistant.

It is **not** a request to rebuild the product.

Plans 2–8 already implemented most major architectural components and converged authority topology onto final RQC, ResourcePlan + PhaseContract, the existing Resource Planner hub, derived EvidenceState, and InvestigationOutcome. The 2026-08-20 decision does not replace that topology. It evolves the **investigation product** that sits on it: from one-pass guided/recommend-only answers toward governed LLM-assisted planning, capability discovery, user-approved investigation and remediation envelopes, bounded iterative tool use, and deterministic execution.

Do not add a parallel framework to match the new names.

Where this document refers to conceptual roles such as:

* shared sufficiency;
* CapabilitySnapshot (joined capability/tool view);
* investigation approval envelope;
* PlanDelta;
* execution hub;
* domain reasoning agents (reasoning workers);
* evidence state;
* investigation outcome;
* remediation plan / verification;

the existing implementation must be mapped first.

Do not create a new database, service, orchestration framework, planner or runtime merely to match terminology in this document.

---

# 2. Core architecture principles

## 2.1 Deterministic authority

Deterministic code retains final authority over:

```text
routing policy
clarification rules
capability authorization
PhasePolicy / PhaseContract
SPL validation
RBAC
HIL
MCP invocation
side-effect authorization
retry/fallback
final validation
```

LLMs provide bounded semantic reasoning, generation and synthesis.

LLMs do not acquire execution authority.

---

## 2.2 T1–T3 first, T4 only for unresolved meaning

T1–T3 deterministically resolve everything that can be reliably established.

They identify:

```text
known / authoritative fields
unresolved semantic fields
```

T4 receives the unresolved semantic responsibility plus locked context.

T4 must not regenerate the complete query contract when only part of it is unresolved.

A heavily semantic request may legitimately have many unresolved fields and therefore use T4 extensively.

---

## 2.3 Final ResolvedQueryContract is authoritative

The canonical order is:

```text
T1–T3
→ sufficiency
→ optional T4
→ deterministic T4 validation/merge
→ FINAL ResolvedQueryContract
→ clarification OR final route/owner
→ CapabilitySnapshot [DET projection of availability / policy posture]
→ InvestigationPlanProposal [LLM, non-authoritative]
→ ValidatedInvestigationPlan [DET]
→ user Run / Edit / Cancel
→ ApprovedInvestigationEnvelope [immutable version]
→ DET compiler
→ authoritative ResourcePlan + PhaseContract
```

ResourcePlan must never be committed from an earlier provisional interpretation and then followed by final route adjudication.

An LLM `InvestigationPlanProposal` is **not** a ResourcePlan. A DET `ValidatedInvestigationPlan` is what the user approves. ResourcePlan + PhaseContract become authoritative **only after** that approval and the DET compiler. Do not hold a ResourcePlan/PhaseContract both before and after approval.

---

## 2.4 Primary skill means ownership

`primary_skill` means:

> primary ownership / graph-entry signal.

It does not mean:

> only capability that may be used.

The complete ResourcePlan + PhaseContract may use multiple capabilities.

**[CHANGED 2026-08-20]** `guided_investigation` is the intended **owner** of broad out-of-catalogue investigation. It must not veto composable RAG, SPL generation, Splunk MCP, other read-only MCP, or LLM reasoning in the skill catalog, EvidencePlan, or composer.

Do not "solve" investigation by routing every hunt to `spl_generation`. Ownership stays `guided_investigation` (or whichever owner the final RQC selects); required work is expressed on the ResourcePlan.

Plan 8 already stated this principle. Production still violates it: `backend/app/skills/catalog.json` `guided_investigation.blocked_tools` still includes `mcp_execution`, and EvidencePlan still hardcodes SPL/MCP off. That is an **IMPLEMENTATION GAP**. This document does not claim the veto has been removed. The target remains: owner, not RAG-only capability boundary.

---

## 2.5 Resources are composable

A request may use:

```text
zero resources
one resource
multiple resources
repeated resources
```

Examples:

```text
LLM only
Knowledge + LLM
SPL generation only
SPL + MCP
Knowledge + SPL + MCP
MCP + reasoning
multiple evidence/tool calls
```

RAG, SPL and MCP are not three mutually exclusive routes.

**[CHANGED 2026-08-20]** Repeated use of the same capability in one investigation is first-class (for example several Splunk searches with different arguments). Each MCP/tool execution remains a distinct exact-call authorization. One grant must not cover many queries. Investigation calls remain read-only.

---

## 2.6 Side effects are separate from reasoning

Finding an answer does not automatically authorize acting on it.

Actions such as:

```text
create ticket
send email
update CRM
perform remediation
disable account
isolate endpoint
invoke a write-capable MCP tool
```

must pass explicit deterministic action policy, RBAC and HIL requirements.

**[CHANGED 2026-08-20]** Investigation work is **read-only**. Finding an answer, adapting queries, or reordering evidence steps does not authorize a write. Side-effecting work belongs to the remediation envelope.

---

## 2.7 Structured investigation outcome precedes narration and action

Evidence sufficiency produces a governed structured investigation result before free-form narration or action preparation.

`InvestigationOutcome` is the conceptual role for that result. Before implementation, audit existing production contracts such as `CanonicalFacts`, `FinalEvidenceGate`, `GovernedSynthesisPackage`, and other final-result packages. Extend or project from an existing governed package where practical; do not create a competing result authority merely to match the name.

Final synthesis narrates the outcome and supporting evidence. Free-form synthesis text is never action authority. Post-synthesis actions consume governed structured findings and decision state, not arbitrary final prose.

---

## 2.8 Evidence and generated text are not control authority

Trust classes are explicit:

```text
TRUSTED_CONTROL_AUTHORITY
  deterministic system policy
  registered trusted schemas
  approved configuration
  deterministic authorization state

USER_INTENT / UNTRUSTED_INPUT
  user text
  user uploads

UNTRUSTED_EVIDENCE
  Splunk logs/events
  RAG documents and retrieved knowledge
  MCP result content and external tool output
  emails, tickets and CRM records

NON_AUTHORITATIVE_GENERATED_CONTENT
  prior assistant prose
  LLM reasoning and synthesis text
  raw reasoning / chain-of-thought
```

Instructions found inside evidence are data, not control instructions. Evidence and generated text cannot grant capabilities, select routes, clear RBAC/HIL, alter system policy, authorize actions, or trigger remediation. Prompt construction keeps trusted control instructions separate from explicitly delimited and labelled untrusted evidence blocks.

Raw reasoning / chain-of-thought is never evidence and never control authority. Only structured, schema-validated outputs may enter planning or InvestigationOutcome, and only after deterministic acceptance.

---

## 2.9 LLM proposes; deterministic code authorizes and executes **[NEW 2026-08-20]**

```text
LLM proposes / reasons
DET authorizes / executes
```

LLMs may propose investigation strategy, PlanDelta, hypotheses, evidence-gap interpretations, candidate SPL/detection strategy, and remediation strategy.

LLMs may not:

```text
call MCP or any connector
grant capabilities
invent tools not present in CapabilitySnapshot
clear RBAC / HIL
authorize execution
mutate an approved envelope
execute remediation
```

Domain reasoning agents, if introduced, have the same prohibition. They are **reasoning workers**, not execution workers. They return structured proposals **with evidence references** to the Investigation Coordinator. Only the RP hub executes tools. There is no agent-to-agent execution mesh.

---

## 2.10 CapabilitySnapshot is a projection, not a registry **[NEW 2026-08-20]**

The planner must know which tools and capabilities **really exist**. It must not invent them.

`CapabilitySnapshot` is a deterministic, read-only join of existing authoritative sources, including where applicable:

```text
skill catalog
resource registry
PhaseRegistry
MCP registry ∩ live tools/list ∩ allowlist
Knowledge/RAG configuration
action_tool / action-lane capabilities
model/provider role registry
policy configuration
```

Also include RBAC-relevant **policy posture** (forbidden / not_granted / requires_hil) so a plan cannot treat a forbidden capability as if it were already authorized.

Do not introduce another source of truth or capability database.

Every snapshot row has **two independent dimensions**. They are not a single exclusive enum. A capability may be recommended **and** unavailable.

```text
capability_need:   required | recommended | optional
availability:      available | unavailable
```

```text
need answers:     is this capability relevant to the Final RQC / plan?
availability:     is it registered, discovered, and not policy-forbidden at snapshot time?
```

`executable` is **not** a snapshot field. CapabilitySnapshot does **not** authorize execution. Per-call execution eligibility is decided later, after an approved envelope exists, by policy, RBAC, HIL, PhaseContract, envelope version, and exact-call authorization.

Example that must remain valid:

```text
network_indicator_block
  capability_need = recommended
  availability    = unavailable
  resolution      = propose manual / network-team workflow; do not fake execution
```

A required or recommended security step with `availability=unavailable` is represented as unavailable, manual, or an alternate workflow — never as a falsely executed step.

LLMs must not invent tools outside the snapshot. Domain agents receive a **role-scoped** view of the snapshot, not the entire tool estate.

---

## 2.11 Investigation and remediation are user-approved envelopes **[NEW 2026-08-20]**

Investigation and remediation are separate envelopes.

The canonical `ApprovedInvestigationEnvelope` field list lives in **§13.1**. Do not define a competing variant here.

```text
INVESTIGATION PLAN READY
  [Run investigation]  [Edit plan]  [Cancel]
```

`Run` creates an immutable **read-only** envelope version (§13.1).

Safe read-only adaptation inside that envelope may execute without repeated user approval. Material scope expansion requires HIL. Writes are not investigation PlanDelta; they belong to remediation.

If the user **Edits** the plan:

```text
edit stays within Final RQC
  → DET re-validate → new immutable envelope version → then compile

edit changes meaning / entities / time / objective so Final RQC is stale
  → re-enter understanding (Phase 1 / clarification)
  → do not compile or execute against the previous RQC
```

```text
REMEDIATION PLAN READY
  [Approve]  [Edit]  [Cancel]
```

If the Final RQC already requested a contingent remediation action (for example "investigate and block if malicious"), do **not** redundantly ask "Create remediation plan?". Produce a remediation plan when InvestigationOutcome warrants it. **Approve / Edit / Cancel remains mandatory** before any write.

If the user did not already request remediation, ask Yes / Not now after InvestigationOutcome.

---

## 2.12 Bounded iteration is in scope; unbounded ReAct is not **[NEW 2026-08-20]**

Target investigation loop:

```text
PLAN
→ EXECUTE
→ OBSERVE
→ REASON
→ EVIDENCE sufficiency
     ├─ sufficient → InvestigationOutcome
     └─ gap exists → PlanDeltaProposal [LLM, advisory]
                      ↓
                    DET validation against envelope + snapshot + policy + budget
                      ↓
                    execute next bounded read-only step
                    OR HIL if material scope expansion
                    OR reject-to-remediation if the proposal is a write
                    OR stop (no progress / fingerprint unchanged / budget / policy)
```

This is **not** an open autonomous loop. Stop conditions are deterministic. Plan 8 §25 listed generic PlanDelta as deferred; this decision brings a **bounded, read-only** PlanDelta onto the investigation main path.

A PlanDelta that proposes a write is rejected from the investigation loop and offered only as remediation.

---

# 3. Technology authority legend

```text
[DET]
Deterministic code.
Authoritative.

[LLM]
Model reasoning/generation.
Non-authoritative until validated where required.

[HYBRID]
LLM proposes or generates;
deterministic code governs acceptance/execution.
```

---

# 4. Supporting capability/tool definitions

The architecture requires a known description of available capabilities.

This does not require a new capability service.

The existing authoritative sources may include:

```text
skill catalog
resource registry
PhaseRegistry
MCP registry/tool schemas
Knowledge/RAG configuration
model/provider registry
policy configuration
action_tool / action-lane capabilities
```

A deterministic `CapabilitySnapshot` **[CHANGED 2026-08-20]** joins those sources (plus live MCP discovery ∩ allowlist plus RBAC-relevant policy posture) into the only tool vocabulary a planner or reasoner may see.

Each joined row carries **two independent fields** (see §2.10):

```text
capability_need    required | recommended | optional
availability       available | unavailable
```

It does **not** carry execution authorization. T4 may receive short capability **descriptions** for meaning; it still cannot select or grant tools. Domain agents receive a role-scoped slice of this snapshot, not the full estate.

A read-only planner/T4 view may join existing metadata where needed.

Do not introduce another source of truth.

---

## Capability examples

```yaml
knowledge_recall:
  description: retrieve grounded SOC/security knowledge
  produces: knowledge_evidence
  side_effect: false

spl_generation:
  description: generate SPL for a specified evidence need
  produces: candidate_spl
  side_effect: false

splunk_search:
  description: execute validated read-only SPL
  produces: live_security_evidence
  side_effect: false

llm_reasoning:
  description: interpret supplied or retrieved evidence
  produces: analysis
  side_effect: false

ticket_create:
  description: create incident/service ticket
  produces: action_receipt
  side_effect: true

email_send:
  description: send approved notification email
  produces: action_receipt
  side_effect: true

crm_log:
  description: record approved case/update in CRM
  produces: action_receipt
  side_effect: true

endpoint_isolate:
  description: invoke registered remediation tool
  produces: remediation_receipt
  side_effect: true
```

New MCP servers/tools may register new capabilities without changing the orchestration architecture.

---

# 5. Canonical flow

**TARGET ARCHITECTURE:**

```text
Request/session [DET]
  ↓
PHASE 1 — T1–T3 deterministic understanding [DET]
  ↓
UNDERSTANDING sufficiency [DET]
  ├─ sufficient ──────────────────────────────┐
  └─ unresolved semantic meaning              │
       ↓                                      │
     PHASE 2 — optional bounded T4 [LLM instruct, meaning-only]
       ↓                                      │
     PHASE 3 — deterministic validation/merge │
       └──────────────────────────────────────┘
  ↓
PHASE 4 — FINAL ResolvedQueryContract [DET]
  ↓
clarification OR final owner
  ↓
PHASE 4b — CapabilitySnapshot [DET: need × availability; not execution authorization]
  ↓
PHASE 5 — InvestigationPlanProposal [LLM reasoning, non-authoritative]
           → ValidatedInvestigationPlan [DET]
           → user Run / Edit / Cancel
           → ApprovedInvestigationEnvelope [immutable version]
  ↓
PHASE 6 — DET compiler + PhaseRegistry / PhasePolicy / PhaseContract
           → authoritative ResourcePlan + PhaseContract
  ↓
PHASE 7 — RP iterative execution hub [DET]     sole executor
     ↔ Investigation Coordinator (planning role, not a second graph)
     ↔ bounded domain reasoning workers (propose only, with evidence refs)
     ↔ RAG
     ↔ SPL generation / validation
     ↔ MCP (exact-call, read-only in this envelope)
     ↔ evidence
     ↔ LLM reasoning-as-resource (structured output only; no raw CoT as evidence)
     ↔ bounded read-only PlanDelta (append-only revisions)
  ↓
PHASE 8 — EVIDENCE sufficiency [DET]
  ├─ sufficient → InvestigationOutcome
  └─ evidence gap → PlanDeltaProposal [reasoning, advisory]
                    → DET validation (must remain read-only)
                    → next bounded step OR HIL-on-scope-expand OR stop
                    write proposals leave this loop → remediation
  ↓
InvestigationOutcome [HYBRID → DET-governed structured result]
  status ≠ security disposition
  ↓
PHASE 9 — grounded narration [LLM instruct]
  ↓
final validation [DET]
  ↓
remediation
  ├─ Final RQC already requested contingent action
  │     → produce RemediationPlanProposal when warranted
  │     → skip redundant "Create remediation plan?"
  └─ else ask Yes / Not now
       ├─ Not now ────────────────────────────┐
       └─ Yes → RemediationPlanProposal       │
  then always:
       DET validation
       → user Approve / Edit / Cancel         │
       → PHASE 10 deterministic actions       │
       → verification                         │
       → post-action monitoring where required
       → update incident/change where registered
       └──────────────────────────────────────┘
  ↓
FINAL USER RESPONSE
  ↓
PHASE 11 — safe session / follow-up continuity [DET]
```

**CURRENTLY IMPLEMENTED:** T1–T3 → optional T4 → RQC → ResourcePlan (often from provisional family) → RP hub one-pass. Catalogue-T4 `guided_investigation` is RAG / recommend-only because live `skills/catalog.json` still `blocked_tools` includes `mcp_execution` (and EvidencePlan still turns SPL/MCP off). That is an **implementation gap**, not a change to this target. No CapabilitySnapshot, no investigation envelope, no PlanDelta on the RP graph, no remediation offer.

**IMPLEMENTATION GAP:** everything in the TARGET flow after final owner that is not the current one-pass ResourcePlan + RAG dispatch, including unvetoing guided SPL/MCP in catalog/EvidencePlan **without** claiming it is already fixed.

Bounded `PlanDelta` is on the investigation **target** path. It remains evidence-targeted, envelope-scoped, **read-only**, append-only, and never an open autonomous loop. Unbounded ReAct is forbidden. Writes cannot sneak into investigation.

T1–T3 catalogue matching remains a separate workstream and is not redesigned here.

---

# 6. Phase 0 — Request + Session Context `[DET]`

Inputs:

```text
current query
authenticated user
RBAC identity
session ID
safe prior-turn state
pins
investigation ID
explicit attachments/artifacts
previous clarification state
```

The previous answer itself is not automatically trusted evidence.

Controlled previous contract/evidence references may be used.

---

# 7. Phase 1 — T1–T3 Deterministic Understanding `[DET]`

T1–T3 resolve deterministically known information such as:

```text
goal/intent where known
entities
time scope
user constraints
supplied SPL/rule/content
requested output
requested actions
evidence type
known prohibitions
known clarification requirements
```

Critical query constraints include, where relevant:

```text
source IP and destination IP
host/device
account/user and account type
domain and URL
port, protocol and application
geography
event/action/result
time range
investigation-specific filters
```

These constraints are resolved into the final RQC and passed downstream. The SPL LLM or template renderer must not be expected to rediscover them opportunistically from free text.

Output:

```text
partial ResolvedQueryContract
+
known/locked fields
+
unresolved semantic fields
```

---

# 8. Shared sufficiency

Use one conceptual sufficiency vocabulary.

Do not build multiple overlapping contracts.

## UNDERSTANDING stage

Question:

> Do we know enough about the request to create the authoritative query contract?

## EVIDENCE stage

Question:

> Do we have enough evidence to answer the final query contract?

Existing deterministic evaluators should be adapted rather than replaced.

---

# 9. Phase 2 — T4 Semantic Understanding `[LLM]`

Current semantic model role:

```text
semantic_t4
→ Cisco Foundation-Sec 8B
```

The architecture depends on the role, not permanently on one model name.

---

## T4 input contract

A deterministic prompt builder provides a compact payload:

```text
original query
relevant prior safe context
LOCKED_FIELDS
UNRESOLVED_FIELDS
allowed semantic vocabulary
short relevant capability descriptions
1–3 curated few-shot examples
required structured-output schema
```

Few-shot examples are prompt assets.

They are not another RAG system.

---

## T4 responsibilities

T4 may determine:

```text
semantic analysis goal
competing hypotheses          # about what the user is asking, not whether an attack occurred
threat relationship
semantic intent details
evidence categories needed
whether clarification is necessary
```

T4 competing-hypothesis output is meaning disambiguation. Evidence/hypothesis reasoning after tools run is a **different** reasoning-class role.

T4 may not:

```text
execute tools
generate/execute MCP calls
authorize remediation
set RBAC
set HIL
change policy
override locked T1–T3 facts
grant capabilities
select final route authority
propose or commit an investigation ResourcePlan
select tools from CapabilitySnapshot as execution authority
```

**[CHANGED 2026-08-20]** T4 is not the investigation planner. Completing unresolved meaning is a different job from proposing a whole investigation strategy. Investigation planning, evidence reasoning, PlanDelta reasoning, domain-agent reasoning, and remediation planning use the **reasoning** model family (see §9.1). Expanding T4 into those roles is forbidden.

---

## 9.1 Model roles, not model names **[NEW 2026-08-20]**

Architecture binds orchestration to **roles**. It does not hard-code the execution graph to a model name.

Two model **families** exist in the current local deployment (names may change):

```text
instruct-class    (today: foundation-sec-instruct)
reasoning-class   (today: foundation-sec-reasoning)
```

Target role → family mapping:

```text
semantic_t4
concise transformations
final grounded narration
  → instruct-class

investigation planning
evidence reasoning
hypothesis reasoning
PlanDelta reasoning
domain-agent reasoning
remediation planning
  → reasoning-class
```

Semantic T4 remains a separate meaning-resolution role. It is not the investigation planner.

**CURRENTLY IMPLEMENTED:** role registry exists (`ROLE_DEFAULTS`). `semantic_t4` / narration / routing stay instruct. Several reasoning roles exist (`pattern_reasoner`, `mitre_reasoner`, `missing_evidence_reasoner`, …). `guided_investigation_plan_proposer` is mapped to **instruct** and is retired from live RP dispatch.

**IMPLEMENTATION GAP:** investigation planner, PlanDelta, domain-agent, and remediation planner roles on the reasoning family, wired into production `/chat` after DET validation.

Governance continues to reject reasoning models for routing and narration. Do not point T4 or narration at the reasoning family. F3 serving constraints apply to every additional hop. These roles are **TARGET**, not claimed live.

---

# 10. LLM serving and recovery

Instruct-class and reasoning-class hops are bounded. T4 is one instruct hop; investigation planning, evidence/hypothesis/PlanDelta/domain/remediation reasoning are additional hops. Health, circuit breaking, backpressure, and human-only restart apply to **both** families.

Timeout is a **deployment/SLO setting**, not an architectural constant.

Current constrained VPS remediation setting for semantic T4:

```text
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120
```

This value exists so the current Cisco 8B deployment can complete on the constrained VPS.

The future COE value must be selected from measurements. Additional reasoning hops need their own measured budgets; they must not silently reuse the T4 timeout as if it were architecture.

---

## Model health, circuit breaking, backpressure and human restart

The system must never restart the Cisco LLM automatically. Restart authority is human/operator only.

```text
instruct or reasoning request
   ↓
deterministic concurrency/backpressure gate
   ↓
model health + circuit state (per family / endpoint)
   ├── healthy / CLOSED or permitted HALF_OPEN probe
   │      ↓
   │   invoke model
   │
   └── saturated, failing, unavailable or OPEN
          ↓
      record diagnostic evidence
          ↓
      deterministic degrade / clarification / skip-that-role
          ↓
      HUMAN ACTION REQUIRED when restart is indicated
```

Manual recovery is separate:

```text
model unhealthy
  ↓
diagnostic evidence recorded
  ↓
circuit OPEN / that model family unavailable
  ↓
operator notification/status
  ↓
HUMAN APPROVAL / MANUAL OPERATION
  ↓
restart model/service
  ↓
deterministic health verification
  ↓
controlled HALF_OPEN probe
  ↓
CLOSED only after policy-defined success
```

There is no automatic transition from failure detection to restart. No LLM, agent, ResourcePlanner, circuit breaker, health monitor, worker, retry policy/controller, T4 call, reasoning call, or synthesis path may acquire restart authority. Only an explicitly authorized human/operator may initiate a model or serving-process restart.

The existing serving/client/runtime seam owns any future circuit breaker and backpressure implementation. It must support bounded concurrent instruct and reasoning requests, a bounded queue only where appropriate, deterministic saturation handling, timeout/degrade rather than unlimited waiting, and suppression of request storms against a failing model. Thresholds are deployment configuration, not architecture constants. No sidecar or new reliability service is introduced without separate approval.

---

# 11. Phase 3 — T4 Validation + Merge `[DET]`

Validate:

```text
schema
field eligibility
locked-field integrity
known semantic vocabulary
time/entity validity
prohibition integrity
clarification consistency
```

T4 changes only unresolved semantic fields.

Derived fields such as:

```text
required capabilities
evidence requirements
route hints
```

are recomputed deterministically from the final understanding.

---

# 12. Phase 4 — Final ResolvedQueryContract + Route `[DET]`

The final RQC is the authoritative interpretation of the current turn.

Conceptually it includes:

```text
goal/intent
entities
time scope
ambiguity
clarification
required evidence
allowed/prohibited capability boundaries
requested output
requested actions
provenance
confidence
```

The final RQC carries authoritative entities and constraints, including explicit source/destination, identity, host, network, geography, event/result, time and investigation filters where applicable. Every downstream representation is derived from this contract and must preserve locked constraints.

Canonical SPL constraint flow:

```text
user query
→ deterministic T1–T3 extraction
→ final RQC authoritative entities/constraints
→ ResourcePlan evidence requirement
→ SPL generation
→ source-specific field mapping
→ deterministic postprocessing/validation
→ normalized_spl
→ call-level authorization
→ MCP execution
```

Example:

```text
"Show failed VPN administrator logins from 203.0.113.24 yesterday."

event_type = authentication
auth_result = failed
access_type = vpn
account_type = administrator
source_ip = 203.0.113.24
time_scope = yesterday
```

Those resolved values must be carried into SPL generation; they are not suggestions for later model inference.

Then deterministic route adjudication selects the primary owner.

Primary ownership does not constrain the complete set of resources.

---

## Clarification

If clarification is required:

```text
ask focused question
store unresolved handoff
end current run
```

The next user message enters Phase 0/1 using safe prior context.

Do not build a plan for an unresolved request.

Investigation envelope HIL (Run / Edit / Cancel) happens **after** a valid plan exists. It is not a substitute for clarification.

---

# 13. Phase 5 — Investigation plan proposal, validation, and approval

ResourcePlan determines **what work is required**, but it is not created until after user approval (Phase 6).

The final RQC must be the authoritative query input to planning.

**[CHANGED 2026-08-20]** After Final RQC + CapabilitySnapshot, a reasoning model may emit a non-authoritative `InvestigationPlanProposal`. Reuse existing `InvestigationPlan` + `validate_investigation_plan` wherever they fit.

The proposal should primarily describe:

```text
goal / investigation_objective
evidence needed
dependencies
conditions
success criteria
```

It should not hard-code tool names unless a named registered capability is truly required. Deterministic validation binds evidence needs to CapabilitySnapshot rows using both axes (`capability_need` and `availability`) and produces a `ValidatedInvestigationPlan`. A row with `capability_need=recommended` and `availability=unavailable` stays on the plan as a manual/alternate step. That validated plan is what the user sees. It is **not** yet a ResourcePlan.

```text
InvestigationPlanProposal     [LLM, advisory]
  → ValidatedInvestigationPlan  [DET vs Final RQC + snapshot posture + policy]
  → user Run / Edit / Cancel
  → ApprovedInvestigationEnvelope  [immutable version]
  → DET compiler (Phase 6)
  → authoritative ResourcePlan + PhaseContract
```

The compiled ResourcePlan may include:

```text
repeated capability instances (same tool, different arguments)
envelope_version
read-only investigation steps only
plan_source = deterministic | llm_proposed_validated
```

Do not promote `workflow_plan` (inert UI skeleton, `execution_enabled=false`) into the editable investigation plan.

Do not re-enable retired `llm_plan_bridge` / `resource_plan_shadow` as a second planner. New proposals become ResourcePlan only through this sequence.

**CURRENTLY IMPLEMENTED:** ResourcePlan + composer + `InvestigationPlan` contract + validator exist. Live RP path commits ResourcePlan from EvidencePlan without a reasoning whole-investigation proposal and without user Run/Edit/Cancel.

**IMPLEMENTATION GAP:** live InvestigationPlanProposal → ValidatedInvestigationPlan → envelope HIL → then compile.

The existing ResourcePlan schema remains authoritative for the compiled object unless deliberately evolved. Do not create a competing executable schema.

---

## 13.1 ApprovedInvestigationEnvelope **[NEW 2026-08-20]**

When the validated investigation plan includes live search, multi-step evidence collection, or iterative hops, production must support:

```text
INVESTIGATION PLAN READY
  [Run investigation]
  [Edit plan]
  [Cancel]
```

`Run` creates a bounded **read-only** `ApprovedInvestigationEnvelope` as an **immutable version**. This is the **canonical field list**. Other sections reference it; they must not invent a second schema.

```text
envelope_version

objective
targets / entities
time scope
approved evidence categories
allowed read-only capabilities
source / index scope where relevant

budget:
  hop limit
  timeout
  cost / resource limits where applicable

PlanDelta policy:
  automatic bounded read-only delta allowed inside envelope
  HIL required for material scope expansion

prohibited actions
  # all writes; investigation is evidence gathering only
```

Semantics (same everywhere):

```text
safe read-only adaptation inside approved envelope
  → may execute without repeated user approval

material scope expansion
  → HIL (new envelope version; re-enter understanding if Final RQC is stale)

write / remediation
  → not part of investigation PlanDelta
  → RemediationPlan → Approve / Edit / Cancel → Phase 10
```

The approved version is not mutated. Later PlanDelta objects are **append-only revisions** that reference `envelope_version` and a prior revision fingerprint.

`Edit` is revalidated before a new immutable version can be created:

```text
edit consistent with Final RQC
  → new ValidatedInvestigationPlan
  → new envelope_version
  → then compile

edit changes meaning, entities, time, or objective so Final RQC is stale
  → re-enter Phase 1 / clarification
  → do not compile or execute against the previous RQC
```

`Cancel` ends the run without compilation or execution.

Clarification (Phase 4) still terminates before any plan. Envelope HIL is not a substitute for missing meaning; it is approval of already-understood work.

Safe read-only hops inside the envelope do not require per-query confirmation. Each MCP call still requires exact-call authorization. Scope expansion follows the §13.1 PlanDelta policy (HIL). Writes are not investigation work and must not continue inside this loop even with HIL; they become remediation.

Reuse existing HIL/handoff persistence and, where it fits, `execution_review_action`. Do not copy Experience Center chip contracts into production.

**CURRENTLY IMPLEMENTED:** clarification handoff; SPL `execution_review_action`; action-lane approve/deny. No investigation envelope.

**IMPLEMENTATION GAP:** Run / Edit / Cancel + immutable `ApprovedInvestigationEnvelope` versions.

---

# 14. Examples of ResourcePlan behavior

## Example A — “Generate this SPL query”

User:

> Generate an SPL query that shows failed privileged VPN logins from Germany during the last 24 hours.

Possible plan:

```text
SPL generation
→ deterministic SPL validation
→ return validated SPL
```

No MCP execution is required unless the user asks to run it.

No RAG is mandatory unless useful context is genuinely required.

---

## Example B — “Explain this SPL query”

```text
supplied SPL
→ LLM explanation
→ deterministic output checks
→ answer
```

No SPL generation.

No MCP.

No RAG by default.

---

## Example C — “Review this situation”

User provides alert/evidence.

Possible:

```text
supplied evidence
→ knowledge context where needed
→ evidence reasoning
→ synthesis
```

If live evidence is missing:

```text
SPL generation
→ validation
→ Splunk MCP
→ reasoning
```

Resources depend on the evidence requirement, not a fixed route.

---

## Example D — Investigation

> Check failed VPN admin logins and determine whether this looks like lateral movement.

Possible:

```text
Knowledge
→ SPL generation
→ validation
→ Splunk MCP
→ evidence reasoning
→ (bounded further Splunk / other read MCP if EvidenceState still has gaps)
→ synthesis
```

**[CHANGED 2026-08-20]** This example is the intended `guided_investigation` path, not a `spl_generation` reroute. Production must not collapse it to RAG-only / `recommend_only` solely because the owner skill is `guided_investigation`. Execution still requires snapshot availability, envelope approval, SPL validation, exact-call authorization, RBAC/HIL, and policy. Investigation steps in this example are read-only; blocking is remediation.

---

# 15. Phase 6 — ResourcePlan Compiler + PhaseContract `[DET]`

**[CHANGED 2026-08-20]** This phase runs **after** user approval of a `ValidatedInvestigationPlan`. It must not compile an unapproved proposal into an authoritative ResourcePlan.

These are complementary, not alternative.

## ResourcePlan compiler

Owns:

```text
work dependencies
schedulable resource work
runtime binding
```

## PhaseRegistry → PhasePolicy → PhaseContract

Owns mandatory lifecycle controls such as:

```text
SPL source resolution
spl_postprocessor
SPL validation
RBAC
HIL
execution gates
```

Architectural invariant:

```text
compiled ResourcePlan work
+
applicable mandatory PhaseContract obligations
=
authoritative governed execution graph
```

A compiler downgrade cannot silently erase applicable mandatory lifecycle work.

---

# 16. Phase 7 — Existing Resource Planner Execution Hub `[DET]`

The existing Resource Planner graph remains the execution authority.

Do not introduce a second executor.

Conceptually:

```text
                  Knowledge/RAG
                       │
                       ▼
                    RP HUB
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        SPL          MCP          LLM reasoning
          │            │            │
          └────────────┴────────────┘
                       │
                       ▼
                 result/evidence state
```

Each execution capability returns:

```text
status
output
provenance
error/failure
policy state
latency
```

The orchestration hub, not individual tools/models, owns what happens next.

**[CHANGED 2026-08-20]** The four Resource Planner specialists (`skill`, `knowledge`, `mcp`, `spl`) remain **advisory auditors**. They must not grow connector, discovery, tool, LLM, or execution authority.

If domain reasoning agents are added later, they are **reasoning workers**, not execution workers and not a promotion of the four specialists. An agent is justified only where domain reasoning/selection across multiple operations is useful. Simple actions stay governed action capabilities:

```text
create ticket
update incident
send email
exact firewall block
```

Typical later reasoning workers (optional, only when useful):

```text
Splunk investigation reasoner
Knowledge / RAG reasoner
```

All worker results are structured **proposals with evidence references** returned to the coordinator. The hub then executes tools. No free agent-to-agent execution mesh. One MCP server is not automatically one agent.

The bounded iterative loop (Phase 8 PlanDelta) lives **inside** this hub / `execute_plan_dispatch`. Do not keep a separate imperative hybrid executor as a second production path.

---

## 16.1 Investigation Coordinator and domain reasoning **[NEW 2026-08-20]**

Hierarchical bounded multi-agent reasoning is allowed only where domain selection across multiple operations is useful. It is **TARGET**, not a second orchestrator.

```text
Investigation Coordinator
        ↓
bounded domain task
        ↓
Domain Reasoning Agent   [reasoning worker, role-scoped snapshot view]
        ↓
structured proposal / result with evidence references
        ↓
Coordinator / deterministic planner
        ↓
RP execution hub           [sole tool/MCP executor]
        ↓
actual tool / MCP
```

The Investigation Coordinator is a **planning/reasoning role** on the existing Resource Planner path. It is not a second graph, planner, or runtime.

Potential domains (only when justified and onboarded):

```text
Splunk investigation
SOAR
Knowledge / RAG
Agilius / patch management
future endpoint / IAM domains
```

Do not use one-agent-per-tool as a rule. Simple actions remain governed action capabilities unless real domain reasoning justifies an agent:

```text
create ticket
update incident
send email
exact firewall block
```

Domain agents are **reasoning workers**, not execution workers:

```text
do not directly call MCP
do not grant capabilities
do not authorize actions
do not create peer-to-peer agent execution meshes
receive a role-scoped CapabilitySnapshot view, not the entire tool estate
return structured proposals with evidence references to the coordinator
```

The RP hub remains the sole execution authority.

**CURRENTLY IMPLEMENTED:** four advisory specialists only.

**IMPLEMENTATION GAP:** coordinator role + any domain agent. Do not promote specialists into agents.

---

## 16.2 Tool failure returns to orchestration **[NEW 2026-08-20]**

Tool/MCP/RAG/LLM-step failure returns to the hub. Deterministic policy may then:

```text
retry
alternate capability
different evidence query
degraded result
HIL
stop
```

Execution order may change based on evidence through a validated PlanDelta, not through an unrestricted ReAct/swarm loop.

---

## 16.3 RAG / knowledge contract **[NEW 2026-08-20]**

Do not design a new ingestion pipeline in this architecture phase.

Use the existing RAG/storage/query contracts (`KnowledgeRepository`, governed `retrieve_soc_kb`, import validate/save-draft/publish). Curated SOP/policy documents may initially be seeded through those mechanisms.

A future full ingestion pipeline must write to the **same** knowledge contract so retrieval, SourceEvidence, and sufficiency do not fork.

**CURRENTLY IMPLEMENTED:** JSON knowledge repository + retrieve + import draft/publish.

**IMPLEMENTATION GAP:** none required for this decision beyond seeding via existing import. Vector/chunk pipeline remains a later extension.

---

# 17. SPL lifecycle invariant

```text
final-RQC mandatory constraints [locked]
     +
applicable governed source-specific field mappings [deterministically resolved]
     ↓
governed SPL generation / source-resolution seam / spl_postprocessor
  (exact seam order follows the audited existing implementation)
     ↓
mandatory-constraint preservation check
     ↓
deterministic validation
     ↓
approved non-null normalized_spl
     ↓
call-level authorization
  (policy + RBAC + HIL + MCP gate)
     ↓
execution
```

Candidate SPL is never executable authority.

Only validated non-null normalized SPL may reach MCP execution.

## Source resolution versus postprocessing

Final-RQC mandatory constraints are locked. Applicable source-specific field mappings are deterministically resolved through governed source profiles. For example, canonical `source_ip` may map to `src`, `src_ip`, `client_ip`, `sourceAddress`, or another approved source-specific field. SPL generation and postprocessing operate using those governed constraints and mappings, and deterministic validation proves that `normalized_spl` preserved every mandatory applicable constraint.

`spl_source_resolve` retains its audited implementation ownership of source/schema resolution. `spl_postprocessor` and deterministic SPL validation retain mandatory-constraint preservation and execution-policy conformance. They must not invent an IP, user, host, domain, time range, or other query constraint absent from the final RQC or another governed source.

This is an authority and data-dependency invariant, not a mandate to move `spl_source_resolve` or override the audited implementation. Its exact placement before or after candidate generation must follow the audited existing implementation unless contradictory measured evidence requires an explicit `ARCHITECTURE_DECISION_REQUIRED` STOP approved by the user. This does not reopen Plan 7 A2/A3. Before changing SPL generation or lifecycle code, trace the actual extraction, RQC, generation, source-resolution, postprocessing, validation, and execution-gate seams and classify each `EXISTS`, `PARTIAL`, `MISSING`, or `MISPLACED`.

Every mandatory final-RQC constraint relevant to the SPL must either:

1. be represented in `normalized_spl`; or
2. carry an explicit deterministic reason why it is not applicable to that SPL.

Silent constraint dropping or widening is prohibited. When a mandatory constraint is lost, deterministic code may repair it only through an already-governed unambiguous mapping rule; otherwise reject, request governed regeneration, or clarify according to existing policy. An LLM cannot silently invent a repair.

## Authorization is bound to the governed call

Access to an MCP server or tool is not authorization for arbitrary later calls. Exact-call authorization applies to **every material MCP/tool invocation**, not only Splunk search.

The execution grant is scoped to the specific final call and binds:

```text
authenticated user/service identity
investigation and trace identity
MCP server and tool identity
normalized arguments hash
read-only / write classification
source/index scope where applicable
time range where applicable
result / timeout / resource limits
HIL state
expiry and one-run scope
approved investigation envelope_version          # read-only investigation calls
approved remediation-plan version               # write / side-effecting calls
```

For Splunk search, the grant additionally binds:

```text
validated normalized_spl
normalized SPL fingerprint/hash
permitted commands/operators
```

If `normalized_spl`, normalized arguments, tool identity, time range, source scope, selected connection/tool, envelope version, remediation-plan version, or another material bound field changes after authorization, the prior authorization is invalid and the final call must be re-evaluated. Extend the existing policy/RBAC/HIL/MCP/confirmation seams where possible; do not add an authorization service unless a code audit proves those seams cannot own the decision.

One grant must never authorize arbitrary later queries or writes.

---

# 18. Phase 8 — Evidence Sufficiency `[DET]`

## Minimal canonical EvidenceState

The core architecture has one minimal deterministic `EvidenceState` view derived from evidence already carried in graph/runtime state. It is not a database, persistence layer, or duplicate raw-evidence store.

Conceptually it exposes:

```text
required_evidence
obtained_evidence
missing_evidence
stale_evidence
invalidated_evidence
blocked_evidence
provenance
trust_class
scope
observed_at / freshness metadata where available
```

Core EvidenceState does not require every item to have a plan-step instance ID. Detailed producer/step-instance attribution remains an evidence-gated extension.

The deterministic sufficiency comparison is:

```text
Final RQC required evidence
vs
minimal canonical current EvidenceState
```

If sufficient:

```text
establish InvestigationOutcome, then synthesize
```

If incomplete:

use bounded PlanDelta refinement when permitted by the investigation envelope, policy, CapabilitySnapshot, and budget.

Target architecture supports evidence-targeted refinement.

The production system must not create an uncontrolled autonomous loop.

**[CHANGED 2026-08-20]** Bounded `PlanDelta` and repeated step-instance execution are **in scope** for investigation. They are not an open ReAct loop. Investigation PlanDelta is **read-only**. Revisions are **append-only** against the immutable `envelope_version`.

```text
EVIDENCE sufficiency reports a gap
  ↓
PlanDeltaProposal [LLM reasoning, advisory]
  ↓
DET checks:
  same envelope_version / investigation objective
  same approved targets / time / index scope
  availability = available on the (role-scoped) CapabilitySnapshot
  read-only
  not a write / side-effect   # writes never continue here, including via HIL
  RBAC / policy okay for a later exact-call
  budget / hop cap okay
  fingerprint is not identical to a prior unsuccessful delta
  PlanDelta policy allows automatic in-envelope read-only delta
  ↓
append revision → exact-call authorize → execute next bounded step
OR HIL if material scope expansion (new envelope version)
OR reject and route to remediation if the proposal is a write
OR stop
```

Example:

```text
Initial search: 922 denied + 3 allowed
Reasoning: allowed sessions materially matter
Proposal: add authentication correlation
DET: inside envelope, read-only, availability=available → execute automatically
  (new exact-call grant; prior grant is invalid)
```

If the proposed delta materially expands scope, it requires user/HIL approval of a new envelope version (and RQC re-entry if meaning changed). If it introduces a write, it is **not** an investigation PlanDelta; offer it only as remediation.

Deterministic stop conditions include: sufficient evidence, no progress, same effective fingerprint, policy block, resource exhaustion, timeout/cost budget, failed delta validation, hop cap, or envelope expiry.

Reuse existing primitives where they fit (`evaluate_guided_refinement`, hop budgets such as `MAX_MCP_HOPS`, missing-evidence reasoner, evidence observer) as **proposal/stop machinery**, not as a second planner.

## Evidence reuse and invalidation across turns

Safe follow-up context reuse is not automatic evidence reuse. Evidence applicability is evaluated against the new final RQC before it can satisfy EVIDENCE sufficiency.

Controlled lifecycle statuses may use existing equivalent vocabulary or:

```text
REUSABLE
STALE
OUT_OF_SCOPE
SUPERSEDED
INVALIDATED
BLOCKED
```

Applicability considers, where relevant:

```text
entity and account/user scope
host/device scope
IP/domain scope
geographic scope
time scope and freshness requirement
source/index
authenticated user and RBAC scope
investigation purpose
policy constraints
newer or contradictory evidence
```

A follow-up that changes a material constraint triggers evidence applicability evaluation. Evidence that does not satisfy the new RQC cannot satisfy EVIDENCE sufficiency. Historical evidence remains available for provenance/history while marked unusable for the current requirement; it is not deleted merely because it became stale or out of scope.

Canonical follow-up flow:

```text
safe session delta
→ final RQC
→ evidence reuse/invalidation evaluation
→ minimal EvidenceState
→ EVIDENCE sufficiency
```

## InvestigationOutcome

After deterministic EVIDENCE sufficiency and before final synthesis/actions, establish the authoritative structured result of the investigation. Evidence reasoning may use an LLM to propose semantic findings or hypotheses, but that proposal is non-authoritative. The resulting structured candidate must pass deterministic schema, evidence/provenance, and policy validation before it becomes the authoritative `InvestigationOutcome`. Use or minimally extend an equivalent governed production result package if one exists; do not duplicate `CanonicalFacts`, `FinalEvidenceGate`, `GovernedSynthesisPackage`, or another existing authority.

Conceptually the outcome separates **investigation status** from **security disposition**:

```text
investigation_status:
  completed | incomplete | blocked | cancelled

disposition:          # security finding; not process state
  suspicious | benign | inconclusive

findings
supported hypotheses
hypotheses not confirmed
evidence references
missing evidence
deterministic severity/risk facts where already governed
recommended actions
policy/action eligibility state
provenance/trace identity
```

`blocked` means the investigation could not complete (policy, HIL, capability, or envelope). It does **not** mean "the threat was blocked" and must not be used as a security disposition.

The exact schema and controlled vocabulary must be audited against existing code before implementation.

Invariants:

```text
LLM reasoning is not evidence.
LLM-proposed findings/hypotheses remain non-authoritative until deterministic
schema, evidence/provenance and policy validation accepts the structured outcome.
Only governed source evidence may support authoritative findings.
Final synthesis narrates InvestigationOutcome and supporting evidence.
Free-form synthesis text is never action authority.
Post-synthesis actions consume governed structured findings/decision state.
LLM-generated severity, authorization or policy conclusions are non-authoritative
unless existing deterministic policy explicitly validates them.
```

---

# 19. Phase 9 — Final Synthesis `[LLM]`

Synthesis receives:

```text
Final ResolvedQueryContract
InvestigationOutcome
minimal EvidenceState / governed supporting evidence
relevant source/provenance data
requested answer format
```

The LLM prepares or narrates a human-readable result.

It has no tool execution authority.

It may not create or upgrade the authoritative disposition, severity/risk facts, policy state, action eligibility, or evidence support. Those values come from the governed structured outcome and deterministic authorities.

Final deterministic validation applies:

```text
grounding
policy
format
security
action eligibility
```

If no approved action is requested, the validated narration may become the final user response. If an approved action is requested, Phase 9 prepares the narration but does not emit the final user response yet. Phase 10 executes first; its governed action receipt or failure is then incorporated into the final user response.

---

# 20. Phase 10 — Post-Synthesis Actions `[HYBRID + DET]`

This phase handles actions resulting from the final analysis.

It is distinct from synthesis.

**[CHANGED 2026-08-20]** Investigation and remediation are separate. Investigation is read-only. After InvestigationOutcome and grounded narration:

```text
If Final RQC already requested a contingent remediation action
  (example: "investigate and block if malicious")
  → do not ask "Create remediation plan?"
  → if InvestigationOutcome warrants action, produce RemediationPlanProposal

Else
  → ask:
        Create remediation plan?
          [Yes]
          [Not now]
  → Not now ends Phase 10 for this turn
  → Yes produces RemediationPlanProposal
```

In **all** cases, user **Approve / Edit / Cancel** is mandatory before any write. Producing a plan is not execution.

```text
InvestigationOutcome
+ refreshed CapabilitySnapshot
+ policy / SOP context
→ RemediationPlanProposal [reasoning LLM, non-authoritative]
→ DET validation against action_tools + snapshot + RBAC + policy
→ remediation plan shown
  [Approve]  [Edit]  [Cancel]
```

Only an approved remediation plan may execute. User edits are revalidated before execution. Material new write actions require approval.

**TARGET** execution lifecycle:

```text
execute
→ verify
→ post-action monitoring where required
→ update incident / change where registered
→ final governed result
```

Rollback / compensating-action requirements should be represented on the remediation plan where relevant. LLM prose cannot stand in for verification.

Do not assume currently missing connectors exist. Architecture approval of this flow does not invent SOAR, Agilius, firewall, production email, or similar. They appear in CapabilitySnapshot only after onboarding.

Examples:

```text
draft/send email
create SOC ticket
create ITSM ticket
log CRM case/update
open incident
invoke remediation MCP
isolate endpoint
disable account
block indicator
trigger approved workflow
```

---

## Action flow

```text
final RQC
+
InvestigationOutcome
+
approved action intent/payload
+
deterministic policy + RBAC + HIL
+
idempotency state
        ↓
Action intent / payload preparation
        ↓
policy
RBAC
HIL where required
idempotency / duplicate protection
        ↓
registered MCP/tool
        ↓
exact-call authorization
  (tool identity + normalized arguments;
   writes bind approved remediation-plan version)
        ↓
action receipt / failure
        ↓
final user response reports the governed action result
```

Actions do not consume free-form synthesis as authority. Ticket, email, CRM and remediation payloads must be built from governed structured findings/decision state plus explicitly approved content and policy inputs. Examples such as `ticket_create`, `email_send`, `crm_log`, `endpoint_isolate`, `account_disable`, and `indicator_block` remain separately governed side effects.

---

## LLM role in actions

LLM may generate content such as:

```text
email body
ticket summary
incident description
recommended remediation explanation
```

LLM may not send/execute it directly.

Example:

```text
LLM drafts incident email
        ↓
deterministic action package
        ↓
RBAC/HIL
        ↓
email MCP/tool
        ↓
send
```

---

## New MCP tools

A new MCP integration such as:

```text
ServiceNow
Jira
CRM
EDR
SOAR
email
IAM
endpoint security
```

registers its tools and capability metadata with existing registries.

Resource/action planning may then reference those registered capabilities.

No orchestration redesign is required merely because a new MCP server is connected.

---

## Read-only vs side-effecting MCP

Every tool must be classified.

```text
READ_ONLY

e.g.
Splunk search
ticket lookup
asset lookup
```

versus:

```text
SIDE_EFFECTING

e.g.
ticket create/update
email send
endpoint isolate
account disable
firewall block
CRM write
```

Side-effecting operations require the appropriate deterministic policy, RBAC/HIL and duplicate-execution protection.

Verification is deterministic observation that the approved action had the intended governed effect (or an honest failure).

Connectors that do not yet exist remain unregistered. They are not executable.

---

# 21. Phase 11 — Session / Follow-Up State `[DET]`

Persist only safe controlled continuity information.

Potential state:

```text
final RQC
stable entities
time scope
route/plan identity
clarifications
evidence references/status
evidence scope/freshness/applicability metadata
InvestigationOutcome reference
action receipts
investigation ID
trace ID
```

Do not maintain uncontrolled private memories per agent.

---

## Follow-up example

Turn 1:

> Check failed VPN admin logins from Germany yesterday.

Turn 2:

> What about service accounts?

Phase 0 loads previous safe context.

Phase 1 interprets the new message as a delta:

```text
retain:
  VPN failed-login scope
  Germany
  yesterday

replace/add:
  account_type = service_account
```

Then the normal sufficiency/planning/execution flow applies.

Prior evidence is evaluated against the replacement `account_type=service_account` constraint. Evidence scoped only to administrator accounts may remain in history/provenance but is `OUT_OF_SCOPE` for the new RQC and cannot satisfy the new turn's EVIDENCE sufficiency.

Do not solve generic follow-up through an ever-growing phrase catalogue.

---

# 22. Full example: investigation → ticket → email

User:

> Investigate the failed VPN admin logins from Germany yesterday. If it looks serious, create a ticket and prepare an email for the SOC team.

Flow:

```text
Phase 1
T1–T3
→ event/time/account/geo/requested actions known

Phase 2
T4 only if semantic assessment needs resolution

Phase 3
T4 validation

Phase 4
Final RQC:
  investigate authentication activity
  assess seriousness
  live evidence required
  requested actions:
    create ticket if threshold/policy met
    prepare/send email according to policy

Phase 4b
CapabilitySnapshot:
  two axes per capability (need, availability)
  not execution authorization
  example: ticket_create may be recommended and available
           isolate_endpoint may be recommended and unavailable

Phase 5
InvestigationPlanProposal [reasoning LLM, non-authoritative]
  goal, evidence needed, dependencies, conditions, success criteria
→ ValidatedInvestigationPlan [DET]
user Run / Edit / Cancel
→ ApprovedInvestigationEnvelope [immutable version; §13.1]
  read-only evidence gathering only

Phase 6
DET compiler
→ authoritative ResourcePlan + PhaseContract
  retrieve context
  generate SPL
  execute validated search (read-only)
  assess evidence
  (ticket/email are requested actions, not investigation steps)

Phase 7
RP hub executes the compiled plan
  repeated Splunk allowed as new exact-call grants
  no writes

Phase 8
minimal EvidenceState
→ evidence sufficiency
→ bounded read-only PlanDelta if gaps remain inside envelope
→ InvestigationOutcome:
  investigation_status: completed | incomplete | blocked | cancelled
  disposition: suspicious | benign | inconclusive
  supported/unconfirmed hypotheses
  governed findings and evidence refs
  action eligibility

Phase 9
final synthesis:
  narrate InvestigationOutcome
  explain supporting evidence and limitations
  no action authority in prose

skip "Create remediation plan?" because Final RQC already requested
  contingent ticket/email if serious
still require Approve / Edit / Cancel before any write

Phase 10
RemediationPlanProposal (because outcome warrants action)
  DET validate
  user Approve / Edit / Cancel
  consume final RQC + InvestigationOutcome
  exact-call grant binds approved remediation-plan version
  create governed ticket payload
  create approved email content
  deterministic policy/HIL/RBAC
  ticket MCP
  email MCP
  verification
  post-action monitoring where required
  collect receipts
if Cancel: skip writes

Final user response
  incorporate governed action receipts or failures

Phase 11
persist investigation/ticket/action references
```

---

# 23. Runtime posture

Current intended Plan 7/8 VPS posture (unchanged):

```text
LANGGRAPH_ORCHESTRATION_ENABLED=true
AI_SOC_RESOURCE_PLAN_EXECUTION_ENABLED=true
AI_SOC_PIPELINE_DISPATCH_V2_ENABLED=false
AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=true
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120
AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=false
```

The timeout is environment-specific.

It is not a permanent architectural constant.

**[NEW 2026-08-20]** Investigation-envelope HIL, PlanDelta, reasoning investigation planner, and remediation planner require **new** flags or explicit existing-flag reuse documented at implementation time. Do not silently reuse T4 flags to enable investigation planning or iteration.

Repo defaults for new investigation-execution behavior stay **off** until each seam is proven. Production GO remains deferred. F3 and live MCP remain unproven.

The T1–T3 catalogue/matching patch does not change this posture and must not be coupled to these flags.

---

# 24. Current implementation status

## Exists / substantially built

```text
T1–T3 deterministic understanding
ResolvedQueryContract
T4 semantic seam
deterministic T4 merge rules
route adjudication
ResourcePlan
PhaseRegistry
PhasePolicy
PhaseContract
deterministic compiler/merge
Resource Planner LangGraph
Knowledge/RAG
SPL lifecycle
HIL/RBAC
MCP gate / AUTH0 exact-call seam
evidence/context sufficiency
distributed evidence/result fields suitable for a derived minimal EvidenceState
governed final synthesis
CanonicalFacts / FinalEvidenceGate / GovernedSynthesisPackage result seams
controlled session pins/handoffs
prompt-injection filtering and bounded evidence-observer sanitization seams
InvestigationPlan + validate_investigation_plan (advisory; proposer retired from live dispatch)
action lane /api/actions/{id}/approve|deny
LLM role registry (instruct vs reasoning families)
MCP discovery snapshot ∩ allowlist (process-memory)
guided refinement gate (imperative path; not the live RP graph loop)
```

---

## Known minimum authority corrections

```text
1. Final RQC must precede clarification/route/ResourcePlan.

2. T1–T3 must expose known/locked versus unresolved semantic fields.

3. T4 must operate on the unresolved semantic responsibility,
   with compact few-shot prompting and deterministic validation.

4. Primary skill must not veto cross-capability ResourcePlan work.
   **[CHANGED 2026-08-20]** This is now a required product correction for
   guided_investigation catalogs/EvidencePlan, not an optional cleanup.

5. ResourcePlan must consume final RQC.

6. Generic follow-up continuity must use safe prior contract/context,
   not only phrase-specific follow-up rules.

7. Existing model serving must support deterministic health detection,
   circuit breaking, backpressure and bounded failure handling. Restart is
   human/operator-only; there is no automatic restart authority.

8. A minimal derived EvidenceState must canonically compare final-RQC
   requirements with current governed evidence, including applicability/freshness.

9. A minimal governed InvestigationOutcome seam must exist between EVIDENCE
   sufficiency and synthesis/actions, preferably by extending existing result packages.

10. SPL generation must preserve mandatory final-RQC constraints through source
    mapping, postprocessing and normalized validation.

11. Splunk execution authorization must bind to the final normalized call, not
    merely to generic tool/server access.

12. Prompt construction must separate trusted control from explicitly labelled
    untrusted evidence/generated content.
```

---

## TARGET vs CURRENTLY IMPLEMENTED vs IMPLEMENTATION GAP **[NEW 2026-08-20]**

| Concept | Target | Currently implemented | Gap |
|---|---|---|---|
| T1–T3 before T4 | required | yes | keep |
| semantic T4 meaning-only | required | yes, when hop runs | F3 serving; hop often skipped |
| Final RQC before plan | required | **misplaced** — plan can commit from provisional family | correction #1 still open |
| `guided_investigation` owner, composable RAG+SPL+MCP | required | **still violated:** `skills/catalog.json` blocks `mcp_execution` / write / remediation; EvidencePlan is RAG/`recommend_only` | unveto catalog+EvidencePlan at implementation time; do not reroute to `spl_generation`; **not fixed in this architecture drop** |
| CapabilitySnapshot (need × availability, two axes) | required | separate registries; live MCP snapshot exists | no joined projection; must **not** include execution authorization |
| InvestigationPlanProposal → ValidatedInvestigationPlan → approval → compile | required | `InvestigationPlan` + validator exist; live path commits ResourcePlan **before** approval | wire sequence; no ResourcePlan before approval |
| ApprovedInvestigationEnvelope immutable versions | required | SPL confirm + action-lane only | missing |
| RP hub sole iterative executor | required | RP `composed_dispatch` is one-pass RAG for guided; hybrid loop is imperative-only | move loop into hub |
| Bounded read-only PlanDelta (append-only) | required | Plan 8 deferred; observer/reasoner do not mutate plan | missing contract |
| Repeated exact-call MCP (all tools) | required | AUTH0 exists for Splunk-shaped calls; guided never reaches it | every material call; writes bind remediation-plan version |
| Domain reasoning workers + role-scoped snapshot | optional-where-justified | four **auditors** only | do not promote specialists; agents must not execute |
| LLM reasoning ≠ evidence; raw CoT excluded | required | InvestigationOutcome requires provenance | keep; ban CoT as evidence/control |
| InvestigationOutcome status vs disposition | required | schema currently mixes `blocked` into disposition | split |
| Remediation: skip redundant ask if already requested; Approve/Edit/Cancel always | required | no offer; action lane mock/unavailable writes | missing |
| RAG seed via existing import | required | KnowledgeRepository + import exist | no new pipeline |
| F3 / live MCP / production GO | not claimed | unproven | unchanged |

These rows are architecture status, not an implementation plan.

---

# 25. Remaining architecture extensions — not automatic current work

**[CHANGED 2026-08-20]** Bounded PlanDelta, CapabilitySnapshot, investigation/remediation envelopes, and Phase 10 *flow* are no longer automatic-deferrals. They are approved architecture. Connector implementation is still gated on real onboarding.

Still not automatic current work:

```text
full step-instance execution beyond what the envelope/PlanDelta needs
detailed per-step / producer-instance EvidenceState ledger
major serving infrastructure redesign (F3 remains unsolved by this decision)
automated remediation without user approval
Phase 10 connector/integration implementation (ticket, email, CRM, SOAR,
  Agilius, firewall, EDR) until each tool is registered and proven
Experience Center fixture reuse as production investigation
T1–T3 catalogue/matching redesign (separate in-flight workstream)
```

These remain valid extensions or separate workstreams.

They should not automatically become blocking work on this investigation track unless a measured use case requires them.

The current system must nevertheless preserve a design that does not prevent these extensions later.

---

# 26. Architecture invariants

1. T1–T3 deterministic understanding runs before T4.

2. T4 addresses unresolved semantic meaning.

3. Locked T1–T3 facts cannot be rewritten by T4.

4. T4 is **meaning-only** (instruct-class) and cannot execute tools, grant capabilities, or act as the investigation planner.

5. Final RQC is authoritative before planning.

6. Clarification terminates before planning.

7. Primary skill is ownership, not sole capability authority.

8. ResourcePlan describes required work and dependencies.

9. PhaseContract owns mandatory lifecycle controls.

10. Mandatory lifecycle work cannot disappear due to compiler downgrade.

11. Knowledge/RAG, SPL, MCP and LLM reasoning are composable.

12. A query may use none, one or many of those capabilities.

13. Explicit final-RQC entities and constraints flow into SPL generation; the SPL LLM does not rediscover them opportunistically.

14. Applicable source-specific mappings are deterministically resolved through governed source profiles; `spl_source_resolve` does not perform semantic query understanding, and its exact placement follows the audited existing implementation unless contradictory measured evidence triggers an approved `ARCHITECTURE_DECISION_REQUIRED` STOP.

15. `spl_postprocessor`/validation preserves mandatory constraints and cannot invent missing IPs, identities, hosts, domains or other constraints.

16. Every mandatory applicable RQC constraint appears in `normalized_spl` or has an explicit deterministic non-applicability reason.

17. Candidate SPL is never executable.

18. Only validated non-null normalized SPL may reach MCP.

19. MCP/tool access is not authorization for an arbitrary call; exact-call authorization binds to the final normalized tool identity and arguments (and `normalized_spl` for Splunk) and expires on material change. Writes also bind the approved remediation-plan version.

20. RBAC/HIL/policy remain deterministic.

21. Tool failure returns to orchestration.

22. Minimal EvidenceState is a derived governed view, not a new database or duplicate evidence store.

23. Detailed per-step evidence attribution is an extension; it is not required for the minimal core EvidenceState.

24. Follow-up context reuse and evidence reuse are distinct; prior evidence must pass applicability/freshness checks against the new RQC.

25. Historical evidence may remain for provenance while being unusable for the current requirement.

26. InvestigationOutcome is the governed structured result between EVIDENCE sufficiency and synthesis/actions; LLM-proposed semantic findings or hypotheses become authoritative only after deterministic schema, evidence/provenance and policy validation. `investigation_status` (including `blocked`) is process state; security `disposition` is `suspicious | benign | inconclusive`.

27. Final synthesis narrates InvestigationOutcome and supporting evidence; it does not create decision or action authority.

28. Post-synthesis actions consume final RQC, InvestigationOutcome, approved payload/intent, deterministic policy, RBAC, HIL and idempotency state—not free-form prose. When an approved action is requested, the final user response follows Phase 10 and incorporates its governed action receipt or failure.

29. LLM-generated severity, authorization or policy conclusions are not authoritative unless deterministically validated by existing policy.

30. Instructions found inside evidence are data, not control instructions.

31. Untrusted evidence and prior assistant/generated content cannot grant capabilities, select routes, clear RBAC/HIL, alter policy, authorize actions or trigger remediation.

32. Prompt builders keep trusted control instructions separate from explicitly delimited and labelled untrusted evidence/data.

33. Deterministic health detection, circuit breaking and backpressure may stop or degrade instruct and reasoning requests; they cannot restart the model.

34. Cisco LLM restart is explicit human/operator action only, followed by deterministic health verification and a controlled circuit transition.

35. No LLM, agent, ResourcePlanner, circuit breaker, health monitor, worker, retry policy/controller, T4 call, reasoning call or synthesis path can authorize model restart or create an automatic restart loop. Only an explicitly authorized human/operator may initiate a model or serving-process restart.

36. New MCP tools may be added through existing registries without redesigning orchestration.

37. Side-effecting MCP tools require policy/RBAC/HIL/idempotency controls.

38. No uncontrolled autonomous planning/execution/refinement loop is permitted. Bounded read-only PlanDelta inside an approved envelope is the only permitted investigation iteration.

39. **[NEW 2026-08-20]** `guided_investigation` (or any primary owner) must not veto composable RAG, SPL, MCP, or reasoning required by the final RQC. Do not reroute all investigations to `spl_generation` to obtain those capabilities.

40. **[NEW 2026-08-20]** T4 is meaning-only. Investigation planning, PlanDelta reasoning, domain-agent reasoning, and remediation planning are different roles and use the reasoning model family. Instruct remains the family for T4, concise transformation, and narration.

41. **[NEW 2026-08-20]** `CapabilitySnapshot` records two independent fields per row: `capability_need` (`required` / `recommended` / `optional`) and `availability` (`available` / `unavailable`). Need and availability are not mutually exclusive. The snapshot is not per-call execution eligibility. LLM-invented tools are forbidden. Domain agents receive a role-scoped snapshot view.

42. **[NEW 2026-08-20]** Authority sequence is InvestigationPlanProposal → ValidatedInvestigationPlan → user approval → DET compiler → ResourcePlan + PhaseContract. There is no authoritative ResourcePlan before approval.

43. **[NEW 2026-08-20]** Investigation is read-only. User Run/Edit/Cancel creates an immutable envelope version. PlanDelta is append-only. Writes cannot enter the investigation loop.

44. **[NEW 2026-08-20]** The same capability may be invoked repeatedly in one investigation. Each material MCP/tool execution requires a new exact-call grant. A prior grant is invalid if normalized arguments, tool identity, `normalized_spl`, envelope version, or another material bound field changes.

45. **[NEW 2026-08-20]** Domain agents are reasoning workers. They return structured proposals with evidence references to the Investigation Coordinator. They cannot call MCP, grant capabilities, authorize actions, or form an agent-to-agent mesh. The RP hub remains the sole executor. The four specialists remain advisory auditors.

46. **[NEW 2026-08-20]** Remediation is never automatic execution. If the user already requested contingent action, skip the redundant "Create remediation plan?" question and produce a plan when warranted. Approve/Edit/Cancel is always required before writes. Execute → verify → monitor.

47. **[NEW 2026-08-20]** LLM reasoning is not evidence. Raw reasoning / chain-of-thought is never evidence or control. Hypotheses and PlanDelta proposals remain non-authoritative until schema, provenance, snapshot, envelope, and policy validation.

48. **[NEW 2026-08-20]** The Resource Planner graph is the sole production investigation executor. Dual imperative vs graph investigation loops are not the target.

49. **[NEW 2026-08-20]** This architecture must not disturb the in-flight T1–T3 catalogue/matching workstream. Matcher, truth-set baseline, and T2 commit hygiene changes are out of scope here.

50. **[NEW 2026-08-20]** A user plan edit that changes Final RQC meaning, entities, time, or objective re-enters understanding. It must not compile against a stale RQC.

---

# 27. Architecture audit and implementation discipline

For every architecture role, audit:

```text
EXISTS
PARTIAL
MISSING
MISPLACED
```

Prefer:

```text
reuse
→ reorder authority
→ minimally extend existing contracts
→ verify
```

over:

```text
new framework
→ new service
→ duplicate authority
```

A failing test is not permission to change architecture.

Architecture changes require measured contradictory evidence and explicit approval.

The Plan 8 freeze document `architecture.plan8-frozen-2026-08-15.md` must remain unmodified. Implementation tracks this file. The T1–T3 catalogue patch tracks its own plan and must not be mixed into investigation-architecture implementation.
