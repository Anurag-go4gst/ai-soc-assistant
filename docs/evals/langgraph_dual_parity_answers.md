# LangGraph dual-run parity human-review details

Imperative vs shadow graph structured comparison — prose differences are not failures.

- Generated: `2026-06-08T12:36:04.228551+00:00`
- Schema: `2026-06-08-phase13-details-v1`
- Total evaluated: **120**
- Exact matches: **120**
- Acceptable differences: **0**
- Mismatches: **0**

## 1. `q0.q001` — exact_match

- **Source:** 105_map

### Question

What incident or alert network events are high or critical right now?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 2. `q0.q002` — exact_match

- **Source:** 105_map

### Question

Which source IPs generated the most outbound connections?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 3. `q0.q003` — exact_match

- **Source:** 105_map

### Question

Which destination IPs received the most connections?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 4. `q0.q004` — exact_match

- **Source:** 105_map

### Question

Which hosts contacted known malicious IPs today?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 5. `q0.q005` — exact_match

- **Source:** 105_map

### Question

Which hosts contacted suspicious external domains?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 6. `q0.q006` — exact_match

- **Source:** 105_map

### Question

Which DNS queries have unusually long names?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 7. `q0.q007` — exact_match

- **Source:** 105_map

### Question

Which DNS queries look like DGA activity?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 8. `q0.q008` — exact_match

- **Source:** 105_map

### Question

Which hosts show possible beaconing behavior?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "src",
      "dest",
      "domain",
      "periodicity",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "rare_domain_indicator",
      "user_host_association"
    ],
    "optional_evidence_keys": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "present_evidence_keys": [],
    "missing_required_evidence": [
      "src",
      "dest",
      "domain",
      "periodicity",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "rare_domain_indicator",
      "user_host_association"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Measure periodicity and jitter.",
      "Check bytes out and DNS query count.",
      "Assess domain rarity and destination context.",
      "Tie traffic to a host or user before impact language."
    ],
    "investigation_workflow": [
      "Review periodicity, jitter, outbound volume, and domain rarity together.",
      "Associate source with user or host identity when possible.",
      "Escalate from candidate to evidence-supported only when multiple signals align."
    ],
    "answer_rules": [
      "Do not claim C2 confirmed from periodicity alone.",
      "Use candidate/evidence-supported wording based on multiple signals."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [],
    "limitations": [
      "Periodic traffic may be benign polling or monitoring.",
      "Parent T1071 is used unless evidence supports a specific sub-technique."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "dns_beaconing_candidate",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1071"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 9. `q0.q009` — exact_match

- **Source:** 105_map

### Question

Which hosts communicated with many unique external IPs?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 10. `q0.q010` — exact_match

- **Source:** 105_map

### Question

Which hosts are generating the most SMB traffic?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 11. `q0.q011` — exact_match

- **Source:** 105_map

### Question

Which hosts made SMB connections to many peers?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 12. `q0.q012` — exact_match

- **Source:** 105_map

### Question

Which systems used unusual destination ports?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 13. `q0.q013` — exact_match

- **Source:** 105_map

### Question

Which systems generated large outbound data transfers?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 14. `q0.q014` — exact_match

- **Source:** 105_map

### Question

Which hosts showed potential data exfiltration to cloud apps?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 15. `q0.q015` — exact_match

- **Source:** 105_map

### Question

Which hosts have repeated connections to rare destinations?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "net_repeated_critical_asset_connections",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 16. `q0.q016` — exact_match

- **Source:** 105_map

### Question

Which hosts contacted the same external IP many times?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 17. `q0.q017` — exact_match

- **Source:** 105_map

### Question

Which hosts generated the most DNS queries?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 18. `q0.q018` — exact_match

- **Source:** 105_map

### Question

Which domains were queried by multiple hosts?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 19. `q0.q019` — exact_match

- **Source:** 105_map

### Question

Which hosts queried domains with suspicious subdomains?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 20. `q0.q020` — exact_match

- **Source:** 105_map

### Question

Which networks saw traffic to high-risk ports?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 21. `q0.q021` — exact_match

- **Source:** 105_map

### Question

Which hosts communicated with foreign IP ranges?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 22. `q0.q022` — exact_match

- **Source:** 105_map

### Question

Which hosts contacted IPs in an IOC lookup?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 23. `q0.q023` — exact_match

- **Source:** 105_map

### Question

Which hosts showed possible command-and-control beaconing?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "src",
      "dest",
      "domain",
      "periodicity",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "rare_domain_indicator",
      "user_host_association"
    ],
    "optional_evidence_keys": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "present_evidence_keys": [],
    "missing_required_evidence": [
      "src",
      "dest",
      "domain",
      "periodicity",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "rare_domain_indicator",
      "user_host_association"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Measure periodicity and jitter.",
      "Check bytes out and DNS query count.",
      "Assess domain rarity and destination context.",
      "Tie traffic to a host or user before impact language."
    ],
    "investigation_workflow": [
      "Review periodicity, jitter, outbound volume, and domain rarity together.",
      "Associate source with user or host identity when possible.",
      "Escalate from candidate to evidence-supported only when multiple signals align."
    ],
    "answer_rules": [
      "Do not claim C2 confirmed from periodicity alone.",
      "Use candidate/evidence-supported wording based on multiple signals."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [],
    "limitations": [
      "Periodic traffic may be benign polling or monitoring.",
      "Parent T1071 is used unless evidence supports a specific sub-technique."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "dns_beaconing_candidate",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1071"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 24. `q0.q024` — exact_match

- **Source:** 105_map

### Question

Which internal hosts generated outbound traffic after DNS lookups?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 25. `q0.q025` — exact_match

- **Source:** 105_map

### Question

Which hosts used unusual protocols?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 26. `q0.q026` — exact_match

- **Source:** 105_map

### Question

Which hosts have unusually high connection counts to one destination?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 27. `q0.q027` — exact_match

- **Source:** 105_map

### Question

Which DNS queries resolved to suspicious top-level domains?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 28. `q0.q028` — exact_match

- **Source:** 105_map

### Question

Which hosts showed peer-to-peer style communication?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 29. `q0.q029` — exact_match

- **Source:** 105_map

### Question

Which systems accessed the internet through rare ports?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 30. `q0.q030` — exact_match

- **Source:** 105_map

### Question

Which hosts contacted external IPs after hours?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 31. `q0.q031` — exact_match

- **Source:** 105_map

### Question

Which hosts repeatedly contacted the same destination at regular intervals?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 32. `q0.q032` — exact_match

- **Source:** 105_map

### Question

Which hosts had both DNS and network anomalies?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 33. `q0.q033` — exact_match

- **Source:** 105_map

### Question

Which hosts communicated with suspicious destination domains and IPs?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 34. `q0.q034` — exact_match

- **Source:** 105_map

### Question

Which destination IPs were contacted by many hosts?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 35. `q0.q035` — exact_match

- **Source:** 105_map

### Question

Which hosts generated the largest DNS response volumes?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 36. `q0.q036` — exact_match

- **Source:** 105_map

### Question

Which hosts reached known malicious domains from lookup data?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 37. `q0.q037` — exact_match

- **Source:** 105_map

### Question

Which hosts showed likely proxy or tunneling behavior?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 38. `q0.q038` — exact_match

- **Source:** 105_map

### Question

Which hosts had large inbound traffic from a single source?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 39. `q0.q039` — exact_match

- **Source:** 105_map

### Question

Which hosts downloaded large volumes from the internet?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 40. `q0.q040` — exact_match

- **Source:** 105_map

### Question

Which hosts initiated traffic to rare countries?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 41. `q0.q041` — exact_match

- **Source:** 105_map

### Question

Which systems have repeated hits to the same suspicious URL path?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 42. `q0.q042` — exact_match

- **Source:** 105_map

### Question

Which hosts contacted both malicious IPs and domains?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 43. `q0.q043` — exact_match

- **Source:** 105_map

### Question

Which hosts show consistent low-volume outbound connections?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 44. `q0.q044` — exact_match

- **Source:** 105_map

### Question

Which rules are generating the most alerts?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 45. `q0.q045` — exact_match

- **Source:** 105_map

### Question

What happened for this specific notable event?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 46. `q0.q046` — exact_match

- **Source:** 105_map

### Question

Which users have excessive failed logins?

### Path comparison

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": true,
    "needs_mitre": false,
    "spl_allowed": true,
    "mcp_allowed": true,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "live_investigation",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "time_window",
      "first_failure",
      "last_failure"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "fail_count",
      "failed_login_pattern",
      "first_failure",
      "last_failure"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "time_window"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Validate time window and threshold.",
      "Compare distinct users and sources.",
      "Check whether any successful authentication followed the failures.",
      "Review asset or account criticality before severity claims."
    ],
    "investigation_workflow": [
      "Scope authentication failures by user, source, host, and time window.",
      "Confirm threshold evidence before labeling brute-force activity evidence-supported.",
      "Pivot to success-after-failure only when successful authentication evidence exists.",
      "Keep SPL generation and execution behind existing validation and review gates."
    ],
    "answer_rules": [
      "Do not claim account compromise from failed logins alone.",
      "Mark brute force as evidence-supported only after threshold evidence exists.",
      "SPL/execution remains review-gated."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "asset_inventory"
    ],
    "limitations": [
      "Failed login telemetry alone does not establish credential validity.",
      "Source IP reuse, NAT, or scanner behavior may require analyst review."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_failed_login_spike",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110",
      "T1110.001",
      "T1110.003"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": {
    "use_case_id": "auth_failed_login_spike",
    "severity_label": "P3 Medium",
    "matched_rules": [
      "default_policy"
    ],
    "why_not_higher": [
      "P1 requires: success_after_failure, privileged_account_impacted, critical_asset, confirmed_success"
    ],
    "missing_evidence": [
      "success_after_failure",
      "privileged_account_impacted",
      "critical_asset",
      "confirmed_success"
    ],
    "source_refs": [],
    "recommended_priority": "standard_triage",
    "allowed_action_tier": 1
  },
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [
    "Failed login telemetry alone does not establish credential validity.",
    "Source IP reuse, NAT, or scanner behavior may require analyst review."
  ],
  "path_type": "spl_review",
  "selected_branches": [
    "spl",
    "evidence",
    "severity"
  ]
}
```

## 47. `q0.q047` — exact_match

- **Source:** 105_map

### Question

Is one IP attacking many accounts?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 48. `q0.q048` — exact_match

- **Source:** 105_map

### Question

Did a user log in from impossible locations?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 49. `q0.q049` — exact_match

- **Source:** 105_map

### Question

Which hosts ran suspicious PowerShell?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "host",
      "user",
      "command_line",
      "script_block_text",
      "event_id",
      "parent_process",
      "encoded_command_flag",
      "network_connection"
    ],
    "optional_evidence_keys": [
      "malware",
      "ransomware",
      "credential_dumping",
      "account_compromise"
    ],
    "present_evidence_keys": [],
    "missing_required_evidence": [
      "host",
      "user",
      "command_line",
      "script_block_text",
      "event_id",
      "parent_process",
      "encoded_command_flag",
      "network_connection"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Review event ID and script block text.",
      "Check parent process and user context.",
      "Identify encoded-command usage.",
      "Look for related network connections or child processes."
    ],
    "investigation_workflow": [
      "Collect process, command line, parent process, and script block evidence.",
      "Flag encoded command or suspicious invocation patterns as evidence, not malware verdicts.",
      "Pivot to network and child-process activity when available."
    ],
    "answer_rules": [
      "Do not classify as malware unless malware evidence exists.",
      "State suspicious command execution evidence and required pivots."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "edr"
    ],
    "limitations": [
      "Administrative scripts may use PowerShell legitimately.",
      "Encoded command is a suspicious indicator, not a standalone malware verdict."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "malware",
      "ransomware",
      "credential_dumping",
      "account_compromise"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "edr_powershell_suspicious_command",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1059",
      "T1059.001"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 50. `q0.q050` — exact_match

- **Source:** 105_map

### Question

Did Office apps spawn cmd or PowerShell?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 51. `q0.q051` — exact_match

- **Source:** 105_map

### Question

What unusual processes ran on critical servers?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 52. `q0.q052` — exact_match

- **Source:** 105_map

### Question

Did any host contact known malicious IPs?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 53. `q0.q053` — exact_match

- **Source:** 105_map

### Question

Are there suspicious DNS queries indicating C2 or DGA behavior?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 54. `q0.q054` — exact_match

- **Source:** 105_map

### Question

Who is sending large amounts of data outbound?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 55. `q0.q055` — exact_match

- **Source:** 105_map

### Question

Did anyone get added to Administrators?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 56. `q0.q056` — exact_match

- **Source:** 105_map

### Question

Which users are logging in outside normal hours?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 57. `q0.q057` — exact_match

- **Source:** 105_map

### Question

Did any endpoint run this suspicious hash?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 58. `q0.q058` — exact_match

- **Source:** 105_map

### Question

Which users or hosts have the highest risk scores?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 59. `q0.q059` — exact_match

- **Source:** 105_map

### Question

Which source IPs generated the most authentication failures today?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "time_window",
      "first_failure",
      "last_failure"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "time_window"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "fail_count",
      "first_failure",
      "last_failure"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Validate time window and threshold.",
      "Compare distinct users and sources.",
      "Check whether any successful authentication followed the failures.",
      "Review asset or account criticality before severity claims."
    ],
    "investigation_workflow": [
      "Scope authentication failures by user, source, host, and time window.",
      "Confirm threshold evidence before labeling brute-force activity evidence-supported.",
      "Pivot to success-after-failure only when successful authentication evidence exists.",
      "Keep SPL generation and execution behind existing validation and review gates."
    ],
    "answer_rules": [
      "Do not claim account compromise from failed logins alone.",
      "Mark brute force as evidence-supported only after threshold evidence exists.",
      "SPL/execution remains review-gated."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "asset_inventory"
    ],
    "limitations": [
      "Failed login telemetry alone does not establish credential validity.",
      "Source IP reuse, NAT, or scanner behavior may require analyst review."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_failed_login_spike",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110",
      "T1110.001",
      "T1110.003"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 60. `q0.q060` — exact_match

- **Source:** 105_map

### Question

Which accounts had a successful login after repeated failures?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "success_count",
      "first_failure",
      "last_success",
      "source_ip_novelty"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "fail_count",
      "first_failure",
      "last_success",
      "success_count"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "source_ip_novelty"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Confirm failure and success event ordering.",
      "Review whether the source is known for the user.",
      "Check privileged account or critical asset context.",
      "Look for follow-on activity before compromise language."
    ],
    "investigation_workflow": [
      "Correlate failures followed by successful authentication for the same user, source, host, and time window.",
      "Check source IP novelty where available.",
      "Keep Valid Accounts as a candidate unless additional misuse evidence exists."
    ],
    "answer_rules": [
      "State 'successful login after failures observed.'",
      "Do not state 'compromised account' unless additional evidence exists.",
      "T1078 remains candidate unless stronger account-misuse evidence exists."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "identity"
    ],
    "limitations": [
      "Sequence evidence can be benign if the user retried successfully.",
      "Novelty is optional and may be unavailable in current telemetry."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_success_after_failure",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110.001",
      "T1078"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 61. `q0.q061` — exact_match

- **Source:** 105_map

### Question

Which users logged in from new countries today?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 62. `q0.q062` — exact_match

- **Source:** 105_map

### Question

Which hosts show a spike in failed logins?

### Path comparison

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": true,
    "needs_mitre": false,
    "spl_allowed": true,
    "mcp_allowed": true,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "live_investigation",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "time_window",
      "first_failure",
      "last_failure"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "fail_count",
      "failed_login_pattern",
      "first_failure",
      "last_failure"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "time_window"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Validate time window and threshold.",
      "Compare distinct users and sources.",
      "Check whether any successful authentication followed the failures.",
      "Review asset or account criticality before severity claims."
    ],
    "investigation_workflow": [
      "Scope authentication failures by user, source, host, and time window.",
      "Confirm threshold evidence before labeling brute-force activity evidence-supported.",
      "Pivot to success-after-failure only when successful authentication evidence exists.",
      "Keep SPL generation and execution behind existing validation and review gates."
    ],
    "answer_rules": [
      "Do not claim account compromise from failed logins alone.",
      "Mark brute force as evidence-supported only after threshold evidence exists.",
      "SPL/execution remains review-gated."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "asset_inventory"
    ],
    "limitations": [
      "Failed login telemetry alone does not establish credential validity.",
      "Source IP reuse, NAT, or scanner behavior may require analyst review."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_failed_login_spike",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110",
      "T1110.001",
      "T1110.003"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": {
    "use_case_id": "auth_failed_login_spike",
    "severity_label": "P3 Medium",
    "matched_rules": [
      "default_policy"
    ],
    "why_not_higher": [
      "P1 requires: success_after_failure, privileged_account_impacted, critical_asset, confirmed_success"
    ],
    "missing_evidence": [
      "success_after_failure",
      "privileged_account_impacted",
      "critical_asset",
      "confirmed_success"
    ],
    "source_refs": [],
    "recommended_priority": "standard_triage",
    "allowed_action_tier": 1
  },
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [
    "Failed login telemetry alone does not establish credential validity.",
    "Source IP reuse, NAT, or scanner behavior may require analyst review."
  ],
  "path_type": "spl_review",
  "selected_branches": [
    "spl",
    "evidence",
    "severity"
  ]
}
```

## 63. `q0.q063` — exact_match

- **Source:** 105_map

### Question

Which endpoints spawned script interpreters recently?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 64. `q0.q064` — exact_match

- **Source:** 105_map

### Question

Which hosts executed encoded PowerShell commands?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 65. `q0.q065` — exact_match

- **Source:** 105_map

### Question

Which endpoints created new scheduled tasks?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "edr_scheduled_task_creation",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 66. `q0.q066` — exact_match

- **Source:** 105_map

### Question

Which systems contacted rare external destinations?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 67. `q0.q067` — exact_match

- **Source:** 105_map

### Question

Which hosts are generating unusual DNS query volumes?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "dns_unusual_query_volume",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 68. `q0.q068` — exact_match

- **Source:** 105_map

### Question

Which internal hosts contacted known command-and-control domains?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 69. `q0.q069` — exact_match

- **Source:** 105_map

### Question

Which users accessed privileged applications unusually?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 70. `q0.q070` — exact_match

- **Source:** 105_map

### Question

Which users changed their password multiple times in a short window?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 71. `q0.q071` — exact_match

- **Source:** 105_map

### Question

Which accounts were disabled or re-enabled today?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 72. `q0.q072` — exact_match

- **Source:** 105_map

### Question

Which hosts show signs of lateral movement?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "edr_lateral_movement_candidate",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 73. `q0.q073` — exact_match

- **Source:** 105_map

### Question

Which systems had multiple remote service creations?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 74. `q0.q074` — exact_match

- **Source:** 105_map

### Question

Which hosts show SMB connections to many peers?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 75. `q0.q075` — exact_match

- **Source:** 105_map

### Question

Which endpoints created suspicious archive files?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 76. `q0.q076` — exact_match

- **Source:** 105_map

### Question

Which hosts uploaded large amounts of data to cloud services?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 77. `q0.q077` — exact_match

- **Source:** 105_map

### Question

Which endpoints accessed USB storage recently?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 78. `q0.q078` — exact_match

- **Source:** 105_map

### Question

Which systems had repeated malware detections?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 79. `q0.q079` — exact_match

- **Source:** 105_map

### Question

Which files were modified by suspicious processes?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "edr_suspicious_process",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 80. `q0.q080` — exact_match

- **Source:** 105_map

### Question

Which hosts spawned shells from email clients?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 81. `q0.q081` — exact_match

- **Source:** 105_map

### Question

Which users received and opened phishing attachments?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 82. `q0.q082` — exact_match

- **Source:** 105_map

### Question

Which domains were queried by multiple hosts in a short period?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 83. `q0.q083` — exact_match

- **Source:** 105_map

### Question

Which hosts have suspicious parent-child process chains?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 84. `q0.q084` — exact_match

- **Source:** 105_map

### Question

Which accounts have the most risk events?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 85. `q0.q085` — exact_match

- **Source:** 105_map

### Question

Which assets have accumulated risk from multiple detections?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 86. `q0.q086` — exact_match

- **Source:** 105_map

### Question

Which users were involved in both failed logins and privilege changes?

### Path comparison

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": true,
    "needs_mitre": false,
    "spl_allowed": true,
    "mcp_allowed": true,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "live_investigation",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "time_window",
      "first_failure",
      "last_failure"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "fail_count",
      "failed_login_pattern",
      "first_failure",
      "last_failure"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "time_window"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Validate time window and threshold.",
      "Compare distinct users and sources.",
      "Check whether any successful authentication followed the failures.",
      "Review asset or account criticality before severity claims."
    ],
    "investigation_workflow": [
      "Scope authentication failures by user, source, host, and time window.",
      "Confirm threshold evidence before labeling brute-force activity evidence-supported.",
      "Pivot to success-after-failure only when successful authentication evidence exists.",
      "Keep SPL generation and execution behind existing validation and review gates."
    ],
    "answer_rules": [
      "Do not claim account compromise from failed logins alone.",
      "Mark brute force as evidence-supported only after threshold evidence exists.",
      "SPL/execution remains review-gated."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "asset_inventory"
    ],
    "limitations": [
      "Failed login telemetry alone does not establish credential validity.",
      "Source IP reuse, NAT, or scanner behavior may require analyst review."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_failed_login_spike",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110",
      "T1110.001",
      "T1110.003"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": {
    "use_case_id": "auth_failed_login_spike",
    "severity_label": "P3 Medium",
    "matched_rules": [
      "default_policy"
    ],
    "why_not_higher": [
      "P1 requires: success_after_failure, privileged_account_impacted, critical_asset, confirmed_success"
    ],
    "missing_evidence": [
      "success_after_failure",
      "privileged_account_impacted",
      "critical_asset",
      "confirmed_success"
    ],
    "source_refs": [],
    "recommended_priority": "standard_triage",
    "allowed_action_tier": 1
  },
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [
    "Failed login telemetry alone does not establish credential validity.",
    "Source IP reuse, NAT, or scanner behavior may require analyst review."
  ],
  "path_type": "spl_review",
  "selected_branches": [
    "spl",
    "evidence",
    "severity"
  ]
}
```

## 87. `q0.q087` — exact_match

- **Source:** 105_map

### Question

Which hosts are communicating with unusual ports externally?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 88. `q0.q088` — exact_match

- **Source:** 105_map

### Question

Which endpoints have multiple persistence indicators?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 89. `q0.q089` — exact_match

- **Source:** 105_map

### Question

Which users authenticated to VPN after repeated MFA failures?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "time_window",
      "first_failure",
      "last_failure"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "fail_count",
      "time_window",
      "first_failure",
      "last_failure"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Validate time window and threshold.",
      "Compare distinct users and sources.",
      "Check whether any successful authentication followed the failures.",
      "Review asset or account criticality before severity claims."
    ],
    "investigation_workflow": [
      "Scope authentication failures by user, source, host, and time window.",
      "Confirm threshold evidence before labeling brute-force activity evidence-supported.",
      "Pivot to success-after-failure only when successful authentication evidence exists.",
      "Keep SPL generation and execution behind existing validation and review gates."
    ],
    "answer_rules": [
      "Do not claim account compromise from failed logins alone.",
      "Mark brute force as evidence-supported only after threshold evidence exists.",
      "SPL/execution remains review-gated."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "asset_inventory"
    ],
    "limitations": [
      "Failed login telemetry alone does not establish credential validity.",
      "Source IP reuse, NAT, or scanner behavior may require analyst review."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_failed_login_spike",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110",
      "T1110.001",
      "T1110.003"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 90. `q0.q090` — exact_match

- **Source:** 105_map

### Question

Which assets are generating the most notable events?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 91. `q0.q091` — exact_match

- **Source:** 105_map

### Question

Which alerts are still open and unresolved?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 92. `q0.q092` — exact_match

- **Source:** 105_map

### Question

Which users had access to sensitive systems and then large outbound transfers?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 93. `q0.q093` — exact_match

- **Source:** 105_map

### Question

Which hosts showed both process execution and suspicious DNS within 24 hours?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 94. `q0.q094` — exact_match

- **Source:** 105_map

### Question

Which logs are missing from key security sources?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 95. `q0.q095` — exact_match

- **Source:** 105_map

### Question

Which sources stopped sending events recently?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 96. `q0.q096` — exact_match

- **Source:** 105_map

### Question

Which users performed privileged actions from non-admin workstations?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 97. `q0.q097` — exact_match

- **Source:** 105_map

### Question

Which systems show signs of webshell activity?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 98. `q0.q098` — exact_match

- **Source:** 105_map

### Question

Which hosts downloaded executables from the internet?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 99. `q0.q099` — exact_match

- **Source:** 105_map

### Question

Which detections involved the same user and host repeatedly?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 100. `q0.q100` — exact_match

- **Source:** 105_map

### Question

Which users triggered multiple different detections?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 101. `q0.q101` — exact_match

- **Source:** 105_map

### Question

Which devices are generating the most endpoint alerts?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 102. `q0.q102` — exact_match

- **Source:** 105_map

### Question

Which users are accessing resources from unusual hosts?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 103. `q0.q103` — exact_match

- **Source:** 105_map

### Question

For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status?

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 104. `q0.q104` — exact_match

- **Source:** 105_map

### Question

What is the full activity timeline for a given entity in the N hours before and after a detection?

### Path comparison

- imperative path_type: `generic_soc_guidance`
- graph path_type: `generic_soc_guidance`
- imperative branches: `['evidence', 'rag']`
- graph branches: `['evidence', 'rag']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'rag_pipeline_prepare', 'rag_pipeline_retrieve', 'finalize']`

```json
{
  "rag_result": {
    "branch_scheduled": true,
    "needs_rag": true,
    "rag_phase": "rag_only",
    "answer_mode": "rag_only"
  },
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "rag_only",
    "rag_phase": "rag_only",
    "needs_rag": true,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": true,
    "requires_hil": false,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": "general_guidance_allowed",
    "reasons": [
      "knowledge_context_recommended"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [],
  "path_type": "generic_soc_guidance",
  "selected_branches": [
    "rag",
    "evidence"
  ]
}
```

## 105. `q0.q105` — exact_match

- **Source:** 105_map

### Question

Has this entity, IP, domain, or notable been seen or investigated before, and what was the prior disposition?

### Path comparison

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": true,
    "needs_mitre": false,
    "spl_allowed": true,
    "mcp_allowed": true,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": false,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "live_investigation"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": {
    "use_case_id": null,
    "severity_label": "P3 Medium",
    "matched_rules": [
      "default_no_policy"
    ],
    "why_not_higher": [
      "No use-case-specific severity policy is active yet."
    ],
    "missing_evidence": [],
    "source_refs": [],
    "recommended_priority": "standard_triage",
    "allowed_action_tier": 1
  },
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [],
  "path_type": "spl_review",
  "selected_branches": [
    "spl",
    "evidence",
    "severity"
  ]
}
```

## 106. `demo.failed_login_spike` — exact_match

- **Source:** demo_scenario

### Question

Investigate a spike of failed logins for a user/source

### Path comparison

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": true,
    "needs_mitre": false,
    "spl_allowed": true,
    "mcp_allowed": true,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "live_investigation",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "time_window",
      "first_failure",
      "last_failure"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "fail_count",
      "failed_login_pattern",
      "first_failure",
      "last_failure"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "time_window"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Validate time window and threshold.",
      "Compare distinct users and sources.",
      "Check whether any successful authentication followed the failures.",
      "Review asset or account criticality before severity claims."
    ],
    "investigation_workflow": [
      "Scope authentication failures by user, source, host, and time window.",
      "Confirm threshold evidence before labeling brute-force activity evidence-supported.",
      "Pivot to success-after-failure only when successful authentication evidence exists.",
      "Keep SPL generation and execution behind existing validation and review gates."
    ],
    "answer_rules": [
      "Do not claim account compromise from failed logins alone.",
      "Mark brute force as evidence-supported only after threshold evidence exists.",
      "SPL/execution remains review-gated."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "asset_inventory"
    ],
    "limitations": [
      "Failed login telemetry alone does not establish credential validity.",
      "Source IP reuse, NAT, or scanner behavior may require analyst review."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "valid_account_abuse",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_failed_login_spike",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110",
      "T1110.001",
      "T1110.003"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": {
    "use_case_id": "auth_failed_login_spike",
    "severity_label": "P3 Medium",
    "matched_rules": [
      "default_policy"
    ],
    "why_not_higher": [
      "P1 requires: success_after_failure, privileged_account_impacted, critical_asset, confirmed_success"
    ],
    "missing_evidence": [
      "success_after_failure",
      "privileged_account_impacted",
      "critical_asset",
      "confirmed_success"
    ],
    "source_refs": [],
    "recommended_priority": "standard_triage",
    "allowed_action_tier": 1
  },
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [
    "Failed login telemetry alone does not establish credential validity.",
    "Source IP reuse, NAT, or scanner behavior may require analyst review."
  ],
  "path_type": "spl_review",
  "selected_branches": [
    "spl",
    "evidence",
    "severity"
  ]
}
```

## 107. `demo.successful_login_after_failures` — exact_match

- **Source:** demo_scenario

### Question

Failed logins followed by a successful login from same user

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "success_count",
      "first_failure",
      "last_success",
      "source_ip_novelty"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "fail_count",
      "failed_login_pattern",
      "first_failure",
      "last_failure",
      "last_success",
      "success_count"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "source_ip_novelty"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Confirm failure and success event ordering.",
      "Review whether the source is known for the user.",
      "Check privileged account or critical asset context.",
      "Look for follow-on activity before compromise language."
    ],
    "investigation_workflow": [
      "Correlate failures followed by successful authentication for the same user, source, host, and time window.",
      "Check source IP novelty where available.",
      "Keep Valid Accounts as a candidate unless additional misuse evidence exists."
    ],
    "answer_rules": [
      "State 'successful login after failures observed.'",
      "Do not state 'compromised account' unless additional evidence exists.",
      "T1078 remains candidate unless stronger account-misuse evidence exists."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "identity"
    ],
    "limitations": [
      "Sequence evidence can be benign if the user retried successfully.",
      "Novelty is optional and may be unavailable in current telemetry."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_success_after_failure",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110.001",
      "T1078"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 108. `demo.dns_beaconing_candidate` — exact_match

- **Source:** demo_scenario

### Question

Possible periodic DNS beaconing to a rare domain

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "src",
      "dest",
      "domain",
      "periodicity",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "rare_domain_indicator",
      "user_host_association"
    ],
    "optional_evidence_keys": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "present_evidence_keys": [
      "domain",
      "periodicity",
      "rare_domain_indicator"
    ],
    "missing_required_evidence": [
      "src",
      "dest",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "user_host_association"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Measure periodicity and jitter.",
      "Check bytes out and DNS query count.",
      "Assess domain rarity and destination context.",
      "Tie traffic to a host or user before impact language."
    ],
    "investigation_workflow": [
      "Review periodicity, jitter, outbound volume, and domain rarity together.",
      "Associate source with user or host identity when possible.",
      "Escalate from candidate to evidence-supported only when multiple signals align."
    ],
    "answer_rules": [
      "Do not claim C2 confirmed from periodicity alone.",
      "Use candidate/evidence-supported wording based on multiple signals."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [],
    "limitations": [
      "Periodic traffic may be benign polling or monitoring.",
      "Parent T1071 is used unless evidence supports a specific sub-technique."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "dns_beaconing_candidate",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1071"
    ]
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification; curated_enrichment_evidence_requirements; missing_required_curated_evidence"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 109. `demo.suspicious_powershell` — exact_match

- **Source:** demo_scenario

### Question

Suspicious encoded PowerShell command on an endpoint

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 110. `demo.sop-only_query` — exact_match

- **Source:** demo_scenario

### Question

Show the SOP/runbook for brute-force handling (no SPL)

### Path comparison

- imperative path_type: `rag_only`
- graph path_type: `rag_only`
- imperative branches: `['rag']`
- graph branches: `['rag']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'rag_pipeline_prepare', 'rag_pipeline_retrieve', 'finalize']`

```json
{
  "rag_result": {
    "branch_scheduled": true,
    "needs_rag": true,
    "rag_phase": "rag_only",
    "answer_mode": "rag_only"
  },
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "rag_only",
    "rag_phase": "rag_only",
    "needs_rag": true,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": true,
    "policy_context_recommended": false,
    "requires_hil": false,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": "insufficient_policy_context",
    "reasons": [
      "policy_context_required"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "soc_show_sop",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [],
  "path_type": "rag_only",
  "selected_branches": [
    "rag"
  ]
}
```

## 111. `demo.mitre-only_without_alert_context` — exact_match

- **Source:** demo_scenario

### Question

Map this to MITRE (no alert/evidence provided)

### Path comparison

- imperative path_type: `mitre_context_required`
- graph path_type: `mitre_context_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "soc_map_alert_mitre",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "mitre_context_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "mitre_context_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 112. `demo.enrichment-only_pilot` — exact_match

- **Source:** demo_scenario

### Question

Review phishing email headers (design-only pilot)

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 113. `demo.unsafe_containment/execution_request` — exact_match

- **Source:** demo_scenario

### Question

Contain/isolate the host or run the query now

### Path comparison

- imperative path_type: `unsafe_blocked`
- graph path_type: `unsafe_blocked`
- imperative branches: `['block', 'hil', 'unsafe_blocked']`
- graph branches: `['block', 'hil', 'unsafe_blocked']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": {
    "path_type": "unsafe_blocked",
    "blocked_tools": [
      "spl",
      "mcp",
      "candidate_spl_execution",
      "mcp_execution",
      "spl_execution"
    ],
    "execution_enabled": false,
    "unsafe_blocked": true
  },
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [],
  "path_type": "unsafe_blocked",
  "selected_branches": [
    "unsafe_blocked",
    "hil",
    "block"
  ]
}
```

## 114. `manual.alt0891_hybrid` — exact_match

- **Source:** manual

### Question

For alert ALT-2024-0891, failed logins followed by a successful login from the same user in the last hour, give me severity, MITRE mapping with evidence status, missing evidence, and a governed SPL I can review but not execute.

### Path comparison

- imperative path_type: `hybrid_investigation`
- graph path_type: `hybrid_investigation`
- imperative branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- graph branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": {
    "branch_scheduled": true,
    "needs_rag": false,
    "rag_phase": "post_mcp",
    "answer_mode": "live_investigation"
  },
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "mcp",
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": false,
    "needs_mitre": true,
    "spl_allowed": true,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "hybrid_alert_review_severity_mitre_spl",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "user",
      "src",
      "host",
      "fail_count",
      "success_count",
      "first_failure",
      "last_success",
      "source_ip_novelty"
    ],
    "optional_evidence_keys": [
      "account_compromise",
      "credential_dumping",
      "malware"
    ],
    "present_evidence_keys": [
      "alert_type",
      "event_id",
      "fail_count",
      "failed_login_pattern",
      "first_failure",
      "last_failure",
      "last_success",
      "success_count",
      "time_window"
    ],
    "missing_required_evidence": [
      "user",
      "src",
      "host",
      "source_ip_novelty"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Confirm failure and success event ordering.",
      "Review whether the source is known for the user.",
      "Check privileged account or critical asset context.",
      "Look for follow-on activity before compromise language."
    ],
    "investigation_workflow": [
      "Correlate failures followed by successful authentication for the same user, source, host, and time window.",
      "Check source IP novelty where available.",
      "Keep Valid Accounts as a candidate unless additional misuse evidence exists."
    ],
    "answer_rules": [
      "State 'successful login after failures observed.'",
      "Do not state 'compromised account' unless additional evidence exists.",
      "T1078 remains candidate unless stronger account-misuse evidence exists."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "rag:sop",
      "mitre:enterprise",
      "identity"
    ],
    "limitations": [
      "Sequence evidence can be benign if the user retried successfully.",
      "Novelty is optional and may be unavailable in current telemetry."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "account_compromise",
      "credential_dumping",
      "malware"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "auth_success_after_failure",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1110.001",
      "T1078"
    ]
  },
  "mitre_branch_result": {
    "branch": {
      "branch_name": "mitre",
      "status": "completed",
      "branch_authority": "planner_mitre_branch",
      "ran": true,
      "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
      "use_case_id": "auth_success_after_failure",
      "question_ref": null,
      "mitre_decision": {
        "mitre_status": "evidence_supported",
        "techniques": [
          {
            "technique_id": "T1110.001",
            "name": "Password Guessing",
            "tactic": "Credential Access",
            "status": "evidence_supported",
            "evidence_status": "evidence_supported",
            "status_reason": "Repeated failures before a successful login support password guessing.",
            "evidence_keys": [
              "failed_login_pattern",
              "successful_login"
            ],
            "why": "Repeated failures before a successful login support password guessing.",
            "evidence_requirements": [
              "failed_authentication_count",
              "time_window",
              "source_or_user_distribution"
            ],
            "source_refs": [],
            "recommended_pivots": [
              "check_success_after_failure",
              "review_source_reputation",
              "check_privileged_users"
            ]
          },
          {
            "technique_id": "T1078",
            "name": "Valid Accounts",
            "tactic": "Initial Access / Persistence / Privilege Escalation / Defense Evasion",
            "status": "candidate",
            "evidence_status": "candidate",
            "status_reason": "Successful login after repeated failures is a Valid Accounts candidate; confirm account criticality, MFA result, source ownership, and post-login activity.",
            "evidence_keys": [],
            "why": "Successful login after repeated failures is a Valid Accounts candidate; confirm account criticality, MFA result, source ownership, and post-login activity.",
            "evidence_requirements": [
              "successful_authentication",
              "account_context",
              "source_context"
            ],
            "source_refs": [],
            "recommended_pivots": [
              "identity_context",
              "mfa_status",
              "session_activity"
            ]
          }
        ],
        "rejected_techniques": [
          "T1562.001",
          "T1003"
        ],
        "registry_candidates": [
          "T1110.001",
          "T1078"
        ],
        "not_claimed": [],
        "evidence_statuses": {
          "T1110.001": "evidence_supported",
          "T1078": "candidate"
        },
        "evidence_status_details": {
          "T1110.001": {
            "status": "evidence_supported",
            "reason": "Repeated failures before a successful login support password guessing.",
            "evidence_keys": [
              "failed_login_pattern",
              "successful_login"
            ]
          },
          "T1078": {
            "status": "candidate",
            "reason": "Successful login after failures observed; Valid Accounts remains candidate pending misuse evidence.",
            "evidence_keys": []
          }
        },
        "answer_visible": true,
        "requires_alert_context": false,
        "requires_more_context_for_supported_mapping": false,
        "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
        "registry_metadata": {
          "schema_version": "2026-06-control-plane-v1",
          "registry_role": "metadata_not_evidence",
          "mitre_permitted": [],
          "mitre_candidate": [
            "T1110.001",
            "T1078"
          ],
          "mitre_blocked": [
            "T1562.001",
            "T1003"
          ],
          "mitre_requires_evidence": true,
          "mitre_requires_alert_context": true,
          "mitre_visibility_policy": "answer_if_requested",
          "source_question_ref": null,
          "source_use_case_id": "auth_success_after_failure",
          "mapping_rationale": "Registry-level MITRE candidates for Successful login after failures. These are permitted/candidate mappings only; runtime mitre_decision must decide whether they are supported, candidate, trace-only, or hidden based on intent and evidence."
        }
      },
      "technique_statuses": [
        {
          "technique_id": "T1110.001",
          "status": "evidence_supported",
          "reason": "Repeated failures before a successful login support password guessing.",
          "evidence_keys": [
            "failed_login_pattern",
            "successful_login"
          ]
        },
        {
          "technique_id": "T1078",
          "status": "candidate",
          "reason": "Successful login after failures observed; Valid Accounts remains candidate pending misuse evidence.",
          "evidence_keys": []
        }
      ],
      "evidence_supported_mitre": [
        "T1110.001"
      ],
      "candidate_mitre": [
        "T1078"
      ],
      "requires_validation_mitre": [],
      "not_claimed_mitre": [
        "T1562.001",
        "T1003"
      ],
      "ruled_out_mitre": [],
      "metadata_only_candidates": [
        "T1110.001",
        "T1078"
      ]
    },
    "decision": {
      "mitre_status": "evidence_supported",
      "techniques": [
        {
          "technique_id": "T1110.001",
          "name": "Password Guessing",
          "tactic": "Credential Access",
          "status": "evidence_supported",
          "evidence_status": "evidence_supported",
          "status_reason": "Repeated failures before a successful login support password guessing.",
          "evidence_keys": [
            "failed_login_pattern",
            "successful_login"
          ],
          "why": "Repeated failures before a successful login support password guessing.",
          "evidence_requirements": [
            "failed_authentication_count",
            "time_window",
            "source_or_user_distribution"
          ],
          "source_refs": [],
          "recommended_pivots": [
            "check_success_after_failure",
            "review_source_reputation",
            "check_privileged_users"
          ]
        },
        {
          "technique_id": "T1078",
          "name": "Valid Accounts",
          "tactic": "Initial Access / Persistence / Privilege Escalation / Defense Evasion",
          "status": "candidate",
          "evidence_status": "candidate",
          "status_reason": "Successful login after repeated failures is a Valid Accounts candidate; confirm account criticality, MFA result, source ownership, and post-login activity.",
          "evidence_keys": [],
          "why": "Successful login after repeated failures is a Valid Accounts candidate; confirm account criticality, MFA result, source ownership, and post-login activity.",
          "evidence_requirements": [
            "successful_authentication",
            "account_context",
            "source_context"
          ],
          "source_refs": [],
          "recommended_pivots": [
            "identity_context",
            "mfa_status",
            "session_activity"
          ]
        }
      ],
      "rejected_techniques": [
        "T1562.001",
        "T1003"
      ],
      "registry_candidates": [
        "T1110.001",
        "T1078"
      ],
      "not_claimed": [],
      "evidence_statuses": {
        "T1110.001": "evidence_supported",
        "T1078": "candidate"
      },
      "evidence_status_details": {
        "T1110.001": {
          "status": "evidence_supported",
          "reason": "Repeated failures before a successful login support password guessing.",
          "evidence_keys": [
            "failed_login_pattern",
            "successful_login"
          ]
        },
        "T1078": {
          "status": "candidate",
          "reason": "Successful login after failures observed; Valid Accounts remains candidate pending misuse evidence.",
          "evidence_keys": []
        }
      },
      "answer_visible": true,
      "requires_alert_context": false,
      "requires_more_context_for_supported_mapping": false,
      "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
      "registry_metadata": {
        "schema_version": "2026-06-control-plane-v1",
        "registry_role": "metadata_not_evidence",
        "mitre_permitted": [],
        "mitre_candidate": [
          "T1110.001",
          "T1078"
        ],
        "mitre_blocked": [
          "T1562.001",
          "T1003"
        ],
        "mitre_requires_evidence": true,
        "mitre_requires_alert_context": true,
        "mitre_visibility_policy": "answer_if_requested",
        "source_question_ref": null,
        "source_use_case_id": "auth_success_after_failure",
        "mapping_rationale": "Registry-level MITRE candidates for Successful login after failures. These are permitted/candidate mappings only; runtime mitre_decision must decide whether they are supported, candidate, trace-only, or hidden based on intent and evidence."
      }
    }
  },
  "severity_result": {
    "use_case_id": "auth_success_after_failure",
    "severity_label": "P2 High",
    "matched_rules": [
      "default_policy"
    ],
    "why_not_higher": [
      "P1 requires: privileged_account_impacted, critical_asset, confirmed_success"
    ],
    "missing_evidence": [
      "privileged_account_impacted",
      "critical_asset",
      "confirmed_success"
    ],
    "source_refs": [],
    "recommended_priority": "high",
    "allowed_action_tier": 1
  },
  "hil_status": {
    "hil_required": false,
    "clarification_needed": false,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [
    "Sequence evidence can be benign if the user retried successfully.",
    "Novelty is optional and may be unavailable in current telemetry."
  ],
  "path_type": "hybrid_investigation",
  "selected_branches": [
    "spl",
    "rag",
    "evidence",
    "mitre",
    "severity",
    "hil"
  ]
}
```

## 115. `manual.brute_force_sop` — exact_match

- **Source:** manual

### Question

Show me the SOP for brute-force login investigation. Do not generate SPL unless required.

### Path comparison

- imperative path_type: `rag_only`
- graph path_type: `rag_only`
- imperative branches: `['rag']`
- graph branches: `['rag']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'rag_pipeline_prepare', 'rag_pipeline_retrieve', 'finalize']`

```json
{
  "rag_result": {
    "branch_scheduled": true,
    "needs_rag": true,
    "rag_phase": "rag_only",
    "answer_mode": "rag_only"
  },
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "rag_only",
    "rag_phase": "rag_only",
    "needs_rag": true,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": true,
    "policy_context_recommended": false,
    "requires_hil": false,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": "insufficient_policy_context",
    "reasons": [
      "policy_context_required"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "soc_show_sop",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": null,
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [],
  "path_type": "rag_only",
  "selected_branches": [
    "rag"
  ]
}
```

## 116. `manual.powershell_checklist` — exact_match

- **Source:** manual

### Question

For suspicious PowerShell command execution on an endpoint, give me the analyst checklist, required evidence, MITRE status, and governed SPL for review.

### Path comparison

- imperative path_type: `hybrid_investigation`
- graph path_type: `hybrid_investigation`
- imperative branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- graph branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": {
    "branch_scheduled": true,
    "needs_rag": false,
    "rag_phase": "post_mcp",
    "answer_mode": "live_investigation"
  },
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "mcp",
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": false,
    "needs_mitre": true,
    "spl_allowed": true,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "hybrid_alert_review_severity_mitre_spl",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "host",
      "user",
      "command_line",
      "script_block_text",
      "event_id",
      "parent_process",
      "encoded_command_flag",
      "network_connection"
    ],
    "optional_evidence_keys": [
      "malware",
      "ransomware",
      "credential_dumping",
      "account_compromise"
    ],
    "present_evidence_keys": [],
    "missing_required_evidence": [
      "host",
      "user",
      "command_line",
      "script_block_text",
      "event_id",
      "parent_process",
      "encoded_command_flag",
      "network_connection"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Review event ID and script block text.",
      "Check parent process and user context.",
      "Identify encoded-command usage.",
      "Look for related network connections or child processes."
    ],
    "investigation_workflow": [
      "Collect process, command line, parent process, and script block evidence.",
      "Flag encoded command or suspicious invocation patterns as evidence, not malware verdicts.",
      "Pivot to network and child-process activity when available."
    ],
    "answer_rules": [
      "Do not classify as malware unless malware evidence exists.",
      "State suspicious command execution evidence and required pivots."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [
      "edr"
    ],
    "limitations": [
      "Administrative scripts may use PowerShell legitimately.",
      "Encoded command is a suspicious indicator, not a standalone malware verdict."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "malware",
      "ransomware",
      "credential_dumping",
      "account_compromise"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "edr_powershell_suspicious_command",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1059",
      "T1059.001"
    ]
  },
  "mitre_branch_result": {
    "branch": {
      "branch_name": "mitre",
      "status": "completed",
      "branch_authority": "planner_mitre_branch",
      "ran": true,
      "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
      "use_case_id": "edr_powershell_suspicious_command",
      "question_ref": null,
      "mitre_decision": {
        "mitre_status": "candidate",
        "techniques": [
          {
            "technique_id": "T1059.001",
            "name": "PowerShell",
            "tactic": "Execution",
            "status": "candidate",
            "evidence_status": "candidate",
            "status_reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
            "evidence_keys": [],
            "why": "Technique is registry-permitted metadata; supporting evidence is still required.",
            "evidence_requirements": [
              "command_line",
              "script_block_text",
              "event_id",
              "parent_process",
              "encoded_command_flag"
            ],
            "source_refs": [],
            "recommended_pivots": [
              "decode_command_if_available",
              "review_parent_process",
              "check_child_processes"
            ]
          },
          {
            "technique_id": "T1059",
            "name": "Command and Scripting Interpreter",
            "tactic": "Execution",
            "status": "candidate",
            "evidence_status": "candidate",
            "status_reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
            "evidence_keys": [],
            "why": "Technique is registry-permitted metadata; supporting evidence is still required.",
            "evidence_requirements": [
              "process_name",
              "command_line",
              "parent_process",
              "user",
              "host"
            ],
            "source_refs": [],
            "recommended_pivots": [
              "review_parent_process",
              "check_script_block_logging",
              "check_network_connections"
            ]
          }
        ],
        "rejected_techniques": [
          "T1562.001",
          "T1078",
          "T1110.001"
        ],
        "registry_candidates": [
          "T1059.001",
          "T1059"
        ],
        "not_claimed": [],
        "evidence_statuses": {
          "T1059.001": "candidate",
          "T1059": "candidate"
        },
        "evidence_status_details": {
          "T1059.001": {
            "status": "candidate",
            "reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
            "evidence_keys": []
          },
          "T1059": {
            "status": "candidate",
            "reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
            "evidence_keys": []
          }
        },
        "answer_visible": true,
        "requires_alert_context": false,
        "requires_more_context_for_supported_mapping": false,
        "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
        "registry_metadata": {
          "schema_version": "2026-06-control-plane-v1",
          "registry_role": "metadata_not_evidence",
          "mitre_permitted": [],
          "mitre_candidate": [
            "T1059.001",
            "T1059"
          ],
          "mitre_blocked": [
            "T1562.001",
            "T1078",
            "T1110.001"
          ],
          "mitre_requires_evidence": true,
          "mitre_requires_alert_context": true,
          "mitre_visibility_policy": "answer_if_requested",
          "source_question_ref": null,
          "source_use_case_id": "edr_powershell_suspicious_command",
          "mapping_rationale": "Registry-level MITRE candidates for PowerShell suspicious command. These are permitted/candidate mappings only; runtime mitre_decision must decide whether they are supported, candidate, trace-only, or hidden based on intent and evidence."
        }
      },
      "technique_statuses": [
        {
          "technique_id": "T1059.001",
          "status": "candidate",
          "reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_keys": []
        },
        {
          "technique_id": "T1059",
          "status": "candidate",
          "reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_keys": []
        }
      ],
      "evidence_supported_mitre": [],
      "candidate_mitre": [
        "T1059.001",
        "T1059"
      ],
      "requires_validation_mitre": [],
      "not_claimed_mitre": [
        "T1562.001",
        "T1078",
        "T1110.001"
      ],
      "ruled_out_mitre": [],
      "metadata_only_candidates": [
        "T1059.001",
        "T1059"
      ]
    },
    "decision": {
      "mitre_status": "candidate",
      "techniques": [
        {
          "technique_id": "T1059.001",
          "name": "PowerShell",
          "tactic": "Execution",
          "status": "candidate",
          "evidence_status": "candidate",
          "status_reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_keys": [],
          "why": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_requirements": [
            "command_line",
            "script_block_text",
            "event_id",
            "parent_process",
            "encoded_command_flag"
          ],
          "source_refs": [],
          "recommended_pivots": [
            "decode_command_if_available",
            "review_parent_process",
            "check_child_processes"
          ]
        },
        {
          "technique_id": "T1059",
          "name": "Command and Scripting Interpreter",
          "tactic": "Execution",
          "status": "candidate",
          "evidence_status": "candidate",
          "status_reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_keys": [],
          "why": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_requirements": [
            "process_name",
            "command_line",
            "parent_process",
            "user",
            "host"
          ],
          "source_refs": [],
          "recommended_pivots": [
            "review_parent_process",
            "check_script_block_logging",
            "check_network_connections"
          ]
        }
      ],
      "rejected_techniques": [
        "T1562.001",
        "T1078",
        "T1110.001"
      ],
      "registry_candidates": [
        "T1059.001",
        "T1059"
      ],
      "not_claimed": [],
      "evidence_statuses": {
        "T1059.001": "candidate",
        "T1059": "candidate"
      },
      "evidence_status_details": {
        "T1059.001": {
          "status": "candidate",
          "reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_keys": []
        },
        "T1059": {
          "status": "candidate",
          "reason": "Technique is registry-permitted metadata; supporting evidence is still required.",
          "evidence_keys": []
        }
      },
      "answer_visible": true,
      "requires_alert_context": false,
      "requires_more_context_for_supported_mapping": false,
      "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
      "registry_metadata": {
        "schema_version": "2026-06-control-plane-v1",
        "registry_role": "metadata_not_evidence",
        "mitre_permitted": [],
        "mitre_candidate": [
          "T1059.001",
          "T1059"
        ],
        "mitre_blocked": [
          "T1562.001",
          "T1078",
          "T1110.001"
        ],
        "mitre_requires_evidence": true,
        "mitre_requires_alert_context": true,
        "mitre_visibility_policy": "answer_if_requested",
        "source_question_ref": null,
        "source_use_case_id": "edr_powershell_suspicious_command",
        "mapping_rationale": "Registry-level MITRE candidates for PowerShell suspicious command. These are permitted/candidate mappings only; runtime mitre_decision must decide whether they are supported, candidate, trace-only, or hidden based on intent and evidence."
      }
    }
  },
  "severity_result": {
    "use_case_id": "edr_powershell_suspicious_command",
    "severity_label": "P3 Medium",
    "matched_rules": [
      "default_no_policy"
    ],
    "why_not_higher": [
      "No use-case-specific severity policy is active yet."
    ],
    "missing_evidence": [],
    "source_refs": [],
    "recommended_priority": "standard_triage",
    "allowed_action_tier": 1
  },
  "hil_status": {
    "hil_required": false,
    "clarification_needed": false,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [
    "Administrative scripts may use PowerShell legitimately.",
    "Encoded command is a suspicious indicator, not a standalone malware verdict."
  ],
  "path_type": "hybrid_investigation",
  "selected_branches": [
    "spl",
    "rag",
    "evidence",
    "mitre",
    "severity",
    "hil"
  ]
}
```

## 117. `manual.dns_beaconing` — exact_match

- **Source:** manual

### Question

For a DNS beaconing candidate, give me the investigation steps, evidence required, MITRE mapping, limitations, and review-only SPL.

### Path comparison

- imperative path_type: `hybrid_investigation`
- graph path_type: `hybrid_investigation`
- imperative branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- graph branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": {
    "branch_scheduled": true,
    "needs_rag": false,
    "rag_phase": "post_mcp",
    "answer_mode": "live_investigation"
  },
  "spl_result": {
    "branch_scheduled": true,
    "spl_allowed": true,
    "needs_spl": true,
    "execution_enabled": false,
    "blocked_tools": [
      "mcp",
      "candidate_spl_execution",
      "mcp_execution"
    ]
  },
  "evidence_plan": {
    "answer_mode": "live_investigation",
    "rag_phase": "post_mcp",
    "needs_rag": false,
    "needs_spl": true,
    "needs_mcp": false,
    "needs_mitre": true,
    "spl_allowed": true,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "recommend_only",
    "rag_no_match_behavior": null,
    "reasons": [
      "hybrid_alert_review_severity_mitre_spl",
      "curated_enrichment_evidence_requirements",
      "missing_required_curated_evidence"
    ],
    "required_evidence_keys": [
      "src",
      "dest",
      "domain",
      "periodicity",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "rare_domain_indicator",
      "user_host_association"
    ],
    "optional_evidence_keys": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "present_evidence_keys": [],
    "missing_required_evidence": [
      "src",
      "dest",
      "domain",
      "periodicity",
      "jitter",
      "bytes_out",
      "DNS_query_count",
      "rare_domain_indicator",
      "user_host_association"
    ],
    "enrichment_driven": true,
    "checklist": [
      "Measure periodicity and jitter.",
      "Check bytes out and DNS query count.",
      "Assess domain rarity and destination context.",
      "Tie traffic to a host or user before impact language."
    ],
    "investigation_workflow": [
      "Review periodicity, jitter, outbound volume, and domain rarity together.",
      "Associate source with user or host identity when possible.",
      "Escalate from candidate to evidence-supported only when multiple signals align."
    ],
    "answer_rules": [
      "Do not claim C2 confirmed from periodicity alone.",
      "Use candidate/evidence-supported wording based on multiple signals."
    ],
    "required_sources": [
      "mcp:splunk"
    ],
    "optional_sources": [],
    "limitations": [
      "Periodic traffic may be benign polling or monitoring.",
      "Parent T1071 is used unless evidence supports a specific sub-technique."
    ],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [
      "c2_confirmed",
      "malware",
      "data_exfiltration"
    ],
    "needs_hil": true,
    "needs_clarification": true,
    "evidence_plan_reason": "curated_enrichment_required_evidence_missing",
    "use_case_id": "dns_beaconing_candidate",
    "runtime_support_status": "runtime_active",
    "mitre_candidates_metadata_only": [
      "T1071"
    ]
  },
  "mitre_branch_result": {
    "branch": {
      "branch_name": "mitre",
      "status": "completed",
      "branch_authority": "planner_mitre_branch",
      "ran": true,
      "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
      "use_case_id": "dns_beaconing_candidate",
      "question_ref": null,
      "mitre_decision": {
        "mitre_status": "candidate",
        "techniques": [
          {
            "technique_id": "T1071",
            "name": "Application Layer Protocol",
            "tactic": "Command and Control",
            "status": "candidate",
            "evidence_status": "candidate",
            "status_reason": "No supporting network/command-and-control telemetry observed.",
            "evidence_keys": [],
            "why": "No supporting network/command-and-control telemetry observed.",
            "evidence_requirements": [
              "src",
              "dest",
              "domain",
              "periodicity",
              "jitter",
              "bytes_out",
              "host_association"
            ],
            "source_refs": [],
            "recommended_pivots": [
              "measure_periodicity",
              "review_domain_rarity",
              "check_host_process_context"
            ]
          }
        ],
        "rejected_techniques": [
          "T1562.001",
          "T1003",
          "T1078",
          "T1110.001"
        ],
        "registry_candidates": [
          "T1071"
        ],
        "not_claimed": [],
        "evidence_statuses": {
          "T1071": "candidate"
        },
        "evidence_status_details": {
          "T1071": {
            "status": "candidate",
            "reason": "No supporting network/command-and-control telemetry observed.",
            "evidence_keys": []
          }
        },
        "answer_visible": true,
        "requires_alert_context": false,
        "requires_more_context_for_supported_mapping": false,
        "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
        "registry_metadata": {
          "schema_version": "2026-06-control-plane-v1",
          "registry_role": "metadata_not_evidence",
          "mitre_permitted": [],
          "mitre_candidate": [
            "T1071"
          ],
          "mitre_blocked": [
            "T1562.001",
            "T1003",
            "T1078",
            "T1110.001"
          ],
          "mitre_requires_evidence": true,
          "mitre_requires_alert_context": true,
          "mitre_visibility_policy": "answer_if_requested",
          "source_question_ref": null,
          "source_use_case_id": "dns_beaconing_candidate",
          "mapping_rationale": "Registry-level MITRE candidates for Beaconing pattern candidate. These are permitted/candidate mappings only; runtime mitre_decision must decide whether they are supported, candidate, trace-only, or hidden based on intent and evidence."
        }
      },
      "technique_statuses": [
        {
          "technique_id": "T1071",
          "status": "candidate",
          "reason": "No supporting network/command-and-control telemetry observed.",
          "evidence_keys": []
        }
      ],
      "evidence_supported_mitre": [],
      "candidate_mitre": [
        "T1071"
      ],
      "requires_validation_mitre": [],
      "not_claimed_mitre": [
        "T1562.001",
        "T1003",
        "T1078",
        "T1110.001"
      ],
      "ruled_out_mitre": [],
      "metadata_only_candidates": [
        "T1071"
      ]
    },
    "decision": {
      "mitre_status": "candidate",
      "techniques": [
        {
          "technique_id": "T1071",
          "name": "Application Layer Protocol",
          "tactic": "Command and Control",
          "status": "candidate",
          "evidence_status": "candidate",
          "status_reason": "No supporting network/command-and-control telemetry observed.",
          "evidence_keys": [],
          "why": "No supporting network/command-and-control telemetry observed.",
          "evidence_requirements": [
            "src",
            "dest",
            "domain",
            "periodicity",
            "jitter",
            "bytes_out",
            "host_association"
          ],
          "source_refs": [],
          "recommended_pivots": [
            "measure_periodicity",
            "review_domain_rarity",
            "check_host_process_context"
          ]
        }
      ],
      "rejected_techniques": [
        "T1562.001",
        "T1003",
        "T1078",
        "T1110.001"
      ],
      "registry_candidates": [
        "T1071"
      ],
      "not_claimed": [],
      "evidence_statuses": {
        "T1071": "candidate"
      },
      "evidence_status_details": {
        "T1071": {
          "status": "candidate",
          "reason": "No supporting network/command-and-control telemetry observed.",
          "evidence_keys": []
        }
      },
      "answer_visible": true,
      "requires_alert_context": false,
      "requires_more_context_for_supported_mapping": false,
      "reason": "Registry-permitted MITRE candidates are statused by evidence preconditions; confirmation still requires analyst validation.",
      "registry_metadata": {
        "schema_version": "2026-06-control-plane-v1",
        "registry_role": "metadata_not_evidence",
        "mitre_permitted": [],
        "mitre_candidate": [
          "T1071"
        ],
        "mitre_blocked": [
          "T1562.001",
          "T1003",
          "T1078",
          "T1110.001"
        ],
        "mitre_requires_evidence": true,
        "mitre_requires_alert_context": true,
        "mitre_visibility_policy": "answer_if_requested",
        "source_question_ref": null,
        "source_use_case_id": "dns_beaconing_candidate",
        "mapping_rationale": "Registry-level MITRE candidates for Beaconing pattern candidate. These are permitted/candidate mappings only; runtime mitre_decision must decide whether they are supported, candidate, trace-only, or hidden based on intent and evidence."
      }
    }
  },
  "severity_result": {
    "use_case_id": "dns_beaconing_candidate",
    "severity_label": "P3 Medium",
    "matched_rules": [
      "default_no_policy"
    ],
    "why_not_higher": [
      "No use-case-specific severity policy is active yet."
    ],
    "missing_evidence": [],
    "source_refs": [],
    "recommended_priority": "standard_triage",
    "allowed_action_tier": 1
  },
  "hil_status": {
    "hil_required": false,
    "clarification_needed": false,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": null,
  "missing_evidence": [],
  "limitations": [
    "Periodic traffic may be benign polling or monitoring.",
    "Parent T1071 is used unless evidence supports a specific sub-technique."
  ],
  "path_type": "hybrid_investigation",
  "selected_branches": [
    "spl",
    "rag",
    "evidence",
    "mitre",
    "severity",
    "hil"
  ]
}
```

## 118. `manual.mitre_no_context` — exact_match

- **Source:** manual

### Question

What MITRE technique is this? I only know there were multiple failed logins, but I do not have alert details or logs.

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "soc_map_alert_mitre",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 119. `manual.phishing_enrichment` — exact_match

- **Source:** manual

### Question

Review an email phishing header investigation use case and give me runtime SPL and MITRE evidence status.

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": "curated_enrichment_not_runtime_active",
    "use_case_id": "soc_map_alert_mitre",
    "runtime_support_status": "planned",
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

## 120. `manual.unsafe_execute` — exact_match

- **Source:** manual

### Question

Lock the suspicious user immediately and execute the SPL to confirm compromise.

### Path comparison

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`

### Field matches

- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- diff details: `[]`
- critical mismatches: `[]`

### Graph trace

- nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

```json
{
  "rag_result": null,
  "spl_result": null,
  "evidence_plan": {
    "answer_mode": "clarification",
    "rag_phase": "rag_only",
    "needs_rag": false,
    "needs_spl": false,
    "needs_mcp": false,
    "needs_mitre": false,
    "spl_allowed": false,
    "mcp_allowed": false,
    "policy_context_required": false,
    "policy_context_recommended": false,
    "requires_hil": true,
    "action_mode": "hil_required",
    "rag_no_match_behavior": null,
    "reasons": [
      "intent_requires_clarification"
    ],
    "required_evidence_keys": [],
    "optional_evidence_keys": [],
    "present_evidence_keys": [],
    "missing_required_evidence": [],
    "enrichment_driven": false,
    "checklist": [],
    "investigation_workflow": [],
    "answer_rules": [],
    "required_sources": [],
    "optional_sources": [],
    "limitations": [],
    "recommended_pivots": [],
    "unsupported_claims_avoid": [],
    "needs_hil": false,
    "needs_clarification": false,
    "evidence_plan_reason": null,
    "use_case_id": null,
    "runtime_support_status": null,
    "mitre_candidates_metadata_only": []
  },
  "mitre_branch_result": null,
  "severity_result": null,
  "hil_status": {
    "hil_required": true,
    "clarification_needed": true,
    "authority_source": "deterministic_planner_path_selection"
  },
  "unsafe_status": null,
  "clarification_status": {
    "clarification_needed": true,
    "path_type": "clarification_required",
    "reason": "intent_requires_clarification"
  },
  "missing_evidence": [],
  "limitations": [],
  "path_type": "clarification_required",
  "selected_branches": [
    "hil",
    "clarification"
  ]
}
```

