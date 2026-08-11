---
name: reference-probe-audit
description: Run the 10-probe reference-knowledge contract (P1–P6 positive, N1–N4 negative) through the in-process /chat pipeline and diff routes/shapes/panels against the frozen baseline. Use when executing Phase 3 of plans/2026-07-04_1736 (items 16, 18, 19, 22), after any change to answer_shape_router / routing floors / MITRE-CVE-ATLAS handling, or when the user says "run the probes", "probe audit", or /reference-probe-audit.
---

# reference-probe-audit — ask the question, check its path

The acceptance contract for the canonical reference-knowledge path is behavioral: ten fixed questions with expected routes. Any routing/shape/guard change must be judged against ALL ten — a fix that greens P1 while flipping N1 is a regression, not a fix.

## The probe set (canonical copy: `backend/app/tests/fixtures/reference_knowledge/probes.json`; if it does not exist yet, item 16 creates it with exactly these)

| ID | Question | Expected (post-Phase-3) |
|----|----------|------------------------|
| P1 | What MITRE ATLAS techniques apply to prompt injection against our LLM agent using MCP tools? | `reference_taxonomy` → knowledge_recall/reference_knowledge, AML IDs + names, no clarification |
| P2 | Using the onboarded MITRE ATLAS data, list the top AML techniques relevant to LLM prompt injection and MCP-agent abuse. This is a taxonomy question, not an alert mapping. | same as P1 |
| P3 | What is T1110.003 and how do we detect it? | reference_taxonomy; ATT&CK facts + template ref if any |
| P4 | Explain CVE-2024-3400. Are we affected? | reference_taxonomy; CVE facts + honest env-exposure gap |
| P5 | Map this alert to MITRE: 5 failed logins then success on DC-01 | alert-mapping path, byte-identical to baseline |
| P6 | Give me SPL to detect brute force | spl_generation, byte-identical to baseline |
| N1 | Search our logs for CVE-2024-3400 exploitation attempts | hunt/SPL — never reference panel |
| N2 | Was T1110 activity seen on our network last week? | live investigation — never reference panel |
| N3 | Map alert 4625-burst on DC-01 to MITRE | alert mapping — never reference panel |
| N4 | Update our ATLAS coverage dashboard | meta-ops — never reference panel |

## How to run

1. Preferred from the repository host: `DATABASE_URL=postgresql://ai_soc:ai_soc_dev_password@127.0.0.1:5434/ai_soc_assistant TELEMETRY_MODE=none PYTHONPATH=backend:. python3 scripts/audit_reference_probes.py --check` (created by item 16). This is an in-process pipeline run with live LLM and MCP work disabled, but canonical audit-critical persistence remains enabled and fail-closed. Do not replace the database URL with an empty value or otherwise bypass persistence to make the audit run.
   `--check` is the default and writes nothing. A drift exit (`1`) is a valid completed comparison, so non-mutation verification must capture and compare the baseline hash after the command regardless of that exit; see A0 in `plans/2026-08-08_1824_architecture-review-corrective-actions.md` for the exact wrapper. Use `--out <path>` for a scratch report. **Only** `--update-baseline` rewrites
   `docs/evals/reference_knowledge_baseline.md`, and that is a deliberate, separately-justified act — never part of a verification run.
2. If the script does not exist yet, run each probe in-process (pattern used by existing eval scripts): build the chat request, call the pipeline entry `process_chat_message`/equivalent used by `app/api` chat route, capture per probe: `selected_skill`, `request_mode`, `answer_mode`, `match_path`, MITRE/ATLAS panel status, clarification/human_review reason.
3. Compare against `docs/evals/reference_knowledge_baseline.md` (item 16 baseline). Report as a 10-row table: probe | expected | actual | PASS/DRIFT.

## Rules

- **Never adjust a probe question to make it pass.** Probes are frozen; only expected-values change, and only via a plan Drift-log entry.
- P5/P6/N1–N4 are non-regression: any drift from baseline = stop, investigate the guard/floor interaction before proceeding.
- Quality contracts (item 22) ride on top: answer must contain ≥1 resolved ID with name, zero hallucinated IDs (every T/AML.T/CVE token in the answer must exist in that turn's resolver output), non-empty citations, no clarification demand on P1–P4.
- Record the full table in the plan item's Evidence field, not just "passed".
