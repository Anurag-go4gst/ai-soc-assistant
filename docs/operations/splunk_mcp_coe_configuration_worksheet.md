# Splunk MCP COE configuration worksheet

**COE sign-off:** 2026-07-03  
**Manifest reference:** [`docs/splunk_mcp_tool_manifest_2026-07-03.json`](../splunk_mcp_tool_manifest_2026-07-03.json)

## Splunk platform (operator)

- [x] Splunk MCP Server app installed on SH/SHC (Splunkbase)
- [x] REST API access enabled (Splunk Cloud if applicable)
- [x] Token authentication enabled on instance
- [x] Service account role has `mcp_tool_execute`
- [x] Encrypted MCP token created (`mcp_tool_admin` + `edit_tokens_own`)
- [x] Server-side tool toggles reviewed (core `splunk_*` on; SAIA per policy)
- [x] Guardrails recorded (Timeout ___s, default rows ___, rate limit ___)
- [ ] TLS verification policy recorded (`SPLUNK_MCP_TLS_VERIFY`, CA path if private CA)
- [ ] Encrypted MCP token supplied as env or file reference (never committed)

## AI-SOC Settings (operator)

1. Settings → MCP Registry → Splunk MCP connection
2. Paste **exact** endpoint URL from Splunk MCP app
3. Paste encrypted bearer token (shown once at creation)
4. **Test connection** → Connected / authenticated
5. **Discover tools** → `splunk_run_query` (or `run_splunk_query` alias) present
6. Enable **Allow saved search execution** only after COE saved-search inventory signed
7. Save connection (execution stays env change-control only)

## Verification commands

```bash
PYTHONPATH=backend:. python3 scripts/eval_splunk_mcp_coe_qualification.py --check
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_splunk_mcp_coe_qualification.py app/tests/test_splunk_mcp_manifest_validation.py app/tests/test_p3_mcp_live_readiness.py -q
PYTHONPATH=../backend:.. python3 -c "from app.connectors.mcp.live_readiness import evaluate_splunk_mcp_live_readiness as r; print(r(coe_contract_approved=True))"
```

## Catalogue auto-execute (DG-5)

- Kill-switch: `AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED` (default `false`)
- Pilot map: `backend/app/coverage/catalogue_execution_map_v1.json`
- Enable flag only after pilot rows `coe_verified=true` and staging smoke

## Rollback

- `MCP_GLOBAL_EXECUTION_ENABLED=false`
- `MCP_SERVER_SPLUNK_SOC_EXECUTION_ENABLED=false`
- `AI_SOC_CATALOGUE_AUTO_EXECUTE_ENABLED=false`
- Splunk app: Invalidate Keys only with change window (rotates all encrypted tokens)
