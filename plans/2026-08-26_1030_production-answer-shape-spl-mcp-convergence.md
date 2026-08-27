---
name: production-answer-shape-spl-mcp-convergence
overview: "Post-P10: converge production /chat on EC answer shape via governed multi-goal objective persistence, conditional remediation/email, and isolated mock-MCP proof — without weakening J7 or enabling live MCP."
status: draft
date: 2026-08-26
canonical_plan: plans/2026-08-26_1030_production-answer-shape-spl-mcp-convergence.md
loop_runner: plans/LOOP_RUNNER_production-answer-shape-spl-mcp-convergence.md
architecture_authority: architecture.md
architecture_policy: read_only
live_mcp: default_off_until_P11
verified_release_baseline_sha: 6b63df610ff4a0994a593537ab46c71464afe570
last_product_change_sha: c109402d69956df455a780fd49a191fa173ab7ac
product_decision_b4: PRESERVE_CONDITIONAL_INTENT_WITHOUT_WEAKENING_EVIDENCE_AUTHORITY
---

# POST-P10 PRODUCTION ANSWER & TOOL-ORCHESTRATION CONVERGENCE

## Positioning

This is a **new bounded product-quality plan** starting from the fully promoted P10 release baseline. It is **not**:

- P8 defect closure
- a P9 prerequisite
- a P10 prerequisite
- P11 / live MCP activation
- a second master plan or second orchestration architecture

| Label | SHA |
|---|---|
| **VERIFIED_RELEASE_BASELINE_SHA** | `6b63df610ff4a0994a593537ab46c71464afe570` |
| **LAST_PRODUCT_CHANGE_SHA** | `c109402d69956df455a780fd49a191fa173ab7ac` |

Independently verified (operator attestation, post-handoff): GitHub `master`, `release/p10-final`, and `feat/complete-or-abstain-t4-ux`, plus the VPS checkout, all point at `6b63df61…`. Product code tip remains `c109402d…`; `c109402d..6b63df61` is docs/handoff only.

**Do not trust stale master-plan status tables.** Where `plans/2026-08-25_1806_ai-soc-master-parallel-closure.md` still shows P8 `EVALUATED_FAIL` / P9–P10 `TODO`, later P9/P10 promotion and handoff evidence plus Git ancestry win. **P8, P9, and P10 are closed.** Do not reopen them.

**Historical P10 handoff meta is point-in-time.** `docs/evals/p10_handoff/handoff_meta.json` fields such as `push_performed=false` / `merge_performed=false` / `deploy_performed=false` describe the state **when that packet was committed**. They are **not** current operational truth. Do not rewrite that historical evidence. Phase **0.1** still re-attests remote `master`, worktree start SHA, and runtime/VPS SHA when runtime validation is used.

P10 itself recorded the follow-on gap this plan owns (`future_post_master_plan_gap`):  
investigation → evidence → conclusion → **conditional remediation** → **conditional email/communication draft** → HIL → send.

Suggested (do **not** create during plan authoring):

```bash
git worktree add ../ai-soc-wt-post-p10-convergence -b ws/post-p10-answer-tool-convergence 6b63df610ff4a0994a593537ab46c71464afe570
```

---

## Objective

"Done" means: for every row in the convergence expectation bank, a live production `/chat` turn returns the **expected answer shape and tool/action posture** along this lifecycle:

```text
USER OBJECTIVE
→ ORIENTATION
→ INVESTIGATION PLAN
→ APPROVE / EDIT / CANCEL
→ EVIDENCE / TOOL COLLECTION
→ FINDINGS
→ CONCLUSION
→ RECOMMENDED NEXT ACTION
→ ELIGIBLE REMEDIATION          # only when J7 / outcome eligibility holds
→ CONDITIONAL DOWNSTREAM ACTIONS  # preserved even when not yet eligible
→ HIL BEFORE SIDE EFFECTS
```

The central problem is **preserving a complete multi-stage user objective** through:

```text
Final RQC
├── investigation objective / evidence requirements
└── requested conditional actions
    - remediation intent
    - email_draft intent
    - recipient_roles
    - governed predicate(s)

Approve (UI) → investigation_review_action = "run"
→ immutable read-only ApprovedInvestigationEnvelope

→ ResourcePlan + PhaseContract   # READ-ONLY investigation only
→ EvidenceState
→ InvestigationOutcome

Then:
Final RQC requested actions
+ InvestigationOutcome
→ deterministic eligibility / predicate evaluation
→ Phase 10 remediation / action path   # ticket/email are NOT ResourcePlan steps
→ final answer contract
```

— not merely reordering frontend cards.

### Investigation HIL vocabulary (accepted production contract)

| Surface | Vocabulary |
|---|---|
| **Visible investigation controls** | **Approve / Edit / Cancel** |
| **Governed wire actions** | `run` / `edit` / `cancel` |

So: **Approve** investigation plan → `investigation_review_action = "run"` → creates immutable read-only **ApprovedInvestigationEnvelope**.

Do **not** revert the production UI back to a visible “Run investigation” label.

**Remediation** also uses **Approve / Edit / Cancel**, but it is a **separate HIL gate** for write-capable actions — not the investigation envelope approval.

### ResourcePlan is read-only investigation only

- Ticket / email / remediation are **requested actions** owned by **Final RQC**, not investigation ResourcePlan steps.
- After envelope approval, ResourcePlan + PhaseContract execute **read-only** investigation only.
- Conditional remediation/email resolve **after** InvestigationOutcome via the Phase 10 remediation/action path.
- Do **not** place conditional remediation/email actions inside ResourcePlan.

### What this plan does NOT deliver

**Production answers will not match Experience Center prose.** EC is a deterministic fixture and is **not** the system under test; it defines the target *shape* only. Production must never import or execute EC fixtures.

| EC today | Production after this plan |
|---|---|
| Fixture prose, agent narrative, S4 workflow copy | Live governed pipeline answers — **different text** |
| Synthetic "live" hunt rows | Mock rows labelled simulated (isolated profile only), or no MCP if flags stay off |
| Full EC stages (`opening_narrative`, `brief`, `connection_trace`, …) | Deferred unless a PROTECTED `schemas/responses.py` packet is separately approved |
| — | Live Splunk / P11 **untouched** |

Honest promise: **eligibility-driven shape + objective-persistence convergence** on the bank — not EC content equality, not live MCP.

Non-goals: live Splunk MCP (P11), new env flag *names*, `architecture.md` edits, weakening J7 evidence authority, EC content parity, inventing recipient email addresses, a second planner/router/MCP framework/state machine.

### Invariants (never negotiable)

1. `architecture.md` read-only. A discovered conflict is an operator decision, not an edit.
2. `candidate_spl` never executes. Only validator-approved, non-null `normalized_spl` may approach the MCP execution gate.
3. LLM output is advisory. The LLM may recommend tools, draft prose, or propose plans; only deterministic code selects/invokes tools or authorizes side effects. `supports_tool_calling` stays `False`; no `tools` array reaches the wire.
4. EC (`backend/app/demo/`) stays isolated. `app/demo/ec_email.py` is never reused by production.
5. Discovery metadata is capability information, **not** execution authority.
6. **No new env flag name.** A new *profile file* composed of existing flags is permitted; a new flag name is a STOP.
7. A capability being enabled must never equal a surface being rendered.
8. **J7 evidence authority remains true.** Knowledge-only / SOP-only / incomplete / inconclusive evidence → **no** remediation plan PRESENT and **no** write. Completed + evidence-backed `suspicious` (+ policy) → remediation plan **may PRESENT** under REMEDIATION PLAN ELIGIBILITY; write still needs separate Approve. Showing a plan ≠ USER-CONDITIONAL ACTION ELIGIBILITY and ≠ execution.
9. Mock evidence ≠ real SourceEvidence. Mock results never establish compromise, unlock real remediation/write authority, or set `live_mcp_proven`.
10. Extend existing authority path only — Final RQC (owns investigation objective **and** requested conditional actions) → ApprovedInvestigationEnvelope → ResourcePlan (**read-only investigation only**) → EvidenceState / InvestigationOutcome → Phase 10 remediation/action lane. **No** second planner, conditional-action planner, second Resource Planner, alternate state machine, EC execution path, or side-channel action registry.
11. **Single Resource Planner / registry authority.** The existing Resource Planner graph/hub remains the sole **investigation** execution planner/executor authority. The existing governed tool registry, capability policy/catalog, MCP effective catalog, RAG / curated knowledge registry/crosswalk, and provenance registry remain the authoritative seams. Email / communication integrate via **Final RQC requested actions + Phase 10 action/remediation path** into those registries — **not** as ResourcePlan investigation steps. **Do not** create a second capability DB, second tool registry, email-specific planner, communication orchestration framework, parallel MCP registry, second RAG catalogue, or action side-channel. Where a capability is missing, **extend the existing authoritative registry**.

---

## Final product decision — B4

**B4 = PRESERVE CONDITIONAL INTENT WITHOUT WEAKENING EVIDENCE AUTHORITY.**

B1 / B2 / B3 are **retired** (not unresolved choices). In particular, **B1 is rejected**: do not make an active remediation CTA eligible merely because an investigation-shaped turn reached any conclusion.

### Conditional-action lifecycle (do not collapse)

| State | Meaning |
|---|---|
| **REQUESTED** | User objective asked for this action (possibly under a condition) |
| **PENDING_CONDITION** | Requested, but governing condition not yet satisfied |
| **ELIGIBLE** | Condition + InvestigationOutcome / policy gates satisfied; may surface as proposal |
| **APPROVED** | Analyst HIL approved the proposal |
| **EXECUTED** | Deterministic connector ran under authorization |

Example:

> If compromise is confirmed, remediate and draft an email to the firewall and identity teams.

**Two distinct gates — do not collapse:**

| Gate | Eligibility |
|---|---|
| **REMEDIATION PLAN ELIGIBILITY** | `completed` + evidence-backed `suspicious` InvestigationOutcome + remediation policy / J7 eligibility. May **PRESENT** a RemediationPlanProposal for analyst **Approve / Edit / Cancel**. **NO write** until analyst Approves. Does **not** require `compromise_confirmed` merely to **show** a remediation plan. |
| **USER-CONDITIONAL ACTION ELIGIBILITY** | Action **REQUESTED** on Final RQC + exact governed `predicate_id` satisfied + action policy / HIL requirements. |

**`suspicious` ≠ `compromise_confirmed`.**

If outcome is completed + suspicious but compromise is **not** confirmed under the user’s predicate:

- remediation plan = **MAY BE PRESENT** (plan eligibility)
- remediation execution = **NO** without approval
- email intent = **PENDING_CONDITION**
- email send = **NO**
- Do **not** claim compromise confirmed

Before evidence confirms the user’s predicate (and before suspicious completion):

- user-conditional remediation/email intents may be **PENDING_CONDITION** / visible as intent
- email send authority = **ABSENT**
- remediation **execution** = **ABSENT**

After completed + suspicious (plan eligibility) **and** (separately) after the exact user predicate is satisfied (conditional-action eligibility):

- remediation plan may be shown; execution still needs HIL Approve
- email draft may become **ELIGIBLE** only if REQUESTED + predicate true; send still separate HIL

Aligns with `architecture.md` D11 / §2.11 / §22: contingent remediation requested in Final RQC → do not re-ask “Create remediation plan?” when warranted; **Approve / Edit / Cancel** remains mandatory before writes. **Warranted ≠ inconclusive.** Showing a plan ≠ claiming the user’s conditional predicate is true.

### Governed condition predicates (not free-text authority)

Shorthand such as `condition: compromise_confirmed` in examples is **conceptual only**. Target representation must use a **governed predicate**, not arbitrary free-text as action authority:

```text
condition:
  predicate_id: account_compromise_confirmed   # example id — exact id from existing or minimal extension
```

| Rule | Requirement |
|---|---|
| Predicate evaluation authority | **DETERMINISTIC** |
| Allowed inputs | InvestigationOutcome; accepted EvidenceState; policy / authorization state; approved operator state where applicable |
| LLM may | extract/propose the intended condition; explain it |
| LLM may **not** | decide the condition has become true; transition PENDING_CONDITION → ELIGIBLE; authorize an action; perform **any** conditional-action lifecycle transition |

**Conditional-action state authority (all transitions):**

| Transition | Authority |
|---|---|
| REQUESTED → PENDING_CONDITION | Deterministic plan/contract normalization |
| PENDING_CONDITION → ELIGIBLE | Deterministic governed predicate evaluation **only** |
| ELIGIBLE → APPROVED | Explicit HIL only where approval is required |
| APPROVED → EXECUTED | Deterministic authorized connector/action executor **only** |

An LLM-generated email draft is **never** APPROVED or EXECUTED by itself.

**Preflight (Phase 1):** inspect whether a deterministic predicate mechanism already exists on **Final RQC** (`resolved_query.py` / `resolved_query_builder.py`) and action contracts. If not, identify the **minimum extension** to Final RQC first. **Do not** create a separate condition engine or second planner. **Do not** jump first to `schemas/responses.py`.

### Skill identity is not business authority

`_selected_skill(state) == "knowledge_recall"` must not be the sole veto for multi-goal turns that also contain investigation + conditional remediation. Replace skill-identity vetoes with **contract-driven** gates:

- Pure knowledge: `answer_mode == knowledge_only_answer` → no remediation
- Multi-goal: investigation + SOP + conditional remediation → **preserve all goals**; CTA still depends on InvestigationOutcome / evidence
- Knowledge / SOP / RAG **coexist** with investigation; they are not mutually exclusive categories
- Do **not** turn `knowledge_recall` into remediation authority

`backend/app/chat/remediation_runtime.py` is **governance-sensitive** (accepted J7 seam). Before any edit, record: CURRENT CONTRACT → PROPOSED CONTRACT → WHY J7 REMAINS TRUE → POSITIVE TEST → NEGATIVE TEST → ROLLBACK. Do not treat it as “unfrozen therefore safe.”

---

## Primary design case (eval bank only — never hardcode into product)

```text
Investigate the 25 failed SSH logins followed by a successful login to the
admin account from 198.51.100.42. Determine whether the account is
compromised. If the evidence confirms malicious activity, prepare the
remediation actions and draft an email to the firewall and identity teams
summarizing the evidence and requesting the required containment actions.
```

Observed (baseline behaviour to preserve where correct):

- routes toward auth_success_after_failure / `attack_discovery`-class investigation
- requires governed evidence; does not claim compromise when evidence is insufficient
- does not expose remediation CTA when J7 criteria fail
- does not execute MCP when disabled

Lost today (this plan’s product gap):

- conditional remediation objective
- conditional email-draft objective
- recipient **roles** (`firewall_team`, `identity_team`)
- full multi-stage objective after initial investigation routing
- possible confusion of “draft an email” with “investigate an email”

**Do not hardcode this exact query into product logic.** It is a primary architectural evaluation row only.

---

## Email architecture (objective persistence first)

Diagnosis: the primary gap is **objective persistence on Final RQC**, not “missing COE email config,” and not ResourcePlan steps.

Preserve on **Final RQC** (predicate is governed — see B4 section):

```text
requested_conditional_actions / communication_intent:   # Final RQC owns these
  - remediation intent (optional)
  - email_draft:
      condition:
        predicate_id: account_compromise_confirmed   # conceptual example
      recipient_roles:
        - firewall_team
        - identity_team
```

Target flow:

```text
user objective → Final RQC (investigation + requested conditional actions)
→ Approve/Edit/Cancel (UI) → wire run/edit/cancel → ApprovedInvestigationEnvelope
→ ResourcePlan (READ-ONLY investigation only) → InvestigationOutcome
→ deterministic plan eligibility + user-conditional predicate evaluation
→ Phase 10 remediation/action path
→ email draft (ELIGIBLE only if predicate) → HIL → send (separate)
```

Integrate email into the **existing** capability policy/catalog and Phase 10 action/remediation lane — **not** as a ResourcePlan investigation step and **not** a new communication framework.

Three distinct cases (do not collapse):

| Case | Meaning |
|---|---|
| **A** | “Investigate this suspicious email” → email/phishing **investigation** capability (ResourcePlan / evidence) |
| **B** | “Draft an email to the firewall team” → **communication drafting** (Final RQC requested action → Phase 10) |
| **C** | “Send the approved email” → **external side-effect** requiring authorization/HIL |

- **Investigate email ≠ draft email ≠ send email.**
- Do **not** invent recipient email addresses.
- Initial support is **role-based** (`firewall_team`, `identity_team`, `incident_commander`, `system_owner`). Recipient resolution is a later governed step.
- Do **not** require a production default recipient merely to make an eval pass.
- **Email draft ≠ email send.** A draft may be produced without send authority. Send requires separate HIL.

---

## State-aware answer shapes (UI is a consequence)

Define **one** canonical analyst-visible investigation plan surface. Prefer the existing governed investigation/evidence plan + approval contract.

**Do not** blindly revive generic `workflow_plan`. Measured fact: `knowledge_recall` always has a non-empty blueprint (3 steps). `workflow_plan has steps` ≠ “show analyst investigation plan.” Audit whether `workflow_plan` carries unique analyst-relevant information; if it is primarily orchestration metadata, keep it diagnostic/provenance only. Avoid two competing plan cards.

| State | Analyst-visible shape |
|---|---|
| **A — awaiting investigation approval** | orientation; investigation plan; **Approve / Edit / Cancel** (wire: `run` / `edit` / `cancel`). **No** terminal conclusion pretending investigation already happened; **no** mock/live MCP until envelope approved |
| **B — approved / investigating** | plan status after ApprovedInvestigationEnvelope; **progress/execution telemetry** (below); current findings only from accepted evidence; limitations |
| **C — terminal inconclusive** | findings; inconclusive conclusion; important missing evidence; recommended next action; **conditional requested downstream actions may be mentioned**; **NO** active remediation plan CTA unless REMEDIATION PLAN ELIGIBILITY allows; user-conditional email remains PENDING_CONDITION if predicate unmet |
| **D — terminal suspicious / evidence-backed** | findings; conclusion; recommended next action; **remediation plan may PRESENT** under REMEDIATION PLAN ELIGIBILITY (Approve/Edit/Cancel — separate write HIL); user-conditional email draft only if USER-CONDITIONAL ACTION ELIGIBILITY holds; HIL before write/send |
| **E — pure knowledge/SOP** | answer; sources/provenance; **NO** investigation plan unless genuinely investigation-shaped; **NO** remediation; **NO** MCP merely because MCP is available |

**State B — progress telemetry ≠ EvidenceState authority.** Distinguish explicitly:

| Channel | Contents | Authority |
|---|---|---|
| **PROGRESS / EXECUTION TELEMETRY** | planned, attempted, failed, skipped, empty, retry diagnostics | Observable to the analyst; **never** factual EvidenceState |
| **SOURCE EVIDENCE** | only actually obtained **and accepted** evidence | Sole EvidenceState factual authority |

State B may show progress, but progress events must **never** become EvidenceState factual authority. Preserve the existing EvidenceState invariant.

Frontend ordering follows these states; it is not the primary architecture.

---

## Eligibility / assertion contract

| Surface / assertion | Renders / true iff |
|---|---|
| Investigation plan (canonical) | Investigation-shaped Final RQC / pending `investigation_approval` (not “workflow_plan length ≥ 1”); controls **Approve / Edit / Cancel** → wire `run` / `edit` / `cancel` |
| Remediation plan proposal | **REMEDIATION PLAN ELIGIBILITY** (completed + suspicious + J7/policy) — may PRESENT without user `compromise_confirmed`; separate Approve/Edit/Cancel before writes |
| User-conditional remediation / email intent | REQUESTED or PENDING_CONDITION on Final RQC; **USER-CONDITIONAL ACTION ELIGIBILITY** for ELIGIBLE transitions — never skill name alone |
| Email draft | ELIGIBLE only when REQUESTED + exact predicate satisfied; still not send |
| Email send | Separate HIL / authorization |
| MCP tool trace | Named capability selected; `executed` reflects reality; mock labelled mock; **envelope-bound** exact-call grant |

### Split execution assertions (eval spec — not automatic schema growth)

Do **not** overload a single `execution_eligible` in bank expectations. Assert at least conceptually:

- `mcp_read_execution_eligible`
- `remediation_execution_eligible`
- `write_execution_eligible`
- `email_send_eligible`

Exact field names: determine in preflight by inspecting existing contracts. **Do not** automatically add `schemas/responses.py` fields. If the payload cannot represent the distinction, raise a **protected change packet**.

### LLM expectation

Do **not** require global `live_llm_called = false`. The LLM may be used for bounded semantic proposal, allowed reasoning roles, answer composition, and email drafting, provided it does **not**: own routing, decide evidence truth, authorize MCP, authorize remediation, authorize email send, or call MCP directly. Eval tests **authority**, not arbitrary absence of an LLM call.

---

## Convergence bank

Harness: extend / reuse `scripts/eval_investigation_answer_shape.py` patterns → `scripts/eval_convergence_expectations.py` + `docs/evals/answer_shape/convergence_expectation_bank_v1.json`.

**Primary multi-goal row family** (outcome/profile variants — do **not** assert multi-goal ⇒ automatic remediation CTA):

| row_id | Profile | Pins |
|---|---|---|
| `CV.MULTI.01A` | MCP OFF / insufficient evidence | plan PRESENT; SOP context PRESENT; conclusion INCONCLUSIVE; conditional remediation/email intents PRESERVED (PENDING_CONDITION); remediation plan ABSENT; email send ABSENT; false execution claims = 0 |
| `CV.MULTI.01B` | evidence-backed suspicious; user predicate not necessarily true | plan PRESENT; findings PRESENT; conclusion SUSPICIOUS; **remediation plan MAY PRESENT** (plan eligibility); write = HIL REQUIRED; email draft ELIGIBLE only if predicate satisfied else PENDING_CONDITION; email send = HIL REQUIRED / ABSENT until approved; do not claim compromise_confirmed unless predicate true |
| `CV.MULTI.01C` | isolated mock MCP after envelope Approve | named tool selected YES; mock invocation YES only **after** ApprovedInvestigationEnvelope; mock evidence labelled simulated YES; real incident evidence NO; remediation/write authority from mock = NO; grants bound to envelope_version |
| `CV.SOP.01` | pure SOP / knowledge | no remediation CTA; no SPL required; no mock MCP call; no investigation plan unless genuinely investigation-shaped |
| `CV.SPL.*` / `CV.NOMCP.*` / `CV.TRACE.*` | as measured | honest SPL posture; mock mode alone must not trigger calls; trace-derived seams |

Also seed the primary SSH/admin design-case query as the MULTI.01 family text (or paraphrase), never into product code.

---

## Mock MCP (accepted in principle — test-only)

Dedicated isolated profile (existing flag names only), **non-default**:

```text
MCP_MODE=mock
MCP_GLOBAL_EXECUTION_ENABLED=true
MCP_SERVER_MOCK_EXECUTION_ENABLED=true
SPLUNK_MCP_ENABLED=false
SPLUNK_MCP_BASE_URL=   # empty
SPLUNK_MCP_TOKEN=      # empty
```

Default COE/VPS remains `MCP_GLOBAL_EXECUTION_ENABLED=false`. P11 remains NOT STARTED. Mock proves orchestration only. Mock result ≠ real SourceEvidence; not real compromise evidence; not remediation authority; not write authority; never `live_mcp_proven`. No mock profile becomes the default deployment profile.

**Envelope-bound authorization (Phase 5):** Before investigation Approve (UI) → wire `run` → immutable ApprovedInvestigationEnvelope: **mock MCP invocation = NO**. After `envelope_version=N`, every material mock call requires a **new** exact-call authorization bound to at least: approved `envelope_version`, exact tool/server, normalized arguments, `normalized_spl` where applicable, RBAC/policy context. Changing `envelope_version` invalidates the prior grant. Mock follows the same authorization architecture as eventual live MCP.

**Verify in Phase 5.1:** no production deployment manifest / default profile references the mock profile by default (compose, env profile selector, COE runbooks).

**Declared posture exception:** master-plan “MCP default-off through P10” remains true for default profiles; `coe-mock` (name TBD) is a deliberate non-default test profile only.

---

## Deferred (not on the critical path)

| ID | Item |
|---|---|
| **DEFERRED_P11_MCP_READINESS** | Durable Postgres MCP discovery snapshot (changes restart/discovery semantics; rewrites pinned production-enforcement contract) |
| **DEFERRED_ACTION_CAPABILITY_GENERALIZATION** | `create_ticket` proposable-bucket / global action-lane enablement — email is the required downstream proof; do not enable action-lane proposals globally merely for unrelated ticket visibility |
| **OPTIONAL_PHASE_S** | Splunk efficiency advisory lints in `draft_quality.py` (advisory ≠ validator; never weaken `spl_validator.py`) |
| **DEFERRED_TECH_DEBT** | Dead `if True or settings.ai_soc_spl_template_governance_enabled` cleanup in `pipeline.py` (zero-behaviour; protected) |

If preflight proves email orchestration **cannot** reuse the existing action contract without the proposable-bucket abstraction, show that dependency **before** implementing — do not silently re-expand scope.

---

## Historical P8 packets

Before referencing any historical P8 protected packet, **verify current HEAD** at the release baseline.

| Packet | Rule |
|---|---|
| `P8-J7-KNOWLEDGE-REMEDIATION-OFFER` | Likely **SUPERSEDED** by shipped `remediation_offer_cta_eligible` (`ed1445ae` lineage). Verify; do not re-apply. |
| `P8-D-CHATPANEL-SCENARIO-PICKER` | Verify whether demo empty-state leakage is already gone on `6b63df61`. If present fixed → **CLOSED**. If still open → exact packet + approval. **Never assume open.** |

---

## Dependency order

```text
0.1 → 0.2 → 0.3 → 0.4
 → 1.1 → 1.2 → 1.3 → 1.4 → 1.5
 → 2.1 → 2.2 → 2.3 → 2.4 → 2.5
 → 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6 → 3.7
      ├─→ 4.1 → 4.2 → 4.3 → 4.4          # SPL stream (parallelizable)
      ├─→ 5.1 → … → 5.7                  # mock-MCP stream (parallelizable)
      └─→ 6.1 → … → 6.9                  # answer/UI after Phase 3
              └─→ (MCP/mock-render items may also depend on 5.5–5.6)
 → 7.1   # waits for Phase 4 complete|skipped-by-evidence, Phase 5 complete, Phase 6 complete
```

**After Phase 3 closes** (objective persistence + state contract + B4 + email draft contract), Phase **6** answer/UI convergence may proceed on those contracts. Phases **4** and **5** are **parallelizable** bounded streams (a single `loop-asap` worker may still execute them sequentially). Phase 6 items that render MCP/mock execution state may depend on Phase **5.5–5.6**. Do **not** block unrelated answer-shape work on mock-MCP completion. Do not create conflicting file ownership across streams — one owner per file; queue handoffs.

Phase **7** waits for: Phase 4 complete **or** explicitly SKIPPED_BY_EVIDENCE; Phase 5 complete; Phase 6 complete.

Stop for operator review at phase boundaries where material architecture changed (especially after Phase 1 contract decisions and after Phase 3 B4 wiring).

### Trace diagnosis schema (Phase 0.3 artifact)

Each trace in `docs/evals/answer_shape/trace_diagnosis_v1.md` (and any harness export) records:

```text
PRIMARY_FAILURE_SEAM: <exactly one>
CONTRIBUTING_SEAMS:   [<zero or more>]
```

- **PRIMARY** answers: “What earliest/root architectural seam materially prevented the intended outcome?”
- **CONTRIBUTING** captures later or parallel blockers (e.g. `MCP_DISABLED`, `SPL_NOT_EXECUTED`, `CAPABILITY_UNAVAILABLE`).
- Do **not** force a multi-stage pipeline failure into a single explanation.
- Closed primary vocabulary includes at least: `G0`, `G1`, `G-TMPL`, `G-SLOT`, `G15`, `OBJECTIVE_PERSISTENCE`, `CAPABILITY_SELECTION`, `AUTHORIZATION`, `ENVIRONMENT_UNRESOLVED`, plus other named seams as measured.
- **No** final primary seam of bare `"unknown"`. If the environment prevents classification, primary = `ENVIRONMENT_UNRESOLVED` with quoted blocker.

---

## Checklist

### Phase 0 — Post-P10 baseline + evidence

- [x] **0.1** — Re-attest release baseline
  - **Do:** Record `git rev-parse HEAD` in the worktree; `git fetch` and record remote `origin/master`, `origin/release/p10-final`, and coordination branch tips; confirm start SHA equals or is descended from `VERIFIED_RELEASE_BASELINE_SHA` (`6b63df61…`). If runtime/VPS validation will be used, record that host’s checkout SHA. Confirm `LAST_PRODUCT_CHANGE_SHA` (`c109402d…`) remains the product tip for code behaviour. Do **not** rewrite `docs/evals/p10_handoff/handoff_meta.json`.
  - **Verify:** Written attestation in `docs/evals/answer_shape/baseline_v1.md` (or successor path) with all SHAs; any mismatch stops the loop.
  - **Depends on:** none
  - **Evidence:** `docs/evals/answer_shape/baseline_v1.md` written 2026-08-26T17:28:13Z. Remotes `origin/master`/`origin/release/p10-final`/`origin/feat/complete-or-abstain-t4-ux` = `6b63df61…`. Cursor workspace HEAD=`c109402d…` (ancestor only — not execution root). Created worktree `/Users/aagarwal/Downloads/ai-soc-wt-post-p10-convergence` @ `ws/post-p10-answer-tool-convergence` = `6b63df61…` (`START_EQUALS_OR_DESCENDED=yes`). Product tip still `c109402d…`. VPS not probed. `handoff_meta.json` not rewritten. Verdict PASS.

- [x] **0.2** — Ingest/review reported production traces
  - **Do:** Pull or attach the reported trace bundles for the two operator-reported production failures (and the primary SSH/admin design-case if a live host run exists). Use existing `scripts/fetch_debug_bundle.sh` with **environment-derived** `BASE` (read `AI_SOC_*_HOST_PORT` from the target `.env` — never hard-code historical 8011/8012/3010/3013). No credentials in plan, git, or artifacts.
  - **Verify:** Non-empty JSON with `trace_id`, steps, SPL/validation or explicit degrade reason; HTTP success not 401 when live pull is used.
  - **Depends on:** 0.1
  - **Evidence:** **DONE_WITH_ENVIRONMENT_UNRESOLVED_INPUTS** (operator decision 2026-08-26 continue-loop). Safe non-credentialled discovery **FOUND_NONE** (`docs/evals/answer_shape/traces/0.2_discovery_audit.md`). Prod failures #1/#2 recorded as `ENVIRONMENT_UNRESOLVED` with reason `authoritative trace_id / redacted bundle unavailable to this execution environment.` (not fabricated/substituted). In-process design-case capture `docs/evals/answer_shape/traces/design_case_ssh_admin_in_process.json`: `trace_id=97a0661e-24b2-4fd5-bc16-7579853a34e6`, steps=3, skill=`knowledge_recall`, mode=`clarification`, VERIFY_NONEMPTY=True; role=ADDITIONAL_DIAGNOSTIC_ONLY. No credentialed fetch. Conclusions about the two unavailable production traces remain unresolved.

- [x] **0.3** — Classify failure seams (primary + contributing)
  - **Do:** For each trace, assign exactly one `PRIMARY_FAILURE_SEAM` (earliest/root architectural seam that materially prevented the intended outcome) and zero or more `CONTRIBUTING_SEAMS` (later or parallel blockers). Use the Trace diagnosis schema above. Separately note whether conditional remediation/email intent was lost (`OBJECTIVE_PERSISTENCE` often primary even when MCP is also off).
  - **Verify:** `docs/evals/answer_shape/trace_diagnosis_v1.md` — every trace has exactly one primary; contributing list may be empty; **no** bare `"unknown"` primary (use `ENVIRONMENT_UNRESOLVED` if needed); primary counts sum to traces reviewed.
  - **Depends on:** 0.2
  - **Evidence:** Wrote `docs/evals/answer_shape/trace_diagnosis_v1.md`. Primaries: prod#1/#2 = `ENVIRONMENT_UNRESOLVED` (no invented root cause); design-case = `OBJECTIVE_PERSISTENCE` with CONTRIBUTING `[CAPABILITY_SELECTION, ENVIRONMENT_UNRESOLVED]`. Checksum 2+1=3 reviewed. VERIFY_0.3_PASS. Commit: `5895cb48`.

- [x] **0.4** — Build and freeze the convergence bank + suite baseline
  - **Do:** Add `scripts/eval_convergence_expectations.py` + `docs/evals/answer_shape/convergence_expectation_bank_v1.json` with MULTI.01A/B/C, SOP, SPL, NOMCP, TRACE rows and the primary design-case text. Where TRACE rows carry diagnosis, include `PRIMARY_FAILURE_SEAM` + `CONTRIBUTING_SEAMS`. Freeze baseline. Record full pytest failure **node-ID** set, governance, frontend test/build, RACES baseline SHA.
  - **Verify:** Two consecutive harness runs byte-identical; `--check` frozen; baseline doc lists SHAs and failure node-IDs.
  - **Depends on:** 0.3
  - **Evidence:** Bank+harness+frozen baseline added. BYTE_IDENTICAL_OK; `--check` PASS; summary pass=4 product_gap=3 deferred_live=2 fail=0. Suite doc `docs/evals/answer_shape/suite_baseline_v1.md`; pytest node-IDs `pytest_failure_node_ids_v1.txt` (404 host-venv failures — environment-contaminated; not treated as plan-introduced product defects). Protected `--check` 15/15. RACES_BASELINE_SHA=`27970ea4…`. Frontend/governance deferred to phase boundaries.

### Phase 1 — Multi-goal objective persistence (Final RQC first)

**Primary contract gap:** Final RQC. Governance-sensitive preflight files:

- `backend/app/chat/contracts/resolved_query.py`
- `backend/app/chat/resolved_query_builder.py`

Current RQC does **not** structurally preserve `requested_actions` / conditional actions / recipient roles / requested outputs. Audit/extend **Final RQC first**. Do **not** smuggle into provenance, `workflow_plan`, or unrelated metadata. Do **not** jump first to `schemas/responses.py`.

- [x] **1.1** — Trace current Final RQC extraction for multi-goal / conditional language
  - **Do:** On the primary design-case query (in-process), document which fields survive into Final RQC today by reading `resolved_query.py` + `resolved_query_builder.py` (goals, remediation request, communication/email, recipient roles, **governed condition/predicate** if any). File:line evidence only — no product change. Preflight: does a deterministic predicate mechanism already exist on RQC?
  - **Verify:** Memo under `docs/evals/answer_shape/` with file:line; lists present vs lost intents; predicate mechanism PRESENT/ABSENT; confirms RQC is the structural gap if intents are lost.
  - **Depends on:** 0.4
  - **Evidence:** `docs/evals/answer_shape/rqc_multigoal_audit_v1.md` — RQC fields at `resolved_query.py:44-76`; requested_conditional_actions/email/recipient_roles/predicate ABSENT; RQC structural gap confirmed; predicate mechanism ABSENT.

- [x] **1.2** — Confirm ResourcePlan stays read-only investigation (no conditional action smuggling)
  - **Do:** Same query: confirm ResourcePlan / PhaseContract carries **investigation evidence steps only**. Document that remediation/email/recipient_roles/predicates must **not** be ResourcePlan steps; they belong on Final RQC → Phase 10 after InvestigationOutcome. Record any current incorrect placement as a defect to remove, not extend.
  - **Verify:** Memo continues 1.1; explicit “ResourcePlan must remain read-only investigation” attestation; gap list for RQC-owned requested actions.
  - **Depends on:** 1.1
  - **Evidence:** Same memo §1.2 — no typed email/remediation/recipient ResourcePlan step kinds; read-only investigation attested; RQC-owned gap list recorded.

- [x] **1.3** — Prove whether conditional actions / recipient roles survive end-to-end today
  - **Do:** Run `CV.MULTI.01A` expectations against current HEAD; record actual vs expected for intent preservation and remediation-plan / email gates.
  - **Verify:** Harness report row `CV.MULTI.01A`; failures named as PRODUCT_GAP vs PASS.
  - **Depends on:** 1.2
  - **Evidence:** Frozen harness `CV.MULTI.01A` = PRODUCT_GAP (investigation_plan_PRESENT_unmet; conditional_remediation/email intents not preserved). VERIFY_1.3_PASS.

- [x] **1.4** — Minimal Final RQC contract support only if missing
  - **Do:** If 1.1–1.3 prove Final RQC cannot represent requested conditional actions + governed `predicate_id` + `recipient_roles` + lifecycle states, extend **`resolved_query.py` / `resolved_query_builder.py`** (and only then other consumers). Raise a protected packet for `schemas/responses.py` / pipeline **only if** wire exposure is required after RQC owns the fields. **Reuse an existing field only when its current semantics exactly represent the required concept.** Do **not** repurpose provenance, diagnostics, generic metadata, or `workflow_plan` message fields. Do **not** put conditional actions into ResourcePlan. **No** second planner / condition engine / side-channel registry.
  - **Verify:** Either “no schema change required” with proof that named RQC fields already mean the required concepts, or an exact protected packet path starting with RQC CURRENT/PROPOSED contract.
  - **Depends on:** 1.3
  - **Evidence:** Extended RQC (`RequestedConditionalAction`, `requested_conditional_actions`, `requested_outputs`); packet `docs/evals/answer_shape/rqc_1_4_contract_packet.md`; `schemas/responses.py` not touched. Tests `test_resolved_query_contract.py` 10 passed.

- [x] **1.5** — Persist investigation + SOP + remediation condition + email intent on Final RQC simultaneously
  - **Do:** Implement the minimal RQC persistence wiring approved in 1.4 so multi-goal turns keep all intents without granting write/send authority early and without ResourcePlan ownership of those actions.
  - **Verify:** `CV.MULTI.01A` — intents PRESERVED on RQC; remediation plan ABSENT when not plan-eligible; email send ABSENT; `CV.SOP.01` unchanged (no remediation).
  - **Depends on:** 1.4
  - **Evidence:** Builder `_extract_requested_conditional_actions` preserves remediation+email_draft+roles+predicate as PENDING_CONDITION on design-case (VERIFY_1.4_EXTRACT_PASS). No write/send granted. End-to-end answer-shape CV.MULTI.01A remains PRODUCT_GAP until Phase 2/3 surfacing (RQC persistence proven separately).

### Phase 2 — State-aware answer contract

- [x] **2.1** — Define state A–E contracts in the bank and docs
  - **Do:** Encode A–E expected surfaces into bank metadata / shape contract doc; map each MULTI/SOP row to a state.
  - **Verify:** Every bank row names exactly one primary state; doc checked in.
  - **Depends on:** 1.5
  - **Evidence:** `answer_state_contract_v1.md` + bank `primary_answer_state` on all 9 rows (exactly one each).

- [x] **2.2** — One canonical investigation plan surface
  - **Do:** Audit `workflow_plan` vs `investigation_approval` / evidence plan. Choose one analyst-visible plan. If `workflow_plan` is metadata-only, keep it collapsed/diagnostic.
  - **Verify:** Written decision with file:line; no dual plan cards in UI fixtures for state A.
  - **Depends on:** 2.1
  - **Evidence:** `canonical_investigation_plan_surface_v1.md` — canonical = investigation_approval card; workflow_plan diagnostic-only.

- [x] **2.3** — Plan-before-terminal-answer behaviour (state A)
  - **Do:** While investigation approval is pending, surface plan + **Approve / Edit / Cancel** (wire `run` / `edit` / `cancel`) **before** any terminal conclusion that pretends investigation finished. No MCP (mock or live) before ApprovedInvestigationEnvelope.
  - **Verify:** Frontend DOM-order test for pending vs decided; harness payload gates for state A; Approve maps to `run`.
  - **Depends on:** 2.2
  - **Evidence:** Existing `InvestigationPlanApprovalCard.test.tsx` pins Approve/Edit/Cancel and Approve→`investigation_review_action: 'run'` — vitest **2 passed**. P4 envelope tests pin no execution before envelope.

- [x] **2.4** — Findings / conclusion / limitations contract (states B–D)
  - **Do:** Ensure findings and conclusion (including honest inconclusive) are distinct from diagnostics; limitations/missing evidence named when inconclusive.
  - **Verify:** `CV.MULTI.01A` inconclusive conclusion + missing-evidence; `CV.MULTI.01B` suspicious conclusion.
  - **Depends on:** 2.3
  - **Evidence:** Production `InvestigationOutcome`/`InvestigationOutcomeCard` already separates findings, disposition (conclusion), missing_evidence/limitations from progress diagnostics — pinned. Fixtures `docs/evals/answer_shape/fixtures/cv_multi_01{a,b}_outcome.json`. `pytest app/tests/test_answer_shape_findings_conclusion_contract.py -q` → **4 passed** (01A disposition=inconclusive + missing_evidence/limitations named; 01B disposition=suspicious + findings PRESENT; progress not in findings; no compromise_confirmed). Vitest `InvestigationOutcomeCard.test.tsx` → **8 passed**. Harness scores fixture contract: 01A observed disposition=inconclusive missing_evidence_count=2; 01B disposition=suspicious findings_count=1; conclusion/findings/missing gaps cleared (end-to-end plan/intent gaps remain PRODUCT_GAP). `eval_convergence_expectations.py --check` PASS after baseline refresh.

- [x] **2.5** — Conditional requested-actions display without CTA inflation
  - **Do:** When intents are PENDING_CONDITION, surface them as requested/conditional next actions — **not** as remediation CTA or send buttons.
  - **Verify:** `CV.MULTI.01A` shows preserved intent language / structured intent; remediation CTA absent; negative test that UI cannot treat PENDING_CONDITION as ELIGIBLE.
  - **Depends on:** 2.4
  - **Evidence:** DONE 2026-08-26. The existing redacted `control_plane_trace.resolved_query` projection now carries only allowlisted Final-RQC action kind/lifecycle/governed predicate/recipient-role identifiers; no free text, address, eligibility, approval, or execution fields. Production `ChatBubble` renders `PENDING_CONDITION` rows in a non-interactive “Requested conditional actions” card with explicit “not eligible, approved, sent, or executed” copy. `CV.MULTI.01A` DOM test pins remediation + email-draft intent, governed condition, `firewall_team`/`identity_team`, and absence of Approve/Send/remediation CTA; ELIGIBLE rows cannot enter the pending surface. Backend targeted → **27 passed**; frontend targeted → **10 passed**; `npm run build` PASS; convergence bank `--check` PASS byte-identical (`4e4816d4…`). Invariant check PASS: no LLM→MCP/SPL/state/flag/demo changes, no authority-bearing fields exposed, tests only added. Live LLM separately observed **ENVIRONMENT_UNRESOLVED**: configured `local_primary` + `foundation_sec_reasoning` health = red/`URLError`; Qwen intentionally wired-disabled; no live success claimed.

### Phase 3 — Remediation + email under B4

- [x] **3.1** — Remove skill-identity veto via contract logic (governance-sensitive)
  - **Do:** Replace `_selected_skill == "knowledge_recall"` business veto with contract gates (`knowledge_only_answer`, investigation-shaped RQC, outcome eligibility). Keep distinct **REMEDIATION PLAN ELIGIBILITY** (completed+suspicious+J7) vs **USER-CONDITIONAL ACTION ELIGIBILITY** (REQUESTED + predicate). Record CURRENT/PROPOSED/WHY J7 REMAINS TRUE/tests/rollback before editing `remediation_runtime.py`.
  - **Verify:** Updated `test_j7_remediation_evidence_authority.py`; pure SOP → no remediation plan; multi-goal with insufficient evidence → no plan CTA but intents preserved; completed+suspicious → remediation plan may PRESENT; predicate-unmet email stays PENDING_CONDITION.
  - **Depends on:** 2.5
  - **Evidence:** DONE 2026-08-27. Required packet: `docs/evals/answer_shape/remediation_runtime_3_1_contract_packet.md` (CURRENT/PROPOSED/J7/POSITIVE/NEGATIVE/ROLLBACK). Removed the direct `_selected_skill == knowledge_recall` veto and reused existing `investigation_outcome_applicable()` over Final RQC + current contract surfaces. All J7 positive gates remain: planner enabled + Outcome V2 applicability + `remediation_offer_required` + completed + suspicious; `knowledge_only_answer` remains negative. Tests pin pure SOP no CTA, multi-goal investigation survives a stale knowledge skill label, incomplete/inconclusive preserves actions without CTA, and predicate-unmet email stays PENDING_CONDITION. J7 + P10 + product-applicability → **53 passed**; RACES isolation → **8 passed**; convergence bank `--check` byte-identical PASS. Invariant check PASS: no LLM/MCP/SPL/state/flag/demo/connector changes; no lifecycle transition added.

- [x] **3.2** — Preserve J7 evidence authority (regression pin)
  - **Do:** No weakening of evidence-backed plan eligibility. Incomplete/inconclusive → remediation plan ABSENT. Do not require `compromise_confirmed` merely to show a plan when completed+suspicious.
  - **Verify:** J6/J7 journey commands green; `CV.MULTI.01A` plan ABSENT; `CV.SOP.01` plan ABSENT; `CV.MULTI.01B` may PRESENT plan without claiming compromise_confirmed.
  - **Depends on:** 3.1
  - **Evidence:** DONE 2026-08-27. Added `test_post_p10_j7_convergence.py` with row-named deterministic pins: `CV.MULTI.01A` incomplete+inconclusive → remediation plan/approval/envelope ABSENT while requested intent stays PENDING_CONDITION; `CV.SOP.01` knowledge contract → ABSENT even under a malformed suspicious-shaped outcome; `CV.MULTI.01B` completed+suspicious → validated remediation plan MAY PRESENT without `compromise_confirmed` claim, approval envelope, write, or conditional-email transition. Deterministic J6/J7 + convergence command → **40 passed**. Historical `eval_p8_c_journeys.py` live-LLM rerun is **ENVIRONMENT_UNRESOLVED** because configured endpoints are red/`URLError`; it was not reported as a live pass and its historical scorecard was not rewritten. Test-only diff; runtime/J7 code unchanged from verified 3.1.

- [x] **3.3** — Implement B4 with two distinct eligibility gates end-to-end
  - **Do:** Wire REQUESTED → PENDING_CONDITION → ELIGIBLE for **user-conditional** actions via exact predicates; separately allow RemediationPlanProposal under REMEDIATION PLAN ELIGIBILITY without collapsing into the user predicate. Remediation Approve/Edit/Cancel is a separate write HIL.
  - **Verify:** `CV.MULTI.01A` vs `CV.MULTI.01B` differ on the axes named in the bank; suspicious ≠ compromise_confirmed pinned.
  - **Depends on:** 3.2
  - **Evidence:** DONE 2026-08-27. Governance packet: `docs/evals/answer_shape/remediation_runtime_3_3_contract_packet.md`. Existing Phase-10 seam now separates `remediation_plan_eligible` (planner enabled + investigation-shaped Final RQC + completed + suspicious + evidence refs + non-knowledge contract) from the optional create-plan CTA (`remediation_offer_required`). Closed predicate resolver advances only predicate-bearing REQUESTED→PENDING_CONDITION and exact PENDING_CONDITION→ELIGIBLE; `account_compromise_confirmed` requires a strict true EvidenceState assertion bound to intersecting outcome evidence refs plus collected-environment FinalEvidenceGate permission. Suspicious/key-presence/mock/simulated evidence cannot satisfy it. Pre-requested remediation directly presents the existing validated plan with Approve/Edit/Cancel posture; no redundant create ask, approval envelope, execution, or email send. With no injected/turn-budget LLM seam, automatic plan uses the honest deterministic baseline and records `attempted=false`; no live success fabricated. B4/J7/L2/P13/product-applicability → **129 passed**; RACES isolation → **8 passed**; convergence `--check` byte-identical PASS. Two stale test fixtures were corrected to include evidence refs matching their claimed evidence-backed suspicious posture. Invariant check PASS.

- [x] **3.4** — Email draft on Phase 10 / action lane (not ResourcePlan)
  - **Do:** When Final RQC requests `email_draft`, resolve via Phase 10 remediation/action path after InvestigationOutcome — **not** as a ResourcePlan investigation step. Distinguish cases A/B/C. Never reuse `ec_email.py`.
  - **Verify:** Unit/integration tests for draft-planned vs send-not-planned; ResourcePlan steps contain no email_send/email_draft; `CV.MULTI.01B` draft eligibility only when predicate satisfied.
  - **Depends on:** 3.3
  - **Evidence:** DONE 2026-08-27. Governance packet: `docs/evals/answer_shape/phase10_email_action_lane_3_4_contract_packet.md`. The post-InvestigationOutcome Phase-10 seam now always runs deterministic Final-RQC conditional-action resolution, independently of the optional remediation-planner flag; explicit remediation review remains flag-gated. `CV.MULTI.01B` exact accepted predicate evidence advances only `email_draft` to `ELIGIBLE`; the unmet `CV.MULTI.01A` shape remains `PENDING_CONDITION`. Neither path creates `email_send`, remediation approval/execution, or an action proposal. A real deterministic hybrid ResourcePlan composition is pinned to contain no `email_draft`, `email_send`, or `action:*` step. No demo email module, recipient address, provider call, or draft prose was introduced; those remain 3.5–3.7. Focused lane/J7 tests → **14 passed**; broader P10/P11/P13/ResourcePlan suite → **139 passed** (one existing Starlette deprecation warning); convergence `--check` byte-identical PASS; invariant check PASS.

- [x] **3.5** — Role-based recipients
  - **Do:** Persist `recipient_roles` without inventing addresses. Resolution may remain unresolved / HIL clarification — do not invent emails to pass eval.
  - **Verify:** Roles survive on MULTI.01*; no literal invented addresses in fixtures; negative test.
  - **Depends on:** 3.4
  - **Evidence:** DONE 2026-08-27. Final-RQC `RequestedConditionalAction.recipient_roles` now enforces the governed role-id allowlist (`firewall_team`, `identity_team`, `incident_commander`, `system_owner`), deduplicates roles, and drops unknown values or address-shaped strings. Deterministic extraction recognizes all four roles. The safe debug projection shares the same allowlist, and the redacted session RQC pin now persists conditional action kind/lifecycle/predicate/roles without accepting recipient-address or draft-content fields. The MULTI design-case roles survive extraction, Phase-10 resolution, trace projection, and session pinning; unsupported roles and `analyst@example.invalid` are negative-tested and absent from stored output. Convergence fixtures contain no `@`, recipient address, or recipient email fields. Focused RQC/session/trace/Phase-10 tests → **37 passed**; broader role/P10/P11/P13 suite → **124 passed** (one existing Starlette deprecation warning); convergence `--check` byte-identical PASS; invariant check PASS.

- [x] **3.6** — Email draft production (governed)
  - **Do:** When ELIGIBLE, produce draft content from governed structured findings + approved inputs; LLM may draft prose under existing authority rules.
  - **Verify:** Draft present on `CV.MULTI.01B` when eligible; absent send; authority tests.
  - **Depends on:** 3.5
  - **Evidence:** DONE 2026-08-27. Protected/governance packet: `docs/evals/answer_shape/email_draft_3_6_protected_change_packet.md`. Added typed additive `GovernedEmailDraft` output on the Phase-10 `/chat` path and an analyst-visible draft-only card. Production occurs only for Final-RQC `email_draft=ELIGIBLE` plus completed+suspicious InvestigationOutcome with accepted findings and evidence refs. The deterministic draft consumes only those governed fields, severity, and allowlisted role ids; it has no address field and pins `recipient_resolution_required=true`, `llm_attempted=false`, `llm_status=not_attempted_no_governed_email_role`, `send_authorized=false`, and `sent=false`. No new LLM role/provider/model/prompt was added, no unreachable live provider was called or claimed successful, and no demo email module was reused. Unmet predicate or missing governed findings/evidence yields no draft. Protected `pipeline.py`/`schemas/responses.py` changes are content-pinned by exact SHA-256 in the RACES freeze test, so any later byte drift fails. Broad RACES/wire/P10/P11/P13/RQC/session suite → **130 passed** (one existing Starlette deprecation warning); frontend draft/pending-state tests → **2 passed**; production frontend build PASS (existing bundle-size advisory only); convergence `--check` byte-identical PASS; invariant check PASS.

- [x] **3.7** — Separate HIL-authorized send proof
  - **Do:** Prove send cannot fire from draft or proposal alone; requires separate HIL/authorization path.
  - **Verify:** Explicit negative test + harness `email_send_eligible=false` until approved; `CV.MULTI.01A` send ABSENT.
  - **Depends on:** 3.6
  - **Evidence:** DONE 2026-08-27. Governance note: `docs/evals/answer_shape/email_send_hil_3_7_contract_packet.md`. Added fail-closed `email_send_eligible()` on the Phase-10 seam (Final-RQC has no `email_send` kind; draft/PENDING/ELIGIBLE/remediation Approve/LLM-shaped payload/missing recipients all → False). No connector/executor introduced. Negative suite `test_email_send_hil_3_7.py` → **8 passed**; with lane/lifecycle/J7 → **21 passed**; P10 planning slice → **28 passed**. Harness ABSENT/HIL pin tightened without baseline drift → `--check` byte-identical PASS. No protected freeze-path edits. Invariant check PASS (no LLM→MCP, no SPL, no EC, no new flags, no TypedDict channel).

### Phase 4 — SPL diagnosis / targeted coverage

- [x] **4.1** — Gate histogram / root cause
  - **Do:** From 0.3 + bank, count gates using PRIMARY seams (contributing seams noted separately). **Do not** assume template enablement is the fix.
  - **Verify:** `docs/evals/answer_shape/spl_gate_histogram_v1.md` primary counts sum to bank/trace size; explicit target line; or **SKIPPED_BY_EVIDENCE** if SPL is not material to objective/shape failures.
  - **Depends on:** 0.4 (parallel with Phases 1–3 / 5 / 6 once 0.4 done; must complete or skip-by-evidence before 7.1)
  - **Evidence:** DONE 2026-08-27. Wrote `docs/evals/answer_shape/spl_gate_histogram_v1.md`. PRIMARY checksum: ENVIRONMENT_UNRESOLVED×2 + OBJECTIVE_PERSISTENCE×1 = **3/3** traces (= bank TRACE rows). `G-TMPL_COUNT=0`, `G-TMPL_MATERIAL=false`. Explicit target: `TARGET: none (no template enablement); 4.2 = SKIPPED_BY_EVIDENCE`. CV.SPL.01 has no PRIMARY (honest-posture MEASURE_ON_LIVE only). MULTI gaps are objective/eligibility/mock — not G-TMPL.

- [x] **4.2** — Targeted template / binding work only if G-TMPL is material
  - **Do:** Enable only individually justified `enabled:false` active templates (one commit each); bind null use cases only if measurement shows correctness. If 4.1 shows G-TMPL is not material, mark this item **SKIPPED_BY_EVIDENCE** with reason (e.g. `G-TMPL = 0 material failures after 4.1`) — do **not** implement unnecessary template flips and do **not** falsely mark DONE.
  - **Verify:** Per-template pytest + governance sheets `--check`; harness: no wrong-template regressions; no weakened abstention. **Or** Evidence records `SKIPPED_BY_EVIDENCE: <reason>` citing 4.1 histogram.
  - **Depends on:** 4.1
  - **Evidence:** SKIPPED_BY_EVIDENCE: `G-TMPL = 0 material failures after 4.1` (cite `docs/evals/answer_shape/spl_gate_histogram_v1.md` — `G-TMPL_COUNT=0`, `G-TMPL_MATERIAL=false`, target line none). No `enabled:false` template flips; no use-case binding changes; `spl_validator.py` untouched.

- [x] **4.3** — Honest no-SPL reason
  - **Do:** Ensure clarification reasons reach the analyst-visible surface (map in UI only if needed; verify HEAD before assuming ChatPanel packet is open).
  - **Verify:** `CV.SPL.02`-class row: non-null reason, no empty code block.
  - **Depends on:** 4.2
  - **Evidence:** DONE 2026-08-27. ChatPanel left untouched (RACES freeze; HEAD already maps fields). `AnalystResponseCard` + `ChatBubble` omit empty/whitespace SPL `<pre>`/`<code>` while still showing `spl_status_detail` / reject reasons. Added bank row `CV.SPL.02` + fixture `cv_spl_02_no_spl_reason.json`; harness scores STRUCTURAL PASS. Frontend targeted → **5 passed**. Intentional baseline freeze for new row (total 9→10, SPL.02 PASS); `--check` PASS. No `spl_validator.py` change.

- [x] **4.4** — No validator weakening
  - **Do:** Confirm `spl_validator.py` untouched by this phase; efficiency work stays OPTIONAL_PHASE_S.
  - **Verify:** `git diff --stat` excludes `safeguards/spl_validator.py` for Phase 4 commits.
  - **Depends on:** 4.3
  - **Evidence:** DONE 2026-08-27. `git diff ec4c8451..32307a92 --name-only | grep spl_validator` → **NONE**. Phase 4 commits `dc3d4eb4`/`5695114f`/`32307a92` only touched histogram/docs/UI/harness. OPTIONAL_PHASE_S untouched.

### Phase 5 — Isolated mock MCP

- [x] **5.1** — Isolated mock profile (existing flags only)
  - **Do:** Add non-default profile example per Mock MCP section; default COE unchanged; document posture exception. Confirm no production deployment manifest/default profile selects the mock profile.
  - **Verify:** Profile file exists; default profile still has global execution false; no secrets; grep/attest that default compose/COE profile does not reference mock profile.
  - **Depends on:** 0.4 (parallel stream; Phase 3 preferred before claiming email+mock interactions, but 5.1 itself only needs baseline)
  - **Evidence:** DONE 2026-08-27. Added `env/profiles/coe-mock.env.example` (existing keys only: MCP_MODE=mock, global+mock execution true, SPLUNK_MCP_ENABLED=false, empty URL/token). Manifest entry `test_only: true`; `env/README.md` posture note; `EnvProfile.test_only` surfaced. Default `coe` still `MCP_GLOBAL_EXECUTION_ENABLED=false`; compose default `${AI_SOC_ENV_PROFILE:-coe}` does not reference coe-mock. `pytest app/tests/test_coe_mock_profile.py app/tests/test_env_profiles.py app/tests/test_mac_staging_profile.py -q` → **8 passed**.

- [x] **5.2** — Deterministic named capability selection
  - **Do:** Activate existing capability selection behind Resource Planner hub — do not build a second selector.
  - **Verify:** Under mock profile, `CV.MULTI.01C` / INV row reports named tool; NOMCP row does not execute.
  - **Depends on:** 5.1
  - **Evidence:** DONE 2026-08-27. Test-only pins in `test_post_p10_mock_mcp_5_2.py`: under coe-mock env keys, `select_mcp_tool(..., mcp_capability=EVENT_SEARCH)` → `splunk_run_query` selected (no second selector); `CV.NOMCP.01` with MCP_MODE=mock but global execution false → connector never called / `mcp_global_execution_disabled`; mock profile remains test-only non-default. `pytest app/tests/test_post_p10_mock_mcp_5_2.py -q` → **2 passed**.

- [x] **5.3** — Validated normalized SPL before mock call
  - **Do:** Prove gate still requires approved non-null `normalized_spl`.
  - **Verify:** Existing MCP gate tests + harness.
  - **Depends on:** 5.2
  - **Evidence:** SKIPPED_BY_EVIDENCE 2026-08-27: no product gap — existing gate already requires approved non-null `normalized_spl` before mock call. Re-ran `pytest app/tests/test_mcp_execution_gate.py app/tests/test_mcp_execution_contract_e2e.py app/tests/test_splunk_call_authorization.py app/tests/test_hil_mock_execution_hardening.py -q` → **55 passed** (includes `test_mock_execution_uses_only_normalized_spl` + `test_validation_failure_creates_human_review`). Zero code change.

- [x] **5.4** — Exact-call authorization (envelope-bound)
  - **Do:** Keep AUTH0 / canonical arguments hash path; no bypass for mock. Every material mock MCP call must have a **NEW** exact-call authorization bound to at least: `approved envelope_version`, exact tool/server, normalized arguments, `normalized_spl` where applicable, RBAC/policy context. Changing `envelope_version` invalidates the prior grant. Mock follows the same authorization architecture as eventual live MCP.
  - **Verify:** Exact-call authorization tests green under mock profile; negative test that pre-approval / stale envelope_version grants fail closed.
  - **Depends on:** 5.3
  - **Evidence:** DONE 2026-08-27. Packet: `docs/evals/answer_shape/mcp_execution_gate_5_4_envelope_auth_packet.md`. AUTH0 `envelope_version` in fingerprint; gate threads `approved_investigation_envelope`. Stale v1→v2 confirm → `exact_call_grant_invalidated`, no connector call. RACES pin advanced for `mcp_execution_gate.py` SHA-256 `b12b0a05…`. Tests: `test_post_p10_mock_mcp_5_4_envelope_auth.py` + AUTH0 suite → **10+10 passed**; RACES → **8 passed**.

- [x] **5.5** — Named mock invocation only after ApprovedInvestigationEnvelope
  - **Do:** Before investigation Approve (UI) → wire `run` → immutable ApprovedInvestigationEnvelope: **mock MCP invocation = NO**. After envelope_version=N: named mock invocation allowed only under 5.4 grant. Trace shows server/tool/mode=mock/execution=simulated + envelope_version.
  - **Verify:** `CV.MULTI.01C` pins; negative test pre-approval invocation absent.
  - **Depends on:** 5.4
  - **Evidence:** DONE 2026-08-27. Packet: `docs/evals/answer_shape/mcp_execution_gate_5_5_envelope_required_packet.md`. Gate `require_approved_investigation_envelope` + pipeline investigation path wiring. Pre-envelope → `investigation_envelope_required` (connector never called). RACES pins advanced for gate+pipeline. Tests → **5 passed** (5.4+5.5); hil/gate smoke → **27 passed**.

- [x] **5.6** — Simulated-result labelling
  - **Do:** UI/trace never present mock rows as live Splunk evidence.
  - **Verify:** Frontend/backend tests for simulated labelling; browser spot-check optional.
  - **Depends on:** 5.5
  - **Evidence:** DONE 2026-08-27. `_execution_label` treats mock_connector/evidence_source=mock/mode=mock as simulated; SourceEvidence provenance `ai_soc_simulated_mock_mcp`; frontend planningOutcome label SIMULATED. Tests `test_post_p10_mock_mcp_5_6_5_7.py` → **3 passed**; lifecycle still green.

- [x] **5.7** — No mock-derived remediation/write authority
  - **Do:** Mock evidence cannot move remediation to ELIGIBLE for real write authority or satisfy compromise for production containment.
  - **Verify:** Negative tests; `CV.MULTI.01C` remediation write authority = NO.
  - **Depends on:** 5.6
  - **Evidence:** DONE 2026-08-27. `test_mock_evidence_cannot_satisfy_compromise_or_authorize_email_send` pins simulated provenance leaves email_draft PENDING_CONDITION and `email_send_eligible=false`; no `live_mcp_proven`. Combined with 5.6 suite → **3 passed**; conditional lifecycle green.

### Phase 6 — Answer / UI convergence

Starts after Phase **3** closes (objective persistence + state contract + B4 + email draft). Does **not** wait for Phase 4 or Phase 5 completion, except mock-specific labelling that names a Phase 5 dependency.

- [ ] **6.1** — Orientation
  - **Do:** Ensure state A/B show orientation consistent with governed plan — no EC fixture copy. State B may show progress telemetry but must not treat it as EvidenceState.
  - **Verify:** Bank + component tests; progress-vs-evidence distinction pinned where UI shows both.
  - **Depends on:** 3.7
  - **Evidence:** _(fill)_

- [ ] **6.2** — Plan presentation
  - **Do:** Canonical plan surface only (2.2 decision).
  - **Verify:** No dual cards; state A order test.
  - **Depends on:** 6.1
  - **Evidence:** _(fill)_

- [ ] **6.3** — Evidence / findings
  - **Do:** Findings from accepted EvidenceState only; no fabricated MCP/RAG; progress events never become SourceEvidence.
  - **Verify:** Trace/evidence truth tests still green; harness.
  - **Depends on:** 6.2
  - **Evidence:** _(fill)_

- [ ] **6.4** — Conclusion
  - **Do:** Inconclusive vs suspicious conclusions match outcome.
  - **Verify:** MULTI.01A/B.
  - **Depends on:** 6.3
  - **Evidence:** _(fill)_

- [ ] **6.5** — Recommended next action
  - **Do:** Surface recommended next action without implying execution; PENDING_CONDITION intents may appear without CTA.
  - **Verify:** Harness + UI test.
  - **Depends on:** 6.4
  - **Evidence:** _(fill)_

- [ ] **6.6** — Eligible remediation plan (separate write HIL)
  - **Do:** Under REMEDIATION PLAN ELIGIBILITY, remediation plan may PRESENT with Approve/Edit/Cancel; write only after Approve. Do not require user `compromise_confirmed` merely to show the plan. Do not conflate with USER-CONDITIONAL ACTION ELIGIBILITY for email.
  - **Verify:** MULTI.01A absent / 01B may present; write not automatic.
  - **Depends on:** 6.5
  - **Evidence:** _(fill)_

- [ ] **6.7** — Conditional communication
  - **Do:** Draft eligibility and role display per Phase 3.
  - **Verify:** MULTI.01A/B email axes.
  - **Depends on:** 6.6
  - **Evidence:** _(fill)_

- [ ] **6.8** — Technical provenance secondary
  - **Do:** Diagnostics/trace collapsed by default; oracle fields primary. Items that render MCP/mock execution state (if any in this item or adjacent UI) may additionally **Depends on** 5.5–5.6; unrelated provenance collapse does **not** wait on Phase 5.
  - **Verify:** Frontend default-collapsed tests / browser note.
  - **Depends on:** 6.7
  - **Evidence:** _(fill)_

- [ ] **6.9** — Compare production answer arc with EC target shape
  - **Do:** Score against shape bank (not EC prose). Record pass_rate movement vs pre-change scorecard if still valid on baseline. Optionally incorporate Phase 4/5 harness deltas when those streams have closed.
  - **Verify:** Convergence harness + shape scorecard report.
  - **Depends on:** 6.8
  - **Evidence:** _(fill)_

### Phase 7 — Final regression / acceptance

- [ ] **7.1** — Full acceptance matrix
  - **Do:** Run and record: backend full; frontend test + build; Stage 3 governance; RACES; P8 frozen bank; 105 goldens; clean-answer/parity as applicable; planner; T4; SPL; S4; J6; J7; curated RAG; production `/chat` isolation; EC isolation; convergence bank `--check`; browser QA against **attested** runtime ports from `.env`.
  - **Verify:** All gates green or explicitly operator-adjudicated by named residual; zero unexplained new failure node-IDs vs 0.4; closing report A–P criteria below. Phase 4 is complete **or** SKIPPED_BY_EVIDENCE; Phase 5 complete; Phase 6 complete.
  - **Depends on:** 4.4 (or 4.1 SKIPPED_BY_EVIDENCE closing Phase 4), 5.7, 6.9
  - **Evidence:** _(fill)_

---

## Protected / governance-sensitive paths

Treat carefully; exact diff + operator approval + RACES baseline advance when mutating freeze paths:

| Path | Why | Likely phase |
|---|---|---|
| `backend/app/chat/contracts/resolved_query.py`, `resolved_query_builder.py` | **Primary RQC gap** — requested conditional actions | 1.1–1.5 |
| `backend/app/chat/pipeline.py` | Live path authority | 1.4+, 3.x if required |
| `backend/app/schemas/responses.py` | Wire contract — **only after RQC owns fields** | 1.4 only if proven necessary |
| `backend/app/api/routes_chat.py` / `routes_chat_stream.py` / `routes_actions.py` | API authority | 3.x / 6.x if required |
| `backend/app/graph/` / `planner/` / `routing/` | Planning authority — ResourcePlan stays read-only investigation | 1.x — extend only, no second planner |
| `backend/app/orchestration/mcp_execution_gate.py` | MCP execution — envelope-bound grants | 5.x |
| `backend/app/safeguards/spl_validator.py` | Safety — **do not weaken** | avoid |
| `frontend/src/components/ChatPanel.tsx` | RACES / EC isolation | 4.3 / 6.x only if HEAD still needs it |
| `backend/app/chat/remediation_runtime.py` | **Governance-sensitive J7** | 3.1–3.3 |
| `backend/app/chat/query_signals.py` / `intent_classifier.py` | Accepted P8 seams | touch only with proof |

`architecture.md` remains READ ONLY.

---

## Closing criteria (A–P)

| # | Criterion |
|---|---|
| A | Multi-goal user objective survives end-to-end |
| B | Investigation / SOP / remediation / email goals can coexist |
| C | Conditional requested actions remembered when currently ineligible (PENDING_CONDITION) |
| D | J7 evidence authority intact |
| E | No remediation plan PRESENT / write for incomplete/inconclusive evidence; completed+suspicious may PRESENT plan without requiring user `compromise_confirmed` |
| F | Email draft distinct from email send |
| G | Recipient roles preserved without invented addresses |
| H | MCP selection remains deterministic |
| I | LLM never directly calls MCP |
| J | Mock MCP proves orchestration only and is clearly simulated |
| K | Mock evidence cannot grant real remediation/write authority |
| L | SPL produced when governed and honestly withheld when not |
| M | Production `/chat` answer arc materially converges toward EC target **shape** |
| N | Production does not import or execute EC fixtures |
| O | No second planner / router / MCP framework / state machine |
| P | Zero new unexplained regressions |

---

## Commit conditions

1. Exactly one checklist item per commit (templates: one commit per template if 4.2 runs).
2. Verify ran verbatim; Evidence filled before commit.
3. Zero new pytest failure node-IDs vs 0.4 baseline (diff names from `-rf`).
4. Convergence harness `--check` passes or diffs are the intended named change.
5. `/invariant-check` PASS on 7 groups for pipeline/planner/SPL/MCP/LLM touches.
6. Phase boundaries: governance regression + RACES 8.
7. Protected/governance-sensitive edits carry recorded approval (and RACES baseline advance when freeze paths change) in the same commit.
8. No secrets in repo artifacts.
9. No push / merge / deploy from this plan’s loop.

---

## Stop conditions

- Every checklist item is **DONE** or legitimately **SKIPPED_BY_EVIDENCE** (with Evidence), **or**
- Same Verify fails twice on one item, **or**
- Protected/governance-sensitive diff needed without CURRENT/PROPOSED/J7-preservation packet, **or**
- New env flag **name** would be required, **or**
- Premises disproved (e.g. baseline SHA mismatch in 0.1), **or**
- Any change would give mock evidence write/remediation authority, **or**
- Any change would weaken J7, **or**
- LLM would perform a conditional-action lifecycle transition, **or**
- Scope pressure to implement DEFERRED_* / OPTIONAL_PHASE_S items on the critical path, **or**
- Unexplained regression in the acceptance matrix.

### Checklist terminal states

| State | Meaning |
|---|---|
| **DONE** | Item executed and Verify passed; Evidence recorded |
| **SKIPPED_BY_EVIDENCE** | Item’s explicit precondition was disproved by an earlier measured gate; evidence and reason recorded |
| **DEFERRED_BY_PLAN** | Only for items already declared `DEFERRED_*` / `OPTIONAL_PHASE_S` |
| **BLOCKED** | Not completion |

A phase is complete only when every item is **DONE** or legitimately **SKIPPED_BY_EVIDENCE** per its written precondition. Example: `4.2 = SKIPPED_BY_EVIDENCE` / `Reason: G-TMPL = 0 material failures after 4.1`.

---

## Verification gaps (flag before coding)

- Exact Final RQC / wire field names for requested conditional actions (preflight in 1.1–1.4) — **RQC first**, then `schemas/responses.py` only if needed.
- Whether ChatPanel historical packet is still open on `6b63df61` (verify before any ChatPanel work).
- Whether email needs `DEFERRED_ACTION_CAPABILITY_GENERALIZATION` after 1.3–1.4 (prove dependency first).
- Ports/runtime URLs always from target `.env` — never historical hard-codes.

## Drift log

_Record every premise change, redundant item, or scope shift here. The operator must acknowledge before the loop continues._

- 2026-08-26 rev 1 — Initial plan as P8 defect closure.
- 2026-08-26 rev 2 — Review fixes (C10–C14, B1 recommendation, template count, etc.).
- 2026-08-26 rev 3 — **Post-P10 reposition.** B4 final; B1/B2/B3 retired; conditional-action lifecycle REQUESTED→…→EXECUTED; email objective persistence; state A–E; MULTI.01A/B/C; defer durable discovery / create_ticket / efficiency lints / pipeline dead-branch; isolated mock profile; start from `6b63df61` / product `c109402d`; historical handoff meta not current truth; stale master-plan status tables disregarded for P8–P10 closure.
- 2026-08-26 rev 4 — **Final consistency pass.** Trace diagnosis PRIMARY+CONTRIBUTING; governed predicate_id (not free-text); no field overloading in 1.4; State B progress≠EvidenceState; Phase 6 decoupled from 4/5 (7.1 still waits for all); single RP/registry authority invariant; mock default-profile non-reference check.
- 2026-08-26 rev 5 — **Freeze corrections.** Loop runner: 6.8≠mock UI; Phase 6 mock deps = 5.5–5.6 only where MCP/mock is rendered; full conditional-action transition authority table (LLM never transitions); checklist terminal states DONE / SKIPPED_BY_EVIDENCE / DEFERRED_BY_PLAN / BLOCKED (Phase 4.2 skip formalized).
- 2026-08-26 rev 6 — **Architecture precision.** Investigation UI Approve/Edit/Cancel → wire run/edit/cancel (do not revert to “Run investigation”); ResourcePlan read-only investigation only; Final RQC owns requested conditional actions (`resolved_query.py` / `resolved_query_builder.py` first — not responses.py first); REMEDIATION PLAN ELIGIBILITY vs USER-CONDITIONAL ACTION ELIGIBILITY (`suspicious` ≠ `compromise_confirmed`); envelope-bound mock MCP; phases 4/5/6 parallelizable not necessarily concurrent.
- 2026-08-26 rev 7 — **0.2 operator decision (initial).** Keep 0.2 BLOCKED awaiting two authoritative production `trace_id`s or redacted bundles…
- 2026-08-26 rev 8 — **0.2 continue-loop operator decision.** After exhausting safe non-credentialled discovery (FOUND_NONE): record each unavailable production failure as ENVIRONMENT_UNRESOLVED with exact reason; capture SSH/admin design-case in-process as additional diagnostic only; close 0.2 as DONE_WITH_ENVIRONMENT_UNRESOLVED_INPUTS; 0.3 may proceed without inventing root causes for unavailable traces.
- 2026-08-26 rev 9 — **Cursor workspace sync.** Canonical checklist progress (12/42 through 2.3, HEAD `ede02f94` on `ws/post-p10-answer-tool-convergence`) mirrored into the Cursor checkout plan + LOOP_RUNNER execution-status block so the open IDE files match the worktree.
- 2026-08-26 rev 10 — **2.4 complete** (`2496e3dc`). Findings/conclusion/limitations contract pinned for MULTI.01A/B; next item 2.5. Cursor plan/LOOP_RUNNER re-synced.
- 2026-08-26 rev 11 — **2.5 complete.** Pending Final-RQC conditional actions now reach the production UI through the safe resolved-query projection without remediation/send CTA inflation. Live LLM remains environment-unresolved (configured endpoints red/`URLError`); no provider/model changes.
- 2026-08-27 rev 12 — **Ship audit / Cursor resync.** Verified worktree HEAD `3ed1ec36` has checklist **20/42** through **3.6** (2.5–3.6 product commits present with Evidence). Next: **3.7**. Phases 4–7 still open. Mirrored plan + LOOP_RUNNER into Cursor IDE checkout.
- 2026-08-27 rev 13 — **3.7 complete.** Fail-closed `email_send_eligible` + negative HIL proofs; EMAIL DRAFT ≠ EMAIL SEND; remediation Approve does not unlock Phase-10 draft send; harness ABSENT pin active without baseline rewrite. Next: Phase 4.1 (parallelizable with 5.x / 6.x).
- 2026-08-27 rev 14 — **4.1 complete.** SPL gate histogram: G-TMPL=0 material; primary sum 3/3. Next: 4.2 SKIPPED_BY_EVIDENCE then 4.3/4.4; Phase 5/6 remain eligible in parallel.
- 2026-08-27 rev 15 — **4.2 SKIPPED_BY_EVIDENCE** (`G-TMPL = 0 material failures after 4.1`). No template flips.
- 2026-08-27 rev 16 — **4.3 complete.** CV.SPL.02 honesty surface + intentional harness baseline advance (new STRUCTURAL row). ChatPanel untouched.
- 2026-08-27 rev 17 — **Phase 4 closed** (4.4: `spl_validator.py` untouched across Phase 4 commits). Next: Phase 5.1.
