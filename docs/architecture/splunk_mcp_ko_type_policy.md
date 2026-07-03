# Splunk `get_knowledge_objects` type policy

Splunk MCP Server 1.2.x exposes many KO types via `splunk_get_knowledge_objects`. AI-SOC classifies each for discovery vs defer vs block.

## Allow discovery (metadata only)

`saved_searches`, `macros`, `lookups`, `data_models`, `field_extractions`, `field_aliases`, `calculated_fields`, `tags`, `views`, `panels`, `apps`, `eventtypes`

## Discovery with caution

| Type | Policy |
|------|--------|
| `alerts` | Metadata only; may imply scheduled actions — no auto-execution |
| `automatic_lookups` | Metadata only |
| `lookup_transforms` | Metadata only |

## Block or defer for agent execution

| Type | Policy |
|------|--------|
| `workflow_actions` | **Defer execution** — enforcement-adjacent (firewall/SOAR lane); discovery OK at most |
| `mltk_models`, `mltk_algorithms` | Defer unless ML use case scoped |

## Playbook alignment

[`backend/app/connectors/mcp/mcp_tool_playbook.json`](../../backend/app/connectors/mcp/mcp_tool_playbook.json) `splunk_get_knowledge_objects.produces` lists the allow-discovery set above (not `workflow_actions` or MLTK types).
