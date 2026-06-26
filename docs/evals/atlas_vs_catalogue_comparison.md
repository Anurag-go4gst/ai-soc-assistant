# ATLAS raw vs catalogue/105 MITRE findings — comparison

**Date:** 2026-06-16  
**Inputs:** `docs/threat-intel/atlas/raw/ATLAS_Matrix.json` (+ Case_Study_Frequency), `docs/evals/out/llm_mitre_catalogue_audit.json`  
**Method:** offline deterministic, no LLM.

## 1. Taxonomy overlap

- ATLAS rows: **185**, distinct AML technique IDs: **170**.
- Our audit touched **112** enterprise ATT&CK IDs.
- **Enterprise↔ATLAS direct ID overlap: 0** (none — separate taxonomies, as expected).
- ATLAS is the AI/ML-threat matrix (AML.Txxxx); our catalogue is enterprise ATT&CK (Txxxx). They do not share IDs — ATLAS is a **net-new coverage domain**, not a validation set for our enterprise expansion candidates.

## 2. Duplicate techniqueID across tactics (plan E2 gate)

- 185 rows collapse to 170 IDs → **14 techniques appear under multiple tactics** (do not collapse before review). Examples:
  - `AML.T0012`: initial-access, privilege-escalation
  - `AML.T0015`: defense-evasion, impact, initial-access
  - `AML.T0018`: ai-attack-staging, persistence
  - `AML.T0018.000`: ai-attack-staging, persistence
  - `AML.T0018.001`: ai-attack-staging, persistence
  - `AML.T0018.002`: ai-attack-staging, persistence
  - `AML.T0020`: persistence, resource-development
  - `AML.T0052`: initial-access, lateral-movement

## 3. Coverage gap — AI-only tactics (no enterprise SOC coverage)

| ATLAS tactic | techniques | case-study freq |
|---|---|---|
| **ai-attack-staging** | 17 | 36 |
| **ai-model-access** | 4 | 25 |

These tactics (AI model access, AI attack staging) have **zero coverage** in our 105/catalogue and zero overlap with the LLM expansion candidates — the AI/LLM/MCP-threat gap for T2 guided-hunt and the ATLAS workstream.

## 4. Shared-name tactics (parallel to our SOC coverage)

| ATLAS tactic | techniques | case-study freq |
|---|---|---|
| resource-development | 26 | 90 |
| impact | 19 | 54 |
| execution | 13 | 48 |
| defense-evasion | 16 | 39 |
| initial-access | 15 | 37 |
| reconnaissance | 12 | 24 |
| persistence | 14 | 19 |
| discovery | 16 | 18 |
| exfiltration | 9 | 18 |
| privilege-escalation | 4 | 17 |
| credential-access | 6 | 14 |
| collection | 6 | 11 |
| command-and-control | 3 | 5 |
| lateral-movement | 5 | 3 |

Where ATLAS reuses enterprise tactic names, AI attacks parallel our SOC detections (e.g. credential-access, exfiltration, C2) — candidate cross-domain links per plan §C3b.

## 5. Top ATLAS techniques by real-world case-study frequency

| AML technique | score | tactic(s) |
|---|---|---|
| AML.T0065 | 20 | resource-development |
| AML.T0047 | 13 | ai-model-access |
| AML.T0051.001 | 13 | execution |
| AML.T0048.003 | 12 | impact |
| AML.T0048.000 | 10 | impact |
| AML.T0051.000 | 10 | execution |
| AML.T0017 | 9 | resource-development |
| AML.T0053 | 9 | execution, privilege-escalation |
| AML.T0025 | 8 | exfiltration |
| AML.T0000 | 8 | reconnaissance |
| AML.T0055 | 7 | credential-access |
| AML.T0040 | 7 | ai-model-access |
| AML.T0068 | 7 | defense-evasion |
| AML.T0042 | 7 | ai-attack-staging |
| AML.T0079 | 7 | resource-development |

## 6. Conclusion

- ATLAS does **not** validate our enterprise expansion candidates (no ID overlap); the full enterprise ATT&CK bundle is still required for that (§5 of the MITRE audit report).
- ATLAS is a **separate coverage domain**: AI/LLM/MCP threats absent from our catalogue. Highest-frequency AML techniques + AI-only tactics are the priority for ATLAS intake and T2 AI-threat guided-hunt grounding.
- Duplicate/multi-tactic gate satisfied: review before any normalization (plan E2/E3); raw preserved unmodified.
