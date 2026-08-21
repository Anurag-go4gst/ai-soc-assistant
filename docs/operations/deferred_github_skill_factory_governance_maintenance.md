# Deferred: GitHub Skill Factory governance-gate maintenance

**Status:** deferred — **do not implement inside**
`plans/2026-08-21_1937_understanding-authority-and-response-ux.md`.
**Raised:** 2026-08-21, during P0 of that plan.
**Owner:** governance/tooling maintenance, not the understanding-authority track.

## Symptom

`./scripts/run_stage3_governance_regression.sh` exits **1 at its first step** on macOS:

```text
GitHub skill clone root not found: /private/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills
REGRESSION FAILED: github discovery index stale
```

The same cause fails
`backend/app/tests/test_github_skill_expansion_factory_baseline.py::test_factory_generators_check_against_committed_artifacts`
(the test shells out to the same three `--check` scripts).

## Root cause (measured, not inferred)

```text
docs/skills/github_skill_discovery_index.json
  clone_root_used = "/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills"
  generated_at    = 2026-06-11T10:33:35+00:00, 754 skills, no upstream SHA recorded

scripts/github_skill_factory_lib.py::resolve_clone_root  → Path(...).resolve()
  macOS: /tmp is a symlink to /private/tmp  →  "/private/tmp/ai-soc-references/..."

scripts/build_github_skill_discovery_index.py::_check_payload (lines 173-176)
  normalizes ONLY generated_at
  → clone_root_used compared verbatim: "/private/tmp/..." != "/tmp/..."  → "stale"
```

Two independent defects:

1. **A machine-specific absolute path is treated as semantic artifact content.**
   `clone_root_used` records where the generator happened to run, then the staleness
   check compares it byte-for-byte. The artifact is therefore not portable across
   hosts, and **no** clone path can satisfy the gate on macOS.
2. **The external source is unpinned.** No branch, tag, or commit is fixed anywhere
   (`plans/AI_SOC_MASTER_PLAN.md:50` documents a plain default-branch `git clone`), and
   no upstream SHA is stored in the artifact. Even on Linux, a moved upstream reports
   "stale" because *upstream* changed, not because our artifacts drifted — and
   regenerating would rewrite 754 committed rows from an unpinned source.

Scope: only the discovery index embeds a clone path. `github_skill_triage_scores.json`
and `proposed_use_cases_from_github.json` do not, so governance steps 2–3 are unaffected.

## Not a runtime dependency

Runtime reads the **committed** JSON artifacts via
`backend/app/knowledge/mapping_exports.py:337-339`. It never reads the clone. The clone
is a regeneration/staleness-gate dependency only, so this limitation does not affect
application behaviour.

## Proposed maintenance (deferred)

1. **Pin the external source SHA** — record the upstream commit in the artifact and have
   the generators check against that pin, so "stale" means our artifacts drifted rather
   than upstream moved.
2. **Stop treating `clone_root_used` as semantic content** — either drop it from the
   compared payload, normalize it in `_check_payload` the way `generated_at` already is,
   or store it as non-semantic provenance outside the comparison.

Both are changes to the governance generators and require their own review. Neither is a
correctness fix to application code.

## Current disposition

Classified **`KNOWN_MACOS_GOVERNANCE_ENV_LIMITATION`**. Explicitly **not** worked around:
no clone created, no vendoring, no fake `clone_root_used`, no regeneration of the 754
committed rows, no governance-script edit, and the failure is not hidden or xfailed.

**Release gate:** before P8 is declared release-ready, governance step 1 must run on
**Linux** (VPS or COE) against the **exact same candidate Git SHA**, and the result
recorded. That gate is repository/governance validation and does **not** require live LLM
or MCP.
