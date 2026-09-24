---
name: ec-cio-coherence-and-lifecycle
overview: "Make EC /scenarios questions 1–9 (+ a new RAG question) CIO-grade: justified plan steps, logical remediation, clean emails and SPL, one coherent incident story and tool fabric, stable scrolling — then put every question on Plan → Approve → Outcome → Remediation → Approve."
status: draft (rev 2 — after plan-reviewer REVISE + content review)
date: 2026-09-24
canonical_plan: plans/2026-09-24_1635_ec-cio-coherence-and-lifecycle.md
loop_runner: plans/LOOP_RUNNER_ec-cio-coherence-and-lifecycle.md (to be created at first loop-asap, from plans/LOOP_RUNNER_TEMPLATE.md)
---

# EC CIO coherence + uniform agent lifecycle

## Objective

This plan ships in **two independently shippable releases**, so neither is a 10-day block.

- **Release A (~6 d):**
  - Stable scrolling.
  - Justified and logical content for the four agent scenarios (S1, S2, S4, S7).
  - One email composer and one tool catalog.
  - A new **RAG question (R1)** with a 2-step remediation (incident + email).
  - Q1/Q2 inference, SPL and flow fixes.
  - The S1 → Q1 → S3 facts reconciled.
- **Release B (~5 d, separate approval):**
  - Move S5, S3, S6 and Q1 onto the `ec_agent_workflow` lifecycle, so every question is Plan → Approve → Outcome → Remediation → Approve.

**Evidence base:**
- [`docs/evals/ec_cio_coherence/content_review_2026-09-24.md`](../docs/evals/ec_cio_coherence/content_review_2026-09-24.md): per-step KEEP/FIX/ADD/REMOVE with reasons.
- Plan-reviewer report (2026-09-24, verdict REVISE, folded in below).

**Scope and freezes:**
- **Scope:** EC only. That is `backend/app/demo/**`, `frontend/src/components/ec/**`, `frontend/src/lib/ecAgentWorkflow.ts`, and new EC-only files.
- **Frozen:** `architecture.md` and production `/chat`: `backend/app/{chat,planner,routing,spl,connectors}`, `frontend/src/components/ChatBubble.tsx`, `ChatPanel.tsx`.
- **Dummy MCPs stay dummy:** no live LLM or live MCP from EC.

## Corrections from the review (rev 1 → rev 2)

- **S7 is not contradictory, and S4's Agilus HIL is reached.** Rev-1's claims came from a harness that selected *all* steps. Both findings are dropped. Harness 0.2 uses `default_selected`.
- **Q1/Q2 cannot become agents by registering a profile.** `fixtures/registry.py` returns `None` without a `PACKS` entry, and the flow falls back to `run_demo_scenario` (`ec_turn.py:26-33,176-218`). A pack per scenario is needed. Q1 is in Release B, and Q2 gets a light non-agent fix.
- **Do not change the `executive_summary` shape.** Today it is `string[]` (`types.ts:229`, pinned by `s1Workspace.test.tsx:256`). Add an **additive** `executive_brief` object instead.
- **`ExperienceExecutionProgressPanel` is shared with production `ChatBubble.tsx:139`.** The scroll fix is limited to an `<ol>` overflow inside the component, and ChatBubble tests are added to the gate.
- **The investigation-HIL follow-up ID and label are hardcoded to Agilus/S4** (`EcInvestigationWorkspace.tsx:472-495`). Item A2.5 makes them payload-driven before any other scenario uses HIL.
- **Gates:**
  - The `-k` selector missed `test_s3_*`, `test_s5_*`, `test_s6_*`, `test_s7_*` and `test_live_path_untouched_by_ec`. The gate now lists files explicitly.
  - "Same failure names" cannot catch weakened assertions, so an **assertion-change ledger** is added.
- **The `ec_followups == []` assertion is wrong at COMPLETE.** `generate_executive_summary` is emitted there. The harness asserts it only at `PLAN_READY` and `INVESTIGATION_COMPLETE`.
- **The `(simulated)` grep is replaced by a demo-word lint** scoped to analyst-visible text and email bodies. Provenance stays visible through the tool strip's `demo_fixture` badge.

## Decisions (defaults assumed — correct before the item that needs them)

- **D1 Storyline (A5):** S1 → Q1 → S3 is **one incident thread**.
  - Day 0: S1, new IP, monitoring raised, owner asked about the 3 sessions.
  - Day 1: Q1, the watch fires, auth success is attributed, escalation to P1.
  - Day 1+: S3, block via the firewall process.
  - One incident ID for the whole thread: `INC-2026-89412`.
- **D2 RAG question (A4):** promote `cert_in_ot_reporting_obligation` to **R1** in the Flagship group (10th entry). Its answer must come from a **captured** governed SOC-KB retrieval replayed as a fixture. If the KB lacks the CERT-In document, stop and ask for the source text (it will not be authored freehand).
- **D3 Q2:** light fix only (SPL correctness + terminal "request deployment" offer). No agent pack.
- **D4 Agilus:** "vulnerability & patch orchestration MCP", used in S4 (existing) and S5 (Release B). It is listed in the tool fabric everywhere else.
- **D5 Q1 flagship status:** keep Q1 in the Lab group. Release B adds a pack *without* adding it to `FLAGSHIP_SCENARIO_IDS` (`test_e4_flagship_lab_picker.py:26-30` stays unchanged).

## Stop conditions

- All items checked with evidence, **or**
- the same gate fails twice on one item, **or**
- a decision is needed (D1–D5 or a new one): **stop and ask**, **or**
- R1 KB source missing (D2).

## Gates

**Gate EC (every item that touches EC):**
```
cd backend && python3 -m pytest -q app/tests/test_ec_*.py app/tests/test_experience_center_*.py \
  app/tests/test_s1_*.py app/tests/test_s2_*.py app/tests/test_s3_*.py app/tests/test_s4_*.py \
  app/tests/test_s5_*.py app/tests/test_s6_*.py app/tests/test_s7_*.py \
  app/tests/test_e4_flagship_lab_picker.py app/tests/test_live_path_untouched_by_ec.py \
  app/tests/test_live_chat_ec_parity.py app/tests/test_ec_cio_lifecycle_walk.py
cd frontend && npm test && npm run build
```

**Gate Frozen:**
- `git diff --stat <START_SHA> -- architecture.md backend/app/chat backend/app/planner backend/app/routing backend/app/spl backend/app/connectors frontend/src/components/ChatBubble.tsx frontend/src/components/ChatPanel.tsx`
- It must be **empty**, except A1.2's `ExperienceExecutionProgressPanel.tsx` change, which is allowed with the ChatBubble tests green.

**Gate Release (end of A and of B):**
- Full backend `python3 -m pytest -q -rf`. Failure **names** must equal baseline 0.1.
- `./scripts/run_stage3_governance_regression.sh` PASS.
- `/invariant-check` on the release diff.

**Assertion-change ledger:** every modified pre-existing test assertion is recorded in `docs/evals/ec_cio_coherence/assertion_ledger.md` with old → new and the reason, in the same commit. A changed assertion with no ledger row fails review.

## Dependency order

Release A: `A0.1 → A0.2 → A0.3 → A1.1 → A1.2 → A2.1 → A2.2 → A2.3 → A2.4 → A2.5 → A3.1 → A3.2 → A3.3 → A3.4 → A4.1 → A4.2 → A5.1 → A5.2 → A6.1 → A6.2`
Release B (after A6.2 + user approval): `B1 → B2 → B3 → B4 → B5`

---

## Release A (~6 working days)

### A0 — Baseline and harness (0.5 d)

- [ ] **A0.1** — Baseline
  - **Do:** On clean `master`, record START_SHA and the failure names of the full backend run, plus frontend results, into `docs/evals/ec_cio_coherence/baseline.txt`.
  - **Verify:** `cd backend && python3 -m pytest -q -rf > /tmp/ec_base.txt; tail -3 /tmp/ec_base.txt`; `cd frontend && npm test | tail -5`. The file lists SHA and failure names.
  - **Depends on:** none
  - **Evidence:** _(fill when done)_

- [ ] **A0.2** — Walk and content harness
  - **Do:** Add `backend/app/tests/test_ec_cio_lifecycle_walk.py`.
    - Parametrize over catalog entries 1–9 (+R1 once it exists).
    - Walk each with **default_selected** steps (agent) or ordered chips (legacy).
    - **Lifecycle:** agent scenarios reach `COMPLETE`, `ec_followups==[]` at `PLAN_READY` and `INVESTIGATION_COMPLETE`, and there are no `ec_actions` before approval.
    - **Content:**
      - every investigation step has non-empty `rationale` and `decides`;
      - every remediation step has `rationale`, `reversible` and `approver`;
      - `executive_brief` is present at `INVESTIGATION_COMPLETE` and `COMPLETE`;
      - no demo-word hits (`fixture|simulated|Experience Center|Scenario: S\d|ZD-FIXTURE|\(if checked\)|onboarded|non-executable`) in analyst-visible fields or email bodies;
      - email ticket-status matches lifecycle tickets.
    - **Story:** S1/Q1/S3 share the incident ID and facts.
    - Anything not yet true is `xfail(strict=True)`, one reason per row.
  - **Verify:** `cd backend && python3 -m pytest -q app/tests/test_ec_cio_lifecycle_walk.py -rxX` shows the measured xfail list and 0 unexpected failures. Paste the list into Evidence.
  - **Depends on:** A0.1
  - **Evidence:** _(fill when done)_

- [ ] **A0.3** — Visual baseline (needs the user signed in once in the browser pane)
  - **Do:** Walk questions 1–9 at 1440×900 and 768 px, capturing each phase to `docs/evals/ec_cio_coherence/before/<scenario>/`. Log scroll jumps, clipping and dead chips in `ux_findings.md`.
  - **Verify:** 9 folders with ≥3 screenshots; `ux_findings.md` rows cite scenario + phase.
  - **Depends on:** A0.1
  - **Evidence:** _(fill when done)_

### A1 — Stop the page jumping (0.5 d, ships alone)

- [ ] **A1.1** — Remove the competing scrolls
  - **Do:**
    - Delete the lifecycle scroll effect `EcAgentWorkflow.tsx:241-255`, because the workspace already targets via `agentLifecycleScrollTarget`.
    - Non-agent: call `scrollToAnswerStart` on reveal **start** only (`EcInvestigationWorkspace.tsx:531-532`).
    - Add a 1.5 s user-scroll suppression (wheel/touch/key) in the workspace so auto-scroll never overrides a reader.
  - **Verify:**
    - New `frontend/src/components/ec/ecScrollBehaviour.test.tsx`: exactly one scroll per lifecycle transition PLAN_READY → … → COMPLETE, and 0 after a simulated wheel event.
    - `grep -c "scrollIntoScrollParent(" frontend/src/components/ec/EcAgentWorkflow.tsx` returns 0.
  - **Depends on:** A0.3
  - **Evidence:** _(fill when done)_

- [ ] **A1.2** — Keep progress scrolling inside the panel
  - **Do:** Give the `<ol>` in `ExperienceExecutionProgressPanel.tsx:171` `max-h-80 overflow-y-auto`. `scrollIntoScrollParent` then stops at the list and never moves the outer page. No other change to this shared file.
  - **Verify:**
    - A vitest shows the outer container's `scrollTo` is not called across 5 progress ticks.
    - `npx vitest run src/components/ChatBubble.progress.test.tsx` is green (production consumer).
    - Manual check: S4 run, no outer movement.
  - **Depends on:** A1.1
  - **Evidence:** _(fill when done)_

### A2 — Shared content infrastructure (1.5 d)

- [ ] **A2.1** — Step justification fields
  - **Do:**
    - Extend the plan-step model in `app/demo/ec_agent/types.py` (additive, optional) with:
      - investigation steps: `rationale`, `decides`, `if_skipped`;
      - remediation steps: `rationale`, `reversible`, `approver`, `risk_if_skipped`.
    - Mirror them in `frontend/src/components/ec/types.ts`.
    - Render one "Why:" line per step, plus an expandable detail, in `EcAgentWorkflow.tsx`.
  - **Verify:** `pytest app/tests/test_ec_agent_framework.py -q` (new contract test); vitest renders "Why:" for a step with a rationale and nothing for one without.
  - **Depends on:** A1.2
  - **Evidence:** _(fill when done)_

- [ ] **A2.2** — Additive `executive_brief`
  - **Do:** Add `executive_brief = {verdict, business_impact, risk_from, risk_to, confidence, would_change_if, decision_needed, will_not_do}`. Render it above the existing list. Leave `executive_summary: string[]` untouched.
  - **Verify:** `s1Workspace.test.tsx` still passes unchanged; a new vitest renders the brief; the harness brief-presence xfail stays until A3.
  - **Depends on:** A2.1
  - **Evidence:** _(fill when done)_

- [ ] **A2.3** — One email composer
  - **Do:** Add `app/demo/ec_email_composer.py`, used by all EC drafts:
    - BLUF block (ask, deadline, severity);
    - subject `[P#][INC-id] <action> — <asset>`;
    - ticket block **derived from lifecycle state** (no free text);
    - role-specific footer (the firewall-SOAR line only for firewall/network recipients);
    - evidence list with IDs;
    - CC rules (SOC lead on block/approval);
    - no demo words.
    - Migrate `ec_email_drafts.py` callers.
  - **Verify:**
    - New `test_ec_email_composer.py`: lint every draft reachable from the harness walk (no demo words; ticket block matches created tickets; S1 notify goes to SOC with FW CC).
    - `test_ec_email_drafts.py` / `test_ec_email_transport.py` green. Any changed assertion goes in the ledger.
  - **Depends on:** A2.1
  - **Evidence:** _(fill when done)_

- [ ] **A2.4** — Tool catalog (MCP fabric)
  - **Do:**
    - Add `app/demo/ec_agent/tool_catalog.py` with id, display name, role and `demo_fixture=True` for: Splunk MCP, Agilus MCP (vuln & patch orchestration), Cisco device MCP, CMDB, OT inventory, Network/switch, ITSM, IAM, EDR, Email, SOC-KB (RAG), Playbook registry, SPL validator, SOAR/firewall.
    - Replace free-text `tools[]` in the S1/S2/S4/S7 fixtures with ids.
    - Render a "Connected tools" strip from the payload: used tools lit, others dimmed, one demo badge.
  - **Verify:** The harness tool-id assertion passes for S1/S2/S4/S7; vitest renders the strip from a payload; no per-scenario frontend branch (`grep -n "s[1-7]_" frontend/src/components/ec/EcAgentWorkflow.tsx` shows no new hits).
  - **Depends on:** A2.1
  - **Evidence:** _(fill when done)_

- [ ] **A2.5** — Payload-driven investigation HIL
  - **Do:** `EcInvestigationWorkspace.tsx:472-495` reads `approve_follow_up_id`, `skip_follow_up_id` and labels from `hil_prompt` (already in the payload), falling back to the current S4 ids.
  - **Verify:** `flagshipWorkspace.test.tsx` S4 HIL is unchanged; a new vitest with a non-Agilus HIL payload posts its own follow-up id.
  - **Depends on:** A2.4
  - **Evidence:** _(fill when done)_

### A3 — Content fixes on the agent scenarios (1 d)

Per the content review. Each item fills rationale/brief fields, applies KEEP/FIX/ADD/MERGE, rewrites the opening in agent voice, and removes brief/internal leaks.

- [ ] **A3.1** — S1
  - **Do:**
    - Identity wording → "registered third-party integration endpoint (owner …)".
    - Merge 5 monitoring steps into 2: a saved-search definition (`-15m@m`, cron `*/15`, throttle, 14-day expiry) plus a 14-day backtest.
    - **ADD** "Ask integration owner to confirm the 3 sessions".
    - Notify goes to SOC with FW CC.
    - State the auth-SPL attribution rationale.
  - **Verify:** Harness S1 content rows pass; `test_s1_agent_workflow.py` is updated (the `:132` identity pin goes in the ledger); SPL is still from `_scoped_template_spl` or validator-clean (`validate_spl` approved).
  - **Depends on:** A2.5
  - **Evidence:** _(fill when done)_

- [ ] **A3.2** — S2
  - **Do:**
    - Fix the SPL sourcetype `pgcil:edr` → the AI-gateway Env-KB slot, and show SPL per Splunk step.
    - Add actor/session attribution to the conclusion.
    - Reframe the credential step as "rotate + scope-down (precautionary, reversible)" with a rationale.
    - **ADD** "block/rate-limit offending session at AI gateway" and "extend prompt-injection detection (partial coverage)".
    - Write the exec brief.
  - **Verify:** Harness S2 rows pass; `test_s2_*` green, with the ledger for changes; the new SPL passes `validate_spl`.
  - **Depends on:** A3.1
  - **Evidence:** _(fill when done)_

- [ ] **A3.3** — S4
  - **Do:**
    - **ADD** "compromise assessment on VPN-GW-01/02 — collect logs + config snapshot before patch" and "rotate admin creds / revoke sessions on GW-01/02".
    - Monitoring stays "prepared" in the final summary.
    - Headline → "Exposure reduced · patch pending · 2 gateways under review".
    - Use a realistic advisory ID, not `ZD-FIXTURE`.
    - Hunt SPL: filter to external sources and aggregate by src/dest; show the privileged-management SPL.
    - Write the exec brief.
  - **Verify:** Harness S4 rows pass (no "contained" while `in_progress` is non-empty); `test_ec_s4_siem_first.py`, `test_s4_*` and `flagshipWorkspace.test.tsx` green with the ledger.
  - **Depends on:** A3.2
  - **Evidence:** _(fill when done)_

- [ ] **A3.4** — S7
  - **Do:**
    - **ADD** investigation step "identify accessing source (IP/user/engineering workstation)".
    - Move "ask OT team / ingest reply" into the investigation.
    - **ADD** remediation steps "restrict east-west allow to 10.80.4.14 (OT-safe change, OT engineer approval)" and "RTU logic/config integrity check".
    - The OT email disposition matches the conclusion.
    - Write the exec brief.
  - **Verify:** Harness S7 rows pass; `test_s7_*` green with the ledger; the Path A default is unchanged (`investigation_state.py:42-53`).
  - **Depends on:** A3.3
  - **Evidence:** _(fill when done)_

### A4 — RAG question R1 (1 d)

- [ ] **A4.1** — Capture the governed retrieval
  - **Do:** Run the governed SOC-KB retriever for the R1 query *outside* EC, e.g. a one-off script in `scripts/`. Save query rewrite, top-k chunks (doc, section, score, text) and the used/discarded split to `backend/app/demo/captures/r1_cert_in_rag.json`. **If no CERT-In document exists in the KB, stop (D2).**
  - **Verify:** The capture file exists with ≥3 chunks from ≥2 documents; `grep -c "CERT-In" backend/app/demo/captures/r1_cert_in_rag.json` ≥1; EC purity tests (`test_ec_isolation.py`, `test_experience_center_canonical_purity.py`) green.
  - **Depends on:** A3.4
  - **Evidence:** _(fill when done)_

- [ ] **A4.2** — R1 pack on the agent lifecycle
  - **Do:**
    - Copy `fixtures/_agent_template/` → `fixtures/r1/`, add a `PACKS` entry and register the profile.
    - **Plan steps:** rewrite query → retrieve (SOC-KB) → rerank → grounding check → compose answer with citations.
    - **Outcome:** a "How RAG answered this" panel from the capture (chunks, scores, used/discarded, sentence citations, an explicit "not in KB" line), plus the exec brief.
    - **Remediation (one approval):**
      - (1) create an incident flagged *CERT-In reportable* with the 6 h clock start and deadline;
      - (2) email CISO + Legal/Compliance with a pre-filled CERT-In report draft (A2.3 composer, editable, send is HIL).
    - Add R1 to the Flagship group; `test_e4` is updated via the ledger.
  - **Verify:** The harness R1 row passes (lifecycle + content + email lint); every answer sentence has ≥1 citation id present in the capture (new test); `npm test` green (no per-scenario frontend branch — the RAG panel renders from a generic `rag_trace` payload).
  - **Depends on:** A4.1
  - **Evidence:** _(fill when done)_

### A5 — Q1/Q2 fixes and storyline facts (1 d)

- [ ] **A5.1** — Q1 inference, SPL, flow (legacy shape kept)
  - **Do:**
    - MITRE T1110.001 → T1595/T1046 (scanning), T1078 stays "requires validation".
    - Add SPL for the 1 h deny summary, allow-after-deny on 10.20.1.10, and `svc_jump_ops` auth success with `values(src)`.
    - Remove the turn-0 `ticket_create`.
    - Chips advance (each removes itself and appends a finding line).
    - P1 isolate/disable carries a reason and a HIL gate.
  - **Verify:**
    - Harness Q1 rows (no action before chip, chips don't repeat, all SPL `validate_spl`-approved).
    - `test_live_path_untouched_by_ec.py::test_ec_q1_ticket_does_not_call_production_actions` is re-pointed to the chip-created ticket (ledger).
    - `test_ec_pipeline_dispatch_parity.py` and `test_experience_center_response.py` are updated (ledger).
  - **Depends on:** A4.2
  - **Evidence:** _(fill when done)_

- [ ] **A5.2** — Storyline + Q2
  - **Do:**
    - Add an optional `ec_story_thread {thread_id, day, prior_verdict}` badge on S1/Q1/S3.
    - One incident ID `INC-2026-89412`.
    - S3 first-seen and "confirmed" wording is consistent with Day 2 after Q1.
    - Q2 baseline SPL: continuous hourly buckets, drop the unused `event_count`, sort before `head`, a min-hours filter.
    - Q2's single chip becomes a terminal "Request saved-search deployment (prepared, not deployed)".
  - **Verify:** The harness story row passes (same ID/IP/host/account/ports across S1/Q1/S3); Q2 SPL is still sourced from `templates.json` via the `/spl-template-add` flow (derived sheets regenerated, staleness gate green); `validate_spl` approved.
  - **Depends on:** A5.1
  - **Evidence:** _(fill when done)_

### A6 — Release A closure (0.5 d)

- [ ] **A6.1** — Gate Release
  - **Do:** Run Gate EC, Gate Frozen and Gate Release.
  - **Verify:** All green; failure names equal A0.1; the ledger is complete for every modified assertion.
  - **Depends on:** A5.2
  - **Evidence:** _(fill when done)_

- [ ] **A6.2** — Visual re-walk + CIO rubric
  - **Do:** Re-walk 1–9 + R1 into `after_A/`. Score each against: verdict readable ≤10 s; every step shows *why*; remediation sequenced and gated with reasons; emails pass the lint and read BLUF-first; no scroll jump; tool fabric consistent. Write `docs/evals/ec_cio_coherence/report_release_A.md`.
  - **Verify:** S1/S2/S4/S7/R1 pass 6/6. S3/S5/S6/Q1 pass the email/SPL/scroll criteria, and their lifecycle criterion is marked "Release B". Every `ux_findings.md` row is resolved or deferred.
  - **Depends on:** A6.1
  - **Evidence:** _(fill when done)_

---

## Release B (~5 working days — approve separately after A6.2)

Each scenario gets its own pack + `PACKS` entry + profile (template: `fixtures/_agent_template/`). Legacy fixtures stay, so **rollback = remove the `PACKS` entry**. One PR per scenario. Same gates as A.

- [ ] **B1** — S5 on the lifecycle (1.5 d)
  - **Do:** Plan: show breach evidence (+SPL) → device version (Cisco MCP) → hardening policy (SOC-KB) → Agilus eligibility + image hash. Remediation, in the order from the content review: restrict mgmt ACL → forensic capture *before* change → rotate creds → change ticket + network approval (HIL) → Agilus upgrade 14→15 → verify version **and** config integrity → update incident.
  - **Verify:** The harness S5 xfail flips; `test_s5_*` updated via the ledger; forensic-capture step index < upgrade step index (assert).
  - **Depends on:** A6.2
  - **Evidence:** _(fill when done)_

- [ ] **B2** — S3 on the lifecycle (1.5 d)
  - **Do:** Plan: reuse Day-1 evidence → firewall-block SOP → exception check. Remediation order: prepare → SOC-lead approval (HIL) → send → ingest reply → confirm exception owner/expiry → remove exception + block (HIL, rollback) → **post-block verification SPL** → incident update → closure.
  - **Verify:** The harness S3 xfail flips; the SOC-lead approval index < send-request index < block index (assert); `test_s3_*`, `test_ec_s3_coordination.py` updated via the ledger.
  - **Depends on:** B1
  - **Evidence:** _(fill when done)_

- [ ] **B3** — Q1 on the lifecycle as Day 1 (1 d)
  - **Do:** Build a pack from the A5.1 content: the plan includes watch-fired context, allow-after-deny and auth attribution. Outcome: escalate MEDIUM→P1 with the reason. Remediation: isolate jump host (HIL) → disable `svc_jump_ops` (HIL) → P1 incident update → notify.
  - **Verify:** The harness Q1 lifecycle xfail flips; `test_e4` is unchanged (D5).
  - **Depends on:** B2
  - **Evidence:** _(fill when done)_

- [ ] **B4** — S6 on the lifecycle (1 d; cut line if Release B runs over)
  - **Do:** Plan: failures by account/source (counts) → **success-after-failure** (`auth_success_after_failure` template) → MFA outcome → scope pivots as plan revisions → historical INC-VPN-0712 match. Remediation: conditional-access block on DE for privileged VPN + watch (account disable NOT_RECOMMENDED, with the reason) → reopen/update INC-VPN-0712 → email the owner.
  - **Verify:** The harness S6 xfail flips; the outcome has numeric counts and named accounts; `test_s6_*` updated via the ledger.
  - **Depends on:** B3
  - **Evidence:** _(fill when done)_

- [ ] **B5** — Release B closure
  - **Do:** Gate Release; re-walk into `after_B/`; zero xfails remain in `test_ec_cio_lifecycle_walk.py`; update `plans/README.md` (this plan + mark stale "Active" rows whose branches are merged) and `docs/ec/agent_workflow_template.md` (justification fields, executive_brief, tool catalog, email composer, rag_trace, story thread).
  - **Verify:** `pytest app/tests/test_ec_cio_lifecycle_walk.py -rxX` shows 0 xfail; governance PASS; plan audit shows no `GAP:`; `find frontend/dist ! -perm -a+r | wc -l` = 0.
  - **Depends on:** B4
  - **Evidence:** _(fill when done)_

## Verification gaps (flag before coding)

- A0.3 / A6.2 need the user signed in once in the browser pane; the agent does not enter credentials.
- A4.1 depends on a CERT-In document being present in the governed SOC-KB (D2).

## Drift log

- 2026-09-24 rev 2: plan-reviewer verdict REVISE. The corrections above were adopted. Estimate re-based from 6 d → A 6 d + B 5 d, split into two approvals per the "not 10 days" constraint. Two rev-1 findings (S7, S4 HIL) were withdrawn as harness artifacts.
