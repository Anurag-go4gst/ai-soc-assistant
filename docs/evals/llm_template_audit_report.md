# LLM Template Audit Report (Phase F)

Generated: 2026-06-13T11:28:51.621225+00:00
Active templates: 10
Pass: 8 · Review: 2

| template_id | use_case_id | approved | relevant | pipes | status | findings |
|---|---|---:|---:|---:|---|---|
| auth_failed_login_spike | auth_failed_login_spike | yes | — | 4 | pass | — |
| auth_success_after_failure | auth_success_after_failure | yes | — | 6 | pass | — |
| auth_new_source_ip | auth_new_source_ip_login | yes | — | 4 | pass | — |
| auth_account_lockout_trend | auth_account_lockout_trend | yes | — | 2 | pass | — |
| aws_security_group_modifications | aws_security_group_modifications | yes | — | 3 | pass | — |
| aws_console_success_logins_by_user | aws_console_success_logins_by_user | yes | — | 3 | pass | — |
| aws_iam_policy_modifications | aws_iam_policy_modifications | yes | — | 3 | pass | — |
| auth_failed_login_top_users_exclude_service_accounts | auth_failed_login_top_users_exclude_service_accounts | yes | — | 3 | pass | — |
| dns_beaconing_candidate | dns_beaconing_candidate | no | — | 10 | review | validation_failed:disallowed_sourcetype; verbosity_high |
| edr_powershell_suspicious_command | edr_powershell_suspicious_command | no | — | 5 | review | validation_failed:disallowed_sourcetype |
