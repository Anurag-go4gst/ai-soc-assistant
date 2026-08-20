# AI SOC Assistant — Canonical Architecture

## Architecture status

**FROZEN FOR PLAN 8 IMPLEMENTATION**

Freeze date: **2026-08-15**

Meaning:

- Plan 8 implementation must conform to this architecture.
- Implementation convenience is not authority to modify the architecture.
- During Plan 8 coding, `architecture.md` remains read-only unless contradictory measured evidence triggers an explicit `ARCHITECTURE_DECISION_REQUIRED` STOP and the user approves the resulting architecture decision.
- Implementation gaps remain gaps; this freeze does not claim that unproven target roles already exist in production.

---

## 1. Purpose

This document defines the intended architecture and authority boundaries of the AI SOC Assistant.

It is **not** a request to rebuild the product.

Plans 2–7 have already implemented most major architectural components. The current objective is to connect those components with the correct authority and execution order, fix measured gaps, and avoid adding parallel frameworks.

The code audit at `84ce333` found that the primary remaining issue is **authority topology rather than missing frameworks**.

Where this document refers to conceptual roles such as:

* shared sufficiency;
* capability/tool catalog;
* execution hub;
* evidence state;
* investigation outcome;

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
→ clarification
→ final route/owner
→ ResourcePlan
```

ResourcePlan must never be committed from an earlier provisional interpretation and then followed by final route adjudication.

---

## 2.4 Primary skill means ownership

`primary_skill` means:

> primary ownership / graph-entry signal.

It does not mean:

> only capability that may be used.

The complete ResourcePlan + PhaseContract may use multiple capabilities.

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
```

Instructions found inside evidence are data, not control instructions. Evidence and generated text cannot grant capabilities, select routes, clear RBAC/HIL, alter system policy, authorize actions, or trigger remediation. Prompt construction keeps trusted control instructions separate from explicitly delimited and labelled untrusted evidence blocks.

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
```

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

```text
Request + safe session context [DET]
  ↓
PHASE 1 — T1–T3 deterministic understanding [DET]
  ↓
UNDERSTANDING sufficiency [DET]
  ├─ sufficient ──────────────────────────────┐
  └─ unresolved semantic meaning              │
       ↓                                      │
     PHASE 2 — optional bounded T4 [LLM]      │
       ↓                                      │
     PHASE 3 — deterministic validation/merge │
       └──────────────────────────────────────┘
  ↓
PHASE 4 — final ResolvedQueryContract [DET]
  ↓
clarification OR final owner
  ↓
PHASE 5 — ResourcePlan [DET / bounded HYBRID]
  ↓
PHASE 6 — ResourcePlan Compiler + PhaseRegistry / PhasePolicy / PhaseContract [DET]
  ↓
Authoritative Governed Execution Graph [DET]
  ↓
PHASE 7 — existing Resource Planner execution hub [DET]
  ↓
minimal EvidenceState derived from existing governed state [DET]
  ↓
PHASE 8 — EVIDENCE sufficiency [DET]
  ├─ bounded evidence-targeted refinement only if proven and permitted
  └─ proceed / bounded refine / degrade / block
  ↓
InvestigationOutcome [HYBRID → deterministically governed structured result]
  ↓
PHASE 9 — response preparation / final synthesis [LLM, narration only]
  ↓
final validation [DET]
  ↓
approved action requested?
  ├─ no ─────────────────────────────────────┐
  └─ yes                                     │
       ↓                                     │
     PHASE 10 — governed post-synthesis action
       ↓                                     │
     action receipt / failure                │
       └─────────────────────────────────────┘
  ↓
FINAL USER RESPONSE
  ↓
PHASE 11 — safe session / follow-up continuity [DET]
```

`PlanDelta` is not required on the main path. Evidence-targeted refinement is an optional bounded branch, never an open autonomous loop.

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
competing hypotheses
threat relationship
semantic intent details
evidence categories needed
whether clarification is necessary
```

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
```

---

# 10. T4 serving and recovery

T4 execution is bounded.

Timeout is a **deployment/SLO setting**, not an architectural constant.

Current constrained VPS remediation setting:

```text
AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120
```

This value exists so the current Cisco 8B deployment can complete on the constrained VPS.

The future COE value must be selected from measurements.

---

## Model health, circuit breaking, backpressure and human restart

The system must never restart the Cisco LLM automatically. Restart authority is human/operator only.

```text
T4 request
   ↓
deterministic concurrency/backpressure gate
   ↓
model health + circuit state
   ├── healthy / CLOSED or permitted HALF_OPEN probe
   │      ↓
   │   invoke model
   │
   └── saturated, failing, unavailable or OPEN
          ↓
      record diagnostic evidence
          ↓
      deterministic degrade / clarification
          ↓
      HUMAN ACTION REQUIRED when restart is indicated
```

Manual recovery is separate:

```text
model unhealthy
  ↓
diagnostic evidence recorded
  ↓
circuit OPEN / T4 unavailable
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

There is no automatic transition from failure detection to restart. No LLM, agent, ResourcePlanner, circuit breaker, health monitor, worker, retry policy/controller, T4 call, or synthesis path may acquire restart authority. Only an explicitly authorized human/operator may initiate a model or serving-process restart.

The existing serving/client/runtime seam owns any future circuit breaker and backpressure implementation. It must support bounded concurrent T4 requests, a bounded queue only where appropriate, deterministic saturation handling, timeout/degrade rather than unlimited waiting, and suppression of request storms against a failing model. Thresholds are deployment configuration, not architecture constants. No sidecar or new reliability service is introduced without separate approval.

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

---

# 13. Phase 5 — ResourcePlan

ResourcePlan determines **what work is required**.

The final RQC must be its authoritative query input.

Conceptual minimum:

```yaml
objective: ...

answer_mode: ...

steps:
  - id: step_1
    capability: ...
    operation: ...
    inputs: [...]
    depends_on: [...]
    produces: [...]

required_evidence: [...]

requested_actions: [...]

budget: ...
```

The actual existing ResourcePlan schema remains authoritative unless deliberately evolved.

Do not create a competing schema.

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
→ synthesis
```

---

# 15. Phase 6 — ResourcePlan Compiler + PhaseContract `[DET]`

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

Access to Splunk/MCP is not authorization for arbitrary SPL. The execution grant/decision is scoped to the specific final call and, where available or applicable, binds:

```text
authenticated user/service identity
investigation and trace identity
Splunk connection and MCP tool
source/index scope
validated normalized_spl
normalized SPL fingerprint/hash
time range
permitted commands/operators
read-only/write classification
result limits
timeout/resource limits
HIL state
expiry and one-run scope
```

If `normalized_spl`, its time range, source scope, selected connection/tool, or another material bound field changes after authorization, the prior authorization is invalid and the final call must be re-evaluated. Extend the existing policy/RBAC/HIL/MCP/confirmation seams where possible; do not add an authorization service unless a code audit proves those seams cannot own the decision.

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

use only whatever bounded refinement behavior is currently proven and enabled.

Target architecture supports evidence-targeted refinement.

The production system must not create an uncontrolled autonomous loop.

Advanced generic `PlanDelta` and repeated step-instance execution remain implementation extensions unless separately proven necessary.

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

Conceptually the outcome may contain:

```text
disposition: suspicious | benign | inconclusive | blocked
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

The exact schema and controlled vocabulary must be audited against existing code before implementation.

Invariants:

```text
LLM-proposed findings/hypotheses remain non-authoritative until deterministic
schema, evidence/provenance and policy validation accepts the structured outcome.
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

Phase 5
ResourcePlan:
  retrieve context
  generate SPL
  execute validated search
  assess evidence

Phase 6
PhaseContract:
  SPL validation
  RBAC/HIL/MCP requirements

Phase 7
execute investigation

Phase 8
minimal EvidenceState
→ evidence sufficiency
→ InvestigationOutcome:
  disposition
  supported/unconfirmed hypotheses
  governed findings and evidence refs
  action eligibility

Phase 9
final synthesis:
  narrate InvestigationOutcome
  explain supporting evidence and limitations
  no action authority in prose

Phase 10
post-synthesis action:
  consume final RQC + InvestigationOutcome
  create governed ticket payload
  create approved email content
  deterministic policy/HIL/RBAC
  ticket MCP
  email MCP
  collect receipts

Final user response
  incorporate governed action receipts or failures

Phase 11
persist investigation/ticket/action references
```

---

# 23. Runtime posture

Current intended Plan 7 VPS posture:

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
MCP gate
evidence/context sufficiency
distributed evidence/result fields suitable for a derived minimal EvidenceState
governed final synthesis
CanonicalFacts / FinalEvidenceGate / GovernedSynthesisPackage result seams
controlled session pins/handoffs
prompt-injection filtering and bounded evidence-observer sanitization seams
```

---

## Known minimum authority corrections

```text
1. Final RQC must precede clarification/route/ResourcePlan.

2. T1–T3 must expose known/locked versus unresolved semantic fields.

3. T4 must operate on the unresolved semantic responsibility,
   with compact few-shot prompting and deterministic validation.

4. Primary skill must not veto cross-capability ResourcePlan work.

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

# 25. Advanced architecture extensions — not automatic current work

The audit identified useful future capabilities:

```text
full step-instance execution
detailed per-step / producer-instance EvidenceState ledger
generic PlanDelta
multi-round evidence refinement
richer capability snapshot
major serving infrastructure redesign
automated remediation framework beyond separately approved actions
Phase 10 connector/integration implementation (ticket, email, CRM, remediation) unless separately approved
```

These are valid architectural extensions.

They should not automatically become current blocking implementation work unless a measured use case requires them.

The current system must nevertheless preserve a design that does not prevent these extensions later.

---

# 26. Architecture invariants

1. T1–T3 deterministic understanding runs before T4.

2. T4 addresses unresolved semantic meaning.

3. Locked T1–T3 facts cannot be rewritten by T4.

4. T4 is reasoning-only and cannot execute tools.

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

19. Splunk/MCP access is not authorization for an arbitrary call; execution authorization binds to the final normalized call and expires on material change.

20. RBAC/HIL/policy remain deterministic.

21. Tool failure returns to orchestration.

22. Minimal EvidenceState is a derived governed view, not a new database or duplicate evidence store.

23. Detailed per-step evidence attribution is an extension; it is not required for the minimal core EvidenceState.

24. Follow-up context reuse and evidence reuse are distinct; prior evidence must pass applicability/freshness checks against the new RQC.

25. Historical evidence may remain for provenance while being unusable for the current requirement.

26. InvestigationOutcome is the governed structured result between EVIDENCE sufficiency and synthesis/actions; LLM-proposed semantic findings or hypotheses become authoritative only after deterministic schema, evidence/provenance and policy validation.

27. Final synthesis narrates InvestigationOutcome and supporting evidence; it does not create decision or action authority.

28. Post-synthesis actions consume final RQC, InvestigationOutcome, approved payload/intent, deterministic policy, RBAC, HIL and idempotency state—not free-form prose. When an approved action is requested, the final user response follows Phase 10 and incorporates its governed action receipt or failure.

29. LLM-generated severity, authorization or policy conclusions are not authoritative unless deterministically validated by existing policy.

30. Instructions found inside evidence are data, not control instructions.

31. Untrusted evidence and prior assistant/generated content cannot grant capabilities, select routes, clear RBAC/HIL, alter policy, authorize actions or trigger remediation.

32. Prompt builders keep trusted control instructions separate from explicitly delimited and labelled untrusted evidence/data.

33. Deterministic health detection, circuit breaking and backpressure may stop or degrade T4 requests; they cannot restart the model.

34. Cisco LLM restart is explicit human/operator action only, followed by deterministic health verification and a controlled circuit transition.

35. No LLM, agent, ResourcePlanner, circuit breaker, health monitor, worker, retry policy/controller, T4 call or synthesis path can authorize model restart or create an automatic restart loop. Only an explicitly authorized human/operator may initiate a model or serving-process restart.

36. New MCP tools may be added through existing registries without redesigning orchestration.

37. Side-effecting MCP tools require policy/RBAC/HIL/idempotency controls.

38. No uncontrolled autonomous planning/execution/refinement loop is permitted.

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
