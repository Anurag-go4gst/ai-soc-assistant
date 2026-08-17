---
name: races-investigation-execution-ux
overview: "Build a shared Experience Center execution-progress shell, complete S1–S7 operational journeys with honest staged playback, add allowlisted real outbound EC email, then converge legacy ChatPanel demoMode onto the same visual product in a separate worktree."
status: active
date: 2026-08-17
canonical_plan: plans/2026-08-17_races-investigation-execution-ux.md
loop_runner: plans/LOOP_RUNNER_races-investigation-execution-ux.md
revision: 2
revision_date: 2026-08-17
---

# RACES investigation execution UX (rev 2)

**Status: `active`.** Implementation is approved on `feat/races-investigation-execution-ux`.

Do **not** reopen [`plans/2026-08-16_2310_races-experience-center.md`](2026-08-16_2310_races-experience-center.md) (DONE, PR #143).

**Baselines**

| Pin | Value |
|-----|--------|
| Master | `af93fb373d48efc1d5e8dd36795bc62fb026d868` |
| RACES merge | PR #143 @ `d4f9210303aac5f6ae964f0259fb9fc25dd59743` |
| Primary branch | `feat/races-investigation-execution-ux` |
| Parallel legacy branch | `feat/legacy-ec-experience-convergence` (create after H1 presentation checkpoint) |
| Parallel worktree | `/var/www/ai-soc-assistant-legacy-ec` |

## Objective

One Experience Center **product family**:

```text
Scenario selected → Run investigation → agent visibly works → evidence arrives
→ InvestigationOutcome → SOC answer → follow-up journeys → coordination
→ HIL → governed action → receipt → verify → updated outcome / closure
```

RACES (`/scenarios`) is Workstream A. Legacy ChatPanel **demoMode=true** is Workstream B in a separate worktree. Production `/chat` live semantics stay frozen.

## User decisions (rev 2 — authoritative)

These **supersede** rev 1 where they conflict.

1. **Legacy EC work is approved**, but **not in the primary RACES worktree.** ChatPanel `demoMode=true` freeze exception applies only on `feat/legacy-ec-experience-convergence`. It does **not** authorize live `/chat` streaming, `LIVE_LINEAR_STEPS`, server progress mapping, production actions, or ChatPipeline changes.
2. **Both ECs must look like the same product.** Not “similar DNA” — one canonical presentation shell (`ExperienceExecutionProgressPanel`) matching the existing `InvestigationProgressPanel` chrome exactly (header, cyan/dark panel, spinner, rows, elapsed, n/N, activity lines, badges, finalization, spacing, typography, error, waiting, answer transition). Scenario **content** may differ.
3. **S1–S7 are not done** until each has a meaningful Investigation → gaps → follow-up → decision → recommended action → HIL (if side effect) → execute → receipt → verify (if meaningful) → updated outcome / closure path. Destructive remediation is not required when evidence is insufficient — the UI must say why and offer the correct next evidence/action.
4. **Outbound Send email is REAL** through an EC-controlled allowlisted transport when configured. Not a fake `SUCCESS`. Splunk/Cisco/EDR/IAM/etc. stay simulated. Inbound replies may remain fixture-backed and must be labeled as such. Automated tests never send real mail.

## Stop conditions

- All checklist items checked with evidence, **or**
- Same Verify fails twice on one item, **or**
- Decision needed, **or**
- Any hard STOP below.

### Hard STOP

Stop immediately if a step requires: production `/chat` / T1–T4 / RQC / route adjudication; ResourcePlan / compiler / PhaseRegistry / PhasePolicy / PhaseContract / Resource Planner graph; production EvidenceState / InvestigationOutcome / synthesis / Phase 10 / MCP gate / SPL validator **behavior** / session semantics; `architecture.md`; live MCP/LLM/RAG for animation; backend sleep orchestrator; another Resource Planner or MCP framework; production `/api/actions`; inventing evidence in a journey; false live-connector claims; unrestricted email recipients; committed email secrets; real email from pytest/vitest; leaking legacy demo features into `demoMode=false`; invariant FAIL; weakening tests to continue.

### Continue automatically when

Change stays EC/demo scoped; scenario completeness improves without production redesign; real email stays allowlisted and explicit; Verify and invariants pass. Do not ask between normal phases.

### Allowed freeze exception (Workstream B only)

MAY edit `frontend/src/components/ChatPanel.tsx` **only** for `demoMode=true` Experience Center presentation/actions, and only on the legacy branch/worktree.

Tests must prove:

```text
demoMode=true  → shared Experience Center presentation
demoMode=false → existing production live-chat progress/behavior unchanged
```

---

# Workstream split

## A — RACES (this worktree)

Branch `feat/races-investigation-execution-ux` owns: shared visual shell foundation; `ec_execution_journey`; RACES player; S1–S7 completeness; follow-up/Phase 10 UX; real email transport; RACES acceptance.

Do **not** edit ChatPanel here.

## B — Legacy EC (separate worktree)

After H1 shared-shell checkpoint commit on A:

1. `git worktree add /var/www/ai-soc-assistant-legacy-ec -b feat/legacy-ec-experience-convergence master`
2. Cherry-pick **only** the shared presentation-primitive commit(s) if they are not on master yet.
3. Implement H7 there. Do not merge worktrees while unstable.

---

# Shared visual architecture

```text
                         ExperienceExecutionProgressPanel
                         (pure renderer — same chrome as old EC)
                                 ↑
                 ┌───────────────┴───────────────┐
                 │                               │
        RACES EC journey player          Legacy demo player
          scenario metadata            legacy progress metadata
                 │                               │
        /scenarios runtime              ChatPanel demoMode=true

Production live chat:
existing server progress semantics
→ optional shared pure renderer only
→ NO EC journey sequencer
```

**Canonical files (NEW)**

| File | Role |
|------|------|
| `frontend/src/components/experience-center/ExperienceExecutionProgressPanel.tsx` | Pure visual shell cloned from `InvestigationProgressPanel.tsx` |
| `frontend/src/lib/experienceCenterExecution.ts` | Shared types + status model (PENDING/RUNNING/COMPLETE/WAITING/BLOCKED/FAILED/VERIFYING) |
| `frontend/src/components/ec/ecExecutionJourneyPlayer.ts` | RACES sequencer only (do not import live-chat `playInvestigationProgress`) |

Place the shell **outside** `components/ec/` so ChatPanel can import it in Workstream B without violating G2 (`ChatPage`/`Cockpit`/`ChatPanel` must not import `@/components/ec`).

Inspect before restyling: `InvestigationProgressPanel.tsx`, ChatBubble progress layout, spinner, `LiveElapsed`, n/N, activity-line interval, completion icons, error/finalization blocks.

Acceptance: shared component **or** DOM/class contract + screenshots proving equivalent rendering.

---

# S1–S7 completeness matrix (audited 2026-08-17)

Legend: `YES` present · `PARTIAL` present but incomplete · `GAP` missing · `SIM` simulated only (must become real email where listed)

| Requirement | S1 | S2 | S3 | S4 | S5 | S6 | S7 |
|-------------|----|----|----|----|----|----|----|
| Initial investigation | YES | YES | YES | YES | YES | YES | YES |
| EvidenceState | YES | YES | YES | YES | YES | YES | YES |
| InvestigationOutcome | YES | YES | YES | YES | YES | YES | YES |
| Meaningful uncertainty | YES | YES (breach not confirmed) | YES (whitelist reassess) | YES (vulnerable ≠ compromised) | YES until v15 verified | YES (scope) | YES (`unresolved_conflict`) |
| 3+ contextual follow-ups | YES (5 continue) | YES | YES | YES | YES | YES | YES |
| Operational next action | PARTIAL | PARTIAL | YES | YES | YES | PARTIAL | PARTIAL |
| Ticket | YES (auto-exec) | YES (auto-exec) | YES | YES | YES | YES fetch/update | YES (path-gated) |
| Email | **GAP** | **SIM** `notify` auto-exec | **SIM** `email_send` auto-exec | **SIM** `notify` | **SIM** `notify` | **SIM** `notify` | **SIM** `email_send` auto-exec |
| Tool / MCP (simulated) | firewall_block HIL | iam_disable HIL | firewall HIL | temp control HIL | cisco.upgrade HIL | none (correct) | none until path |
| HIL for side effects | PARTIAL (block yes; ticket auto) | PARTIAL (iam yes; notify auto) | YES block/whitelist; **email auto** | YES control; **notify auto** | YES upgrade; **notify auto** | **notify auto** | **email auto** |
| Action receipt | PARTIAL | PARTIAL | YES (fake email SUCCESS) | YES | YES | PARTIAL | PARTIAL |
| Verification | **GAP** | **GAP** (credential state) | YES `verify_firewall_rule` | YES temp control | YES v15 | PARTIAL (ticket update flag) | **GAP** until path |
| Outcome update after action | PARTIAL | PARTIAL | YES reassessment | PARTIAL | YES | YES applicability | YES path A/B |
| Closure / summary | **GAP** | **GAP** | **GAP** | YES `generate_executive_summary` | YES `generate_closure_summary` | **GAP** | **GAP** |
| Execution journey animation | **GAP** | **GAP** | **GAP** | **GAP** | **GAP** | **GAP** | **GAP** |

### Gap close list (H2)

**S1** — Add: REAL email to firewall/security team (logical `FIREWALL_TEAM`); HIL + simulated firewall execute + **verify rule**; update incident; closure/executive summary. Do not auto-block from initial evidence. Keep existing 30+30 / `validate_spl` / EDR / TI / prior-incident follow-ups.

**S2** — Keep Attempted → Blocked → breach not confirmed. Convert AppSec notify to REAL email (`APPSEC_TEAM`) with HIL/review/send. Add credential verify after `iam_disable`. Add update-incident + closure. Do not auto-execute email.

**S3** — Keep workflow. Replace auto `ensure_executed_action(email_send)` with draft → review → **real send** → WAITING. Inbound ingest stays fixture-backed and labeled. Add closure. Keep HIL for whitelist/block + verify.

**S4** — Convert network notify to REAL email (`NETWORK_TEAM`). Keep no-playbook COMPLETE (not FAILED). Keep vulnerable ≠ compromised. Closure already exists.

**S5** — Convert `request_network_approval` to REAL approval-request email when configured. No auto-approve. No live Cisco claims. Closure already exists.

**S6** — Convert owner notify to REAL email (`INCIDENT_OWNER`). Optional IAM escalate chip (notify/HIL, not destructive). Add current-scope incident summary. Do **not** invent firewall/Cisco remediation.

**S7** — Convert Ask OT team to REAL email (`OT_TEAM`) with HIL; inbound fixture-backed. After Path A/B, keep tickets; add closure/summary. Do not remediate before conflict resolution.

**Email audit:** no SMTP/SendGrid/SES client exists in-repo (`.env.example` has no mail keys; `config.py` has no SMTP settings; S3 test currently forbids `smtplib` **in the S3 pack**). Implement isolated `backend/app/demo/ec_email.py` (or equivalent). Keep `smtplib` out of fixture packs.

---

# Real email architecture (H6A)

EC-only. Never `/api/actions`. Never production Phase 10.

```text
Draft → Review → visitor clicks Send → allowlist check → transport
→ provider acceptance receipt
```

| Field | Real send | Simulated tool |
|-------|-----------|----------------|
| `production_side_effect` | `false` | `false` |
| `external_side_effect` | `true` | `false` |
| `execution_mode` | `live_allowlisted_email` | `simulated_phase10_action` |
| provenance | `ec_allowlisted_email` (NEW kind) | `simulated_phase10_action` |

Do **not** label a real email as `simulated_phase10_action`.

**Allowlist:** map logical teams `FIREWALL_TEAM | APPSEC_TEAM | NETWORK_TEAM | INCIDENT_OWNER | OT_TEAM | SOC_LEAD` to env-configured addresses. Exact mailbox and/or approved test-domain allowlist. Unknown recipient → **FAIL CLOSED** (`recipient_not_allowlisted`).

**Idempotency:** stable action id + idempotency key + sent timestamp + provider message id. Re-Execute must not send a duplicate unless a new action is prepared.

**Secrets:** SMTP/API credentials from env/secret manager only. Never commit.

**Tests:** in-memory/fake transport. Pytest/vitest must not open a network mail socket.

**Live:** if unconfigured, return `REAL_EMAIL_CONFIGURATION_REQUIRED` — do not fake SUCCESS. Final PASS for real email requires one manual allowlisted send accepted by the provider.

**Inbound:** fixture-backed unless a later isolated read connector exists. UI must not claim live inbound if fixture.

Preferred implementation: stdlib `smtplib` behind `EcEmailTransport` protocol with `FakeEcEmailTransport` default in tests.

---

# Target journeys (visitor copy)

Locked titles for H3 (S1/S3/S5) and H4 (S2/S4/S6/S7) remain as in the user brief. Honesty: no TLS handshake, bearer auth, live MCP, or live Splunk execution claims. Use “Replaying governed Splunk search”, “Checking Cisco router”, etc.

Follow-up journeys (H5) keyed by stable `follow_up_id`, never raw phrase matching (S6 synonyms already resolve to ids).

Phase 10 (H6B): player **WAITS** at HIL with no fake timer. Skip never manufactures approval, email, remediation, or verification.

Timing: initial 8–12s; follow-up 4–7s; jitter ±20% max.

---

# Dependency order

Workstream A:

`H0-1 → H0-2 → H1-1 → H1-2 → H1-3 → H1-4 → H2-1 → H2-2 → H2-3 → H2-4 → H2-5 → H2-6 → H2-7 → H3-1 → H3-2 → H3-3 → H4-1 → H4-2 → H5-1 → H6A-1 → H6A-2 → H6B-1 → H8-1 → H9-A`

Workstream B (other worktree, after H1-4 commit):

`H7-0 → H7-1 → H7-2 → H7-3 → H9-B`

## Checklist

- [x] **H0-1** — Pin catalogs, freeze, live progress, flagship tests
  - **Do:** Run isolation/catalog/live-progress and S1–S7 pytest. Do not change production files. Record counts in Evidence.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_races_chatpanel_scenario_list_isolation.py app/tests/test_races_g2_frontend_isolation.py app/tests/test_live_path_untouched_by_ec.py app/tests/test_live_chat_linear_progress.py app/tests/test_s1_governed_splunk_investigation.py app/tests/test_s2_ai_application_security.py app/tests/test_s3_firewall_team_coordination.py app/tests/test_s4_zero_day_no_playbook.py app/tests/test_s5_cisco_hardening_remediation.py app/tests/test_s6_investigation_continuity.py app/tests/test_s7_conflicting_ot_evidence.py -q`
  - **Depends on:** none
  - **Evidence:** `55 passed in 3.29s` (2026-08-17). Completeness matrix in this plan filled from current S1–S7 packs. No production files changed.

- [x] **H0-2** — Pin ChatPanel freeze on Workstream A
  - **Do:** Confirm primary branch does not modify ChatPanel. Capture `git diff --name-only -- frontend/src/components/ChatPanel.tsx`.
  - **Verify:** `git diff --name-only -- frontend/src/components/ChatPanel.tsx backend/app/api/routes_chat.py backend/app/chat/pipeline.py backend/app/schemas/responses.py` prints nothing related to this workstream
  - **Depends on:** H0-1
  - **Evidence:** Command printed empty. Working tree only has plan files (`plans/README.md` modified, new 2026-08-17 plan + loop runner). ChatPanel/routes_chat/pipeline/PlaceholderResponse untouched.

- [x] **H1-1** — Shared pure visual shell matching old EC
  - **Do:** Add `ExperienceExecutionProgressPanel` under `frontend/src/components/experience-center/` by adapting `InvestigationProgressPanel.tsx` (header, spinner, rows, elapsed, n/N, activity lines, error, finalization, cyan/slate chrome). Add WAITING / BLOCKED / VERIFYING without removing old states. Do not restyle into a different card system. Do not change `LIVE_LINEAR_STEPS`.
  - **Verify:** `cd frontend && npm test -- src/components/experience-center/ src/lib/experienceCenterExecution.ts`; `rg -n "TLS handshake|bearer auth" frontend/src/components/experience-center/ frontend/src/lib/experienceCenterExecution.ts` prints nothing
  - **Depends on:** H0-2
  - **Evidence:** `vitest` 8 passed. Implementation files have no TLS/bearer copy (only a negative assertion in the test). Chrome constants match InvestigationProgressPanel (`rounded-xl border border-cyan-500/25 bg-cyan-500/[0.05]`). LIVE_LINEAR_STEPS untouched.

- [x] **H1-2** — `ec_execution_journey` on ExperienceCenterResponse only
  - **Do:** Add optional journey models to `backend/app/demo/ec_response.py`. Do not touch `PlaceholderResponse`. Backend does not sleep.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_experience_center_response.py app/tests/test_s1_governed_splunk_investigation.py -q`; `rg -n "ec_execution_journey" backend/app/schemas/responses.py` prints nothing
  - **Depends on:** H1-1
  - **Evidence:** pytest `19 passed in 2.33s`. `rg` on `backend/app/schemas/responses.py` prints nothing (`placeholder_grep` empty). Lab turns still have `ec_execution_journey is None`; no backend sleep.

- [x] **H1-3** — RACES player + workspace hide Layer 1 until complete
  - **Do:** RACES sequencer in `frontend/src/components/ec/` using the shared shell. Fetch may finish immediately; UI plays stages. Layer 1 hidden until complete or Skip (Skip may land in H8; if absent, wait for playback). Epoch cancel on new Run / scenario switch so stale answers cannot appear.
  - **Verify:** `cd frontend && npm test -- src/components/ec/`; grep `EcInvestigationWorkspace.tsx` for `ExperienceExecutionProgressPanel`
  - **Depends on:** H1-2
  - **Evidence:** `vitest` `src/components/ec/` 18 passed. Workspace imports `ExperienceExecutionProgressPanel` (lines 11 and 113). Layer 1 hidden until playback; stale epoch cancel covered. Skip deferred to H8.

- [ ] **H1-4** — Presentation-only checkpoint commit
  - **Do:** Commit shared shell + RACES player wiring (no ChatPanel, no production modules) as the cherry-pick base for Workstream B. Message: `execution-ui: add shared progress shell and RACES player`.
  - **Verify:** `git log -1 --oneline`; `git diff --name-only HEAD~1 -- frontend/src/components/ChatPanel.tsx backend/app/chat/pipeline.py` empty
  - **Depends on:** H1-3
  - **Evidence:** _(fill when done)_

- [ ] **H2-1** — Close S1 operational gaps (email/verify/update/closure chips)
  - **Do:** Add S1 chips/actions: email firewall/security team (logical `FIREWALL_TEAM`, not sent until H6A transport), HIL firewall execute + verify, update incident, closure summary. Do not auto-block. Do not change 30+30 SPL.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_governed_splunk_investigation.py -q`
  - **Depends on:** H1-4
  - **Evidence:** _(fill when done)_

- [ ] **H2-2** — Close S2 operational gaps
  - **Do:** Stop auto-executing AppSec notify. Prepare email_send with HIL. Add credential verify, update-incident, closure. Keep breach not confirmed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s2_ai_application_security.py -q`
  - **Depends on:** H2-1
  - **Evidence:** _(fill when done)_

- [ ] **H2-3** — Close S3 email-HIL + closure gaps (still fake transport until H6A)
  - **Do:** Stop auto `ensure_executed_action` on send; require Approve/Send. Add closure summary. Keep inbound fixture-backed. Keep block/whitelist HIL + verify.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s3_firewall_team_coordination.py -q`
  - **Depends on:** H2-2
  - **Evidence:** _(fill when done)_

- [ ] **H2-4** — Close S4 notify-HIL (logical NETWORK_TEAM)
  - **Do:** Prepare real-email-shaped notify/email_send with HIL instead of auto-exec. Keep no-playbook COMPLETE and executive summary.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s4_zero_day_no_playbook.py -q`
  - **Depends on:** H2-3
  - **Evidence:** _(fill when done)_

- [ ] **H2-5** — Close S5 approval-email HIL
  - **Do:** Convert `request_network_approval` to email_send HIL (logical `NETWORK_TEAM` or `SOC_LEAD`). Do not auto-approve upgrade.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s5_cisco_hardening_remediation.py -q`
  - **Depends on:** H2-4
  - **Evidence:** _(fill when done)_

- [ ] **H2-6** — Close S6 owner-email + summary
  - **Do:** HIL email to `INCIDENT_OWNER`. Add current-scope summary chip. No destructive remediation.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s6_investigation_continuity.py -q`
  - **Depends on:** H2-5
  - **Evidence:** _(fill when done)_

- [ ] **H2-7** — Close S7 OT-email HIL + closure
  - **Do:** Ask OT team uses email_send HIL (logical `OT_TEAM`); inbound still fixture. Add closure/summary after Path A or B. Do not force incident before resolution.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s7_conflicting_ot_evidence.py -q`
  - **Depends on:** H2-6
  - **Evidence:** _(fill when done)_

- [ ] **H3-1** — S1 initial 12-stage journey metadata
  - **Do:** Author `ec_execution_journey` on empty follow-ups with the locked S1 titles. Honest Splunk replay copy.
  - **Verify:** pytest assertion that initial S1 stage titles match the locked 12; `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_governed_splunk_investigation.py -q`
  - **Depends on:** H2-7
  - **Evidence:** _(fill when done)_

- [ ] **H3-2** — S3 initial 7-stage + WAITING after send
  - **Do:** Locked S3 titles; after send without ingest, journey WAITING (no auto-ingest).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s3_firewall_team_coordination.py -q`
  - **Depends on:** H3-1
  - **Evidence:** _(fill when done)_

- [ ] **H3-3** — S5 initial 9-stage journey
  - **Do:** Locked S5 titles disclosing version 14 as fixture replay.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s5_cisco_hardening_remediation.py -q`
  - **Depends on:** H3-2
  - **Evidence:** _(fill when done)_

- [ ] **H4-1** — S2/S4 initial journeys
  - **Do:** S2 Attempted → Blocked → not confirmed. S4 no-playbook COMPLETE not FAILED.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s2_ai_application_security.py app/tests/test_s4_zero_day_no_playbook.py -q`
  - **Depends on:** H3-3
  - **Evidence:** _(fill when done)_

- [ ] **H4-2** — S6/S7 initial journeys
  - **Do:** S6 initial + scope-change follow-up stages (OUT_OF_SCOPE / SUPERSEDED / REUSABLE / STALE). S7 linger on Conflict detected; initial disposition `unresolved_conflict`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s6_investigation_continuity.py app/tests/test_s7_conflicting_ot_evidence.py -q`
  - **Depends on:** H4-1
  - **Evidence:** _(fill when done)_

- [ ] **H5-1** — Follow-up journeys by `follow_up_id`
  - **Do:** Author continuation journeys for major continue-chips (EDR, TI, prior incidents, scope change, DLP/identity, OT inventory, etc.). Header “Continuing investigation”. Shorter duration hints.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_governed_splunk_investigation.py app/tests/test_s2_ai_application_security.py app/tests/test_s3_firewall_team_coordination.py app/tests/test_s6_investigation_continuity.py app/tests/test_s7_conflicting_ot_evidence.py -q`
  - **Depends on:** H4-2
  - **Evidence:** _(fill when done)_

- [ ] **H6A-1** — Isolated EC email transport + fake default
  - **Do:** Add `backend/app/demo/ec_email.py` (protocol + SMTP impl + Fake). Env keys for host/port/user/pass/from, logical team map, allowlist. Fail closed. Idempotency store. Wire `email_send` execute through adapter. Tests use Fake. No secrets in git. Update S3 “no smtplib in pack” to allow adapter module.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_ec_email_transport.py app/tests/test_s3_firewall_team_coordination.py -q`
  - **Depends on:** H5-1
  - **Evidence:** _(fill when done)_

- [ ] **H6A-2** — Flags: production_side_effect false, external_side_effect true
  - **Do:** Real-send receipts use `execution_mode=live_allowlisted_email`. Unconfigured → `REAL_EMAIL_CONFIGURATION_REQUIRED`, not fake SUCCESS. Animation never auto-sends.
  - **Verify:** pytest: allowlist reject; duplicate execute does not call transport twice; fake transport used under pytest; `production_side_effect is False`
  - **Depends on:** H6A-1
  - **Evidence:** _(fill when done)_

- [ ] **H6B-1** — Phase 10 player WAIT at HIL; execute/verify journeys
  - **Do:** Firewall / Cisco / credential / ticket action journeys. WAITING until Approve. Execute → receipt → verify. No verify-before-execute success. Tickets remain simulated.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s5_cisco_hardening_remediation.py app/tests/test_s3_firewall_team_coordination.py -q`; frontend player WAITING test
  - **Depends on:** H6A-2
  - **Evidence:** _(fill when done)_

- [ ] **H7-0** — Create legacy worktree (Workstream B)
  - **Do:** After H1-4 commit exists, create `/var/www/ai-soc-assistant-legacy-ec` on `feat/legacy-ec-experience-convergence` from master and cherry-pick shared-shell commit(s). Do not implement B in the primary worktree.
  - **Verify:** `git -C /var/www/ai-soc-assistant-legacy-ec rev-parse --abbrev-ref HEAD` equals `feat/legacy-ec-experience-convergence`; ChatPanel still frozen on primary branch
  - **Depends on:** H1-4
  - **Evidence:** _(fill when done — may run in parallel after H1-4)_

- [ ] **H7-1** — Legacy demoMode uses shared shell; remove TLS/bearer copy
  - **Do:** **Workstream B only.** ChatPanel `demoMode=true` renders `ExperienceExecutionProgressPanel`. Replace dishonest demo strings. Do not change `LIVE_LINEAR_STEPS` or `/chat/stream`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_live_chat_linear_progress.py app/tests/test_races_g2_frontend_isolation.py -q`; ChatPanel/Cockpit still do not import `@/components/ec`; `rg -n "TLS handshake" frontend/src/lib/investigationProgress.ts` empty in demo activity (live block unchanged)
  - **Depends on:** H7-0
  - **Evidence:** _(fill when done)_

- [ ] **H7-2** — Selective legacy demo coordination (not all 10)
  - **Do:** **Workstream B only.** Audit frozen 10; add EC email/ticket/HIL only where useful (prioritize firewall coordinated incident, IR containment, CERT-In/OT, supply-chain). `demoMode=true` only. Do not wholesale-port S1–S7 FSMs.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_races_chatpanel_scenario_list_isolation.py -q`; live `/chat` tests still pass
  - **Depends on:** H7-1
  - **Evidence:** _(fill when done)_

- [ ] **H7-3** — Legacy Send email reuses same EC transport
  - **Do:** **Workstream B only.** One mail system. Same allowlist/idempotency/HIL.
  - **Verify:** same email pytest module; no second SMTP stack (`rg -n "smtplib" backend/app/demo/`)
  - **Depends on:** H7-2, H6A-1
  - **Evidence:** _(fill when done)_

- [ ] **H8-1** — Skip, reset, timing, honesty polish (Workstream A)
  - **Do:** Skip-to-answer skips animation only. Epoch reset on scenario switch. Timing 8–12s / 4–7s / ±20%. Shared error “Investigation interrupted”. Honesty grep clean.
  - **Verify:** `rg -n "TLS handshake|bearer auth|live MCP|live Splunk execution" frontend/src/components/ec/ frontend/src/components/experience-center/ backend/app/demo/fixtures/`; `cd frontend && npm test -- src/components/ec/ src/components/experience-center/ && npm run build`
  - **Depends on:** H6B-1
  - **Evidence:** _(fill when done)_

- [ ] **H9-A** — RACES acceptance + freeze re-pin
  - **Do:** Browser-walk S1–S7 against the user acceptance script (or record blockers). Re-run freeze + flagship tests. `/invariant-check` 7/7 on the diff.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_live_path_untouched_by_ec.py app/tests/test_races_g2_frontend_isolation.py app/tests/test_races_chatpanel_scenario_list_isolation.py app/tests/test_live_chat_linear_progress.py app/tests/test_s1_governed_splunk_investigation.py app/tests/test_s2_ai_application_security.py app/tests/test_s3_firewall_team_coordination.py app/tests/test_s4_zero_day_no_playbook.py app/tests/test_s5_cisco_hardening_remediation.py app/tests/test_s6_investigation_continuity.py app/tests/test_s7_conflicting_ot_evidence.py -q`
  - **Depends on:** H8-1
  - **Evidence:** _(fill when done)_

- [ ] **H9-B** — Legacy acceptance (Workstream B)
  - **Do:** Visual parity vs RACES shell; dishonest strings gone; selected demo scenarios; live `/chat` regression. Report `LEGACY_EC_CONVERGENCE_STATUS`.
  - **Verify:** live linear progress pytest + catalog isolation + G2 on the legacy worktree
  - **Depends on:** H7-3
  - **Evidence:** _(fill when done)_

## Verification gaps

H9-A browser walk depends on a running stack; if UI is down, record `BROWSER=BLOCKED` and keep automated Verify. H6A live send depends on operator env — unconfigured is `REAL_EMAIL_STATUS=CONFIGURATION_REQUIRED`, not a fake pass.

## Drift log

- 2026-08-17 rev 2: User approved implementation, visual **parity** (not “similar DNA”), S1–S7 completeness, **real allowlisted email**, and legacy ChatPanel **demoMode** freeze exception **in a separate worktree only**.
- 2026-08-17: Rev 1 plan file was not present on this worktree (`plans/README.md` had been deleted in the working tree and was restored from git). Completeness matrix filled from current packs.
- 2026-08-17: No in-repo mail transport exists. S3 currently auto-executes simulated `email_send` and tests forbid `smtplib` in the S3 pack — adapter must live outside packs.
- 2026-08-17: POST `/demo/scenarios/{id}/run` already returns `ExperienceCenterResponse`; ChatPanel ignores extras. Do not add backend sleeps.

## Commit strategy

Primary A:

1. `execution-ui: add shared progress shell and RACES player`
2. `races: complete flagship investigation and remediation journeys`
3. `races: add follow-up and Phase 10 execution experiences`
4. `races: add allowlisted real EC email transport`
5. `races: polish and acceptance`

Legacy B:

1. `legacy-ec: adopt shared execution presentation`
2. `legacy-ec: add selected EC demo coordination actions`
3. `legacy-ec: acceptance and live-chat regression`

Do not merge branches automatically. Do not merge PRs without final review.

## Final report fields

When reporting: A RACES · B Legacy · C Email (no secrets) · D Production isolation · E branch SHAs.

End with `RACES_AGENTIC_UX_STATUS` and `LEGACY_EC_CONVERGENCE_STATUS` independently. Unconfigured mail → `REAL_EMAIL_STATUS=CONFIGURATION_REQUIRED`.
