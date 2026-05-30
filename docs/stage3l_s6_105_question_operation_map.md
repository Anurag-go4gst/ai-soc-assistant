# Stage 3L-S6.2: 105-Question Operation Mapping (Provisional Report)

**Status:** S6.2 report generated from shared builder (2026-05-30).

**Machine-readable:** [`stage3l_s6_105_question_operation_map.json`](stage3l_s6_105_question_operation_map.json)  
**Runtime shadow (S6.1):** [`backend/app/coverage/question_runtime_map_v1.json`](../backend/app/coverage/question_runtime_map_v1.json)

## Source of truth

| Layer | Artifact | Role |
|-------|----------|------|
| Inputs | [`docs/soc_question_taxonomy_stage3k_q0.md`](soc_question_taxonomy_stage3k_q0.md) + [`pattern_coverage_v1.json`](../backend/app/coverage/pattern_coverage_v1.json) | Committed taxonomy and manifest overlay only |
| Builder | [`tools/coverage_authoring/question_runtime_map_builder.py`](../tools/coverage_authoring/question_runtime_map_builder.py) | Single pass generates S6.1 + S6.2 |
| S6.1 | `backend/app/coverage/question_runtime_map_v1.json` | Runtime shadow input — **regenerate, do not hand-edit** |
| S6.2 | `docs/stage3l_s6_105_question_operation_map.json` | Provisional report — **regenerate, do not hand-edit** |

**Do not** use untracked `docs/input/soc_team_questions_stage3kq0.txt` for CI.

**Drift rule:** If S6.1 runtime map and S6.2 report diverge on `question_ref`, `proposed_primary_skill` / `likely_runtime_operation`, or manifest linkage, `check_question_operation_map.py` **must fail**.

## S6.1 vs S6.2

| | S6.1 | S6.2 |
|---|------|------|
| Purpose | Runtime-safe shadow enrichment | Human/provisional taxonomy analysis |
| Consumed by `/chat` | Yes (observation only) | **No** |
| Schema | Runtime map row (`proposed_primary_skill`, `promotion_status`, …) | Report fields (`provisional_status`, `dependency_type`, `notes`, …) |
| Readiness labels | `manifest_readiness` on map row when in manifest | Q4 readiness **only** when `promoted_to_manifest=true` |

S6.2 fields are **not** a second runtime contract.

## Regenerate

```bash
export PYTHONPATH=backend
python tools/coverage_authoring/coverage_drafter.py --emit-maps
python tools/coverage_authoring/check_question_operation_map.py
```

## Snapshot (regenerated)

| Metric | Value |
|--------|------:|
| Questions | 105 |
| Promoted to manifest | 10 |
| `likely_routable` | 48 |
| `likely_needs_detection` | 26 |
| `likely_needs_lookup` | 14 |
| `likely_needs_context` | 7 |
| `likely_multi_signal` | 7 |
| `likely_needs_review` | 2 |
| `likely_unsupported` | 1 |

## Audit

```bash
export PYTHONPATH=backend
python tools/coverage_authoring/check_question_operation_map.py
python tools/coverage_authoring/check_question_operation_map.py --json
```

## Non-goals

- Do not add 105 rows to `pattern_coverage_v1.json`
- Do not mark all 105 live-ready
- Do not change `/chat` routing or authority allowlist
- No MCP/SPL/LLM execution

## Tests

```bash
export PYTHONPATH=backend
python3 -m pytest tools/coverage_authoring/tests/test_question_operation_map_stage3l_s6_2.py -q
cd backend && python3 -m pytest app/tests/test_question_runtime_map_stage3l_s6.py -q
```
