# Stage 3M-S0: MCP Readiness Design

**Status:** Design (S0). S1 implements envelope + fixture adapter only.

**Scope:** Read-only Splunk MCP search results after existing SPL validation and execution gates. No live MCP in S0/S1.

---

## Problem

Today Splunk search results move through the stack as **ad hoc dicts**:

- `MockMcpConnector` returns `status`, `rows`, `row_count`, …
- `mcp_execution_gate` copies `_safe_rows` into `execution.results_preview`
- `build_source_evidence` re-sanitizes preview rows

There is no canonical internal contract. Real Splunk MCP JSON shape is **not verified in-repo** (COE URL, transport, auth, tool args, and response schema remain open).

---

## Target architecture

```text
spl_validator → mcp_tool_selector → mcp_execution_gate
  → MCP adapter (mock | fixture | real)
  → SplunkResultEnvelope
  → downstream (execution preview, source_evidence, demo fixtures)
```

**Policy:** Past the adapter, downstream code must consume `SplunkResultEnvelope` only — never raw MCP payloads. Migration is staged: S1 proves fixture path; S2 gate/evidence; S3 demo; S5 live read.

---

## In scope (Stage 3M program)

- Internal `SplunkResultEnvelope` with normalization, truncation metadata, schema-unconfirmed flags
- Fixture/mock-payload adapter (S1)
- MCP adapter interface + real branch marked schema-unconfirmed (S2)
- Consumer migration: execution gate, source evidence (S2), Experience Center demo wiring (S3)
- HF shadow proposal/narration demo path (S4)
- First controlled live MCP read + schema validation (S5)

---

## Out of scope (unchanged)

- Executing `candidate_spl`; only validated `normalized_spl` may reach MCP gate (existing rule)
- `MCP_GLOBAL_EXECUTION_ENABLED` default false
- SAIA / generative tools as candidate-only
- Final LLM synthesis, Answer Guard execution, Splunk writes
- LLM → MCP direct tool calling
- `/chat` analyst answer text changes in S1

---

## Real MCP schema (hypothesis only)

Until COE supplies a signed JSON sample:

| Assumed field | Notes |
|---------------|--------|
| `rows` / results array | List of objects |
| `row_count` or total | May differ from returned row length |
| `status` / error | Failure and timeout paths |
| Tool aliases | `run_splunk_query`, `splunk_run_query` |

All real responses must set:

- `schema_confirmed=false`
- `schema_confirmed_reason=real_schema_unverified`

S5 validates and may flip `schema_confirmed` only after COE sign-off.

---

## Internal envelope safety limits

These are **AI-SOC internal caps**, not claimed Splunk platform limits:

| Limit | Value |
|-------|-------|
| `max_rows` (envelope storage default) | 100 |
| `preview_rows` default | 5 |
| Field cap | 40 |
| Value cap | 240 |

Phrase: *internal envelope safety limits pending real MCP schema validation.*

---

## Stage exit criteria

| After | True |
|-------|------|
| **S1** | Contract + fixture normalization proven; real schema unverified; gate/evidence/demo **not** migrated |
| **S2** | Adapter interface; gate + evidence consume envelope |
| **S3** | Demo fixture path uses envelope; analyst text unchanged |
| **S4** | HF shadow demo path |
| **S5** | First controlled live read + adapter validation |

After **S3**, only the real MCP branch + first live read validation remain for the MCP result path (plus S4 if not done).

---

## Consumer migration map

| Consumer | Stage |
|----------|-------|
| `mcp_execution_gate` | S2 |
| `build_source_evidence` | S2 |
| `demo/scenarios` execution + fixture evidence | S3 |
| Real `SplunkMcpConnector` | S2 stub / S5 live |

---

## Verification

- S1: `pytest app/tests/test_splunk_result_envelope_stage3m_s1.py`
- Each implementation stage: full backend pytest + harness 6/6
