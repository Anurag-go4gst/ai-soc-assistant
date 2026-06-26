# MITRE Catalogue Audit — Disposition Worklist

Source: `docs/evals/out/llm_mitre_catalogue_audit.json` (147 rows; LLM mapper vs deterministic permitted/candidate/blocked).
Report: `docs/evals/llm_mitre_catalogue_audit_coe_report.md`. Re-run: `scripts/llm_mitre_catalogue_audit.py --full`.

Buckets: agree 80 | gap 30 | contradiction 11 | over_map 3 | llm_empty 23.

This worklist records the **reviewed** disposition. Naive read ("promote all 30 gaps") is wrong: ~half the
gap rows are LLM over-attribution onto SOC meta-operations or wrong-domain techniques. Only genuine
candidate-tier fits were promoted.

**Standard label (applies to every promotion / anchor in this doc):**

> These mappings are acceptable only as **candidate ATT&CK anchors** for routing and investigation. They must
> NOT be emitted as **confirmed MITRE techniques** unless downstream evidence proves the adversary behavior
> required by the specific ATT&CK technique definition. Correct label = `candidate_mitre_anchors` /
> `possible_attack_relevance`; incorrect label = `confirmed_mitre_technique`. ATT&CK is a knowledge base of
> adversary *behavior* (the "how") — not a tag for generic SOC analytics/ranking questions.

---

## Bucket 1 — Gaps (30 rows) — DONE (reviewed, partial promote)

Promotions land as **candidate** tier (not `permitted`/supported) in `mitre_registry.candidate` +
top-level `mitre_candidates` of the two enrichment drafts. Candidate ⇒ requires evidence to confirm; MCP
execution unchanged. Provenance stamped in `mitre_registry.candidate_provenance`.

### Promoted (14) — technique genuinely fits (candidate tier)

| Row | Added (candidate) | Rationale |
|-----|-------------------|-----------|
| q0.q046, q0.q047, q0.q062 | T1110 | Parent of already-permitted T1110.001; brute-force questions |
| q0.q060 | T1110 | Parent; permits T1078+T1110.001 |
| q0.q089 | T1110 | Brute-force parent. **(COE correction: dropped T1110.003 — MFA failures ≠ password spray; spray needs many-accounts pattern. T1621 MFA-fatigue would fit but is MISSING from bundle → WS-G expansion candidate.)** |
| q0.q050, q0.q063, q0.q083 | T1059.001 | PowerShell sub of permitted T1059; questions name shell/script exec |
| q0.q021, q0.q028, q0.q040 | T1071 | Outbound/C2-style comms hunts (foreign IP / p2p / rare country) |
| auth_account_lockout_trend | T1110 | Brute-force parent |
| auth_failed_login_spike | T1110 | Brute-force parent. **(COE correction: dropped T1110.003 — failed-login volume ≠ spray; T1110.003 needs spray pattern, not volume.)** |
| net_new_outbound_destination | T1071 | New outbound destination = C2 candidate |

**COE correction — removed from promotions (re-classified no-map):**

| Row | Was | Now | Why |
|-----|-----|-----|-----|
| edr_malware_alert_summary | T1059.001 | **no-map** | "Malware summary" alone does not prove PowerShell. T1059.001 = PowerShell command/scripting use. Add only if EDR alert explicitly names PowerShell/script execution. |

### Rejected (15) — no-action, our no-map / block posture is correct

| Row(s) | LLM proposed | Why rejected |
|--------|--------------|--------------|
| soc_compare_past_incidents, soc_create_investigation_note, soc_draft_ticket, soc_map_alert_mitre, soc_optimize_spl, soc_show_sop, soc_summarize_alert_evidence, soc_generate_spl, soc_recommend_next_pivots | T1566.001/T1059.001/T1110*/T1071/T1078/T1566.002 | SOC **meta-operations** (knowledge_recall / SPL authoring / ticketing). No MITRE attribution. LLM hallucinated technique onto the tool, not an alert. Confirms trace-only/no-map. |
| q0.q051, q0.q057 | T1071 | Process/hash execution questions — T1071 is a **network** (app-layer C2) technique; wrong domain. |
| q0.q045 | T1059.001, T1566.001 | Generic "what happened for this notable" — binding specific techniques to an arbitrary notable is unsound. |
| auth_impossible_travel, net_vpn_login_anomaly | T1071 | Auth anomalies (T1078 territory), not app-layer C2. |
| ot_unexpected_command | T1059.001 | OT context; T1059.001 is Windows PowerShell — unlikely. |

---

## Bucket 4 — Over-map (3 rows) — DONE (candidate anchors valid with evidence; no change)

Not "confirmed correct." Our mapping is more specific/complete than the LLM and KEEPS as a **candidate
anchor** — valid only when downstream evidence proves the technique's required behavior.

| Row | We map | LLM | Verdict (candidate-only) |
|-----|--------|-----|--------------------------|
| q0.q092 | T1048 | T1078 only | Candidate, not confirmed. T1048 (Exfil Over Alt Protocol) needs exfiltration over an alternative protocol — large outbound transfer is suspicious, not proof. |
| q0.q093 | T1071.004 | T1059 only | Candidate, not confirmed. Correct anchor if suspicious DNS indicates C2/tunneling; not confirmed by "suspicious DNS" alone. |
| auth_success_after_failure | T1110.001 | T1078 only | Reasonable candidate; supported only if repeated guessing led to success. One failure → success = do not over-map. |

⚠️ Side-finding (not part of this disposition): **T1048 and T1071.004 are MISSING from
`mitre_attack_subset.json` bundle** though referenced in mappings (also T1621 for the q0.q089 MFA-fatigue
case). Real bundle-completeness gap — track under WS-G / bundle expansion (MITRE's own `mitreattack-python`
works ATT&CK STIX content for exactly this).

---

## Bucket 2 — Contradictions (11 rows, all T1078) — COE REVIEW (handed to user to verify)

Audit validated our T1078 **blocks** (no Valid-Accounts claim without identity evidence). Keep all blocks.
MITRE T1078 requires adversaries *using* valid accounts/credentials — not "user/account-shaped data."

**COE strict decision on the two judgment rows:**
- **q0.q086** (failed logins + privilege changes): **do NOT unblock T1078 by default.** Keep T1098 (Account
  Manipulation) + T1110.001 (Password Guessing). Add T1078 **only as candidate** if evidence shows successful
  use of a valid account after the failed attempts / privilege change.
- **q0.q096** (privileged actions from non-admin workstations): allow T1078 **only as candidate with
  evidence** — needs successful-auth/session evidence + account identity + abnormal-source-workstation context.
  Stronger than q086, never confirmed by the question alone.

**The confusion (all 11):** the 8B LLM attaches **T1078 (Valid Accounts)** reflexively to any user/account-shaped
question. We **block** T1078 — claiming valid-account abuse needs identity/auth evidence, not derivable from a
"which X has most Y" ranking. Common block set on most rows: T1003 (OS Credential Dumping), T1078 (Valid
Accounts), T1110.001 (Password Guessing), T1562.001 (Impair Defenses / Disable Tools) — the standard
don't-over-claim guard.

| Row | Question | Ours: permitted | Ours: candidate | Ours: blocked | LLM valid | Conflict | Verdict |
|-----|----------|-----------------|-----------------|---------------|-----------|----------|---------|
| q0.q001 | What incident or alert network events are high or critical right now? | — | — | T1003,T1078,T1110.001,T1562.001 | T1078, T1566.002 | T1078 | Generic triage. T1078 over-claim. Keep block. (T1566.002 gap ignorable — generic dashboard) |
| q0.q044 | Which rules are generating the most alerts? | — | — | T1003,T1078,T1110.001,T1562.001 | T1078 | T1078 | Rule-volume analytics, no account abuse. Keep block. |
| q0.q078 | Which systems had repeated malware detections? | — | — | T1003,T1078,T1110.001,T1562.001 | T1059, T1078 | T1078 | Malware count summary. T1078 unfounded. Keep block. |
| q0.q081 | Which users received and opened phishing attachments? | T1204, T1566.001 | — | T1003,T1078,T1110.001,T1562.001 | T1078, T1566.001 | T1078 | We already map T1566.001+T1204 (correct). Phishing ≠ valid-account abuse. Keep block. |
| q0.q084 | Which accounts have the most risk events? | — | — | T1003,T1078,T1110.001,T1562.001 | T1078 | T1078 | Risk-score ranking. Keep block. |
| **q0.q086** | Which users were involved in both failed logins and privilege changes? | T1098, T1110.001 | — | T1003,T1078,T1562.001 | T1078 | T1078 | **COE judgment.** We map T1098 (Account Manipulation)+T1110.001. Privilege-change correlation *may* justify T1078 **as candidate** with evidence. |
| q0.q090 | Which assets are generating the most notable events? | — | — | T1003,T1078,T1110.001,T1562.001 | T1078 | T1078 | Notable-volume ranking. Keep block. |
| **q0.q096** | Which users performed privileged actions from non-admin workstations? | T1098 | — | T1003,T1078,T1110.001,T1562.001 | T1078 | T1078 | **COE judgment.** Privileged-from-wrong-host = classic valid-account-abuse signal; T1078 **as candidate** may be warranted. |
| q0.q099 | Which detections involved the same user and host repeatedly? | — | — | T1003,T1078,T1110.001,T1562.001 | T1078 | T1078 | Correlation count. Keep block. |
| auth_mfa_failure_spike | Investigate MFA failure spike | — | T1110.001 | T1003,T1078,T1562.001 | T1078, T1110 | T1078 | MFA spike = brute-force (candidate T1110.001; T1110 promoted in Bucket 1). T1078 premature. Keep block. |
| net_repeated_critical_asset_connections | Repeated connection attempts to critical asset | — | — | T1003,T1078,T1110.001,T1562.001 | T1078, T1110 | T1078 | Network connection attempts ≠ account abuse. Keep block. |

**Recommendation:** keep all 11 T1078 blocks. Only q0.q086 + q0.q096 need a COE yes/no on "allow T1078 **as candidate** when
privileged-correlation evidence is present" — never as confirmed.

---

## Bucket 3 — Expansion candidates (97) — BLOCKED on WS-G

Validate via STIX (mitreattack-python offline resolver, not built — plan §15): drop deprecated
(T1043/T1086) + hallucinated → COE promote list. Implement with WS-G; this disposition will solve them
once WS-G resolver exists. **Will it solve them?** Yes — WS-G G3 (expansion validation) → G5 (write-back)
is the exact path; same candidate-tier write mechanism used here for Bucket 1.

---

## Bucket 5 — LLM empty (23) — DONE (no-action) — splits two ways

LLM returned no technique (not_applicable). Two sub-groups.

### 5a — True no-map (we ALSO map nothing). Full agreement, trace-only confirmed (14)

| Ref | Question |
|-----|----------|
| q0.q002 | Which source IPs generated the most outbound connections? |
| q0.q003 | Which destination IPs received the most connections? |
| q0.q020 | Which networks saw traffic to high-risk ports? |
| q0.q058 | Which users or hosts have the highest risk scores? |
| q0.q085 | Which assets have accumulated risk from multiple detections? |
| q0.q091 | Which alerts are still open and unresolved? |
| q0.q095 | Which sources stopped sending events recently? |
| q0.q100 | Which users triggered multiple different detections? |
| q0.q101 | Which devices are generating the most endpoint alerts? |
| q0.q103 | For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status? |
| q0.q104 | What is the full activity timeline for a given entity in the N hours before and after a detection? |
| q0.q105 | Has this entity, IP, domain, or notable been seen or investigated before, and prior disposition? |
| edr_isolation_recommendation | Recommend endpoint isolation |
| soc_explain_spl | Explain this SPL |

→ Analytics / lookup / asset-context / response / meta. No ATT&CK technique. **No action.**

### 5b — Divergence: LLM empty but WE map an anchor (9) — STRICT-MITRE caveat

These resolve in the registry as **candidate / needs_review status**, NOT `supported`/confirmed
(verified via `mitre_permitted_builder._deterministic_status`: T1078→candidate, the rest→needs_review;
only `T1110.001`+`auth_failed_login_spike` ever resolves `supported`). `mitre_permitted`-list membership =
"anchor allowed to surface for routing/investigation," not a confirmed technique label.

> **Disposition (replaces earlier "no action — our mapping is the more useful one"):**
> **No blocker if treated as candidate ATT&CK anchors for routing/investigation. NOT valid as confirmed
> MITRE technique labels unless downstream evidence confirms the behavior.** Correct label =
> `candidate_mitre_anchors` / `possible_attack_relevance`; incorrect label = `confirmed_mitre_technique`.

| Ref | Question | Anchor | Strict-MITRE verdict (candidate-only) |
|-----|----------|--------|----------------------------------------|
| q0.q004 | Which hosts contacted known malicious IPs today? | T1041, T1071 | Partially wrong **if confirmed**. T1071 only if traffic is app-layer C2. T1041 (Exfil Over C2) needs evidence of data theft over an existing C2 channel — not just known-bad comms. |
| q0.q010 | Which hosts are generating the most SMB traffic? | T1021.002 | Candidate only. SMB volume alone = analytics. T1021.002 needs SMB/admin-share use for remote interaction / lateral movement. |
| q0.q017 | Which hosts generated the most DNS queries? | T1071.004 | Candidate only. DNS volume ≠ DNS C2. Sub-technique needs adversary comms over DNS (commands/results embedded). |
| q0.q032 | Which hosts had both DNS and network anomalies? | T1071.004 | Candidate only. Stronger than plain count, still not confirmed without C2/tunneling behavior. |
| q0.q035 | Which hosts generated the largest DNS response volumes? | T1071.004 | Candidate only. Large responses suspicious, but correctness needs DNS-based C2/tunneling evidence, not volume. |
| q0.q059 | Which source IPs generated the most authentication failures today? | T1110.001 | Reasonable candidate (stronger anchor), still needs repeated/iterative guessing behavior per MITRE password-guessing def. |
| q0.q061 | Which users logged in from new countries today? | T1078 (permitted) | **Intended/defensible exception, candidate only.** New-country login is a stronger valid-account-abuse candidate than generic account ranking. But T1078 needs obtained/abused existing creds — geo anomaly alone is not proof. Resolves as **candidate** status (verified), not confirmed. |
| q0.q071 | Which accounts were disabled or re-enabled today? | T1098 | Reasonable candidate if event suggests adversary account manipulation (credential/permission changes preserving access). |
| q0.q088 | Which endpoints have multiple persistence indicators? | T1053, T1543, T1547 | Acceptable as **grouped persistence anchors** only if indicators are typed: scheduled task→T1053; service/system-process create/modify→T1543; boot/logon autorun→T1547. Prefer sub-techniques when the exact artifact is known. |

→ **No code action.** Status layer already enforces candidate/needs_review (not confirmed). Framing corrected above.
