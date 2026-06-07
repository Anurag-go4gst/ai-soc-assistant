# Skill Enrichment Status Matrix

Per **internal use case** implementation progress (docs only — not runtime).  
Updated with Batch 8 (2026-06-07). `backend/app/use_cases/content_enrichment.json` is the tracked enrichment baseline; docs remain metadata only and are not runtime prompt inputs.

**Status values:** `not_started` | `designed` | `content_added` | `mitre_added` | `spl_bound` | `tests_added` | `accepted` | `blocked`

| Internal Use Case | GitHub Reference | Live Skill | Planning Skill | MITRE Added | Evidence Added | SPL Template | Workflow Added | Answer Rules | RAG Added | Tests Added | Status |
| ----------------- | ---------------- | ---------- | -------------- | ----------- | -------------- | ------------ | -------------- | ------------ | --------- | ----------- | ------ |
| `auth_failed_login_spike` | `detecting-rdp-brute-force-attacks`, `triaging-security-alerts-in-splunk` | `attack_discovery` | `threshold_anomaly` | Metadata only | Yes | `active` | Yes | Yes | No | Yes | `tests_added` |
| `auth_success_after_failure` | `detecting-rdp-brute-force-attacks`, `triaging-security-alerts-in-splunk` | `attack_discovery` | `correlate_sequence` | Metadata only | Yes | `active` | Yes | Yes | No | Yes | `tests_added` |
| `email_phishing_header_review` | `analyzing-email-headers-for-phishing-investigation`, `triaging-security-alerts-in-splunk` | `attack_discovery` | `phishing_triage` | Metadata only | Yes | `planned` | Yes | Yes | No | Yes | `tests_added` |
| `edr_powershell_suspicious_command` | `hunting-for-anomalous-powershell-execution` | `attack_discovery` | `suspicious_command_execution` | Metadata only | Yes | `active` | Yes | Yes | No | Yes | `tests_added` |
| `dns_beaconing_candidate` | `hunting-for-command-and-control-beaconing` | `attack_discovery` | `beaconing_pattern_review` | Metadata only | Yes | `active` | Yes | Yes | No | Yes | `tests_added` |
| `soc_incident_triage` | `triaging-security-incident-with-ir-playbook` | `alert_summary` | `incident_triage_playbook` | Metadata only | Yes | `unavailable` | Yes | Yes | No | Yes | `tests_added` |
| `endpoint_ransomware_impact_review` | `analyzing-ransomware-encryption-mechanisms`, `triaging-security-incident-with-ir-playbook` | `attack_discovery` | `ransomware_impact_review` | Metadata only | Yes | `planned` | Yes | Yes | No | Yes | `tests_added` |

### Notes

- **Active records:** `auth_failed_login_spike`, `auth_success_after_failure`, `edr_powershell_suspicious_command`, `dns_beaconing_candidate`.
- **Planned records:** `email_phishing_header_review`, `soc_incident_triage`, `endpoint_ransomware_impact_review`; enrichment may ship before new 105-question rows or catalog entries.
- **Cross-cutting** `triaging-security-alerts-in-splunk` supports multiple rows above; no separate use-case row.
- **Next:** Add explicit offline question-to-use-case mappings only from defensible sources; do not infer from skill similarity.
