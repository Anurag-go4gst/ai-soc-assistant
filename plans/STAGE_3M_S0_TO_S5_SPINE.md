# Stage 3M — S0 → S5 Spine

Canonical index for Splunk MCP result envelope and adapter program.

> Downstream must consume `SplunkResultEnvelope` only past the MCP adapter — never raw MCP dicts.

## Stage index

| Code | Focus | Spec | Status | Commit |
|------|-------|------|--------|--------|
| S0 | MCP readiness design | [docs/stage3m_s0_mcp_readiness_design.md](../docs/stage3m_s0_mcp_readiness_design.md) | Done | `35cecfd` |
| S1 | `SplunkResultEnvelope` + fixture adapter + tests | [docs/stage3m_s1_splunk_result_envelope.md](../docs/stage3m_s1_splunk_result_envelope.md) | Done | `cc00739` |
| S2 | MCP adapter interface; gate + evidence consume envelope (no live MCP) | [docs/stage3m_s2_splunk_result_adapter.md](../docs/stage3m_s2_splunk_result_adapter.md) | Done | `90224b7` |
| S3 | Experience Center demo consumes envelope | [docs/stage3m_s3_demo_envelope.md](../docs/stage3m_s3_demo_envelope.md) | Done | `d153e44` |
| S4 | HF shadow proposal/narration demo | [docs/stage3m_s4_hf_shadow_demo.md](../docs/stage3m_s4_hf_shadow_demo.md) | Done | `d741db3` |
| S5 | First controlled live MCP read + schema validation | [docs/stage3m_s5_first_live_mcp_read_runbook.md](../docs/stage3m_s5_first_live_mcp_read_runbook.md) | Done (harness); live read pending | `99129b2` |

**Commit hash rule:** Update the Commit column when the stage lands (same pattern as Stage 3L / 3K).

## Next (post-S4)

**S5 live read:** run manual capture under COE when endpoint/auth/tool are available; keep `schema_confirmed=false` until COE reviews `docs/stage3m_s5_live_mcp_schema_capture.json`. Do not wire live MCP into `/chat` until a later stage.

## Exit criteria

| After stage | What is true |
|-------------|--------------|
| S1 | Envelope + fixture adapter + tests; legacy gate/evidence/demo unchanged |
| S2 | Adapter interface; gate + evidence consume envelope; no live MCP |
| S3 | Demo fixture path consumes envelope; analyst text unchanged |
| S4 | HF shadow demo path (lineage only; default off) |
| S5 | Live MCP capture runbook + manual harness; COE schema sign-off pending |

After **S5 harness**: first operator live read + `schema_confirmed=true` only after COE review; real `/chat` MCP branch unchanged until later stage.

## Verification (every code stage)

```bash
cd backend && python3 -m pytest
python3 -m test_harness.harness.runner --json
```
