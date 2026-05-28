# Stage 3K-Q4A: Author-Time Coverage Drafter CLI (optional, future)

**Status:** Proposed — **not** part of Q4 runtime delivery.

## Objective

Optional human-in-the-loop CLI to draft `pattern_coverage_v1.json` entries from SOC question text using closed enums (skills, templates, readiness labels). Outputs are reviewed before merge; the running backend never calls this tool.

## Scope (when implemented)

- Module under `tools/coverage_authoring/coverage_drafter.py`
- Inputs: question text from `docs/soc_question_taxonomy_stage3k_q0.md`, closed registries
- Outputs: draft JSON validated by `app.coverage.coverage_models`
- Drafts land in `tools/coverage_authoring/drafts/` until promoted to the manifest
- Instruct-only LLM allowed at author time; no Reasoning, no `/chat` wiring

## Non-Goals

- No runtime LLM from `/chat`
- No SPL/MCP execution
- No automatic promotion of drafts without human review

## Relationship to Q4

Q4 ships the **committed manifest** and deterministic loader only. Q4A is a separate, optional authoring convenience.
