# Reference Knowledge Probe Baseline

Generated: 2026-08-15 15:41 UTC

Current baseline for the reference-knowledge probe contract. P1-P4 should route through `reference_taxonomy` / `reference_knowledge`; P5/P6/N1-N4 are frozen non-regression rows.

| ID | Kind | Route | Answer | Authority owner | Resource purposes | PhaseContract | Dispatch | HIL | Result |
|---|---|---|---|---|---|---|---|---|---|
| P1 | positive | knowledge_recall | rag_only | resource_plan_phase_contract | knowledge_retrieval,narration | prepare_rag_only,rag_early,reference_finalize | reference_finalize,prepare_rag_only,rag_early | none | skipped |
| P2 | positive | knowledge_recall | rag_only | resource_plan_phase_contract | knowledge_retrieval,narration | prepare_rag_only,rag_early,reference_finalize | reference_finalize,prepare_rag_only,rag_early | none | skipped |
| P3 | positive | knowledge_recall | rag_only | resource_plan_phase_contract | knowledge_retrieval,narration | prepare_rag_only,rag_early,reference_finalize | reference_finalize,prepare_rag_only,rag_early | none | skipped |
| P4 | positive | knowledge_recall | rag_only | resource_plan_phase_contract | knowledge_retrieval,narration | prepare_rag_only,rag_early,reference_finalize | reference_finalize,prepare_rag_only,rag_early | none | skipped |
| P5 | positive_non_regression | knowledge_recall | live_investigation | canonical_non_planned |  |  |  | intent_clarification | not_executed |
| P6 | positive_non_regression | spl_generation | live_investigation | resource_plan_phase_contract | spl_artifact,mcp_execution,narration | workflow_spl,spl_postprocessor,spl_source_resolve,execution | workflow_spl,spl_postprocessor,spl_source_resolve,execution | spl_source_profile_clarification | not_executed |
| N1 | negative | spl_generation | live_investigation | resource_plan_phase_contract | spl_artifact,mcp_execution,narration | workflow_spl,spl_postprocessor,spl_source_resolve,execution | workflow_spl,spl_postprocessor,spl_source_resolve,execution | intent_clarification | not_executed |
| N2 | negative | knowledge_recall | clarification | canonical_non_planned |  |  |  | none | not_executed |
| N3 | negative | knowledge_recall | live_investigation | resource_plan | mitre_mapping,narration |  | workflow_spl,spl_source_resolve,execution | intent_clarification | skipped |
| N4 | negative | knowledge_recall | clarification | canonical_non_planned |  |  |  | execution_approval | not_executed |

## Frozen Non-Regression Contract

- Authority fields come from ResourcePlan, PhaseContract/merge, and the current dispatch/execution result; retired `pipeline_dispatch.decision` fields are not read or reconstructed.
- P5/P6/N1-N4 current routes are the non-regression baseline for item 18.
- N3 intentionally duplicates the alert-mapping guard class covered by P5.
- This file is updated deliberately when P1/P2 flip red to green; the probe script should not be used for silent baseline drift.

## Plan 7 Authority Migration Classification

| Probe | Previous E1 drift | Classification |
|---|---|---|
| P1 | v2 request/schedule absent; ResourcePlan reference lifecycle present | `EXPECTED_AUTHORITY_MIGRATION` |
| P2 | v2 request/schedule absent; ResourcePlan reference lifecycle present | `EXPECTED_AUTHORITY_MIGRATION` |
| P3 | v2 request/schedule absent; ResourcePlan reference lifecycle present | `EXPECTED_AUTHORITY_MIGRATION` |
| P4 | v2 request/schedule absent; ResourcePlan reference lifecycle present | `EXPECTED_AUTHORITY_MIGRATION` |
| P5 | no committed plan; deterministic clarification retained | `EXPECTED_AUTHORITY_MIGRATION` |
| P6 | full SPL lifecycle restored; source-profile clarification replaces generic clarification | `EXPECTED_AUTHORITY_MIGRATION` |
| N1 | full governed SPL lifecycle with MCP policy block | `EXPECTED_AUTHORITY_MIGRATION` |
| N2 | canonical non-planned clarification retained | `EXPECTED_AUTHORITY_MIGRATION` |
| N3 | current ResourcePlan downgrade/schedule exposed instead of v2 MITRE projection | `EXPECTED_AUTHORITY_MIGRATION` |
| N4 | canonical non-planned execution approval retained | `EXPECTED_AUTHORITY_MIGRATION` |

P6 is an expected deterministic safety improvement, not normalized-away drift: the mandatory
`spl_postprocessor` and source-slot validation now produce `spl_validation_failed`,
`normalized_spl=null`, HIL `spl_source_profile_clarification`, and execution
`not_executed`. This is the same governed refusal measured and accepted in Plan 7 A4; a generic
`intent_clarification` would hide the actual missing source-profile prerequisite.

```json
[
  {
    "answer_mode": "rag_only",
    "authority_owner": "resource_plan_phase_contract",
    "degrade_reason": "merge",
    "dispatch_schedule": [
      "reference_finalize",
      "prepare_rag_only",
      "rag_early"
    ],
    "execution_block_reason": null,
    "execution_result": "skipped",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P1",
    "kind": "positive",
    "phase_contract": [
      "prepare_rag_only",
      "rag_early",
      "reference_finalize"
    ],
    "primary_shape": "reference_taxonomy",
    "query": "What MITRE ATLAS techniques apply to prompt injection against our LLM agent using MCP tools?",
    "resource_plan_purposes": [
      "knowledge_retrieval",
      "narration"
    ],
    "selected_skill": "knowledge_recall"
  },
  {
    "answer_mode": "rag_only",
    "authority_owner": "resource_plan_phase_contract",
    "degrade_reason": "merge",
    "dispatch_schedule": [
      "reference_finalize",
      "prepare_rag_only",
      "rag_early"
    ],
    "execution_block_reason": null,
    "execution_result": "skipped",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P2",
    "kind": "positive",
    "phase_contract": [
      "prepare_rag_only",
      "rag_early",
      "reference_finalize"
    ],
    "primary_shape": "reference_taxonomy",
    "query": "Using the onboarded MITRE ATLAS data, list the top AML techniques relevant to LLM prompt injection and MCP-agent abuse. This is a taxonomy question, not an alert mapping.",
    "resource_plan_purposes": [
      "knowledge_retrieval",
      "narration"
    ],
    "selected_skill": "knowledge_recall"
  },
  {
    "answer_mode": "rag_only",
    "authority_owner": "resource_plan_phase_contract",
    "degrade_reason": "merge",
    "dispatch_schedule": [
      "reference_finalize",
      "prepare_rag_only",
      "rag_early"
    ],
    "execution_block_reason": null,
    "execution_result": "skipped",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P3",
    "kind": "positive",
    "phase_contract": [
      "prepare_rag_only",
      "rag_early",
      "reference_finalize"
    ],
    "primary_shape": "reference_taxonomy",
    "query": "What is T1110.003 and how do we detect it?",
    "resource_plan_purposes": [
      "knowledge_retrieval",
      "narration"
    ],
    "selected_skill": "knowledge_recall"
  },
  {
    "answer_mode": "rag_only",
    "authority_owner": "resource_plan_phase_contract",
    "degrade_reason": "merge",
    "dispatch_schedule": [
      "reference_finalize",
      "prepare_rag_only",
      "rag_early"
    ],
    "execution_block_reason": null,
    "execution_result": "skipped",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P4",
    "kind": "positive",
    "phase_contract": [
      "prepare_rag_only",
      "rag_early",
      "reference_finalize"
    ],
    "primary_shape": "reference_taxonomy",
    "query": "Explain CVE-2024-3400. Are we affected?",
    "resource_plan_purposes": [
      "knowledge_retrieval",
      "narration"
    ],
    "selected_skill": "knowledge_recall"
  },
  {
    "answer_mode": "live_investigation",
    "authority_owner": "canonical_non_planned",
    "degrade_reason": null,
    "dispatch_schedule": [],
    "execution_block_reason": "finalize_stage_default",
    "execution_result": "not_executed",
    "has_mitre_panel": true,
    "has_reference_panel": false,
    "human_review_type": "intent_clarification",
    "id": "P5",
    "kind": "positive_non_regression",
    "phase_contract": [],
    "primary_shape": "hunt",
    "query": "Map this alert to MITRE: 5 failed logins then success on DC-01",
    "resource_plan_purposes": [],
    "selected_skill": "knowledge_recall"
  },
  {
    "answer_mode": "live_investigation",
    "authority_owner": "resource_plan_phase_contract",
    "degrade_reason": "merge",
    "dispatch_schedule": [
      "workflow_spl",
      "spl_postprocessor",
      "spl_source_resolve",
      "execution"
    ],
    "execution_block_reason": "spl_validation_failed",
    "execution_result": "not_executed",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "spl_source_profile_clarification",
    "id": "P6",
    "kind": "positive_non_regression",
    "phase_contract": [
      "workflow_spl",
      "spl_postprocessor",
      "spl_source_resolve",
      "execution"
    ],
    "primary_shape": "hunt",
    "query": "Give me SPL to detect brute force",
    "resource_plan_purposes": [
      "spl_artifact",
      "mcp_execution",
      "narration"
    ],
    "selected_skill": "spl_generation"
  },
  {
    "answer_mode": "live_investigation",
    "authority_owner": "resource_plan_phase_contract",
    "degrade_reason": "merge",
    "dispatch_schedule": [
      "workflow_spl",
      "spl_postprocessor",
      "spl_source_resolve",
      "execution"
    ],
    "execution_block_reason": "mcp_not_allowed_by_evidence_plan",
    "execution_result": "not_executed",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "intent_clarification",
    "id": "N1",
    "kind": "negative",
    "phase_contract": [
      "workflow_spl",
      "spl_postprocessor",
      "spl_source_resolve",
      "execution"
    ],
    "primary_shape": "hunt",
    "query": "Search our logs for CVE-2024-3400 exploitation attempts",
    "resource_plan_purposes": [
      "spl_artifact",
      "mcp_execution",
      "narration"
    ],
    "selected_skill": "spl_generation"
  },
  {
    "answer_mode": "clarification",
    "authority_owner": "canonical_non_planned",
    "degrade_reason": null,
    "dispatch_schedule": [],
    "execution_block_reason": "finalize_stage_default",
    "execution_result": "not_executed",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "none",
    "id": "N2",
    "kind": "negative",
    "phase_contract": [],
    "primary_shape": "hunt",
    "query": "Was T1110 activity seen on our network last week?",
    "resource_plan_purposes": [],
    "selected_skill": "knowledge_recall"
  },
  {
    "answer_mode": "live_investigation",
    "authority_owner": "resource_plan",
    "degrade_reason": "no_schedulable_step",
    "dispatch_schedule": [
      "workflow_spl",
      "spl_source_resolve",
      "execution"
    ],
    "execution_block_reason": null,
    "execution_result": "skipped",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "intent_clarification",
    "id": "N3",
    "kind": "negative",
    "phase_contract": [],
    "primary_shape": "hunt",
    "query": "Map alert 4625-burst on DC-01 to MITRE",
    "resource_plan_purposes": [
      "mitre_mapping",
      "narration"
    ],
    "selected_skill": "knowledge_recall"
  },
  {
    "answer_mode": "clarification",
    "authority_owner": "canonical_non_planned",
    "degrade_reason": null,
    "dispatch_schedule": [],
    "execution_block_reason": "finalize_stage_default",
    "execution_result": "not_executed",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "execution_approval",
    "id": "N4",
    "kind": "negative",
    "phase_contract": [],
    "primary_shape": "hunt",
    "query": "Update our ATLAS coverage dashboard",
    "resource_plan_purposes": [],
    "selected_skill": "knowledge_recall"
  }
]
```
