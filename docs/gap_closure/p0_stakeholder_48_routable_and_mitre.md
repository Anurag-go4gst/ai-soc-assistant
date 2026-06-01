# P0-8 — Stakeholder Brief: 48 `likely_routable`, Production Lifecycle, MITRE Three Layers

Audience: COE deck, SOC leadership, and engineering reviewers.

## Why 48 `likely_routable` exists

COE needed one pass over **105 real SOC team questions** to answer:

> How many questions are **template/SPL-shaped** at design time vs blocked on lookup, vetted detection, context enrichment, or multi-signal work?

That is **Stage 3L-S6.2** ([`../stage3l_s6_105_question_operation_map.md`](../stage3l_s6_105_question_operation_map.md)) — **provisional dependency bucketing** for roadmap priority, Q4 promotion, and eval buckets. It is **not** a claim that 48 questions work on live `/chat` today (~99/105 still hit legacy clarification on the keyword router).

### What “routable” means here

**`likely_routable`** ≈ taxonomy says the primary path is template/SPL-shaped **without** a hard lookup/detection/context/multi-signal blocker **at design time**.

It does **not** mean:

- 48 skills, 48 MCP tools, or 48 promoted patterns (**10** promoted; **8** of the 48 are promoted)
- Live-routable on `/chat`
- Runtime precondition pass (S7 `precondition_eval` decides per request)

### How 48 is computed

[`tools/coverage_authoring/operation_report_fields.py`](../../tools/coverage_authoring/operation_report_fields.py):

- `dependency_type == template` → **`likely_routable`** (~43 rows)
- Plus **`promoted_to_manifest`** without skill drift → **`likely_routable`**

| `provisional_status` (S6.2) | Count | Meaning |
|-----------------------------|------:|---------|
| **likely_routable** | **48** | Template/SPL path at taxonomy level |
| likely_needs_detection | 26 | Vetted detection required |
| likely_needs_lookup | 14 | Notable/IOC/case lookup |
| likely_needs_context | 7 | Asset/identity enrichment |
| likely_multi_signal | 7 | Multiple signal families |
| likely_needs_review | 2 | Ambiguous / drift |
| likely_unsupported | 1 | Blocked (`q0.q028`) |

**Orthogonal columns on the same row:** `likely_runtime_operation` (e.g. `threshold_anomaly` 32, `aggregate_and_rank` 9) is **what analytic work**; `likely_routable` is **what infra deps** at design time.

### 48 vs S7 preconditions (slide fix)

| | **48 `likely_routable`** | **S7 precondition_eval** |
|---|--------------------------|---------------------------|
| When | Author-time / CI report | Per request |
| Role | Coverage planning | Execution gate |
| On execution diagram? | **No** | **Yes** |

A row can be `likely_routable` yet fail runtime preconditions (missing template env, time window, execution flags off).

### Production lifecycle

| Aspect | Production target |
|--------|-------------------|
| As **live routing gate** | **Ceases** — never authority on `/chat` |
| As **registry metadata** | **Remains** — keep `design_dependency_bucket` / `provisional_status` for COE reporting |
| As fixed count “48” | **Evolves** — regenerate when taxonomy or promotions change |
| Eval harness | **Remains** — `likely_routable` bucket in 105 shadow eval |

**Deck one-liner:** *48 is a planning bucket on 105 questions, not production readiness. Preconditions gate execution; the bucket stays for coverage roadmap.*

**Rename (P0):** Prefer `design_dependency_bucket` over `provisional_status` in unified registry exports to avoid implying live routability.

---

## MITRE — three layers (honest status)

### Today (no single join per 105 row)

| Layer | Artifact | Role | Live? |
|-------|----------|------|-------|
| **Taxonomy (105)** | `suggested_MITRE_candidates` in [`../soc_question_taxonomy_stage3k_q0.md`](../soc_question_taxonomy_stage3k_q0.md) | Per-question planning IDs | **No** |
| **Use cases (42)** | `mitre_candidates` in [`catalog.json`](../../backend/app/use_cases/catalog.json) | Keyword bridge | **Partial** — `match_use_cases` → [`mitre_kb.py`](../../backend/app/threat/mitre_kb.py) |
| **Runtime KB** | [`mitre_attack_subset.json`](../../backend/app/threat/mitre_attack_subset.json) — **2 techniques** | Mappable with status | **Yes** — only when use case matches |

Most `/chat` requests → `mitre_mappings: []`. Taxonomy MITRE is **not** joined to operations or the 105 runtime map today.

### Target (P5) — `mitre_permitted[]` per registry row

```text
mitre_permitted[]  ← taxonomy suggested_MITRE + use-case mitre_candidates + offline bundle
                   ← filter to IDs with status supported/candidate in runtime KB
                   ← synthesis may only cite supported set in production
```

**Deck line:** *MITRE on 105 is documented in taxonomy; live maps ~2 techniques via use-case overlap; target is `mitre_permitted[]` per registry row.*

| Phase | Deliverable |
|-------|-------------|
| P0-8 | This stakeholder doc |
| P5-6 | Report-only `mitre_permitted` builder |
| P5-7 | Flag-gated synthesis uses permitted set only |
| P5-10 | LLM MITRE candidate mapper (review queue; not authority) |

### Status vocabulary (target)

| Target label | Meaning in answers |
|--------------|-------------------|
| `supported` | SOC-approved; may cite in production |
| `candidate` | Valid ID; label as candidate in lab/system-check |
| `needs_review` | Trace/review only |
| `not_mapped` | Explicit “no mapping” |
| `not_applicable` | Knowledge/ops rows — do not force MITRE |
