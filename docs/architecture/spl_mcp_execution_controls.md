# Additional SPL Generation and MCP Execution Controls

**Status:** Documentation / governance contract only. No runtime enforcement in this pass.  
**Date:** 2026-06-12  
**Related:** `docs/architecture/real_splunk_mcp_safety_contract.md`, `docs/stage3m_s0_mcp_readiness_design.md`, `docs/safeguards.md`, `contracts/splunk_mcp_connection_contract.md`

This document extends the existing Splunk MCP safety and readiness contracts with slot-binding rules, identity/RBAC requirements, workload caps, async search lifecycle, empty-vs-failed result semantics, CIM/tstats policy, multi-step orchestration, and template promotion telemetry. Implementation is deferred until a follow-up engineering pass.

---

## 1. Slot Binding and SPL Injection Prevention

All dynamic slot values must be validated and escaped before entering template rendering.

This applies to all slot types, including:

* host
* user
* src_ip
* dest_ip
* index
* sourcetype
* time_window
* threshold
* port
* CIDR
* zone
* rule name
* country
* application/protocol

Rules:

1. Slot variables must be type-checked before rendering.
2. Slot variables must use strict allowlisted character patterns.
3. String slots must be escaped before insertion into SPL.
4. Numeric slots must be parsed as numbers, not interpolated as raw text.
5. IP/CIDR slots must be validated using IP/CIDR parsers.
6. Index and sourcetype slots must be selected from allowlisted values.
7. User-provided strings must never be inserted directly into raw SPL.
8. LLM-generated slot values must go through the same validator as user-provided slots.
9. Template rendering must fail closed if any slot fails validation.

Example blocked input:

```text
host="server1\" | delete | search *"
```

Expected behavior:

```text
slot_validation_failed
→ no candidate SPL
→ HIL/clarification required
```

The deterministic SPL validator remains mandatory, but it is not a substitute for slot-level input sanitization.

---

## 2. MCP Identity Context and RBAC

Before Splunk MCP execution is enabled, the MCP contract must define the identity model.

Required decision:

```text
Does the MCP search execute as:
1. a shared service account, or
2. the requesting analyst via pass-through / delegated token?
```

Governance rule:

* Preferred model: analyst identity pass-through or delegated scoped token.
* If a service account is used, it must be read-only and restricted to approved indexes/sourcetypes.
* The assistant must not retrieve data beyond the analyst's RBAC permission.
* MCP result envelopes must record the execution identity mode.
* Queries must not bypass Splunk RBAC by using elevated backend credentials silently.

Required MCP metadata:

```json
{
  "identity_mode": "analyst_passthrough | delegated_token | scoped_service_account",
  "rbac_scope_checked": true,
  "allowed_indexes": [],
  "allowed_sourcetypes": [],
  "execution_user": "<redacted-or-role-id>"
}
```

If identity context is missing, MCP execution must remain blocked.

---

## 3. Workload Management, Timeout, and Compute Caps

Row limits are not enough. A bad SPL can consume compute before returning few or zero rows.

Before MCP execution, every Splunk search must have:

* maximum runtime timeout
* earliest/latest time bounds
* result row limit
* index/sourcetype constraints
* optional workload pool / WLM class
* optional search priority tag

Required controls:

```text
SPL_MAX_TIME_SECONDS
SPL_MAX_RESULT_LIMIT
SPL_ALLOWED_INDEXES
SPL_ALLOWED_SOURCETYPES
SPL_DEFAULT_EARLIEST
SPL_DEFAULT_LATEST
SPL_WLM_POOL or equivalent search tag
```

If supported by the Splunk environment, AI-generated searches should be routed to a lower-priority workload pool so production alerting and SOC dashboards are not impacted.

---

## 4. Async MCP Search Lifecycle

Splunk searches may exceed normal agent/request timeouts. MCP execution must support asynchronous search lifecycle.

Recommended MCP tool split:

```text
splunk.submit_search_job
→ returns search_job_id

splunk.poll_search_results
→ checks status and retrieves results
```

Lifecycle:

```text
submit_search_job
→ job_id created
→ poll until completed / failed / timeout / cancelled
→ retrieve result envelope
→ validate result schema
→ convert to SourceEvidence
```

Required job states:

```text
submitted
running
completed
completed_empty
failed
timed_out
cancelled
permission_denied
schema_invalid
```

The planner must not assume that `search_splunk` is a single synchronous call.

If the job is still running beyond timeout, the final answer should say:

```text
The search was submitted but did not complete within the allowed time window. No evidence conclusion was drawn.
```

---

## 5. Empty Result vs Failed Execution

An empty result is not the same as a failed execution.

The MCP result envelope must distinguish:

### Successful empty result

```json
{
  "execution_status": "completed",
  "result_count": 0,
  "collection_status": "collected",
  "evidence_meaning": "negative_result"
}
```

Allowed conclusion:

```text
No matching events were found in the searched source and time window.
```

Not allowed:

```text
No malicious activity exists.
```

### Failed search

```json
{
  "execution_status": "failed",
  "result_count": null,
  "collection_status": "failed",
  "error_type": "syntax_error | permission_denied | timeout | sourcetype_missing | field_extraction_failed"
}
```

Allowed conclusion:

```text
The search did not complete successfully, so no evidence conclusion can be drawn.
```

The LLM must not convert failed execution into negative evidence.

---

## 6. CIM / tstats Performance Rule

When using accelerated Splunk datamodels with `tstats`, require:

```spl
summariesonly=true
```

unless there is an explicit approved exception.

Example:

```spl
| tstats summariesonly=true count from datamodel=Authentication.Authentication by Authentication.user Authentication.src
```

Rules:

1. `tstats` must use approved datamodels only.
2. `summariesonly=true` should be required for performance-sensitive searches.
3. If acceleration is unavailable, the system should fall back to a non-executed draft or ask for source-profile review.
4. The assistant must not silently generate expensive raw scans as a replacement for accelerated datamodel searches.

---

## 7. Subsearch Policy and Multi-Step Orchestration

Subsearches remain blocked by default in generated SPL because they can be expensive, hard to bound, and risky for automated execution.

However, some SOC investigations require multi-step correlation.

Instead of inline subsearches, use orchestrated multi-step search:

```text
Search A:
Find candidate entities, such as IPs, users, hosts, domains.

Extract bounded entity list:
Limit to approved max entity count.

Search B:
Inject validated entities as typed slots into a second template.

Validate Search B:
Run deterministic SPL validation and slot-binding validation.
```

Example:

```text
Step 1: Find suspicious source IPs from authentication logs.
Step 2: Validate extracted IPs.
Step 3: Search firewall logs for those IPs using an allowlisted slot.
```

Subsearches may be allowed only through explicit exception policy:

```text
bounded_subsearch_allowed=true
max_subsearch_rows=N
time_bound_required=true
validator_approved=true
```

Default remains: no subsearches in generated SPL.

---

## 8. SPL Telemetry and Template Promotion Lifecycle

Lab draft SPL and LLM SPL advisory outputs should not become governed templates automatically.

However, the system should collect review telemetry for promotion.

Track:

* draft family
* use_case_id
* analyst reviewed
* analyst modified SPL
* analyst executed outside assistant
* execution successful
* result useful
* false positive / false negative feedback
* required field fixes
* SOC approval status

Promotion lifecycle:

```text
lab_draft
→ analyst_reviewed
→ field_mapped
→ tested_against_fixture
→ SOC approved
→ governed_template_candidate
→ regression tests added
→ active governed template
```

A draft can be promoted only when:

1. source profile is confirmed
2. SPL validator passes
3. SOC-STD-SPL-001 quality checks pass
4. test fixture is added
5. SOC approval is recorded
6. template status changes deliberately from planned/draft to active

---

## 9. Checklist Additions

### SPL Quality Checklist

* [ ] Are all dynamic slot variables type-validated before rendering?
* [ ] Are slot values escaped or normalized before template insertion?
* [ ] Are index and sourcetype values allowlisted?
* [ ] Does the SPL avoid raw user-string interpolation?
* [ ] Does the template prevent SPL injection through host/user/IP/time/window fields?
* [ ] Does any `tstats` query use `summariesonly=true` where applicable?
* [ ] Are subsearches avoided or replaced by orchestrated multi-step searches?
* [ ] Does the query have earliest/latest time bounds?
* [ ] Does the query avoid broad unfielded wildcard base searches?
* [ ] Do all final table fields survive aggregation?

### MCP Readiness Checklist

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
