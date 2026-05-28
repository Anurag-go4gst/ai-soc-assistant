# Stage 3K-Q4A — Author-Time Coverage Drafter CLI

Optional **author-time only** tooling to draft candidate entries for `backend/app/coverage/pattern_coverage_v1.json`. This package is **not** imported by the FastAPI backend and is **never** called from `/chat`.

## What Q4A is

- A human-in-the-loop helper that proposes **draft JSON** under `tools/coverage_authoring/drafts/`
- Uses **closed registries** already committed in the repo (runtime skills, templates, IOC lookups, vetted detections, evidence contracts)
- Validates drafts against `app.coverage.coverage_models.PatternCoverageEntry`
- Records `draft_only=true`, `requires_human_review=true`, `promoted_to_manifest=false`

## What Q4A is not

- **Not** runtime coverage — the running app only reads the committed manifest (Q4)
- **Not** analyst-facing answers, SPL execution, MCP execution, final LLM synthesis, or Answer Guard
- **Not** automatic promotion into `pattern_coverage_v1.json`
- **Not** allowed to invent `template_ref`, `lookup_ref`, `detection_ref`, or `evidence_contract_ref`
- **Not** allowed to promote `sample_only` templates

> LLM assistance is candidate-only. Deterministic core owns validation, normalization, binding, rendering, execution eligibility, and all blocking decisions. If LLM output disagrees with deterministic validation, deterministic wins and the disagreement is recorded.

## Prerequisites

From the repository root:

```bash
export PYTHONPATH=backend
```

## Generate a deterministic draft

```bash
python tools/coverage_authoring/coverage_drafter.py \
  --question "Which hosts contacted known malicious IPs today?"
```

```bash
python tools/coverage_authoring/coverage_drafter.py --question-ref q004
```

```bash
python tools/coverage_authoring/coverage_drafter.py \
  --question "Which DNS queries look like DGA activity?"
```

Draft files are written as `tools/coverage_authoring/drafts/draft_<timestamp>_<slug>.json`.

## Optional Instruct-only LLM assist

No live LLM call is made unless you supply raw model output (offline authoring flow):

```bash
python tools/coverage_authoring/coverage_drafter.py \
  --question "Which DNS queries look like DGA activity?" \
  --use-llm \
  --llm-raw-file tools/coverage_authoring/tests/fixtures/llm_dga_entry.json \
  --llm-model-family instruct
```

**Foundation-sec-Reasoning** and reasoning providers are **rejected**.

## Manual / validate-only mode

Validate an existing draft:

```bash
python tools/coverage_authoring/coverage_drafter.py \
  --validate-draft tools/coverage_authoring/drafts/example.json
```

Validate a hand-edited entry JSON and write a draft:

```bash
python tools/coverage_authoring/coverage_drafter.py \
  --entry-json path/to/entry.json \
  --output tools/coverage_authoring/drafts/my_reviewed_draft.json
```

## Promotion to the runtime manifest

1. Review the draft JSON and fix `validation_errors` / warnings.
2. Confirm readiness, blockers, and governance flags.
3. **Manually** copy the `entry` object into `backend/app/coverage/pattern_coverage_v1.json`.
4. Run backend tests: `cd backend && python3 -m pytest app/tests/test_pattern_coverage_pack_stage3k_q4.py`
5. Update `docs/soc_pattern_coverage_pack_stage3k_q4.md` if the SOC-facing table changes.

Q4A never writes the committed manifest.

## Tests

```bash
PYTHONPATH=backend python3 -m pytest tools/coverage_authoring/tests -q
```
