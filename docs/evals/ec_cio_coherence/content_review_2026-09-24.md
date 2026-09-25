# EC questions 1–9 — content review (plans, inference, remediation, emails, SPL)

**Date:** 2026-09-24 · **Tree:** `master @ 37010815` · **Method:** in-process walk of
`run_experience_center_turn` for each catalog entry. Agent scenarios used **default step
selections** (plan → HIL if prompted → remediation plan → approve). Legacy scenarios followed
every chip in order. Raw dump: session scratchpad `ec_dump.json` (not committed).

**Correction to the first review pass:** my first harness selected *every* plan step, including
optional ones. That forced S7 onto Path B and skipped S4's Agilus HIL. With default selections,
**S7 concludes correctly** ("device active, CMDB stale → real concern") and **S4 does stop for
Agilus approval**. Neither finding is carried forward.

Verdict legend: **KEEP** = logical as-is · **FIX** = keep the step but change it · **ADD** = missing step · **REMOVE/MERGE** = redundant or illogical.

---

## Cross-cutting findings (apply to all questions)

| # | Finding | Why a CIO/CISO notices | Fix |
|---|---------|------------------------|-----|
| X1 | **Plan steps state *what*, never *why*.** No step says which decision it informs. Remediation steps have no "risk if skipped" and no "reversible?" | The core ask is "is this plan justified?", and nothing on screen answers it | Add `rationale`, `decides`, `if_skipped` per investigation step. Add `rationale`, `reversible`, `approver`, `risk_if_skipped` per remediation step. Render them as one line under each step |
| X2 | **Engineering notes leak into analyst text.** Examples: "No EDR MCP is onboarded — do not invent an EDR connector", "There is no CMDB MCP — this is a simulated inventory lookup", "Candidate SPL stays non-executable", brief item "No live MCP, live LLM… on this path" | It reads as a disclaimer rather than a product | Move governance notes to the transparency drawer. The tool catalog carries `demo_fixture=true` once per page |
| X3 | **Opening narratives are boilerplate.** "…you can follow these steps using Splunk and MCP Tools and RAG Guidelines"; "This investigation would typically involve…"; "Here's a step-by-step guide…" | Sounds like a generic LLM, not an agent that has a plan | Agent voice in 2 lines: "My plan: 6 steps across Splunk, CMDB and OT inventory. Goal: decide incident vs data-quality. Nothing runs until you approve." |
| X4 | **Email template defects (all 11 drafts).** (a) The same robotic opener in every draft. (b) The footer "Firewall containment must be executed through SOAR" appears on AppSec, IAM, OT and incident-owner emails. (c) The signature says "Experience Center (governed demonstration — not a live production ticket…)". (d) **TICKET STATUS is stale or wrong**: "No incident ticket opened in this session yet" appears after the plan already created INC-2026-89412 (S1) and INC-48219 (S4). (e) Internal words appear: "Scenario: S1", "fixture replay", "simulated cisco.upgrade", "EC hardening policy", "ZD-FIXTURE-…", "(if checked)", "scenario condition — not an operational error". (f) No deadline or SLA except the IAM email. No CC to the SOC lead on block/approval mails | Emails are the most "real" artefact a CIO reads. These errors are visible in 5 seconds | One email composer: BLUF first 3 lines (ask + deadline + severity); subject `[P#][INC-id] <action> — <asset>`; ticket block bound to lifecycle state; role-specific footer; evidence list with IDs; no demo words (lint test) |
| X5 | **Incident IDs don't reconcile.** The same thread produces FW-INC-2026-0615, INC-S3-10042, INC-2026-89412, and a change ticket labelled "Incident ticket OPEN (CHG-R17-15)" | Breaks trust in the "system of record" story | One ID per thread (see storyline). Incident ≠ change is enforced in the composer |
| X6 | **Legacy answers never evolve.** S3, S5, S6 and Q1 repeat the *identical* summary sentence on every chip turn (13× in S3) while only the action list grows | The CIO sees nothing learned from each step | Solved by lifecycle adoption (Release B). Until then, each chip must append a finding line |
| X7 | **Same IP, three verdicts.** S1 = new, MEDIUM, not malicious, "prior 30-day window empty". S3 = "confirmed malicious scanning", first seen **2026-06-18**, P2. Q1 = "~5,200 denies in 1 h + account breach", P1 | The first contradiction a CIO clicks into | Storyline thread (plan item B-4) |

---

## Q1 (S1) — "New IP 198.51.100.42 — malicious over 30 days? SOP to monitor/block"

**Investigation plan — overall GOOD.** It asks the right questions in the right order: who → what did it do → novel? → known bad? → would detections catch it → SOP.

| Step | Verdict | Reason |
|---|---|---|
| Identify IP role (SOC-KB) | **FIX** | The finding "registered MCP endpoint" is jargon for an *external* IP. Say "Registered third-party integration endpoint (partner API/MCP) — owner: <team>", then add a rationale: an owned endpoint changes the question from "attacker?" to "is this expected business traffic?" |
| 30-day network activity | KEEP | The core evidence; the SPL is correct (see below) |
| Novelty (prior 30 d) | KEEP | Justifies "newly observed" |
| Local TI | KEEP | Honest "unlisted ≠ benign" |
| Existing detection coverage | KEEP | Strong CIO point: the IOC detection is blind to new IPs |
| SOP retrieval | KEEP | Drives the remediation |
| Agent-added: permitted sessions + auth | KEEP | The best moment in the demo (the agent adapts the plan). Label it clearly as "added because 3 allows were found" |
| Optional IAM / EDR / ITSM | FIX | The text is internal ("No EDR MCP is onboarded — do not invent…"). Rewrite as "Optional — adds certainty on X; not required for SOP decision" |

**Inference — mostly sound.** MEDIUM, "not confirmed", block threshold not met: consistent with the evidence.
**Gap:** nothing in the plan tries to *resolve* the 3 unexplained permitted sessions, which is the only open question.

**Remediation plan — logical, but padded, and one step is missing.**

| Step | Verdict | Reason |
|---|---|---|
| Generate / Validate / Run baseline / Verify results / Monitor (5 steps) | **MERGE → 2** | These are four views of one query. Replace them with (1) "Create 14-day watch (scheduled saved search) — definition + validation" and (2) "Backtest the watch over last 14 d (3 sessions)". Today "monitoring" is a one-off `-14d` lookback, which is not monitoring |
| Create incident | KEEP | Incident as a record of unexplained permits: justified |
| Notify SOC team | **FIX** | The label says SOC, but the email goes **TO=FIREWALL_TEAM** and the result says "SOC team notified · FIREWALL_TEAM". Send to SOC and CC the Firewall team because of the exception question |
| Conditional IP block → NOT_REQUIRED | KEEP | Showing a *declined* action with its reason is good governance |
| Update incident | KEEP | |
| **ADD:** Ask the integration owner to confirm the 3 sessions (email, HIL) | **ADD** | This is the only step that closes the open question. It becomes the trigger for escalation in the storyline (Day 1) |

**Email (to firewall team):** the ticket status says "No incident ticket opened" but INC-2026-89412 was created earlier. "Scenario: S1…" is a demo leak. The CONFIRMED list includes "Governed Splunk searches completed and validated", which is a process claim, not a finding.

**SPL:** all correct and scoped (index/sourcetype/time/`head`).
- The auth query deliberately does not filter by source IP and returns `values(src)` to test attribution. That is correct; **say so in the rationale**.
- The monitoring SPL must become a saved-search definition: `earliest=-15m@m latest=@m … action=allow | stats … | where allow_count>0`, cron `*/15 * * * *`, throttle 1 h, 14-day expiry.

---

## Q2 (S2) — "Customer AI assistant targeted by prompt injection?"

**Investigation plan — GOOD, 8 steps.** It answers 3 clear questions (attempted? executed? data touched?).

| Step | Verdict | Reason |
|---|---|---|
| Replay existing detection first | KEEP | Right instinct (reuse before build) |
| Gateway/guardrail, tool-call attempts, DLP, broader tool history, session, restricted-data audit | KEEP | Each maps to one of the 3 questions. Add the `decides` field to show the mapping |
| AI security policy (SOC-KB) | KEEP | This is a RAG step. Show the citation |

**Inference — sound.** "Attempted, blocked, breach not confirmed." Gap: the conclusion never says **who** (user/session/source) attempted it, and a CIO asks "is it one actor or a campaign?". **ADD** an actor/session attribution line (fixture).
**Executive summary is empty** at every phase.

**Remediation plan — needs reasons, and two key steps are missing.**

| Step | Verdict | Reason |
|---|---|---|
| Create AI security incident | KEEP | |
| Disable integration credential | **FIX (justify)** | The tool call was *blocked* and credential compromise is unconfirmed, so a hard disable needs a stated reason. Re-frame as "Rotate + scope-down export connector credential (precautionary, reversible, 15 min)" with the rationale "the attacker reached the tool-authorization layer; this connector can export customer records" |
| Email AppSec | FIX | See the email notes below |
| Verify credential state | KEEP | |
| Update incident / closure | KEEP | |
| **ADD:** Block/rate-limit the offending session or user at the AI gateway | **ADD** | The obvious containment is missing |
| **ADD:** Close the detection gap: extend the prompt-injection detection (coverage is "partial") | **ADD** | Investigation step 1 found partial coverage; remediation must act on it |

**Email (AppSec):** it says "Closure / executive summary prepared for reference AI-SEC-8841", but the email is step 3 of 6 and the incident step shows no ID. The firewall-SOAR footer is irrelevant here.

**SPL:** `sourcetype=pgcil:edr … tool_name=export_customer_records` is the **wrong source**: tool-call events come from the AI gateway, not EDR. Use `pgcil:ai_gateway` (Env-KB slot). Only 1 of 7 Splunk steps shows its SPL; show one per step.

---

## Q3 (S3) — "Malicious 198.51.100.42 confirmed — follow firewall-block process"

**No plan; 13 chips.** The order that is offered is illogical:

| Current chip order problem | Correct order (proposed remediation plan) |
|---|---|
| "Send request" and "Request IP block" are offered before SOC-lead approval | 1 Retrieve firewall-block SOP → 2 Prepare mandatory-field request → **3 SOC-lead approval (HIL)** → 4 Send to firewall team → 5 Ingest reply (vendor whitelist found) → **6 Confirm exception owner + expiry** → 7 Decision: remove exception + block (HIL, 30 d, rollback defined) → **8 Verify: post-change SPL shows denies, zero allows** → 9 Update incident → 10 Closure |
| "Remove vendor whitelist" is offered before the exception owner confirms | Step 6 must precede step 7 (removing a business exception without its owner is an outage risk) |
| SOC-lead email *asks for approval after* the block was requested | Approval is step 3 |

**Inference:** "Confirmed malicious scanning", first seen 2026-06-18, contradicts S1 ("prior 30 d empty"). The storyline fixes this: S3 is Day 2, after Q1's escalation.
**Emails (3):** good mandatory-field structure (keep it), but the three emails cite three different ticket states and IDs. The block request has no CC to the SOC lead.
**SPL:** none shown. **ADD** the post-block verification SPL (step 8); it is the only objective proof the block worked.

---

## Q4 (S4) — "Zero-day on VPN gateways, no detection/playbook"

**Investigation plan — STRONG (the reference).** It covers inventory → versions → hunt → detections → playbooks → IR guidance → Agilus HIL.
- KEEP all. The agent superseding one step is a good adaptive moment.
- The Agilus HIL wording is good: "Connect Agilus MCP — cross-reference builds vs vendor emergency catalog".

**Inference — sound** ("4 vulnerable, 2 need compromise review, not confirmed", confidence 82). Executive summary is empty.

**Remediation plan — the biggest logic gap in the set.**

| Step | Verdict | Reason |
|---|---|---|
| Restrict WAN management (email to network ops) | KEEP | Correct compensating control; the email explains why |
| Step-up MFA via IAM | KEEP | Realistic SLA stated |
| P1 incident, emergency change, Agilus patch submit | KEEP | Order is right (the change ticket gates the patch) |
| Temporary Splunk monitoring candidate → "prepared" | FIX | The final summary says **"Temporary Splunk monitoring enabled"**: a contradiction |
| Notify owners | KEEP | |
| **ADD:** Compromise assessment on VPN-GW-01/02 (collect logs + config snapshot *before* patch/reboot) | **ADD** | The investigation said "2 require deeper compromise review", and remediation never does it. Patching first destroys volatile evidence |
| **ADD:** Rotate admin credentials / revoke sessions on GW-01/02 | **ADD** | Standard for anomalous privileged management activity |
| Final headline "Exposure contained" | **FIX** | Patch and MFA are still in progress: use "Exposure reduced · patch pending · 2 gateways under review" |

**Emails (3):** content is the best in the set (WHY / SCOPE / SLA). Fix "ZD-FIXTURE-VPN-2026-001" (use a realistic advisory ID), the "(scenario condition — not an operational error)" line, and email 3's "No incident ticket opened" (INC-48219 exists).

**SPL:** the management-session hunt is reasonable. **FIX:** add `| where NOT cidrmatch("10.0.0.0/8",src)` (external sources only), aggregate `by src, dest` and not `by uri action`, and show the second SPL for the privileged-management correlation step.

---

## Q5 (S5) — "Breach on Cisco R-17 — does hardening policy require remediation?"

**No plan; chips.** The answer asserts a "breach condition" but **never shows the breach evidence**.

**Remediation logic is wrong for a *compromised* device.** Upgrading firmware on a breached router does not remove an attacker; it removes evidence. The correct plan:

1. Show the breach evidence (unknown admin login / config change / ACL change on R-17).
2. **Restrict management access** (ACL to management VRF).
3. **Capture forensic state** (`show tech`, running-config, and a config diff vs golden) *before* any change.
4. Rotate device credentials/keys.
5. Agilus: verify upgrade eligibility and image hash for v15 (Agilus becomes the patch MCP here, coherent with S4).
6. Change ticket + network approval (HIL).
7. Upgrade 14→15 via Agilus.
8. Verify: version = 15 **and** config integrity vs golden.
9. Update incident.

**Email (network approval):** "fixture replay", "EC hardening policy", "simulated cisco.upgrade" are demo leaks. A change ticket CHG-R17-15 is labelled "Incident ticket OPEN".
**SPL:** none. **ADD** the R-17 admin-login/config-change SPL that proves the "breach condition".

---

## Q6 (S6) — "Failed privileged VPN logins from Germany yesterday"

**No plan; the first answer is one sentence** with no counts, accounts or verdict.
**The missing key question:** did any **success** follow the failures? That is what a CIO asks first, and it is not asked.

**Proposed plan:**
1. Failures by account/source/geo (counts).
2. **Success after failure** from the same sources (the verdict driver).
3. MFA outcome on those attempts.
4. Scope pivots as *plan revisions*: service accounts → build servers.
5. Historical match to INC-VPN-0712.

**Remediation:**
- If there were no successes: conditional-access block for the DE geo on privileged VPN plus a watch. Disable accounts is NOT_RECOMMENDED, and the plan must say so and why: failures only, MFA held.
- Update or reopen INC-VPN-0712 and email the owner.

**Email:** says the scope is service accounts / svc_deploy, but the on-screen answer still says "service accounts out of scope". It is stale against the conversation.
**SPL:** none. **ADD** the failure summary and success-after-failure SPL; the governed template `auth_success_after_failure` already exists.

---

## Q7 (S7) — "Splunk shows OT access; CMDB says retired"

**Investigation plan — GOOD.** It reconciles two sources with three independent checks (OT inventory, firewall, ARP/MAC).
**Depth gap:** it never identifies **who** accessed the device (source IP/user/engineering workstation). **ADD** that step; for a live OT device it is the most important question.

**Inference — correct on default path A** ("active device, stale CMDB, real concern"). Executive summary is empty.

**Remediation:**

| Step | Verdict | Reason |
|---|---|---|
| Ask OT team / ingest reply | **MOVE** to investigation | The conclusion already says "real concern"; OT confirmation is evidence, not remediation |
| Create security incident | KEEP | Now justified |
| CMDB data-quality ticket | KEEP | |
| **ADD:** Restrict the east-west allow to 10.80.4.14 (OT-safe change, HIL, OT-engineer approval) | **ADD** | Unauthorized access to a live RTU with an open allow path is left open |
| **ADD:** Check RTU logic/config integrity vs baseline | **ADD** | Standard OT response; a CIO in a power utility will expect it |

**Email (OT team):**
- It still says "Disposition: unresolved conflict — do not force incident", which contradicts the conclusion.
- "(if checked)" is a template placeholder leak.
- "Incident ticket OPEN (reference pending…)" is a confusing ticket status.

**SPL:** none shown for 2 Splunk steps. **ADD** them.

---

## Q8 (Q1 lab) — "5,000+ firewall blocks in last hour + breach on internal server account"

**Inference errors:**
- **MITRE T1110.001 Password Guessing is mapped from firewall denies.** Firewall denies show **scanning**, not password guessing: map T1595 Active Scanning / T1046 Network Service Discovery. Keep T1078 Valid Accounts as "requires validation".
- "Successful internal account use" is asserted without an auth query.

**SPL defects:**
- The only SPL is `earliest=-24h … action=deny | where deny_count>=50`, yet the claim is about the **last hour**, and the claim's core (3 allows + `svc_jump_ops` success) has **no SPL at all**.
- **ADD:** a 1 h deny summary, allow-after-deny correlation on 10.20.1.10, and the `svc_jump_ops` auth success with `values(src)` (same shape as S1, so the story connects).

**Flow defects:**
- `ticket_create` is pre-staged on turn 0.
- The 3 chips never change.
- The recommended "isolate jump host + disable svc_jump_ops" is a P1 action with no approval gate or reason shown.

---

## Q9 (Q2 lab) — "Standard firewall baseline SPL template"

**The answer is adequate** for an SPL ask: governed template, Env-KB slots resolved, analyst checklist.

**SPL review:**
- `bucket span=1h | stats … by _time, src | stats avg/stdev by src` **ignores hours with zero events**. That biases the baseline upward for bursty sources. Use `timechart span=1h limit=0 count(eval(action="deny")) by src | untable …` or `makecontinuous`, or document the caveat in the checklist.
- `event_count` is computed and never used.
- `| head 100` without `sort` truncates arbitrarily. Add `| sort - avg_deny`, or drop `head` for a baseline.
- Consider `| where hours_observed>=24` so sparse sources don't get meaningless bounds.

**Flow:** a single chip that loops. **Recommendation (light lifecycle):** plan (resolve slots → render → validate) → outcome (SPL + validation) → offer "Request saved-search deployment" (prepared, not deployed).

---

## NEW — RAG question (proposed R1)

**Candidate:** existing lab entry `cert_in_ot_reporting_obligation`, "For a suspected OT incident, what does CERT-In require us to report within 6 hours?"
- Today it is `knowledge_recall` with one source labelled "SOC KB fixture", no retrieval view and no next step.
- It is the best RAG demo in the catalog: regulatory, time-boxed, CIO-relevant, and it connects to S7 (OT incident).

**Proposed journey:**
1. **Plan:** rewrite query → retrieve from SOC-KB (CERT-In Directions 2022 + internal OT IR SOP) → rerank → grounding check → answer with citations. Approve.
2. **Outcome — "How RAG answered this" panel:**
   - Query rewrite.
   - Top-k chunks with source doc, section and score.
   - Which chunks were used vs discarded.
   - A sentence-level citation on every claim.
   - An explicit "not in KB → not answered" line (e.g. sector-specific CEA obligations if the KB lacks them).
   - The answer itself: the 6-hour clock from *noticing*, the reportable categories that cover OT/SCADA, the minimum fields, the log-retention obligation, and who files.
3. **Remediation (2 steps, one approval):**
   - **Create incident flagged "CERT-In reportable"** with the 6-hour clock start time and deadline.
   - **Email the CISO + Legal/Compliance** with a pre-filled CERT-In report draft for review (the draft is shown and editable; send is HIL).
4. **Email review points for the new draft:**
   - BLUF with the deadline timestamp.
   - Fields mapped to the CERT-In form.
   - Unknowns marked as unknown.
   - Citations to the KB sections.
   - No demo words.

**Content caution:** the CERT-In facts must come from the actual KB document chunk (captured fixture from the governed SOC-KB retrieval), not be authored freehand. EC stays deterministic; the capture is replayed.
