# blind_holdout_v1 — specification & coverage matrix

Status: **spec frozen; question text + labels NOT authored** (independent-reviewer task).
Owner of authoring: an independent reviewer, NOT the implementer.
Plan reference: §4.1 (corpus lifecycle), §4.2 (per-question schema), §4.3 (validation).

## Purpose

`blind_holdout_v1` is the sealed benchmark used to judge a release candidate. It is
authored **after** the P2-B prompts and routing are frozen, by a reviewer who did not
implement them, and is never seen during implementation. This document freezes only
the *specification and coverage matrix* now; the reviewer authors and seals the
question text and expert labels later.

## Hard rules (do not violate)

1. **Independence**: authored blind to `discovery_v1`, `labeled_release_v1`, the 105
   catalogue, the Cisco 50, and the PowerGrid banks. Author from SOC-analyst intent,
   not from existing question wording.
2. **Seal before reveal**: freeze question text + SHA-256 hashes + labels before any
   implementer sees them. Implementers see them only once the release candidate is
   fixed. Any post-reveal tuning ⇒ new holdout version (`blind_holdout_v2`).
3. **Dedup is post-authoring audit only**: semantic dedup against existing banks may
   *reject* an overlapping row but must not rewrite a question toward catalogue
   wording.
4. **Schema**: every row uses the full §4.2 schema (`scripts/validate_release_bank.py`
   must pass), including expert `must_include` / `must_not_claim`.

## Coverage matrix (minimum counts, 40-row holdout)

| Dimension | Required cells |
|---|---|
| Tier | T1 ≥ 18, T2 ≥ 14, boundary ≥ 6, plus ≥ 2 T0 in-catalogue control |
| Answer shape | ≥ 8 distinct (`hunt`, `process_aware_ot`, `regulatory_knowledge`, `ir_containment_advisory`, `source_health`, `baselining`, `ti_advisory_mapping`, `knowledge_explanation`, …) |
| Acceptable skill | each of the 5 live skills appears as the expected route on ≥ 3 rows |
| Evidence legs | ≥ 8 multi-leg rows (≥ 2 domains), explicitly labelled |
| Artifact | `spl` ≥ 8, `mitre` ≥ 4, `cve` ≥ 4, `rag` ≥ 6, `mcp_plan` ≥ 2, `guidance` ≥ 6 |
| Failure mode | ≥ 4 honest-gap rows (answer must admit insufficient evidence) |
| Safety | ≥ 6 boundary rows: unsafe execution, out-of-scope, destructive enforcement, data-exfil request, prompt-injection-in-RAG, mass-target |
| HIL | ≥ 3 `execution_confirmation`, ≥ 4 `review` |
| Latency class | ≥ 10 `deterministic`, rest `llm_optional`/`llm_required` |

## Authoring & validation workflow

1. Reviewer authors 40 rows blind, fills the full §4.2 schema incl. expert fields.
2. Run `scripts/validate_release_bank.py` against the holdout file (structural gate).
3. Two-reviewer correctness pass + one adjudication (plan §4.3).
4. Seal: write `blind_holdout_v1.json` + a sibling `.sha256` manifest; commit the
   manifest only until reveal.
5. Five-row canary (auth, trace read, health, scoring, redaction) before any full run.

## Scoring

Score with `scripts/score_release_bank.py` (four layers, §4.4). The first attempt is
the reliability score; retries are resilience only. No single heuristic is a release
pass/fail; layer-3 human review is authoritative, layer-4 LLM judge only after
calibration against layer-3 labels.

## Residual (explicitly out of implementer scope)

- Sealed question text + expert labels (independent reviewer).
- The two-reviewer correctness/adjudication pass.
- The live release-candidate run that consumes this holdout.
