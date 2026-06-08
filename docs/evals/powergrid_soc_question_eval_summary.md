# PowerGrid SOC question evaluation summary

Phase 13C — live `/chat` API harness for PowerGrid OT/IT SOC questions. Evaluation only; no runtime cutover.

- Generated: `2026-06-08T20:45:57.459119+00:00`
- Schema: `2026-06-09-powergrid-soc-v1`
- Total evaluated: **50**
- PASS / REVIEW / FAIL: **35** / **15** / **0**
- Critical violations: **0**
- Major warnings: **36**
- MCP execution disabled: **True**
- LangGraph orchestration enabled: **False** (must be false)

## Guidance Fallback Failures

- _(none)_

## Spl Intent Routing Failures

- `pg.auth.002` (major) — ['missing_spl_when_required', 'spl_question_says_not_required', 'success_after_failure_wrong_use_case']: spl_question_says_not_required; missing_spl_when_required; success_after_failure_wrong_use_case
- `pg.auth.003` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.fw.001` (major) — ['missing_spl_when_required']: missing_spl_when_required; firewall_labeled_auth_anomaly; fuzzy_session_matching_in_spl
- `pg.fw.003` (major) — ['missing_spl_when_required']: missing_spl_when_required; fuzzy_session_matching_in_spl
- `pg.fw.004` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.fw.007` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.fw.009` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.002` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.dns.003` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.dns.005` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.dns.006` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.ep.001` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required
- `pg.ep.003` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.ep.004` (major) — ['missing_spl_when_required', 'spl_question_says_not_required']: spl_question_says_not_required; missing_spl_when_required

## Mitre Overclaim Risks

- _(none)_

## Execution Display Inconsistencies

- _(none)_

## Wrong Use Case Mapping

- `pg.auth.002` (major) — ['success_after_failure_wrong_use_case']: spl_question_says_not_required; missing_spl_when_required; success_after_failure_wrong_use_case
- `pg.fw.001` (major) — ['firewall_labeled_auth_anomaly']: missing_spl_when_required; firewall_labeled_auth_anomaly; fuzzy_session_matching_in_spl

## Draft Spl Quality Issues

- `pg.fw.001` (major) — ['fuzzy_session_matching_in_spl']: missing_spl_when_required; firewall_labeled_auth_anomaly; fuzzy_session_matching_in_spl
- `pg.fw.002` (major) — ['fuzzy_session_matching_in_spl']: fuzzy_session_matching_in_spl
- `pg.fw.003` (major) — ['fuzzy_session_matching_in_spl']: missing_spl_when_required; fuzzy_session_matching_in_spl

## Answer Usefulness Issues

- `pg.auth.003` (major) — ['forbidden_term_present']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.fw.001` (major) — ['forbidden_term_present']: missing_spl_when_required; firewall_labeled_auth_anomaly; fuzzy_session_matching_in_spl
- `pg.dns.003` (major) — ['forbidden_term_present']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.dns.005` (major) — ['forbidden_term_present']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present
- `pg.ep.003` (major) — ['forbidden_term_present']: spl_question_says_not_required; missing_spl_when_required; forbidden_term_present

