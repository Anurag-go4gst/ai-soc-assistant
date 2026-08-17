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
remain blocked until this authority layer existed — it now does.

## ENFORCEMENT CORRECTION — 2026-08-17 (PR #144 review question #2, same branch)

**Question:** does the live `/chat` MCP execution path actually enforce the
effective approved tool catalog, or was the PERSISTENCE DECISION section
below built on top of an unenforced mechanism?

**Answer, before this correction: NO.** The prior report's own honest
finding — "not yet consulted by the live `/chat` path" — was accurate, and
that made the earlier `CODE_SIDE_MCP_CATALOG_READY=YES` claim wrong for
the specific claim "the catalog is an execution prerequisite." It was
observability-only. This is now fixed.

**Fix:** `mcp_execution_gate.py::evaluate_mcp_execution` now computes
`effective_catalog` unconditionally on every call (new helper
`_effective_catalog_for_target_server`, mirrors `_select_server`'s own
target-server resolution) and passes it into `select_mcp_tool` — the same
optional parameter added two rounds ago, now actually wired to the real
`/chat` entry point instead of only reachable by a caller that opts in.
No new flag: the parameter's presence on every call *is* the enforcement,
not a toggle.

**Bug found and fixed during wiring:** `compare_schema()` keyed
`LOCAL_TOOL_CONTRACTS` by exact tool name, so an allowlist entry using the
alias `run_splunk_query` (a real, already-supported alias of
`splunk_run_query` per `RUN_QUERY_ALIASES`) would always resolve
`SCHEMA_UNKNOWN` regardless of a valid server-reported schema — an
alias-configured deployment would be permanently blocked in live registry
mode. Fixed by normalizing through the existing
`mcp_rbac.py::canonical_mcp_tool_name()` before the contract lookup.

**Test breakage and fix:** wiring real enforcement broke 6 pre-existing
tests across `test_mcp_execution_gate.py`, `test_hil_mock_execution_
hardening.py`, `test_splunk_mcp_coe_qualification.py`, `test_splunk_mcp_
transport.py`, `test_coe_single_live_switch.py` (×2), and `test_catalogue_
auto_execute_gate.py` — all because they exercised registry-mode execution
paths without ever having discovery run, which the new invariant
correctly now blocks earlier than before. Each was fixed by seeding a
valid `DiscoverySnapshot` for the tool under test (proving the *original*
test intent — e.g. "registry mode without credentials fails closed on
config" — still holds *downstream* of the new catalog check, not that the
catalog check should be weakened). Also added an autouse `conftest.py`
fixture clearing the process-wide discovery-snapshot store before/after
every test, matching this repo's existing pattern for other global-state
singletons (`canonical_execution_idempotency`, `resource_plan_authority`,
etc.) — without it, one test seeding a snapshot would leak into unrelated
later tests.

**Production-path test matrix (mission's 12-item list, all via the real
`evaluate_mcp_execution` entry point with a connector that raises if
`call_tool` is ever reached):** all 12 pass —
`test_mcp_effective_catalog_production_enforcement.py`. Confirms: no
snapshot blocks before connector call; a verified tool reaches and passes
the real AUTH0 gate; a simulated restart (put-then-clear) re-blocks a
previously-executable tool; `APPROVED_BUT_MISSING`/`SCHEMA_MISMATCH`/
`SCHEMA_UNKNOWN`/`DISCOVERY_STALE` all block; a server-only tool is never
selectable at all (fails at `requested_tool_not_found`, before the catalog
check even runs, because it was never locally approved); the fallback
mechanism (still no live automatic-retry trigger exists anywhere in
`gate.py` — same as before, unchanged scope) only ever proposes
catalog-verified tools and always builds a distinct new AUTH0 grant;
`MCP_GLOBAL_EXECUTION_ENABLED=true` alone does not bypass the catalog
check; passing the catalog check does not bypass RBAC or the mandatory
per-call HIL confirmation.

**What remains honestly true and unchanged:** `mcp_capability` is still
never populated by `pipeline.py` (still hardcodes `execution_intent=
"spl_search"`) — `CAPABILITY_RESOLVER_ENFORCED_IN_CHAT=no` is accurate;
the *capability* vocabulary is wired and enforced whenever supplied, but
nothing in production supplies it yet. That is a materially smaller,
separate gap than "the catalog is unenforced" (which is now closed) — a
mis-selected capability signal is still caught by the exact same
catalog/AUTH0/RBAC/HIL chain; a config-only catalog was the actual
security-relevant gap, and that one is fixed.

## PERSISTENCE DECISION — 2026-08-17 (PR #144 review question, same branch)

**Question:** is in-memory discovery snapshot storage an intentional
production-safe final design, or an unfinished code-side requirement
mis-classified as `BLOCKED_LIVE_CONTRACT`?

**Trace result (critical finding):** `effective_catalog`/
`compute_effective_catalog` is **not consulted anywhere in the live
`/chat` → `evaluate_mcp_execution` → `select_mcp_tool` call path** — grep
confirmed zero references in `pipeline.py`/`mcp_execution_gate.py` outside
the pre-existing, unrelated `effective_catalogue_match_path` (use-case
catalogue, a different concept). This was already documented as
deliberate scope (item 6/7 evidence: "pipeline.py wiring is a separate,
governance-reviewed activation decision"), but it changes this decision:
**the in-memory-vs-Postgres question currently has zero live-authorization
consequence**, because nothing reads discovery state to gate a real
execution decision yet. Whichever storage is chosen only affects the
`/debug/mcp/catalog` observability surface and (new, this round)
`/debug/readiness`'s `mcp_discovery` summary — not what analysts can
actually execute.

**Decision: OPTION A (intentionally ephemeral, process-memory) — confirmed
correct.** Checked against every stated acceptance criterion:
- restart loss intentional — yes, by design (module docstring)
- live execution fails closed after restart — **N/A today** (nothing
  gates on discovery state yet); the mechanism itself computes
  `DISCOVERY_UNVERIFIED → executable=false` correctly and will apply the
  instant it's wired (unchanged from item 6's original design)
- operator can see `DISCOVERY_UNVERIFIED` — yes, `/debug/mcp/catalog` +
  new `/debug/readiness.mcp_discovery[].mcp_discovery_verified`
- bounded refresh available — yes, `POST /debug/mcp/discovery/refresh`
- refresh operationally cheap — yes, one handshake call
- no automatic authorization — yes, snapshot never touches
  `TOOL_ALLOWLIST`
- runbook documents rediscovery after restart — **was missing, fixed this
  round** (`CLAUDE.md` § Splunk MCP go-live, step 5)

**§5 (persist-for-history-but-require-fresh-discovery-for-authority)
evaluated and rejected as unnecessary right now:** that pattern only
matters once persisted state could ever influence `executable=true`. Since
no live path reads discovery state at all yet, adding persistence today
would add a component with no consumer and no way to prove its restart
behavior (no live DB was reachable to test a writer against — same
constraint as the original round). Revisit if/when item 6/7's live wiring
is actually activated and drift-history-across-restarts becomes an
operationally real requirement.

**§6 saved-search lifecycle:** confirmed coherent — `saved_search_name_
allowed()` (local policy, persists in `.env`/catalogue map, unaffected by
this question) is fully independent of MCP server-side discovery state.
No server-discovered saved-search metadata is trusted anywhere (Splunk
knowledge-object discovery execution is not implemented — `splunk_get_
knowledge_objects` still hits `NotImplementedError`, per §19, untouched).

**§7 reclassification:**

> "Postgres-backed discovery snapshot writer (no live DB reachable)"

was previously listed as `BLOCKED_LIVE_CONTRACT`/`D. GENUINE_LIVE_ONLY_
REQUIREMENT` by implication. **Reclassified to `B.
OPTIONAL_OBSERVABILITY_ENHANCEMENT`** — not required by final design (the
in-memory model is the correct final design per the decision above), not
a code-side gap (nothing is unfinished — the observability surfaces that
exist are complete and tested), and not blocked on a live database at all
(a durable store could be built and tested against a real Postgres
whenever someone wants drift history across restarts — it was never
actually gated on a *live Splunk MCP server*, which is the actual
`LIVE_MCP_PROVEN` boundary this repo's "live-only" language is reserved
for).

**Code change made this round:** one small, additive readiness surface
(`build_debug_readiness()` → new `mcp_discovery` block: `mcp_configured`,
`mcp_discovery_verified`, `mcp_discovery_status`, `mcp_discovery_age_
seconds`, `mcp_global_execution_enabled` per server) plus one runbook
paragraph. Capability resolver, AUTH0, fallback rules, tool-selection
policy, and `architecture.md` all untouched — confirmed via `git diff`
scoped to this round's single commit.

## FOLLOW-UP CLOSURE — 2026-08-17 (same day, branch `feat/mcp-effective-tool-catalog`)

Items 1/2/4/5/6/7/8 above are now **implemented** (see each item's
updated Evidence). Base for this round: `origin/master @
af93fb373d48efc1d5e8dd36795bc62fb026d868` (== the `af93fb3` this plan was
already anchored to; no drift between rounds). Local commit `2a9d105`
(item 3) preserved by branching `feat/mcp-effective-tool-catalog` off
local `master` before any further work, per instruction not to touch
`master` directly or create a second worktree.

Discovery tools remain non-executable in practice
(`NotImplementedError` for 4 tools, `tool_not_allowlisted` for
`splunk_get_user_info`/`splunk_get_info` at the connector layer) — this
round did not touch or "fix" that either (§19 metadata tool implementation
boundary, verified untouched). The effective-catalog/capability/resolver
mechanism is built and tested but not wired into the live `pipeline.py`
call path — that activation is a separate, governance-reviewed decision
(items 6/7 evidence explains why).

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

- [x] **0** — Confirm no drift since last audit — **DONE**
  - **Do:** Re-verified before building phases 4+: traced all 3
    `connector.call_tool()` sites in `mcp_execution_gate.py`, confirmed
    each preceded by a grant construction + `grants_match()` check.
  - **Verify:** manual trace (see commit `3279ea2` parent context / this
    session's "Phase 1 — Re-verify AUTH0 closure" step).
  - **Depends on:** none
  - **Evidence:** No drift found. `af93fb3..2a9d105` diff already reviewed
    in the prior session. Base for this round of work confirmed as
    `origin/master @ af93fb373d48efc1d5e8dd36795bc62fb026d868`.

- [x] **1** — Add discovery snapshot storage — **DONE, WITH A RECORDED DEVIATION**
  - **Do:** Implemented `InMemoryDiscoverySnapshotStore` in
    `backend/app/connectors/mcp/discovery_snapshot.py` (process-runtime
    cache, thread-safe, explicit-refresh-only) instead of a Postgres/
    SQLAlchemy table. Schema for a future durable store is reserved at
    `backend/app/db/migrations/0007_mcp_discovery_snapshot.sql`
    (idempotent DDL, matches the existing `ai_trace_runs` asyncpg pattern)
    but the writer/reader against it is **not implemented**.
  - **Verify:** `pytest app/tests/test_mcp_discovery_snapshot.py -q` — 9 passed.
  - **Depends on:** 0
  - **Evidence:** Deviation reason: this session had no reachable live
    Postgres to prove an asyncpg write path against (the repo's DB runs
    inside Docker on a hostname only reachable from other containers, not
    from this host process), and an unproven DB writer must not be
    claimed done per this mission's own rule ("Do NOT invent live Splunk
    results" — the same principle applies to inventing an untested DB
    path). The in-memory store satisfies "deterministic current-snapshot
    retrieval," "no tokens," "operator can see timestamp/source/
    staleness," and "explicit refresh only" in full. Cross-restart
    durability is the one property deferred — commit `8c478d1`.

- [x] **2** — Discovery refresh action — **DONE, IMPLEMENTED DIFFERENTLY THAN PLANNED**
  - **Do:** Implemented as `POST /debug/mcp/discovery/refresh` (existing
    debug-API auth gate reused) instead of a standalone CLI script. A
    standalone script would populate its own separate process's in-memory
    store, not the running backend's — a same-process API action is the
    only way an in-memory store design can actually affect live
    selection, so this is a correction, not a shortcut. Calls the real
    `SplunkMcpConnector().handshake_initialize_and_list_tools()`; an
    unconfigured/unreachable server yields an honest `status="failed"`
    snapshot, never fabricated, never a silent Mock substitution.
  - **Verify:** `pytest app/tests/test_mcp_debug_catalog_api.py -q` — 6 passed.
  - **Depends on:** 1
  - **Evidence:** Commit `d471cb6`. If/when the Postgres-backed store from
    item 1 is built, this endpoint's `get_discovery_snapshot_store().put()`
    call is the only line that changes.

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

- [x] **4** — Effective-catalog derivation function — **DONE**
  - **Do:** Implemented as a new pure-function module
    `backend/app/connectors/mcp/effective_catalog.py`
    (`compute_effective_catalog`) rather than modifying `registry.py`
    in place — kept `McpServerStatus.discovered_tools` semantics
    completely unchanged (avoids destabilizing the large existing test
    surface that depends on it meaning "config allowlist"); this new
    module is additive and is what `select_mcp_tool` optionally consumes
    (item 6). Dark-launch: nothing calls it from the live pipeline yet.
  - **Verify:** `pytest app/tests/test_mcp_effective_catalog.py -q` — 17 passed, covering all 9 drift statuses.
  - **Depends on:** 1
  - **Evidence:** Commit `53d6584`. `mode != "registry"` path proven
    unchanged via `test_no_mock_fallback_mode_gates_correctly` plus the
    full existing `test_mcp_registry.py`/`test_mcp_execution_gate.py`
    suites passing untouched (27 tests).

- [x] **5** — Schema-compatibility comparator — **DONE**
  - **Do:** `compare_schema()` in `effective_catalog.py`. Real required-
    param contracts only for `splunk_run_query` and
    `splunk_run_saved_search` (the only two tools with an implemented
    argument-passing execution path) — the other 6 tools are explicit
    `no_required_params=True` per the no-invented-arguments rule (§19),
    so schema comparison is a deliberate no-op for them until they gain
    real implementations.
  - **Verify:** `pytest app/tests/test_mcp_effective_catalog.py -k schema -q` — all SCHEMA 9-14 matrix items covered, passed.
  - **Depends on:** 4
  - **Evidence:** Commit `53d6584`. `SCHEMA_UNKNOWN` → `executable=False`
    for live registry mode implemented as instructed (no carve-out used
    beyond the explicit `no_required_params` policy).

- [x] **6** — Wire `select_mcp_tool` to read effective catalog — **DONE, NO FLAG NEEDED**
  - **Do:** Added optional `effective_catalog: EffectiveCatalogResult | None`
    parameter to `select_mcp_tool`. When `None` (every existing caller
    today), behavior is byte-identical to before — no flag required
    because the parameter's absence *is* the off state, not a separate
    flag gating a code branch. When supplied, both the capability-
    resolved and default-eligible paths additionally require
    `executable=True` in the verified catalog.
  - **Verify:** `pytest app/tests/test_mcp_capability_resolver.py app/tests/test_mcp_tool_selector* -q` plus scoped regression `pytest app/tests -q -k "mcp or splunk or saved_search or execution_gate or auth0 or call_grant"` — 554 passed after this change, 0 regressions vs. the 507 baseline before it.
  - **Depends on:** 3, 4, 5
  - **Evidence:** Commit `5d427e5`. Live pipeline wiring (having
    `pipeline.py` actually construct and pass an `effective_catalog`) is
    explicitly **not** included — that is a production-activation
    decision (needs a real discovery snapshot to exist in the running
    process first) outside this closure's scope, not a P0/P1 gap: the
    mechanism is additive, tested, and inert until a caller opts in.
    **SUPERSEDED 2026-08-17 (see § ENFORCEMENT CORRECTION above):** the
    gate itself (`evaluate_mcp_execution`, the actual `/chat` entry
    point — not `pipeline.py` directly) now always constructs and passes
    `effective_catalog`. The distinction that mattered was gate-level
    wiring, not `pipeline.py`-level; `pipeline.py` never needed to know
    about the catalog at all. `mcp_capability` (item 7) remains genuinely
    unsupplied by `pipeline.py` — that part of this evidence still holds.

- [x] **7** — `mcp_capability` vocabulary + resolver wiring — **DONE, WITH A RECORDED DEVIATION**
  - **Do:** New module `backend/app/connectors/mcp/mcp_capability.py`
    (8-value closed vocabulary, `validate_capability`,
    `resolve_capability_tool_name`, 1:1 `CAPABILITY_TO_TOOL` map) wired
    into `select_mcp_tool` (unknown capability → `requires_human_review`
    reason `capability_unresolved`, never silently defaults). **Did not**
    extend `mcp_specialist.py::_fill_blank_proposals` to emit
    `mcp_capability` — that module already proposes the coarser
    `execution_intent` guess today, and wiring a second, finer capability
    signal through the same advisory seam without a governed decision on
    how the two coexist risked exceeding "fills blanks only, no new
    authorship power." The resolver mechanism is complete and tested
    independent of who calls it.
  - **Verify:** `pytest app/tests/test_mcp_capability_resolver.py -q` — 10 passed, covering SELECTION 15-23.
  - **Depends on:** 6
  - **Evidence:** Commit `5d427e5`.

- [x] **8** — Operator drift-visibility surface — **DONE**
  - **Do:** `GET /debug/mcp/catalog` + `POST /debug/mcp/discovery/refresh`
    in `routes_debug.py`, reusing the existing `_require_debug_api_access`
    gate. No new auth surface.
  - **Verify:** `pytest app/tests/test_mcp_debug_catalog_api.py -q` — 6 passed (404 when disabled, 403 without `debug_access`, safe no-secrets payload, honest failed-not-fabricated refresh).
  - **Depends on:** 4
  - **Evidence:** Commit `d471cb6`.

- [~] **9** — Full test matrix execution (§I) — **PARTIAL: unit/contract tiers DONE, live tier BLOCKED_LIVE_CONTRACT**
  - **Do:** Handshake/catalog + tool-contract tiers run via `FakeTransport`
    and synthetic snapshots throughout phases 2-8's test files (110 new
    tests across 7 files this round, all passing). The governed `/chat`
    tier requires a real Splunk MCP server and operator sign-off per the
    existing go-live runbook — **not run**, consistent with this
    session's live-proof boundary (no credentials, no live server
    reachable).
  - **Verify:** `pytest app/tests/test_mcp_tool_descriptor_parsing.py app/tests/test_mcp_discovery_snapshot.py app/tests/test_mcp_effective_catalog.py app/tests/test_mcp_capability_resolver.py app/tests/test_mcp_fallback_and_security_invariants.py app/tests/test_mcp_debug_catalog_api.py app/tests/test_mcp_authority_gap_closure.py app/tests/test_splunk_call_authorization.py -q` — 165 passed.
  - **Depends on:** 6, 7, 8
  - **Evidence:** BLOCKED_LIVE_CONTRACT: governed `/chat` end-to-end tier.
    Everything else DONE.

- [~] **10** — Governance regression + `architecture.md` no-diff check — **PARTIAL**
  - **Do:** `architecture.md` no-diff check DONE (`git diff af93fb3..HEAD -- architecture.md` empty, and `config.py` diff also empty — zero new flags across the whole branch). Full
    `./scripts/run_stage3_governance_regression.sh` exceeded this
    session's tool timeout again (same as the prior AUTH0-closure round)
    — not run to completion.
  - **Verify:** `git diff af93fb373d48efc1d5e8dd36795bc62fb026d868..HEAD --stat -- architecture.md backend/app/config.py` both empty. Scoped MCP regression (566-593 passed across phases, see individual phase evidence above) stands in as this round's completion evidence. A 4-test pre-existing failure cluster (`test_canonical_clarification_contract.py`, `test_final_route_precedes_resource_plan.py`, `test_final_rqc_precedes_planning.py`) was independently reproduced against the clean `af93fb3` baseline via `git archive` (not a new worktree) — confirmed unrelated to this branch, not hidden, not fixed (out of scope).
  - **Depends on:** 9
  - **Evidence:** DEFERRED_LIVE_PROOF: full unbounded governance script run.
    Recommend running it in an environment without this session's
    per-command timeout before merge.

- [x] **11** — Plan closure audit — **DONE (this update)**
  - **Do:** All items above updated with Do/Verify/Depends on/Evidence
    and a DONE/PARTIAL/BLOCKED_LIVE_CONTRACT/DEFERRED_LIVE_PROOF status.
  - **Verify:** manual re-read of every item above; no item marked DONE
    that has a genuine live-proof gap (those are marked BLOCKED_LIVE_
    CONTRACT or DEFERRED_LIVE_PROOF instead, per this mission's explicit
    instruction not to mark code defects or unavailable live contracts as
    implemented).
  - **Depends on:** 10
  - **Evidence:** Plan status header should move from `active` to
    `active` (not `done`) — item 9's live `/chat` tier and item 10's full
    governance script remain genuinely open, by design, until a real COE
    environment runs them.

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
