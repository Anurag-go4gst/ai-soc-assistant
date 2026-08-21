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

**Remaining governance prerequisite (operator decision, NOT a Python problem).** With the venv,
`run_stage3_governance_regression.sh` executes but exits **1 at its first step**, needing an
external third-party clone that is absent from this Mac:

```text
GitHub skill clone root not found: /private/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
REGRESSION FAILED: github discovery index stale
```

Steps 1–3 (`build_github_skill_discovery_index.py`, `score_github_skill_triage.py`,
`build_github_skill_factory_artifacts.py`) read it via `AI_SOC_GITHUB_SKILL_CLONE_ROOT`
(`scripts/github_skill_factory_lib.py:20`); it is set in neither `.env` nor any profile, and no
clone exists anywhere on this host. Cloning an external repository is an **operator decision** —
P0 must resolve it by pointing `AI_SOC_GITHUB_SKILL_CLONE_ROOT` at an existing clone or having
the operator create one (`docs/skills/README.md:42`). **Do not modify the governance script to
skip these steps** unless the script is proven defective.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same Verify gate fails twice on one item, **or**
- Architecture interpretation ambiguous / would require editing `architecture.md`, **or**
- New authority decision required, **or**
- Implementation seems to need a second router, second T4 service, or T4 investigation runtime, **or**
- Security / HIL / RBAC / exact-call would be weakened, **or**
- Legitimate existing work would need deletion

## Dependency order

`P0 → P1 → P2 → P3 → P4 → P5 → P6 → P6.1 → P7 → P8`

## Prohibited globally

- Modify `architecture.md`
- Special-case individual user questions (including firewall phrasing)
- Keyword patches / firewall-only rules
- Implement embeddings now
- Second router / second planner / second T4 / T4 investigation runtime
- Fake LLM or MCP availability
- Hide failing tests to continue
- Merge or push unless operator requests

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
| Control-vocabulary leak (P6.1) | `chat/contracts/staged_sufficiency.py:18-19,35` (`SufficiencyStatus` / `SufficiencyNextAction` / `_EVIDENCE_NEXT_BY_STATUS`), `chat/contracts/investigation_outcome.py:52,163,312-318` (`recommended_next_action` / `_recommended_next_action`) |
| SPL fidelity | `spl/request_authority.py`, `chat/review_only_spl_renderer.py` |
| Provenance | `control_plane_trace`, `route_plan_shadow`, `investigation_lineage`, `provenance.semantic_t4` |
| UI composition | `ChatBubble.tsx`, `InvestigationOutcomeCard.tsx`, `RemediationPlanApprovalCard.tsx`, `AnalystResponseCard.tsx`, `ChatPanel.tsx` |

## Checklist

- [ ] **P0** — Baseline + architecture freeze gate
  - **Do:** Record branch, base SHA `49e545d9`, architecture freeze SHA `49c5a494`, clean worktree (ignore local `.claude/` only), Mac profile/flags (this host is `AI_SOC_ENV_PROFILE=development`: ResourcePlan execution ON, dispatch-v2 OFF, `AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=true` — note the repo default for that flag is **false**), LLM/MCP posture, and pin `architecture.md` as read-only for this plan. **Establish and record the test runner** per *Test toolchain on this Mac* — the runner decision is **MAC-FIRST and already resolved: host venv for governance, container for application tests**; re-confirm both run, and do not relocate P7 to COE/VPS. **Resolve the one open governance prerequisite**: set `AI_SOC_GITHUB_SKILL_CLONE_ROOT` to an existing clone, or have the operator create one — governance exits 1 at step 1 without it. If neither is possible, record the concrete reason and **STOP for the runner decision** rather than silently moving P7 to COE. **Capture a green pre-change baseline** for the suites P1–P5 will touch, so P7 can honestly classify any failure as regression vs pre-existing. Confirm no equivalent active plan exists beyond this file. Do not change runtime code.
  - **Verify:** `git rev-parse HEAD`; `git status --short` shows only optional local tool noise; `git diff 49c5a494 -- architecture.md` is empty; `git show 49c5a494:architecture.md | rg -n 'COMPLETE|ABSTAIN|MUST reject|MUST NOT materially contradict|InvestigationOutcome applies|embedding / vector'` (host-side; `rg` is not in the container) returns all six anchors; `docker compose exec -T backend python -m pytest app/tests/test_t1_t4_authority_boundary.py app/tests/test_spl_query_fidelity.py app/tests/test_t4_contract_merge_authority.py -q` recorded as the baseline; `cd frontend && npm test` recorded as the baseline. `test ! -w` is not required — instead prove no `architecture.md` diff during later phases.
  - **Depends on:** none
  - **Evidence:** _(fill when done)_
  - **Commit:** none (docs evidence in plan Evidence only) or `docs(plan): record P0 baseline` if an evidence file is added under `docs/evals/`

- [ ] **P1** — T1–T3 complete-or-abstain acceptance gate
  - **Do:** AUDIT FIRST the live path `understand_query` → `match_use_cases` → `lane_for_match_path` → known vs guided. Implement a single DET acceptance gate: ACCEPT only when match is complete, confident, margin-sufficient, compatible, and fully governed; otherwise ABSTAIN with no partial semantic commit. Keep a clean T3 candidate interface so future lexical∪embedding candidates can share the gate. Do not implement embeddings. Do not special-case queries.
  - **Verify:** `docker compose exec -T backend python -m pytest app/tests/test_t1_t4_authority_boundary.py app/tests/test_spl_query_fidelity.py -q` (both files exist; measured green pre-change) plus NEW focused tests (create `app/tests/test_complete_or_abstain_understanding.py`) covering: exact 105 ACCEPT+T4 skipped; strong catalogue paraphrase ACCEPT; single generic source token cannot bind rich detection; unclear objective ABSTAIN; unknown SOC ask ABSTAIN.
  - **Depends on:** P0
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P1 only

- [ ] **P2** — T4 full semantic fallback + DET validation
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
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P2 only

- [ ] **P3** — Final-RQC product applicability
  - **Do:** AUDIT FIRST the **four** seams below (rev 1 listed only the first three; the fourth is where the blocked status is actually decided):
    1. `chat/evidence_planner.py:480` — the `spl_generation_only` branch. Confirmed shape: unless `is_universal_utility_spl_authoring` matches (→ `answer_mode="spl_utility_authoring"`), it falls through to `answer_mode="live_investigation"` with `needs_spl=True`, `needs_mcp` descriptive and `mcp_allowed=mcp_authorised` (false when not catalogue-matched). This is the mislabel the plan targets.
    2. `chat/contracts/investigation_outcome.py:62` — `derive_investigation_outcome`.
    3. `chat/remediation_runtime.py:144` — `maybe_attach_remediation_offer`.
    4. **`evidence/final_evidence_gate.py`** — independently special-cases `spl_generation_only`: line 476 (`spl_generation_only` + `route_live_data_request` + zero collected evidence) and its presence in `_POLICY_SEVERITY_FAMILIES` (line 449) alongside `_NON_SEVERITY_INTENT_FAMILIES` (line 433). Fixing only `evidence_planner.py` will leave this path producing the same wrong posture.

    Make product lifecycle selection depend on Final RQC answer goal / investigation shape — not on T4_USED, MCP unavailable, or missing live rows. Pure SPL authoring must use review-only SPL composition without InvestigationOutcome `blocked`/`BLOCKED`/remediation. Investigation-shaped RQCs still enter the common investigation lifecycle regardless of T1–T3 vs T4 understanding path.
  - **Verify:** NEW `app/tests/test_final_rqc_product_applicability.py` including generic coverage for SPL-authoring shaped RQC (no InvestigationOutcome investigation_status packaging / no remediation_offer_required by default) and investigation-shaped RQC still eligible for outcome; add at least one case entering through `final_evidence_gate` so seam 4 is pinned, not just seam 1. Reproduce the firewall SPL authoring *shape* via signals/fixtures without hardcoding that sentence as a special case. `docker compose exec -T backend python -m pytest app/tests/test_final_rqc_product_applicability.py -q`. `/invariant-check`.
  - **Depends on:** P2
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P3 only

- [ ] **P4** — Deterministic understanding provenance
  - **Do:** Extend existing provenance (`control_plane_trace` / `route_plan_shadow` / `investigation_lineage` / RQC `provenance`) with a concise deterministic strip: T1/T2/T3 accept-or-abstain, T4 used/skipped, final intent, final owner. Surface under existing “How this answer was produced”. No new tracing framework. No chain-of-thought.
  - **Verify:** Unit/contract test that provenance fields are present and deterministic for ACCEPT and ABSTAIN→T4 paths, run as `docker compose exec -T backend python -m pytest app/tests/<new_or_owning_file>.py -q`; frontend or lineage consumer test if a UI field is added. Host-side `rg` proves no new telemetry catalog event invented without closed-catalog registration (canonical planning telemetry is a **closed catalog** — `emit_planning_event()` rejects unregistered names, so an unregistered event fails rather than silently passing).
  - **Depends on:** P3
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P4 only

- [ ] **P5** — Response ownership + outcome/remediation semantics
  - **Do:** Define one primary response profile from Final RQC. Fix `ChatBubble` stacking so SPL authoring does not show InvestigationOutcomeCard + local remediation CTA + RemediationPlanApprovalCard + AnalystResponseCard together. Remove or demote the **local** OutcomeCard remediation Yes/Not-now so only backend-governed `RemediationPlanApprovalCard` is authoritative when remediation applies. Confirmed target: `InvestigationOutcomeCard.tsx` line 17 holds purely local `useState<'yes' | 'not_now' | null>` driving the CTA block at lines 88–108 — local UI state with no backend authority, which is the duplication to remove. Note line 18 already short-circuits (`if (!outcome.investigation_status) return null`), so a correct P3 backend fix makes the card self-hide; P5 should rely on that rather than adding a frontend denylist. Investigation / knowledge / remediation profiles remain governed.
  - **Verify:** Frontend tests for composition by profile; backend packaging tests that SPL-authoring turns omit `investigation_outcome.investigation_status` and remediation_approval when not applicable. `cd frontend && npm test -- ChatBubble` (script is `vitest run`, so the extra `--run` in rev 1 was redundant; the existing owning file is `src/components/ChatBubble.progress.test.tsx` — extend it or add a sibling). `cd frontend && npm run build`.
  - **Depends on:** P3, P4
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P5 only

- [ ] **P6** — UI/UX SOC workspace improvement
  - **Do:** Widen the structured answer workspace (center column `w-full` / sensible desktop max) while keeping prose ~68–80ch. Allow SPL/code, tables, plans, evidence, traces to use broader width. Clear hierarchy: direct answer → supporting artifact → next action when applicable → collapsible technical/authority details. Responsive: laptop, wide desktop, mobile.
    **Vocabulary fix — presentation layer only.** Both tokens exist, in *different* fields, and rev 2 of this plan initially got this wrong by claiming only `BLOCKED` was real. Measured 2026-08-21:

    ```text
    SufficiencyStatus     = Literal["SUFFICIENT","PARTIAL","INSUFFICIENT","BLOCKED"]  # staged_sufficiency.py:18
    SufficiencyNextAction = Literal["CONTINUE","CALL_T4","CLARIFY","DEGRADE","BLOCK"] # staged_sufficiency.py:19
    _EVIDENCE_NEXT_BY_STATUS["BLOCKED"] = "BLOCK"                                     # staged_sufficiency.py:35
    ```

    So `BLOCKED` is the **status** and `BLOCK` is the **workflow next-action**. `investigation_status`/`disposition` `"blocked"` are typed `Literal[...]` in `chat/contracts/investigation_outcome.py:18-20`; the analyst-visible status string comes from `humanize(outcome.investigation_status)` at `InvestigationOutcomeCard.tsx:38`. **Change the display-label mapping, not the backend literal** — renaming a contract value is a governed-contract change outside this item's scope and would break the `Literal` types and their tests. If a backend rename ever looks necessary, that is a new authority decision → stop condition. The `BLOCK` next-action leak is **not** cosmetic and is handled separately in **P6.1**, which is a required item, not an optional polish.
  - **Verify:** `cd frontend && npm test && npm run build`; host-side `rg -n 'investigation_status|BLOCKED' backend/app/chat/contracts/investigation_outcome.py` shows the contract literals **unchanged**; manual Mac screenshot checklist recorded in Evidence for: no duplicate answers, no duplicate remediation controls, no investigation conclusion on SPL-only, wider workspace, readable prose, SPL not cramped, collapsed “How this answer was produced” / technical path.
  - **Depends on:** P5
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P6 only

- [ ] **P6.1** — Workflow control vocabulary must never present as security containment
  - **Do:** Enforce this invariant, which is **separate from and not satisfied by** the P6 status-label remap:

    ```text
    WORKFLOW CONTROL STATUS/ACTION  must never be presented as  SECURITY CONTAINMENT ACTION
    ```

    **Confirmed leak path (measured 2026-08-21 — this is live production code, not hypothetical):**

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

    `_recommended_next_action` performs **no** vocabulary translation, so the workflow-control token reaches the analyst verbatim. Audit **both** surfaces — `investigation_status` presentation **and** `recommended_next_action` derivation/presentation. Remapping only `investigation_status` does **not** close this and must not be recorded as closing it.

    A degraded/blocked investigation may render as “Unable to proceed” / “Evidence unavailable”. It must **never** render as or imply “Block IP”, “Block firewall traffic”, or any containment step, unless a governed remediation/action contract explicitly authorizes that action. Containment language may originate **only** from the governed remediation/action-capability path, never from sufficiency or run-status control vocabulary. Prefer fixing the derivation/presentation seam (translate control vocabulary into analyst-facing process language) over renaming enums. **Do not rename governed backend enum values** — if architecture appears to require it, that is a new authority decision → STOP.
  - **Verify:** NEW test proving a blocked/degraded investigation cannot produce a containment-looking user-facing recommendation derived solely from sufficiency/run-status control vocabulary: drive `derive_investigation_outcome` with `sufficiency.status="BLOCKED"` / `next_action="BLOCK"` (and the `run_status.next_action` variant, since it takes precedence in the `or`) and assert `recommended_next_action` is not the raw control token and contains no containment verb. Assert the same for `DEGRADE`/`CLARIFY`. Assert the governed remediation path is still able to recommend real containment when authorized — this must not become a blanket keyword ban. Run: `../.venv/bin/python -m pytest app/tests/<new_file>.py -q` (or the container form). Frontend assertion that no raw control token renders in the outcome card. `/invariant-check`.
  - **Depends on:** P5
  - **Evidence:** _(fill when done)_
  - **Commit:** one logical commit for P6.1 only

- [ ] **P7** — Full regression + Mac end-to-end acceptance
  - **Do:** Run required suites and product scenarios A–K from the operator brief (exact, paraphrase, firewall SPL authoring shape, explicit review-only SPL with do-not-execute, rich Cisco detection, ambiguous suspicious, unknown investigation, MITRE, multi-turn time/entity correction, literal survival). Record LLM/MCP honest degrade on Mac. Do not fake services.
  - **Verify:** `PATH="$PWD/.venv/bin:$PATH" ./scripts/run_stage3_governance_regression.sh` on the **host venv** (never in the container — read-only `/workspace` vs `REPO_ROOT=/workspace` + `cd backend && pytest`), with the `AI_SOC_GITHUB_SKILL_CLONE_ROOT` prerequisite resolved in P0. Full backend suite via `cd backend && ../.venv/bin/python -m pytest -q` or the container form; targeted authority/fidelity/HIL/MCP suites green; `cd frontend && npm test && npm run build` green; scenario matrix table filled in Evidence with pass/fail. Classify any failure as regression / env / pre-existing **by diffing against the P0 baseline** — per `CLAUDE.md`, there is no CI here, so do not assume a red test is pre-existing; diff failure **names**, not counts (`.pytest_cache` `lastfailed` accumulates across filtered runs). If the governance runner is still unavailable, that is an env blocker to record explicitly — do not silently substitute the plain pytest run for it.
  - **Depends on:** P0 (runner + baseline), P1–P6, P6.1
  - **Evidence:** _(fill when done)_
  - **Commit:** optional evidence-only commit under `docs/evals/` if needed

- [ ] **P8** — Release / git synchronization record
  - **Do:** Confirm `architecture.md` byte-identical to freeze commit `49c5a494` for that file content path (`git diff 49c5a494 -- architecture.md` empty). Clean worktree. Record CODE_SHA, ENVIRONMENT=MAC, PROFILE, LLM_STATE, MCP_STATE, TEST_RESULTS, UI_ACCEPTANCE. Do not deploy to VPS/COE in this plan.
  - **Verify:** `git status --short`; `git diff 49c5a494 -- architecture.md`; Evidence block complete.
  - **Depends on:** P7
  - **Evidence:** _(fill when done)_
  - **Commit:** none unless recording an eval report file

## Product scenarios (P7 matrix)

| ID | Scenario | Expected |
|---|---|---|
| A | Exact governed T1–T3 happy path | ACCEPT; T4 skipped |
| B | Known catalogue paraphrase | ACCEPT when complete/confident |
| C | Firewall SPL authoring shape | Final RQC SPL authoring; no InvestigationOutcome BLOCK/remediation pollution |
| D | Explicit review-only SPL with index/sourcetype/time + do not execute | Literals survive; review-only; no execute |
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
- ~~**Open (P7 blocker):** the governance regression runner on this Mac is unresolved.~~ **Resolved 2026-08-21:** MAC-FIRST host venv established and measured; governance now executes. **One prerequisite remains and is an operator decision, not a code gap:** `AI_SOC_GITHUB_SKILL_CLONE_ROOT` (external clone absent) — P0 owns it.

## Anchors verified 2026-08-21 (pre-execution review)

- SHAs `49c5a494` (architecture freeze) and `49e545d9` (base) both exist and are ancestors of HEAD; `git diff 49c5a494 -- architecture.md` is **empty** (freeze intact).
- All 19 backend modules and all 5 frontend components in the reuse table exist at the stated paths.
- All 5 named symbols resolve: `understand_query` (`query_understanding/parser.py:86`), `match_use_cases` (`use_cases/registry.py:119`), `lane_for_match_path` (`chat/lane_router.py:48`), `derive_investigation_outcome` (`chat/contracts/investigation_outcome.py:62`), `maybe_attach_remediation_offer` (`chat/remediation_runtime.py:144` — was missing from the rev 1 reuse table).
- All 6 P0 `rg` anchors match the frozen `architecture.md`.
- `.cursor/hooks/audit-plan-discipline.sh` → **0 gaps**, 9 Verify fields, 9 unchecked items.
- The 3 test files cited as existing do exist; the 3 cited as NEW do not yet exist (as intended).
- **Control-vocabulary leak confirmed in live code:** `SufficiencyNextAction` includes `"BLOCK"`
  (`staged_sufficiency.py:19`), `_EVIDENCE_NEXT_BY_STATUS["BLOCKED"] = "BLOCK"` (line 35), and
  `_recommended_next_action` (`investigation_outcome.py:312-318`) passes it through **verbatim with no
  vocabulary translation** into `recommended_next_action` → analyst UI. P6.1 exists for this.
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
  | 1 | `test_live_path_untouched_by_ec.py::test_races_freeze_files_unchanged_since_baseline` | **Pre-existing code state** — `RACES commits modified freeze files vs 08c8b40c: ['backend/app/chat/pipeline.py']`, introduced by `3a5f5001 fix(spl): enforce request authority and semantic fidelity` earlier on this branch. **P0 must decide** whether that freeze baseline is stale or the change is genuinely out of allowlist |

  **Runner caveat — do not "verify" these in the container.** The same six files fail *worse* there
  (**33 failed**), because these tests shell out to git and `/app` is not a git repo. Git/freeze-aware and
  DB-aware tests belong on the **host venv**; the container remains fine for ordinary application tests.
  Per `CLAUDE.md`, master was 26 tests red for three days unnoticed — there is no CI here.

## Drift log

- 2026-08-21: Architecture freeze landed as `49c5a494` on master before this plan; feature branch `feat/complete-or-abstain-t4-ux` carries prior auth/COE/SPL/UI commits plus this plan. Do not re-amend architecture.md here.
- 2026-08-21 (rev 3, pre-LOOP gap closure): (a) **P6.1 added** — workflow control vocabulary must never present as security containment; rev 2 had asserted only `BLOCKED` was real, which was **half wrong**: `BLOCKED` is the status and `BLOCK` is the `SufficiencyNextAction`, and `_recommended_next_action` leaks it verbatim to the analyst. Remapping `investigation_status` alone does not close it. (b) **P2 T4-failure negative made REQUIRED** (unavailable / timeout / invalid response → fail closed at semantic authority; five explicit must-hold clauses) plus scenario **L**. (c) **P2 literal-machinery wording corrected** — rev 2 over-committed to `spl/request_authority.py` as the literal authority; now a generality audit across all Final-RQC families, with reuse-directly vs extract-to-shared-seam branches. (d) Scenario **M** added. (e) **Governance runner resolved MAC-FIRST** via gitignored host venv; remaining `AI_SOC_GITHUB_SKILL_CLONE_ROOT` prerequisite recorded as an operator decision rather than silently relocating P7 to COE.
- 2026-08-21 (rev 2, pre-execution review): corrected before any code was written — (a) every backend Verify command was unrunnable on this Mac (no host pytest) → switched to the container form and added a toolchain section; (b) P7's governance script is blocked on both host and container → P0 now owns the runner decision; (c) P6 named a non-existent token `BLOCK` (actual: `BLOCKED`/`blocked`) and risked editing a governed `Literal` → rescoped to presentation-label mapping; (d) P2's "T4 must not commit those fields" contradicted the existing `SemanticT4Proposal`, which already carries `required_capabilities` → clarified as *recompute, do not delete*, per frozen §11; (e) P3 audited 3 seams but the blocked posture is also decided in `evidence/final_evidence_gate.py` → added as seam 4; (f) P2 now points at existing literal machinery (`request_authority.py`, `user_constraint_bindings.py`) instead of implying a new parallel structure.
- Separate agentic investigation production plan remains independent; this plan owns understanding authority + response/UI applicability, not envelope/PlanDelta feature buildout.
