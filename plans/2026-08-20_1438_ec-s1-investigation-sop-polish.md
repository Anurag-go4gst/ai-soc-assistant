---
name: ec-s1-investigation-sop-polish
overview: "Polish Experience Center S1: deepen allowed-session investigation, add EC-only RAG SOP, Yes/Not-now remediation checkpoint, honest IOC/TI/LLM wording. EC/demo only."
status: done
date: 2026-08-20
canonical_plan: plans/2026-08-20_1438_ec-s1-investigation-sop-polish.md
---

# S1 investigation + SOP polish (Experience Center only)

## Objective

S1 (`s1_governed_splunk_investigation`) already runs Plan → Investigate → Conclude → Remediation. Polish it so: (1) three allowed sessions on `10.20.1.10` are investigated automatically as an **Added by agent** read-only step; (2) an EC-only SOC-KB SOP fixture drives monitoring vs conditional block; (3) remediation is created only after **Yes, create remediation plan**; (4) wording is precise (unlisted ≠ benign, no-fire ≠ safe, MCP identity only after inventory evidence, LLM ≠ evidence). Production `/chat` and `architecture.md` stay frozen.

Done when: first turn title is `Newly observed IP 198.51.100.42 — malicious use not confirmed`; investigation answers the four inference questions; allowed sessions are not buried under 922 denies; SOP RAG is cited; `create_remediation_plan` is a user Yes; block is not auto-executed because SOP threshold is not met; `live_llm_called` / `live_mcp_called` stay false.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- EC fixtures stay `coe_synthetic_fixture`. No live LLM/MCP. No VirusTotal/IPVoid.
- Candidate SPL stays `execution_eligible=false`. LLM-shaped SPL (fixture) must pass `validate_spl` and never claim deployment.
- Firewall block stays HIL; do not auto-execute it when SOP blocking threshold is not met.
- No production `/chat` or `architecture.md` edits.

## User directives

- Keep Investigate → inference → ask Yes/Not now → execute approved plan → verify → result.
- Do not create or execute remediation before Yes.
- Auth for the 3 allows is materially necessary and available via Splunk — not an optional leftover.
- EDR remains optional/off (no EDR MCP onboarded). Do not invent tools.

## Dependency order

`1 → 2 → 3 → 4 → 5 → 6 → 7`

## Checklist

- [x] **1** — EC-only SOP RAG fixture
  - **Do:** Add `backend/app/demo/fixtures/s1/sop_rag.py` — enterprise SOC SOP for newly observed external / MCP endpoint monitoring and blocking (investigation requirements, monitoring criteria/duration, escalation, when monitoring-alone is enough, block conditions, HIL/Network approval, change/incident, verify, rollback, post-action monitoring). Surface as SourceEvidence via `retrieve_soc_kb`. Not vendor guidance.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.fixtures.s1.sop_rag import SOP_TITLE, sop_source_evidence; assert 'Monitoring and Blocking SOP' in SOP_TITLE; ev=sop_source_evidence(); assert ev['tool_name']=='retrieve_soc_kb'; assert 'vendor' not in (ev.get('source_name') or '').lower(); rows=ev['preview_rows']; assert rows and any('monitoring duration' in str(r).lower() or 'duration' in str(r).lower() for r in rows)"`
  - **Depends on:** none
  - **Evidence:** `python3 -c` SOP fixture assert → `item1 OK`. Title `Newly Observed External / MCP Endpoint Monitoring and Blocking SOP`; `tool_name=retrieve_soc_kb`; preview rows include Monitoring duration (14 days).

- [x] **2** — Investigation steps + adaptation
  - **Do:** Update `agent_config.py`: retrieve SOP (SOC-KB); do not pre-claim MCP identity in opening; keep notable + 30d + novelty; local TI wording; remove auth as optional leftover; add `ADAPTATION_STEP` permitted communication/auth (`added_by_agent`, reason cites 3 allowed / 922 denied). Handler appends and applies `investigate_permitted_sessions` + `check_successful_auth` after the firewall search.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.fixtures.s1.agent_config import OPENING_NARRATIVE, INVESTIGATION_STEP_DEFS, ADAPTATION_STEP; n=OPENING_NARRATIVE.lower(); assert 'newly registered mcp' not in n; assert any(s['id']=='retrieve_sop' and s.get('default_selected') for s in INVESTIGATION_STEP_DEFS); assert ADAPTATION_STEP.get('added_by_agent') is True; assert '3 allowed' in ADAPTATION_STEP['reason']"`
  - **Depends on:** 1
  - **Evidence:** `python3 -c` config assert → `item2 OK`. Opening does not pre-claim MCP; `retrieve_sop` default-selected; adaptation reason cites `3 allowed`.

- [x] **3** — Findings, identity promotion, four-question inference
  - **Do:** Update findings/state/pack evidence: notable = IP not in IOC lookup/content used by existing notable (not-fire ≠ benign); TI = not present in local IOC/TI (unlisted ≠ benign); MCP identity only after `ev-s1-mcp-identity`; PLAN_READY title `Newly observed IP 198.51.100.42 — malicious use not confirmed`; conclusion answers what happened / malicious confirmed? / why notable did not fire / SOP next. Allowed-session findings include dest identity, port/service, timestamps, allow vs deny, auth not attributable, expected-for-MCP uncertain, no confirmed follow-on.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py -q`
  - **Depends on:** 2
  - **Evidence:** `pytest app/tests/test_s1_agent_workflow.py` — 5 passed (included in later `25 passed` with governed + isolation). Plan-ready title matches; investigation adds `permitted_sessions` + SOP + four-question conclusion; `live_llm_called` is false.

- [x] **4** — LLM advisory fixture (not evidence)
  - **Do:** Add EC-only advisory interpretation + candidate monitoring SPL. Label `LLM interpretation — not evidence`. Pipeline: LLM candidate → `validate_spl` → normalized SPL → not deployed. `live_llm_called` stays false. No invented tools.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.fixtures.s1.llm_advisory import candidate_monitoring_spl, advisory_label; from app.safeguards.spl_validator import validate_spl; from app.demo.fixtures.s1.pack import _firewall_template_profile; r=validate_spl(candidate_monitoring_spl(), template_profile=_firewall_template_profile()); assert r.get('approved') is True; assert r.get('execution_eligible') is False; assert 'not evidence' in advisory_label().lower()"`
  - **Depends on:** 3
  - **Evidence:** `python3 -c` → `item4 OK True False`. Candidate SPL `approved=True`, `execution_eligible=False`; advisory label contains `not evidence`.

- [x] **5** — Remediation offer + SOP-derived plan
  - **Do:** INVESTIGATION_COMPLETE emits `remediation_offer` Yes/Not now (`create_remediation_plan` / `decline_remediation_plan`). Do not mint remediation actions before Yes. After Yes, plan includes targeted monitoring, prepared (not deployed) detection candidate, incident, monitor affected hosts, conditional block + Network HIL, residual monitoring, incident update. Auto-execute must not execute `firewall_block` because SOP threshold is not met. Each rem step carries plan → execution status → result → verification.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py app/tests/test_s1_governed_splunk_investigation.py -q`
  - **Depends on:** 4
  - **Evidence:** Combined with item 3/7: `pytest` agent + governed + isolation → `25 passed`. Decline keeps `notify` unminted; after Yes+run, `firewall_block` stays `PREPARED`/`APPROVAL_REQUIRED`; chip-path HIL still waits at prepare.

- [x] **6** — Frontend: Yes/Not now + rem execution columns
  - **Do:** `EcAgentWorkflow` renders `remediation_offer` (Yes / Not now) instead of a single continue CTA when present. Remediation rows can show execution_status / actual_result / verification from finding.details. Generic agent contract — no S1 denylist.
  - **Verify:** `cd frontend && npm test -- src/components/ec/s1Workspace.test.tsx src/components/ec/flagshipWorkspace.test.tsx --reporter=dot`
  - **Depends on:** 5
  - **Evidence:** `npm test -- src/components/ec/s1Workspace.test.tsx src/components/ec/flagshipWorkspace.test.tsx --reporter=dot` → `Test Files 2 passed (2) / Tests 24 passed`. Covers Yes/Not now, ADDED BY AGENT reason, rem PLAN STEP/STATUS/RESULT/VERIFICATION.

- [x] **7** — Isolation + existing S1 chip path
  - **Do:** Chip-path HIL still works; pack does not import production chat/MCP; git diff excludes `architecture.md` and `backend/app/chat/`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py app/tests/test_s1_governed_splunk_investigation.py app/tests/test_ec_isolation.py -q`; `git diff --name-only` must not include `architecture.md` or `backend/app/chat/`
  - **Depends on:** 6
  - **Evidence:** `pytest … -q` → `25 passed`. `git diff --name-only` has no `architecture.md` or `backend/app/chat/`. Chip-path follow-ups (`test_s1_every_follow_up_advances_state_and_updates_evidence`, firewall HIL) remain green.

## Verification gaps

None — every item has a concrete Verify command.

## Drift log

- 2026-08-20: Prior S1 agent plan used a plan-shaped first-turn title that avoided “not confirmed”. This polish follows the user’s requested title `Newly observed IP … — malicious use not confirmed`, then promotes MCP identity after inventory evidence.
- EC LLM participation is a **fixture advisory** (`live_llm_called=false`), demonstrating the governed candidate→validate→evidence chain without calling a live model.
