# Catalogue bind coverage/margin distribution (item 2)

Plan: `plans/2026-08-19_1130_catalogue-matching-coverage-and-margin.md`.
Matcher: production `match_use_cases` — `confidence` still decides; diagnostics are reported only.
Dump: `docs/evals/catalogue_bind_distribution_v1.json` via `scripts/eval_catalogue_bind_distribution.py`.

**No threshold is proposed.** This table exists so item 3 cannot pick one without a row here.

## What this corpus actually exercises

| corpus | bound at T2 | unbound at T2 |
|---|---|---|
| routing truth set (96) | **11** | **85** |
| 105 goldens | **14** | **91** |

A 105-based check that does not state “14 of 105 bind at T2” is measuring almost nothing. T1 exact-match already serves the other 91.

`bind_margin` is observed on **3 of 11** truth-set binds. One is negative. None sit in a 0.00–0.12 band. The earlier sweep where margins 0.00 / 0.06 / 0.12 were identical is the same fact: candidates rarely tie.

## Truth-set bind classes (current matcher, pre-cull)

After the negation fix, the original defect class is empty at T2:

| class | n | meaning |
|---|---|---|
| `no_bind` | 84 | including `rt.neg.001` (the zero-day). T2 no longer steals it; the live route still falls to the knowledge floor — items 3–5 / T4 are what move it, not a coverage floor. |
| `correct_bind` | 9 | bound skill ∈ `acceptable_skills` |
| `wrong_family` | 2 | `rt.alert.002` → `net_vpn_login_anomaly` on `vpn login`; `rt.know.002` → `soc_map_alert_mitre` on `mitre` |
| `missed_procedure` | 1 | `rt.neg.004` — label wants knowledge, nothing bound |
| `false_knowledge` | **0** | the `soc_show_sop` / “playbook” steal is gone |

### All 11 T2-bound truth-set rows

| row | class | use case | template? | coverage_ratio | specificity | coverage_score | bind_margin | matched |
|---|---|---|---|---|---|---|---|---|
| rt.hunt.005 | correct | edr_powershell_suspicious_command | yes | 0.4000 | 2.88 | 1.1520 | — | suspicious powershell |
| rt.hunt.006 | correct | edr_scheduled_task_creation | **no** | 0.3333 | 3.51 | 1.1705 | — | scheduled task |
| rt.hunt.007 | correct | edr_lateral_movement_candidate | **no** | 0.2857 | 3.51 | 1.0033 | — | lateral movement |
| rt.alert.001 | correct | auth_success_after_failure | yes | 0.2368 | 2.83 | 0.6714 | +0.42 | followed by a successful login |
| rt.alert.002 | wrong_family | net_vpn_login_anomaly | yes | 0.0741 | 2.49 | 0.1844 | — | vpn login |
| rt.know.001 | correct | soc_show_sop | no (knowledge) | 0.0714 | 3.51 | 0.2508 | — | sop |
| rt.know.002 | see below | soc_map_alert_mitre | no (knowledge) | 0.0455 | 3.12 | 0.1419 | **−0.29** | mitre |
| rt.know.005 | correct | edr_powershell_suspicious_command | yes | 0.0952 | 2.88 | 0.2743 | +0.13 | suspicious powershell |
| rt.para.011 | correct | edr_scheduled_task_creation | **no** | 0.2857 | 3.51 | 1.0033 | — | scheduled task |
| rt.neg.005 | correct | soc_show_sop | no (knowledge) | 0.1429 | 3.51 | 0.5016 | — | sop |
| rt.neg.006 | correct | soc_show_sop | no (knowledge) | 0.1429 | 3.51 | 0.5016 | — | playbook |

`rt.know.002` is the row that previously killed an absolute floor. The plan recorded it as a **correct** bind (`soc_map_alert_mitre` at coverage 0.14). Strict skill-set labelling marks it `wrong_family` because `mitre_mapping` is not in `acceptable_skills` (`knowledge_recall`, `guided_investigation`). Both readings are shown; the threshold conclusion does not depend on picking one.

## Do the populations separate?

Treating `rt.know.002` as a misfire (strict skill-set):

| statistic | correct range | misfire range | separates? |
|---|---|---|---|
| coverage_ratio | 0.0714–0.4000 | 0.0455–0.0741 | **no** (overlap at 0.07) |
| specificity | 2.83–3.51 | 2.49–3.12 | **no** |
| coverage_score | 0.2508–1.1705 | 0.1419–0.1844 | yes on n=2, **do not trust** |
| bind_margin | +0.13–+0.42 (n=2) | −0.29 (n=1) | n too small |

Treating `rt.know.002` as the plan previously did (correct knowledge bind): coverage_score correct min drops to **0.1419**, and the remaining misfire (`rt.alert.002` at 0.1844) sits **inside** that range. Separation disappears.

A legitimate SOP bind (`rt.know.001`) sits at coverage_ratio **0.0714** — one word in fourteen. Any floor high enough to be interesting takes that with it. That is the same overlap that rejected an absolute coverage floor on 2026-08-20.

**Consequence for item 3:** do not ship a coverage cutoff, including the 0.22 plateau midpoint. Approach B’s measured win was **re-ranking**, not veto. Item 3’s Do must be rewritten to relative ranking (+ runner-up margin as a seam, not a proven gate). Item 4 still has no margin that fires on this corpus.

## 105 questions that actually bind at T2 (14)

| question | T2 bind | template? | coverage_score | matched |
|---|---|---|---|---|
| q0.q008 | dns_beaconing_candidate | yes | 0.5853 | beaconing |
| q0.q015 | net_repeated_critical_asset_connections | **no** | 0.7802 | repeated connection |
| q0.q023 | dns_beaconing_candidate | yes | 0.5853 | beaconing |
| q0.q046 | auth_failed_login_spike | yes | 1.6013 | failed login(s) |
| q0.q049 | edr_powershell_suspicious_command | yes | 1.1520 | suspicious powershell |
| q0.q059 | auth_failed_login_spike | yes | 0.6328 | failure(s) |
| q0.q060 | auth_success_after_failure | yes | 2.8290 | successful login after |
| q0.q062 | auth_failed_login_spike | yes | 1.2010 | failed login(s) |
| q0.q065 | edr_scheduled_task_creation | **no** | 1.1705 | scheduled task |
| q0.q067 | dns_unusual_query_volume | **no** | 3.1416 | unusual dns / dns query volume |
| q0.q072 | edr_lateral_movement_candidate | **no** | 1.0033 | lateral movement |
| q0.q079 | edr_suspicious_process | yes | 0.8229 | suspicious process |
| q0.q086 | auth_failed_login_spike | yes | 0.8734 | failed login(s) |
| q0.q089 | auth_failed_login_spike | yes | 0.6328 | failure(s) |

The four **no-template** rows are T1 exact questions whose T2 shell steals paraphrases (`rt.hunt.006`, `rt.para.011`, `rt.hunt.007`) without a governed query. T1 still serves the verbatim 105 row. Those shells are in the cull below. Templated overlap with T1 is paraphrase coverage with SPL — kept.

## Catalogue cull (owner direction, after this table)

Rule: among bindable rows with no SPL template, keep **knowledge-only / no MCP**, plus the two T1 SPL-native meta rows (template-null by design). Delete hunt/MCP shells and non-knowledge workflow rows that can bind and block T4. Do not delete templated hunts. Do not delete unbindable `sample_*` template-registry anchors.

Live count before cull: 58 bindable, 31 without template (stale index JSON still showed MFA as empty; `catalog.json` already has `auth_mfa_failure_spike`).

### Preserve (7)

| use_case_id | skill | why |
|---|---|---|
| soc_show_sop | knowledge_recall | SOP/playbook retrieval, RAG only |
| soc_explain_spl | knowledge_recall | explain existing SPL, RAG only |
| soc_compare_past_incidents | knowledge_recall | RAG only |
| soc_environment_hygiene | knowledge_recall | RAG only |
| soc_map_alert_mitre | mitre_mapping | knowledge, no MCP. Generic pattern `mitre` is item 5, not this cull. |
| soc_generate_spl | spl_generation | **T1 meta**, `meta_output_artifact`. Not an empty hunt. |
| soc_optimize_spl | spl_generation | **T1 meta**, same. |

### Delete (24)

Hunt / MCP required, no template (19):
`auth_impossible_travel`, `auth_service_account_abnormal_login`, `auth_disabled_account_login`, `net_new_outbound_destination`, `net_port_scanning`, `net_east_west_anomaly`, `net_blocked_region_connection`, `net_repeated_critical_asset_connections`, `dns_unusual_query_volume`, `dns_tunneling_candidate`, `edr_new_service_creation`, `edr_scheduled_task_creation`, `edr_lateral_movement_candidate`, `edr_credential_dumping_signal`, `edr_malware_alert_summary`, `ot_unexpected_command`, `ot_it_to_ot_auth_anomaly`, `ot_critical_asset_after_hours`, `ot_protocol_anomaly`.

Not knowledge, no template (5):
`edr_isolation_recommendation`, `soc_create_investigation_note`, `soc_summarize_alert_evidence`, `soc_recommend_next_pivots`, `soc_draft_ticket`.

Lab draft families in `draft_preview.py` stay. Those are the out-of-registry / T4-adjacent preview path, not T2 catalogue binds.

IDF and which rows bind will change after this cull. Item 3 must use a post-cull re-run of the dump, not the 0.22 figure from the pre-cull sweep.

## Post-cull re-measure (same dump file, after deleting 24 rows)

`docs/evals/catalogue_bind_distribution_v1.json` was regenerated after the cull. Catalogue is **41** rows (34 bindable, 7 templateless knowledge/T1-meta).

| corpus | bound at T2 | unbound at T2 |
|---|---|---|
| routing truth set (96) | **8** | **88** |
| 105 goldens | **10** | **95** |

Classes: `no_bind` 87, `correct_bind` 6, `wrong_family` 2 (`rt.alert.002` / `rt.know.002`), `missed_procedure` 1, `false_knowledge` 0.

The four no-template T2 steals (`rt.hunt.006`, `rt.hunt.007`, `rt.para.011`, and 105 rows q0.q015/065/067/072) are gone. `rt.know.001` still binds `soc_show_sop` at coverage_ratio **0.0714**. Coverage_ratio still overlaps. Item 3 still has no univariate cutoff.

Remaining templateless bindable (7): `soc_show_sop`, `soc_explain_spl`, `soc_compare_past_incidents`, `soc_environment_hygiene`, `soc_map_alert_mitre`, `soc_generate_spl`, `soc_optimize_spl`.
