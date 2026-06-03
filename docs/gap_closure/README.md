# Gap Closure Roadmap — Documentation Pack

**Plan:** [`ai_soc_gap_roadmap_a03fc3c3`](../../.cursor/plans/ai_soc_gap_roadmap_a03fc3c3.plan.md) (Cursor plan store)

**Stage:** P0 through P6/P6-add. P0 documents remain below for registry/deck grounding; the current workflow document records the live query-to-answer behavior after the later-stage implementation.

| ID | Document |
|----|----------|
| Current | [Current query-to-answer workflow](current_query_to_answer_workflow.md) |
| QU bridge | [QU→route_skill validation](qu_route_bridge_validation.md) |
| P0-6 / P0-7 | [Unified 105+ registry](p0_unified_105_registry.md) |
| P0-8 | [48 `likely_routable` + MITRE three layers](p0_stakeholder_48_routable_and_mitre.md) |
| P0-9 | [Live flow-check profile](p0_live_flow_check_profile.md) |
| P0-10 | [Trace and demo labels](p0_trace_demo_labels.md) |
| P0-11 | [Deck zero-ambiguity pack](p0_deck_zero_ambiguity_pack.md) |
| P3 | [MCP evidence matrix and COE contract](p3_mcp_evidence_matrix_and_coe_contract.md) |
| P4 | [SOC RAG intake and stub lineage](p4_soc_rag_intake_and_stub.md) |
| P6 | [Guarded synthesis lab](p6_guarded_synthesis_lab.md) |

**P0 hardening (code):** empty-result sufficiency (`execution_negative_result`), MCP-result injection scan on evidence path, lineage placeholders for future synthesis/guard audit fields.

**Verification:**

```bash
./scripts/run_stage3_governance_regression.sh
cd backend && PYTHONPATH=../backend:.. python3 -m pytest
```
