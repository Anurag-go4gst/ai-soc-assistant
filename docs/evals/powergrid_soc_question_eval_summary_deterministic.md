# PowerGrid SOC question evaluation summary

Phase 13C — live `/chat` API harness for PowerGrid OT/IT SOC questions. Evaluation only; no runtime cutover.

- Generated: `2026-06-11T11:18:51.857043+00:00`
- Schema: `2026-06-09-powergrid-soc-v1`
- Total evaluated: **50**
- PASS / REVIEW / FAIL: **50** / **0** / **0**
- Critical violations: **0**
- Major warnings: **0**
- MCP execution disabled: **True**
- LangGraph orchestration enabled: **False** (must be false)
- Eval profile: **deterministic**

## LLM composer coverage

- Final synthesis enabled (backend): **True**
- Live synthesis enabled (backend): **True**
- Composer gate open (`composer_is_enabled`): **True**

- Composer eligible rows: **50** / 50
- Composer attempted rows: **8**
- Composer used rows (LLM prose applied): **8**
- Compose validation blocked rows: **0**
- Compose fallback rows: **0**
- Analyst-summary narration LLM called: **0**
- Answer-guard blocked rows: **1**
- Final-answer guard blocked rows: **0**
- Thin deterministic answer rows: **1**

### Skip categories

- `early_skip`: **7**
- `other_skip`: **35**

### Skip / block reasons

- (24) `guidance_only_deterministic_envelope`
- (7) `draft_spl_preview_active`
- (5) `conceptual_mitre_deterministic_guidance`
- (3) `mitre_evidence_threshold_deterministic_guidance`
- (3) `unsafe_blocked_deterministic_guidance`

### Thin deterministic answer reasons

- `short_deterministic_answer`: **1**

### Thin deterministic question IDs

`pg.dns.010`

## Guidance Fallback Failures

- _(none)_

## Spl Intent Routing Failures

- _(none)_

## Mitre Overclaim Risks

- _(none)_

## Execution Display Inconsistencies

- _(none)_

## Wrong Use Case Mapping

- _(none)_

## Draft Spl Quality Issues

- _(none)_

## Answer Usefulness Issues

- _(none)_

