# ATLAS Data Staging

Use this directory for operator-supplied MITRE ATLAS Navigator layer JSON files.

## Raw input (no edits)

Place pasted/downloaded source files in:

- `docs/threat-intel/atlas/raw/`

Canonical staged filenames (source-of-truth, already present):

- `ATLAS_Matrix.json`
- `ATLAS_Case_Study_Frequency.json`

## Review reports (pre-normalization)

Duplicate/multi-tactic review artifacts go in:

- `docs/threat-intel/atlas/reports/`

## Normalized output

Generated artifacts go in:

- `docs/threat-intel/atlas/normalized/`

Required process:

1. Preserve raw file bytes exactly.
2. Run duplicate/multi-tactic check on `techniqueID`.
3. Review duplicate report (`reports/`).
4. Normalize only after approval.
