# PowerGrid SOC question evaluation summary

Phase 13C — live `/chat` API harness for PowerGrid OT/IT SOC questions. Evaluation only; no runtime cutover.

- Generated: `2026-06-30T13:50:33.999932+00:00`
- Schema: `2026-06-09-powergrid-soc-v1`
- Total evaluated: **50**
- PASS / REVIEW / FAIL: **42** / **5** / **3**
- Critical violations: **3**
- Major warnings: **5**
- MCP execution disabled: **False**
- LangGraph orchestration enabled: **False** (must be false)
- Eval profile: **live_llm**

## LLM composer coverage

- Final synthesis enabled (backend): **True**
- Live synthesis enabled (backend): **False**
- Composer gate open (`composer_is_enabled`): **False**

- Composer eligible rows: **0** / 50
- Composer attempted rows: **0**
- Composer used rows (LLM prose applied): **0**
- Compose validation blocked rows: **0**
- Compose fallback rows: **0**
- Analyst-summary narration LLM called: **0**
- Answer-guard blocked rows: **4**
- Final-answer guard blocked rows: **0**
- Thin deterministic answer rows: **9**

### Skip categories

- `early_skip`: **16**
- `no_composer_trace`: **3**
- `other_skip`: **31**

### Skip / block reasons

- (20) `guidance_only_deterministic_envelope`
- (16) `composer_not_eligible`
- (5) `conceptual_mitre_deterministic_guidance`
- (3) `mitre_evidence_threshold_deterministic_guidance`
- (3) `unsafe_blocked_deterministic_guidance`

### Thin deterministic answer reasons

- `empty_answer`: **3**
- `guidance_only_insufficient_evidence`: **3**
- `short_deterministic_answer`: **3**

### Thin deterministic question IDs

`pg.auth.001`, `pg.auth.004`, `pg.auth.005`, `pg.auth.008`, `pg.auth.009`, `pg.fw.006`, `pg.dns.007`, `pg.dns.009`, `pg.ep.004`

## Guidance Fallback Failures

- `pg.auth.001` (major) — ['guidance_only_insufficient_evidence']: guidance_only_insufficient_evidence
- `pg.dns.009` (major) — ['guidance_only_insufficient_evidence']: guidance_only_insufficient_evidence
- `pg.ep.004` (major) — ['guidance_only_insufficient_evidence']: guidance_only_insufficient_evidence

## Spl Intent Routing Failures

- _(none)_

## Mitre Overclaim Risks

- `pg.dns.001` (major) — ['conceptual_mitre_no_direct_negation']: conceptual_mitre_no_direct_negation

## Execution Display Inconsistencies

- _(none)_

## Wrong Use Case Mapping

- _(none)_

## Draft Spl Quality Issues

- _(none)_

## Answer Usefulness Issues

- `pg.unsafe.001` (major) — ['forbidden_term_present']: forbidden_term_present

