---
name: ec-r1-rag-procedure-question
overview: "Replace the EC R1 RAG question with a procedure question (reported phishing, user clicked); answer from a chunk-level hybrid retrieval record with a citation on every sentence, then SOP-cited actionables."
status: done — 12/12 (rev 4 visual check of the after-approval screen pending sign-in); uncommitted
date: 2026-09-29
canonical_plan: plans/2026-09-29_1536_ec-r1-rag-procedure-question.md
branch: feat/ec-r1-phishing-procedure
start_sha: e6a14376
---

# EC R1 — procedure question with cited answer, then actionables

## Why

The current R1 question — *"A privileged database admin account logged in successfully after repeated
failed logins. What does our SOP require, and who do we need to escalate to?"* — is overkill for a
RAG demo:

1. **It is an investigation, not a procedure lookup.** It runs a Splunk login search (`the_login`) and
   the answer depends on that telemetry, so RAG is not what answers it.
2. **It asks two questions at once** about a Tier-1 privileged DB — a live incident, not a "what's our
   process" ask.
3. **Citations are a single footer line** (`Sources: A · B`), so nobody can see which sentence came from
   which passage, or that there was any retrieval at all.

An analyst asks the knowledge base *"what do we do when X happens?"* for high-volume cases where the
procedure — not telemetry — decides the next steps. Reported phishing where the user clicked is the most
common Tier-1 ticket; every SOP step maps to a ticket or an email.

## Frozen content

### F1 — Question

> **A user reported a phishing email and says they clicked the link. What does our phishing procedure say we should do?**

- Label: `R1 · What does our phishing procedure say? (knowledge base)`
- `demo_order=8`, `family="r1_governed_rag"`, `scenario_id` unchanged (D1).
- Old question and `legacy_phrasings` retired, not aliased (D3).

### F2 — Environment additions (`ec_environment.py`)

| Constant | Value |
|---|---|
| `SOP_PHISHING` | `SOC-SOP-PHISH-001` (current approved version `2026.3`) |
| `PHISH_USER` | `r.mehta` (Finance · accounts payable) |
| `PHISH_SENDER` | `billing@invoice-portal-verify[.]com` (defanged) |
| `TASK_R1_IAM` | `TASK0019263` |
| `TASK_R1_MAIL` | `TASK0019264` |
| `INCIDENT_R1` | `INC0048415` (reused) |

### F3 — Investigation checks (knowledge base only — no Splunk search)

| id | title | tool | operation | result |
|---|---|---|---|---|
| `sop` | What does our phishing procedure say? | `soc_kb` | `soc_kb.retrieve · SOC-SOP-PHISH-001` | 5 chunks kept from SOC-SOP-PHISH-001 v2026.3 (§3.1–§3.4, §4.1); top match §3.2 "Contain the account", rerank 0.96. Four steps apply to a click. |
| `escalation` | When do we escalate? | `soc_kb` | `soc_kb.retrieve · SOC-ESC-MATRIX-01` | Row PH-02 "Phishing — user interaction", rerank 0.86: Tier 1 owns it; escalate to Tier 2 only on password entry, an approved MFA prompt, or more than 10 people clicking. |

### F4 — Retrieval record (rendered by the existing "How RAG answered this" panel)

Index and pipeline — model names are the SOC-KB's configured defaults (`config.py`:
`soc_kb_vector_model`, `soc_kb_reranker_model`) and stage names follow `knowledge/hybrid.py::RETRIEVAL_STAGES`:

- Query rewrite: `reported phishing email · user clicked link · required response steps · escalation criteria`
- Collections: `SOC SOPs` · `Escalation matrix` · `Priority policy`
- Index: `BAAI/bge-m3` dense, 1024-d · BM25 sparse · 41 approved documents · 1,286 chunks · section-aware chunking, 512-token max, 64-token overlap
- Funnel: 40 dense + 40 BM25 candidates → 58 after reciprocal-rank fusion (k=60) → 5 excluded by policy → top 8 reranked by `BAAI/bge-reranker-v2-m3` → 7 kept (rerank ≥ 0.50) → 6 cited
- Excluded before ranking (5): 3 superseded (SOC-SOP-PHISH-001 v2025.4 §3), 1 draft (SOC-SOP-PHISH-002 "Invoice fraud" v0.4), 1 expired (awareness bulletin 2024-11)

Kept chunks (sorted by rerank):

| label | chunk_id | section | tokens | cosine (rank) | BM25 (rank) | rerank | used for |
|---|---|---|---|---|---|---|---|
| [2] | `SOC-SOP-PHISH-001@2026.3#c07` | §3.2 Contain the account | 212 | 0.861 (1) | 15.4 (1) | 0.96 | Step: reset password, revoke sessions |
| [3] | `SOC-SOP-PHISH-001@2026.3#c08` | §3.3 Contain the message | 198 | 0.824 (2) | 11.7 (3) | 0.93 | Step: purge and block sender |
| [1] | `SOC-SOP-PHISH-001@2026.3#c06` | §3.1 Open an incident | 188 | 0.812 (3) | 12.9 (2) | 0.91 | Step: open an incident |
| [4] | `SOC-SOP-PHISH-001@2026.3#c09` | §3.4 Notify the user | 174 | 0.797 (4) | 10.2 (5) | 0.88 | Step: tell the user, ask what they entered |
| [5] | `SOC-ESC-MATRIX-01@2026.1#c14` | Row PH-02 Phishing — user interaction | 96 | 0.774 (6) | 10.8 (4) | 0.86 | Escalation criteria |
| [6] | `SOC-POL-PRIO-01@2026.2#c03` | Rule 3 | 81 | 0.702 (9) | 6.1 (11) | 0.71 | Priority P3 |
| [7] | `SOC-SOP-PHISH-001@2026.3#c10` | §4.1 Credential entry confirmed | 205 | 0.768 (5) | 9.4 (6) | 0.64 | Not applied — password entry not confirmed |

Chunk excerpts (quoted in the panel):

1. §3.1 — "For every reported phishing message a user interacted with, open an incident. Set priority per SOC-POL-PRIO-01; do not raise it on the report alone."
2. §3.2 — "If the user clicked a link, reset the user's password and revoke active sessions within 4 hours, whether or not credential entry is confirmed."
3. §3.3 — "Remove the message from all mailboxes by message ID and block the sender address at the email gateway. Record the purge count in the incident."
4. §3.4 — "Tell the user what was done and ask whether they entered credentials, approved an MFA prompt or opened an attachment. Record the answer."
5. PH-02 — "Owner: SOC Tier 1. Escalate to Tier 2 on credential entry, MFA approval, or more than 10 recipients clicking."
6. Rule 3 — "Attempted misuse with no access gained, on a non-critical asset: P3."
7. §4.1 — "If the user entered credentials, treat it as account compromise: escalate to Tier 2 and follow SOC-SOP-AUTH-003."

### F5 — Cited answer

Headline (conclusion card): **"Our phishing procedure sets four steps for a click. None of the escalation conditions is met yet."**

| # | Sentence | Cites |
|---|---|---|
| 1 | Open an incident at P3: the user clicked, but no password entry is confirmed. | [1] [6] |
| 2 | Reset r.mehta's password and revoke active sessions within 4 hours, as a precaution. | [2] |
| 3 | Remove the email from every mailbox and block the sender. | [3] |
| 4 | Tell the user what was done and ask whether they entered a password, approved a sign-in prompt or opened an attachment. | [4] |
| 5 | Tier 1 keeps this. Escalate to Tier 2 only if a password was entered, an MFA prompt was approved, or more than 10 people clicked. | [5] |

Knowledge gap (not answered): *"How long to keep the sender blocked — SOC-SOP-PHISH-001 sets no review date."*
Still unresolved: *"Did r.mehta enter a password? The escalation decision depends on the answer."*
Assessment: `threat="Suspected"`, `asset_tier=2`, `evidence_state="attempted_misuse"` → computed **P3, SOC-POL-PRIO-01 rule 3**.

### F6 — Actionables (after the answer; one approval executes the batch)

The proposal text of each action names the SOP section it fulfils.

| id | title | tool / verb | proposal ends with | executed |
|---|---|---|---|---|
| `open_incident` | Open a {priority} incident | `itsm` / `incident` | `(SOC-SOP-PHISH-001 §3.1)` | Incident INC0048415 opened ({priority}) |
| `reset_credentials` | Ask IAM to reset the password and revoke sessions | `itsm` / `request`, `Identity & Access Management` | `(SOC-SOP-PHISH-001 §3.2)` | Request TASK0019263 raised with IAM |
| `purge_and_block` | Ask the email team to remove the message and block the sender | `itsm` / `request`, `Messaging & Email Security` | `(SOC-SOP-PHISH-001 §3.3)` | Request TASK0019264 raised with the email team |
| `email_user` | Tell the user and ask what they entered | `email` → `INCIDENT_OWNER` | `(SOC-SOP-PHISH-001 §3.4)` | Sent to r.mehta · `AWAITING_REPLY` |

Email — To `r.mehta` (mailbox `INCIDENT_OWNER`), no cc. Subject: `The email you reported — what happens next`. Body:

> Thanks for reporting the suspicious email. You're receiving this because SOC-SOP-PHISH-001 requires us to
> follow up when a reported link was clicked.
>
> What we're doing: your password is being reset and your active sessions signed out, and the email is
> being removed from every mailbox.
>
> Please reply today: did you enter your password, approve a sign-in prompt, or open an attachment after
> clicking? Either answer is fine — it tells us whether to escalate.
>
> {tickets}
>
> SOC Tier 1

Final state `OPEN — AWAITING USER REPLY`; headline *"Incident open, password reset and email removal
requested, and the user asked what they entered — as the phishing procedure requires."*; pending *"User's
reply on password entry"*; next trigger *"If the user entered a password or approved a prompt, escalate to
Tier 2 (SOC-ESC-MATRIX-01)."*; not proposed *"No Tier 2 escalation — none of the matrix conditions is met yet."*

## Rev 3 — screen redesign (frozen; supersedes F1, F4–F6 where they differ)

User direction (2026-09-29): no "§" anywhere; the answer is too elaborate — show the document's steps first,
then action items; easy screen, not full of text; a 2–3 line opening; show the document date; issue a staff
advisory for the phishing link; reference the ticket in the email; do **not** offer the scoping searches.

**Question (re-frozen — the answer names the user, so the question must):**
> r.mehta from Finance reported a phishing email and says they clicked the link. What does our phishing procedure say we should do?

**Screen after Run (single view, actions shown directly under the document — no "Show proposed response" click):**

1. Title `Phishing — user clicked a link` + priority badge (P3, computed) · Opening, 3 lines:
   *"r.mehta in Finance clicked a link in a reported phishing email. Our procedure treats this as P3 until we
   know whether a password was entered. Contain the account and the email now, warn staff, and ask r.mehta."*
2. Source line: `SOC-SOP-PHISH-001 · Phishing response procedure · v2026.3 · approved 12 Mar 2026`, then
   `Also used: SOC escalation matrix v2026.1 (20 Jan 2026) · Incident priority policy v2026.2 (4 Feb 2026)`.
3. **What the procedure says** — one line per step, grouped by phase; each ref is a chip (`3.2`) that reveals the
   one-line excerpt:
   - Contain: reset password + sign out sessions within 4 h (IAM, 3.2) · remove the email everywhere + block
     sender (Email team, 3.3) · isolate the laptop — *only if a file was downloaded or ran* (Endpoint team, 3.5)
   - Scope: find everyone who received or opened it (SOC, 4.1) · check the laptop for anything that ran after
     the click (SOC, 4.2)
   - Record and notify: open an incident at policy priority — P3 for a click (SOC Tier 1, 3.1 + Rule 3) · send
     a staff advisory: sender, subject, do not click (SOC Tier 1, 3.6) · tell the user, ask if they entered a
     password (SOC Tier 1, 3.4)
   - Escalation line: Tier 2 if a password was entered, an MFA prompt was approved, or more than 10 people
     clicked (PH-02).
4. `▸ How this was found — 11 chunks · hybrid search · top match 0.96` — collapsed; expands to the chunk panel.
5. Open question: *Did r.mehta enter a password? This decides escalation.*
6. **Action items** (all ticked): Open P3 incident (ITSM) · Password reset + sign-out (IAM request) · Remove
   email + block sender (Email team request) · **Send staff advisory** (Email → `STAFF_ADVISORY`) · Email
   r.mehta (Email). **No scoping-search action.**

**Emails:**
- Staff advisory — to `All staff` (mailbox `STAFF_ADVISORY`), subject `Security advisory: phishing email
  "Overdue invoice INV-20931"`; body: sender, subject, defanged link `hxxps://invoice-portal-verify[.]com/pay/INV-20931`,
  what to do, `SOC reference: {ticket:open_incident}`. **No ticket list and no user name** (privacy — the
  engine's default ticket block names r.mehta's reset request).
- User email — subject `[{ticket:open_incident}] The email you reported — what happens next`; body opens with
  `Reference: {ticket:open_incident}`; ticket list kept.

**Retrieval record:** 11 kept chunks (3.1–3.6, 4.1, 4.2, 5.1 not applied, PH-02, Rule 3), 10 cited; funnel
40 + 40 → 58 fused → 5 excluded → 12 reranked → 11 kept → 10 cited. Chunk labels are the refs (`3.2`, `PH-02`,
`Rule 3`) — no `[n]`, no `§`.

**Engine additions (all optional, default off — other scenarios byte-identical, re-proven by item 2's capture):**
`ScenarioSpec.propose_with_answer` (run → actions proposed in one step); `Email.include_ticket_list`
(default True); `workflow.procedure_answer` payload built from the record; `LOGICAL_TEAMS += STAFF_ADVISORY`
(address via the existing `AI_SOC_EC_EMAIL_<TEAM>` pattern; unconfigured → honest "Not sent").

- [x] **9** — Rev 3 backend: record (documents, steps, escalation, opening, refs), spec, engine options, mailbox
  - **Do:** as above; update R1 journey copy; drop "§" from every R1 string.
  - **Verify:** `pytest -q app/tests/test_ec_rag_record.py app/tests/test_r1_rag_answer.py app/tests/test_ec_cio_lifecycle_walk.py app/tests/test_ec_spec_engine.py` green, incl. new: no `§` in any R1 payload string; advisory body has no `r.mehta` and no `Tickets:`; user email names `INC0048415` after execution; no search action; run lands on `REMEDIATION_PLAN_READY`. Capture diff: only R1 changes.
  - **Depends on:** 8
  - **Evidence:** R1 slice 282 passed; capture compare: 9 scenarios SAME, only R1 CHANGED. Advisory sent with link, sender and `SOC reference: INC0048415`, no `r.mehta`, no ticket list; user email subject `[INC0048415] …`, body opens `Reference: INC0048415`; run lands on `REMEDIATION_PLAN_READY`; no `§` in any R1 turn. New `.env.example` key `AI_SOC_EC_EMAIL_STAFF_ADVISORY` added to `docs/architecture/flag_rightsizing_audit{.md,_data.json}` (keep, operator infra) after `test_every_env_example_key_in_disposition_table` caught it. Full backend: **16 failed, 7815 passed** — identical failure-name set to baseline.

- [x] **10** — Rev 3 frontend: `EcProcedureAnswer`
  - **Do:** new component (header, opening, date line, phased one-line steps with ref chips → excerpt, escalation
    line, collapsed `EcRagTrace` with `showAnswer={false}`); `EcAgentWorkflow` renders it in place of the
    conclusion card, findings table and standalone RAG panel when `procedure_answer` is present.
  - **Verify:** `npm test` (new component tests; existing EcRagTrace tests unchanged) and `npm run build` pass.
  - **Depends on:** 9
  - **Evidence:** `EcProcedureAnswer.tsx` + tests (4); `EcRagTrace` `showAnswer` prop (default true, existing tests unchanged). `npm test` 153 passed (intermittent pre-existing teardown error only); `npm run build` passes.

## Rev 4 — UX round (user feedback after the rev-3 walk)

| # | Feedback | Change |
|---|---|---|
| U1 | Same generic animation plays on submit and on Run | Root cause: neither R1 turn carried a journey, so the browser fell back to its 10-step investigation animation. R1 now gets `knowledge_request_journey` ("Processing your request", 2 stages) on the plan turn and `knowledge_retrieval_journey` ("Searching the knowledge base", 4 stages) on the run turn (`fixtures/registry.py::_knowledge_answer_animation`, RAG specs only). |
| U2 | Highlight the key message | Opening rendered as a highlighted callout (`procedure-key-message`), normal font size. |
| U3 | Step 8 must cover sensitive information | Step, 3.4/PH-02/5.1 excerpts, escalation line, open question, user email, pending/next all say "password or sensitive information". |
| U4 | Answer disappears after Approve | Procedure answer stays on screen at `COMPLETE`/`PARTIAL`. |
| U5 | Show the outcome as a table; drop the "not sent" advisory | Each step gets a status (Done / Requested / Pending / Only if needed) with View ticket / View email; the separate completion block is not shown for procedure answers. Advisory is now a **request ticket to Internal Communications** (`TASK0019265`) carrying the advisory text — no outbound mail, nothing to fail; the `STAFF_ADVISORY` mailbox, `include_ticket_list` and the `.env.example`/audit rows are reverted. |
| U6 | Summary of done vs pending | `progress_summary` (Done / Requested / Pending) + Waiting on + Next under the steps. Scoping steps (4.1, 4.2) and isolation stay Pending / Only if needed — the app does not claim them. |
| U7 | Keep it simple, not staged | "Requested" (not "done") for work handed to other teams; incident no longer claims "read back from ITSM"; animations short and plain. |

- [x] **11** — Rev 4 UX changes
  - **Verify:** `pytest -q app/tests/test_ec_rag_record.py app/tests/test_r1_rag_answer.py app/tests/test_ec_cio_lifecycle_walk.py app/tests/test_ec_spec_engine.py app/tests/test_ec_pipeline_dispatch_parity.py` green; capture compare: only R1 changes; full backend failure-name set equals baseline; `npm test` + `npm run build` pass.
  - **Depends on:** 10
  - **Evidence:** EC slices 286 passed; capture compare 9 SAME / R1 CHANGED; R1 journeys: plan `Processing your request` (2), run `Searching the knowledge base` (4), S1 unchanged; full backend **16 failed, 7819 passed**, identical failure-name set to baseline; frontend 156 passed (intermittent pre-existing teardown error only), build passes. Browser check of the after-approval screen pending the user's sign-in (pane session closed).

## Decisions

- **D1** keep `scenario_id` — content change only, zero wiring churn.
- **D2** actionables stay in the shared lifecycle (answer → "Show proposed response" → approve → closure).
- **D3** retire the old phrasing — a DB-login question must not get a phishing answer.
- **D4** plan turn keeps "Nothing runs until you approve" (engine-wide behaviour).
- **D5** legacy R1 pack (`fixtures/r1/*`, `ec_agent/profiles/r1.py`, `test_r1_rag_answer.py`) untouched —
  not imported by the live path (`profiles/__init__.py` imports only `fixtures.specs`).
- **D6 (rev 2)** reuse the existing `EcRagTrace` panel (`frontend/src/components/ec/EcRagTrace.tsx`,
  already wired in `EcAgentWorkflow.tsx`) instead of new citation UI; extend it with optional chunk/index
  fields only.
- **D7 (rev 2)** action citations live in the proposal text, not a new `Action.cites` field — no engine or
  UI change for actions.
- **D8 (rev 2)** copy never says "fictional", "synthetic" or "demo". The payload's existing EC provenance
  (tool-fabric `demo_fixture`, envelope provenance) is **kept** — it is the EC governance stamp, not UI
  copy — and nothing claims a live model call.

## Review (rev 2, against the code)

| # | Finding | Resolution |
|---|---|---|
| R1 | Conclusion card renders `narrative_points` + `sources`; `rag_trace` renders the same answer → duplicate. | When `spec.rag` is set the conclusion emits `narrative_points=[]` and `sources=[]`; headline + assessment stay; `rag_trace.answer.headline=""` and `EcRagTrace` renders the headline only when non-empty. |
| R2 | `spec.points` feeds the incident ticket description (`_ticket_record`) and `outcome.confirmed`. | R1 keeps `points` = the 5 answer sentences; `_check_spec` fails if they differ from the rag answer texts. |
| R3 | `rag_trace` is hidden at `COMPLETE` (`EcAgentWorkflow.tsx`). | Accepted — closure shows the final summary. |
| R4 | Retrieval numbers must be internally consistent or the panel reads as fake. | `_check_spec` enforces: kept chunks sorted by rerank desc; dense and BM25 ranks unique; every cite resolves; every cited chunk is `used`; no excluded document version is cited; funnel counts consistent (fused ≥ kept + excluded, reranked ≥ kept ≥ cited). |
| R5 | Other scenarios must not change. | `rag` defaults to `None`; `rag_trace` key only emitted when set; item 2 diffs all nine other scenarios. |
| R6 | Old question might still fuzzy-resolve to R1 via `resolve_ec_query_fuzzy`. | Test asserts it does not resolve to R1. |
| R7 | `EcRagTrace.test.tsx` and `ecSpecWorkflow.test.tsx` pin the legacy shape. | New fields optional; existing tests unchanged and must stay green. |

## Stop conditions

- All items checked with evidence, **or** same gate fails twice, **or** any non-R1 payload diff (item 2),
  **or** a decision contradicting F1–F6.

## Dependency order

`0 → 1 → 2 → 3 → 4 → 5 → 6 → 8 → 9 → 10 → 7` (7, the browser walk, runs last on the rev-3 screen)

## Checklist

- [x] **0** — Baseline
  - **Do:** Branch `feat/ec-r1-phishing-procedure` from `e6a14376`. Capture every scenario's `ec_agent_workflow` at each lifecycle stage to the scratchpad.
  - **Verify:** `cd backend && ../.venv/bin/python -m pytest -q app/tests/test_ec_cio_lifecycle_walk.py app/tests/test_ec_pipeline_dispatch_parity.py app/tests/test_r1_rag_answer.py` green; baseline JSON written.
  - **Depends on:** none
  - **Evidence:** Branch `feat/ec-r1-phishing-procedure` @ `e6a14376`. 188 passed (walk + dispatch parity + r1 rag). Baseline payloads captured for 10 scenarios × all stages (normalized; two captures identical). Full-suite baseline run in a clean worktree at `e6a14376`: **16 failed, 7790 passed** (pre-existing).

- [x] **1** — Engine: optional retrieval record
  - **Do:** New `app/demo/ec_agent/rag_record.py` (dataclasses `RagChunk`, `RagExclusion`, `CitedSentence`, `RagRecord`; `build_rag_trace(record)`; `check_rag_record(record, points)`). `ScenarioSpec.rag: RagRecord | None = None`. `build_workflow` emits `rag_trace` after the investigation ran, and suppresses conclusion `narrative_points`/`sources` (R1). `_check_spec` calls `check_rag_record` (R2, R4).
  - **Verify:** new `app/tests/test_ec_rag_record.py`: dangling cite raises; unsorted rerank raises; cited excluded version raises; points≠answer raises; R1 payload has 7 passages, 5 sentences, 6 distinct cited labels.
  - **Depends on:** 0
  - **Evidence:** `app/demo/ec_agent/rag_record.py` + `ScenarioSpec.rag`; `test_ec_rag_record.py` 23 passed (dangling cite, missing cite, unsorted rerank, excluded version, not-used cite, points≠answer all raise; model names equal `Settings` defaults).

- [x] **2** — Other scenarios unchanged
  - **Do:** Re-capture item-0 payloads and diff.
  - **Verify:** empty diff for S1–S7, Q1, Q2 at every stage; test asserts no `rag_trace` key for them.
  - **Depends on:** 1
  - **Evidence:** Per-scenario compare after engine change: 10/10 identical; after R1 rewrite: 9 SAME, only `r1_rag_privileged_success_after_failure` CHANGED. `test_non_rag_scenarios_emit_no_rag_trace` ×9 green.

- [x] **3** — Environment constants (F2)
  - **Do:** Add constants to `ec_environment.py`.
  - **Verify:** `grep -rn "TASK0019263\|TASK0019264" backend/app/demo --include='*.py'` → defined once each in `ec_environment.py`.
  - **Depends on:** 0
  - **Evidence:** `TASK0019263`/`TASK0019264` defined once in `ec_environment.py` (plus `PHISH_USER`, `PHISH_SENDER`, `SOP_PHISHING`).

- [x] **4** — R1 spec rewrite (F1, F3–F6)
  - **Do:** Rewrite `fixtures/specs/r1_sop_answer.py`; drop `legacy_phrasings`; no SPL.
  - **Verify:** tests: question == F1 verbatim; no R1 check/action has `spl`; priority P3 rule 3 and incident title contains `P3`; each action proposal names a section of a used chunk; old question does not fuzzy-resolve to R1 (R6).
  - **Depends on:** 1, 3
  - **Evidence:** `r1_sop_answer.py` rewritten; tests green: question verbatim, no SPL, P3 computed, every action names a used chunk's section, old question no longer resolves to R1, walk ends `OPEN — AWAITING USER REPLY`.

- [x] **5** — R1 progress journey copy
  - **Do:** Update `r1_initial()` and `R1_FOLLOW_UP_JOURNEYS` in `ec_journeys.py` to the phishing retrieval (bge-m3 + BM25, fusion, rerank, citations) and the four actions.
  - **Verify:** the R1 block contains no `privileged`, `AUTH-003`, `adm_`, `Tier 2 SOC analyst`; `pytest -q app/tests -k "ec_ or journey"` green.
  - **Depends on:** 4
  - **Evidence:** R1 journey block: forbidden-term scan returns `[]`; `pytest -k "ec_ or journey"` 455 passed, 26 skipped.

- [x] **6** — Frontend: extend `EcRagTrace` (optional fields)
  - **Do:** Types: optional `index`, `funnel`, per-passage `chunk_id`, `section`, `tokens`, `scores {dense, dense_rank, bm25, bm25_rank, rerank}`, per-exclusion `detail`. Render an index/funnel strip and a per-passage metadata line when present; render headline only if non-empty.
  - **Verify:** `cd frontend && npm test` green incl. new case (chunk id, cosine, BM25, rerank, funnel rendered; headline omitted when empty); existing `EcRagTrace.test.tsx` unchanged and green; `npm run build` passes.
  - **Depends on:** 1
  - **Evidence:** `npm test`: 149 passed (baseline with changes stashed: 148 passed); the 1–2 vitest teardown errors (`window is not defined` from `ecComposerCollapse`/`s1Workspace` tests) occur on the stashed baseline too. `npm run build` passes.

- [x] **7** — Browser walk
  - **Do:** Walk R1 plan → run → answer → proposed response → approve → closure; spot-check S1 and S4.
  - **Verify:** screenshots show cited answer + chunk panel, 4 actions with SOP sections, P3, editable email with ticket block, final `OPEN — AWAITING USER REPLY`.
  - **Depends on:** 4, 5, 6
  - **Evidence:** Walked R1 in the in-app browser (signed in by the user; 532px pane): plan → Run → procedure screen with short "SOC ANSWER" headline, 3-line opening, dated source line, 8 numbered steps in 3 phases with ref chips, escalation line, collapsed retrieval, open question, then 5 action items pending approval incl. staff advisory draft. First pass exposed the full opening duplicated as the large headline and a broken source-line wrap (user report: font too large, text not visible) — fixed (short `conclusion_headline`, short `final_headline`, inline source line) and re-walked. **Approve not clicked** in the running stack (EC email may be live-configured); closure covered by tests (`OPEN — AWAITING USER REPLY`).

- [x] **8** — Full gates
  - **Do:** `/invariant-check` on the diff; full suites.
  - **Verify:** backend full pytest — failure names diffed against item-0 master baseline (no new failures); `npm test && npm run build` green; governance regression script PASS.
  - **Depends on:** 7
  - **Evidence:** Invariant check PASS (no MCP/LLM/SPL/flag/state changes; secret-pattern hits are prose only; R1 provenance `live_llm_called/live_mcp_called/live_rag_called = False`). Backend full run: **16 failed, 7812 passed** vs baseline **16 failed, 7790 passed** — identical failure-name set; +23 new tests, −1 collected (`test_governance_trace_reports_the_validated_search_never_the_candidate[r1…]` is parametrized only over specs with SPL; R1 now has none). Frontend 149 passed, build OK. Governance script run on branch and on clean `e6a14376` with the full-pytest step skipped (compared above) and exit-on-fail disabled: outputs identical except timings — the same three gates fail on both (crosswalk stale, sentinel 14/17, golden Tier 0); all other gates (harness, parity, Cisco 50/0/0, dispatch matrix 5/5, OT probes 6/6, answer quality 17/17) pass on both.

## Commit conditions

Feature branch only. No push/merge until the user has reviewed item 7.

## Verification gaps (flag before coding)

_None._

## Drift log

- rev 2 (2026-09-29): user asked for no "fictional" wording and a retrieval that reads like real chunked
  RAG with embeddings. Added F4 retrieval record, D6–D8, review table; removed `Action.cites` and the
  conclusion-level citation fields from rev 1 (superseded by reusing `EcRagTrace`).
- impl (2026-09-29): `test_r1_rag_answer.py::test_rag_trace_only_after_the_plan_is_approved` asserted the
  conclusion's `sources` line, which R1 no longer uses (R1). Retargeted to `rag_trace` (passages present,
  every sentence cited) and strengthened (plan turn must carry no `rag_trace`); `live_rag_called is False`
  kept. `test_ec_cio_lifecycle_walk.py::_analyst_visible_text` extended to scan RAG-panel text against the
  `DEMO_WORDS` realism bar, since R1's answer moved out of `narrative_points`.
- impl (2026-09-29): CLAUDE.md baselines are stale for this master — backend 16 pre-existing failures,
  frontend 148 tests, governance script fails at `soc capability crosswalk stale` on unmodified `e6a14376`.
  Item 8 therefore compares against the measured baseline, not the documented one.
- rev 3 walk (2026-09-29): the spec's `conclusion_headline` doubles as the turn's large "SOC ANSWER" title; setting it
  to the 3-line opening duplicated the opening in a large font. Headline is now a short line; the opening lives only
  in the procedure card. `test_ec_cio_lifecycle_walk` gained `_findings_turn` (the answer turn is the run turn when a
  scenario proposes actions with the answer); other scenarios resolve to the same turn as before.
