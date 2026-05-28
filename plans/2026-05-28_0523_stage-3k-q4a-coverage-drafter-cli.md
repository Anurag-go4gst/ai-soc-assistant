# Stage 3K-Q4A: Author-Time Coverage Drafter CLI (optional)

**Status:** Done
**Tool path:** `tools/coverage_authoring/coverage_drafter.py`
**Tests:** `tools/coverage_authoring/tests/test_coverage_drafter_q4a.py` (run with `PYTHONPATH=backend python3 -m pytest tools/coverage_authoring/tests`)
**Runtime:** Not wired to `/chat` or backend request path

## Objective

Optional human-in-the-loop CLI to draft `pattern_coverage_v1.json` entries from SOC question text using closed enums (skills, templates, readiness labels). Outputs are reviewed before merge; the running backend never calls this tool.

## Delivered

- `tools/coverage_authoring/coverage_drafter.py` — CLI (`--question`, `--question-ref`, `--entry-json`, `--use-llm` + `--llm-raw-file`, `--validate-draft`)
- `draft_schema.py`, `registries.py`, `deterministic.py`, `validator.py`, `llm_assist.py`, `taxonomy_lookup.py`, `io_utils.py`
- `drafts/.gitkeep` — draft output directory only
- `README.md` — author-time workflow and promotion steps
- Closed-world validation: no invented refs; `sample_only` templates rejected; governance flags forced false
- Instruct-only LLM path via offline `--llm-raw-file`; Reasoning rejected; no live LLM by default
- Tool tests (14) excluded from default backend pytest collection

## Non-Goals (unchanged)

- No runtime LLM from `/chat`
- No SPL/MCP execution
- No automatic promotion without human review
- No writes to `backend/app/coverage/pattern_coverage_v1.json`

## Relationship to Q4

Q4 ships the **committed manifest** and `app.coverage.coverage_loader`. Q4A only produces reviewed drafts under `tools/coverage_authoring/drafts/`.

## Verification

```bash
PYTHONPATH=backend python3 -m pytest tools/coverage_authoring/tests -q
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```
