---
name: ec-s7-agent-framework
overview: "Convert Experience Center S7 (Splunk OT unauthorized access vs retired CMDB) onto the reusable EC agent workflow used by S4/S2. EC/demo only; architecture.md and live /chat frozen."
status: done
date: 2026-08-19
canonical_plan: plans/2026-08-19_1836_ec-s7-agent-framework.md
---

# Convert S7 onto the EC agent framework

## Objective

S7 (`s7_conflicting_ot_evidence`) answers:

> Splunk shows unauthorized access to an OT device, but the asset system says the device was retired. Determine whether this is a real incident.

Today that journey is chip-driven with Path A (device active, CMDB stale) and Path B (recycled identity). Convert it to the S4/S2 agent envelope (`ec_agent_workflow`) so the visitor sees Plan → Investigate → Findings → Remediation, with honest fixture evidence: Splunk vs CMDB conflict is explicit, Splunk alone does not force an incident, default investigation resolves toward Path A (OT inventory active). Do **not** produce a generic interview/physical-inspection how-to.

Done when: S7 first turn is `PLAN_READY` with an editable investigation plan; `run_investigation` does not force an incident from Splunk alone; default investigation shows the device active / CMDB stale; remediation is one-approval batch HIL (OT email + tickets); existing Path A/B chip tests still pass; production `/chat` and `architecture.md` untouched.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- EC fixtures stay `coe_synthetic_fixture`; no live LLM/MCP on the agent path.
- Investigation may name **Splunk MCP** for telemetry (and Splunk-indexed firewall logs). CMDB, OT inventory, and switch ARP are **simulated** — no CMDB/OT/network MCP is onboarded.
- `create_incident_ticket` remains blocked until Path A evidence exists (`_apply` already enforces this).
- Agent `run_remediation` may batch-approve minted `ec_actions` after one plan approval (same as S4/S2).
- Path B chip `confirm_stale_identity` stays available via the existing follow-up API.
- No production `/chat` or `architecture.md` edits.

## Dependency order

`1 → 2 → 3 → 4 → 5`

## Checklist

- [x] **1** — S7 agent config and findings
  - **Do:** Add `backend/app/demo/fixtures/s7/agent_config.py`, `investigation_findings.py`, `investigation_state.py`, `remediation_plan.py`. Investigation steps map to Splunk replay, CMDB record, `check_ot_inventory`, `check_firewall_activity`, `check_arp_mac` (default Path A). `confirm_stale_identity` exists with `default_selected=False`. Remediation maps `ask_ot_team` / `ingest_ot_response` / `create_incident_ticket` / `recommend_cmdb_correction` / `generate_closure_summary`.
  - **Verify:** `python3 -c "from app.demo.fixtures.s7.agent_config import INVESTIGATION_STEP_DEFS, REMEDIATION_STEP_DEFS, S7_SCENARIO_ID; assert S7_SCENARIO_ID=='s7_conflicting_ot_evidence'; assert any(s.get('follow_up_id')=='check_ot_inventory' for s in INVESTIGATION_STEP_DEFS); stale=next(s for s in INVESTIGATION_STEP_DEFS if s.get('follow_up_id')=='confirm_stale_identity'); assert stale.get('default_selected') is False"` from `backend` with `PYTHONPATH=../backend:..`
  - **Depends on:** none
  - **Evidence:** Import assertion printed `ok` (2026-08-20). Six investigation steps include `check_ot_inventory`; Path B `confirm_stale_identity` is `default_selected=False`.

- [x] **2** — Orchestration handler + profile registration
  - **Do:** Add `fixtures/s7/agent_handler.py` (lifecycle, no investigation HIL) and `ec_agent/profiles/s7.py`; import from `ec_agent/profiles/__init__.py`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.ec_agent.registry import has_agent_profile; assert has_agent_profile('s7_conflicting_ot_evidence')"`
  - **Depends on:** 1
  - **Evidence:** Same import command printed `ok`; `has_agent_profile('s7_conflicting_ot_evidence')` is True.

- [x] **3** — Wire `build_s7_turn` and journeys
  - **Do:** Accept `agent_state` in `build_s7_turn`; emit `ec_agent_workflow`; hide orchestration chips during plan/investigate; add `run_investigation` / `create_remediation_plan` / `run_remediation` / Splunk/CMDB review follow-ups / `generate_executive_summary` to `S7_FOLLOWUPS`. Add matching `S7_FOLLOW_UP_JOURNEYS` rows. Keep `_apply()` Path A/B chip semantics. Keep `ec_action_readiness` and `ec_investigation_pivot` on the envelope.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s7_conflicting_ot_evidence.py -q`
  - **Depends on:** 2
  - **Evidence:** `app/tests/test_s7_conflicting_ot_evidence.py` → `5 passed in 1.54s`. Path B chip-list assertion updated to post `recommend_cmdb_correction` (agent UI hides chips).

- [x] **4** — Agent lifecycle tests
  - **Do:** Add `app/tests/test_s7_agent_workflow.py` pinning PLAN_READY, investigation that does not force an incident from Splunk alone, Path A conclusion (active device / stale CMDB), no interview/physical-inspection how-to, and full lifecycle to COMPLETE with `production_side_effect is False`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s7_agent_workflow.py app/tests/test_s7_conflicting_ot_evidence.py app/tests/test_ec_agent_framework.py -q`
  - **Depends on:** 3
  - **Evidence:** `14 passed in 1.86s` (2026-08-20). Opening rejects physical inspection / interview how-to; investigation does not mint `ticket_create`; full lifecycle `COMPLETE` with `production_side_effect is False`.

- [x] **5** — Re-audit existing S7 + isolation
  - **Do:** Confirm first-turn incident remains blocked; Path A chip HIL email still `APPROVAL_REQUIRED`; pack does not import production MCP/actions; no production files changed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s7_conflicting_ot_evidence.py app/tests/test_s7_agent_workflow.py app/tests/test_ec_isolation.py -q`; `git diff --name-only` must not include `architecture.md` or `backend/app/chat/`
  - **Depends on:** 4
  - **Evidence:** Combined S7 + isolation: `11 passed`. `git diff --name-only` has no `architecture.md` or `backend/app/chat/`. Path A chip test still asserts `email_send` `APPROVAL_REQUIRED`. Pack has no `app.connectors` / `app.chat` imports.

## Verification gaps

None — every item has a concrete Verify command.

## Drift log

_None yet._
