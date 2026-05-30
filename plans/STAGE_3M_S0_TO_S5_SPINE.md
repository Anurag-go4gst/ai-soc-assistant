# Stage 3M — S0 → S5 Spine

Canonical index for Splunk MCP result envelope and adapter program.

> Downstream must consume `SplunkResultEnvelope` only past the MCP adapter — never raw MCP dicts.

## Stage index

| Code | Focus | Spec | Status | Commit |
|------|-------|------|--------|--------|
| S0 | MCP readiness design | [docs/stage3m_s0_mcp_readiness_design.md](../docs/stage3m_s0_mcp_readiness_design.md) | Done | `35cecfd` |
| S1 | `SplunkResultEnvelope` + fixture adapter + tests | [docs/stage3m_s1_splunk_result_envelope.md](../docs/stage3m_s1_splunk_result_envelope.md) | Done | `cc00739` |
| S2 | MCP adapter interface; gate + evidence consume envelope (no live MCP) | — | Proposed | — |
| S3 | Experience Center demo consumes envelope | — | Proposed | — |
| S4 | HF shadow proposal/narration demo | — | Proposed | — |
| S5 | First controlled live MCP read + schema validation | — | Proposed | — |

**Commit hash rule:** Update the Commit column when the stage lands (same pattern as Stage 3L / 3K).

## Next (post-S1)

**S2 (controlled):** Adapter interface; migrate `mcp_execution_gate` and `build_source_evidence` to consume `SplunkResultEnvelope` only. Real MCP branch stays `schema_confirmed=false` / `real_schema_unverified` until S5.

## Exit criteria

| After stage | What is true |
|-------------|--------------|
| S1 | Envelope + fixture adapter + tests; legacy gate/evidence/demo unchanged |
| S2 | Adapter interface; gate + evidence consume envelope |
| S3 | Demo fixture path consumes envelope; analyst text unchanged |
| S4 | HF shadow demo path |
| S5 | First controlled live MCP read + real schema validation |

After **S3**: only real MCP branch + first live read validation remain for the MCP result path (S4 if not landed).

## Verification (every code stage)

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```
