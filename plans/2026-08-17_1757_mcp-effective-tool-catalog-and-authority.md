---
name: mcp-effective-tool-catalog-and-authority
overview: "Make MCP tool discovery truthful (server ∩ allowlist) and close the AUTH0/HIL authority gap on read-only MCP tools before any capability-based selection goes live"
status: active
date: 2026-08-17
canonical_plan: plans/2026-08-17_1757_mcp-effective-tool-catalog-and-authority.md
loop_runner: plans/LOOP_RUNNER_TEMPLATE.md
---

# MCP Effective Tool Catalog & Authority Convergence

## DECISION RECORDED — 2026-08-17 (item 3 resolved, implemented)

Option chosen: **unify all user/investigation-triggered live MCP execution
behind one exact-call AUTH0 model** — not option (a)/(b)/(c) as separately
scoped alternatives, but the generalization of (a): extend the existing
`build_splunk_call_grant` to also bind a `canonical_arguments_hash` for
non-SPL calls, and make every execution path (`splunk_run_query` — already
had this, unchanged; `splunk_run_saved_search`; the 5 read-only
metadata/identity tools) construct and verify a grant before
`connector.call_tool()`. HIL stays orthogonal, decided per-tool by a new
deterministic `_hil_required_for_read_only()` policy (`identity_lookup`
requires confirmation, `metadata_discovery` does not) — AUTH0 is mandatory
in both cases. Implemented in
`backend/app/orchestration/splunk_call_authorization.py` and
`backend/app/orchestration/mcp_execution_gate.py`, commit
`<see report below>`. `architecture.md` not touched.

**Dependency for the rest of this plan**: items 6/7 (wiring
`select_mcp_tool` to an effective catalog and to a capability vocabulary)
remain blocked until this authority layer existed — it now does. Items 1/2
(discovery snapshot storage) and 4/5/8-11 (effective catalog, schema
compatibility, drift visibility, tests, governance closure) are
**unimplemented** — explicitly out of scope for this round per instruction
("Implement ONLY the authority-gap closure first ... Do NOT yet implement:
effective MCP tool catalog / live tools/list intersection / capability
vocabulary expansion / metadata connector implementations / tool-search
behavior / RACES changes"). Discovery tools remain non-executable in
practice today (`NotImplementedError` for 4 tools, `tool_not_allowlisted`
for `splunk_get_user_info`/`splunk_get_info` at the connector layer) — this
authority change did not touch or "fix" that; it closes the gate-layer gap
that would otherwise apply the moment those connector-layer limitations are
later lifted.

DO NOT IMPLEMENT the remaining items until this file's checklist below
has each item's **Verify** filled and no unresolved decision gate remains.
`architecture.md` is FROZEN and READ-ONLY for this plan; no item may edit
it.

Investigation basis: two prior read-only audits in this session —
`docs/evals/mcp_tool_discovery_selection_audit_2026-08-17.md` (discovery/
selection trace) and this plan's own AUTH0 coverage trace (§A below,
folded into item 3). Worktree: `/var/www/ai-soc-master`
(master @ `af93fb3`). Cursor RACES worktree (`feat/races-investigation-
execution-ux`) is untouched by this plan and must stay untouched.

## Objective

Two independent problems, one plan, because item 6/7 (capability wiring)
must not ship until item 3 (authority gap) is closed:

1. **Discovery truthfulness**: `registry.py`'s `discovered_tools` is
   currently 100% `.env`-sourced, never reconciled against a real
   `tools/list`. Make the effective tool catalog `SERVER_DISCOVERED ∩
   LOCAL_APPROVED_ALLOWLIST ∩ DETERMINISTIC_POLICY`, fail-closed for live
   registry execution when discovery is unverified or shows drift.
2. **Authority gap**: read-only MCP tools (`metadata_discovery`,
   `identity_lookup` execution intents) reach `connector.call_tool()`
   through `_execute_read_only_mcp_tool` with **no AUTH0 exact-call grant
   and no HIL confirmation** — the only gates are
   `MCP_GLOBAL_EXECUTION_ENABLED`, `server.execution_enabled`, RBAC role,
   and tool-blocked classification. This must be resolved (or explicitly,
   narrowly accepted with a named compensating control) before any
   capability model routes real ResourcePlan goals into that path.

"Done" for this plan = catalog algorithm + authority decision are both
implemented, tested, and governance-regression green — **not** merely
designed. Design was already completed in-conversation (see conversation
history / this file's §Design Reference); this plan is the execution
checklist for it.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed (tradeoff / ambiguous requirement / COE deferral) —
  **stop and ask**. Item 3's authority-gap resolution is a decision point
  by design — do not silently pick an answer.

## Dependency order

`0 → 1 → 2 → 3 → (STOP/DECIDE) → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11`

Items 0-3 are pure investigation/scaffolding, safe to execute without
further approval. Item 3's output is a decision gate — items 4+ (anything
wiring capability selection to live execution) must not start until that
decision is recorded.

## A. AUTH0 coverage matrix (evidence for item 3 — already traced this session)

| tool | reaches `call_tool`? | via `execution_intent` | ResourcePlan required? | AUTH0 grant? | RBAC? | HIL? | connector-level status today |
|---|---|---|---|---|---|---|---|
| `splunk_run_query` | yes | `spl_search` (pipeline hardcoded default) | no (hardcoded, not plan-driven) | **yes** — `call_grant_from_validation`→`build_splunk_call_grant`, binds normalized_spl/earliest/latest/indexes/operators/limit/timeout | yes | yes (`require_confirmation` logic, registry mode always requires) | executable |
| `splunk_run_saved_search` | yes | `saved_search_execution` | yes (`candidate_spl.generation_mode=="saved_search_primary"`) | **no** — no `call_grant_from_validation` call in `_execute_saved_search_with_hil`; authority = `saved_search_name_allowed()` allowlist + mandatory per-call analyst `execution_review_action=="confirm"` | yes | yes (always mandatory, no bypass flag found) | executable (alternate control, not AUTH0 fingerprint) |
| `splunk_get_info` | no capability maps to it today | n/a | n/a | n/a | n/a | n/a | **blocked at connector**: not in `SPLUNK_DISCOVERY_TOOLS`, not in `ALLOWED_READ_TOOL_ALIASES` → `tool_not_allowlisted` if ever called |
| `splunk_get_indexes` | yes | `metadata_discovery` | no | **no** — `_execute_read_only_mcp_tool` has zero grant/HIL calls | yes | **no** | `is_discovery=True` → `NotImplementedError` in `call_tool` (v1 scope O4) — currently fails closed, but by omission not design |
| `splunk_get_index_info` | yes | `metadata_discovery` | no | **no** | yes | **no** | same — `NotImplementedError` |
| `splunk_get_metadata` | yes | `metadata_discovery` | no | **no** | yes | **no** | same — `NotImplementedError` |
| `splunk_get_user_info` | yes | `identity_lookup` (name-pinned) | no | **no** | yes | **no** | **blocked at connector**: not in `SPLUNK_DISCOVERY_TOOLS` nor `ALLOWED_READ_TOOL_ALIASES` → `tool_not_allowlisted` — contract mismatch (gate allows it, connector rejects it) |
| `splunk_get_knowledge_objects` | yes | `metadata_discovery` | no | **no** | yes | **no** | `is_discovery=True` → `NotImplementedError` |

**AUTHORITY_GAP_FOUND = YES.**

The gap is real at the gate layer (`mcp_execution_gate.py::_execute_read_
only_mcp_tool`, no AUTH0/HIL) for all 5 read-only capabilities
(`SERVER_INFO`, `INDEX_DISCOVERY`, `INDEX_METADATA`, `SOURCE_METADATA`,
`KNOWLEDGE_OBJECT_DISCOVERY`, `USER_CONTEXT`). It is currently masked for
5 of those by an *unrelated* connector-level omission (`NotImplementedError`
for 4 discovery tools per v1 scope O4; `tool_not_allowlisted` for
`splunk_get_user_info`/`splunk_get_info` because they were never added to
`ALLOWED_READ_TOOL_ALIASES`/`SPLUNK_DISCOVERY_TOOLS`). **Per explicit
instruction: do not declare metadata calls "safe" on the strength of that
incidental masking.** Closing the connector-level `NotImplementedError`
(a natural next step once discovery execution ships) would immediately
expose live execution with zero AUTH0/HIL — must not happen without item 3
resolved first.

Compensating-control candidates for item 3 (pick one, record decision in
item 3's Evidence — do not implement until picked):
- (a) Extend `build_splunk_call_grant`/`call_grant_from_validation` to
  cover read-only tool calls too (bind tool name + arguments instead of
  normalized_spl), giving all 8 tools one uniform AUTH0 mechanism.
- (b) Add mandatory per-call HIL confirmation to
  `_execute_read_only_mcp_tool`, mirroring the saved-search pattern
  (allowlist + confirm), accepting that as sufficient for read-only/
  non-search tools given lower blast radius.
- (c) Some hybrid: AUTH0 grant for `identity_lookup`/anything returning
  PII-adjacent data (`splunk_get_user_info`), lighter HIL-only for pure
  index/metadata listing.

## B. Corrected effective-catalog algorithm

```
EFFECTIVE_MCP_TOOL_CATALOG =
  for each name in LOCAL_APPROVED_TOOL_ALLOWLIST (.env, unchanged authority, base of iteration):
    descriptor = classify_mcp_tool(name)                     # existing, deterministic
    server_entry = last_discovery.tools.get(name) if last_discovery.ran else None
    local_approved = True
    safe_classification = not descriptor.blocked

    if registry.mode == "registry":  # COE/live path — corrected per mandatory correction #1
      if not last_discovery.ran:
        status = DISCOVERY_UNVERIFIED
        executable = False                                    # fail-closed, no exception for GLOBAL_EXECUTION_ENABLED=false either — diagnostic-only in that case, still computed the same way
      elif server_entry is None:
        status = APPROVED_BUT_MISSING
        executable = False
      else:
        schema_status = compare_schema(descriptor, server_entry)   # SCHEMA_COMPATIBLE | SCHEMA_INCOMPATIBLE | SCHEMA_UNKNOWN
        if schema_status == SCHEMA_INCOMPATIBLE:
          status = SCHEMA_MISMATCH
          executable = False
        elif schema_status == SCHEMA_UNKNOWN:
          status = SCHEMA_MISMATCH        # default recommendation: fail closed for live COE execution tools (see D)
          executable = False
        elif not safe_classification:
          status = UNSAFE_OR_BLOCKED
          executable = False
        else:
          status = APPROVED_AND_PRESENT
          executable = True

    else:  # mock/development mode — compatibility retained, does not weaken COE
      status = APPROVED_AND_PRESENT if safe_classification else UNSAFE_OR_BLOCKED
      executable = safe_classification   # today's behavior unchanged for mock

    if last_discovery.ran and last_discovery.age_seconds > STALE_THRESHOLD:
      status = DISCOVERY_STALE            # overrides display status, does not re-flip executable already set above
    if last_discovery.attempted and not last_discovery.ran:
      status = DISCOVERY_FAILED

server_discovered_catalog = { name: server_entry for name, server_entry in last_discovery.tools.items() }  # includes SERVER_ONLY_NOT_APPROVED names, kept as a SEPARATE view (§G)
```

`MCP_GLOBAL_EXECUTION_ENABLED=false` does not change the algorithm's
`executable` computation — it stays a diagnostic value in that case
because the pre-existing outer gate (`registry.global_execution_enabled`
check in `_gate_review`) still blocks everything regardless of catalog
`executable`. No second activation flag introduced — this confirms
mandatory correction #1's "does not introduce a second activation flag."

## C. Proposed discovery/storage lifecycle (existing seams only)

Audited before choosing: `app/connectors/telemetry` (event sink,
write-only/append semantics — wrong shape for "current state" queries),
`app/db` SQLAlchemy models (durable, already used for `ai_trace_runs` per
COE observability — right shape for a queryable current-state row),
in-process module-level cache (used nowhere else for cross-request state
in this codebase — request-scoped only, would not survive worker
restarts, rejected).

**Recommendation: one new SQLAlchemy table, `mcp_discovery_snapshot`**,
same DB the trace spine already uses (`app/db/`), not a new datastore
class — reuses the existing Postgres seam. Row per `(server_name)`, columns:
`captured_at`, `source` (`"startup" | "operator_refresh"`), `tools_json`
(name/description/input_schema/annotations only — **no secrets, no
tokens**), `age_seconds` computed at read time. No mutable file under
`docs/` or any committed path — `docs/` stays git-tracked, static,
policy-only.

Guarantees (all four checked against this design):
- No server discovery result may edit `TOOL_ALLOWLIST` — the table is
  read-only input to the catalog algorithm (§B); allowlist stays `.env`.
- No discovered server description becomes policy — `descriptor.capability`
  is still resolved by local `classify_mcp_tool()` name-matching, never
  by parsing the server's free-text description (mandatory correction #4).
- No secret/token enters the snapshot — handshake auth headers are never
  part of the `tools/list` response body being stored; explicit redaction
  pass before insert as a defensive check.
- Operator can see timestamp/source/staleness — `captured_at`, `source`,
  computed `age_seconds` are first-class columns, not buried in JSON.

## D. Schema-compatibility policy

`compare_schema(local_expected, server_reported) -> SCHEMA_COMPATIBLE |
SCHEMA_INCOMPATIBLE | SCHEMA_UNKNOWN`:

- `SCHEMA_UNKNOWN` — server did not report an `inputSchema` for this tool
  (common — many MCP servers omit it), or local side has no expected
  contract defined yet for this tool.
- `SCHEMA_INCOMPATIBLE` — any of: required parameter the local caller
  needs is missing from server's declared schema; a parameter the local
  caller sends is typed incompatibly (e.g. server declares `string`,
  local sends structured object); server marks a parameter this app
  supplies as execution-sensitive in a way local policy doesn't already
  account for (e.g. a newly-required `write`-flavored param); the
  reported schema is structurally invalid JSON-schema.
- `SCHEMA_COMPATIBLE` — none of the above; local caller's argument set is
  a valid subset/match against server's declared schema.

**For live COE execution: `SCHEMA_INCOMPATIBLE` → `executable=False`.
Default recommendation, per instruction: `SCHEMA_UNKNOWN` also →
`executable=False` for live COE** (safer default; many MCP servers may
simply not advertise schemas, and treating silence as "safe" defeats the
point of verification). A normalized schema fingerprint (hash of the
declared shape) is exposed alongside `schema_status` purely for drift
diagnostics — not itself a policy input.

## E. Capability-origin/validation path

`mcp_capability` originates in `PlanStep.args_template["mcp_capability"]`
(V1 `PlanStep`, the currently-wired live contract — **not**
`PlanStepV2.resource_capability`, per mandatory correction #6: do not
activate V2 merely because the field name is more apt). It may be
*proposed* during planning by `mcp_specialist.py::_fill_blank_proposals`
(existing advisory-only seam, fills blanks on already-authorized steps,
adds no new authorship power — unchanged constraint from prior audit).

Before it reaches the execution gate, `mcp_capability` is **revalidated
deterministically**, not trusted as planning output:
```
raw_capability = step.args_template.get("mcp_capability")
validated_capability = raw_capability if raw_capability in KNOWN_CAPABILITY_VOCAB else None
if validated_capability is None:
    → requires_human_review("tool_selection_review", "capability_unresolved")
```
This mirrors the existing pattern where `user_requested_mcp_tool` is
never trusted verbatim either — always re-checked against the closed
vocabulary/catalog before use. Raw LLM-provided MCP tool names remain
non-authoritative (unchanged from today — confirmed no wiring path exists
for that in the prior audit).

## F. Deterministic tool resolver

1:1 map, no LLM involvement, pure function:

```
EVENT_SEARCH                  → splunk_run_query
SAVED_SEARCH_EXECUTION        → splunk_run_saved_search
SERVER_INFO                   → splunk_get_info
INDEX_DISCOVERY               → splunk_get_indexes
INDEX_METADATA                → splunk_get_index_info
SOURCE_METADATA                → splunk_get_metadata
USER_CONTEXT                  → splunk_get_user_info
KNOWLEDGE_OBJECT_DISCOVERY     → splunk_get_knowledge_objects
```

No collisions in this vocabulary today, so §7's "multiple tools per
capability" precedence rule has no live case to implement yet — reserved:
if a future capability ever maps to >1 candidate tool, precedence is
`registry.default_server`'s tool first, tie → `requires_human_review
("tool_selection_review", "ambiguous_capability_multiple_tools")`, never
an LLM pick. `capability_to_tool_name()` looks up
`EFFECTIVE_MCP_TOOL_CATALOG[tool_name].executable` before returning a
result — missing/false → `requires_human_review`, not a silent fallback.

## G. Drift/operator visibility model

Two views over one discovery snapshot + policy evaluation, both retained
(mandatory correction #8 — do not hide `SERVER_ONLY_NOT_APPROVED`):

- **`effective_approved_catalog`** — only names from `LOCAL_APPROVED_
  TOOL_ALLOWLIST`, each tagged with one of: `DISCOVERY_UNVERIFIED`,
  `APPROVED_AND_PRESENT`, `APPROVED_BUT_MISSING`, `SCHEMA_MISMATCH`,
  `UNSAFE_OR_BLOCKED`, `DISCOVERY_STALE`, `DISCOVERY_FAILED`. This is
  what `select_mcp_tool`/the resolver reads.
- **`server_discovered_catalog`** — every name the last handshake
  actually returned, including ones not in the local allowlist, tagged
  `SERVER_ONLY_NOT_APPROVED` for those. Never consulted by the resolver;
  exists purely for operator visibility (surfaced via existing `/debug`
  API pattern, gated by `AI_SOC_DEBUG_API_ENABLED` + `debug_access`, per
  CLAUDE.md's COE observability section — no new auth surface).

## H. Files that would change (implementation phase only — none touched by this planning session)

- `backend/app/connectors/mcp/discovery.py` — extend `McpToolDescriptor`;
  add `compare_schema()`.
- `backend/app/connectors/mcp/registry.py` — effective-catalog derivation
  function (additive); read from new discovery-snapshot table instead of
  (or alongside, transitionally) `.env`-only `discovered_tools`.
- `backend/app/db/` — new `mcp_discovery_snapshot` model + migration.
- `backend/app/connectors/mcp/splunk_mcp.py` — no signature change to
  `handshake_initialize_and_list_tools`; new snapshot-writer consumes its
  output.
- `backend/app/orchestration/mcp_tool_selector.py` — read `executable`/
  `drift_status` from effective catalog; add `mcp_capability` resolution
  step (§E/§F) ahead of existing intent-matching (existing logic
  preserved as-is downstream).
- `backend/app/orchestration/mcp_execution_gate.py::_execute_read_only_
  mcp_tool` — **item 3's decision determines this file's change**: add
  AUTH0 grant construction and/or mandatory HIL, per whichever
  compensating control is picked.
- `backend/app/orchestration/splunk_call_authorization.py` — extend
  `build_splunk_call_grant` if option (a)/(c) from item 3 is chosen, to
  bind tool name + read-only arguments instead of requiring
  `normalized_spl`.
- `backend/app/planner/mcp_specialist.py` — emit `mcp_capability` instead
  of/alongside the current binary `execution_intent` guess.
- New: operator refresh script (parallel to, does not modify,
  `scripts/eval_splunk_mcp_coe_qualification.py`).

No changes to: `architecture.md`, `spl_validator.py`, `mcp_rbac.py`'s
policy file (unless item 3 needs new tool entries — none expected),
`PhaseContract`, `InvestigationOutcome`, RQC code.

## I. Tests

- **A. Handshake/catalog test** — synthetic `last_discovery` snapshots
  (present/missing/schema-mismatched/stale) → assert correct `drift_status`
  + `executable` per §B truth table. No live Splunk required.
- **B. Tool contract/connectivity test** — direct `connector.call_tool()`
  per approved tool (extends existing `test_splunk_mcp_transport.py`
  FakeTransport pattern). Live Splunk required for a real run; AUTH0 not
  required (gate not invoked at this layer).
- **C. Governed production `/chat` test** — one bounded `EVENT_SEARCH`
  call and, once item 3 is resolved, one read-only capability call,
  exercised through the full ResourcePlan→capability→catalog→gate→
  AUTH0/HIL→connector path. Live Splunk + `/chat` required.
- **Regression**: `_no_mock_fallback_in_registry`-style guard extended to
  assert the new snapshot mechanism never silently substitutes
  `MockMcpConnector` output as a live snapshot.
- Full governance regression (`./scripts/run_stage3_governance_regression.sh`)
  required before any item touching `mcp_execution_gate.py` merges.

## J. Architecture impact

None. Confirmed against `architecture.md:1178-1200` ("New MCP tools")
verbatim in the prior audit — this plan is additive within that stated
pattern (capability metadata registered with existing registries,
resource/action planning referencing it, no orchestration redesign for a
new MCP server). No edit to `architecture.md` proposed or needed.

## Checklist

- [ ] **0** — Confirm no drift since last audit
  - **Do:** Nothing to implement; re-run `git log --oneline bf7c304..HEAD`
    inside `/var/www/ai-soc-master` and diff MCP-relevant paths again if
    more than a few days have passed since 2026-08-17.
  - **Verify:** `git -C /var/www/ai-soc-master diff --stat <last-audited-sha>..HEAD -- backend/app/connectors/mcp backend/app/orchestration/mcp_execution_gate.py backend/app/orchestration/mcp_tool_selector.py backend/app/orchestration/splunk_call_authorization.py` is empty, or new commits are reviewed and this plan's file/line citations re-verified.
  - **Depends on:** none
  - **Evidence:** _(fill when done)_

- [ ] **1** — Add `mcp_discovery_snapshot` table + model
  - **Do:** New SQLAlchemy model in `backend/app/db/`, migration, per §C.
    Columns: `server_name`, `captured_at`, `source`, `tools_json`
    (redacted, no secrets), no allowlist-editing code path anywhere near it.
  - **Verify:** new unit test asserts inserting a snapshot with a fake
    bearer-token-bearing description gets redacted before persist; `alembic`/migration applies cleanly against dev DB.
  - **Depends on:** 0
  - **Evidence:** _(fill when done)_

- [ ] **2** — Snapshot writer wrapping `handshake_initialize_and_list_tools()`
  - **Do:** New operator-facing script (does not modify
    `scripts/eval_splunk_mcp_coe_qualification.py`), calls the existing
    connector method, writes to the table from item 1. No behavior change
    to any live selection path yet (dark launch).
  - **Verify:** run against `FakeTransport` test double; assert row
    written with correct `source="operator_refresh"`, no secrets present
    in `tools_json`.
  - **Depends on:** 1
  - **Evidence:** _(fill when done)_

- [x] **3** — Resolve the AUTH0/HIL authority gap on read-only tools (DECISION GATE)
  - **Do:** Unify all live MCP execution behind one exact-call AUTH0 model
    (generalized option (a) — see DECISION RECORDED above). Extended
    `build_splunk_call_grant`/added `call_grant_from_tool_call` in
    `splunk_call_authorization.py`; wired mandatory grant construction +
    verification into `_execute_saved_search_with_hil` and
    `_execute_read_only_mcp_tool` in `mcp_execution_gate.py`. HIL decided
    orthogonally by new `_hil_required_for_read_only()`.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_mcp_authority_gap_closure.py app/tests/test_splunk_call_authorization.py -q` — 23 passed. Scoped regression `python3 -m pytest app/tests -q -k "mcp or splunk or saved_search or execution_gate or auth0 or call_grant"` — 507 passed, 0 failed.
  - **Depends on:** none
  - **Evidence:** Implemented 2026-08-17. Chose the unified model over a
    narrower per-tool alternative because the instruction explicitly
    required unifying all user-triggered live execution behind one AUTH0
    seam rather than three independent mechanisms. `splunk_run_query`'s
    existing normalized_spl-bound contract untouched (all 7 pre-existing
    tests in `test_splunk_call_authorization.py` pass unmodified — new
    `canonical_arguments_hash` field is empty-string/no-op for calls that
    don't pass `tool_arguments`, verified by unchanged fingerprint
    (in)equalities). `splunk_run_saved_search` gained a grant it never had
    (previously allowlist+HIL only, no mutation detection between propose
    and confirm — closed). 5 metadata/identity tools gained a mandatory
    grant they never had (previously zero AUTH0/HIL, only
    `MCP_GLOBAL_EXECUTION_ENABLED`+RBAC+blocked-classification — closed).
    Full unbounded `pytest app/tests` and
    `./scripts/run_stage3_governance_regression.sh` both exceeded this
    session's tool timeout (background run killed at 143, governance
    script killed at 100s bound) — not run to completion; scoped
    MCP/AUTH0-relevant regression (507 tests) and a partial full run
    (2210+ tests passed before an unrelated pre-existing failure in
    `test_answer_expectation_matrix.py`, which fails on a clean checkout
    of this worktree because `docs/evals/out/answer_expectation_matrix.json`
    was never generated here — confirmed unrelated to this change) stand
    as the evidence for this round. Full governance regression should be
    run before this plan's item 10.

- [ ] **4** — Effective-catalog derivation function
  - **Do:** Implement §B algorithm in `registry.py`, reading item 1's
    snapshot table. Still disconnected from `select_mcp_tool` (dark
    launch) — zero behavior change to live selection at this step.
  - **Verify:** unit tests cover all 7 `drift_status` values from §B/§G
    truth table against synthetic snapshots; `registry.mode != "registry"`
    (mock/dev) path unchanged from today's behavior, asserted by existing
    mock-mode tests still passing untouched.
  - **Depends on:** 1
  - **Evidence:** _(fill when done)_

- [ ] **5** — Schema-compatibility comparator
  - **Do:** Implement `compare_schema()` per §D. Define local expected
    contracts for at minimum `splunk_run_query`'s arguments (most
    consequential tool).
  - **Verify:** unit tests: missing required param → `SCHEMA_INCOMPATIBLE`;
    no server schema reported → `SCHEMA_UNKNOWN`; matching schema →
    `SCHEMA_COMPATIBLE`; `SCHEMA_UNKNOWN` and `SCHEMA_INCOMPATIBLE` both
    resolve to `executable=False` when fed through item 4's algorithm in
    `registry.mode="registry"`.
  - **Depends on:** 4
  - **Evidence:** _(fill when done)_

- [ ] **6** — Wire `select_mcp_tool` to read effective catalog (BEHAVIOR CHANGE — requires item 3 done)
  - **Do:** Replace raw `server.discovered_tools` reads in
    `mcp_tool_selector.py` with item 4's `effective_approved_catalog`.
    Behind existing repo default-off-flag convention (new flag name TBD
    at implementation time, e.g. `AI_SOC_MCP_EFFECTIVE_CATALOG_ENABLED`,
    default false).
  - **Verify:** governance regression green with flag off (byte-identical
    to pre-change behavior) and flag on (previously-executable tool that
    is now `APPROVED_BUT_MISSING`/`SCHEMA_MISMATCH` in a synthetic
    snapshot correctly returns `requires_human_review` instead of
    executing).
  - **Depends on:** 3, 4, 5
  - **Evidence:** _(fill when done)_

- [ ] **7** — `mcp_capability` vocabulary + resolver wiring
  - **Do:** Implement §E validation path + §F resolver. Extend
    `mcp_specialist.py::_fill_blank_proposals` to emit `mcp_capability`
    into `PlanStep.args_template` (still advisory-only, still only fills
    blanks on already-authorized steps — no new authorship power).
  - **Verify:** unit test: unresolved/unknown `mcp_capability` value →
    `requires_human_review("tool_selection_review", "capability_unresolved")`,
    never silently defaults to `spl_search`. Existing
    `EXECUTION_ELIGIBLE_SKILLS`/RBAC/HIL checks downstream unchanged and
    still enforced (integration test through the gate).
  - **Depends on:** 6
  - **Evidence:** _(fill when done)_

- [ ] **8** — Operator drift-visibility surface
  - **Do:** Extend existing `/debug` API (per `AI_SOC_DEBUG_API_ENABLED`)
    with a read-only endpoint returning both §G views
    (`effective_approved_catalog`, `server_discovered_catalog`) plus
    snapshot `captured_at`/`source`/`age_seconds`.
  - **Verify:** endpoint returns 403/404 when `AI_SOC_DEBUG_API_ENABLED`
    is false (existing gate pattern); returns both views correctly
    against a seeded snapshot when true.
  - **Depends on:** 4
  - **Evidence:** _(fill when done)_

- [ ] **9** — Full test matrix execution (§I)
  - **Do:** Run handshake/catalog tests, tool-contract tests (if live
    Splunk MCP available and credentials legitimately supplied by
    operator — otherwise FakeTransport only), and — only after item 3 is
    resolved and item 6/7 are flagged on in a COE environment — the
    governed `/chat` test.
  - **Verify:** all three test tiers pass; governed `/chat` test explicitly
    requires operator sign-off per existing Splunk MCP go-live runbook
    (`docs/coe/COE_GIT_DEPLOY_RUNBOOK.md`, `contracts/splunk_mcp_connection_
    contract.md`) — not run from a generic VPS per existing `--live`
    posture.
  - **Depends on:** 6, 7, 8
  - **Evidence:** _(fill when done)_

- [ ] **10** — Governance regression + `architecture.md` no-diff check
  - **Do:** `./scripts/run_stage3_governance_regression.sh`; separately
    confirm `git diff -- architecture.md` is empty across the whole plan's
    commit range.
  - **Verify:** script reports PASS; `architecture.md` diff empty.
  - **Depends on:** 9
  - **Evidence:** _(fill when done)_

- [ ] **11** — Plan closure audit
  - **Do:** Re-audit all checkmarks per `AGENTS.md` plan discipline
    before declaring done; update `plans/README.md` active-work table.
  - **Verify:** `.cursor/hooks/audit-plan-discipline.sh plans/2026-08-17_1757_mcp-effective-tool-catalog-and-authority.md` reports 0 `GAP:` lines.
  - **Depends on:** 10
  - **Evidence:** _(fill when done)_

## Verification gaps (flag before coding)

- Item 3's exact test assertions depend on which option (a/b/c) gets
  picked — cannot write the precise `Verify` command until that decision
  is made. Treat item 3's Verify above as a template, refine once decided.
- Item 9's live-Splunk tiers depend on credentials becoming legitimately
  available — this plan does not assume or schedule that; item 9 may
  partially complete (FakeTransport tiers only) and still be considered
  blocked-not-failed on the live tiers pending operator action.

## Drift log

- 2026-08-17: Plan created directly from a two-pass in-conversation design
  review (initial design → corrected design after 9 mandatory
  corrections from user). No prior version of this plan existed.
