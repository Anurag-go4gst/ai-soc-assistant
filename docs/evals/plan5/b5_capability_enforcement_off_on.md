# Plan 5 B5 — capability enforcement OFF→ON measurement

Observation only. Flag remains **default OFF**. No skill-contract widening.
No protected/frozen baseline refresh.

## Summary

- Truth-set rows measured: **87**
- Adjudication route changed OFF→ON: **0**
- ON veto (demote to `knowledge_recall`): **0**
- ON unsatisfied (already `knowledge_recall`, required cap denied): **0**
- Label required-cap denied by truth-set skill: **23**
- Label required-cap denied by adjudicated skill: **13**
- Truth-set evaluator note: `scripts/eval_routing_truth_set.py does not call adjudicate_route; deterministic arm uses select_route_from_understanding and live arm uses route_skill. Adjudication-layer deltas in this file can be invisible to --check.`

RP graph on this measurement host short-circuits when canonical planning
persistence fails (`handoff_load_failed` / DNS). `route_adjudication` is then
absent, so live enforcement is **unreachable** on that degrade path. The
adjudication-layer table above is the authoritative OFF→ON instrument.

## Route-change rows

_None. Enforcement did not change any adjudicated skill._

## Residual observations (named)

### rt.d1.003 (ownership_deferred)

- Query: `Did anyone get added to Administrators?`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d1.005 (ownership_deferred)

- Query: `Which users accessed privileged applications unusually?`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d1.006 (ownership_deferred)

- Query: `Which accounts were disabled or re-enabled today?`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d1.011 (ownership_deferred)

- Query: `Which logs are missing from key security sources?`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d1.012 (ownership_deferred)

- Query: `Which sources stopped sending events recently?`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d1.013 (ownership_deferred)

- Query: `Which users performed privileged actions from non-admin workstations?`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d1.014 (ownership_deferred)

- Query: `For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status?`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d2.003 (d2_defect)

- Query: `Are there signs of Kerberoasting against domain controllers in the finance subnet?`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d2.010 (d2_defect)

- Query: `Explain when timechart is preferable to stats for tuning a threshold and provide a review-only example.`
- Label acceptable skills: `['spl_generation', 'knowledge_recall']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.d2.017 (d2_defect)

- Query: `Optimize a search that performs eval and regex on millions of events before applying its base filters.`
- Label acceptable skills: `['spl_generation', 'knowledge_recall']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.001 (paraphrase)

- Query: `which sources sent out the largest number of outbound sessions`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.002 (paraphrase)

- Query: `did any of our machines reach out to IPs on the threat list in the past day`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `[]`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `spl_generation`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.003 (paraphrase)

- Query: `any domain lookups that look algorithmically generated`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.004 (paraphrase)

- Query: `do we have endpoints calling home on a regular cadence`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.005 (paraphrase)

- Query: `hosts talking to an unusually wide spread of external addresses`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.006 (paraphrase)

- Query: `machines opening SMB sessions against a lot of different peers`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.007 (paraphrase)

- Query: `anyone shipping unusually large volumes of data outward`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.008 (paraphrase)

- Query: `endpoints where PowerShell ran in a way that looks off`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.009 (paraphrase, ownership_deferred)

- Query: `was anybody granted local admin rights recently`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.010 (paraphrase)

- Query: `who currently carries the highest risk score`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `spl_generation` (evidence_plan_live_or_hybrid, family `spl_generation_only`)
- ON adjudicated: `spl_generation` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.011 (paraphrase)

- Query: `new scheduled tasks appearing on any workstation`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `[]`
- Label caps denied by adjudicated skill: `[]`
- Truth-set skill (evaluator arm): `attack_discovery`
- OFF adjudicated: `attack_discovery` (catalogue_registry_skill, family `live_investigation`)
- ON adjudicated: `attack_discovery` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.012 (paraphrase)

- Query: `signs that something is moving sideways through the estate`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.013 (paraphrase, ownership_deferred)

- Query: `are we missing log feeds from any important security source`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.014 (paraphrase, ownership_deferred)

- Query: `which log sources went quiet lately`
- Label acceptable skills: `['alert_summary', 'attack_discovery', 'knowledge_recall', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

### rt.para.015 (paraphrase)

- Query: `have we run into this indicator before and what did we decide last time`
- Label acceptable skills: `['attack_discovery', 'spl_generation']`
- Label required capabilities: `['spl']`
- Label caps denied by truth-set skill: `['spl']`
- Label caps denied by adjudicated skill: `['spl']`
- Truth-set skill (evaluator arm): `knowledge_recall`
- OFF adjudicated: `knowledge_recall` (intent_clarification, family `clarification_required`)
- ON adjudicated: `knowledge_recall` enforcement=`compatible` denied=`[]`
- Route changed: **False**

## Mechanism

`spl_generation` grants **SPL only**. `live_investigation` requires **SPL+MCP**. Enforcement therefore vetoes
`spl_generation` → `knowledge_recall` whenever the contract family is `live_investigation`. It never promotes
`knowledge_recall` to an SPL-capable skill. That is why residual hunt under-routing is unchanged and why one
in-catalogue hunt that already used `spl_generation` regresses.

## ON-arm product delta (in-catalogue guard / pytest)

Truth-set `--arm both` is **identical** OFF and ON (`64/76`, live `59/76`, 0 regressions): the evaluator does not
call `adjudicate_route`.

Temporary `AI_SOC_LIVE_CAPABILITY_ENFORCEMENT_ENABLED=true` backend pytest: **3 failed / 5158 passed**.

| Failure | Kind | Meaning |
|---|---|---|
| `test_enforcement_flag_defaults_off` | measurement artifact | `Settings()` reads the ON env var; `config.py` default remains `False` |
| `test_full_guard_passes_against_baseline` | **real product delta** | `cisco.ot.029` only |
| `test_in_catalogue_contract_guard_still_green` | wrapper of the row above | same row |

**cisco.ot.029** — "Show any operational setpoint modifications transmitted to solar grid inverters over the last 24 hours."

| Field | OFF | ON |
|---|---|---|
| route | `spl_generation` | `knowledge_recall` |
| execution_status | `requires_human_review` | `skipped` |
| execution_eligible | `false` | `None` |
| human_review_required | `true` | `false` |
| spl_approved | `false` | `None` |
| enabled_sections | `analyst_action_guidance` | `[]` |
| analyst_enabled_sections | `analyst_action_guidance`, `draft_spl_preview` | `draft_spl_preview` |

The guard prints the first 10 diffs; all 7 were this row. No other 105/Cisco catalogue row moved.

## Residual-row observations (no patches)

| Row class | Observation |
|---|---|
| `rt.d2.003` | Label needs SPL; truth-set skill `knowledge_recall`; adjudication already `spl_generation` / `spl_generation_only` / compatible. ON does not change the route. Does not fix the evaluator-arm miss. |
| `rt.d2.010` | Clarification family, empty contract required caps, `knowledge_recall` compatible. Label still wants SPL. ON no-op. |
| `rt.d2.017` | Same as `.010`. ON no-op. |
| `asset_identity_context` / `data_source_health` | Several d1 rows: truth-set `knowledge_recall`, adjudication already `spl_generation` and compatible. Ownership still deferred. ON no-op. |
| Paraphrase hunts | Mix of clarification (`knowledge_recall`, compatible because required caps are empty) and a few already-SPL-capable adjudications. ON never promotes the under-routed paraphrases. |

## Gate results

**OFF (production default):** targeted `test_capability_enforcement.py` 11 passed; backend pytest **5161 passed / 0 failed**; truth set `--arm both --check` **0 regressions** (`64/76`, live `59/76`); path honoring **105/105**; governance **PASS** (parity **120 exact**, Cisco **50/0/0**, sentinel **17/17**, harness 6/6); reference probes **10/10** (compose Postgres `127.0.0.1:5434`); manifest **15/15**. Stale governance reports reverted.

**ON (temporary env):** truth set identical; pytest **3 failed** as tabled above. Full ON governance was not re-run; it would fail the same pytest slice. No protected/frozen artifact was refreshed.

## Options (STOP — `B_LIVE_CAPABILITY_ENFORCEMENT`)

1. **Keep default OFF** (recommended). Ships the veto path for later activation. Avoids regressing `cisco.ot.029` and avoids silently treating `spl_generation` as MCP-incapable on every `live_investigation` contract.
2. **Activate default ON.** Accept the `cisco.ot.029` demotion and the `spl_generation`×`live_investigation` veto. Does **not** rescue D2/paraphrase under-routing.
3. **Change the compatibility policy** (out of B5). Examples: grant MCP on `spl_generation`, or stop requiring MCP for `live_investigation` when the selected skill is SPL-authoring. That is a second capability decision, not an activation flip.

Recommendation: **remain OFF** until a named policy decides how `spl_generation` should relate to `live_investigation`. Do not proceed to B6 or Phase C from this gate.

