# ATLAS Data Staging

Use this directory for operator-supplied MITRE ATLAS Navigator layer JSON files.

## Raw input (no edits)

Place pasted/downloaded source files in:

- `docs/threat-intel/atlas/raw/`

Suggested filenames:

- `atlas_matrix_raw.json`
- `atlas_case_study_frequency_raw.json`

## Normalized output

Generated artifacts go in:

- `docs/threat-intel/atlas/normalized/`

Required process:

1. Preserve raw file bytes exactly.
2. Run duplicate/multi-tactic check on `techniqueID`.
3. Review duplicate report.
4. Normalize only after approval.
