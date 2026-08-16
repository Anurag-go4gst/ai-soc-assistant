# Splunk MCP live activation checklist (readiness only)

Live MCP execution remains **default-off**. This checklist documents prerequisites; it does not enable execution.

## Pre-go-live gates

1. **Credentials configured** — `MCP_SERVER_SPLUNK_SOC_URL`, bearer token or approved auth mode; secrets never committed.
2. **Server allowlist configured** — metadata tools plus one approved search tool (`splunk_run_query` / alias) only; mutating/SAIA tools blocked.
3. **RBAC / session gates** — app session auth, MCP RBAC policy, per-call SPL execution confirmation (`ai_soc_require_spl_execution_confirmation=true`).
4. **Approved normalized SPL required** — `spl_validation.approved=true` and non-null `normalized_spl`; candidate SPL never executed.
5. **HIL approval** — human review when policy requires; `effective_hil_required` honored in RunContract.
6. **Disallowed tools rejected** — discovery may list admin/generative tools; deterministic policy blocks them.
7. **Execution envelope captured** — live rows carry provenance + sanitized envelope; empty results reported honestly.
8. **Rollback flags documented** — operator sets `MCP_GLOBAL_EXECUTION_ENABLED=false`. Per-server Splunk execution stays pre-armed in the COE seed.

## Verification commands (non-executing)

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_p3_mcp_live_readiness.py app/tests/test_mcp_go_live_checklist.py -q
PYTHONPATH=../backend:.. python3 -c "from app.connectors.mcp.live_readiness import evaluate_splunk_mcp_live_readiness as r; print(r())"
```

Expected default posture: `ready_for_live_splunk_mcp=false`, `mcp_called=false`, `execution_authorized=false`.

## Activation (operator only, after COE sign-off)

1. Complete contract in `contracts/splunk_mcp_connection_contract.md`.
2. Set registry mode + Splunk server config per `.env.splunk-live.example`.
3. Run governance regression: `./scripts/run_stage3_governance_regression.sh`.
4. Enable **only** `MCP_GLOBAL_EXECUTION_ENABLED=true` in the approved environment. Per-server Splunk execution is already pre-armed in the COE profile.
5. Bounded staging smoke with HIL owner present; document rollback owner.

No LLM tool-calling. LLM must never call MCP directly.
