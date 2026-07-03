# Resource onboarding contract (registry schema v2)

Planner-composable resources are declared in [`backend/app/planner/resource_registry_v1.json`](../../backend/app/planner/resource_registry_v1.json) and loaded by [`resource_registry.py`](../../backend/app/planner/resource_registry.py). Schema version **2** adds onboarding lifecycle fields so dispatch stays honest until an operator has verified fixtures and live smoke.

## Lifecycle

| `onboarding_status` | Meaning |
|---------------------|---------|
| `declared` | Row exists; contract not verified — **never dispatch** |
| `contract_verified` | Input/output contract reviewed — still no dispatch |
| `fixture_tested` | Mock/fixture path proven — **mock dispatch allowed** when `availability=fixture_only` |
| `live_smoked` | Operator live smoke passed — **live dispatch allowed** when `availability=available` |

## Dispatchability matrix

| Path | `availability` | `onboarding_status` | Dispatch? |
|------|------------------|---------------------|-----------|
| Mock / fixture | `fixture_only` | ≥ `fixture_tested` | Yes |
| Live | `available` | `live_smoked` | Yes |
| Any | `not_implemented` | any | No |
| Any | `blocked` | any | No |
| Any | any | `declared` | No |

Composer/executor (item 4.2) bind to this matrix; LLM plan promotion (item 1.3) rejects steps on non-dispatchable resources.

## Adding a new MCP tool

1. **Registry row** — `mcp_tool:<server>_<tool>` with `capabilities`, `input_contract`, `policy_tier`, `read_only`, `auth_contract` (env var **names** only).
2. **Policy review** — mutating/admin tools stay `availability=blocked`; search tools need validator + execution gate alignment.
3. **Fixture tests** — mock connector handler + pytest; set `availability=fixture_only`, `onboarding_status=fixture_tested`.
4. **Operator env** — MCP server URL/token in settings; playbook entry in `mcp_tool_playbook.json`.
5. **Live smoke** — one bounded call through the execution gate; then set `availability=available`, `onboarding_status=live_smoked`.

## Adding an HTTP API

1. Row kind `http_api` (legacy alias `api` accepted on load).
2. `auth_contract` lists env var names (e.g. `bearer_token_env`).
3. Start `onboarding_status=declared`, `availability=not_implemented` until contract + fixture exist.
4. Example placeholder: `http_api:cisco_api_placeholder` (declared-only until Cisco API contract is provided).

## Adding an action tool

1. Row kind `action_tool`, `read_only=false`, explicit `capabilities` (e.g. `create_ticket`).
2. Mock ITSM adapter (DG-3) for fixture path; human approval gate before any write.
3. Never dispatch at `declared`; promote through fixture_tested → live_smoked like MCP.

## Cache / reload

`load_resource_registry(reload=True)` re-reads JSON. v1 payloads auto-upgrade to v2 on first load (in-place write). Tests should call `clear_resource_registry_cache()` when mutating the registry file.
