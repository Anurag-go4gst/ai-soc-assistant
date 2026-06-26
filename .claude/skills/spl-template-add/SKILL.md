---
name: spl-template-add
description: Add or edit a governed SPL template in backend/app/spl/templates.json safely — writing validator-clean SPL, regenerating derived sheets, and running the staleness/governance gates. Use when the user wants to add, edit, or promote an SPL template, a use-case query, or asks about templates.json. Triggers on "add SPL template", "new template", "edit templates.json", /spl-template-add.
---

# spl-template-add

Add/edit a governed SPL template without tripping the deterministic validator or leaving derived artifacts stale. The template registry is authority for in-catalogue SPL — EC and live both source from it via `_scoped_template_spl`, so a bad edit ships everywhere.

**File:** `backend/app/spl/templates.json` (dict keyed by `template_id`; 29 entries). Each entry: `template_id`, `status` (`active`/review-only), `use_case_id`, `required_entities`, `default_time_window`, `spl_text`, `returned_fields`, `validation_rules` (`allowed_indexes`/`allowed_sourcetypes`...).

## Validator gotcha (read before writing spl_text)

`validate_spl` (`backend/app/safeguards/spl_validator.py`) **splits the query on `|`** and reads each segment as a command. Consequences:
- **No regex alternation inside `match()`/`rex` that contains `|`** — a `|` in a regex is read as a pipe → a phantom command → rejected. Use base-search `OR` terms or `eval`+`case` instead.
- Every command must be in the allowlist (`SPL_ALLOWED_COMMANDS`); blocked commands (`SPL_BLOCKED_COMMANDS`, anything generative/write/admin/SAIA) reject.
- Index/sourcetype must be in `.env` `SPL_ALLOWED_INDEXES`/`SPL_ALLOWED_SOURCETYPES` AND the template's own `validation_rules`. Eval-vs-live drift here breaks live while evals pass — keep `.env` aligned.
- Keep `execution_eligible` / executability OFF. Candidate/template SPL is never executable; MCP exec flags stay false.

## Procedure

1. **Write the entry.** Match an existing sibling's shape (e.g. `auth_failed_login_spike`). Reuse an existing use-case family before inventing one. Include `returned_fields` and `validation_rules`.
2. **Restore timestamp-only siblings.** Editing one template can perturb the 9 timestamp-only sibling entries — verify they are unchanged after your edit (diff `templates.json`; only your intended entry should differ beyond timestamps).
3. **Regenerate derived sheets** (do NOT hand-edit them):
   ```bash
   cd /var/www/ai-soc-assistant
   PYTHONPATH=backend:. python3 scripts/build_soc_validation_sheets.py
   ```
   This refreshes `docs/validation/spl_template_review_sheet.json` and related sheets. Then confirm the staleness gate passes:
   ```bash
   PYTHONPATH=backend:. python3 scripts/build_soc_validation_sheets.py --check
   ```
4. **Validate the SPL deterministically** — run the relevance/validator evals:
   ```bash
   PYTHONPATH=backend:. python3 scripts/eval_spl_relevance.py --check
   ```
5. **Governance gate** (must be green before commit):
   ```bash
   ./scripts/run_stage3_governance_regression.sh
   ```
   Expected: backend pytest 0 failed, harness 6/6, all `--check` gates exit 0. Also run the SOC validation pytest if iterating fast: `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_soc_validation_package_phase10.py -q`.
6. **EC parity.** If the template backs an Experience Center scenario, EC follows automatically via `_scoped_template_spl(template_id, host=)` — do not hardcode SPL in `app/demo/scenarios.py`.

## Done when
templates.json valid + siblings intact + sheets regenerated (`--check` clean) + relevance eval clean + governance regression PASS. Commit templates.json and the regenerated sheets together, one scoped commit.
