# Reference Knowledge Probe Baseline

Generated: 2026-07-05 17:59 UTC

Current baseline for the reference-knowledge probe contract. P1-P4 should route through `reference_taxonomy` / `reference_knowledge`; P5/P6/N1-N4 are frozen non-regression rows.

| ID | Kind | Selected skill | Answer mode | Request mode | Shape | Human review | Stages |
|---|---|---|---|---|---|---|---|
| P1 | positive | knowledge_recall | rag_only | reference_knowledge | reference_taxonomy | none | rag_early,reference_finalize |
| P2 | positive | knowledge_recall | rag_only | reference_knowledge | reference_taxonomy | none | rag_early,reference_finalize |
| P3 | positive | knowledge_recall | rag_only | reference_knowledge | reference_taxonomy | none | rag_early,reference_finalize |
| P4 | positive | knowledge_recall | rag_only | reference_knowledge | reference_taxonomy | none | rag_early,reference_finalize |
| P5 | positive_non_regression | knowledge_recall | live_investigation | mitre_knowledge | hunt | intent_clarification | mitre_finalize |
| P6 | positive_non_regression | spl_generation | live_investigation | spl_authoring | hunt | intent_clarification | pre_spl_mcp_discovery,workflow_spl,spl_postprocessor,spl_source_resolve,mcp_execution |
| N1 | negative | spl_generation | live_investigation | spl_authoring | hunt | intent_clarification | pre_spl_mcp_discovery,workflow_spl,spl_postprocessor,spl_source_resolve,mcp_execution |
| N2 | negative | knowledge_recall | clarification | clarification | hunt | none |  |
| N3 | negative | knowledge_recall | live_investigation | mitre_knowledge | hunt | intent_clarification | mitre_finalize |
| N4 | negative | knowledge_recall | clarification | clarification | hunt | execution_approval |  |

## Frozen Non-Regression Contract

- P5/P6/N1-N4 current routes are the non-regression baseline for item 18.
- N3 intentionally duplicates the alert-mapping guard class covered by P5.
- This file is updated deliberately when P1/P2 flip red to green; the probe script should not be used for silent baseline drift.

```json
[
  {
    "answer_mode": "rag_only",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P1",
    "kind": "positive",
    "primary_shape": "reference_taxonomy",
    "query": "What MITRE ATLAS techniques apply to prompt injection against our LLM agent using MCP tools?",
    "request_mode": "reference_knowledge",
    "selected_skill": "knowledge_recall",
    "stage_schedule": [
      "rag_early",
      "reference_finalize"
    ]
  },
  {
    "answer_mode": "rag_only",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P2",
    "kind": "positive",
    "primary_shape": "reference_taxonomy",
    "query": "Using the onboarded MITRE ATLAS data, list the top AML techniques relevant to LLM prompt injection and MCP-agent abuse. This is a taxonomy question, not an alert mapping.",
    "request_mode": "reference_knowledge",
    "selected_skill": "knowledge_recall",
    "stage_schedule": [
      "rag_early",
      "reference_finalize"
    ]
  },
  {
    "answer_mode": "rag_only",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P3",
    "kind": "positive",
    "primary_shape": "reference_taxonomy",
    "query": "What is T1110.003 and how do we detect it?",
    "request_mode": "reference_knowledge",
    "selected_skill": "knowledge_recall",
    "stage_schedule": [
      "rag_early",
      "reference_finalize"
    ]
  },
  {
    "answer_mode": "rag_only",
    "has_mitre_panel": false,
    "has_reference_panel": true,
    "human_review_type": "none",
    "id": "P4",
    "kind": "positive",
    "primary_shape": "reference_taxonomy",
    "query": "Explain CVE-2024-3400. Are we affected?",
    "request_mode": "reference_knowledge",
    "selected_skill": "knowledge_recall",
    "stage_schedule": [
      "rag_early",
      "reference_finalize"
    ]
  },
  {
    "answer_mode": "live_investigation",
    "has_mitre_panel": true,
    "has_reference_panel": false,
    "human_review_type": "intent_clarification",
    "id": "P5",
    "kind": "positive_non_regression",
    "primary_shape": "hunt",
    "query": "Map this alert to MITRE: 5 failed logins then success on DC-01",
    "request_mode": "mitre_knowledge",
    "selected_skill": "knowledge_recall",
    "stage_schedule": [
      "mitre_finalize"
    ]
  },
  {
    "answer_mode": "live_investigation",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "intent_clarification",
    "id": "P6",
    "kind": "positive_non_regression",
    "primary_shape": "hunt",
    "query": "Give me SPL to detect brute force",
    "request_mode": "spl_authoring",
    "selected_skill": "spl_generation",
    "stage_schedule": [
      "pre_spl_mcp_discovery",
      "workflow_spl",
      "spl_postprocessor",
      "spl_source_resolve",
      "mcp_execution"
    ]
  },
  {
    "answer_mode": "live_investigation",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "intent_clarification",
    "id": "N1",
    "kind": "negative",
    "primary_shape": "hunt",
    "query": "Search our logs for CVE-2024-3400 exploitation attempts",
    "request_mode": "spl_authoring",
    "selected_skill": "spl_generation",
    "stage_schedule": [
      "pre_spl_mcp_discovery",
      "workflow_spl",
      "spl_postprocessor",
      "spl_source_resolve",
      "mcp_execution"
    ]
  },
  {
    "answer_mode": "clarification",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "none",
    "id": "N2",
    "kind": "negative",
    "primary_shape": "hunt",
    "query": "Was T1110 activity seen on our network last week?",
    "request_mode": "clarification",
    "selected_skill": "knowledge_recall",
    "stage_schedule": []
  },
  {
    "answer_mode": "live_investigation",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "intent_clarification",
    "id": "N3",
    "kind": "negative",
    "primary_shape": "hunt",
    "query": "Map alert 4625-burst on DC-01 to MITRE",
    "request_mode": "mitre_knowledge",
    "selected_skill": "knowledge_recall",
    "stage_schedule": [
      "mitre_finalize"
    ]
  },
  {
    "answer_mode": "clarification",
    "has_mitre_panel": false,
    "has_reference_panel": false,
    "human_review_type": "execution_approval",
    "id": "N4",
    "kind": "negative",
    "primary_shape": "hunt",
    "query": "Update our ATLAS coverage dashboard",
    "request_mode": "clarification",
    "selected_skill": "knowledge_recall",
    "stage_schedule": []
  }
]
```
