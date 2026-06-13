# Real Splunk MCP Safety Contract

Status: Batch 6 planning contract only. Do not implement or enable real Splunk MCP from this document alone.

This contract defines the safety, approval, audit, and technical requirements that must be satisfied before AI SOC Assistant can use a real Splunk MCP adapter. The current repository baseline still blocks real MCP execution: `backend/app/connectors/mcp/splunk_mcp.py` is a placeholder, `mcp_execution_gate.py` returns `real_mcp_adapter_not_implemented` for non-mock mode, and `MCP_GLOBAL_EXECUTION_ENABLED` plus per-server execution flags default to false.

## Non-Goals

- Do not enable real Splunk MCP.
- Do not add live server URLs, tokens, credentials, or secret references with real values.
- Do not execute SPL against real Splunk.
- Do not bypass `validate_spl()`, human review, or MCP execution gates.
- Do not allow LLMs to call Splunk/MCP tools directly.
- Do not enable production LLM SPL fallback.
- Do not change runtime routing, live skill enums, MITRE behavior, or session-memory authority.

## Current Baseline

Relevant files inspected for this contract:

- `backend/app/connectors/mcp/splunk_mcp.py`: real connector placeholder; all calls are unavailable or `NotImplementedError`.
- `backend/app/connectors/mcp/mock.py`: mock-only execution returns synthetic rows and `mock=true`.
- `backend/app/orchestration/mcp_tool_selector.py`: deterministic tool selection for `spl_search`; execution-eligible live skills are `attack_discovery` and `spl_generation`.
- `backend/app/orchestration/mcp_execution_gate.py`: validates tool selection, global/server execution flags, tool capability, HIL, and blocks non-mock mode today.
- `backend/app/safeguards/spl_validator.py`: blocks unsafe commands, missing time bounds, missing result limit, disallowed indexes/sourcetypes, macros/subsearches/external calls/secrets.
- `backend/app/splunk/capabilities.py`: current expected Splunk tool names and SAIA/core tool capability profile.
- `backend/app/spl/templates.json`: active templates include status, use case, validation rules, time bounds, and result limits.
- `.env.example` and `backend/app/config.py`: execution and connector defaults are disabled or placeholders.

## Confirmed Air-Gapped Tool Surface (2026-06-12)

The customer-confirmed Splunk MCP deployment exposes seven canonical `splunk_*` tools:

| Tool | Policy treatment |
|---|---|
| `splunk_run_query` | Read-only search; only validator-approved, non-null `normalized_spl` may reach the existing execution gate. |
| `splunk_get_info` | Read-only readiness discovery; not evidence authority. |
| `splunk_get_indexes` | Read-only index discovery; results are scoped to the MCP service account's permissions. |
| `splunk_get_index_info` | Read-only detail for a known index. |
| `splunk_get_metadata` | Read-only host/source/sourcetype discovery for query preparation. |
| `splunk_get_user_info` | Sensitive discovery; visible in status, blocked from evidence selection. |
| `splunk_get_knowledge_objects` | Read-only knowledge-object discovery for checking existing detections and macros. |

Official `splunk_*` names are canonical. Livehybrid-style names such as `search_splunk` and `list_indexes` are aliases only and are not present on this air-gapped server. No SAIA/assistant, write/admin, saved-search-execution, or KV-store tools are part of the confirmed surface.

The deterministic planning order follows the investigation pattern described by Splunk Lantern: retrieve the governed runbook, discover indexes and metadata, prepare a bounded query, then synthesize the evidence. In this application, runbooks come from the governed SOC-KB RAG path, not an Atlassian or Confluence MCP. SOAR may become a future playbook source, but no SOAR connector exists today.

Discovery is represented as planned-only records: `splunk_get_indexes` -> `splunk_get_metadata` -> optional `splunk_get_index_info` -> optional `splunk_get_knowledge_objects`. These records do not call MCP. Guided investigations expose the same sequence as a manual analyst checklist while execution gates remain closed.

The real argument schema for `splunk_run_query` remains unconfirmed. `schema_confirmed=false` stays authoritative until COE captures and approves a sample through `live_schema_capture.py`; no unconfirmed response may be promoted to live evidence.

## Activation Gates

All of the following gates must pass before any future real Splunk execution is allowed:

| Gate | Required condition | Current source / future owner |
|------|--------------------|-------------------------------|
| SPL validation | `validate_spl()` returns `approved=true` | `spl_validator.py` |
| Normalized SPL | `spl_validation.normalized_spl` is non-null | `SplValidationEnvelope` |
| Template status | Template is `active`, production-ready, and allowed for the selected use case | `templates.json`, `content_enrichment.json`, future gate check |
| Query shape | Read-only search only; no write/admin/query-side effects | `spl_validator.py`, future adapter preflight |
| Time bounds | `earliest` and `latest` are present; no all-time search | `spl_validator.py` |
| Result limit | `head`/limit or equivalent required, max rows enforced | `spl_validator.py`, future adapter caps |
| Index/sourcetype | Every index and sourcetype is allowlisted | `spl_validator.py`, env policy |
| Blocked commands | `delete`, `collect`, `outputlookup`, `inputlookup`, `rest`, `script`, `map`, `loadjob`, `sendemail`, saved-search execution commands absent | `spl_validator.py` |
| Human approval | Current approval state is `approved_for_read_only_search` for this exact normalized SPL hash or trace action | future approval store |
| Global execution | `MCP_GLOBAL_EXECUTION_ENABLED=true` | config |
| Server execution | target Splunk server `execution_enabled=true` | MCP registry/server config |
| Real server mode | server type/mode is explicitly real Splunk MCP, not mock or unconfirmed fallback | MCP registry + connector |
| Tool allowlist | selected tool capability is `spl_search` and tool name is allowlisted | `mcp_tool_selector.py`, registry |
| User/request authority | authenticated user or request context is authorized to request approval | future approval layer |
| Audit enabled | durable audit sink is available before live execution starts | future audit readiness gate |
| Result adapter confirmed | real MCP response schema is signed/confirmed; no `real_schema_unverified` execution result may be treated as live evidence | `splunk_result_adapter.py`, future COE sample |

Failure of any gate must produce `execution_status_label=not_executed` and either `review_required`, `admin_action_required`, `denied`, `expired`, or `failed`, never `live_executed`.

## Allowed Real Tool Set

Initial real Splunk MCP scope is read-only search only.

Preferred canonical tool names:

- `splunk_run_query`
- `run_splunk_query` as an alias only if the discovered MCP server exposes that name

The selected tool must advertise `capability=spl_search`. If a server exposes different names, the implementation must map them explicitly in the registry and tests before use. User-requested tool names are preferences only; deterministic policy remains authority.

Discovery/status-only tools may be visible but must not execute SPL:

- `splunk_get_info`
- `splunk_get_indexes`
- `splunk_get_index_info`
- `splunk_get_metadata`
- `splunk_get_user_info`
- `splunk_get_knowledge_objects`

SAIA/generative/assistant tools remain blocked for execution authority:

- `saia_generate_spl`
- `saia_explain_spl`
- `saia_optimize_spl`
- `saia_ask_splunk_question`

`splunk_run_saved_search` is out of initial scope even if discovered. Enabling it requires a separate contract because saved searches can hide writes, macros, broad searches, or unreviewed logic.

## Explicitly Blocked Actions

The real adapter and gate must block:

- SPL commands or effects: `delete`, `collect`, `outputlookup`, `inputlookup` writeback, `sendemail`, `map`, `script`, `rest`, `loadjob`, saved-search invocation, macros unless explicitly permitted later.
- Saved search creation, modification, deletion, dispatch, or schedule changes.
- Alert creation, modification, deletion, suppression, or severity changes.
- Notable event modification, status change, ownership change, or suppression.
- Index writes, summary-index writes, lookup writes, KV store writes, or telemetry writeback to Splunk.
- Admin/config endpoints, app/package management, indexer/search-head configuration, role/user management.
- Credential, token, secret, session, or auth metadata lookup.
- Arbitrary REST calls or HTTP egress from SPL or MCP.
- Long-running unbounded searches.
- All-time searches, `earliest=0`, `earliest=all`, or equivalent.
- Broad wildcard searches without index, sourcetype, time bound, aggregation, and result cap constraints.
- Any tool selected by an LLM, SAIA, or user string without deterministic allowlist validation.

## Approval Model

Approval state values:

- `not_requested`
- `review_required`
- `approved_for_read_only_search`
- `denied`
- `expired`
- `admin_action_required`

Rules:

- Approval is per query or per bounded investigation action, not global.
- Approval must expire. Default future recommendation: 15 minutes or the end of the active investigation action, whichever is sooner.
- Approval must bind to `trace_id` and `normalized_spl_sha256`.
- Approval must include the selected MCP server, selected MCP tool, template id, use case id, requested user, approver, approval timestamp, and expiry timestamp.
- Approval cannot be reused after any normalized SPL change, template change, time-window change, selected tool change, or use-case change.
- Approval cannot be granted by session context, LLM output, route-plan suggestions, or user-requested MCP fields.
- Session pins may carry prior context for follow-up, but every execution request must re-enter the approval model.
- If approval is missing, stale, mismatched, or denied, the gate returns `review_required`, `expired`, or `denied` and does not call MCP.
- `admin_action_required` is used for missing connector config, unconfirmed schema, unavailable audit sink, or non-allowlisted tools.

## Required Audit Trail

A future live execution attempt must write an audit record before and after execution. Required fields:

- `trace_id`
- `session_id`
- `turn_id` or request id if available
- authenticated user id / username if available
- selected live execution skill
- planning or analytic skill
- `use_case_id`
- SPL template id
- candidate SPL provider and template status
- normalized SPL
- normalized SPL SHA-256 hash
- validation result, policy version, reject reasons, warnings, enforced limits
- approval status
- approval id
- approver id / role if available
- approval timestamp and expiry timestamp
- execution requested timestamp
- execution started timestamp
- execution completed timestamp
- MCP server id
- MCP server mode/type
- MCP tool name
- result count
- returned preview count
- truncation status and truncation reason
- timeout status
- error status and error type
- `evidence_source=live` only after successful approved real execution
- `execution_status=live_executed | blocked | failed`
- `execution_status_label=live_executed | not_executed | review_required`

Audit entries must not store secrets. If normalized SPL may include sensitive literals, future implementation must define a redacted display SPL plus a secured raw audit policy before production use.

## Result Limits and Timeouts

Initial defaults:

- Max rows: 100 total rows returned from Splunk.
- Preview rows in API response: 5 rows, matching current `RESULT_PREVIEW_CAP`.
- Timeout: 30 seconds maximum MCP call duration unless a lower server timeout is configured.
- Max time window: 24 hours by default; narrower template defaults like `-60m` should remain preferred for authentication pilots.
- Earliest/latest: required for every query.
- All-time search: forbidden.
- Response truncation: if Splunk returns more rows or fields than allowed, truncate response preview, preserve `result_count`, and set truncation metadata in the result envelope/trace.
- Error behavior: fail closed. Return `execution_status_label=not_executed` for blocked preflight, `failed` for connector/runtime errors, and never treat partial/error results as live evidence without explicit envelope status.

Future implementation must enforce limits both in SPL validation and adapter arguments. Validation alone is not enough because server-side caps protect against malformed or future query shapes.

## Secrets and Configuration Requirements

No secrets are stored in this repo. Future deployment configuration must use environment variables or a secret manager.

Required placeholders/config inputs:

- Splunk MCP server URL: `MCP_SERVER_SPLUNK_SOC_URL` or equivalent.
- Transport: `MCP_SERVER_SPLUNK_SOC_TRANSPORT=streamable_http | sse`.
- Auth mode: `MCP_SERVER_SPLUNK_SOC_AUTH_MODE=bearer | none` only where approved.
- Token/secret reference name: secret-manager key or environment variable name; no literal token in repo.
- TLS verification: enabled by default; disabling requires `admin_action_required`.
- Connect timeout seconds.
- Read timeout / execution timeout seconds.
- Max rows.
- Allowed indexes.
- Allowed sourcetypes.
- Tool allowlist containing only read-only search and status/discovery tools.
- Global execution flag.
- Per-server execution flag.
- Audit sink readiness flag or health status.

Existing `.env.example` placeholders remain examples only. Any future docs must continue using `.invalid`, blank values, or secret reference names, not live endpoints or tokens.

## Response and UI Behavior

When real execution is still blocked:

- Show `execution_status_label=not_executed` or `review_required`.
- Show `human_review.required=true` and the blocking reason.
- Do not show live evidence tables.

When future approved live execution succeeds:

- Show that live execution happened explicitly: `evidence_source=live` and `execution_status_label=live_executed`.
- Show approval state and approver/role if available.
- Show selected server/tool.
- Show result count and whether results were truncated.
- Show limitations and missing evidence.
- Show that no remediation, writeback, containment, alert modification, or notable modification was executed.
- Keep candidate SPL and executed SPL labeling distinct.
- MITRE status remains evidence-based. Live search results can provide evidence, but live execution does not automatically confirm MITRE techniques, account compromise, C2, ransomware, or phishing.

## Session Context Interaction

Batch 5 session memory is structured pins only and does not grant execution authority.

Rules:

- Session pins may remember prior trace id, use case id, normalized/candidate SPL, validation status, MITRE status, and execution status.
- Session pins cannot approve execution.
- Session pins cannot preserve HIL approval.
- If a user asks to refine prior SPL, the refined SPL must be revalidated.
- Approval expires if normalized SPL changes.
- Approval expires if selected MCP server/tool changes.
- Stale session context must ask for clarification and cannot execute.
- LLM-generated follow-up text cannot approve execution or choose the real MCP tool.

## Testing Plan for Future Implementation

Future real-adapter implementation must add tests for:

- Real MCP disabled by default.
- `MCP_MODE=splunk_mcp` or registry real server without approval returns blocked/admin review.
- Valid SPL but no approval returns `review_required`.
- Approval with normalized SPL hash mismatch returns blocked.
- Approval with trace/action mismatch returns blocked.
- Unsafe SPL command is rejected before MCP gate.
- Missing time bounds is rejected before MCP gate.
- Missing result limit is rejected before MCP gate.
- Disallowed index/sourcetype is rejected before MCP gate.
- Stale approval returns `expired`.
- Denied approval returns `denied`.
- Session memory cannot approve execution.
- LLM tool recommendation cannot select or approve a real MCP tool.
- User-requested MCP tool cannot bypass deterministic allowlist.
- SAIA/generative tools remain blocked from execution.
- Saved-search execution remains blocked in initial scope.
- Result truncation appears in execution/result envelope and UI trace.
- `evidence_source=live` appears only after approved real execution.
- Failed connector calls return `failed` without live evidence.
- Audit record is written before and after execution.
- Audit record contains normalized SPL hash and no secrets.
- MITRE evidence status is not promoted merely because execution happened.
- Full governance regression still passes with default flags.

## MCP Readiness Checklist

Use when preparing for real Splunk MCP execution (S5+). Full rules: `docs/architecture/spl_mcp_execution_controls.md` §2–§5.

* [ ] Is the MCP execution identity model defined?
* [ ] Does MCP execution respect requesting analyst RBAC?
* [ ] Are service accounts read-only and scope-limited if used?
* [ ] Does MCP support async submit/poll lifecycle for long searches?
* [ ] Are timeout and workload caps enforced?
* [ ] Does the result envelope distinguish completed-empty from failed execution?
* [ ] Are permission errors, syntax errors, and field extraction errors represented separately?
* [ ] Is result injection defense applied before rows reach LLM or answer synthesis?
* [ ] Does empty result produce negative evidence only for the searched source/time window?
* [ ] Does failed execution avoid any evidence conclusion?

## Future Implementation Checklist

Do not start implementation until all items are accepted:

- COE provides signed real MCP server URL, transport, auth mode, and allowed tool names.
- COE provides a signed sample response for the read-only search tool.
- Result adapter schema is updated from `real_schema_unverified` to confirmed.
- Approval store/design is implemented and tested.
- Audit sink readiness is implemented and tested.
- Real adapter has timeout, max-row, TLS, and secret-redaction tests.
- UI copy distinguishes live evidence from mock evidence.
- Full governance regression passes with defaults and with a lab-only real-adapter blocked-path test profile.
