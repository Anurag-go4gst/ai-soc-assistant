# Plan 5 A2 — STOP: the DRAFT and the committed runtime map disagree on 11 rows

A2 is implemented and correct in structure, but it cannot be closed without an authority decision.
No committed artifact has been modified.

## What A2 did

- New shared pure module `backend/app/threat/mitre_runtime_promotion.py` holding
  `registry_block_from_draft` + `runtime_patch_for_draft_item`. Extracted rather than imported from
  the promoter CLI because importing that module mutates `sys.path` at import time
  (`scripts/promote_mitre_registry_to_runtime.py:13`) — a side effect, per the extraction rule.
- `scripts/promote_mitre_registry_to_runtime.py` now imports the shared helper; its two local
  definitions (56 lines) were deleted. No duplicated MITRE patch logic remains.
  Verified: `--dry-run` → `questions 105/105, use_cases 42/65` (unchanged); backend MITRE suites
  `45 passed`.
- `tools/coverage_authoring/question_runtime_map_builder.py` gained `_apply_governed_mitre_registry`,
  applying the same patch with `row.update(...)` so key insertion order — and therefore byte
  identity — is preserved.

**Result: 7 of the 7 dropped governed fields are restored**, and the key order matches the committed
artifact exactly. `test_rebuild_preserves_every_committed_field` and
`test_governed_registry_block_survives_regeneration` now pass.

## The blocker

After the fix, **11 of 105 rows still differ**, in `mitre_candidate` and the nested
`mitre_registry.candidate`, and only those:

| question_ref | committed runtime map | DRAFT @ HEAD |
|---|---|---|
| `q0.q021`, `q0.q028`, `q0.q040` | `[]` | `['T1071']` |
| `q0.q046`, `q0.q047`, `q0.q060`, `q0.q062`, `q0.q089` | `[]` | `['T1110']` |
| `q0.q050`, `q0.q063`, `q0.q083` | `[]` | `['T1059.001']` |

Cause, traced through git:

- `1106dd3` added the DRAFT with `candidate: []` on these rows.
- `56b48d9` promoted that DRAFT into the runtime map — hence `[]` in the committed artifact.
- **`7ee7a34` ("disposition worklist + candidate-anchor promotions from LLM catalogue audit") later
  advanced the DRAFT**, adding these candidates — **and the promoter was never re-run.**

So the DRAFT is one curation commit ahead of the runtime map. This is a real generated-artifact
authority dependency that no prior plan recorded.

**It also reframes the A1 containment finding.** The 11 rows A1 measured as "broadening under
fallback" are exactly these 11. The fallback was not inventing claims — it was reading the newer
DRAFT. The broadening and the divergence are one defect, not two.

## Why this is a STOP and not an implementation choice

The two A2 acceptance criteria are, at these 11 rows, mutually exclusive:

- *"the builder must reproduce the existing governed artifact"* and *"zero new analyst-visible MITRE
  technique claims relative to the governed committed map"* → the builder must **not** take the
  DRAFT's candidates, which means the builder must ignore its own source of truth and silently
  discard an approved MITRE disposition.
- *"make the builder reproduce promoter-owned governed MITRE metadata"* from the authoritative source
  → the builder must take them, which **changes the committed runtime map on 11 rows** and broadens
  analyst-visible candidates.

Deciding which is correct requires knowing whether `7ee7a34`'s candidate-tier promotions were meant
to reach runtime. That is a MITRE governance decision, outside the approved Phase-A scope.

## Options (no work done on any)

1. **DRAFT is authoritative; the runtime map is stale.** Re-run the promoter, accept an 11-row change
   to the committed map, update the containment baseline to the post-promotion state. Honest, but it
   is a governed-artifact change and broadens analyst-visible candidates on 11 of 105 questions —
   needs the same scrutiny any MITRE widening gets.
2. **The runtime map is authoritative; the DRAFT curation was never approved for runtime.** Pin the
   builder to the committed candidate state and record `7ee7a34` as deliberately un-promoted. Keeps
   Phase A byte-idempotent and containment-clean, but the builder then no longer purely derives from
   its source, and the divergence persists as latent debt.
3. **Split the decision.** Land A2 with the 7 governed fields restored and the candidate fields
   sourced so the artifact is reproduced exactly (option 2 mechanics), and raise the DRAFT-vs-runtime
   promotion as its own scoped item with the 11-row diff attached.

Recommendation: **option 3**. It closes the containment regression now — which is the urgent part,
since a regeneration today silently broadens claims — without deciding a MITRE governance question
inside a builder-correctness item.

## Current repo state

Uncommitted, coherent, nothing governed modified:
`backend/app/threat/mitre_runtime_promotion.py` (new), `scripts/promote_mitre_registry_to_runtime.py`
(refactor), `question_runtime_map_builder.py` (patch applied), 2 new test files.
15 tests fail, all on these 11 rows; 35 pass. `question_runtime_map_v1.json` is **unmodified**.
