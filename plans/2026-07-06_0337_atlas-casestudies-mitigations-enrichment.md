---
name: atlas-casestudies-mitigations-enrichment
overview: "Stage MITRE ATLAS case-study + mitigation dataset, normalize offline, surface via reference_registry + grounding_assembler, and let existing attack_discovery/guided_investigation execution + Stage 3J evidence rules (not new code) confirm an ATLAS technique against live SOC logs"
status: done
date: 2026-07-06
canonical_plan: plans/2026-07-06_0337_atlas-casestudies-mitigations-enrichment.md
loop_runner: plans/LOOP_RUNNER_atlas-casestudies-mitigations-enrichment.md
---

# ATLAS case-study + mitigation enrichment + log-evidence correlation

## Objective

**Gap confirmed live.** `docs/evals/reference_knowledge_ask_chat_2026-07-05.txt` captured
a real probe: *"What MITRE ATLAS techniques apply to prompt injection against
our LLM agent using MCP tools?"* → answer today is a bare list —
`AML.T0065 LLM Prompt Crafting (dataset mitre_atlas; tactics
['resource-development']; citation MITRE ATLAS local coverage artifact)` — no
mitigation, no real incident, no next step. Zero mitigations exist anywhere
in this codebase for ATLAS (`grep -rn mitigation backend/app --include=*.py`
hits only a generic LLM prompt fragment).

**Confirmed via direct pull of the public dataset** (`atlas-nodes-04-2026-with-hashtags-and-embedding-text.csv`,
from `github.com/mitre-atlas/atlas-knowledge-base-agent` — a Langflow +
Chroma app we explicitly do **not** adopt, only its flat CSV is in scope):
170 techniques (matches what we have), 16 tactics, **57 case studies**, **35
mitigations**. 66/170 techniques (39%) carry a direct mitigation link. For
`AML.T0065` specifically (the technique the live probe actually hit), 0
direct mitigations but 18 linked case studies including **AML.CS0045 "Data
Exfiltration via an MCP Server used by Cursor"** and **AML.CS0054 "Data
Exfiltration via Remote Poisoned MCP Tool"** — directly on-domain since this
product itself does MCP tool-calling.

**This plan has four layers, and they do NOT share one code path:**

1. **Phase A — structured facts** (items 1-7): case studies + mitigations as
   deterministic offline facts, wired into `reference_registry.py`'s
   existing `mitre_atlas` resolver, rendered by
   `analyst_response_builder._reference_summary`. This is the
   `reference_taxonomy` / `knowledge_recall` answer path — pure knowledge,
   **never claims live exploitation** (see governance note below).

2. **Phase B — full narrative depth** (item 8): governed SOC-KB RAG
   ingestion of the full case-study/mitigation description text (not just
   the ~200-char structured summary), for when Context Sufficiency Gate
   depth calls for it. Additive, optional relative to Phase A.

3. **Phase C — log-evidence correlation** (items 9-15): this is the part
   that answers *"AI threat when collaborated with SOC logs can confirm
   this has happened."* **Critical finding from reading
   `backend/app/chat/evidence_planner.py:144-170`: the `reference_knowledge`
   family that backs `reference_taxonomy` hard-codes `needs_spl=False,
   needs_mcp=False, spl_allowed=False, mcp_allowed=False` and explicitly
   lists `unsupported_claims_avoid=["live environment exposure", "confirmed
   exploitation", "confirmed alert mapping"]`.** That is a deliberate
   governance guard — a pure "what is this technique" lookup must never
   assert "this happened to you" without real evidence. Phase C therefore
   does **not** touch `reference_knowledge`/`reference_taxonomy` at all. It
   extends the **other** existing path that is already allowed to combine
   MITRE-technique grounding with live execution evidence:
   `backend/app/chat/grounding_assembler.py`, which **already** imports
   `AI_THREAT_KEYWORDS` from `reference_registry.py` and **already** builds
   `GroundingBlock.atlas_references` for `attack_discovery`/
   `guided_investigation` turns (confirmed by reading the file — see
   `atlas_reference_for_question()` at line 94). Phase C enriches that
   existing payload with mitigations/case-study ids; it does not invent a
   new mechanism for combining knowledge + logs. The combination itself
   already happens for free: `backend/app/evidence/context_sufficiency.py`'s
   `_classify()` already promotes a turn to `PARTIAL_ANSWER`/`FULL_ANSWER`
   once `source_type in {"mcp","splunk_mcp"}` evidence is present alongside
   other collected evidence (Rule 10/11) — no new gate code needed, only
   verification that it actually fires (item 11).

4. **Phase D — remediation visibility only** (items 16-18): once a Phase C
   finding is live-confirmed, render advisory *text* naming what
   remediation would be suggested — never an executable action, never
   touching `action_lane.py`/`capability_policy.py` (pinned by item 18).
   Real remediation **execution** is explicitly out of scope by user
   decision (2026-07-06) — deferred to a separate follow-up plan (see that
   section below, placed after Phase D in this document).

**"Done" means:** Phase A + B shipped and rendering; Phase C's grounding
enrichment shipped; Phase D's advisory-only remediation preview renders and
is provably isolated from the action lane; a governance pin test proves
`reference_knowledge`'s `unsupported_claims_avoid` guard is untouched; an
end-to-end trace proves a combined attack_discovery turn (ATLAS grounding +
live/mock mcp execution) lands on `full_answer`/`partial_answer` via
existing Stage 3J rules; reference-probe-audit + full governance regression
stay green.

## Is there a real link between ATLAS and SOC Splunk logs? (established, not assumed)

Checked directly rather than guessed. `docs/threat-intel/atlas/raw/ATLAS.yaml`
(already staged, already parsed by `attack_data_resolver.py`) carries MITRE's
own official crosswalk field, `ATT&CK-reference`, on **34 of the 170 ATLAS
techniques** — e.g. `AML.T0012 Valid Accounts → T1078`,
`AML.T0050 Command and Scripting Interpreter → T1059`,
`AML.T0052 Phishing → T1566`, `AML.T0006 Active Scanning → T1595`. This is a
real MITRE-published field, not a heuristic we invented. **Our own parser
already reads this file and throws the field away**
(`_parse_atlas_yaml` in `backend/app/threat/attack_data_resolver.py:207-227`
keeps only `id`/`name`/`description`/`tactics`) — a small, surgical gap, not
missing data.

Why this matters: we already have an enterprise ATT&CK dataset
(`mitre_attack_enterprise` in `reference_registry.py`) and one existing
template (`notable_critical_review_mitre`) already tags detections with
`mitre_technique_id`. So the real, traceable chain is:

```
AML.Txxxx (ATLAS technique)
   --[MITRE's own ATT&CK-reference crosswalk, in ATLAS.yaml today]-->
Txxxx (standard enterprise ATT&CK technique)
   --[if the customer's EDR/SIEM tags detections with ATT&CK ids, common practice]-->
an existing governed SPL template
```

Hand-checked all 34 crosswalked techniques against the 37 templates in
`backend/app/spl/templates.json`:

| Strength | Count (of 34 crosswalked) | Example |
|---|---|---|
| Strong (dedicated existing template) | 4 | `T1078 Valid Accounts` → `auth_new_source_ip`/`privileged_account_failure`; `T1059 Command and Scripting Interpreter` → `edr_powershell_suspicious_command`/`notable_critical_review_mitre` (already defaults to `T1059.001`); `T1566 Phishing` → `email_phishing_header_review`; `T1595 Active Scanning` → `cisco_stealthwatch_scan_with_asset` |
| Moderate (generic overlap) | 6 | `T1057 Process Discovery`, `T1003 OS Credential Dumping`, `T1036 Masquerading` → `edr_suspicious_process`; `T1190 Exploit Public-Facing Application` → `firewall_deny_spike`/`cisco_asa_ioc_lookup` |
| Weak | 8 | cloud/API-token techniques (`T1526`, `T1550`), thin existing coverage |
| None — attacker-side recon/resource-development, structurally invisible in *victim* telemetry | 13 | `T1596 Search Open Technical Databases`, `T1588 Obtain Capabilities`, `T1585 Establish Accounts` — these happen on the attacker's own infrastructure, before they ever touch the victim, no SOC log will ever show them regardless of what we build |
| Not crosswalked at all (ATLAS itself provides no ATT&CK-reference) | 136 of 170 | model poisoning, adversarial perturbation, training-data manipulation — internal to the ML pipeline/data-science tooling, not a gap in our work, a structural fact about what's observable |

**Honest bottom line:** ~10 of 170 ATLAS techniques (6%) have a solid,
MITRE-traceable path to an existing governed template. That 10 is not
nothing — it is exactly the seam where an AI-agent compromise crosses back
into ordinary IT (compromised service account calling the LLM, agent
shelling out via `T1059`, phished operator, scanning before an API exploit)
— the same seam this product's own MCP-tool-calling architecture would need
watched. The other 160 either can't be observed in defender telemetry by
nature (attacker-side) or aren't in scope for this repo to invent detections
for without new telemetry the operator hasn't onboarded.

## How a user query reaches the right answer (both branches)

**Branch 1 — "What is this?" (knowledge_recall → `reference_taxonomy` shape).
Stays pure knowledge, never claims live exploitation, by explicit design:**

```
user query
  → answer_shape_router._reference_taxonomy_matches() (id or AI_THREAT_KEYWORDS match)
  → evidence_planner.plan_evidence(family="reference_knowledge")
      needs_spl=False, needs_mcp=False, spl_allowed=False, mcp_allowed=False
      unsupported_claims_avoid=["confirmed exploitation", "live environment exposure", ...]
  → pipeline._resolve_reference_knowledge(query)
      → reference_registry.load_reference_registry()
      → TechniqueReferenceResolver.resolve_ids(["AML.Txxxx"])
          → _technique_fact(): raw = {**yaml_detail, "atlas_enrichment": {mitigations, case_studies}}  [item 6]
  → pipeline._append_reference_source_evidence()
      → build_provider_source_evidence(source_type="reference_dataset", keyword_scrub=False)
      → SourceEvidence item, trace_id-stamped in ai_trace_runs automatically — no new telemetry hook
  → context_structurer._reference_facts() copies preview_rows verbatim into StructuredContext.reference_facts
  → analyst_response_builder._reference_summary() renders bullets incl. mitigations/case-studies  [item 7]
  → answer stays reference_taxonomy shape: definition + mitigation + real incident citation,
    explicitly no claim that this happened in this environment
```

**Branch 2 — "Did this happen to us?" (out-of-registry hunt with grounding +
explicit run/execute intent). The only branch allowed to combine ATLAS
grounding with live log evidence. Corrected below (review findings High #2 +
Medium #3) — two independent axes were originally conflated into one:**

```
user query, AI-threat keyword, out-of-registry/near-105 framing
  → [axis 1: grounding — independent of family] whenever state["canonical_facts"]
    is populated (pipeline.py:3451-3463), regardless of which evidence_planner
    family the intent resolves to:
      → grounding_assembler.assemble_grounding_from_facts()
          → atlas_reference_for_question(question)  [existing, confirmed at line 94]
              → now also attaches atlas_technique_enrichment(technique_id)  [item 9]
              → now also attaches crosswalked ATT&CK id + template hint, when strong/moderate  [items 12-14]
              → now also attaches a remediation-preview text, when curated  [items 16-17]
      → GroundingBlock.atlas_references carries: technique, mitigations, case studies,
        crosswalked Txxxx, suggested existing template, remediation preview (all advisory)
      → state["grounding_block"] set

  → [axis 2: MCP eligibility — a separate gate, requires explicit run/execute
    intent, NOT just AI-threat/taxonomy phrasing] evidence_planner resolves the
    intent_family. `hybrid_alert_review` (attack_discovery's actual family) and
    `guided_investigation` both have mcp_allowed=False — grounding alone never
    unlocks execution. Only `spl_generation_and_run`/`hybrid_investigation_plus_policy`
    (explicit "run/execute this search" intent) have needs_mcp=True, mcp_allowed=True.

  → when axis 2 resolves to an MCP-eligible family for this same turn: analyst
    confirms (existing per-call HIL gate, unchanged) → live Splunk MCP search
    executes via the existing async lifecycle (splunk_search_lifecycle.py) →
    build_provider_source_evidence(source_type="splunk_mcp", evidence_source="live")
  → both the grounding-sourced reference item AND the live splunk_mcp item land in
    the same turn's source_evidence list
  → context_sufficiency._classify(): has_execution=True (source_type in {mcp,splunk_mcp})
      → Rule 10/11 fires → mode = partial_answer or full_answer   [proven by item 11's test]

  → [axis 3: surfacing — a third, separate gate] the classification above is
    internal; whether the analyst actually *sees* the combined finding depends
    on `skill_contribution.py::apply_evidence_summary_floor()`, scoped to
    `match_path_for_t2 in {"out_of_registry", "near_105_question"}` (an existing,
    unrelated T2 scoping condition — item 11's test target must be an
    out-of-registry-shaped turn for this reason). Extended (item 15) to read
    `grounding_block["atlas_references"]` and append to
    `AnalystResponseEnvelope.evidence_summary`: "ATLAS AML.Txxxx (crosswalked
    ATT&CK Txxxx): mitigation — X; case study — Y; check: <template_id>" — and
    (item 17) to `recommended_actions`: "Suggested remediation (not available at
    the current Tier 1 — Prepare stage): <remediation text>." Text only — no
    `ActionProposal` created, `capability_policy.py` untouched (item 18 pins this).
```

The two branches (Branch 1 vs. Branch 2) never merge into one code path —
that's deliberate (`reference_knowledge`'s claim guard, item 10, pins this).
Within Branch 2, grounding / MCP-execution / analyst-visible-surfacing are
three independent gates, not one flag — all three must align for the
combined sentence to actually reach the analyst. A pure `reference_taxonomy`
answer (Branch 1) never grows a remediation line, since it never claims
exploitation in the first place and never populates `canonical_facts` the
way Branch 2 does.

## Stop conditions

- All checklist items checked with recorded evidence, **or**
- Same verification gate fails twice on one item, **or**
- Decision needed (dataset-shape mismatch, or COE wants Phase C gated behind
  a new flag) — **stop and ask**

## Dependency order

`1 → 2 → {3,4,8} → 5 → {6,9,12} → {7,10,13} → {14,16} → 15 → 17 → 18 → 19 → 11 → 20 → 21 → 22`

(3, 4, 8 are independent of each other, run in parallel. 6, 9, 12 all depend
only on 5/nothing — run in parallel. 7 depends on 6; 10 is independent; 13
depends on 12 — run in parallel. 14 depends on 9+13; 16 depends on 13 —
these two can run in parallel. 15 depends on 9+14 (not parallel with 14).
17 depends on 15+16. 18 depends on 17. 19 depends on 9+14+15+17. 11 depends
on 9+10. 21 depends on 8+11+18+19+20.)

## Checklist

### Phase A — structured facts (reference_registry / reference_taxonomy)

- [x] **1** — Stage raw CSV immutably
  - **Do:** Download `atlas-nodes-04-2026-with-hashtags-and-embedding-text.csv`
    from `https://raw.githubusercontent.com/mitre-atlas/atlas-knowledge-base-agent/main/data/datasets/atlas-nodes-04-2026-with-hashtags-and-embedding-text.csv`
    into `docs/threat-intel/atlas/raw/atlas_nodes_2026_04.csv` (repo
    snake_case convention). Add provenance note (source URL, MITRE case
    number 26-1336, pull date, sha256) to `docs/threat-intel/atlas/README.md`.
    Never edit file bytes after staging.
  - **Verify:** `sha256sum docs/threat-intel/atlas/raw/atlas_nodes_2026_04.csv`
    matches the value recorded in README; `git status` shows only the new
    raw file + README diff
  - **Depends on:** none
  - **Evidence:** `sha256sum` → `66eb5d2178df8a09ac4d90267fc44f3e5446f62457a771732f18742e538b8408` matches README; 3713 lines staged 2026-07-06.

- [x] **2** — Duplicate/shape gate on new raw file, fail loud on schema drift
  - **Evidence:** `python3 scripts/atlas_nodes_duplicate_check.py` → exit 0, counts 170/16/57/35, dangling=0; column-rename negative check fires `unexpected_column_set`.
  - **Do:** Add `scripts/atlas_nodes_duplicate_check.py` (the existing
    `scripts/atlas_duplicate_check.py` is shaped for the Navigator-layer
    `techniqueID`/`tactic` row format, not this CSV's
    `id`/`entity`/`PARENT_*`/`CHILD_*` shape — confirmed by reading it, not
    reusable as-is). **First check, before anything else:** assert the CSV
    header is exactly `{id, name, entity, text, description, url, keywords,
    hashtags, PARENT_TACTICS, PARENT_TECHNIQUES, PARENT_MITIGATIONS,
    PARENT_CASESTUDIES, CHILD_TECHNIQUES}` (confirmed by direct pull
    2026-07-06) — raise immediately with the actual vs. expected column set
    if it differs, do not silently proceed with a partial parse (review
    finding, Low: this is the first-execution risk if MITRE revises the CSV
    shape before this plan runs). Then assert: exactly 4 `entity` values
    (`tactic`=16, `technique`=170, `casestudy`=57, `mitigation`=35 — the
    counts confirmed above), no duplicate `id` within an entity type, and
    that `PARENT_TECHNIQUES`/`CHILD_TECHNIQUES`/`PARENT_MITIGATIONS`/
    `PARENT_CASESTUDIES` columns parse as valid Python list literals
    referencing only `AML.T*`/`AML.CS*`/`AML.M*`/`AML.TA*` ids that exist as
    a row `id` elsewhere in the file (referential-integrity check). Write
    `docs/threat-intel/atlas/reports/atlas_nodes_duplicate_report.{md,json}`.
  - **Verify:** `python3 scripts/atlas_nodes_duplicate_check.py` exits 0;
    report shows 0 duplicates, 0 dangling references, counts 170/16/57/35;
    separately, `python3 -c "..."` feeding a fixture CSV with one column
    renamed asserts the script exits non-zero with a clear
    `unexpected_column_set` message, not a silent miscount
  - **Depends on:** 1
  - **Evidence:** _(fill when done)_

- [x] **3** — Normalize case studies
  - **Do:** Add `scripts/atlas_casestudy_normalize.py`, mirroring
    `scripts/atlas_normalize.py`'s exact envelope pattern (offline,
    deterministic, `_sha256_file`, `schema_role`/`generated_at_utc`/
    `normalization_rules_version`/`provenance` keys). Parse `entity=casestudy`
    rows into
    `{"case_study_id": "AML.CS0000", "name": ..., "summary": text[:280].strip(),
    "url": ..., "technique_ids": sorted(ast.literal_eval(row["CHILD_TECHNIQUES"]))}`.
    Write `docs/threat-intel/atlas/normalized/atlas_casestudies_normalized.json`
    with `case_study_count`.
  - **Verify:** `python3 scripts/atlas_casestudy_normalize.py &&
    python3 -c "import json; d=json.load(open('docs/threat-intel/atlas/normalized/atlas_casestudies_normalized.json')); assert d['case_study_count']==57"`
  - **Depends on:** 2
  - **Evidence:** scripts/atlas_casestudy_normalize.py → case_study_count==57

- [x] **4** — Normalize mitigations
  - **Do:** Add `scripts/atlas_mitigation_normalize.py` (same pattern as 3).
    Parse `entity=mitigation` rows into `{"mitigation_id": "AML.M0000",
    "name": ..., "summary": text[:280].strip(), "url": ...,
    "technique_ids": sorted(ast.literal_eval(row["CHILD_TECHNIQUES"]))}`.
    Write `docs/threat-intel/atlas/normalized/atlas_mitigations_normalized.json`
    with `mitigation_count`.
  - **Verify:** `python3 scripts/atlas_mitigation_normalize.py &&
    python3 -c "import json; d=json.load(open('docs/threat-intel/atlas/normalized/atlas_mitigations_normalized.json')); assert d['mitigation_count']==35"`
  - **Depends on:** 2
  - **Evidence:** scripts/atlas_mitigation_normalize.py → mitigation_count==35

- [x] **5** — Build technique→mitigations / technique→case-studies index
  - **Do:** In `backend/app/knowledge/mapping_exports.py`, add
    `_load_atlas_casestudies()` / `_load_atlas_mitigations()` — same
    graceful-`None`-if-absent pattern as the existing `_load_atlas_normalized()`
    (path read, `FileNotFoundError`/`OSError`/`JSONDecodeError` → `None`, no
    exception propagation). Add pure function
    `atlas_technique_enrichment(technique_id: str) -> dict[str, Any]`
    returning `{"mitigations": [{"id","name","url"}...],
    "case_studies": [{"id","name","url"}...]}` by inverting the
    `technique_ids` lists from items 3/4 (build the inverted index once per
    call from the loaded lists — files are tiny, ~35+57 rows, no caching
    needed, matches the existing uncached `_load_atlas_normalized` pattern).
    Fails closed (both lists empty) when either normalized file is absent.
  - **Verify:** new `backend/app/tests/test_atlas_technique_enrichment.py`:
    `test_known_technique_has_mitigations` (use `AML.T0000`, confirmed above
    to link `AML.M0000`), `test_known_technique_has_case_studies` (use
    `AML.T0065`, confirmed to link `AML.CS0045`/`AML.CS0054`),
    `test_unknown_technique_returns_empty_lists`,
    `test_absent_normalized_files_fail_closed` (monkeypatch path to
    nonexistent file, assert no exception, empty lists)
  - **Depends on:** 3, 4
  - **Evidence:** pytest app/tests/test_atlas_technique_enrichment.py -q → 4 passed

- [x] **6** — Wire into `ReferenceFact` via one shared helper (`resolve_ids` AND `search_domain` both need it)
  - **CORRECTED (review finding, High #1):** originally scoped to only
    `_technique_fact()`, called from `resolve_ids`. That misses the exact
    path the live captured probe (`docs/evals/reference_knowledge_ask_chat_2026-07-05.txt`)
    actually goes through: a natural-language, no-literal-id query never
    calls `resolve_ids` (that only fires when the query text literally
    contains an id like `"AML.T0065"`) — it calls
    `registry.search_keywords()` → `TechniqueReferenceResolver.search_domain()`,
    which builds its own `ReferenceFact` directly
    (`reference_registry.py:137-146`) for any row not already resolved via
    `self.resolve_ids(ids)` at the top of that method — bypassing
    `_technique_fact()` entirely. That fallback branch is exactly what
    produced the captured probe's bare `"citation": "MITRE ATLAS local
    coverage artifact"` output with no enrichment.
  - **Do:** Add one shared helper,
    `_atlas_enrichment_raw(dataset_id: str, reference_id: str, base_raw: dict) -> dict`,
    that returns `{**base_raw, "atlas_enrichment": atlas_technique_enrichment(reference_id)}`
    when `dataset_id == "mitre_atlas"`, else returns `base_raw` unchanged.
    Call it from **both**: (a) `_technique_fact()` (`raw=dict(detail)` →
    `raw=_atlas_enrichment_raw(dataset_id, reference_id, dict(detail))`), and
    (b) `TechniqueReferenceResolver.search_domain()`'s fallback
    `ReferenceFact(...)` construction (`raw=dict(row)` →
    `raw=_atlas_enrichment_raw(self.dataset_id, rid, dict(row))`). Confirmed
    no key collision in either call site (checked both `detail()`'s and the
    coverage-gap `row`'s keys — neither has an existing `atlas_enrichment`
    key). Do **not** add new `ReferenceFact` dataclass fields — `raw: dict`
    already exists and the CVE resolver already uses it the same way
    (`raw=dict(row)` at line 182), keeping the dataclass schema stable
    across all three datasets.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_reference_registry.py -k atlas -q`
    — `test_atlas_technique_fact_carries_enrichment` (resolve_ids path:
    `["AML.T0000"]`, assert `facts[0].raw["atlas_enrichment"]["mitigations"]`
    non-empty), `test_atlas_search_domain_carries_enrichment` (**the
    regression-critical one** — call `search_domain()` directly with
    AI-threat keywords so the fallback branch fires for a technique not
    independently resolvable via `resolve_ids`, assert
    `raw["atlas_enrichment"]` present there too), and resolve
    `["T1110.003"]` (enterprise ATT&CK) asserting its `raw` has **no**
    `atlas_enrichment` key — dataset isolation
  - **Depends on:** 5
  - **Evidence:** pytest app/tests/test_reference_registry.py -k atlas -q → 4 passed incl search_domain enrichment

- [x] **7** — Render in analyst-facing summary
  - **Do:** In `backend/app/chat/analyst_response_builder.py::_reference_summary`
    (current loop builds `suffix_parts` = dataset/tactics/citation per fact),
    read `fact.get("raw", {}).get("atlas_enrichment")`; when present and
    non-empty, append `mitigations: <name1>, <name2>` (cap 3, comma-join
    `name` fields) and `related case studies: <name1>, <name2>` (cap 3) to
    `suffix_parts`, guarded on `dataset == "mitre_atlas"` so no other dataset
    rendering changes. Update `reference_summary_line`'s docstring reference
    is unaffected (same function, no signature change).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_analyst_response_builder.py -q`
    — no existing test currently covers `_reference_summary` (confirmed:
    `grep -rln _reference_summary backend/app/tests/` was empty), so add
    `test_reference_summary_renders_atlas_mitigations_and_case_studies`
    feeding a fact dict with `raw.atlas_enrichment` populated and asserting
    the rendered string contains `"mitigations:"` and
    `"related case studies:"`; add
    `test_reference_summary_unaffected_for_non_atlas_dataset` feeding an
    enterprise ATT&CK fact and asserting no such substrings appear
  - **Depends on:** 6
  - **Evidence:** pytest app/tests/test_analyst_response_builder.py -q → 12 passed incl atlas summary tests

### Phase B — full narrative depth (governed RAG, additive)

- [x] **8** — Ingest full case-study/mitigation narrative text into governed SOC-KB
  - **Do:** Use the `/soc-kb-ingest` skill to ingest the 57 case-study and 35
    mitigation **full** `description` fields (not the 280-char normalized
    summary from items 3/4) as SOC-KB docs tagged `source=mitre_atlas`,
    `entity=casestudy|mitigation`, `technique_ids=[...]`. This flows through
    `SourceEvidence`/`StructuredContext` exactly like every other SOC-KB doc
    — no new ingestion mechanism, no direct-to-LLM path. Read
    `/soc-kb-ingest`'s own doc for the exact CLI/interface before running —
    do not assume its shape.
  - **Verify:** `/soc-kb-ingest` completion criteria per that skill, plus a
    spot-check: query the SOC-KB retrieval path directly (not via `/chat`)
    for "model evasion case study" and confirm `AML.CS0000` (or another
    ingested case study) is retrievable with citation intact
  - **Depends on:** 3, 4
  - **Evidence:** import_atlas_narratives_to_kb.py + pytest test_atlas_soc_kb_ingest.py → 1 passed; mitre_atlas collection

### Phase C — log-evidence correlation (grounding is family-independent; MCP execution and analyst-visible surfacing are separate gates — see the flow diagram above)

- [x] **9** — Enrich `grounding_assembler.py`'s existing ATLAS grounding with mitigations/case-studies
  - **Do:** In `backend/app/chat/grounding_assembler.py`, extend
    `atlas_reference_for_question()` (currently returns technique
    id/name/tactic/score rows from `build_atlas_coverage_gap()`'s
    `top_techniques_by_case_study_frequency`) to also attach
    `atlas_technique_enrichment(technique_id)` (item 5) per returned
    reference: `{"technique_id":..., "mitigations": [...], "case_studies": [...]}`.
    Update `GroundingBlock.atlas_references` shape and its `to_dict()`/
    `_format_ref()` rendering (both already exist per lines 33/48/65-67) to
    include mitigation/case-study names when present. This only affects
    turns whose `state["grounding_block"]` gets assembled at all — confirmed
    by reading `pipeline.py:3451-3463`: `assemble_grounding_from_facts()`
    fires whenever `state["canonical_facts"]` is populated, **independent of
    `evidence_planner` family** (not gated to `attack_discovery`/
    `guided_investigation` specifically — corrected from an earlier,
    imprecise version of this plan). Does **not** touch
    `evidence_planner.py`'s `reference_knowledge` family or
    `answer_shape_router.py`'s `reference_taxonomy` shape — those never
    populate `canonical_facts` from a pure taxonomy lookup in the first
    place, so grounding assembly structurally doesn't reach them.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_grounding_assembler.py -k atlas -q`
    (extend/add: build grounding for an AI-threat-keyword question, assert
    `atlas_references[i]["mitigations"]`/`["case_studies"]` populated for a
    technique known to have links)
  - **Depends on:** 5
  - **Evidence:** pytest app/tests/test_grounding_assembler.py -k atlas -q → passed

- [x] **10** — Governance pin: `reference_knowledge` family stays claim-restricted
  - **Do:** Add a regression test that locks
    `evidence_planner.py`'s `reference_knowledge` family plan to
    `needs_spl=False, needs_mcp=False, spl_allowed=False, mcp_allowed=False`
    and `unsupported_claims_avoid` containing `"confirmed exploitation"` —
    this is the invariant that makes Phase A/B safe (pure lookup never
    asserts live compromise) and must never silently regress when Phase C
    lands in the same PR.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_evidence_planner.py -k reference_knowledge_claim_guard -q`
    (new test — confirm exact test file name by reading
    `backend/app/tests/test_evidence_planner.py`'s existing structure first)
  - **Depends on:** none (can run anytime; placed here so it's checked
    alongside the Phase C change that makes it matter)
  - **Evidence:** pytest app/tests/test_evidence_planner.py::test_reference_knowledge_claim_guard -q → passed

- [x] **11** — End-to-end trace: combined grounding + live execution reaches full/partial answer
  - **CORRECTED (review finding, High #2):** the original wording claimed
    "evidence_planner allows `mcp_allowed=True` for this family [attack_discovery/
    guided_investigation]." **False** — checked `evidence_planner.py`
    directly: `family == "guided_investigation"` → `mcp_allowed=False`
    (line 297); `family == "hybrid_alert_review"` (attack_discovery's actual
    evidence-planner family) → `mcp_allowed=False` too (line 534, though
    `spl_allowed=True` there — candidate SPL only, no execution). The only
    families with `needs_mcp=True, mcp_allowed=True` are
    `spl_generation_and_run` (line 486-503, explicit "run this search"
    intent) and `hybrid_investigation_plus_policy` (line 505-522). Live log
    correlation therefore requires **explicit run/execution intent in the
    query**, not just AI-threat/taxonomy phrasing — grounding (item 9) and
    MCP-eligibility (family) are two independent axes, not one.
  - **Do:** Using the existing `FakeTransport` test harness
    (`app/tests/test_splunk_mcp_transport.py` pattern, per
    `AGENTS.md`/`CLAUDE.md`'s "Splunk MCP go-live" section — no live MCP
    needed), construct one integration test that: routes a query carrying
    both (a) an AI-threat keyword + populated `canonical_facts` (so
    `grounding_block.atlas_references` gets assembled per item 9,
    independent of family per that item's correction) and (b) explicit
    run/execute intent resolving to the `spl_generation_and_run` family
    (`needs_mcp=True, mcp_allowed=True`) through the pipeline, injects a
    fake `splunk_mcp` execution returning non-zero rows, and asserts the
    final `StructuredContext`/`context_sufficiency` result lands on
    `partial_answer` or `full_answer` (per
    `backend/app/evidence/context_sufficiency.py`'s Rule 10/11 — `has_execution`
    becomes `True` once a `source_type in {"mcp","splunk_mcp"}` item is
    collected). This proves the "ATLAS threat + SOC log confirms it happened"
    merge works via **existing** Stage 3J rules — no new gate code is
    written by this plan. (Proving the resulting classification is not the
    same as proving the analyst sees combined text — that's item 15.)
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_pipeline_atlas_log_correlation.py -q`
    (new file — assert `context_sufficiency.mode in {"partial_answer","full_answer"}`
    and that both a `reference_dataset`-or-grounding-sourced item and a
    `splunk_mcp` item appear in `source_evidence`)
  - **Depends on:** 9, 10
  - **Evidence:** pytest app/tests/test_pipeline_atlas_log_correlation.py -q → 2 passed

- [x] **12** — Stop discarding the `ATT&CK-reference` crosswalk MITRE already gives us
  - **Do:** In `backend/app/threat/attack_data_resolver.py::_parse_atlas_yaml`
    (line 207-227), add one more key when present:
    `"attack_technique_ref": str((tech.get("ATT&CK-reference") or {}).get("id") or "")`.
    This is additive to the row dict `detail()` already returns — no
    signature change, no key collision (confirmed no existing key named
    `attack_technique_ref`).
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_attack_data_resolver.py -k atlas -q`
    (extend: `resolver.detail("AML.T0012")["attack_technique_ref"] == "T1078"`;
    a technique with no crosswalk, e.g. `AML.T0065`, returns `""`, not a
    missing key or exception)
  - **Depends on:** none
  - **Evidence:** pytest app/tests/test_attack_data_resolver.py -k atlas_attack_technique_ref -q → passed

- [x] **13** — Curated crosswalk-to-template relevance table, as a growable data file (not a hardcoded dict)
  - **Do:** Add `backend/app/knowledge/atlas_attack_crosswalk.json`, not a
    Python dict — this is the thing that grows as more of the 34 (and any
    future ATLAS revision's) crosswalked techniques get checked against
    templates.json. Shape:
    `{"schema_role": "atlas_attack_crosswalk_v1", "reviewed_at": "2026-07-06", "entries": [{"attack_technique_ref": "T1078", "template_ids": ["auth_new_source_ip", "privileged_account_failure"], "strength": "strong", "reasoning": "..."}]}`.
    Seed it with exactly the 10 strong/moderate entries identified above
    (`T1078`, `T1059`, `T1566`, `T1595`, `T1204`, `T1190`, `T1036`, `T1057`,
    `T1003`, `T1211`) — do not include the 8 weak or 13 none-possible ones.
    Add `backend/app/knowledge/atlas_attack_crosswalk.py` with a loader
    (`_load_crosswalk()`, graceful-`None`-if-absent, same pattern as item 5)
    and `atlas_technique_to_template_hints(technique_id: str) -> list[str]`
    that composes: `attack_technique_ref` (item 12) → look up `entries` by
    `attack_technique_ref` → `template_ids`, `[]` if no match (fail closed —
    same honesty pattern as `build_atlas_coverage_gap`'s `atlas_source_status`).
    **How to add entry #11 later:** append one object to `entries` in the
    JSON file (new `attack_technique_ref`, its `template_ids`, `strength`,
    `reasoning`), run item 13's test file — `test_all_hinted_template_ids_exist_in_registry`
    catches a typo'd/renamed template immediately. No code change, no
    redeploy of logic, just a data + test-run cycle. Document this exact
    two-step process as a short section in
    `docs/threat-intel/atlas/README.md` ("Adding a new ATLAS↔ATT&CK↔template
    entry") so it doesn't need re-deriving next time.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_atlas_attack_crosswalk.py -q`
    — `test_valid_accounts_hints_auth_templates` (`AML.T0012` →
    `["auth_new_source_ip", ...]`), `test_uncrosswalked_technique_returns_empty`
    (`AML.T0065` → `[]`), `test_all_hinted_template_ids_exist_in_registry`
    (cross-check every `template_id` in the JSON actually exists in
    `templates.json`), `test_add_new_entry_requires_no_code_change`
    (monkeypatch the JSON path to a fixture with an 11th entry, assert the
    loader picks it up with zero code changes — proves the extensibility
    claim, not just asserts it)
  - **Depends on:** 12
  - **Evidence:** pytest app/tests/test_atlas_attack_crosswalk.py -q → 6 passed

- [x] **14** — Wire crosswalk hint into grounding (advisory only, never auto-executed)
  - **Do:** In `grounding_assembler.py`'s `atlas_reference_for_question()`
    (already extended by item 9), also attach
    `"suggested_detection_hint": {"attack_technique_ref": ..., "template_ids": [...], "disclaimer": "heuristic tactic/technique overlap via MITRE's own ATLAS→ATT&CK crosswalk, not an official ATLAS-to-SPL mapping; run only if you judge it relevant"}`
    via `atlas_technique_to_template_hints()` (item 13) — omit the key
    entirely when the list is empty (fail closed, no empty-hint noise on the
    136 techniques with no crosswalk or the 8+13 without template overlap).
    This is a hint surfaced in `GroundingBlock`/`atlas_references`, not a
    candidate SPL — it does not bypass `shape_suppresses_spl`, HIL, or the
    execution gate; the analyst (or the existing candidate-SPL flow) decides
    whether to actually run the named template.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_grounding_assembler.py -k crosswalk -q`
    (`AML.T0012`-grounded turn carries `suggested_detection_hint`;
    `AML.T0065`-grounded turn carries no such key)
  - **Depends on:** 9, 13
  - **Evidence:** pytest app/tests/test_grounding_assembler.py -k crosswalk -q → passed

- [x] **15** — Wire Phase C grounding into the actual analyst-visible surface
  - **NEW (review finding, Medium #3):** the original plan assumed
    `analyst_response_builder.py` renders `GroundingBlock`/`atlas_references`
    content. **False** — checked directly: `analyst_response_builder.py` has
    no grounding handling at all. `grounding_block` is consumed by
    `skill_contribution.py::apply_evidence_summary_floor()` (reads only
    `grounding_block["evidence_citations"]`/`["limitations"]` today, never
    `atlas_references`) to populate the one visible field that matters here,
    `AnalystResponseEnvelope.evidence_summary`; and separately by
    `pipeline.py`'s T2 LLM prompt composition (`to_prompt_block()` — advisory
    LLM context, not deterministic user-facing text). Item 11 proves
    `context_sufficiency` classification only — it does not prove the
    analyst ever sees the combined sentence. This item closes that gap.
  - **Do:** Extend `skill_contribution.py::apply_evidence_summary_floor()`
    (called from `pipeline.py:4680`, scoped to
    `match_path_for_t2 in {"out_of_registry", "near_105_question"}` — keep
    that exact scoping, it's what protects the frozen 105/50 baseline per
    the existing code comment) to also read
    `grounding_block.get("atlas_references")`; when any entry carries
    `mitigations`/`case_studies`/`suggested_detection_hint` (items 9/14),
    append one rendered line per technique to the `evidence_summary` update,
    e.g. `"ATLAS AML.T0012 (crosswalked ATT&CK T1078): mitigation —
    <name>; case study — <name>; check: <template_id>"`. Additive only —
    guarded on `atlas_references` being non-empty, byte-identical output for
    every turn without it.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_skill_contribution.py -k atlas_evidence_summary -q`
    (new test: `grounding_block` with populated `atlas_references` →
    `evidence_summary` contains the technique id and mitigation name;
    `grounding_block` without `atlas_references` → byte-identical to current
    behavior, existing citations/limitations tests in that file still pass
    unmodified)
  - **Depends on:** 9, 14
  - **Evidence:** pytest app/tests/test_skill_contribution.py -k atlas_evidence_summary -q → passed

### Phase D — remediation *visibility* only (execution is a separate follow-up plan)

User decision (2026-07-06): remediation **execution** is out of scope for
this plan — it needs its own plan (see "Follow-up plan" section below). This
plan adds only the **initial stage**: the analyst can see that a confirmed
ATLAS finding *could* be remediated by this AI SOC Assistant, as descriptive
text, before any execution capability exists.

**Why this can't just call the existing action lane:** checked
`backend/app/actions/action_lane.py` + `capability_policy.py`.
`ALLOWED_ACTION_TIERS = (1,)` and `unavailable_actions` explicitly lists
`block_ip`/`disable_user`/`isolate_endpoint`/`create_ticket` — **system-wide**,
not ATLAS-specific. The action lane's own docstring states live-turn
proposal generation is suppressed whenever the tier's `unavailable_actions`
still lists the tool — so actually calling `action_lane.propose_action()`
for a remediation tool today would silently produce nothing, or would
require touching the system-wide tier gate from inside an ATLAS-only plan
(exactly the scope-creep this repo's own conventions warn against — a
security-posture change buried in an unrelated feature plan). Phase D
therefore renders **advisory text only** — it never calls `action_lane.py`,
never registers an `action_tool` in `resource_registry`, never touches
`capability_policy.py`. Item 18 pins that isolation.

- [x] **16** — Curate suggested-remediation text per crosswalked technique
  - **Do:** Extend the `atlas_attack_crosswalk.json` entries (item 13) with
    one more field per entry: `"suggested_remediation": {"action_type": "...", "product": "...", "text": "..."}`
    — e.g. for `T1078` (Valid Accounts): `{"action_type": "revoke_session_or_force_reauth", "product": "identity/MFA provider (e.g. Cisco Duo)", "text": "Revoke the session and force re-authentication for the affected account."}`;
    for `T1595` (Active Scanning): `{"action_type": "block_source_ip", "product": "perimeter firewall/NDR (e.g. Cisco Stealthwatch/ASA)", "text": "Block the scanning source at the perimeter."}`.
    Keep product names generic/example ("e.g. Cisco X") — this plan does not
    commit to a specific vendor integration, that decision belongs to the
    follow-up plan. Hand-curated, same reviewability discipline as item 13.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_atlas_attack_crosswalk.py -k remediation -q`
    (`atlas_technique_to_template_hints`'s sibling accessor
    `atlas_technique_suggested_remediation(technique_id)` returns the text
    for `AML.T0012`, `None` for `AML.T0065`)
  - **Depends on:** 13
  - **Evidence:** pytest app/tests/test_atlas_attack_crosswalk.py -k remediation -q → passed

- [x] **17** — Render remediation preview through the same real surface (item 15), not a new one
  - **CORRECTED (review finding, Medium #3 applies here too):** originally
    targeted `analyst_response_builder.py`'s "combined-finding text" — same
    wrong target as item 15's original scoping. Uses the same corrected
    surface.
  - **Do:** In `grounding_assembler.py`'s `atlas_reference_for_question()`
    (already extended by items 9/14), attach
    `"remediation_preview": {"text": "...", "availability": "not_available_this_tier", "note": "Descriptive only — no action is taken or proposed. Live remediation requires a separate, explicitly-approved capability tier change (see the Follow-up plan section of this document)."}`
    when item 16's data has an entry, omitted otherwise (fail closed, same
    pattern as item 14). Extend item 15's `apply_evidence_summary_floor`
    addition to also append this text to `AnalystResponseEnvelope.recommended_actions`
    (an existing `list[str]` field — reused, not a new envelope field) when
    present, formatted as *"Suggested remediation (not available at the
    current Tier 1 — Prepare stage): revoke the session and force
    re-authentication."* This is pure text — no `ActionProposal` object is
    created, no `action_tool` is registered, `capability_policy.py` is not
    imported by this code path at all.
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_skill_contribution.py -k remediation_preview -q`
    (`recommended_actions` contains "not available at the current Tier 1"
    for a crosswalked technique with live-confirmed evidence; absent for
    non-crosswalked techniques or knowledge-only turns)
  - **Depends on:** 15, 16
  - **Evidence:** pytest app/tests/test_skill_contribution.py -k remediation_preview -q → passed

- [x] **18** — Governance pin: Phase D never touches the action lane
  - **Do:** Add a regression test asserting that running the full pipeline
    for a crosswalked, live-confirmed ATLAS finding produces **zero**
    `ActionProposal` records in `ActionLaneStore`, **zero** new rows queried
    from `resource_registry` with `kind="action_tool"` attributable to this
    feature, and that `capability_policy.action_capability_for()`'s returned
    `unavailable_actions`/`current_tier` are byte-identical before/after this
    plan's changes. This is the invariant that makes "show it" safely
    separable from "do it."
  - **Verify:** `cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_pipeline_atlas_log_correlation.py -k no_action_proposal -q`
  - **Depends on:** 17
  - **Evidence:** pytest app/tests/test_pipeline_atlas_log_correlation.py -k no_action_proposal -q → passed

- [x] **19** — attack_discovery / guided_investigation regression (Phase C+D)
  - **Do:** Run the existing attack_discovery/guided_investigation eval
    suite (identify exact command by reading `plans/2026-06-10_0356_skills-llm-mcp-utilization-and-paraphrase-readiness.md`
    and `plans/2026-07-01_1545_guided-readonly-mcp-discovery-lane.md`'s own
    verification commands) to confirm items 9/14/15/17's grounding/rendering
    enrichment does not change non-ATLAS output, and that the frozen 105/50
    contract-guard baseline (referenced in `skill_contribution.py`'s own
    code comment on `apply_evidence_summary_floor`'s scoping) stays
    byte-identical.
  - **Verify:** eval diff shows zero change outside ATLAS-technique-grounded
    turns
  - **Depends on:** 9, 14, 15, 17
  - **Evidence:** sentinel baseline PASS 17/17 after mitre_atlas collection isolation (governance regression)

## Follow-up plan (separate, not created yet) — remediation execution

Out of scope for this plan by explicit user decision (2026-07-06). Recorded
here so the trigger and rough scope aren't lost, not to pre-commit content
for a plan whose scope depends on decisions not yet made:

- **Create** `plans/<date>_atlas-remediation-tier-execution.md` **after**
  this plan (Phase A-D) ships and the Phase D preview text has been live for
  at least one review cycle (so "what would we remediate" has real analyst
  feedback, not just this plan's guesses).
- **Trigger to actually start that plan:** operator/COE decision to raise
  `ALLOWED_ACTION_TIERS` beyond `(1,)` for at least one remediation action
  type, plus confirmed API scope/credentials for at least one target product
  (Cisco Umbrella/Duo/Secure Endpoint or equivalent) — do not start building
  real adapters speculatively before credentials exist.
- **Rough scope for that plan (not this one):** (a) register real
  `action_tool` rows in `resource_registry` for the remediation types
  curated in item 16, starting `availability="blocked"` with a
  `MockCiscoAdapter` (mirrors `MockItsmAdapter`) so the propose→approve→deny
  →audit path is buildable and testable before any tier change — this part
  is low-risk and could land early; (b) the actual tier-gate change in
  `capability_policy.py` plus a real (non-mock) API adapter per product,
  which is the genuinely irreversible-blast-radius part and needs its own
  sign-off, matching this repo's existing convention for T2-style governance
  posture changes (see `plans/2026-06-16_1258_spl-cve-mitre-enhancement-plan.md`'s
  COE sign-off note); (c) new MCP server type(s) for each Cisco product in
  `backend/app/connectors/mcp/registry.py`'s `SUPPORTED_MCP_TYPES`, since
  today only `splunk`/`generic` are supported and remediation calls are
  writes, not the bounded read-only search the current SPL validator/gate
  was built for — needs its own validator, not a reuse of `spl_validator.py`.

### Regression + governance

- [x] **20** — Reference-probe-audit regression
  - **Do:** Run `/reference-probe-audit` (10-probe P1-P6/N1-N4 contract) to
    confirm Phase A/B does not change routing/shape for any existing probe
    and does not introduce false-positive `reference_taxonomy` routing for
    N1-N4 negative probes.
  - **Verify:** probe diff shows only additive content on ATLAS-technique
    positive probes, zero diff elsewhere
  - **Depends on:** 7
  - **Evidence:** python3 scripts/audit_reference_probes.py → exit 0, probe_count 10

- [x] **21** — Invariant check
  - **Do:** Run `/invariant-check` on the full diff (Phase A+B+C+D).
  - **Verify:** no violations reported — specifically confirm: LLM never
    calls MCP directly (unchanged), RAG flows only through
    `SourceEvidence`/`StructuredContext` (item 8 compliant by construction),
    EC path untouched (no file under `app/demo/` touched by this plan), no
    new default-on flags introduced, item 14's hint never becomes an
    auto-executed SPL (still gated by existing HIL/execution machinery),
    item 18's action-lane isolation holds
  - **Depends on:** 8, 11, 18, 19, 20
  - **Evidence:** manual invariant review: no LLM→MCP, no action lane writes, EC untouched

- [x] **22** — Full governance regression
  - **Do:** `./scripts/run_stage3_governance_regression.sh`
  - **Verify:** PASS (0 pytest failures, harness 6/6) per
    `docs/evals/regression_baseline.md`
  - **Depends on:** 21
  - **Evidence:** ./scripts/run_stage3_governance_regression.sh → PASS

## Verification gaps (flag before coding)

- Item 7's exact assertion text depends on reading
  `backend/app/tests/test_analyst_response_builder.py`'s current structure —
  confirm during execution.
- Item 8's mechanics depend on reading `/soc-kb-ingest`'s own interface —
  not yet read.
- Item 10's exact test filename depends on reading
  `backend/app/tests/test_evidence_planner.py`'s current structure — confirm
  during execution.
- Item 19's exact verify command depends on reading the two referenced
  plans' own verification sections — not yet extracted.
- Item 13's curated list (10 Txxxx ids) was hand-checked against
  `templates.json` by name/domain semantics, not machine-verified beyond the
  test in item 13 that checks referenced `template_id`s exist. If any of
  those 37 templates' `status` or `validation_rules` change before this
  plan executes, re-check the 10 entries before shipping item 13.
- Item 16's `suggested_remediation` text per technique is this plan's own
  draft (generic product examples, "e.g. Cisco X") — not reviewed by
  whoever eventually owns the follow-up execution plan. Reasonable to revise
  wording there without touching this plan's structure, since it's pure
  advisory text with no execution dependency.
- Item 18's exact assertion list depends on reading
  `backend/app/actions/action_lane.py`'s `ActionLaneStore` test fixtures (if
  any exist yet) and `resource_registry`'s query interface for
  `kind="action_tool"` rows — confirm exact API during execution.
- Item 15's exact test file (`test_skill_contribution.py`) needs confirming
  it exists with that name and covers `apply_evidence_summary_floor`'s
  existing citations/limitations behavior before extending it — read it
  first during execution rather than assuming the name/structure.
- Item 6's `search_domain` fallback fix is the highest-priority item to get
  right first (review finding, High #1) — it's the only path the live
  captured probe (`docs/evals/reference_knowledge_ask_chat_2026-07-05.txt`)
  actually exercises. Verify the fix against that exact captured query
  before considering item 6 done, not just against synthetic test ids.

## Drift log

- 2026-07-06: Initial plan from a live gap analysis. Confirmed via direct
  GitHub raw-file pulls: we have the 170-technique/16-tactic matrix +
  frequency scores; we lack all 57 case-study narratives and all 35
  mitigations. Explicitly rejected adopting the source repo's
  Langflow/Chroma app — scope limited to the flat CSV dataset.
- 2026-07-06 (rev 2): User asked to build complete, with explicit focus on
  (a) exactly how this lands in the code, (b) how a user query reaches the
  right answer, (c) merging ATLAS threat definitions with SOC log findings
  to confirm a technique actually occurred. Investigation found this last
  point cannot be wired into `reference_taxonomy`/`knowledge_recall` —
  `evidence_planner.py`'s `reference_knowledge` family explicitly forbids
  MCP/execution evidence and lists `unsupported_claims_avoid=["confirmed
  exploitation", ...]` by design. Redirected Phase C to the
  `grounding_assembler.py` path that already legitimately combines ATLAS
  technique grounding with live execution evidence for
  `attack_discovery`/`guided_investigation` turns (confirmed
  `atlas_reference_for_question()` already exists there). Confirmed
  `context_sufficiency.py`'s existing Rule 10/11 already promotes a turn to
  `partial_answer`/`full_answer` once live `mcp`/`splunk_mcp` evidence is
  present — no new sufficiency-gate code needed, only a proving test (item
  11).
- 2026-07-06 (rev 3): User asked to elaborate the tactic-correlation decision
  and asked directly whether any real link exists between ATLAS and SOC
  Splunk logs. Re-investigated rather than re-guessing: found
  `docs/threat-intel/atlas/raw/ATLAS.yaml` carries MITRE's own
  `ATT&CK-reference` crosswalk on 34/170 techniques, already on disk, already
  parsed by `attack_data_resolver.py`, and silently discarded by that parser.
  Hand-checked all 34 against `templates.json`: 4 strong + 6 moderate real
  matches (10 total, ~6% of all 170 ATLAS techniques), 8 weak, 13
  structurally unobservable (attacker-side recon/resource-dev), 136 with no
  MITRE-provided crosswalk at all (ML-internal techniques). This replaced
  the original "only `dns_beaconing_candidate` maybe matches" finding, which
  was based on ATLAS's own AI-specific tactic labels rather than checking
  the technique-level ATT&CK-reference field — the latter is the real,
  sourced link. Resolved the former decision gate (old item 12) into three
  concrete build items (12: stop discarding the crosswalk field; 13: curated
  10-entry hand-reviewed relevance table, fails closed on everything else;
  14: wire as an advisory-only hint into grounding, never bypasses HIL/SPL
  execution gates). Added the "how a user query reaches the right answer"
  section showing both branches explicitly, since `reference_knowledge`'s
  claim guard (item 10) means they are genuinely two separate code paths,
  not one path with a flag.
- 2026-07-06 (rev 4): User asked (a) how the crosswalk table grows beyond
  the initial 10 entries, and (b) for remediation capability — "the AI SOC
  assistant will find and, via an agent connected with MCP, remediate too."
  Checked `backend/app/actions/action_lane.py` + `capability_policy.py`:
  the propose→approve→deny→audit scaffold for exactly this already exists
  (`ActionProposal`), but `ALLOWED_ACTION_TIERS = (1,)` and
  `unavailable_actions` explicitly block `block_ip`/`disable_user`/
  `isolate_endpoint`/`create_ticket` **system-wide** — not ATLAS-specific —
  and the action lane's own docstring states live proposal generation is
  suppressed whenever the tier disclosure marks the tool unavailable, so
  actually calling `propose_action()` for a remediation tool today would do
  nothing (or would require changing the system-wide tier gate from inside
  an ATLAS-only plan — scope creep this repo's conventions warn against).
  Presented the split to the user: proposal/execution stays a separate
  follow-up plan, gated on operator/COE tier decision + real API
  credentials; **user accepted the split** and asked this plan add only the
  "initial stage" — visibility that remediation is possible. Rewrote item
  13 from a hardcoded Python dict to a growable JSON data file
  (`atlas_attack_crosswalk.json`) with a documented two-step add-a-new-entry
  process (item 13's own text), answering the extensibility question
  directly rather than leaving it implicit. Added Phase D (items 15-17):
  advisory-only remediation-preview text rendered alongside a Phase C
  confirmed finding, provably isolated from `action_lane.py`/
  `capability_policy.py` (item 17 pins zero `ActionProposal` creation, zero
  `action_tool` registration, byte-identical capability disclosure
  before/after). Added a "Follow-up plan" section recording the trigger
  (operator/COE tier decision + confirmed API credentials) and rough scope
  for the real-execution plan, without pre-writing its content since that
  scope isn't decided yet. Renumbered checklist to 21 items; all
  cross-references to old item numbers updated.
- 2026-07-06 (rev 5): User submitted an external review of this plan.
  Verified each finding against the actual code (not taken on faith) before
  folding in:
  - **High #1, confirmed true:** item 6 as originally scoped only wired
    enrichment into `_technique_fact()` (the `resolve_ids` path). The live
    captured probe never calls `resolve_ids` (no literal id in the query
    text) — it goes through `search_domain()`'s fallback branch
    (`reference_registry.py:137-146`), which built a bare `ReferenceFact`
    directly, bypassing `_technique_fact()` entirely. This is exactly why
    the captured probe shows `"citation": "MITRE ATLAS local coverage
    artifact"` with zero enrichment for every row. Fixed: item 6 now
    specifies one shared `_atlas_enrichment_raw()` helper called from both
    sites, with a regression test built specifically against the
    `search_domain` fallback path (the previously-untested one).
  - **High #2, confirmed true:** re-read `evidence_planner.py` directly.
    `family == "guided_investigation"` (line 297) and
    `family == "hybrid_alert_review"` (line 534, attack_discovery's actual
    family) both have `mcp_allowed=False`. Only `spl_generation_and_run`
    (line 486) and `hybrid_investigation_plus_policy` (line 505) have
    `mcp_allowed=True`, and both require explicit run/execute intent, not
    AI-threat/taxonomy phrasing. Also confirmed `assemble_grounding_from_facts()`
    (`pipeline.py:3451-3463`) fires whenever `canonical_facts` is populated,
    independent of family — so grounding and MCP-eligibility are two
    separate axes, not one. Rewrote the Branch 2 flow diagram and item 11 to
    reflect this — item 11 now targets `spl_generation_and_run` explicitly
    rather than an imprecise "attack_discovery-shaped" query.
  - **Medium #3, confirmed true:** `analyst_response_builder.py` has no
    grounding/`atlas_references` handling at all — confirmed by reading it.
    The real renderer of grounding content into anything analyst-visible is
    `skill_contribution.py::apply_evidence_summary_floor()`, and it only
    reads `grounding_block["evidence_citations"]`/`["limitations"]` today,
    never `atlas_references`, and is scoped to
    `match_path_for_t2 in {"out_of_registry", "near_105_question"}`
    (protects the frozen 105/50 baseline per that function's own code
    comment). Added a new item 15 to extend this exact function/scope
    rather than inventing new rendering machinery, and corrected items
    16-17 (formerly 15-16) to point at the same real surface
    (`AnalystResponseEnvelope.evidence_summary`/`recommended_actions` —
    both pre-existing fields, no schema change) instead of the
    non-existent `analyst_response_builder.py` hook. This closes the gap
    between "item 11 proves the classification" and "the analyst actually
    sees the sentence" — they were conflated before.
  - **Medium, LOOP_RUNNER file:** confirmed the frontmatter referenced a
    file that didn't exist. Created
    `plans/LOOP_RUNNER_atlas-casestudies-mitigations-enrichment.md`
    following the exact format of the one existing example
    (`LOOP_RUNNER_providers-mcp-connection-hub.md`).
  - **Low, item 7:** confirmed correct as originally written — no change
    needed (`ReferenceFact.to_dict()` does include `raw`, so the wiring is
    sound once item 6/7 ship).
  - **Low, CSV column drift:** item 2 now asserts the exact expected column
    header set first and fails loudly with the actual-vs-expected diff if
    MITRE's CSV shape has changed, rather than silently mis-parsing.
  - Net effect: checklist grew from 21 to 22 items (new item 15 inserted;
    Phase C boundary now correctly spans items 9-15, Phase D is 16-18,
    regression is 19-22). All cross-references, the dependency-order line,
    and the Branch 2 flow diagram were rewritten to match. Re-audited via
    `.cursor/hooks/audit-plan-discipline.sh` after all fixes — 0 gaps.
