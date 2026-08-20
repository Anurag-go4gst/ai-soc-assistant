---
name: ec-s1-connected-remediation
overview: "S1 rem flow as a connected AI SOC: one monitoring chain, operational states, View SPL, request/response, auto executive summary. EC/demo only."
status: done
date: 2026-08-20
canonical_plan: plans/2026-08-20_2130_ec-s1-connected-remediation.md
---

# S1 connected remediation polish (Experience Center only)

## Objective

After Approve remediation, S1 feels like a connected SOC: generated SPL, deployed Splunk monitoring, created the incident, sent notification, verified results, kept request/response evidence, and correctly did **not** block because the SOP threshold was not met. Production `/chat` and `architecture.md` stay frozen.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- EC fixtures stay `coe_synthetic_fixture`. No live LLM/MCP. `live_llm_called` / `live_mcp_called` false.
- Candidate SPL `execution_eligible=false`. LLM output is not evidence.
- Firewall block is **NOT_REQUIRED** at current SOP threshold — do not execute it.
- Risk stays **MEDIUM**; monitoring does not reduce it to LOW.
- No production `/chat` or `architecture.md` edits.
- Primary UX must not say draft / simulated / demo / prepared for successful connected actions.

## Dependency order

`1 → 2 → 3 → 4`

## Checklist

- [x] **1** — Coherent rem steps + operational states
  - **Do:** Replace duplicate monitoring steps with generate SPL → validate → deploy → verify active → 14-day monitor (198.51.100.42, 10.20.1.10, 443/8443, svc_jump_ops). Incident CREATED, SOC notified SENT, block NOT_REQUIRED, incident updated APPLIED. After Approve, execute ITSM/email/notify; never execute firewall_block. Primary headlines use operational copy (no draft/simulated/prepared).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py -q --tb=short`
  - **Depends on:** none
  - **Evidence:** `pytest app/tests/test_s1_agent_workflow.py app/tests/test_s1_governed_splunk_investigation.py app/tests/test_ec_email_drafts.py app/tests/test_ec_email_transport.py -q` → **35 passed**. Rem ids are generate_spl/validate_spl/deploy_monitoring/verify_monitoring/monitor_14d/create_incident/notify_firewall/prepare_block/update_ticket. After Approve: notify/ticket_create/ticket_update/email_send EXECUTED; firewall_block PREPARED/APPROVAL_REQUIRED; statuses ACTIVE/CREATED/SENT/NOT_REQUIRED/DEPLOYED.

- [x] **2** — View SPL + request/response
  - **Do:** Attach existing normalized SPL (investigation 30d/novelty/permits/auth + monitoring query) and connector request/response on Splunk, ITSM, email, SOAR, RAG steps. Frontend: View SPL › and View request / response › in expanded finding. Do not invent generic SPL.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py -q --tb=short`; `cd frontend && npm test -- --run src/components/ec/s1Workspace.test.tsx`
  - **Depends on:** 1
  - **Evidence:** Backend asserts `requested_30d` and `generate_spl` carry `index=pgcil_soc` normalized SPL plus request/response. Frontend `s1Workspace.test.tsx` (16 passed) covers View SPL ›, Normalized SPL, View request / response ›, and NOT_REQUIRED (no PREPARED grid).

- [x] **3** — Executive summary + RESPONSE COMPLETE + MEDIUM risk
  - **Do:** Auto-populate executive summary after investigation (no extra chip required). After rem: concise RESPONSE COMPLETE; risk MEDIUM; monitoring ACTIVE; blocking CONDITIONAL / NOT_REQUIRED. Hide empty sections.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py -q --tb=short`
  - **Depends on:** 1
  - **Evidence:** After `run_investigation`, `workflow.executive_summary` is non-empty with MEDIUM and no `generate_executive_summary` chip. After rem, `final_summary.title == "RESPONSE COMPLETE"`, `risk_from`/`risk_to` MEDIUM. Frontend renders Executive summary after investigation and RESPONSE COMPLETE without MEDIUM→LOW.

- [x] **4** — Isolation + frontend publish
  - **Do:** Keep changes in `backend/app/demo/` and `frontend/src/components/ec/` (+ `lib/ecAgentWorkflow.ts` if needed). Rebuild `frontend/dist`.
  - **Verify:** `git diff --name-only`; `cd frontend && npm run build`
  - **Depends on:** 2, 3
  - **Evidence:** This workstream stayed in `backend/app/demo/` (incl. EC-only `ec_actions.py`), `frontend/src/components/ec/`, `frontend/src/lib/ecAgentWorkflow.ts`, S1 tests, and `plans/`. No `architecture.md` or production `/chat` edits. `npm run build` → `tsc && vite build` OK; `dist/assets/index-D8EZnlag.js`; postbuild chmod ran.

## Verification gaps

None.

## Drift log

_Prior turn made email/ticket HIL drafts. This plan supersedes that for S1 rem **after Approve**: Approve is the batch HIL; connected actions then execute. Chip-path S1 still prepares tickets/email until Send/Confirm (`test_s1_governed_splunk_investigation.py`)._
