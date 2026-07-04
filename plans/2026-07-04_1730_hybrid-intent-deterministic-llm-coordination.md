---
name: hybrid-intent-deterministic-llm-coordination
overview: "Plan the hybrid-intent work so it can run beside danger-tiered MCP command intent without conflict: deterministic routing gets richer, LLM remains advisory, command-shaped MCP/SPL turns are excluded from guided rescue, and hybrid advisory investigations can still be rescued from generic SPL."
status: done
date: 2026-07-04
canonical_plan: plans/2026-07-04_1730_hybrid-intent-deterministic-llm-coordination.md
related_plans:
  - plans/2026-07-04_1610_danger-tiered-mcp-command-intent.md
---

# Hybrid intent routing: deterministic + LLM coordination

## Purpose

This plan owns the **hybrid advisory investigation** side of routing. It must not implement MCP command execution semantics owned by `2026-07-04_1610_danger-tiered-mcp-command-intent.md`.

Goal: make deterministic intent richer and use LLM as an advisory semantic co-signer for hard hybrid questions, while preserving governance defaults:

- LLM never calls MCP directly.
- Deterministic execution policy wins on conflict.
- Candidate SPL remains non-executable unless validated and HIL-approved.
- Command-shaped SPL/MCP requests do not fall into guided rescue.

## Non-conflict contract with danger-tiered MCP plan

| Concern | Owner plan | Shared rule |
|---|---|---|
| `run_spl`, `optimize_spl`, `run_saved_search`, `discovery_ask` command modes | danger-tiered MCP plan | Command modes short-circuit before guided rescue. |
| MCP danger tiers, HIL skip for read-only discovery, `splunk_run_query` HIL | danger-tiered MCP plan | Hybrid plan may request discovery evidence but must not change gate policy. |
| Source-health, OT/process-aware, containment decision-support advisory routing | this plan | These are not command modes unless explicit run/optimize/saved-search/discovery command signals fire. |
| LLM semantic rescue / disagreement telemetry | this plan | LLM suggestions are normalized through deterministic route registries and cannot authorize execution. |
| Generic live-data SPL fallback | shared | Command modes win first; then advisory hybrid shapes; then generic SPL. |

Canonical precedence for both plans:

1. Destructive/write/admin command or direct containment action -> block or HIL.
2. Explicit MCP/SPL command modes -> danger-tiered MCP command spine, not guided rescue.
3. Containment decision-support asks -> guided investigation advisory, not execution.
4. Regulatory / policy / knowledge-only asks -> knowledge recall.
5. Source-health and OT/process-aware hybrid asks -> guided/hybrid evidence planning before generic SPL.
6. Generic live-data searches -> `spl_generation`.
7. Generic novel investigation -> `guided_investigation`.

## Hybrid probes before implementation

Run these through the real HTTP path before making code changes:

```bash
scripts/ask_chat.sh "We saw AGC setpoint commands that could push frequency outside 49.9-50.1 Hz. First list the Splunk indexes or metadata that can prove whether AGC logs exist, then prepare a review-only hunt for injected vs legitimate dispatch. Do not run the SPL until I approve."
```

Expected: process-aware OT + discovery + review-only SPL. No `splunk_run_query`. Read-only discovery may be selected only if MCP flags allow it.

```bash
scripts/ask_chat.sh "Here is SPL: search index=pgcil_soc sourcetype=pgcil:ot_agc earliest=-2h | stats count by command_src setpoint. Validate and optimize it, list missing source profile metadata, and if it passes, ask me before running."
```

Expected: command intent wins over guided rescue. The command plan owns final command-mode implementation; this plan only verifies that advisory hybrid rules do not steal it.

## Dependency order

`1 -> 2 -> 3 -> 4 -> 5`

This plan may run in parallel with `2026-07-04_1610_danger-tiered-mcp-command-intent.md` if each agent respects the ownership table above.

## Checklist

- [x] **1** — Baseline the two hybrid probes through `ask_chat`
  - **Do:** Run both probes with `scripts/ask_chat.sh` and capture the returned trace fields: `query_understanding`, deterministic signals, `semantic_intent`, LLM route suggestion, `selected_skill`, `answer_mode`, `route_adjudication`, `evidence_plan`, SPL validation, MCP selection, HIL reason.
  - **Verify:** Evidence file records the node where each failure occurs: query understanding, intent classification, route adjudication, evidence planning, MCP selector, gate/HIL, or answer surface.
  - **Depends on:** none
  - **Evidence:** Live probes 2026-07-04 via `scripts/ask_chat.sh` → `docs/evals/hybrid_intent_baseline_2026-07-04/` (`ask_chat_probes.txt`, `baseline_summary.json`, `README.md`). Q1 fail: route_adjudication `explicit_run_spl_hil_gate` (false positive on “Do not run the SPL”) + evidence_planning no discovery. Q2 fail: route_adjudication `guided_investigation_rescue` steals command-shaped paste (danger-plan owned). Traces `3a31576f-…` / `ca71c2d0-…`.

- [x] **2** — Add deterministic hybrid-shape signals without changing command ownership
  - **Do:** Add or refine deterministic signals for source-health, OT/process-aware, and containment decision-support. These signals must not fire when command modes from the danger-tiered plan fire.
  - **Verify:** Unit tests show Q9-style containment decision support routes guided advisory; Q11-style source health and Q12-style process-aware OT do not collapse to generic SPL unless they are explicit command/live-search asks.
  - **Depends on:** 1
  - **Evidence:** `hybrid_advisory_source_health` / `hybrid_advisory_process_aware_ot` / `command_mode_active` / `command_shaped_spl` in `query_signals.py`; negation fix for “do not run the SPL”; `_maybe_route_hybrid_advisory` + OOR `command_mode_spine` short-circuit; intent guided for hybrid shapes. `pytest app/tests/test_hybrid_intent_advisory_signals.py app/tests/test_containment_decision_support.py app/tests/test_explicit_run_spl_routing.py app/tests/test_guided_investigation_route.py app/tests/test_route_adjudication.py::test_explicit_run_spl_adjudicates_to_spl_generation_not_knowledge_recall -q` → 53 passed.

- [x] **3** — Use LLM as advisory rescue only inside deterministic windows
  - **Do:** Allow LLM semantic intent to co-sign ambiguous hybrid advisory turns when deterministic confidence is weak or signals conflict. Normalize LLM suggestions through existing registries; record disagreements.
  - **Verify:** Tests with fake LLM show advisory suggestion can rescue hybrid shape, but cannot override command intent, unsafe SPL, HIL, or execution flags.
  - **Depends on:** 2
  - **Evidence:** `hybrid_llm_advisory_rescue()` in `route_adjudication.py`; `intent_advisor_consumable` skips `command_mode_active` / `explicit_run_spl`, allows hybrid advisory window. `pytest app/tests/test_hybrid_llm_advisory_rescue.py -q` → 8 passed (rescue promotes knowledge→guided; blocked by command/unsafe).

- [x] **4** — Wire hybrid shape into evidence planning and canonical telemetry
  - **Do:** Ensure the selected hybrid route changes analyst-visible planning, not only trace metadata. Evidence plan should reflect guided/hybrid investigation, discovery needs, SPL review-only status, and HIL reason.
  - **Verify:** End-to-end tests assert `selected_skill`, `answer_mode`, `route_adjudication.authority_source`, `evidence_plan`, and `workflow_plan.execution_enabled=false` for hybrid advisory probes.
  - **Depends on:** 2, 3
  - **Evidence:** `evidence_planner` grants `discovery_allowed` + `spl_review_allowed` + HIL for hybrid advisory signals (`hybrid_advisory_evidence_plan`). `test_hybrid_advisory_evidence_plan_is_analyst_visible` asserts skill/answer_mode/discovery/spl_review/execution_enabled=false/path_type guided. Full hybrid suite 22 passed.

- [x] **5** — Regression against command MCP plan and existing governance
  - **Do:** Run targeted routing/intent tests plus the danger-tiered MCP command tests if present. Confirm command-shaped turns stay on the command spine and hybrid advisory turns can be guided.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_*intent* app/tests/test_*routing* -q`; then run `./scripts/run_stage3_governance_regression.sh` before claiming complete.
  - **Depends on:** 4 and the relevant command-mode checklist items from `2026-07-04_1610_danger-tiered-mcp-command-intent.md`
  - **Evidence:** Intent/routing `pytest app/tests/test_*intent* app/tests/test_*routing* -q` → 231 passed. Hybrid command-mode ownership (`command_mode_active` short-circuit, hybrid OOR-only) verified in `test_hybrid_intent_advisory_signals.py` / `test_hybrid_llm_advisory_rescue.py`. Catalogue scope fix: hybrid advisory never overrides exact-105/Cisco-50. `./scripts/run_stage3_governance_regression.sh` → PASS (3958+ pytest, harness, clean-answer). Danger plan still owns full MCP gate/`spl_and_run` execution tiers.

## Stop conditions

- Same verification gate fails twice on one item.
- Any change would make LLM authoritative for execution.
- Any change would allow candidate SPL or read-only discovery to bypass MCP execution flags.
- Any overlap with the danger-tiered MCP plan violates the ownership table above.
