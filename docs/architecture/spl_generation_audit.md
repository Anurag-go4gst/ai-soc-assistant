# SPL Generation Audit (Phase A)

Status: **Phase A — audit + baseline only. No behavior change.**
Plan: `/root/.cursor/plans/spl_generation_audit_30f60bc7.plan.md`
Date: 2026-06-13. All claims verified against code at this date.

Primary metric is **relevance + correctness + coverage** — does the generated SPL
answer the asked question? Brevity is secondary (Phase E), measured only on
already-correct SPL. This document records what we generate today, where it is
wrong or missing, and the baseline numbers Phases B–E must beat.

---

## 1. Generation path matrix

| Lane | Generator | LLM? | Analyst field | State today |
|------|-----------|------|---------------|-------------|
| Governed template (happy path) | `templates.json` + slot binding | No | `spl_code` | **10 active** templates |
| Lab draft preview | `app/spl/draft_preview.py` (~30 families) | No | `draft_spl_code` | active fallback |
| Stage 3C stub (legacy) | `app/spl/generator.py` | No | `spl_code` | blocked when governance on |
| LLM main fallback | `app/spl/llm_fallback.py` | Yes | — | **DEAD** (B01) |
| LLM sidecar | `_llm_spl_candidate_stage()` | Yes | `llm_spl_candidate` | UI flag only |

**LLM is wired but dead on `/chat`.** `pipeline.py:2195` calls
`_candidate_from_llm_fallback(...)` without `request_enabled=True`; the default is
`False` (`pipeline.py:2553`), so it always returns `None`. The flag
`ai_soc_llm_spl_fallback_enabled` (`config.py:207`) is inert.

`templates.json` holds **18** templates: **10 active**, 5 `planned` (empty
`spl_text`), 3 `sample` (empty). Catalogue = **46** rows; only **10** bind an
active template → **36 rows (78%) have no governed SPL**.

---

## 2. Relevance baseline (headline)

Source: `scripts/eval_spl_relevance.py` → `docs/evals/spl_relevance_report.json`.
Structural scoring (data source / metric-aggregation / entity), no LLM.

| Corpus | Relevant | Denominator | % | Lanes |
|--------|----------|-------------|---|-------|
| 105 canonical | **81** | 105 | 77.1 | draft 102, none 3 |
| Catalogue (spl-expected) | **9** | 29 | 31.0 | template 9, none 20 |

Catalogue row classes: `spl_expected` 29, `justified_no_spl` 13, `deferred` 4.
`justified_no_spl` = analyst-workflow / knowledge skills (`soc_*`, knowledge_recall,
mitre_mapping, investigation_notes, ticket_drafting, action_planning, alert_summary)
that correctly produce no detection SPL. `deferred` = OT rows flagged "later".
Both are excluded from the coverage denominator — counting them as failures
understated reality. The real coverage gap is **20 spl-expected rows with no SPL**.

Corpora reported separately by design (105 uses the `pattern_type` keyspace,
catalogue uses `use_case_id`; a combined /151 would double-count).

**Top mismatch reasons**
- 105: `aggregation_missing` ×11, `data_source_missing:dns` ×5, `no_spl_generated` ×3, `entity_missing` ×3, others ×2
- Catalogue: `no_spl_generated` ×20 (the real coverage hole, Phase D)

These are the numbers Phases B–D must raise. They are a floor, not a grade — the
structural scorer is conservative and the Phase C gate adds LLM self-critique.

---

## 3. The real problem: mis-routing, not bloat

SPL is routed by a deterministic maze:

```
user_query
  → match_detection_family()      # draft_preview.py:1668 — 10 regex rules, FIRST-MATCH-WINS
  → PATTERN_TYPE_FAMILY_FALLBACK   # draft_preview.py:1646 — ~14 coarse pattern_type → family maps
  → ~30 lab draft families         # verbose deterministic bodies
```

### Confirmed mis-route (R2) — DNS asked, network returned

`build_draft_preview("Which hosts generated the most DNS queries?", pattern_type="top_n_aggregation")`
resolves family `network_traffic_top_talkers` and emits:

```
search index=<network_index> sourcetype=<network_traffic_sourcetype> ... (dest_port=* OR bytes=* OR bytes_out=*)
| eval src_host_norm=lower(coalesce(...))
| ... (no dns query fields anywhere)
```

The question asks about **DNS query volume**; the SPL counts **network bytes**.
`top_n_aggregation` maps generically to `network_traffic_top_talkers`, ignoring
DNS. **5 DNS questions** (q0.q017, q018, q035, q067, q082) hit this. This is the
canonical asked-X-got-Y failure and the headline finding of the audit.

`spl_validator.py` does not catch it — it checks *safety* (index/time/aggregation/
head), never whether the SPL answers the question. A safe-but-wrong SPL passes.

---

## 4. Bug catalog

### Class R — Relevance / correctness (fix first)

| ID | Bug | Location | Impact |
|----|-----|----------|--------|
| R1 | First-match-wins regex routing, order-dependent, no tie-break | `draft_preview.py:1668+` | Asked-X-got-Y when ≥2 families match |
| R2 | Coarse `pattern_type` fallback misroutes (DNS→network confirmed §3) | `draft_preview.py:1647` | Wrong field focus = useless answer |
| R3 | Unmapped `pattern_type` → no SPL (`asset_identity_context`) | `draft_preview.py:1662` | Coverage hole / justified no-SPL |
| R4 | 36/46 catalogue rows have no active template | `templates.json` / `catalog.json` | 78% can't produce governed `spl_code` |
| R5 | No intent↔SPL relevance check exists | (missing) | Safe-but-wrong SPL ships |

### Class W — Wiring (LLM dead)

| ID | Bug | Location |
|----|-----|----------|
| B01 | LLM fallback never invoked (`request_enabled=False` default) | `pipeline.py:2195`, `:2553` |
| B02 | Governance pre-block returns clarification before LLM can run | `pipeline.py:2499-2511` |
| B03 | `generation_mode="internal_llm"` label on `StubSplGenerator` body | `spl_services.py:15,21` |
| B04 | Draft preview tested-invariant: never calls LLM | `test_spl_draft_preview.py` |

### Class V — Verbosity (Phase E only, on correct SPL)

| ID | Bug | Location |
|----|-----|----------|
| B05 | SMB filtered in base search AND in `where` | `draft_preview.py:582,591` |
| B07 | Optimizer never runs on governed templates | `pipeline.py` template branch |
| B08 | `_rule_based_optimize` only adds, never trims | `spl_services.py:126` |
| B11 | LLM prompt forbids `tstats`/`datamodel` → blocks shorter+correct CIM | `llm_fallback.py:381` |
| B12 | SOC-STD-SPL-001 full blocks forced into LLM prompt | `family_engineering.py` + `llm_fallback.py` |

### Class C — Coverage / UX

| ID | Bug | Location |
|----|-----|----------|
| B13 → R4 | 36 rows no template | `catalog.json` |
| B14 → R3 | `asset_identity_context` unmapped (justified no-SPL) | `draft_preview.py:1662` |
| B15 | Parallel SPL surfaces (governed + draft + sidecar) confuse analysts | `analyst_response_builder.py` |

---

## 5. Verbosity (secondary)

Source: `scripts/eval_spl_verbosity.py` → `docs/evals/spl_verbosity_summary.md`.

| Lane | n | median pipes | max pipes | median chars | max chars |
|------|---|--------------|-----------|--------------|-----------|
| draft | 103 | 12 | 20 | 1049 | 1586 |
| template | 10 | 3 | 10 | 526 | 999 |

Drafts are ~4× the size of templates. This is real but **secondary** — drafts are
the lane analysts see for the 36 uncovered rows, so the priority is making them
*correct* (Phases B–C) and *complete* (Phase D) before trimming (Phase E).

---

## 6. Why the happy path stays deterministic

The 10 active templates stay deterministic on the live path for reproducibility
(byte-identical SPL), latency (no live-LLM call), Experience Center isolation
(`coe_synthetic_fixture` must never call a live model), governance tier (templates
are COE authority; LLM output is candidate-only), and availability (single
air-gapped llama.cpp). LLM cross-checks templates **offline** (Phase F,
`scripts/llm_template_audit.py`) and is **primary on the live failover path only**.

Active templates today: `auth_failed_login_spike`, `auth_success_after_failure`,
`auth_new_source_ip_login`, `auth_account_lockout_trend`, `dns_beaconing_candidate`,
`edr_powershell_suspicious_command`, `aws_security_group_modifications`,
`aws_console_success_logins_by_user`, `aws_iam_policy_modifications`,
`auth_failed_login_top_users_exclude_service_accounts`.

---

## 7. Analyst guidance (which lane to trust)

- **`spl_code` (template lane):** governed, vetted, reproducible. Trust as authority.
- **`draft_spl_code` (draft lane):** lab review only, not catalog-approved, verbose,
  and (today) can be mis-routed (§3). Review the data source and fields before use.
- **No SPL:** 36 catalogue rows and 3 of the 105 produce nothing. Phase D closes this.

---

## 7b. Phase B results (routing correctness, deterministic, no LLM)

| Metric | Phase A | Phase B |
|--------|---------|---------|
| 105 spl-expected relevant | 81/105 (raw) | **97/102 (95.1%)** |
| Catalogue spl-expected relevant | 9/29 | 12/31 (38.7%) |

Fixes landed:
- **PowerShell aggregation (+11):** `endpoint_powershell_suspicious` now rolls up
  `stats ... by host_norm` so "which hosts ran X" returns a host ranking, not a raw
  event dump.
- **DNS-aware routing R2 (+5):** two new families `dns_query_volume` (by host) and
  `dns_domain_spread` (by domain, dc hosts), plus hardcoded DNS routing in
  `match_detection_family` before the generic network fallback. DNS questions no
  longer get `network_traffic_top_talkers`.
- **B03:** `generation_mode` for the internal-LLM provider relabelled `stub` (body
  is the deterministic StubSplGenerator; no live LLM on that path).
- **Justified-no-SPL classification** added to the eval (lane-guarded): lookup /
  enrichment rows (`case_state_lookup`, `asset_identity_context` with no SPL;
  catalogue `soc_*` / knowledge skills) are excluded from the coverage denominator
  only when they produce no SPL — a lookup-classed question that still yields
  relevant SPL stays scored.

Deferred (correctly, not gamed):
- **B05** (SMB redundant `where`) → Phase E: its `like(app_norm,"%smb%")` adds
  wildcard breadth beyond the base search and has a contract test; belongs with the
  simplifier + test update.
- **R1** (ambiguous multi-match → clarification) → Phase C: without the LLM
  re-route destination, forcing ambiguous matches to clarification only adds
  regressions.
- **5 remaining 105 mismatches are genuine Phase C LLM cases**, not fabricated
  families: q048 impossible-travel, q056 after-hours, q070 password-change (auth
  questions mis-routed to network — no fitting auth draft family exists), q092/q093
  multi-signal correlation (need multi-source + entity reasoning).

## 8. Baselines recorded (Phase A exit)

| Check | Result |
|-------|--------|
| `eval_spl_relevance.py` | 105: 81/105 · catalogue spl-expected: 9/29 (recorded floor) |
| `eval_spl_verbosity.py` | draft med 12 pipes · template med 3 pipes |
| `eval_105_path_honoring.py --check` | PASS (105/105) |
| `spl_draft_preview_eval` | PASS |
| `run_stage3_governance_regression.sh` | **PASS** |

No app code changed in Phase A — two eval scripts added under `scripts/`, this
doc, and the two eval reports under `docs/evals/`. Phases B–E follow the plan.
