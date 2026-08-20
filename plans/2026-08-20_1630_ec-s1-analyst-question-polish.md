---
name: ec-s1-analyst-question-polish
overview: "Reorder S1 investigation around who/what/succeeded/new/known-bad/coverage/SOP. Fix wording, metrics, provenance, empty UI. EC/demo only."
status: done
date: 2026-08-20
canonical_plan: plans/2026-08-20_1630_ec-s1-analyst-question-polish.md
---

# S1 analyst-question polish (Experience Center only)

## Objective

S1 answers: who is this IP, what did it do, did anything succeed, is it new, is it known bad, would existing detections catch it, and what SOP justifies now. Detection coverage is a late step, not the frame. Agent-added permitted-session investigation stays. Yes/Not now remediation checkpoint stays. Production `/chat` and `architecture.md` stay frozen.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed — **stop and ask**

## Governance invariants

- EC fixtures stay `coe_synthetic_fixture`. No live LLM/MCP. No VirusTotal/IPVoid.
- Candidate SPL stays `execution_eligible=false`. LLM output is reasoning, not evidence.
- Firewall block stays HIL; do not execute when SOP threshold is not met.
- No production `/chat` or `architecture.md` edits.

## User directives

- Keep Investigate → inference → Yes/Not now → create plan → execute approved plan → verify.
- Do not block merely because the IP is new or unlisted.
- `new ≠ malicious`, `unlisted ≠ benign`, `no alert ≠ safe`, `allow ≠ authenticated compromise`.

## Dependency order

`1 → 2 → 3 → 4 → 5`

## Checklist

- [x] **1** — Reorder investigation + detection wording + agent-added step
  - **Do:** Reorder default S1 steps: identity → 30d network → (agent) permitted sessions/auth → novelty → local TI → assess Splunk detection coverage → SOP. Unbundle 30d/identity from notable. Notable title `Assess existing Splunk detection coverage`; finding `Existing IOC detection: No alert — IP not present in the IOC list used by this detection`. Adaptation title/reason: three permitted sessions reached a high-criticality jump host.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -c "from app.demo.fixtures.s1.agent_config import INVESTIGATION_STEP_DEFS, ADAPTATION_STEP; ids=[s['id'] for s in INVESTIGATION_STEP_DEFS if s.get('default_selected')]; assert ids[:3]==['mcp_identity','requested_30d','novelty_window'] or ids[0]=='mcp_identity'; assert ids[-2:]==['evaluate_notable','retrieve_sop'] or ids[-1]=='retrieve_sop'; assert 'Assess existing Splunk detection coverage' in [s['title'] for s in INVESTIGATION_STEP_DEFS]; assert ADAPTATION_STEP['added_by_agent'] is True; assert 'jump host' in ADAPTATION_STEP['reason'].lower()"`
  - **Depends on:** none
  - **Evidence:** `python3 -c` → `item1 OK ['mcp_identity', 'requested_30d', 'novelty_window', 'threat_intel', 'evaluate_notable', 'retrieve_sop'] Investigate permitted sessions and authentication`. Adaptation `added_by_agent=True`; reason contains jump host.

- [x] **2** — Conclusion, metrics, severity, unresolved, agent assessment
  - **Do:** Headline `Newly observed registered MCP endpoint · 3 permitted jump-host sessions remain unexplained · malicious use not confirmed`. Four-question copy without “require validation” or speculative lateral movement. Metrics per user table. Severity reason line. Outstanding uncertainty only the three analyst questions. Primary UI `Agent assessment`; LLM/provenance under View trace.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py -q`
  - **Depends on:** 1
  - **Evidence:** `pytest app/tests/test_s1_agent_workflow.py app/tests/test_s1_governed_splunk_investigation.py app/tests/test_ec_isolation.py -q` → `25 passed in 2.04s`. Headline/metrics/unresolved/agent-assessment assertions in `test_s1_run_investigation_concludes_new_mcp_not_malicious`.

- [x] **3** — Remediation follows SOP; Yes/Not now unchanged
  - **Do:** After Yes, plan monitors 198.51.100.42 for 14 days, allowed activity to 10.20.1.10, svc_jump_ops auth correlation, incident, conditional block (not executed), no Network approval request unless threshold met, residual watch, incident update. Keep Yes/Not now.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py app/tests/test_s1_governed_splunk_investigation.py -q`
  - **Depends on:** 2
  - **Evidence:** Same 25-passed run. `test_s1_full_agent_lifecycle_to_complete` asserts 14-day/jump-host/svc_jump_ops rem titles, block approval not requested, Yes/Not now, firewall_block stays PREPARED/APPROVAL_REQUIRED.

- [x] **4** — Provenance labels + never render empty artefacts
  - **Do:** Source-evidence hint derived from actual items (no Agilus/ITSM unless present). Filter empty bullets/tables/path cards. View trace expands reasoning, not primary LLM implementation language.
  - **Verify:** `cd frontend && npm test -- src/components/ec/s1Workspace.test.tsx src/components/ec/flagshipWorkspace.test.tsx --reporter=dot`
  - **Depends on:** 3
  - **Evidence:** `npm test -- src/components/ec/s1Workspace.test.tsx src/components/ec/flagshipWorkspace.test.tsx --reporter=dot` → `26 passed (26)`. `npm run build` → tsc + vite OK, postbuild chmod. Dist `index-D9oVEdwv.js`.

- [x] **5** — Isolation
  - **Do:** Chip-path HIL still works; git diff excludes `architecture.md` and `backend/app/chat/`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_s1_agent_workflow.py app/tests/test_s1_governed_splunk_investigation.py app/tests/test_ec_isolation.py -q`; `git diff --name-only` must not include `architecture.md` or `backend/app/chat/`
  - **Depends on:** 4
  - **Evidence:** pytest 25 passed including `test_ec_isolation.py`. `git diff --name-only` has no `architecture.md` or `backend/app/chat/` (`ISOLATION_OK`). Chip-path HIL still covered by `test_s1_governed_splunk_investigation.py`.

## Verification gaps

None — every item has a concrete Verify command.

## Drift log

- 2026-08-20: Prior polish used detection-first step order and “require validation” after the allow drill. This plan follows the analyst who/what/succeeded sequence and treats the three allows as validated-but-unexplained.
