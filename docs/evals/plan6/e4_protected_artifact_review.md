# Plan 6 E4 — protected-artifact review

Keep fail-closed **15/15**. No Plan 6 artifact is added to `PROTECTED`.

Eval reports under `docs/evals/plan6/` are evidence, not runtime-authoritative
generated artifacts. They are **not** automatically protected.

## `PROTECTED` membership (unchanged, 15)

| Group | Members |
|---|---|
| eval_baselines (7) | `reference_knowledge_baseline.md`, `regression_baseline.md`, `paraphrase_baseline.md`, `intent_out_of_set_probes_baseline.json`, `out_of_catalog_ot_probe_baseline.json`, `baseline_pre_final_resolution.json`, `routing_truth_set_baseline_v1.json` |
| golden_answers (1) | `question_105_golden.jsonl` |
| governed_registries (4) | `use_cases/catalog.json`, `skills/catalog.json`, `spl/templates.json`, `question_runtime_map_v1.json` |
| published_doc_mirrors (3) | `docs/architecture/details.html` and the two frontend copies |

**Added in Plan 6:** none.

Runtime map and catalog hashes are unchanged from E1/E2 (no promoter).

## Considered and left unprotected (evidence)

| Artifact | Why not `PROTECTED` |
|---|---|
| `docs/evals/plan6/**` (reports, JSON, run captures, corpus) | Plan 6 evidence. Regenerating a run log must not fail the freeze gate. |
| `docs/evals/plan6/vps_corpus_v1.json` | Query list for the VPS harness, not a runtime lookup. |
| `docs/evals/plan6/env_capture.schema.json` | Schema for redacted captures; not loaded by `/chat`. |
| `scripts/eval_plan6_*.py`, `backend/app/evals/plan6_*.py` | Code, not generated runtime artifacts. |
| Six stale governance reports (E3 CONTINUE PRESERVING) | Explicitly not protected; revert after governance. |

## Failing-first pin (already shipped, Plan 5 A4.5)

`test_check_fails_closed_when_a_declared_artifact_is_unrecorded` asserts `--check`
exits non-zero if a `PROTECTED` member is missing from the committed manifest.

## Verify

```text
python3 scripts/freeze_execution_baseline.py --check
→ protected artifacts unchanged (15 checked)

pytest backend/app/tests/test_freeze_execution_baseline_durability.py -q
→ 5 passed
```
