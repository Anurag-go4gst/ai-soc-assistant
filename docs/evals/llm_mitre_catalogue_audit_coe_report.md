# LLM second-opinion audit of catalogue + 105 MITRE mappings — COE review

**Date:** 2026-06-16
**Tool:** `scripts/llm_mitre_catalogue_audit.py` (offline, NOT a runtime feature, NOT imported by `/chat`)
**Model:** Foundation-sec-1.1-8B-Instruct (local llama.cpp, `-c 4000`)
**Scope:** 105 questions + 42 use-cases = **147 rows**
**Authority:** deterministic mapping stays authority; LLM output is advisory review signal only.
**Raw data:** `docs/evals/out/llm_mitre_catalogue_audit.json`

## 1. Summary

| Verdict | Count | Meaning |
|---------|-------|---------|
| agree | 80 (54%) | LLM aligns with our mapping |
| in-bundle gap | 30 | LLM proposes a technique already in our 13-bundle that we don't carry on that row |
| **contradiction** | 11 | LLM proposes a technique we explicitly BLOCKED |
| over_map | 3 | We map a technique the LLM did not surface |
| llm_empty | 23 | LLM correctly returned nothing (lookup/health/analytics rows) |

Our local ATT&CK subset is only **13 techniques**; the LLM surfaced **97 distinct out-of-subset techniques** across 147 SOC questions — quantifying the "limited mapping" gap.

## 2. Contradictions — all 11 are T1078 (Valid Accounts)

Every contradiction is the same: LLM wants **T1078** on detection/notable/risk/phishing/MFA rows where our registry blocks it.

| Row | Question |
|-----|----------|
| q0.q001 | alerts high/critical right now |
| q0.q044 | rules generating most alerts |
| q0.q078 | repeated malware detections |
| q0.q081 | phishing attachments opened |
| q0.q084 | accounts with most risk events |
| q0.q086 | failed logins + privileged actions |
| q0.q090 | assets generating most notable events |
| q0.q096 | privileged actions from non-admin workstations |
| q0.q099 | same user+host repeatedly |
| uc:auth_mfa_failure_spike | MFA failure spike |
| uc:net_repeated_critical_asset_connections | repeated connections to critical asset |

**Assessment:** the LLM systematically over-attributes "Valid Accounts" whenever an account/auth noun appears, on questions that carry **no evidence** of valid-account abuse. Our T1078 block is **defensible and validated** by this pressure test. **COE recommendation: keep the blocks; no change.** (One judgment call: q0.q086 / q0.q096 — privileged-action correlation rows — COE may decide T1078 candidacy is warrantable *with* evidence preconditions.)

## 3. In-bundle gaps (30) — low-risk enrichment, IDs already vetted

Techniques already in our bundle that the LLM maps to rows we left unmapped:

| Technique | Rows | Note |
|-----------|------|------|
| T1110 Brute Force | 11 | strongest signal — failed-login/lockout/MFA rows |
| T1059.001 PowerShell | 10 | process-execution rows |
| T1071 App-Layer Protocol (C2) | 9 | beaconing/external-comm rows |
| T1566.001 Spearphishing Attachment | 7 | phishing rows |
| T1110.003 Password Spraying | 3 | |
| T1566.002 / T1059 / T1078 / T1110.001 | 1–2 each | |

**COE recommendation:** these are already-vetted IDs in our subset — safe to review row-by-row and promote where evidence preconditions hold. Highest value: T1110, T1059.001, T1071, T1566.001.

## 4. Expansion candidates (out-of-subset) — review before promoting

Top out-of-subset techniques the LLM proposes (by frequency across 147 rows):

| Technique | Freq | Plausibility |
|-----------|------|--------------|
| T1071.001 Web Protocols | 22 | solid (C2 over web) |
| **T1043** Commonly Used Port | 21 | ⚠️ **DEPRECATED** (merged into T1571) |
| T1082 System Information Discovery | 10 | solid |
| T1021 Remote Services | 10 | solid (lateral movement) |
| T1041 Exfil Over C2 | 9 | solid |
| T1071.004 DNS | 8 | solid (DNS C2/DGA rows) |
| T1036 Masquerading | 7 | solid |
| T1037 / T1105 / T1133 / T1132 / T1046 / T1095 | 4–6 | mostly solid |
| **T1086** PowerShell (old) | 3 | ⚠️ **DEPRECATED** (→ T1059.001) |

97 distinct IDs total. Mix of genuinely-relevant (T1071.004 DNS, T1021, T1041, T1046) and **deprecated/noise (T1043, T1086)** — proving these cannot be auto-trusted offline.

## 5. Hard limitation — needs full ATT&CK Enterprise bundle

We only hold a 13-technique local subset, so out-of-subset IDs **cannot be deterministically confirmed real-vs-deprecated-vs-hallucinated offline**. T1043 (21×) and T1086 (3×) being deprecated proves the risk. **Required before promoting any expansion candidate:** load the full ATT&CK Enterprise technique list as a validation set, then split expansion candidates into `real → promote-candidate` vs `deprecated/invalid → drop`.

## 6. Recommended COE decisions

1. **Keep all 11 T1078 blocks** — validated by the audit (LLM over-reach, not our error). Decide separately on the 2 privileged-correlation rows.
2. **Approve in-bundle gap review** (§3) — low risk, vetted IDs; promote where evidence preconditions hold.
3. **Approve full ATT&CK bundle load** (§5) before any out-of-subset promotion.
4. Next: compare expansion candidates against the operator-supplied ATLAS raw (`docs/threat-intel/atlas/raw/ATLAS_Matrix.json`) for AI/LLM/MCP-threat coverage, then a second LLM pass + manual review.

## 7. Provenance / reproduce

```bash
PYTHONPATH=backend:. python3 scripts/llm_mitre_catalogue_audit.py --full --kind both --write-report
```

LLM advisory only; deterministic authority unchanged; no runtime path touched.
