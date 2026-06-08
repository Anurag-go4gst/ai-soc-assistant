# SOC clean-answer human-review evidence pack

Full question, answer, evaluation fields, and LangGraph parity comparison per row.

- Generated: `2026-06-08T12:35:51.309468+00:00`
- Schema: `2026-06-08-clean-answer-answers-v1`
- Total evaluated: **120**
- PASS / REVIEW / FAIL: **120** / **0** / **0**
- Average runtime: **3** ms
- Live composer: **False**
- LLM provider configured: **True**
- SPL/MCP execution enabled: **False**

## 1. `q0.q001` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

What incident or alert network events are high or critical right now?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 2. `q0.q002` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which source IPs generated the most outbound connections?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 3. `q0.q003` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which destination IPs received the most connections?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 4. `q0.q004` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts contacted known malicious IPs today?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 5. `q0.q005` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts contacted suspicious external domains?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 6. `q0.q006` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which DNS queries have unusually long names?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 7. `q0.q007` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which DNS queries look like DGA activity?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 8. `q0.q008` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 7 ms
- **Timed out:** False

### Question

Which hosts show possible beaconing behavior?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `dns_beaconing_candidate`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['src', 'dest', 'domain', 'periodicity', 'jitter', 'bytes_out', 'DNS_query_count', 'rare_domain_indicator', 'user_host_association']`
- required evidence: `['src', 'dest', 'domain', 'periodicity', 'jitter', 'bytes_out', 'DNS_query_count', 'rare_domain_indicator', 'user_host_association']`
- limitations: `['Periodic traffic may be benign polling or monitoring.', 'Parent T1071 is used unless evidence supports a specific sub-technique.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 9. `q0.q009` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts communicated with many unique external IPs?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 10. `q0.q010` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts are generating the most SMB traffic?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 11. `q0.q011` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts made SMB connections to many peers?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 12. `q0.q012` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which systems used unusual destination ports?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 13. `q0.q013` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which systems generated large outbound data transfers?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 14. `q0.q014` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts showed potential data exfiltration to cloud apps?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 15. `q0.q015` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts have repeated connections to rare destinations?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `net_repeated_critical_asset_connections`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 16. `q0.q016` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts contacted the same external IP many times?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 17. `q0.q017` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts generated the most DNS queries?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 18. `q0.q018` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which domains were queried by multiple hosts?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 19. `q0.q019` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts queried domains with suspicious subdomains?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 20. `q0.q020` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which networks saw traffic to high-risk ports?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 21. `q0.q021` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts communicated with foreign IP ranges?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 22. `q0.q022` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts contacted IPs in an IOC lookup?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 23. `q0.q023` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 7 ms
- **Timed out:** False

### Question

Which hosts showed possible command-and-control beaconing?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `dns_beaconing_candidate`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['src', 'dest', 'domain', 'periodicity', 'jitter', 'bytes_out', 'DNS_query_count', 'rare_domain_indicator', 'user_host_association']`
- required evidence: `['src', 'dest', 'domain', 'periodicity', 'jitter', 'bytes_out', 'DNS_query_count', 'rare_domain_indicator', 'user_host_association']`
- limitations: `['Periodic traffic may be benign polling or monitoring.', 'Parent T1071 is used unless evidence supports a specific sub-technique.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 24. `q0.q024` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which internal hosts generated outbound traffic after DNS lookups?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 25. `q0.q025` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts used unusual protocols?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 26. `q0.q026` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts have unusually high connection counts to one destination?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 27. `q0.q027` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which DNS queries resolved to suspicious top-level domains?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 28. `q0.q028` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts showed peer-to-peer style communication?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `unsupported`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 29. `q0.q029` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which systems accessed the internet through rare ports?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 30. `q0.q030` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts contacted external IPs after hours?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 31. `q0.q031` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts repeatedly contacted the same destination at regular intervals?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 32. `q0.q032` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts had both DNS and network anomalies?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 33. `q0.q033` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts communicated with suspicious destination domains and IPs?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 34. `q0.q034` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which destination IPs were contacted by many hosts?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 35. `q0.q035` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts generated the largest DNS response volumes?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 36. `q0.q036` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts reached known malicious domains from lookup data?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 37. `q0.q037` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts showed likely proxy or tunneling behavior?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 38. `q0.q038` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts had large inbound traffic from a single source?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 39. `q0.q039` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts downloaded large volumes from the internet?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 40. `q0.q040` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts initiated traffic to rare countries?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 41. `q0.q041` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which systems have repeated hits to the same suspicious URL path?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 42. `q0.q042` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts contacted both malicious IPs and domains?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 43. `q0.q043` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts show consistent low-volume outbound connections?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 44. `q0.q044` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which rules are generating the most alerts?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 45. `q0.q045` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

What happened for this specific notable event?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 46. `q0.q046` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which users have excessive failed logins?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `auth_failed_login_spike`
- path_type: `spl_review`
- branches: `['evidence', 'severity', 'spl']`
- response_profile: `spl_only`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `rejected`
- execution status: `requires_human_review`
- HIL status: `spl_revision`
- missing evidence: `['critical_asset', 'time_window', 'host', 'user', 'src', 'privileged_account_impacted']`
- required evidence: `['first_failure — first failure', 'user — User context', 'time_window', 'last_failure — last failure', 'host', 'fail_count', 'user', 'first_failure', 'time_window — time window', 'host — Host context', 'last_failure', 'fail_count — fail count', 'src — Source host/IP', 'src']`
- limitations: `['Failed login telemetry alone does not establish credential validity.', 'Source IP reuse, NAT, or scanner behavior may require analyst review.']`

### Full answer text

Failed login spike Approved SOP guidance is unavailable for this scenario. review_required SPL validation complete. MCP execution is disabled.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 47. `q0.q047` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Is one IP attacking many accounts?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 48. `q0.q048` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Did a user log in from impossible locations?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 49. `q0.q049` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts ran suspicious PowerShell?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `edr_powershell_suspicious_command`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['host', 'user', 'command_line', 'script_block_text', 'event_id', 'parent_process', 'encoded_command_flag', 'network_connection']`
- required evidence: `['host', 'user', 'command_line', 'script_block_text', 'event_id', 'parent_process', 'encoded_command_flag', 'network_connection']`
- limitations: `['Administrative scripts may use PowerShell legitimately.', 'Encoded command is a suspicious indicator, not a standalone malware verdict.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 50. `q0.q050` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Did Office apps spawn cmd or PowerShell?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 51. `q0.q051` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

What unusual processes ran on critical servers?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 52. `q0.q052` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Did any host contact known malicious IPs?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 53. `q0.q053` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Are there suspicious DNS queries indicating C2 or DGA behavior?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 54. `q0.q054` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Who is sending large amounts of data outbound?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 55. `q0.q055` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Did anyone get added to Administrators?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 56. `q0.q056` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which users are logging in outside normal hours?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 57. `q0.q057` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Did any endpoint run this suspicious hash?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 58. `q0.q058` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which users or hosts have the highest risk scores?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 59. `q0.q059` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 7 ms
- **Timed out:** False

### Question

Which source IPs generated the most authentication failures today?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `auth_failed_login_spike`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['user', 'src', 'host', 'fail_count', 'first_failure', 'last_failure', 'privileged_account_impacted', 'critical_asset']`
- required evidence: `['user', 'src', 'host', 'fail_count', 'time_window', 'first_failure', 'last_failure']`
- limitations: `['Failed login telemetry alone does not establish credential validity.', 'Source IP reuse, NAT, or scanner behavior may require analyst review.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 60. `q0.q060` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 7 ms
- **Timed out:** False

### Question

Which accounts had a successful login after repeated failures?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `auth_success_after_failure`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P2 High`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['user', 'src', 'host', 'source_ip_novelty', 'privileged_account_impacted', 'critical_asset']`
- required evidence: `['user', 'src', 'host', 'fail_count', 'success_count', 'first_failure', 'last_success', 'source_ip_novelty']`
- limitations: `['Sequence evidence can be benign if the user retried successfully.', 'Novelty is optional and may be unavailable in current telemetry.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 61. `q0.q061` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 72 ms
- **Timed out:** False

### Question

Which users logged in from new countries today?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 62. `q0.q062` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 6 ms
- **Timed out:** False

### Question

Which hosts show a spike in failed logins?

### Expected

- use_case_id: `auth_failed_login_spike`
- path_type: `None`

### Actual structured fields

- use_case_id: `auth_failed_login_spike`
- path_type: `spl_review`
- branches: `['evidence', 'severity', 'spl']`
- response_profile: `spl_only`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `approved`
- execution status: `requires_human_review`
- HIL status: `execution_approval`
- missing evidence: `['critical_asset', 'time_window', 'host', 'user', 'src', 'privileged_account_impacted']`
- required evidence: `['first_failure — first failure', 'user — User context', 'time_window', 'last_failure — last failure', 'host', 'fail_count', 'user', 'first_failure', 'time_window — time window', 'host — Host context', 'last_failure', 'fail_count — fail count', 'src — Source host/IP', 'src']`
- limitations: `['Failed login telemetry alone does not establish credential validity.', 'Source IP reuse, NAT, or scanner behavior may require analyst review.']`

### Full answer text

Failed login spike Approved SOP guidance is unavailable for this scenario. ready_for_review Governed SPL draft ready. It has passed deterministic validation and has not been executed.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 63. `q0.q063` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which endpoints spawned script interpreters recently?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 64. `q0.q064` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which hosts executed encoded PowerShell commands?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 65. `q0.q065` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which endpoints created new scheduled tasks?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `edr_scheduled_task_creation`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 66. `q0.q066` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which systems contacted rare external destinations?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 67. `q0.q067` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which hosts are generating unusual DNS query volumes?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `dns_unusual_query_volume`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 68. `q0.q068` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which internal hosts contacted known command-and-control domains?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 69. `q0.q069` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which users accessed privileged applications unusually?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 70. `q0.q070` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which users changed their password multiple times in a short window?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 71. `q0.q071` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which accounts were disabled or re-enabled today?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 72. `q0.q072` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts show signs of lateral movement?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `edr_lateral_movement_candidate`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 73. `q0.q073` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which systems had multiple remote service creations?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 74. `q0.q074` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts show SMB connections to many peers?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 75. `q0.q075` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which endpoints created suspicious archive files?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 76. `q0.q076` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts uploaded large amounts of data to cloud services?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 77. `q0.q077` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which endpoints accessed USB storage recently?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 78. `q0.q078` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which systems had repeated malware detections?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 79. `q0.q079` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which files were modified by suspicious processes?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `edr_suspicious_process`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 80. `q0.q080` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts spawned shells from email clients?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 81. `q0.q081` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which users received and opened phishing attachments?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 82. `q0.q082` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which domains were queried by multiple hosts in a short period?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 83. `q0.q083` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts have suspicious parent-child process chains?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 84. `q0.q084` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which accounts have the most risk events?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 85. `q0.q085` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which assets have accumulated risk from multiple detections?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 86. `q0.q086` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 7 ms
- **Timed out:** False

### Question

Which users were involved in both failed logins and privilege changes?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `auth_failed_login_spike`
- path_type: `spl_review`
- branches: `['evidence', 'severity', 'spl']`
- response_profile: `spl_only`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `rejected`
- execution status: `requires_human_review`
- HIL status: `precondition_review`
- missing evidence: `['critical_asset', 'time_window', 'host', 'user', 'src', 'privileged_account_impacted']`
- required evidence: `['first_failure — first failure', 'user — User context', 'time_window', 'last_failure — last failure', 'host', 'fail_count', 'user', 'first_failure', 'time_window — time window', 'host — Host context', 'last_failure', 'fail_count — fail count', 'src — Source host/IP', 'src']`
- limitations: `['Failed login telemetry alone does not establish credential validity.', 'Source IP reuse, NAT, or scanner behavior may require analyst review.']`

### Full answer text

Failed login spike Approved SOP guidance is unavailable for this scenario. review_required SPL validation complete. MCP execution is disabled.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 87. `q0.q087` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts are communicating with unusual ports externally?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 88. `q0.q088` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which endpoints have multiple persistence indicators?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 89. `q0.q089` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 8 ms
- **Timed out:** False

### Question

Which users authenticated to VPN after repeated MFA failures?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `auth_failed_login_spike`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['user', 'src', 'host', 'fail_count', 'time_window', 'first_failure', 'last_failure', 'privileged_account_impacted', 'critical_asset']`
- required evidence: `['user', 'src', 'host', 'fail_count', 'time_window', 'first_failure', 'last_failure']`
- limitations: `['Failed login telemetry alone does not establish credential validity.', 'Source IP reuse, NAT, or scanner behavior may require analyst review.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 90. `q0.q090` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which assets are generating the most notable events?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 91. `q0.q091` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which alerts are still open and unresolved?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 92. `q0.q092` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which users had access to sensitive systems and then large outbound transfers?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 93. `q0.q093` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which hosts showed both process execution and suspicious DNS within 24 hours?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 94. `q0.q094` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which logs are missing from key security sources?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 95. `q0.q095` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which sources stopped sending events recently?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 96. `q0.q096` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which users performed privileged actions from non-admin workstations?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 97. `q0.q097` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which systems show signs of webshell activity?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 98. `q0.q098` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which hosts downloaded executables from the internet?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 99. `q0.q099` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which detections involved the same user and host repeatedly?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 100. `q0.q100` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which users triggered multiple different detections?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 101. `q0.q101` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Which devices are generating the most endpoint alerts?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 102. `q0.q102` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Which users are accessing resources from unusual hosts?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 103. `q0.q103` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 104. `q0.q104` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

What is the full activity timeline for a given entity in the N hours before and after a detection?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `generic_soc_guidance`
- branches: `['evidence', 'rag']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Generic SOC guidance path selected. Governed KB was checked when enabled; no catalog use case, SPL, MCP, or MITRE evidence claim was created.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `generic_soc_guidance`
- graph path_type: `generic_soc_guidance`
- imperative branches: `['evidence', 'rag']`
- graph branches: `['evidence', 'rag']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'rag_pipeline_prepare', 'rag_pipeline_retrieve', 'finalize']`

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

## 105. `q0.q105` — PASS

- **Source:** 105_map
- **Clean status:** pass
- **Duration:** 2 ms
- **Timed out:** False

### Question

Has this entity, IP, domain, or notable been seen or investigated before, and what was the prior disposition?

### Expected

- use_case_id: `None`
- path_type: `None`

### Actual structured fields

- use_case_id: `None`
- path_type: `spl_review`
- branches: `['evidence', 'severity', 'spl']`
- response_profile: `None`
- runtime_support_status: `metadata_only`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 106. `demo.failed_login_spike` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Investigate a spike of failed logins for a user/source

### Expected

- use_case_id: `auth_failed_login_spike`
- path_type: `spl_review`

### Actual structured fields

- use_case_id: `auth_failed_login_spike`
- path_type: `spl_review`
- branches: `['evidence', 'severity', 'spl']`
- response_profile: `spl_only`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `approved`
- execution status: `requires_human_review`
- HIL status: `execution_approval`
- missing evidence: `['critical_asset', 'time_window', 'host', 'user', 'src', 'privileged_account_impacted']`
- required evidence: `['first_failure — first failure', 'user — User context', 'time_window', 'last_failure — last failure', 'host', 'fail_count', 'user', 'first_failure', 'time_window — time window', 'host — Host context', 'last_failure', 'fail_count — fail count', 'src — Source host/IP', 'src']`
- limitations: `['Failed login telemetry alone does not establish credential validity.', 'Source IP reuse, NAT, or scanner behavior may require analyst review.']`

### Full answer text

Failed login spike Approved SOP guidance is unavailable for this scenario. ready_for_review Governed SPL draft ready. It has passed deterministic validation and has not been executed.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `spl_review`
- graph path_type: `spl_review`
- imperative branches: `['evidence', 'severity', 'spl']`
- graph branches: `['evidence', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 107. `demo.successful_login_after_failures` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 10 ms
- **Timed out:** False

### Question

Failed logins followed by a successful login from same user

### Expected

- use_case_id: `auth_success_after_failure`
- path_type: `hybrid_investigation`

### Actual structured fields

- use_case_id: `auth_success_after_failure`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P2 High`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['user', 'src', 'host', 'source_ip_novelty', 'privileged_account_impacted', 'critical_asset']`
- required evidence: `['user', 'src', 'host', 'fail_count', 'success_count', 'first_failure', 'last_success', 'source_ip_novelty']`
- limitations: `['Sequence evidence can be benign if the user retried successfully.', 'Novelty is optional and may be unavailable in current telemetry.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 108. `demo.dns_beaconing_candidate` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 9 ms
- **Timed out:** False

### Question

Possible periodic DNS beaconing to a rare domain

### Expected

- use_case_id: `dns_beaconing_candidate`
- path_type: `spl_review_plus_rag`

### Actual structured fields

- use_case_id: `dns_beaconing_candidate`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['src', 'dest', 'jitter', 'bytes_out', 'DNS_query_count', 'user_host_association']`
- required evidence: `['src', 'dest', 'domain', 'periodicity', 'jitter', 'bytes_out', 'DNS_query_count', 'rare_domain_indicator', 'user_host_association']`
- limitations: `['Periodic traffic may be benign polling or monitoring.', 'Parent T1071 is used unless evidence supports a specific sub-technique.']`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 109. `demo.suspicious_powershell` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 4 ms
- **Timed out:** False

### Question

Suspicious encoded PowerShell command on an endpoint

### Expected

- use_case_id: `edr_powershell_suspicious_command`
- path_type: `spl_review_plus_rag`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `None`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 110. `demo.sop-only_query` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 4 ms
- **Timed out:** False

### Question

Show the SOP/runbook for brute-force handling (no SPL)

### Expected

- use_case_id: `None`
- path_type: `rag_only`

### Actual structured fields

- use_case_id: `soc_show_sop`
- path_type: `rag_only`
- branches: `['rag']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Governed knowledge path selected. SPL and MCP are skipped for this request.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `rag_only`
- graph path_type: `rag_only`
- imperative branches: `['rag']`
- graph branches: `['rag']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'rag_pipeline_prepare', 'rag_pipeline_retrieve', 'finalize']`

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

## 111. `demo.mitre-only_without_alert_context` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Map this to MITRE (no alert/evidence provided)

### Expected

- use_case_id: `None`
- path_type: `mitre_context_required`

### Actual structured fields

- use_case_id: `soc_map_alert_mitre`
- path_type: `mitre_context_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `intent_clarification`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

I need alert context before mapping to MITRE ATT&CK. Share the alert title, detection rule, notable/event ID, or the SPL and a few sample fields.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `mitre_context_required`
- graph path_type: `mitre_context_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 112. `demo.enrichment-only_pilot` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Review phishing email headers (design-only pilot)

### Expected

- use_case_id: `email_phishing_header_review`
- path_type: `generic_soc_guidance`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `None`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 113. `demo.unsafe_containment/execution_request` — PASS

- **Source:** demo_scenario
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Contain/isolate the host or run the query now

### Expected

- use_case_id: `None`
- path_type: `unsafe_blocked`

### Actual structured fields

- use_case_id: `None`
- path_type: `unsafe_blocked`
- branches: `['block', 'hil', 'unsafe_blocked']`
- response_profile: `None`
- runtime_support_status: `None`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `unsafe_blocked`
- graph path_type: `unsafe_blocked`
- imperative branches: `['block', 'hil', 'unsafe_blocked']`
- graph branches: `['block', 'hil', 'unsafe_blocked']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 114. `manual.alt0891_hybrid` — PASS

- **Source:** manual
- **Clean status:** pass
- **Duration:** 9 ms
- **Timed out:** False

### Question

For alert ALT-2024-0891, failed logins followed by a successful login from the same user in the last hour, give me severity, MITRE mapping with evidence status, missing evidence, and a governed SPL I can review but not execute.

### Expected

- use_case_id: `auth_success_after_failure`
- path_type: `hybrid_investigation`

### Actual structured fields

- use_case_id: `auth_success_after_failure`
- path_type: `hybrid_investigation`
- branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- response_profile: `hybrid_alert_review`
- runtime_support_status: `runtime_active`
- severity: `P2 High`
- MITRE candidate: `['T1078']`
- MITRE evidence-supported: `['T1110.001']`
- MITRE not-claimed: `['T1003', 'T1562.001']`
- SPL status: `approved`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['critical_asset', 'host', 'user', 'source_ip_novelty', 'src', 'privileged_account_impacted']`
- required evidence: `['first_failure — first failure', 'user — User context', 'last_success — last success', 'host', 'fail_count', 'user', 'first_failure', 'success_count', 'source_ip_novelty', 'host — Host context', 'source_ip_novelty — source ip novelty', 'last_success', 'fail_count — fail count', 'success_count — success count', 'src — Source host/IP', 'src']`
- limitations: `['Sequence evidence can be benign if the user retried successfully.', 'Source IP ownership missing', 'Privilege status missing', 'Asset criticality missing', 'MFA result missing', 'Novelty is optional and may be unavailable in current telemetry.', 'Post-login activity missing']`

### Full answer text

The alert has 1 evidence-supported MITRE technique, 1 candidate technique, and 2 techniques not claimed due to insufficient supporting evidence. A governed SPL draft is available for review only and has not been executed. Alert ALT-2024-0891 review This is not confirmed account compromise; it is a candidate authentication security event pending validation. Review only — not executed ready_for_review T1110.001 Evidence Supported T1078 Candidate Governed SPL draft ready. It has passed deterministic validation and has not been executed.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `hybrid_investigation`
- graph path_type: `hybrid_investigation`
- imperative branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- graph branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 115. `manual.brute_force_sop` — PASS

- **Source:** manual
- **Clean status:** pass
- **Duration:** 4 ms
- **Timed out:** False

### Question

Show me the SOP for brute-force login investigation. Do not generate SPL unless required.

### Expected

- use_case_id: `None`
- path_type: `rag_only`

### Actual structured fields

- use_case_id: `soc_show_sop`
- path_type: `rag_only`
- branches: `['rag']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Governed knowledge path selected. SPL and MCP are skipped for this request.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `rag_only`
- graph path_type: `rag_only`
- imperative branches: `['rag']`
- graph branches: `['rag']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'rag_pipeline_prepare', 'rag_pipeline_retrieve', 'finalize']`

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

## 116. `manual.powershell_checklist` — PASS

- **Source:** manual
- **Clean status:** pass
- **Duration:** 6 ms
- **Timed out:** False

### Question

For suspicious PowerShell command execution on an endpoint, give me the analyst checklist, required evidence, MITRE status, and governed SPL for review.

### Expected

- use_case_id: `edr_powershell_suspicious_command`
- path_type: `spl_review_plus_rag`

### Actual structured fields

- use_case_id: `edr_powershell_suspicious_command`
- path_type: `hybrid_investigation`
- branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- response_profile: `hybrid_alert_review`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `['T1059', 'T1059.001']`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `['T1078', 'T1110.001', 'T1562.001']`
- SPL status: `rejected`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['command_line', 'host', 'user', 'network_connection', 'event_id', 'script_block_text', 'encoded_command_flag', 'parent_process']`
- required evidence: `['script_block_text — Script block logs', 'command_line', 'user — User context', 'host', 'network_connection — Network connection context', 'user', 'network_connection', 'encoded_command_flag — Encoded-command indicator', 'event_id — Event ID', 'command_line — Command line', 'event_id', 'script_block_text', 'host — Host context', 'encoded_command_flag', 'parent_process', 'parent_process — Parent process']`
- limitations: `['Encoded command is a suspicious indicator, not a standalone malware verdict.', 'Administrative scripts may use PowerShell legitimately.']`

### Full answer text

The alert has 2 candidate techniques, and 3 techniques not claimed due to insufficient supporting evidence. PowerShell suspicious command review_required T1059.001 Candidate T1059 Candidate SPL validation complete. MCP execution is disabled.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `hybrid_investigation`
- graph path_type: `hybrid_investigation`
- imperative branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- graph branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 117. `manual.dns_beaconing` — PASS

- **Source:** manual
- **Clean status:** pass
- **Duration:** 12 ms
- **Timed out:** False

### Question

For a DNS beaconing candidate, give me the investigation steps, evidence required, MITRE mapping, limitations, and review-only SPL.

### Expected

- use_case_id: `dns_beaconing_candidate`
- path_type: `spl_review_plus_rag`

### Actual structured fields

- use_case_id: `dns_beaconing_candidate`
- path_type: `hybrid_investigation`
- branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- response_profile: `hybrid_alert_review`
- runtime_support_status: `runtime_active`
- severity: `P3 Medium`
- MITRE candidate: `['T1071']`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `['T1003', 'T1078', 'T1110.001', 'T1562.001']`
- SPL status: `rejected`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `['bytes_out', 'jitter', 'user_host_association', 'DNS_query_count', 'periodicity', 'domain', 'rare_domain_indicator', 'src', 'dest']`
- required evidence: `['bytes_out — Outbound bytes', 'jitter — Jitter measurement', 'dest — Destination', 'user_host_association — User/host association', 'bytes_out', 'periodicity — Periodicity measurement', 'domain — DNS domain', 'jitter', 'DNS_query_count — DNS query volume', 'user_host_association', 'rare_domain_indicator — Domain rarity assessment', 'DNS_query_count', 'periodicity', 'domain', 'rare_domain_indicator', 'src — Source host/IP', 'src', 'dest']`
- limitations: `['Periodic traffic may be benign polling or monitoring.', 'Parent T1071 is used unless evidence supports a specific sub-technique.']`

### Full answer text

The alert has 1 candidate technique, and 4 techniques not claimed due to insufficient supporting evidence. Beaconing pattern candidate review_required T1071 Candidate SPL validation complete. MCP execution is disabled.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `hybrid_investigation`
- graph path_type: `hybrid_investigation`
- imperative branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- graph branches: `['evidence', 'hil', 'mitre', 'rag', 'severity', 'spl']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 118. `manual.mitre_no_context` — PASS

- **Source:** manual
- **Clean status:** pass
- **Duration:** 7 ms
- **Timed out:** False

### Question

What MITRE technique is this? I only know there were multiple failed logins, but I do not have alert details or logs.

### Expected

- use_case_id: `None`
- path_type: `mitre_context_required`

### Actual structured fields

- use_case_id: `soc_map_alert_mitre`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `intent_clarification`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

I need alert context before mapping to MITRE ATT&CK. Share the alert title, detection rule, notable/event ID, or the SPL and a few sample fields.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 119. `manual.phishing_enrichment` — PASS

- **Source:** manual
- **Clean status:** pass
- **Duration:** 4 ms
- **Timed out:** False

### Question

Review an email phishing header investigation use case and give me runtime SPL and MITRE evidence status.

### Expected

- use_case_id: `email_phishing_header_review`
- path_type: `generic_soc_guidance`

### Actual structured fields

- use_case_id: `soc_map_alert_mitre`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `planned`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `intent_clarification`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

I need alert context before mapping to MITRE ATT&CK. Share the alert title, detection rule, notable/event ID, or the SPL and a few sample fields.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

## 120. `manual.unsafe_execute` — PASS

- **Source:** manual
- **Clean status:** pass
- **Duration:** 3 ms
- **Timed out:** False

### Question

Lock the suspicious user immediately and execute the SPL to confirm compromise.

### Expected

- use_case_id: `None`
- path_type: `unsafe_blocked`

### Actual structured fields

- use_case_id: `None`
- path_type: `clarification_required`
- branches: `['clarification', 'hil']`
- response_profile: `None`
- runtime_support_status: `None`
- severity: `P3 Medium`
- MITRE candidate: `[]`
- MITRE evidence-supported: `[]`
- MITRE not-claimed: `[]`
- SPL status: `none`
- execution status: `skipped`
- HIL status: `execution_approval`
- missing evidence: `[]`
- required evidence: `[]`
- limitations: `[]`

### Full answer text

Routing complete. SPL is not required at this stage.

### Violations

- _(none)_

### LangGraph parity

- imperative path_type: `clarification_required`
- graph path_type: `clarification_required`
- imperative branches: `['clarification', 'hil']`
- graph branches: `['clarification', 'hil']`
- severity match: `True`
- MITRE bucket match: `True`
- SPL status match: `True`
- execution status match: `True`
- HIL status match: `True`
- parity verdict: `exact_match`
- diff details: `[]`
- graph nodes visited: `['query_understanding', 'planning', 'route_setup', 'rag_branch', 'spl_branch', 'evidence_branch', 'mitre_branch', 'severity_branch', 'hil_branch', 'unsafe_blocked_branch', 'clarification_branch', 'fan_in_aggregate', 'investigation_spl', 'investigation_execution', 'finalize']`

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

