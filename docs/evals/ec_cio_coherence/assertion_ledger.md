# Assertion-change ledger — EC CIO coherence plan

Every pre-existing test assertion modified by `plans/2026-09-24_1635_ec-cio-coherence-and-lifecycle.md`,
with old → new and why. A changed assertion without a row here fails review.

| Item | Test | Old | New | Why |
|------|------|-----|-----|-----|
| A2 | `backend/app/tests/test_s1_agent_workflow.py::test_s1_agent_plan_ready_on_initial_turn` | opening narrative contains "splunk and mcp tools and rag guidelines" | contains "nothing runs until you approve" and **not** the boilerplate | The boilerplate phrase was the defect (content review X3). Other intent pins (IP, "last 30 days", no "suspicious") unchanged. |
| A2 | `backend/app/tests/test_s2_agent_workflow.py::test_s2_agent_plan_ready_on_initial_turn` | narrative contains boilerplate + "collecting and analyzing logs" | contains "nothing runs until you approve", keeps "customer-facing ai assistant", boilerplate absent | Same as above; "collecting and analyzing logs" was generic filler. |
| A2 | `backend/app/tests/test_s2_agent_workflow.py::test_s2_investigation_tools_are_only_onboarded_connectors` | rendered plan tool labels == {"Splunk MCP", "SOC-KB"} | rendered `tool_ids` == {"splunk_mcp", "soc_kb"} | Labels now come from the tool catalog ("SOC-KB (RAG)"). The intent — only onboarded connectors — is asserted on stable ids. The step-def assertion is unchanged. |
| A2 | `backend/app/tests/test_s7_agent_workflow.py::test_s7_agent_plan_ready_on_initial_turn` | narrative contains boilerplate | contains "nothing runs until you approve", boilerplate absent | Same as S1. "retired", "ot" and the negative pins unchanged. |
| A2 | `frontend/src/components/ec/s1Workspace.test.tsx` (agentLifecycleScrollTarget) | INVESTIGATION_COMPLETE / COMPLETE → `[data-ec-section="executive-summary"]` | → `[data-ec-section="executive-brief"], [data-ec-section="executive-summary"]` | S2/S4/S7 have an empty `executive_summary`, so the old target never existed and the page did not scroll to the outcome. The comma selector prefers the new brief and falls back to the summary. |
