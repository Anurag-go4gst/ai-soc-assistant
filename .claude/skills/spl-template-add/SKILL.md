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
3. **Regenerate derived artifacts — THREE of them, in dependency order** (do NOT hand-edit):
   ```bash
   cd /var/www/ai-soc-assistant
   PYTHONPATH=backend:. python3 scripts/build_soc_capability_crosswalk.py   # 1st
   PYTHONPATH=backend:. python3 scripts/build_soc_validation_sheets.py      # 2nd — reads the crosswalk
   PYTHONPATH=backend:. python3 scripts/build_row_authority_report.py --check --warn-eval-drift \
     || PYTHONPATH=backend:. python3 scripts/build_row_authority_report.py --refresh   # 3rd
   ```
   Then confirm all three gates, in the same order:
   ```bash
   PYTHONPATH=backend:. python3 scripts/build_soc_capability_crosswalk.py --check
   PYTHONPATH=backend:. python3 scripts/build_soc_validation_sheets.py --check
   PYTHONPATH=backend:. python3 scripts/build_row_authority_report.py --check
   ```

   **Order matters, and `--check` will lie if you get it wrong.** `--check` compares an
   artifact against what its generator emits *right now* — not against current inputs. Adding
   one template and regenerating only the sheets gives a green sheets `--check` while the
   sheets were built from a stale crosswalk; governance then fails on the crosswalk, you fix
   that, and governance fails on the sheets again. Chain:

   ```
   catalog.json / templates.json
       -> docs/evals/soc_capability_crosswalk.json   (governance --check)
       -> docs/validation/*.json  (10 sheets)        (governance --check)
       -> docs/evals/row_authority_report.json/.md   (pytest test_row_authority_report)
   ```

   `row_authority_report` has its own rules in `docs/evals/ARTIFACT_REFRESH_POLICY.md` —
   run `--check --warn-eval-drift` before `--refresh` so unrelated eval drift is not swept in.
   Its documented "commit when" includes "catalogue authority inputs changed", which adding a
   template is.
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
templates.json valid + siblings intact + **all three** derived artifacts regenerated in order
(crosswalk, sheets, row-authority report; every `--check` clean) + relevance eval clean +
protected-manifest hashes updated for `templates.json`/`catalog.json` if either changed +
governance regression PASS. Commit templates.json, catalog.json, the regenerated artifacts and
the manifest together, one scoped commit.

### Slot gotcha (costs a wrong "fix" if missed)
Templates carry `<auth_index>` / `<auth_sourcetype>` placeholders **by design**. Validating the
raw `spl_text` returns `disallowed_index` / `disallowed_sourcetype` — that is expected, and an
existing sibling fails the same way. Validation happens after `graph_node_spl_source_resolve`
fills the slots. Validate the **slot-resolved** form; do not hardcode a concrete index to make
the validator happy, or you break the source-profile mechanism.
