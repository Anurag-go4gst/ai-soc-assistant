# ATLAS Data Staging

Use this directory for operator-supplied MITRE ATLAS Navigator layer JSON files.

## Raw input (no edits)

Place pasted/downloaded source files in:

- `docs/threat-intel/atlas/raw/`

Canonical staged filenames (source-of-truth, already present):

- `ATLAS_Matrix.json`
- `ATLAS_Case_Study_Frequency.json`
- `atlas_nodes_2026_04.csv` — flat node export (techniques, tactics, case studies, mitigations)

### `atlas_nodes_2026_04.csv` provenance

| Field | Value |
|-------|-------|
| Source URL | `https://raw.githubusercontent.com/mitre-atlas/atlas-knowledge-base-agent/main/data/datasets/atlas-nodes-04-2026-with-hashtags-and-embedding-text.csv` |
| MITRE case | 26-1336 |
| Pull date | 2026-07-06 |
| SHA-256 | `66eb5d2178df8a09ac4d90267fc44f3e5446f62457a771732f18742e538b8408` |

Never edit file bytes after staging. Langflow/Chroma app from the source repo is **not** adopted — only this flat CSV.

## Adding a new ATLAS↔ATT&CK↔template entry

1. Append one object to `entries` in `backend/app/knowledge/atlas_attack_crosswalk.json` (`attack_technique_ref`, `template_ids`, `strength`, `reasoning`, optional `suggested_remediation`).
2. Run `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_atlas_attack_crosswalk.py -q` — `test_all_hinted_template_ids_exist_in_registry` catches typos.

No Python code change is required for data-only additions.

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
