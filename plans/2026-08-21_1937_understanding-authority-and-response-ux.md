---
name: understanding-authority-and-response-ux
overview: "Implement frozen architecture.md complete-or-abstain understanding authority, Final-RQC product applicability, provenance, and SOC response/UI workspace corrections."
status: active
date: 2026-08-21
canonical_plan: plans/2026-08-21_1937_understanding-authority-and-response-ux.md
loop_runner: plans/LOOP_RUNNER_understanding-authority-and-response-ux.md
architecture_freeze_commit: 49c5a4945ae4ff2a319a43980110f220076c1489
base_merge_commit: 49e545d9b7993dc185519a21b18e2ec26ecce40b
feature_branch: feat/complete-or-abstain-t4-ux
---

# Understanding authority + response / UI UX

## Objective

Bring production `/chat` into conformance with the frozen `architecture.md` (commit `49c5a494`) understanding model:

```text
T1–T3 COMPLETE + CONFIDENT → ACCEPT complete contract → skip T4
  OR
T1–T3 ABSTAIN → T4 semantic proposal → DET validation → Final RQC
```

Then ensure Final RQC (not T4 usage, MCP availability, or missing evidence) selects the product lifecycle, and that the analyst UI presents one coherent SOC workspace answer (no duplicate remediation CTAs, no investigation conclusion on pure SPL authoring, readable prose + wide structured content).

**Done** means: all checklist items checked with evidence; architecture.md unchanged from freeze SHA; focused + required regression gates green; Mac UI acceptance recorded for the firewall SPL authoring scenario without InvestigationOutcome / workflow-control (`BLOCKED` status, `BLOCK` next-action) / remediation pollution.

## Architecture authority (frozen — do not edit)

Read-only source: `architecture.md` @ `49c5a494`.

Invariants this plan must not weaken:

- T1–T3 complete-or-abstain (no partial semantic contract + field-level T4 fill)
- Explicit user literals remain binding DET constraints after abstain; T4 must not contradict; DET must reject
- Derived observations are non-authoritative hints only
- T4 is meaning-only (no route / ResourcePlan / CapabilitySnapshot / MCP / RBAC / HIL / remediation authority)
- One Final RQC; owner/capabilities/evidence/route hints DET-derived after validation
- InvestigationOutcome only for investigation-shaped Final RQCs
- Workflow control status/action must never present as a security containment action; containment language may originate only from a governed remediation/action contract
- Future T3 embeddings = candidate retrieval/ranking only (not implemented here)
- candidate_spl non-executable; normalized_spl + exact-call; one RP hub; PlanDelta bounds; remediation separation; no raw CoT

Related but **separate** plan (do not overwrite or merge):
[`plans/2026-08-21_0034_agentic-investigation-production.md`](2026-08-21_0034_agentic-investigation-production.md) — investigation envelope / PlanDelta product track.

## Current completed state (do not re-execute)

```text
P0 DONE  baseline/governance; Mac host venv authoritative for git-aware/full
         regression; container valid for ordinary focused backend tests;
         RACES baseline advanced only to 3a5f5001; macOS GitHub-skill clone-root
         = known platform limitation; Linux governance step 1 required later
         against exact candidate SHA. Commit 8ef0b9ed (evidence) + 5cf66404
         (RACES baseline).
P1 DONE  c742dfdb  T1–T3 complete-or-abstain gate exists; future embedding
         candidates share the same candidate interface; embeddings NOT implemented.
P2 DONE  5d1e487e  ACCEPT skips T4; ABSTAIN → T4 → DET → one Final RQC;
         complete deterministic requests survive T4-down; genuine ABSTAIN +
         T4 unavailable/timeout/invalid fail-closed; old unresolved-field
         response_format authority removed from live path; explicit-user
         constraints flow through production. Literal matrix:
           entity/IP/domain/hash, time          DET_REJECTION
           index, sourcetype, requested output,
           do_not_execute, explicit prohibitions PROTECTED_BY_CONSTRUCTION
         Protected files touched: NONE. architecture.md unchanged.
         Full suite: 20 failed / 6097 passed — postgres env, migration-readiness
         env, macOS GitHub skill factory. No unexplained P2 regression.
HEAD     5d1e487e5f96fd4a9e25f902b477acfb14e90233
branch   feat/complete-or-abstain-t4-ux
origin/master  49e545d9  (ancestor of HEAD; no Git divergence to reconcile)
```

Remaining execution is **exactly** `P3 → P4 → P5 → P6 → P7 → P8`. Do not create extra phases. P6 already contains UUID / viewport / hierarchy / responsive (P6A–P6D) as sub-scope of one phase — do not re-add them. Control-vocabulary leak (`BLOCK`/`BLOCKED` ≠ containment) lives in **P5**, not a separate P6.1.

## Git / promotion (Mac feature branch is current development authority)

Do **not** independently modify VPS or COE source. Do **not** push, merge, rebase, or alter `origin/master` during P3–P8.

P8 produces `FINAL_CANDIDATE_SHA` and **STOPS**. It does not push, merge, or deploy.

External promotion (after this plan, operator-driven — not this loop):

```text
Mac FINAL_CANDIDATE_SHA
  → VPS checkout exact candidate SHA
  → Linux governance + deterministic validation (LLM/MCP not required)
  → PASS
  → push feature branch
  → PR
  → merge master
  → MASTER_RELEASE_SHA
  → Mac / VPS / COE converge on that exact SHA
  → COE live LLM/MCP acceptance
```

## Config drift (record only — do not fix in this plan)

```text
Actual local .env:     AI_SOC_ENV_PROFILE=coe
Some docs claimed:     development   (CLAUDE.md stale; do not edit here)
Effective T4 timeout:  .env AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=10
                       coe profile does not set the timeout (operator .env required)
                       development.env.example still seeds 120
                       P2 Do historically cited 120 / development — that is not
                       this host's effective runtime. Use measured values in P7/P8.
```

Use effective runtime values during verification. Do not alter unrelated CLAUDE.md / config documentation in this workstream.

## Mac / environment posture (implementation + acceptance)

```text
ENVIRONMENT=MAC
LLM: available when office network path reaches endpoints; otherwise honest degrade
Splunk MCP: not configured / unavailable → capability unavailable / fail-closed execution
Missing MCP must NOT disable architecture or invent investigation BLOCKED for SPL authoring
```

### Test toolchain on this Mac (measured 2026-08-21 — read before writing any Verify)

This plan is **MAC-FIRST**: final acceptance must not depend on VPS or COE. Two runners exist,
both established and measured 2026-08-21.

**1. Host venv — RESOLVED, and the governance runner.** The bare interpreter (`python3`, 3.12.8)
has no pytest, which is why rev 2 first declared governance unrunnable here. A local gitignored
venv fixes it with **no application/runtime architecture change**:

```bash
python3 -m venv .venv
.venv/bin/pip install "fastapi" "uvicorn[standard]" "pydantic" "pydantic-settings" \
  "python-dotenv" "httpx" "sqlalchemy" "asyncpg" "langgraph>=0.2.60" "pytest" \
  "mitreattack-python>=6.0.0"
```

`.venv/` is already in `.gitignore` (line 6), so this is not a repo change. Run governance with
the venv first on PATH so the script's own `python3` calls resolve to it:

```bash
PATH="$PWD/.venv/bin:$PATH" ./scripts/run_stage3_governance_regression.sh
```

**Do not `pip install -e backend`** — it fails on setuptools flat-layout discovery because
`backend/` holds three top-level dirs (`app`, tracked `data`, and `env_profiles`, the latter an
untracked artifact Docker creates via the `./env:/app/env_profiles` mount). The editable install
is unnecessary: `backend/pyproject.toml` already sets `pythonpath = ["."]` and
`testpaths = ["app/tests"]`. **Do not "fix" `pyproject.toml` to make the install work** — that is
a runtime/packaging change this plan prohibits, and the Docker build depends on current behaviour.

**2. Backend container — for application tests.** Mounts `./backend:/app` read-write, so host
edits are the code under test (verified: host and container mtimes match).

```bash
docker compose exec -T backend python -m pytest app/tests/<file>.py -q
```

Equivalence measured on the two P1 suites: **77 passed** on both runners. Note the container
mounts the repo root at `/workspace` **read-only** while the governance script sets
`REPO_ROOT=/workspace` and runs `cd backend && pytest` there — so governance runs on the **host
venv only**, never in the container.

`rg` is available on the host but **not** in the container — keep `rg` steps host-side.

**Remaining governance prerequisite — CLONING WILL NOT FIX THIS ON macOS (measured 2026-08-21).**
With the venv, `run_stage3_governance_regression.sh` executes but exits **1 at its first step**:

```text
GitHub skill clone root not found: /private/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
REGRESSION FAILED: github discovery index stale
```

**Do not clone in the hope of fixing step 1 — it is provably unsatisfiable on this host.** The
committed artifact embeds the generating machine's absolute path, and the staleness comparison does
not normalize it:

```text
docs/skills/github_skill_discovery_index.json
  clone_root_used = "/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills"   # generated on Linux
                    generated_at 2026-06-11, 754 skills, no upstream SHA recorded

resolve_clone_root() calls .resolve()  →  on macOS /tmp is a symlink to /private/tmp
                                       →  "/private/tmp/ai-soc-references/..."

_check_payload() normalizes ONLY generated_at            build_github_skill_discovery_index.py:173-176
  → clone_root_used compared verbatim: "/private/tmp/..." != "/tmp/..."  → always "stale"
```

So **any** clone path fails step 1 on macOS: the default `/tmp` path resolves to `/private/tmp`, and
any other path (e.g. an external test-deps dir) mismatches even more plainly. Scope check: only the
**discovery index** embeds a clone path — `github_skill_triage_scores.json` and
`proposed_use_cases_from_github.json` do not, so governance steps 2–3 and the rest of the runner are
unaffected and would pass with a valid clone.

**Is the clone needed for the product to work? No.** Runtime reads the **committed** JSON artifacts
via `backend/app/knowledge/mapping_exports.py:337-339`; it never reads the clone. The clone is a
**regeneration/staleness-gate dependency only**. A second, related reproducibility gap: no branch,
tag, or commit is pinned anywhere (`plans/AI_SOC_MASTER_PLAN.md:50` documents a plain default-branch
`git clone`), and no upstream SHA is recorded in the artifact — so even on Linux a fresh clone of a
moved upstream would report "stale" because *upstream* changed, not because our artifacts drifted.
Regenerating in that situation would rewrite 754 committed rows from an unpinned source.

**P0 disposition — RATIFIED 2026-08-21: `KNOWN_MACOS_GOVERNANCE_ENV_LIMITATION`.**
No clone is created for this Mac workstream. Prohibited while this plan runs: modifying the
governance script, regenerating the 754 committed rows, vendoring the external repo, faking
`clone_root_used`, or hiding/xfailing the failure. `AI_SOC_GITHUB_SKILL_CLONE_ROOT` is defined at
`scripts/github_skill_factory_lib.py:20`, defaulting to `/tmp/ai-soc-references/…`, and is set in
neither `.env` nor any profile — leave it that way.

```text
MAC:      governance step 1 = KNOWN_MACOS_GOVERNANCE_ENV_LIMITATION (does NOT block P1–P6)
RELEASE:  Linux governance step 1 = MANDATORY P8 GATE against the exact final candidate SHA
```

This limitation **does not block P1–P6 implementation**. Every governance step and check that is
valid on Mac still runs normally. It **does** remain a release gate: before P8 is declared
release-ready, run governance step 1 on Linux (VPS or COE) against the **exact same candidate Git
SHA** and record the result. That gate is repository/governance validation — it does **not**
require live LLM or MCP, so the VPS is acceptable even with both unavailable. COE live LLM/MCP
validation is a later deployment acceptance step, outside this loop.

Future governance maintenance (pin the external source SHA; stop treating a machine-specific
absolute `clone_root_used` as semantic artifact content, or normalize it deterministically) is
recorded in [`docs/operations/deferred_github_skill_factory_governance_maintenance.md`](../docs/operations/deferred_github_skill_factory_governance_maintenance.md)
and is **deferred — not implemented in this plan**.

Note the test `test_github_skill_expansion_factory_baseline.py::test_factory_generators_check_against_committed_artifacts`
(line 208) shells out to the same three `--check` scripts, so it fails for exactly this reason —
even though that file's *other* tests correctly use a synthetic `fixture_clone` fixture, matching
the library's own guidance that "tests must pass `--fixture-root` instead of requiring the real clone.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same Verify gate fails twice on one item, **or**
- Architecture interpretation ambiguous / would require editing `architecture.md`, **or**
- New authority decision required, **or**
- Implementation seems to need a second router, second T4 service, or T4 investigation runtime, **or**
- Security / HIL / RBAC / exact-call would be weakened, **or**
- Legitimate existing work would need deletion, **or**
- A **new** change to a RACES-protected freeze path is required (`pipeline.py` included). Previous RACES approval covered **only** commit `3a5f5001`. Any further freeze-path edit needs STOP + explicit operator decision, **or**
- P8 evidence is recorded — the loop **stops**; it does not push, merge, or deploy

## Dependency order

`P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8`

## Prohibited globally

- Modify `architecture.md`
- Special-case individual user questions (including firewall phrasing)
- Keyword patches / firewall-only rules
- Implement embeddings now
- Second router / second planner / second T4 / T4 investigation runtime
- Fake LLM or MCP availability
- Hide failing tests to continue
- Hide env failures (postgres, migration-readiness, macOS GitHub skill factory)
- Merge, push, rebase, or deploy unless the operator explicitly requests it after P8
- Independently modify VPS or COE source
- Create extra phases (no P6.1 / no second UUID or viewport item)

## Existing modules to reuse (audit-first)

| Concern | Prefer |
|---|---|
| T1 exact / near / semantic 105 | `query_understanding/parser.py`, `coverage/question_runtime_map.py`, `coverage/semantic_question_index.py` |
| T2/T3 catalogue | `use_cases/registry.py`, `catalogue/match_tiers.py`, `chat/lane_router.py` |
| Route floors | `routing/select_route_from_understanding.py`, `routing/skill_router.py` |
| Intent / RQC | `chat/intent_classifier.py`, `chat/resolved_query_builder.py`, `chat/contracts/resolved_query.py` |
| T4 | `chat/semantic_t4_understanding.py`, `chat/contracts/semantic_t4_proposal.py` |
| Canonical planning | `chat/canonical_planning_orchestrator.py` |
| Evidence plan / outcome | `chat/evidence_planner.py`, `evidence/evidence_sufficiency.py`, `chat/contracts/investigation_outcome.py`, `evidence/final_evidence_gate.py` |
| Remediation offer | `chat/remediation_runtime.py` (`maybe_attach_remediation_offer`, line 144) |
| Explicit user literals (P2) | **Candidates pending generality audit — not presumed authoritative:** `spl/request_authority.py` (`build_deterministic_request_contract` → `DeterministicRequestContract`; `check_template_semantic_fidelity` → `SemanticFidelityDecision`), `spl/user_constraint_bindings.py` (`build_user_constraint_bindings`). These live under `spl/`; P2 must audit whether the primitives are generic across all Final-RQC families before reuse. |
| Control-vocabulary leak (P5) | `chat/contracts/staged_sufficiency.py:18-19,35` (`SufficiencyStatus` / `SufficiencyNextAction` / `_EVIDENCE_NEXT_BY_STATUS`), `chat/contracts/investigation_outcome.py:52,163,312-318` (`recommended_next_action` / `_recommended_next_action`) |
| SPL fidelity | `spl/request_authority.py`, `chat/review_only_spl_renderer.py` |
| Provenance | `control_plane_trace`, `route_plan_shadow`, `investigation_lineage`, `provenance.semantic_t4` |
| UI composition | `ChatBubble.tsx`, `InvestigationOutcomeCard.tsx`, `RemediationPlanApprovalCard.tsx`, `AnalystResponseCard.tsx`, `ChatPanel.tsx` |

## Checklist

- [x] **P0** — Baseline + architecture freeze gate
  - **Do:** Record branch, base SHA `49e545d9`, architecture freeze SHA `49c5a494`, clean worktree (ignore local `.claude/` only), Mac profile/flags (**measured, not assumed** — `.env` sets `AI_SOC_ENV_PROFILE=coe`, **not** `development` as `CLAUDE.md` states; effective flags read from the running backend: ResourcePlan execution ON, dispatch-v2 OFF, live capability enforcement OFF, `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=true` — note the repo default for that flag is **false**), LLM/MCP posture, and pin `architecture.md` as read-only for this plan. **Establish and record the test runner** per *Test toolchain on this Mac* — the runner decision is **MAC-FIRST and already resolved: host venv for governance, container for application tests**; re-confirm both run, and do not relocate P7 to COE/VPS. **Resolve the one open governance prerequisite**: set `AI_SOC_GITHUB_SKILL_CLONE_ROOT` to an existing clone, or have the operator create one — governance exits 1 at step 1 without it. If neither is possible, record the concrete reason and **STOP for the runner decision** rather than silently moving P7 to COE. **Capture a green pre-change baseline** for the suites P1–P5 will touch, so P7 can honestly classify any failure as regression vs pre-existing. Confirm no equivalent active plan exists beyond this file. Do not change runtime code.
  - **Verify:** `git rev-parse HEAD`; `git status --short` shows only optional local tool noise; `git diff 49c5a494 -- architecture.md` is empty; `git show 49c5a494:architecture.md | rg -n 'COMPLETE|ABSTAIN|MUST reject|MUST NOT materially contradict|InvestigationOutcome applies|embedding / vector'` (host-side; `rg` is not in the container) returns all six anchors; `docker compose exec -T backend python -m pytest app/tests/test_t1_t4_authority_boundary.py app/tests/test_spl_query_fidelity.py app/tests/test_t4_contract_merge_authority.py -q` recorded as the baseline; `cd frontend && npm test` recorded as the baseline. `test ! -w` is not required — instead prove no `architecture.md` diff during later phases.
  - **Depends on:** none
  - **Evidence:** Closed 2026-08-21.
    ```text
    branch      feat/complete-or-abstain-t4-ux
    base        49e545d9   architecture freeze 49c5a494 (git diff -- architecture.md EMPTY)
    profile     AI_SOC_ENV_PROFILE=coe  (measured; CLAUDE.md's "development" is stale)
                t4_semantic_understanding=True  resource_plan_execution=True
                live_capability_enforcement=False  dispatch_v2=False
    runners     host venv .venv/ (Python 3.12.8, pytest 9.1.1) = AUTHORITATIVE for
                git-aware / freeze / governance / DB-aware; container = application tests.
                Equivalence: 77 passed on both for the P1 suites.
    LLM/MCP     Splunk MCP not configured -> capability unavailable / fail-closed.
    governance  step 1 = KNOWN_MACOS_GOVERNANCE_ENV_LIMITATION (ratified; not blocking P1-P6).
                Linux step-1 PASS vs exact final SHA = mandatory P8 release gate.
    RACES       baseline advanced 08c8b40c -> 3a5f500104fb7a9ba609fc70aeb4af5894cee2eb
                (pinned to that commit, not HEAD). Freeze test 8 passed. Commit 5cf66404.
    baseline    20 failed, 6043 passed, 7 skipped, 6 xfailed (439.59s)
                was 21f/6042p before the RACES advance: -1 failure, +1 pass, no new failures.
                14 integration/*postgres* + 5 test_migration_readiness.py  = DB env
                 1 test_github_skill_expansion_factory_baseline.py::
                   test_factory_generators_check_against_committed_artifacts = macOS clone_root limitation
    gates       git diff --check CLEAN; worktree clean except .claude/ local noise.
    ```
  - **Commit:** none (docs evidence in plan Evidence only) or `docs(plan): record P0 baseline` if an evidence file is added under `docs/evals/`

- [x] **P1** — T1–T3 complete-or-abstain acceptance gate
  - **Do:** AUDIT FIRST the live path `understand_query` → `match_use_cases` → `lane_for_match_path` → known vs guided. Implement a single DET acceptance gate: ACCEPT only when match is complete, confident, margin-sufficient, compatible, and fully governed; otherwise ABSTAIN with no partial semantic commit. Keep a clean T3 candidate interface so future lexical∪embedding candidates can share the gate. Do not implement embeddings. Do not special-case queries.
  - **Verify:** `docker compose exec -T backend python -m pytest app/tests/test_t1_t4_authority_boundary.py app/tests/test_spl_query_fidelity.py -q` (both files exist; measured green pre-change) plus NEW focused tests (create `app/tests/test_complete_or_abstain_understanding.py`) covering: exact 105 ACCEPT+T4 skipped; strong catalogue paraphrase ACCEPT; single generic source token cannot bind rich detection; unclear objective ABSTAIN; unknown SOC ask ABSTAIN.
  - **Depends on:** P0
  - **Evidence:** Closed 2026-08-21.
    ```text
    AUDIT (live path, before coding):
      understand_query          query_understanding/parser.py:86
      match_use_cases           use_cases/registry.py:119
      lane_for_match_path       chat/lane_router.py:48  (T1/T2/T3 governed; else T4)
      known-vs-guided           processing_lane_for_initial_tier -> known | guided
      UNDERSTANDING sufficiency chat/contracts/staged_sufficiency.py:227 from_understanding_state
                                sole caller chat/resolved_query_builder.py:382
      T4 gate                   semantic_t4_understanding.py:247 _permits_t4_call
                                  == (understanding_sufficiency.next_action == "CALL_T4")
      derive_next_action        staged_sufficiency.py:83-90 -> CALL_T4 when
                                  stage=UNDERSTANDING and status in {PARTIAL,INSUFFICIENT}
                                  and unresolved non-empty
    FINDING: the live model is exactly the forbidden one — status PARTIAL plus an
      unresolved-field list handed to T4 as a patch set (_schema_limited_to_unresolved,
      _prompt_locked_fields, prompt "Return only fields offered in
      unresolved_fields_to_resolve", _merge_proposal). Architecture §2.2 requires
      complete-or-abstain instead. Rewiring that seam is P2; P1 lands the gate it needs.

    BUILT: backend/app/chat/complete_or_abstain_gate.py
      evaluate_complete_or_abstain(...) -> UnderstandingAcceptance
      binary ACCEPT | ABSTAIN; t4_permitted == is_abstain; ABSTAIN commits nothing
      abstain triggers: not_governed_tier, not_fully_governed, policy_blocked,
        clarification_required, completeness_incomplete, missing_required_fields,
        unresolved_semantic_fields, semantic_incompatibility, no_candidate,
        low_confidence, low_margin  (all applicable reasons collected, not short-circuited)
      thresholds reuse the deterministic routing floor 0.70 + 0.10 margin (no new number)
      MatchCandidate.source = lexical | embedding -> one shared T3 candidate interface;
        identical rules per source, so embeddings can never become an authority tier.
        Embeddings NOT implemented.

    SCOPE: purely additive — 2 new files, zero existing files modified, so no authority
      drift is possible. The gate is NOT yet authoritative on the live path; wiring it
      (and removing the partial handoff) is P2.
    NO query text is special-cased anywhere in the gate.

    VERIFY (host venv, authoritative):
      test_t1_t4_authority_boundary.py + test_spl_query_fidelity.py
        + test_complete_or_abstain_understanding.py ....... 101 passed
      new file alone .................................... 24 passed
      neighbours (shared_sufficiency, live_path_untouched_by_ec,
        keyword_router_authority_reachability) ........... 29 passed
      git diff --check .................................. CLEAN
    ```
  - **Commit:** one logical commit for P1 only

- [x] **P2** — T4 full semantic fallback + DET validation
  - **Do:** On ABSTAIN only, call T4 with original query, trusted schema/vocabulary, meaning-aid capability descriptions, few-shots, **EXPLICIT_USER_LITERAL_CONSTRAINTS**, and optional derived hints. **Reuse-first, but AUDIT GENERALITY FIRST — do not assume an SPL-domain contract is the architecture-wide literal authority.** Candidate existing machinery: `spl/request_authority.py::build_deterministic_request_contract` → `DeterministicRequestContract`, `check_template_semantic_fidelity` → `SemanticFidelityDecision` (material-contradiction rejection), and `spl/user_constraint_bindings.py::build_user_constraint_bindings`. These live under `spl/` and may well be SPL-domain-shaped. **Before adopting any of them, audit whether the primitives are sufficiently generic for every Final-RQC family:** SPL, investigation, knowledge, MITRE, comparison, remediation-related understanding, and other governed operations.

    ```text
    IF the explicit-literal extraction/binding primitives are already generic
        → reuse them directly
    ELSE (the contract is SPL-domain-specific)
        → extract the generic primitive into the existing appropriate shared authority seam
    ```

    Do **not**: create a second literal parser; duplicate entity/time extraction; force all semantic requests through an SPL-domain contract; or create another authority service. The invariant that must survive either branch: **explicit user literals = binding DET validation constraints; derived observations = non-authoritative hints.** Record the audit verdict (generic vs extract) in Evidence — it is a design decision, not an implementation detail. Remove partial locked intent/goal handoff from abstained T1–T3 — the current seam is `chat/canonical_planning_orchestrator.py:1030` calling `maybe_enrich_t4_semantic`, whose *enrich* shape is precisely the field-level patch the frozen architecture now forbids. DET validates schema + literals + prohibitions + query consistency; reject material literal contradictions (e.g. `10.0.0.8`/`2h`/`do_not_execute` cannot become `10.0.0.5`/`24h`/execute). After accept, DET derives Final RQC, owner, capabilities, evidence needs, route hints.
    **Field-authority clarification (resolves an ambiguity in rev 1):** `SemanticT4Proposal` today already carries `intent_family`, `answer_goal`, `required_capabilities`, `prohibited_capabilities`. Frozen `architecture.md` (§11, "Derived fields such as: required capabilities / evidence requirements / route hints ... are recomputed deterministically from the validated understanding") means DET **must recompute and never consume these as authority** — it does **not** mean deleting the fields from the proposal contract. Do not remove them; make them non-authoritative.
    **REQUIRED negative — T4 unavailable / failure (fail closed at semantic authority).** Mac and VPS LLM availability legitimately varies, so this is a first-class path, not an edge case. On `T1–T3 = ABSTAIN` **and** T4 unavailable / timeout / invalid or unparseable structured response, all of the following must hold:

    ```text
    no partial T1–T3 semantic contract becomes authoritative
    no prior intent/goal locks are resurrected
    no guessed / invented Final RQC
    no old deterministic classifier silently becomes the semantic fallback
    no accidental investigation lifecycle merely because T4 failed
    ```

    The system must fail closed at semantic authority — **clarify**, or return an **honest degraded inability to resolve**, per existing architecture/contracts. Note the timeout surface is real: `AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS=120` in the `development` profile this host runs.
  - **Verify:** NEW tests in `app/tests/test_t4_complete_or_abstain_validation.py` (or extend `test_t4_contract_merge_authority.py` only if still the owning seam after audit): T4 skipped on ACCEPT; T4 invoked on ABSTAIN; literal contradiction rejected; derived hints non-binding; a T4 proposal carrying `required_capabilities`/`intent_family` does not change the DET-recomputed Final RQC values; no `primary_skill`/ResourcePlan/MCP grant from T4 proposal. **Plus the required T4-failure negative, as three distinct cases — unavailable, timeout, invalid structured response** — each asserting every one of the five "must hold" clauses above, and asserting the turn ends in clarification or honest degrade (never a fabricated Final RQC and never an investigation lifecycle). Run via `../.venv/bin/python -m pytest app/tests/test_t4_complete_or_abstain_validation.py app/tests/test_t4_contract_merge_authority.py -q` (or the container form). Run `/invariant-check` on the diff.
  - **Depends on:** P1
  - **Evidence:** Closed 2026-08-22 — see IMPLEMENTATION below. **Generality audit (2026-08-21) verdict:**
    ```text
    AUDITED: spl/request_authority.py::DeterministicRequestContract (fields, lines 31-44)

      GENERIC (family-agnostic, reusable as-is across SPL / investigation /
      knowledge / MITRE / comparison / remediation-understanding):
        entities: dict[str, tuple[str,...]]     explicit_predicates: dict[...]
        time_window: str | None                 requested_output_type: str
        execution_intent: str  (carries do_not_execute)   operation: str

      SPL-DOMAIN-SPECIFIC (must NOT be imposed on non-SPL families):
        index: tuple[str,...]        sourcetype: tuple[str,...]
        sufficient_for_spl_authoring: bool
        response_shape  (domain values such as "spl_only")

    VERDICT = EXTRACT, not reuse-directly.
      The extraction/binding *primitives* are generic, but the contract they sit in
      is SPL-shaped. Per the plan's rule, extract the generic explicit-literal core
      into the existing appropriate shared authority seam and have the SPL contract
      COMPOSE it. Do not force investigation/knowledge/MITRE/comparison/remediation
      understanding through an SPL-domain contract, and do not stand up a second
      literal parser, duplicate entity/time extraction, or a new authority service.
      SemanticFidelityDecision / SemanticElementDecision (lines 63-90) are already
      family-agnostic (dimension/value/status/reason) and are reusable as the
      material-contradiction verdict shape without change.

    ALSO AUDITED (the partial handoff P2 must remove):
      semantic_t4_understanding.py
        _schema_limited_to_unresolved (155)  _prompt_locked_fields (179)
        prompt text "Return only fields offered in unresolved_fields_to_resolve" (240)
        _merge_proposal (632)     _permits_t4_call (247)
      Together these implement field-level patching of a partially committed
      contract — the model architecture §2.2 forbids. P2 replaces it with:
      full-query T4 proposal on ABSTAIN only, then DET validation, then DET-derived
      Final RQC.

    FIELD-AUTHORITY NOTE (already recorded in Do): SemanticT4Proposal keeps
      intent_family / answer_goal / required_capabilities / prohibited_capabilities;
      DET must RECOMPUTE and never consume them as authority. Do not delete them.
    ```

    IMPLEMENTATION (2026-08-22), four internal checkpoints; RECOVERY (2026-08-25)
    closed the live ACCEPT/ABSTAIN gaps before commit:

    P2-A generic literal core -> NEW app/chat/contracts/explicit_user_constraints.py
      ExplicitUserConstraints{entities, predicates, data_scope, time_window,
        requested_output_type, execution_prohibited, prohibitions}
      build_explicit_user_constraints(...) reuses build_user_constraint_bindings —
        no second parser, no duplicated entity/time extraction.
      Production carriage: build_resolved_query_contract extracts once into
        provenance.explicit_user_constraints (authority path recorded).
      DeterministicRequestContract COMPOSES the core via explicit_constraints.

    P2-B abstain -> T4 input contract.  OLD PARTIAL AUTHORITY REMOVED FROM LIVE PATH: YES
      _permits_t4_call = P1 complete-or-abstain only (NOT bool(unresolved_fields)).
      ACCEPT arms: (1) catalogue T1–T3 complete_governed_match
                   (2) complete_deterministic_understanding (may be out_of_registry)
      attach_understanding_authority no longer invents semantic_goal for every T4 tier.
      Live response_format uses full _SEMANTIC_T4_SCHEMA (not unresolved-field subset).
      Prompt carries full query + EXPLICIT_USER_LITERAL_CONSTRAINTS + derived hints.

    P2-C DET validation + fail-closed on genuine ABSTAIN + T4 failure only.
      COMPLETE request + T4-down → ACCEPT → answer preserved (no fail-closed poison).
      Genuine ABSTAIN + T4 unavailable/timeout/invalid → clarification / degrade.

    P2-D Final RQC convergence + literal protection matrix:
      entity/time → DET_REJECTION (proposal can express; DET rejects)
      index/sourcetype/output_form/do_not_execute/prohibitions →
        PROTECTED_BY_CONSTRUCTION (not on SemanticT4Proposal; Final RQC derives)

    PROTECTED FILES TOUCHED: NONE. pipeline.py untouched; architecture.md unchanged.

    TESTS (host venv, recovery 2026-08-25):
      focused authority band (utility/winevent + complete-or-abstain + freeze +
        job-aware + merge): 119 passed
      prior-10 live /chat regressions: 0 failed (all green in-process and full suite)
      full suite: 20 failed, 6097 passed, 7 skipped, 6 xfailed (~558s)
        Categories vs P0: 14 postgres-integration env + 5 migration_readiness env
        + 1 macOS factory/governance — same shape as P0's 20.
        Exact names differ within the postgres bucket (retention/handoff/telemetry
        vs earlier asset_registry/debug) but ZERO new unexplained names and ZERO
        of the prior utility/winevent/T4 regressions.
      git diff --check: clean. architecture.md vs 49c5a494: unchanged.
      pipeline.py: untouched. PROTECTED FILES: none.
    ```
  - **Commit:** one logical commit for P2 only

- [x] **P3** — Final-RQC product applicability
  - **Do:** Final RQC determines product lifecycle — **not** T4 used, MCP unavailable, evidence unavailable, or a live-data signal alone. Generic invariant: **SPL authoring ≠ investigation.** A pure review-only SPL request must not become InvestigationOutcome `blocked` + disposition `inconclusive` + a remediation offer merely because MCP/evidence is unavailable. Investigation-shaped Final RQCs still follow the canonical investigation lifecycle. No firewall-specific patch.

    AUDIT FIRST the **four** seams below (rev 1 listed only the first three; the fourth is where the blocked status is actually decided):
    1. `chat/evidence_planner.py:480` — the `spl_generation_only` branch. Confirmed shape: unless `is_universal_utility_spl_authoring` matches (→ `answer_mode="spl_utility_authoring"`), it falls through to `answer_mode="live_investigation"` with `needs_spl=True`, `needs_mcp` descriptive and `mcp_allowed=mcp_authorised` (false when not catalogue-matched). This is the mislabel the plan targets.
    2. `chat/contracts/investigation_outcome.py:62` — `derive_investigation_outcome`.
    3. `chat/remediation_runtime.py:144` — `maybe_attach_remediation_offer`.
    4. **`evidence/final_evidence_gate.py`** — independently special-cases `spl_generation_only`: line 476 (`spl_generation_only` + `route_live_data_request` + zero collected evidence) and its presence in `_POLICY_SEVERITY_FAMILIES` (line 449) alongside `_NON_SEVERITY_INTENT_FAMILIES` (line 433). Fixing only `evidence_planner.py` will leave this path producing the same wrong posture.

    Make product lifecycle selection depend on Final RQC answer goal / investigation shape. Pure SPL authoring must use review-only SPL composition without InvestigationOutcome `blocked`/`BLOCKED`/remediation. Investigation-shaped RQCs still enter the common investigation lifecycle regardless of T1–T3 vs T4 understanding path.
  - **Verify:** NEW `app/tests/test_final_rqc_product_applicability.py` including generic coverage for SPL-authoring shaped RQC (no InvestigationOutcome investigation_status packaging / no remediation_offer_required by default) and investigation-shaped RQC still eligible for outcome; add at least one case entering through `final_evidence_gate` so seam 4 is pinned, not just seam 1. Reproduce the firewall SPL authoring *shape* via signals/fixtures without hardcoding that sentence as a special case. `docker compose exec -T backend python -m pytest app/tests/test_final_rqc_product_applicability.py -q`. `/invariant-check`.
  - **Depends on:** P2
  - **Evidence:**
    ```
    AUDIT: Root defect — `spl_generation_only` + `explicit_spl_authoring` + out-of-catalogue
    was mapped to `answer_mode=live_investigation`, then InvestigationOutcome V2 emitted
    `investigation_status=blocked`, `recommended_next_action=BLOCK`, and remediation offer
    when MCP/evidence absent. Surrogate signals (T4, live_data_request, zero evidence) were
    driving investigation packaging instead of Final RQC semantics.

    SEAM REUSED: `is_investigation_shaped_final_rqc()` in `chat/investigation_shaped.py`;
    added `investigation_outcome_applicable()` wrapper (no second router). Evidence planner
    maps known out-of-catalogue explicit SPL authoring → `spl_utility_authoring`; catalogue
    matched SPL rows keep `live_investigation`. Match path resolved via
    `_deterministic_match_path_from_inputs()` — unknown path preserves prior planner shape.

    CHANGES:
    - `spl_authoring_intent.py`: `is_explicit_review_only_spl_authoring()`
    - `evidence_planner.py`: out-of-catalogue explicit SPL → spl_utility_authoring
    - `final_evidence_gate.py`: spl_utility_authoring skips severity/HIL from live-data
    - `investigation_outcome.py`: legacy outcome when not investigation_outcome_applicable
    - `remediation_runtime.py`: skip offer when no investigation_status

    FIREWALL SHAPE PROBE: "create a spl command for checking the firewall activities in
    last 27 days" → answer_mode=spl_utility_authoring, outcome_applicable=False, no
    investigation_status / recommended_next_action.

    FOCUSED: `pytest app/tests/test_final_rqc_product_applicability.py -q` → 18 passed.
    NEIGHBOURS: evidence_planner, final_evidence_gate, investigation_outcome, t4 suites,
    pipeline_dispatch_phase2b, control_plane_golden, llm_plan_validator → PASS.
    FULL HOST VENV: 6113 passed, 20 failed (same 20 as P2: 14 postgres integration +
    5 migration_readiness + 1 macOS GitHub skill factory). Zero unexplained regressions.
    invariant-check: PASS (no pipeline.py, no new MCP/execution paths, no new flags).
    architecture.md vs 49c5a494: unchanged. pipeline.py: untouched. git diff --check: clean.
    ```
  - **Commit:** one logical commit for P3 only

- [ ] **P4** — Deterministic understanding provenance
  - **Do:** Expose deterministic provenance using **existing** trace structures. Show only the authority path, not chain-of-thought. Reuse `control_plane_trace`, `route_plan_shadow`, RQC `provenance`, and `investigation_lineage`. No new tracing framework unless audit proves reuse is impossible.

    Example (ABSTAIN → T4):

    ```text
    T1 exact       no match
    T2 catalogue   no accepted match
    T3 candidates  abstained
    T4 semantic    used
    Final intent   SPL authoring
    Final owner    spl_generation
    ```

    Example (ACCEPT):

    ```text
    T1–T3          accepted
    T4             skipped
    ```

    Surface under existing “How this answer was produced”.
  - **Verify:** Unit/contract test that provenance fields are present and deterministic for ACCEPT and ABSTAIN→T4 paths, run as `docker compose exec -T backend python -m pytest app/tests/<new_or_owning_file>.py -q`; frontend or lineage consumer test if a UI field is added. Host-side `rg` proves no new telemetry catalog event invented without closed-catalog registration (canonical planning telemetry is a **closed catalog** — `emit_planning_event()` rejects unregistered names, so an unregistered event fails rather than silently passing).
  - **Depends on:** P3
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P4 only

- [ ] **P5** — Response ownership + outcome/remediation semantics
  - **Do:** AUDIT FIRST current composition of `ChatBubble`, `InvestigationOutcomeCard`, `RemediationPlanApprovalCard`, and `AnalystResponseCard`. Final RQC / response profile owns composition. One backend turn must present **ONE** coherent primary answer. Remove fragmented stacking when sections are not applicable.

    Fix `ChatBubble` stacking so SPL authoring does not show InvestigationOutcomeCard + local remediation CTA + RemediationPlanApprovalCard + AnalystResponseCard together. Exactly **ONE** authoritative remediation CTA. Prefer backend-governed remediation interaction. Remove or demote the **local** OutcomeCard remediation Yes/Not-now so only backend-governed `RemediationPlanApprovalCard` is authoritative when remediation applies. Do not leave a cosmetic/local React CTA that appears authoritative. Confirmed target: `InvestigationOutcomeCard.tsx` line 17 holds purely local `useState<'yes' | 'not_now' | null>` driving the CTA block at lines 88–108 — local UI state with no backend authority, which is the duplication to remove. Note line 18 already short-circuits (`if (!outcome.investigation_status) return null`), so a correct P3 backend fix makes the card self-hide; P5 should rely on that rather than adding a frontend denylist. Investigation / knowledge / remediation profiles remain governed.

    **Audit BOTH `investigation_status` and `recommended_next_action`.** Critical semantic invariant (formerly a separate P6.1 — folded here; do not recreate that phase):

    ```text
    WORKFLOW CONTROL STATUS/ACTION  ≠  SECURITY CONTAINMENT RECOMMENDATION
    BLOCK / BLOCKED (workflow)      ≠  "Recommended next action: BLOCK"
    ```

    A blocked investigation may show Unable to proceed / Evidence unavailable / Additional evidence required. It must **not** show analyst-facing `Recommended next action: BLOCK` unless a governed remediation/action plan actually recommends a block action.

    **Confirmed leak path (measured 2026-08-21 — live production code):**

    ```text
    sufficiency.status = "BLOCKED"
      → _EVIDENCE_NEXT_BY_STATUS["BLOCKED"] = "BLOCK"     staged_sufficiency.py:35
      → run_status.next_action / sufficiency.next_action
      → _recommended_next_action():                       investigation_outcome.py:312-318
            value = run_status.get("next_action") or sufficiency.get("next_action")
            return str(value).strip()                     # verbatim pass-through, no mapping
      → InvestigationOutcome.recommended_next_action       investigation_outcome.py:52,163
      → analyst UI  →  "Recommended next action: BLOCK"
    ```

    `_recommended_next_action` performs **no** vocabulary translation. Remapping only `investigation_status` does **not** close this. Containment language may originate **only** from the governed remediation/action-capability path. Prefer translating control vocabulary into analyst-facing process language at the derivation/presentation seam.

    **Do not rename governed backend enum values** (`SufficiencyStatus`, `SufficiencyNextAction`, `InvestigationStatus`, `Disposition`) merely for display. Measured tokens:

    ```text
    SufficiencyStatus     = Literal["SUFFICIENT","PARTIAL","INSUFFICIENT","BLOCKED"]  # staged_sufficiency.py:18
    SufficiencyNextAction = Literal["CONTINUE","CALL_T4","CLARIFY","DEGRADE","BLOCK"] # staged_sufficiency.py:19
    investigation_status / disposition "blocked"  Literal in investigation_outcome.py:18-20
    humanize(outcome.investigation_status) at InvestigationOutcomeCard.tsx:38
    ```

    Change the display-label mapping, not the backend literal. If a backend rename ever looks necessary → STOP (new authority decision).
  - **Verify:** Frontend tests for composition by profile; backend packaging tests that SPL-authoring turns omit `investigation_outcome.investigation_status` and remediation_approval when not applicable. `cd frontend && npm test -- ChatBubble` (script is `vitest run`; owning file `src/components/ChatBubble.progress.test.tsx` — extend it or add a sibling). `cd frontend && npm run build`. Host-side `rg -n 'investigation_status|BLOCKED' backend/app/chat/contracts/investigation_outcome.py` shows the contract literals **unchanged**. NEW test proving a blocked/degraded investigation cannot produce a containment-looking user-facing recommendation derived solely from sufficiency/run-status control vocabulary: drive `derive_investigation_outcome` with `sufficiency.status="BLOCKED"` / `next_action="BLOCK"` (and the `run_status.next_action` variant, since it takes precedence in the `or`) and assert `recommended_next_action` is not the raw control token and contains no containment verb. Assert the same for `DEGRADE`/`CLARIFY`. Assert the governed remediation path is still able to recommend real containment when authorized — this must not become a blanket keyword ban. Run: `../.venv/bin/python -m pytest app/tests/<new_file>.py -q` (or the container form). Frontend assertion that no raw control token renders in the outcome card. `/invariant-check`.
  - **Depends on:** P3, P4
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P5 only

- [ ] **P6** — UI/UX SOC workspace (P6A–P6D; one phase — do not split)
  - **Do:** One assistant turn owns **ONE** maximum useful SOC answer workspace. Execute the four already-scoped sub-items below as **this single phase**. Do not create extra loop items for UUID, viewport, hierarchy, or responsive work.

    ### P6A — COE client-ID compatibility

    Fix message submission failing **before** `streamChatMessage()` runs when the app is reached over non-secure remote HTTP (`http://10.52.1.13:3010/chat`):

    ```text
    Uncaught (in promise) TypeError: crypto.randomUUID is not a function
        at handleSend (ChatPanel.tsx)
        at submit (ChatInput.tsx)

    UX: composer clears / no user bubble / no progress / NO API REQUEST
    ```

    `crypto.randomUUID` is only exposed in a **secure context** (HTTPS, or `localhost`/`127.0.0.1`). COE is reached by raw IP over HTTP, so `window.crypto.randomUUID` is undefined there and defined on the Mac. This is a **client-side ID generation compatibility** defect — not backend, T1/T2/T3/T4, Final RQC, CORS, API-base, Nginx, auth, MCP, or LLM.

    Add `frontend/src/lib/id.ts` exporting one shared `newClientId()` with a three-tier ladder:

    ```text
    1. globalThis.crypto?.randomUUID  — only when it exists AND typeof === "function"
    2. globalThis.crypto.getRandomValues — build a UUID-v4-SHAPED id;
         MUST set version nibble (byte 6 -> 0x40 | low) and variant bits (byte 8 -> 0x80 | low)
    3. final non-crypto fallback — must never be described as cryptographically secure
    ```

    These are **UI correlation identifiers only**. They must never be used for auth tokens, sessions, authorization, security decisions, or idempotency requiring cryptographic uniqueness. Say so in the module docstring.

    **Call-site consolidation — measured 2026-08-25, all 6 direct usages are in one file:**

    ```text
    frontend/src/components/ChatPanel.tsx:405   `progress-${crypto.randomUUID()}`   progress message id
    frontend/src/components/ChatPanel.tsx:569   user message id
    frontend/src/components/ChatPanel.tsx:579   user message id
    frontend/src/components/ChatPanel.tsx:589   user message id
    frontend/src/components/ChatPanel.tsx:599   user message id
    frontend/src/components/ChatPanel.tsx:621   user message id
    rg -c 'crypto\.randomUUID' frontend/src  ->  ChatPanel.tsx:6   (no other file)
    ```

    Replace all six with `newClientId()`. After the change, direct `crypto.randomUUID` must exist **only** inside `frontend/src/lib/id.ts`. Do not create a second fallback implementation anywhere. Out of scope for P6A: `architecture.md`, any backend file, CORS, `VITE_API_BASE_URL`, auth, Nginx, HTTPS rollout, MCP, LLM.

    ### P6B — Maximum useful answer viewport

    **AUDIT FIRST**, then normalize. All assistant sections for ONE turn share ONE common outer answer workspace: `w-full min-w-0` at maximum useful center/chat-column width. Do **not** constrain entire structured answer cards to prose width. Prose ~68–80ch inside the workspace; structured content (SPL/code, tables, evidence, investigation/remediation plans, progress, technical trace, provenance) uses the broader workspace.

    **Measured 2026-08-25 (`rg -n 'max-w-' <components>` — these are the anchors, do not re-derive):**

    ```text
    pages/SocCockpit.tsx:21                    lg:grid-cols-[19rem_minmax(0,1fr)_22rem]  <- center col already minmax(0,1fr): CORRECT
    components/ChatPanel.tsx:638               w-full min-w-0 max-w-full                 <- correct
    components/ChatPanel.tsx:681               .soc-stream ... overflow-x-hidden         <- CLIPS; see overflow note below
    components/ChatBubble.tsx:97               assistant max-w-[94%] / user max-w-[78%]
    components/ChatBubble.tsx:111              max-w-[68ch]   assistant prose bubble
    components/ChatBubble.tsx:192              max-w-[68ch]   cyan note
    components/ChatBubble.tsx:203              max-w-[68ch]   amber note
    components/InvestigationOutcomeCard.tsx:32        max-w-[68ch]
    components/InvestigationPlanApprovalCard.tsx:33   max-w-[72ch]
    components/RemediationPlanApprovalCard.tsx:47     max-w-[72ch]
    components/AnalystResponseCard.tsx:477     w-full min-w-0 max-w-full ... xl:max-w-[1120px]
    ```

    The reported symptom is confirmed: **68ch outcome + 72ch remediation + 1120px analyst answer** in one turn. The defect is at **card level**, not in the cockpit grid.

    Complete the audit table in Evidence for every assistant-response surface — SocCockpit, ChatPanel, ChatBubble, AnalystResponseCard, InvestigationOutcomeCard, InvestigationPlanApprovalCard, RemediationPlanApprovalCard, SPL/code containers, evidence/detail panels, provenance / "How this answer was produced", tables, progress/investigation surfaces — recording for each: **parent available width · `w-full`/`min-w-0` behavior · max-width constraint · overflow behavior · breakpoint-specific constraint**.

    **Target rule.** The outer response workspace fills the available center/chat column, uses `w-full min-w-0`, drops card-level 68ch/72ch constraints, and applies a sensible overall desktop maximum only where needed to prevent pathological ultra-wide layout. Every section of one turn aligns to the **same outer workspace grid**.

    **Content-specific width** (the constraint moves inward to the content, it is not deleted):

    ```text
    PROSE                      readable ~68-80ch, sitting INSIDE the wider workspace
    SPL / CODE                 full answer workspace; do not wrap unnecessarily; h-scroll if genuinely required
    TABLES                     available width; responsive columns / horizontal overflow when necessary
    INVESTIGATION/REMEDIATION  wider workspace; must NOT inherit prose max-width
    EVIDENCE / TECHNICAL TRACE wider workspace; collapsible where appropriate
    STATUS / SMALL CTA         sized to content; must NEVER determine the width of the whole response
    ```

    **Do NOT simply set every child to `max-w-none`.** Objective is **MAXIMUM USEFUL VIEWPORT, not MAXIMUM TEXT LINE LENGTH.** A card that stops constraining its own box must hand the readable-width constraint to its prose child.

    **Two measured conflicts to resolve, not ignore:**

    ```text
    1. ChatPanel.tsx:681  `overflow-x-hidden` on .soc-stream CLIPS horizontal overflow.
       "code/table overflow contained locally" requires the local container to scroll —
       a clipping ancestor silently truncates instead. Resolve at the stream seam.
    2. AnalystResponseCard.tsx:323,340,348,717  `<code className="whitespace-pre-wrap break-words">`
       WRAPS SPL rather than scrolling it, which contradicts "do not wrap unnecessarily".
       The <pre> ancestors (:317,:334,:347,:716) already have `overflow-auto`, and the table
       at :757 already has `overflow-x-auto` — those are correct and must stay.
    ```

    ### P6C — Response visual hierarchy

    One assistant turn should visually read as:

    1. direct answer / conclusion
    2. relevant evidence/artifact/SPL
    3. next action when applicable
    4. collapsible technical/authority detail

    No multiple quasi-independent assistant answers.

    ### P6D — Responsive acceptance

    Verify at least: wide desktop ~1440+ · MacBook/laptop · ~1024px · tablet/narrow · mobile.

    Require: no unnecessary blank right-hand area · no clipped structured content · no page-level horizontal scroll · code/table local overflow only when required · prose readable · consistent outer answer alignment · no overlapping rails · no duplicate answer surfaces.
  - **Verify:** `cd frontend && npm test && npm run build`.

    **P6A:** Host-side `rg -n 'crypto\.randomUUID' frontend/src` returns **only** `frontend/src/lib/id.ts`; `rg -n 'newClientId' frontend/src/components/ChatPanel.tsx` shows the import plus 6 call sites. NEW colocated `frontend/src/lib/id.test.ts` (vitest, `environment: 'jsdom'`, `setupFiles: ./src/test/setup.ts` — `vite.config.ts:7-9`) covering: (A) randomUUID available → helper uses it; (B) randomUUID missing, getRandomValues available → UUID-v4-shaped version nibble `4` and variant in `{8,9,a,b}`; (C) crypto undefined / randomUUID not a function → MUST NOT THROW; (D) final fallback if reachable. Stub via `vi.stubGlobal('crypto', ...)` and restore in `afterEach`. **Honesty note — measured 2026-08-25: there is NO `ChatPanel.test.tsx`.** Do not record "existing ChatPanel tests remain green".

    **P6B:** Host-side `rg -n 'max-w-\[[0-9]+ch\]' frontend/src/components` must show **no card-level ch-constraint on a workspace container**; any surviving `ch` constraint must sit on a **prose** element, and Evidence must name which one and why. Re-run the P6B anchor sweep and paste after-state next to before-state.

    **P6D — screenshot per row in Evidence:**

    ```text
    ~1440px desktop | MacBook/laptop | ~1024px | tablet/narrow | mobile
    ```

    At **every** viewport assert: no unnecessary blank right-hand area · no clipped structured content · no overlapping side rails (`19rem` left / `22rem` right, `SocCockpit.tsx:21`) · **no horizontal page scroll** · code/table overflow contained **locally** · prose still readable · one coherent assistant-answer alignment. Plus: no duplicate answers, no duplicate remediation controls, no investigation conclusion on SPL-only, collapsed "How this answer was produced" / technical path.

    **Honesty note:** there are no width/layout unit tests in this repo and `npm test` will not catch a viewport regression — the screenshot matrix **is** the P6B/P6D evidence.

    **COE acceptance for P6A (after the code lands):** over remote HTTP at `http://10.52.1.13:3010/chat` — (1) type a message, (2) Enter/Send, (3) user bubble appears, (4) progress state appears where applicable, (5) browser issues the API request, (6) no `randomUUID` exception in console. Only after this exception is gone may any subsequent network failure be classified as a separate CORS/API-base/Nginx/auth/backend issue.
  - **Depends on:** P5
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P6 only

- [ ] **P7** — Full regression + Mac end-to-end / UI acceptance
  - **Do:** Mac remains primary implementation/UI acceptance. Run required suites and product scenarios A–M. Record LLM/MCP honest degrade on Mac. Do not fake services. Use **effective** runtime values (`AI_SOC_ENV_PROFILE=coe`; T4 timeout from `.env`, currently `10` — do not assume `development` / `120`).

    Acceptance categories (map onto the scenario matrix; do not invent a second table):

    ```text
    UNDERSTANDING
      exact governed ACCEPT; catalogue paraphrase ACCEPT; ABSTAIN → T4;
      T4 unavailable fail-closed; explicit literal survival; multi-turn corrections
    PRODUCT BEHAVIOR
      pure SPL authoring; investigation; MITRE; knowledge; remediation applicability
    GOVERNANCE
      candidate_spl non-executable; normalized_spl; exact-call authorization;
      HIL/RBAC; Resource Planner authority; evidence authority; remediation authority
    FRONTEND
      no duplicate answers; no duplicate remediation CTA; no false BLOCK containment
      wording; wider workspace; readable prose; full-width structured artifacts;
      responsive layout; UUID fallback
    ```

    Real Mac scenario (P7-C — SPL authoring *shape*, not a keyword patch):

    ```text
    create a spl command for checking the firewall activities in last 27 days
    ```

    Expected: correct Final RQC product shape; coherent SPL-focused answer; no fake InvestigationOutcome; no irrelevant remediation offer; no `Recommended next action: BLOCK`; appropriate provenance; useful viewport.

    Explicit review-only scenario (P7-D — literals must survive):

    ```text
    Give me only a review-only SPL query for index=pgcil_soc and
    sourcetype=cisco:firepower for the last 30 days. Do not execute it.
    ```

    **Mac/Linux limitation (do not hide):** Mac governance step 1 cannot be valid because committed generated metadata contains Linux path semantics. P8 cannot become release-ready until the exact candidate SHA is checked on Linux (`OS=Linux`, `CODE_SHA=FINAL_CANDIDATE_SHA`, governance step 1=`PASS`). LLM/MCP are **not** required for that Linux governance proof.
  - **Verify:** `PATH="$PWD/.venv/bin:$PATH" ./scripts/run_stage3_governance_regression.sh` on the **host venv** (never in the container). Governance **step 1 is a ratified `KNOWN_MACOS_GOVERNANCE_ENV_LIMITATION`** — record it as such, do not work around it; every other governance step must still run and pass on Mac. Full backend suite via `cd backend && ../.venv/bin/python -m pytest -q` or the container form; targeted authority/fidelity/HIL/MCP suites green; `cd frontend && npm test && npm run build` green; scenario matrix table filled in Evidence with pass/fail. Classify any failure as regression / env / pre-existing **by NAME and classification** against the P0 baseline (and P2's 20-fail set) — do not hide postgres, migration-readiness, or macOS GitHub-skill factory failures; do not trust counts or `.pytest_cache` `lastfailed`. If the governance runner is still unavailable, that is an env blocker to record explicitly — do not silently substitute the plain pytest run for it.
  - **Depends on:** P0 (runner + baseline), P1–P6
  - **Evidence:** _(fill when done)_
  - **Commit:** optional evidence-only commit under `docs/evals/` if needed

- [ ] **P8** — Candidate / release evidence (STOP — no push/merge/deploy)
  - **Do:** Produce `FINAL_CANDIDATE_SHA`. Confirm `architecture.md` byte-identical to freeze commit `49c5a494` (`git diff 49c5a494 -- architecture.md` empty). Clean worktree. Record:

    ```text
    FINAL_CANDIDATE_SHA
    CODE_SHA
    ENVIRONMENT=MAC
    PROFILE                  (effective: coe unless measured otherwise)
    LLM_STATE
    MCP_STATE
    BACKEND_TESTS
    FRONTEND_TESTS
    UI_ACCEPTANCE
    KNOWN_ENV_LIMITATIONS    (postgres, migration-readiness, macOS GitHub skill factory,
                              governance step 1 on Mac)
    ```

    Then **STOP**. Do **not** push, merge, rebase, deploy, or modify VPS/COE source in this plan.

    P8 on Mac **cannot** declare RELEASE_READY. Linux governance proof remains a **later external** step against the exact same SHA:

    ```text
    CODE_SHA          = FINAL_CANDIDATE_SHA
    OS                = Linux (VPS acceptable)
    governance step 1 = PASS
    LLM/MCP           not required for this proof
    ```

    Next **external** promotion workflow (operator-driven, after this loop):

    ```text
    FINAL_CANDIDATE_SHA
      → VPS checkout exact SHA
      → Linux governance + deterministic validation
      → PASS
      → push feature branch
      → PR
      → merge master
      → MASTER_RELEASE_SHA
      → Mac / VPS / COE exact same SHA
      → COE live LLM/MCP acceptance
    ```
  - **Verify:** `git status --short`; `git diff 49c5a494 -- architecture.md`; Evidence block complete with every field above; no push/merge/deploy performed.
  - **Depends on:** P7
  - **Evidence:** _(fill when done)_
  - **Commit:** none unless recording an eval report file

## Product scenarios (P7 matrix)

| ID | Scenario | Expected |
|---|---|---|
| A | Exact governed T1–T3 happy path | ACCEPT; T4 skipped |
| B | Known catalogue paraphrase | ACCEPT when complete/confident |
| C | Mac SPL authoring: `create a spl command for checking the firewall activities in last 27 days` | Final RQC SPL authoring; coherent SPL-focused answer; no fake InvestigationOutcome; no irrelevant remediation offer; no `Recommended next action: BLOCK`; useful viewport |
| D | Review-only: `Give me only a review-only SPL query for index=pgcil_soc and sourcetype=cisco:firepower for the last 30 days. Do not execute it.` | Literals survive (`index`, `sourcetype`, 30 days, do-not-execute); review-only; no execute |
| E | Known rich Cisco detection | ACCEPT when complete |
| F | “Is this activity suspicious?” | ABSTAIN / clarify as appropriate |
| G | Unknown investigation | ABSTAIN → T4 → investigation-shaped RQC when warranted |
| H | Explicit MITRE | ACCEPT when governed match complete |
| I | Multi-turn 30d → 3d | Time correction preserved |
| J | Entity/time 10.0.0.5/24h → 10.0.0.8/2h | Literals corrected and enforced |
| K | Explicit do not execute through T4 path | DET rejects execute=true |
| L | T1–T3 ABSTAIN + T4 unavailable/timeout/invalid | Fail-closed semantic resolution; no partial contract resurrection; no invented Final RQC; clarify or honest degrade |
| M | Genuine investigation BLOCKED by evidence/runtime condition | Status may be `blocked`, but **no** user-facing containment recommendation derived from workflow `BLOCK`/`BLOCKED` vocabulary |

## Verification gaps (flag before coding)

- ~~Exact frontend test file names for ChatBubble composition may need creation during P5 audit-first.~~ **Resolved 2026-08-21:** `frontend/src/components/ChatBubble.progress.test.tsx` exists and passes (2 tests); extend it or add a sibling.
- Which existing suite already covers 105/105 path acceptance must be confirmed in P0/P7 (`question` evals / governance script) — do not invent a second 105 harness.
- ~~**Open (P7 blocker):** the governance regression runner on this Mac is unresolved.~~ **Resolved 2026-08-21:** MAC-FIRST host venv established and measured; governance now executes. **One prerequisite remains and is an operator decision, not a code gap:** `AI_SOC_GITHUB_SKILL_CLONE_ROOT` (external clone absent) — P0 owns it. Linux governance step 1 vs exact candidate SHA remains a P8 external gate, not a Mac P7 blocker.
- ~~P6.1 / P6A as extra loop phases.~~ **Resolved 2026-08-25 consolidation:** control-vocabulary leak folded into **P5**; UUID / viewport / hierarchy / responsive stay **P6A–P6D inside P6**. Remaining execution is `P3 → P4 → P5 → P6 → P7 → P8`.

## Anchors verified 2026-08-21 (pre-execution review)

- SHAs `49c5a494` (architecture freeze) and `49e545d9` (base) both exist and are ancestors of HEAD; `git diff 49c5a494 -- architecture.md` is **empty** (freeze intact).
- All 19 backend modules and all 5 frontend components in the reuse table exist at the stated paths.
- All 5 named symbols resolve: `understand_query` (`query_understanding/parser.py:86`), `match_use_cases` (`use_cases/registry.py:119`), `lane_for_match_path` (`chat/lane_router.py:48`), `derive_investigation_outcome` (`chat/contracts/investigation_outcome.py:62`), `maybe_attach_remediation_offer` (`chat/remediation_runtime.py:144` — was missing from the rev 1 reuse table).
- All 6 P0 `rg` anchors match the frozen `architecture.md`.
- `.cursor/hooks/audit-plan-discipline.sh` → **0 gaps** at last consolidation (2026-08-25). Remaining unchecked items are P3–P8.
- The 3 test files cited as existing do exist; the 3 cited as NEW do not yet exist (as intended).
- **Control-vocabulary leak confirmed in live code:** `SufficiencyNextAction` includes `"BLOCK"`
  (`staged_sufficiency.py:19`), `_EVIDENCE_NEXT_BY_STATUS["BLOCKED"] = "BLOCK"` (line 35), and
  `_recommended_next_action` (`investigation_outcome.py:312-318`) passes it through **verbatim with no
  vocabulary translation** into `recommended_next_action` → analyst UI. Owned by **P5** (folded from P6.1).
- **Runners measured:** host venv and container both return **77 passed** on the two P1 suites, and both run
  **pytest 9.1.1** (no version skew between runners).
- **Full-suite baseline MEASURED 2026-08-21 on the host venv — the tree is NOT green. Do not assume green.**

  ```text
  cd backend && ../.venv/bin/python -m pytest -q -p no:cacheprovider
  21 failed, 6042 passed, 7 skipped, 6 xfailed in 443.72s
  ```

  No runtime code was changed by the review that measured this (the rev-3 commit touches `plans/` only), so
  all 21 are **pre-existing or environmental**. Classified by name — P7 must diff against *these names*, not
  counts:

  | Count | Tests | Classification |
  |---|---|---|
  | 14 | `integration/test_canonical_retention_purge.py` (11), `integration/test_handoff_postgres.py` (2), `integration/test_telemetry_postgres.py` (1) | **Env** — PostgreSQL-backed; `pyproject.toml` marks `integration` as skippable when the DB is unavailable |
  | 5 | `test_migration_readiness.py` | **Env** — DB/migration dependent |
  | 1 | `test_github_skill_expansion_factory_baseline.py::test_factory_generators_check_against_committed_artifacts` | **Env** — same missing `AI_SOC_GITHUB_SKILL_CLONE_ROOT` clone that stops governance at step 1 |
  | 1 | `test_live_path_untouched_by_ec.py::test_races_freeze_files_unchanged_since_baseline` | **Pre-existing code state — audited below; `OPERATOR_DECISION_REQUIRED`** |

### RACES freeze audit (completed 2026-08-21 — audit only, nothing changed)

`RACES commits modified freeze files vs 08c8b40c: ['backend/app/chat/pipeline.py']`, from
`3a5f5001 fix(spl): enforce request authority and semantic fidelity`.

**Mechanism (read, not guessed).** `RACES_BASELINE_SHA = "08c8b40c"` is a hardcoded constant in
`backend/app/tests/test_live_path_untouched_by_ec.py:129`; `RACES_FREEZE_PATHS = EC_FORBIDDEN_PREFIXES`.
The test diffs `08c8b40c...HEAD` and fails on any freeze-path hit. The approved maintenance procedure
is **not** a script: the constant is advanced to the exact reviewed commit and a justification comment
appended — the file carries that history in-place ("Advanced again through P10-P13 at `9f1ec922`…",
"Advanced through the final architecture-conformance correction at `08c8b40c`… the freeze continues
from their exact reviewed commit"). Each precedent advance is tied to **reviewed/approved** work.

**Findings.**
1. **Hunks:** 13 hunks, +269 lines, **4 deletions**. New helper `_is_deterministic_spl_utility_authoring`; touchpoints in `graph_node_spl_postprocessor`, `graph_node_execution`, `graph_node_rag_early`, `graph_node_context_finalize`, `_candidate_spl_stage`, `_candidate_from_default_template`, `_context_stage`; new `_candidate_from_user_bound_review_only_skeleton`.
2. **Why:** enforce request authority / semantic fidelity so a rendered SPL cannot drift from explicit user constraints.
3. **Path:** **production live path** (`app/chat/pipeline.py`), but **not EC work** — the commit touches no `app/demo/` file. The freeze exists to stop RACES/EC from reaching production `/chat`; this is production SPL-governance work, which is the class the precedent comments describe as advanceable.
4. **Frozen execution authority altered?** No. The change is uniformly **tightening**.
5. **Weakens any authority axis?** No — measured on the added lines: `execution_eligible: False` and `execution_enabled: False` pinned repeatedly, `optimization_revalidation_approved: False`, `mcp_allowed` **narrowed** (`_mcp_allowed(state)` → forced `False` under a new condition), `approved`/`normalized_spl` still sourced from the real validator. The replacement predicate is strictly more restrictive than the one it replaced: it additionally requires `contract.sufficient_for_spl_authoring and contract.response_shape == "spl_only"`. All 4 deletions are replaced by stricter variants. No HIL/RBAC/exact-call/Resource-Planner/evidence authority is bypassed.
6. **Could it live in a non-frozen seam?** Partly — the request-authority primitives already went to `spl/request_authority.py` (non-frozen). The residue in `pipeline.py` is call-site wiring at the SPL stages; relocating it would need a new seam and risks duplicate authority, which this plan prohibits.
7. **Collateral risk: none.** `3a5f5001` is the **only** commit in `08c8b40c..HEAD` touching any freeze path, so advancing the baseline to HEAD would bless exactly this one change and silently accept no unrelated protected drift.

**Decision: RESOLVED 2026-08-21 — operator-approved, branch B.** `RACES_BASELINE_SHA` advanced from
`08c8b40c` to the exact full SHA `3a5f500104fb7a9ba609fc70aeb4af5894cee2eb`, **pinned to that commit
and deliberately NOT to HEAD**, so no later protected-file change is blessed. The assertion is
unchanged and no allowlist was added; the in-file justification comment follows the established
style. Approval covers **only** the previously reviewed `3a5f5001` production change.

**Still in force for P3–P8:** `pipeline.py` remains RACES-protected. Any **new** need to change a
protected freeze path requires STOP + explicit operator decision. Do not treat the `3a5f5001`
advance as a standing license to edit freeze files.

```text
test_live_path_untouched_by_ec.py  →  8 passed   (freeze test GREEN)
commit: 5cf66404 test(governance): advance RACES baseline for SPL authority fix
```

  **Runner caveat — do not "verify" these in the container.** The same six files fail *worse* there
  (**33 failed**), because these tests shell out to git and `/app` is not a git repo. Git/freeze-aware and
  DB-aware tests belong on the **host venv**; the container remains fine for ordinary application tests.
  Per `CLAUDE.md`, master was 26 tests red for three days unnoticed — there is no CI here.

## Drift log

- 2026-08-25 (post-P2 consolidation, plan-only): Remaining execution folded to `P3 → P4 → P5 → P6 → P7 → P8`. P6.1 control-vocabulary leak moved into P5; P6A UUID / P6B viewport / P6C hierarchy / P6D responsive stay inside P6 (not extra phases). P8 records `FINAL_CANDIDATE_SHA` and **stops** — no push/merge/deploy. Promotion is Mac SHA → VPS Linux governance → push/PR/merge → `MASTER_RELEASE_SHA` → Mac/VPS/COE exact SHA → COE live acceptance. Config drift recorded, not fixed: `.env` `AI_SOC_ENV_PROFILE=coe` (docs previously claimed `development`); effective T4 timeout `.env=10` (not development profile `120`). P2 full suite 20 failed / 6097 passed classified as postgres + migration-readiness + macOS GitHub skill factory. HEAD `5d1e487e`; `origin/master` `49e545d9` is ancestor — no Git divergence.
- 2026-08-21: Architecture freeze landed as `49c5a494` on master before this plan; feature branch `feat/complete-or-abstain-t4-ux` carries prior auth/COE/SPL/UI commits plus this plan. Do not re-amend architecture.md here.
- 2026-08-21 (rev 3, pre-LOOP gap closure): (a) **P6.1 added** — workflow control vocabulary must never present as security containment; rev 2 had asserted only `BLOCKED` was real, which was **half wrong**: `BLOCKED` is the status and `BLOCK` is the `SufficiencyNextAction`, and `_recommended_next_action` leaks it verbatim to the analyst. Remapping `investigation_status` alone does not close it. **(Superseded 2026-08-25: that work is now P5, not a separate phase.)** (b) **P2 T4-failure negative made REQUIRED** (unavailable / timeout / invalid response → fail closed at semantic authority; five explicit must-hold clauses) plus scenario **L**. (c) **P2 literal-machinery wording corrected** — rev 2 over-committed to `spl/request_authority.py` as the literal authority; now a generality audit across all Final-RQC families, with reuse-directly vs extract-to-shared-seam branches. (d) Scenario **M** added. (e) **Governance runner resolved MAC-FIRST** via gitignored host venv; remaining `AI_SOC_GITHUB_SKILL_CLONE_ROOT` prerequisite recorded as an operator decision rather than silently relocating P7 to COE.
- 2026-08-21 (rev 2, pre-execution review): corrected before any code was written — (a) every backend Verify command was unrunnable on this Mac (no host pytest) → switched to the container form and added a toolchain section; (b) P7's governance script is blocked on both host and container → P0 now owns the runner decision; (c) P6 named a non-existent token `BLOCK` (actual: `BLOCKED`/`blocked`) and risked editing a governed `Literal` → rescoped to presentation-label mapping; (d) P2's "T4 must not commit those fields" contradicted the existing `SemanticT4Proposal`, which already carries `required_capabilities` → clarified as *recompute, do not delete*, per frozen §11; (e) P3 audited 3 seams but the blocked posture is also decided in `evidence/final_evidence_gate.py` → added as seam 4; (f) P2 now points at existing literal machinery (`request_authority.py`, `user_constraint_bindings.py`) instead of implying a new parallel structure.
- Separate agentic investigation production plan remains independent; this plan owns understanding authority + response/UI applicability, not envelope/PlanDelta feature buildout.
