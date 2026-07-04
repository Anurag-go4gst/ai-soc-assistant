# Hybrid intent baseline probes (2026-07-04)

Live `/chat` via `scripts/ask_chat.sh` (HTTP `127.0.0.1:8010`). Artifacts:

- `ask_chat_probes.txt` — full responses
- `baseline_summary.json` — extracted authority fields + failure nodes

## Q1 — process-aware OT + discovery + review-only hunt (do not run)

**Query:** AGC setpoint / frequency band; list Splunk indexes or metadata; prepare review-only hunt; do not run SPL until approve.

| Field | Observed | Expected |
|---|---|---|
| `match_path` | `out_of_registry` | `out_of_registry` |
| `selected_skill` | `spl_generation` | guided / hybrid advisory (process-aware OT) |
| `route_adjudication.authority_source` | `explicit_run_spl_hil_gate` | hybrid/guided advisory authority |
| `path_type` | `spl_review` | guided / hybrid investigation |
| `request_mode` | `clarification` | live/hybrid or guided schedule with discovery |
| `evidence_plan.needs_spl` | `false` | review-only SPL allowed / planned |
| `evidence_plan.discovery_allowed` | null | `true` (index/metadata ask) |
| `execution.status` | `requires_human_review` | no `splunk_run_query` (OK) |
| `human_review.reason` | `explicit_run_spl_requires_hil` | not command-run HIL |

**Failure nodes (primary → secondary):**

1. **Route adjudication** — `explicit_run_spl_hil_gate` fires because the phrase “Do not **run the SPL** until I approve” matches `explicit_run_spl` (`\brun the spl\b`), so a **negated** run request is treated as command-run intent. Hybrid process-aware OT never wins.
2. **Evidence planning** — `needs_spl=false`, `discovery_allowed` unset; index/metadata discovery not granted.
3. **Dispatch** — `request_mode=clarification` (no hybrid advisory schedule).
4. **Answer surface** — `answer_mode=clarification`, empty message, HIL card only.

Trace: `3a31576f-0435-4f4d-bf34-362a84d9eb48`

## Q2 — pasted SPL validate/optimize, ask before run (command-shaped)

**Query:** Pasted `search index=pgcil_soc …`; validate and optimize; list missing source profile metadata; ask before running.

| Field | Observed | Expected |
|---|---|---|
| `match_path` | `out_of_registry` | `out_of_registry` |
| `selected_skill` | `guided_investigation` | `spl_generation` (command spine) |
| `route_adjudication.authority_source` | `guided_investigation_rescue` | command intent / `spl_generation` |
| `path_type` | `guided_investigation` | `spl_review` |
| `request_mode` | `clarification` | `spl_and_run` / `spl_authoring` |
| `candidate_spl` | absent | user-provided SPL ingested |
| `discovery_allowed` | `true` | OK for metadata list |
| `needs_spl` | `false` | `true` |
| MCP run | skipped | HIL before run only (danger plan) |

**Failure nodes:**

1. **Route adjudication** — command-shaped pasted SPL **stolen by** `guided_investigation_rescue` (OOR guided floor). Owned primarily by danger-tiered MCP command plan.
2. **Intent / dispatch** — no `spl_generation_and_run` / `spl_authoring`; SPL chain not scheduled.
3. **workflow_spl** — no candidate from paste.

Trace: `ca71c2d0-36c2-48bf-8471-4e24260ab246`

## Implications for this plan (items 2–4)

- Hybrid advisory must **not** lose to false-positive `explicit_run_spl` on “do not run / until I approve”.
- Command modes (danger plan) must short-circuit guided rescue for Q2-style pastes; this plan must not add hybrid rules that steal Q2.
- Process-aware OT + discovery needs must reach evidence planning (`discovery_allowed`, review-only SPL), not clarification-only packaging.
