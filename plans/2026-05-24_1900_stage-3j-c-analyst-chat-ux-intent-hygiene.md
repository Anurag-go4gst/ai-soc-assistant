# Stage 3J-C: Analyst Chat UX and Intent Hygiene

Base: Stage 3J-B (`07b7151` / `075b8b0`).

## Goal

Make chat responses analyst-first, collapse the technical trace, and fix three
intent bugs. No final synthesis, no answer guard, no MCP execution change, no new
providers, no RAG retrieval change.

## Backend (intent hygiene)

- `deterministic_router.py`: SOP/playbook/runbook and MITRE rules added at the top
  (first-match-wins) → both route to `knowledge_recall`, so no SPL is generated.
- `spl/generator.py`: widen the success-after-failures predicate so
  "successful login after failures" hits the failure+success correlation template
  instead of the failed-spike fallback.
- `routes_chat.py`: MITRE-without-alert-context → clarification via the existing
  `human_review` envelope (`review_type="intent_clarification"`); message asks for
  alert title/rule/notable/SPL. Conservative heuristic (keyword + no context marker
  + short message). No skill enum change, no new response field. Sufficiency is
  naturally `insufficient_evidence`.

## Frontend (analyst-first UX)

- `AnalystSummaryCard` (new): status / execution / evidence / readiness / next action,
  derived purely from the existing `PlaceholderResponse`. Human-readable labels map
  the raw codes (raw codes stay in the trace).
- `ChatBubble`: summary card on top; `Stage3DTracePanel` wrapped in a `<details>`
  "Show technical trace", collapsed by default.
- `Stage3DTracePanel`: removed duplicate "Final LLM synthesis is not enabled" footers
  and the redundant badge (stated once in the summary card); added a copy button for
  candidate SPL. Trace ID copy lives on the summary card.
- `CopyButton` (new): shared copy control.
- `StarterPrompts`: grouped into Investigate / Knowledge-SOP / Generate SPL / MITRE.
- `index.css`: lightened the background (`--background` 5% → 11%; gradient
  `#0b1220 → #16233b`; topbar lifted off near-black).

## Tests (backend)

`test_intent_hygiene_stage3jc.py`: SOP→knowledge_recall (no SPL), success-after-failures
correlation SPL (failure AND success, not failed-spike-only), MITRE clarification
(no SPL, intent_clarification review, insufficient_evidence), MITRE-with-context does
not force clarification. No frontend test runner exists; not adding one.

## Verify

- backend pytest (185 pass) · frontend build · harness 6/6 both modes · git diff --check
