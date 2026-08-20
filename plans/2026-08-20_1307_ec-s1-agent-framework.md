---
name: ec-s1-agent-framework
overview: "Convert Experience Center S1 (newly observed IP / MCP identity / SOP monitoring) onto the reusable EC agent workflow used by S2/S4/S7. EC/demo only; architecture.md and live /chat frozen."
status: done
date: 2026-08-20
canonical_plan: plans/2026-08-20_1307_ec-s1-agent-framework.md
---

# Convert S1 onto the EC agent framework

## Objective

S1 (`s1_governed_splunk_investigation`) answers:

> We have seen a new IP 198.51.100.42. Check and verify over the last 30 days whether it is malicious, and what is the standard SOP to raise monitoring and block it if required.

Today the first turn dumps Layer-1 findings immediately. Convert it to the S2/S4 agent envelope (`ec_agent_workflow`) so the visitor sees **Plan → Investigate → Findings/conclusion → Remediation plan**, with honest fixture evidence: existing IOC notable did not fire, last 30 days show firewall communication, prior window empty, identity is a newly registered MCP endpoint, malicious use not confirmed. SOP: raise monitoring first, HIL block only if required. Do **not** call the IP suspicious in the question or opening (if it were a known-bad IOC, Splunk should already have detected it).

Done when: S1 first turn is `PLAN_READY` with an editable investigation plan; `run_investigation` concludes new-MCP / not confirmed malicious; `create_remediation_plan` then `run_remediation` is one-approval batch HIL (monitoring + optional block); existing chip-path HIL tests still pass via the follow-up API; production `/chat` and `architecture.md` untouched.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- EC fixtures stay `coe_synthetic_fixture`; no live LLM/MCP on the agent path.
- Investigation may name **Splunk MCP** for notable evaluation and firewall SPL, plus **SOC-KB** for MCP identity. No invented CMDB/firewall-write/TI MCP.
- Candidate SPL stays `execution_eligible=false`. Firewall block and email stay HIL on the chip path; agent `run_remediation` may batch-approve minted `ec_actions` after one plan approval (same as S2/S4/S7).
- Do not label the IP “suspicious” in `S1_QUERY` or the opening narrative.
- No production `/chat` or `architecture.md` edits.

## User directives

- Follow the S2/S4/S7 agent UI contract (`docs/ec/agent_workflow_template.md`): plan first, then investigate, then conclude, then a remediation plan.
- S3 is **not** on `ec_agent_workflow` yet. This plan uses S2 (and S4/S7) as the shipped reference, not S3’s chip path.

## Dependency order

`1 → 2 → 3 → 4 → 5`

## Checklist

- [x] **1** — S1 agent config and findings
  - **Do:** Add `backend/app/demo/fixtures/s1/agent_config.py`, `investigation_findings.py`, `investigation_state.py`, `remediation_plan.py`. Investigation steps: evaluate existing IOC notable, requested last-30-days firewall search, prior novelty window, MCP identity (SOC-KB). Optional auth/EDR/privileged/previous default off or bundled. Remediation: `raise_mcp_monitoring` first, then HIL `prepare_firewall_block`, ticket, email, verify, update, closure.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.fixtures.s1.agent_config import INVESTIGATION_STEP_DEFS, REMEDIATION_STEP_DEFS, S1_SCENARIO_ID, OPENING_NARRATIVE; assert S1_SCENARIO_ID=='s1_governed_splunk_investigation'; assert any(s.get('follow_up_id')=='raise_mcp_monitoring' for s in REMEDIATION_STEP_DEFS); n=OPENING_NARRATIVE.lower(); assert 'suspicious' not in n; assert 'splunk and mcp tools and rag guidelines' in n"`
  - **Depends on:** none
  - **Evidence:** `python3 -c ...` printed `item1 ok`. `OPENING_NARRATIVE` has no “suspicious”; remediation includes `raise_mcp_monitoring`.

- [x] **2** — Orchestration handler + profile registration
  - **Do:** Add `fixtures/s1/agent_handler.py` (lifecycle, no investigation HIL) and `ec_agent/profiles/s1.py`; import from `ec_agent/profiles/__init__.py`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.ec_agent.registry import has_agent_profile; assert has_agent_profile('s1_governed_splunk_investigation')"`
  - **Depends on:** 1
  - **Evidence:** `python3 -c ...` printed `item2 ok`. `has_agent_profile('s1_governed_splunk_investigation')` is true.

- [x] **3** — Wire `build_s1_turn` and journeys
  - **Do:** Accept `agent_state` in `build_s1_turn`; emit `ec_agent_workflow`; hide orchestration chips during plan/investigate; add `run_investigation` / `create_remediation_plan` / `run_remediation` / `review_existing_notable` / `generate_executive_summary` to the S1 follow-up catalog. Add matching `S1_FOLLOW_UP_JOURNEYS` rows. Keep `_apply_follow_up_effects()` chip semantics. Suppress Layer-1 dump while `use_agent_ui`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_governed_splunk_investigation.py app/tests/test_ec_siem_first_investigation.py -q`
  - **Depends on:** 2
  - **Evidence:** pytest → **35 passed**. First-turn title is plan-shaped (`PLAN_READY`); `EcInvestigationAnswer` hides Assessment / What we found / SIEM cards when `ec_agent_workflow` is present. Email extras always resolved so batch remediation re-apply does not UnboundLocalError.

- [x] **4** — Agent lifecycle tests
  - **Do:** Add `app/tests/test_s1_agent_workflow.py` pinning PLAN_READY (no investigation_results), investigation conclusion (new MCP, notable did not fire, malicious not confirmed), full lifecycle to COMPLETE with `production_side_effect is False`, opening rejects “suspicious IP” / invented Splunk tutorials.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py app/tests/test_s1_governed_splunk_investigation.py app/tests/test_ec_agent_framework.py -q`
  - **Depends on:** 3
  - **Evidence:** pytest → **28 passed**. `test_s1_agent_plan_ready_on_initial_turn`, `test_s1_run_investigation_concludes_new_mcp_not_malicious`, `test_s1_full_agent_lifecycle_to_complete` green. Non-agent dispatch test now uses S3.

- [x] **5** — Re-audit existing S1 + isolation
  - **Do:** Confirm chip-path firewall block still HIL via follow-up API; pack does not import production MCP/actions; no production files changed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_governed_splunk_investigation.py app/tests/test_s1_agent_workflow.py app/tests/test_ec_isolation.py -q`; `git diff --name-only` must not include `architecture.md` or `backend/app/chat/`
  - **Depends on:** 4
  - **Evidence:** pytest → **25 passed**. `git diff --name-only` has no `architecture.md` or `backend/app/chat/`. Chip-path `prepare_firewall_block` still `PREPARED`/`APPROVAL_REQUIRED`. `fixtures/s1` does not import `app.chat` / live MCP.

## Verification gaps

None — every item has a concrete Verify command.

## Drift log

- 2026-08-20: User cited “S2 and S3” as the guideline. **S3 is not on `ec_agent_workflow`.** Shipped references are S2/S4/S7. S1 adopts that contract.
- 2026-08-20: Generic `agentMode` in `EcInvestigationAnswer` now also hides Assessment / What we found / SIEM collapsible / pivot so those Layer-1 dumps cannot sit beside the plan (S1/S2/S7).
