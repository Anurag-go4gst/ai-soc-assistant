# Pilot Evidence Contracts — Batch 3.1

**Purpose:** Document and verify MITRE evidence-status + SPL governance for Batch 3 pilots before Batch 4 pipeline refactors.  
**Authority:** `backend/app/use_cases/content_enrichment.json` (metadata) + `mitre_evidence_preconditions.evaluate_pilot_mitre_evidence_status` + `mitre_decision.resolve_mitre_decision` (runtime).  
**Tests:** `backend/app/tests/test_batch3_pilot_output_contracts.py`, `test_mitre_spl_governance_batch3.py`

---

## Global rules

| Rule | Behavior |
|------|----------|
| MITRE registry metadata | Permitted/candidate only — **not** observed evidence |
| Status vocabulary | `candidate`, `evidence_supported`, `requires_validation`, `not_claimed`, `ruled_out` (additive on `MitreDecision.evidence_statuses`; legacy `techniques` / `not_claimed` lists preserved) |
| SPL templates | `active` → governed template + `validate_spl()`; `planned` / `unavailable` → governed limitation, **no** free LLM fallback outside lab |
| Unsafe wording | Blocked by enrichment `answer_rules` + analyst card phrasing (verified in tests/goldens) |

---

## P1 — `auth_failed_login_spike` (active)

| Field | Contract |
|-------|----------|
| **Required evidence** | user, src, host, fail_count, time_window, first_failure, last_failure |
| **Optional evidence** | (threshold context in query signals) |
| **Missing evidence** | T1110.x stays `candidate`; T1078 → `not_claimed` (failed logins alone) |
| **MITRE candidates** | T1110, T1110.001, T1110.003; T1078 only with success/valid-account misuse context |
| **MITRE status rules** | `failed_login_pattern` → T1110/T1110.001 `evidence_supported`; T1078 rejected without success |
| **SPL template** | `active` — `auth_failed_login_spike` |
| **Answer limitations** | No account compromise from failures alone; SPL/execution review-gated |

**Output verification:** `test_mitre_failed_login_context_maps_t1110_and_blocks_negated_techniques` (golden); `test_failed_login_spike_supports_bruteforce_but_not_valid_accounts` (unit).

---

## P2 — `auth_success_after_failure` (active)

| Field | Contract |
|-------|----------|
| **Required evidence** | user, src, host, fail_count, success_count, first_failure, last_success |
| **MITRE status rules** | T1110.001 `evidence_supported` when failures + success; T1078 `candidate` unless stronger misuse evidence (`source_ip_novelty`, `post_login_activity`, etc.) |
| **SPL template** | `active` — `auth_success_after_failure` |
| **Answer limitations** | Say “successful login after failures observed”; **not** “account compromised” without stronger evidence |

**Output verification:** `test_alt_2024_0891_success_after_failure_hybrid_alert_review` (golden); `test_success_after_failures_supports_t1110_but_t1078_stays_candidate` (unit).

---

## P4 — `edr_powershell_suspicious_command` (active catalog, SPL active)

| Field | Contract |
|-------|----------|
| **Required evidence** | host, user, command_line, script_block_text, event_id, parent_process, encoded_command_flag, network_connection |
| **MITRE status rules** | T1059.001 `candidate` without command evidence; `evidence_supported` with `powershell_command_evidence` / `encoded_command` / script-block signals |
| **SPL template** | `active` — `edr_powershell_suspicious_command`; normalized SPL remains validation/HIL gated |
| **Answer limitations** | Do not call malware without malware evidence |

**Output verification:** `test_powershell_status_requires_command_or_script_evidence`; chat path `test_powershell_active_spl_is_validated_and_review_gated_in_chat`.

---

## P5 — `dns_beaconing_candidate` (active catalog, SPL active)

| Field | Contract |
|-------|----------|
| **Required evidence** | src, dest, domain, periodicity, jitter, bytes_out, DNS_query_count, rare_domain_indicator, user_host_association |
| **MITRE status rules** | T1071 `candidate` with periodicity alone; `evidence_supported` requires periodicity + jitter + network telemetry |
| **SPL template** | `active` — `dns_beaconing_candidate`; normalized SPL remains validation/HIL gated |
| **Answer limitations** | Do not claim C2 confirmed from periodicity alone |

**Output verification:** `test_c2_requires_multiple_beaconing_signals`; chat path `test_beaconing_active_spl_is_validated_and_review_gated_in_chat`.

---

## P3 — `email_phishing_header_review` (planned — no catalog route yet)

| Field | Contract |
|-------|----------|
| **Required evidence** | sender, return_path, reply_to, SPF/DKIM/DMARC, URLs/domains, attachments/hashes, recipients, mail_gateway_verdict |
| **MITRE status rules** | T1566.x `candidate` on single mismatch; `evidence_supported` needs multiple phishing indicators |
| **SPL template** | `planned` — no active template |
| **Runtime path** | Enrichment + MITRE resolver only until catalog/question mapping lands; **no fake active SPL** |

**Output verification:** `test_phishing_single_sender_mismatch_is_candidate_only`; `test_planned_use_case_spl_governance` (phishing).

---

## P6 — `soc_incident_triage` (planned)

| Field | Contract |
|-------|----------|
| **MITRE** | Empty candidate list — assign per alert evidence only |
| **SPL template** | `unavailable` |
| **Answer limitations** | SOP/IR guidance only; no destructive containment without HIL |

**Output verification:** enrichment contract + `test_planned_use_case_spl_governance` (IR triage).

---

## P7 — `endpoint_ransomware_impact_review` (planned)

| Field | Contract |
|-------|----------|
| **Required evidence** | file_rename_count, extension_pattern, affected_paths, process_name, shadow_copy_deletion_indicator, encryption_behavior |
| **MITRE status rules** | T1486 `candidate` on single signal; `evidence_supported` needs multiple impact signals |
| **SPL template** | `planned` |
| **Answer limitations** | No ransomware confirmed from file changes alone |

**Output verification:** `test_ransomware_requires_multiple_impact_signals`; `test_planned_use_case_spl_governance` (ransomware).

---

## SPL status matrix (pilots)

| Use case | `spl_template_status` | Expected output when SPL requested |
|----------|----------------------|-------------------------------------|
| auth_failed_login_spike | active | Normalized SPL + `spl_template_status=active` |
| auth_success_after_failure | active | Normalized SPL + `spl_template_status=active` |
| edr_powershell_suspicious_command | active | Normalized SPL + `spl_template_status=active`; execution remains review-gated |
| dns_beaconing_candidate | active | Normalized SPL + `spl_template_status=active`; execution remains review-gated |
| email_phishing_header_review | planned | Clarification + `governed_limitation` |
| soc_incident_triage | unavailable | Clarification + unavailable limitation |
| endpoint_ransomware_impact_review | planned | Clarification + `governed_limitation` |

---

## Trace / response — Batch 4 improvement candidates

Fields **visible today** (verify in `test_batch3_response_surface_audit`):

| Signal | Where |
|--------|--------|
| MITRE technique rows + Status | `analyst_response.mitre_mappings`, `mitre_mappings` |
| Not claimed | `analyst_response.not_claimed`, `mitre_decision.rejected_techniques` |
| Evidence-supported status | `mitre_decision.evidence_statuses` (additive dict) |
| SPL template status | `candidate_spl` / `spl_validation` payloads when enrichment wired (`spl_template_status`, `governed_limitation`) |
| HIL / execution | `human_review`, `execution`, `analyst_response.execution_status_label` |
| Limitations | `analyst_response.limitations`, enrichment limitations in trace when wired |

**Batch 4 landed (visibility):**

- Top-level `PlaceholderResponse.spl_template_status`, `mitre_evidence_status`, `node_trace`, `answer_guard_status`, `final_answer_safety_status` (control-plane gated)
- `control_plane_trace.node_trace` mirrors top-level `node_trace`
- Deterministic final-answer validator blocks unsafe compromise/C2/ransomware/malware/execution wording

**Still deferred:**

- Unified `session_context_status` (Batch A5 / session memory)

---

## Validation commands

```bash
python3 scripts/build_skill_coverage_matrix.py --check
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_mitre_spl_governance_batch3.py -q
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_skill_content_enrichment_baseline.py -q
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_batch3_pilot_output_contracts.py -q
./scripts/run_stage3_governance_regression.sh
```
