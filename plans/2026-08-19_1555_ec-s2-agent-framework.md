---
name: ec-s2-agent-framework
overview: "Convert Experience Center S2 (prompt-injection / unauthorized tool / restricted-data) onto the reusable EC agent workflow used by S4. EC/demo only; architecture.md and live /chat frozen."
status: done
date: 2026-08-19
canonical_plan: plans/2026-08-19_1555_ec-s2-agent-framework.md
---

# Convert S2 onto the EC agent framework

## Objective

S2 (`s2_ai_prompt_injection`) answers:

> Investigate whether our customer-facing AI assistant is being targeted with prompt-injection attempts and whether any attempts resulted in unauthorized tool execution or restricted-data access.

Today that journey is chip-driven. Convert it to the S4 agent envelope (`ec_agent_workflow`) so the visitor sees Plan → Investigate → Findings → Remediation → Verify → Close, with honest fixture evidence: attempts confirmed, `export_customer_records` blocked, restricted-data access not confirmed. Do **not** produce a generic Splunk tutorial.

Done when: S2 first turn is `PLAN_READY` with an editable investigation plan; `run_investigation` completes the three evidence questions; remediation is one-approval batch HIL; existing chip-path HIL tests still pass; production `/chat` and `architecture.md` untouched.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- EC fixtures stay `coe_synthetic_fixture`; no live LLM/MCP on the agent path.
- `execution_eligible=false` on any SPL; credential disable and AppSec email stay HIL on the chip path.
- Agent `run_remediation` may batch-approve minted `ec_actions` after one plan approval (same as S4).
- No production `/chat` or `architecture.md` edits.

## Dependency order

`1 → 2 → 3 → 4 → 5`

## Checklist

- [x] **1** — S2 agent config and findings
  - **Do:** Add `backend/app/demo/fixtures/s2/agent_config.py`, `investigation_findings.py`, `investigation_state.py`, `remediation_plan.py`. Investigation steps map to existing follow-ups (`review_existing_detection` + DLP / tool history / identity / data-source / policy). Remediation maps ticket / credential HIL / AppSec email / verify / update / closure.
  - **Verify:** `python3 -c "from app.demo.fixtures.s2.agent_config import INVESTIGATION_STEP_DEFS, REMEDIATION_STEP_DEFS, S2_SCENARIO_ID; assert S2_SCENARIO_ID=='s2_ai_prompt_injection'; assert any(s.get('follow_up_id')=='check_dlp' for s in INVESTIGATION_STEP_DEFS)"` from `backend` with `PYTHONPATH=../backend:..`
  - **Depends on:** none
  - **Evidence:** Import assertion printed `ok` (2026-08-19). Eight investigation steps include `check_dlp`; six remediation steps include HIL credential disable.

- [x] **2** — Orchestration handler + profile registration
  - **Do:** Add `fixtures/s2/agent_handler.py` (lifecycle, no investigation HIL) and `ec_agent/profiles/s2.py`; import from `ec_agent/profiles/__init__.py`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.ec_agent.registry import has_agent_profile; assert has_agent_profile('s2_ai_prompt_injection')"`
  - **Depends on:** 1
  - **Evidence:** Same import command printed `ok`; `has_agent_profile('s2_ai_prompt_injection')` is True.

- [x] **3** — Wire `build_s2_turn` and journeys
  - **Do:** Accept `agent_state` in `build_s2_turn`; emit `ec_agent_workflow`; hide orchestration chips during plan/investigate; add `run_investigation` / `create_remediation_plan` / `run_remediation` / `review_existing_detection` / `generate_executive_summary` to `S2_FOLLOWUPS`. Add matching `S2_FOLLOW_UP_JOURNEYS` rows. Keep `_apply()` chip semantics.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s2_ai_application_security.py -q`
  - **Depends on:** 2
  - **Evidence:** `app/tests/test_s2_ai_application_security.py` green as part of the 15-passed S2+framework run (chip HIL path unchanged).

- [x] **4** — Agent lifecycle tests
  - **Do:** Add `app/tests/test_s2_agent_workflow.py` pinning PLAN_READY, investigation answering the three questions (no fake SPL tutorial), and full lifecycle to COMPLETE with `production_side_effect is False`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s2_agent_workflow.py app/tests/test_s2_ai_application_security.py app/tests/test_ec_agent_framework.py -q`
  - **Depends on:** 3
  - **Evidence:** `15 passed in 1.50s` for those three files (2026-08-19). Investigation conclusion pins attempted / blocked / not confirmed; opening narrative rejects `index=your_ai_logs`.

- [x] **5** — Re-audit existing S2 + isolation
  - **Do:** Confirm chip-path credential HIL still requires approval; pack does not import production MCP/actions; no production files changed.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s2_ai_application_security.py app/tests/test_s2_agent_workflow.py -q`; `git diff --name-only` must not include `architecture.md` or `backend/app/chat/`
  - **Depends on:** 4
  - **Evidence:** Combined S2 + SIEM-first + isolation + EC response: `45 passed`. `git diff --name-only` for `architecture.md` and `backend/app/chat/` empty. Chip test still asserts `iam_disable` `APPROVAL_REQUIRED`.

## Verification gaps

None — every item has a concrete Verify command.

## Drift log

_None yet._
