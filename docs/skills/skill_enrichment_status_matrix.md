# Skill Enrichment Status Matrix

Per **internal use case** implementation progress (docs only — not runtime).  
Updated with slice 0 (2026-06-06). Flip flags in `github_skill_intake_register.json` when Track B lands.

**Status values:** `not_started` | `designed` | `content_added` | `mitre_added` | `spl_bound` | `tests_added` | `accepted` | `blocked`

| Internal Use Case | GitHub Reference | Live Skill | Planning Skill | MITRE Added | Evidence Added | SPL Template | Workflow Added | Answer Rules | RAG Added | Tests Added | Status |
| ----------------- | ---------------- | ---------- | -------------- | ----------- | -------------- | ------------ | -------------- | ------------ | --------- | ----------- | ------ |
| `auth_failed_login_spike` | `detecting-rdp-brute-force-attacks`, `triaging-security-alerts-in-splunk` | `attack_discovery` | `threshold_anomaly` | No | Designed (§I P1) | `active` | No | No | No | No | `designed` |
| `auth_success_after_failure` | `detecting-rdp-brute-force-attacks`, `triaging-security-alerts-in-splunk` | `attack_discovery` | `sequence_detection` | No | Designed (§I P2) | `active` | No | No | No | No | `designed` |
| `email_phishing_header_review` | `analyzing-email-headers-for-phishing-investigation` | `attack_discovery` | `phishing_triage` | No | Designed (§I P3) | `planned` | No | No | No | No | `designed` |
| `edr_powershell_suspicious_command` | `hunting-for-anomalous-powershell-execution` | `attack_discovery` | `suspicious_command_execution` | No | Designed (§I P4) | `planned` | No | No | No | No | `designed` |
| `dns_beaconing_candidate` | `hunting-for-command-and-control-beaconing` | `attack_discovery` | `beaconing_pattern_review` | No | Designed (§I P5) | `planned` | No | No | No | No | `designed` |
| `soc_incident_triage` | `triaging-security-incident-with-ir-playbook`, `triaging-security-alerts-in-splunk` | `alert_summary` | `incident_triage_playbook` | No | Designed (§I P6) | N/A | No | No | No | No | `designed` |
| `endpoint_ransomware_impact_review` | `analyzing-ransomware-encryption-mechanisms`, `triaging-security-incident-with-ir-playbook` | `attack_discovery` | `ransomware_impact_review` | No | Designed (§I P7) | `planned` | No | No | No | No | `designed` |

### Notes

- **Proposed use cases** (`email_phishing_header_review`, `soc_incident_triage`, `endpoint_ransomware_impact_review`): enrichment may ship before new 105-question rows or catalog entries (locked policy §B8).
- **Cross-cutting** `triaging-security-alerts-in-splunk` supports multiple rows above; no separate use-case row.
- **Next:** Track B adds `content_enrichment` to catalog → update this matrix and intake `implementation_status` flags together.
