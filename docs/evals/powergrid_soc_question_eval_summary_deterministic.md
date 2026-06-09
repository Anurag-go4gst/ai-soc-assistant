# PowerGrid SOC question evaluation summary

Phase 13C — live `/chat` API harness for PowerGrid OT/IT SOC questions. Evaluation only; no runtime cutover.

- Generated: `2026-06-09T04:03:40.402568+00:00`
- Schema: `2026-06-09-powergrid-soc-v1`
- Total evaluated: **50**
- PASS / REVIEW / FAIL: **46** / **4** / **0**
- Critical violations: **0**
- Major warnings: **6**
- MCP execution disabled: **True**
- LangGraph orchestration enabled: **False** (must be false)
- Eval profile: **deterministic**
- LLM composer rows: **7**
- LLM live synthesis enabled: **False**

## Guidance Fallback Failures

- `pg.ep.002` (major) — ['guidance_only_insufficient_evidence']: guidance_only_insufficient_evidence

## Spl Intent Routing Failures

- _(none)_

## Mitre Overclaim Risks

- _(none)_

## Execution Display Inconsistencies

- _(none)_

## Wrong Use Case Mapping

- `pg.fw.001` (major) — ['firewall_labeled_auth_anomaly']: firewall_labeled_auth_anomaly; fuzzy_session_matching_in_spl; forbidden_term_present

## Draft Spl Quality Issues

- `pg.fw.001` (major) — ['fuzzy_session_matching_in_spl']: firewall_labeled_auth_anomaly; fuzzy_session_matching_in_spl; forbidden_term_present
- `pg.fw.002` (major) — ['fuzzy_session_matching_in_spl']: fuzzy_session_matching_in_spl
- `pg.fw.003` (major) — ['fuzzy_session_matching_in_spl']: fuzzy_session_matching_in_spl

## Answer Usefulness Issues

- `pg.fw.001` (major) — ['forbidden_term_present']: firewall_labeled_auth_anomaly; fuzzy_session_matching_in_spl; forbidden_term_present

