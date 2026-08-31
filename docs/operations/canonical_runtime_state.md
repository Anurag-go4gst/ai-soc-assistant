# CANONICAL REPO / RUNTIME STATE — USE THIS AS REFERENCE

Canonical production source:

- branch: `master`
- SHA: `9e1b13694b4047560f8ddd77a77282147b46c3fb`

Canonical Mac repo / local Docker stack:

- `/Users/aagarwal/Downloads/ai-soc-assistant-t4-architecture-20260821`

Local URLs:

- frontend: `http://127.0.0.1:3013/chat`
- backend: `http://127.0.0.1:8012`

GitHub master: `9e1b13694b4047560f8ddd77a77282147b46c3fb`

VPS master: `9e1b13694b4047560f8ddd77a77282147b46c3fb`

Mac = GitHub = VPS.

Worktree reconciliation is **COMPLETE**.

## Important cleanup facts

- 7 worktrees reduced to 1 canonical worktree.
- stashes = 0.
- **UNIQUE ACCEPTED WORK OUTSIDE MASTER = NONE.**
- old dirty files were audited; most were byte-identical to master.
- post-P10 docs-only missing metadata was rescued and merged as `9e1b1369`.
- stale/generated P8 evidence was archived, not promoted.
- do **not** recover/reintroduce stale `sidecar_clients.py` SPL optimization timeout changes.
- old branches/worktrees are **NOT** product authority.
- [`architecture.md`](../../architecture.md) remains canonical and **READ ONLY**.

## Production feature posture

- accepted production feature flags = ON
- `AI_SOC_SPL_OPTIMIZATION_LLM_ENABLED=true`

## Pre-P11

- live Splunk MCP execution remains **OFF**
- `MCP_GLOBAL_EXECUTION_ENABLED=false`
- `MCP_SERVER_MOCK_EXECUTION_ENABLED=false`
- `MCP_MODE=mock`
- **P11 NOT STARTED**

## Agent rules

Do not use old worktree SHAs or stale feature branches when diagnosing the current product.

When checking a defect always reproduce first on:

- `master` @ `9e1b1369`
- using the `:3013` / `:8012` local stack.

Do not create another worktree unless a new bounded workstream actually requires one.

---

*Update this file when Mac / GitHub / VPS master move together to a new promoted SHA.*
