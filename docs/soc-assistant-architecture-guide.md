# AI SOC Assistant Architecture Guide

## Canonical Route Mapping

| Case | Match path | Route skill | Intent family | Answer mode | Path type |
|---|---|---|---|---|---|
| 105 analytics | `exact_105_question` | `attack_discovery` | `spl_generation_only` | `live_investigation` | `spl_review` |
| Catalog SOP | `use_case_catalog` | `knowledge_recall` | `sop_or_playbook` | `rag_only` | `rag_only` |
| Out-of-registry investigation | `out_of_registry` | `guided_investigation` | `guided_investigation` | `guided_investigation` | `guided_investigation` |
| Unsafe execution | any | existing blocked route | `clarification_required` | `clarification` | `unsafe_blocked` |

`guided_investigation` is a deterministic rescue for SOC-shaped hunt questions that have no 105-question or use-case-catalog match. It does not override registry authority. It returns hypotheses, evidence sources, a manual checklist, limitations, and analyst-review requirements. Candidate SPL remains review-only and is omitted unless an existing deterministic draft family matches. MCP remains disabled.

## Internal Cybersecurity Skills Library

The internal skills catalog in `backend/app/skills/catalog.json` contains governed answer-building blocks. Each entry describes purpose, allowed and blocked tools, required evidence, workflow stages, HIL policy, and action tier. Skills do not execute tools directly; validators, MCP gates, and HIL remain authoritative.

```text
Route skill -> intent -> resource planner
  -> skill chain + RAG + optional SPL draft + MCP intent + narration
  -> governed pipeline stages -> answer contract and policy checks
```

The composer resolves `skill:{skill_id}` descriptors from `backend/app/planner/resource_registry_v1.json`. Skill contracts can veto steps. `resource_decisions` records why RAG, SPL, MCP, MITRE, severity, and HIL were used or skipped.

| Example | Skills | Contribution |
|---|---|---|
| Brute-force investigation | `attack_discovery` -> `spl_generation` -> `spl_validation` -> `evidence_collection` | Governed SPL template, deterministic validation, evidence contract |
| OT chatter OOD hunt | `guided_investigation` -> `evidence_collection` -> `context_sufficiency` -> `answer_guard` | Hypotheses, evidence checklist, limitations, analyst validation; no catalog claim |
| SPL validation | `spl_validation` | Only approved non-null `normalized_spl` may approach the MCP gate |

## Team Examples: Five Paths

| # | User question | Match path | Route | Intent / answer / path | What the analyst gets |
|---|---|---|---|---|---|
| 1 | Which hosts are generating the most SMB traffic? | `exact_105_question` | `attack_discovery` | `spl_generation_only` / `live_investigation` / `spl_review` | Review-only governed analytics SPL |
| 2 | Show me the brute-force login SOP | `use_case_catalog` | `knowledge_recall` | `sop_or_playbook` / `rag_only` / `rag_only` | Cited governed playbook context |
| 3 | Investigate failed login spike on APP-01 | catalog/105 | `attack_discovery` | governed investigation path | Evidence checklist and bounded SPL workflow |
| 4 | Strange OT chatter to a new external host overnight, anything to hunt? | `out_of_registry` | `guided_investigation` | `guided_investigation` / `guided_investigation` / `guided_investigation` | Hunt hypotheses, sources, limitations, manual discovery checklist, HIL |
| 5 | Block this IP on the firewall immediately | any | blocked | `clarification_required` / `clarification` / `unsafe_blocked` | Refusal and human-review requirement |

## LLM Advisory Trace

Live control-plane traces expose `llm_advisory_trace` without granting model authority:

- `llm_advisory_used`: an existing route, intent, or narration advisory ran.
- `llm_route_candidate`: model-suggested route before deterministic normalization.
- `llm_intent_candidate`: model-suggested intent before deterministic normalization.
- `llm_narration_used`: the live synthesis layer rewrote analyst prose.
- `llm_overridden_by_policy`: deterministic policy rejected or ignored an advisory.

No additional LLM call is made to produce this block. The LLM never calls MCP, and route, SPL, MITRE, severity, and execution controls remain deterministic.
