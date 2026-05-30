# Stage 3M — S0 → S5 Spine

Canonical index for Splunk MCP result envelope and adapter program.

> Downstream must consume `SplunkResultEnvelope` only past the MCP adapter — never raw MCP dicts.

## Stage index

| Code | Focus | Status |
|------|-------|--------|
| S0 | MCP readiness design | Done (docs) |
| S1 | `SplunkResultEnvelope` + fixture adapter + tests | Done |
| S2 | MCP adapter interface; gate + evidence migration | Proposed |
| S3 | Experience Center demo consumes envelope | Proposed |
| S4 | HF shadow proposal/narration demo | Proposed |
| S5 | First controlled live MCP read + schema validation | Proposed |

## Specs

| Stage | Document |
|-------|----------|
| S0 | [docs/stage3m_s0_mcp_readiness_design.md](../docs/stage3m_s0_mcp_readiness_design.md) |
| S1 | [docs/stage3m_s1_splunk_result_envelope.md](../docs/stage3m_s1_splunk_result_envelope.md) |

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
