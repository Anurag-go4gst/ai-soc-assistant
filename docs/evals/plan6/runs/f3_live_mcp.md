# Plan 6 F3 — live Splunk/MCP scope

**Verdict: `live_mcp_unproven`.**

## Reason

The controlled read-only live-Splunk test described in F3 (`/chat` → generated SPL →
deterministic validation → HIL/RBAC/MCP gate → real Splunk read-only query → evidence →
grounded answer) **was not run**, because no live endpoint exists on this host:

| Key | Value on the persisted VPS profile |
|---|---|
| `SPLUNK_MCP_BASE_URL` | **empty** |
| `SPLUNK_MCP_TOKEN` | **empty** |
| `MCP_MODE` | `mock` |
| `MCP_GLOBAL_EXECUTION_ENABLED` | `true` |
| `MCP_SERVER_MOCK_EXECUTION_ENABLED` | `true` |

Per the F3 failing-first rule, mock MCP evidence is **not** substituted for live evidence.
No live rows are claimed anywhere in Plan 6.

## What *is* proven

Fail-closed behaviour without credentials is covered deterministically, not by assertion:

```
PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_mcp_execution_gate.py \
  app/tests/test_hil_mock_execution_hardening.py \
  app/tests/test_splunk_mcp_transport.py -q
→ 47 passed
```

- `test_mcp_execution_gate.py:319` and `test_hil_mock_execution_hardening.py:165` assert
  `block_reason == "splunk_mcp_not_configured"` — registry mode without credentials refuses,
  it does not degrade to mock.
- `test_splunk_mcp_transport.py` exercises the submit → poll → fetch lifecycle and the
  result-shape tolerance against `FakeTransport`.

On the F3 VPS window, no MCP call ever executed:

```sql
select event->>'event_type', count(*), count(distinct trace_id)
from mcp_execution_logs where created_at > now() - interval '5 hours' group by 1;
```

| event_type | rows | distinct traces |
|---|---|---|
| `mcp_execution_blocked` | 8 | 8 |
| `mcp_execution_requires_human_review` | 1 | 1 |
| `mcp_tool_discovery_started` | 1 | 1 |
| `mcp_tool_discovery_completed` | 1 | 1 |
| `mcp_tool_selection` | 1 | 1 |

**Zero** executed/succeeded MCP events. One event per trace — no duplicate side effects.

## Consequence for F5

Live Splunk/MCP investigation **cannot be claimed production-ready**. Any GO decision must
be scoped to the capabilities Plan 6 actually proved, and must carry `live_mcp_unproven`
explicitly. The wire contract in `contracts/splunk_mcp_connection_contract.md` stays
`schema_confirmed=false`; the go-live steps in `CLAUDE.md` § *Splunk MCP go-live* remain
outstanding operator work.
