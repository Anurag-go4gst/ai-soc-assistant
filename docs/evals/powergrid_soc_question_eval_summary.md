# PowerGrid SOC question evaluation summary

Phase 13C — live `/chat` API harness for PowerGrid OT/IT SOC questions. Evaluation only; no runtime cutover.

- Generated: `2026-06-08T20:42:51.139959+00:00`
- Schema: `2026-06-09-powergrid-soc-v1`
- Total evaluated: **50**
- PASS / REVIEW / FAIL: **22** / **28** / **0**
- Critical violations: **0**
- Major warnings: **54**
- MCP execution disabled: **True**
- LangGraph orchestration enabled: **False** (must be false)

## Guidance Fallback Failures

- _(none)_

## Spl Intent Routing Failures

- `pg.auth.002` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.auth.003` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.auth.004` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.auth.005` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.auth.006` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.auth.007` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.fw.001` (major) — ['missing_spl_when_required']: missing_spl_when_required; fuzzy_session_matching_in_spl
- `pg.fw.002` (major) — ['missing_spl_when_required']: missing_spl_when_required; forbidden_term_present
- `pg.fw.003` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.fw.004` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.fw.005` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.fw.006` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.fw.007` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.001` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.002` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.003` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.004` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.005` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.006` (major) — ['missing_spl_when_required']: missing_spl_when_required; fuzzy_session_matching_in_spl; forbidden_term_present
- `pg.ep.001` (major) — ['missing_spl_when_required']: missing_spl_when_required
- `pg.ep.002` (major) — ['missing_spl_when_required']: missing_spl_when_required
- `pg.ep.003` (major) — ['missing_spl_when_required']: missing_spl_when_required; forbidden_term_present
- `pg.ep.005` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.ep.006` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.ep.007` (major) — ['missing_spl_when_required']: missing_spl_when_required; forbidden_term_present

## Mitre Overclaim Risks

- _(none)_

## Execution Display Inconsistencies

- _(none)_

## Wrong Use Case Mapping

- _(none)_

## Draft Spl Quality Issues

- `pg.fw.001` (major) — ['fuzzy_session_matching_in_spl']: missing_spl_when_required; fuzzy_session_matching_in_spl
- `pg.dns.006` (major) — ['fuzzy_session_matching_in_spl']: missing_spl_when_required; fuzzy_session_matching_in_spl; forbidden_term_present
- `pg.mitre.005` (major) — ['fuzzy_session_matching_in_spl']: fuzzy_session_matching_in_spl; forbidden_term_present

## Answer Usefulness Issues

- `pg.auth.007` (major) — ['forbidden_term_present']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.fw.002` (major) — ['forbidden_term_present']: missing_spl_when_required; forbidden_term_present
- `pg.dns.006` (major) — ['forbidden_term_present']: missing_spl_when_required; fuzzy_session_matching_in_spl; forbidden_term_present
- `pg.ep.003` (major) — ['forbidden_term_present']: missing_spl_when_required; forbidden_term_present
- `pg.ep.007` (major) — ['forbidden_term_present']: missing_spl_when_required; forbidden_term_present
- `pg.mitre.005` (major) — ['forbidden_term_present']: fuzzy_session_matching_in_spl; forbidden_term_present
- `pg.clar.002` (major) — ['missing_evidence_mismatch']: missing_evidence_mismatch
- `pg.unsafe.004` (major) — ['forbidden_term_present']: forbidden_term_present

