# hooks.md

Suggested local hook policy for this repository.

These hooks are guidance only. Do not install or modify Git hooks without an explicit request.

## Pre-Commit Checks

Run focused checks based on touched files:

- Backend Python changes:
  ```bash
  cd backend
  python3 -m pytest
  ```

- Frontend TypeScript/React changes:
  ```bash
  cd frontend
  npm run build
  ```

- Test harness or execution-boundary changes:
  ```bash
  python3 -m test_harness.harness.runner --json
  TELEMETRY_MODE=none python3 -m test_harness.harness.runner --json
  ```

## Secret Guardrails

Reject commits that include:

- `.env`
- API keys, bearer tokens, session secrets, passwords, or private keys
- raw URLs containing credentials
- status payloads that expose secret values instead of configured booleans

Useful scan patterns:

```bash
git diff --cached --name-only
git diff --cached | grep -Ei 'api[_-]?key|bearer |password|token|session_secret|-----BEGIN'
```

Manual review is still required because placeholder examples may intentionally contain names such as `API_KEY=` with empty or fake values.

## Stage Boundary Guardrails

Until a later stage explicitly enables execution, review staged diffs for accidental additions of:

- SPL generation
- SPL execution
- MCP tool execution
- RAG retrieval
- final LLM synthesis
- Splunk telemetry write paths
- direct LLM-to-MCP tool calling

Useful scan:

```bash
git diff --cached | grep -Ei 'execute_validated_spl|run_query|generate_spl|complete_synthesis|record_mcp_execution|splunk_write|tool_calling.*true'
```

## Commit Message Convention

Use concise imperative messages:

- `Add workflow planning after skill routing`
- `Add multi-MCP and multi-LLM readiness registry`
- `Update agent guidance for readiness stages`

