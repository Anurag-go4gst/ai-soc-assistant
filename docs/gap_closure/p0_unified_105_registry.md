# P0-6 / P0-7 — Unified 105+ Question Registry (Target Model)

**Status:** Documentation and schema extension design (P0). **Not** a single live authority table on `/chat` yet.

## Purpose

COE and engineering need **one row per SOC question** that joins planning metadata (operation, design-time routability, MITRE, MCP needs) without maintaining parallel shadow systems. Today the data is split across artifacts; this doc defines the **target unified registry** and how it relates to what is already committed.

## Three surfaces (live vs EC vs shadow)

| Surface | Entry point | Routing authority | Answer |
|---------|-------------|-------------------|--------|
| **Live `/chat`** | [`routes_chat.py`](../../backend/app/api/routes_chat.py) | **4 legacy intents** (`selected_skill` via [`deterministic_router.py`](../../backend/app/routing/deterministic_router.py)) | No final synthesis; gates + trace + sufficiency |
| **Shadow / planning** | [`question_runtime_map_v1.json`](../../backend/app/coverage/question_runtime_map_v1.json), S6.2 report | **None on live** — observation, eval buckets, route-plan shadow | N/A |
| **Experience Center** | [`routes_scenarios.py`](../../backend/app/api/routes_scenarios.py), [`scenarios.py`](../../backend/app/demo/scenarios.py) | **`expected_skill`** (4 intents) for demo scripts | Golden `coe_synthetic_fixture` answers |

**Deck rule:** *105 mapped in shadow ≠ 105 live-routable.* Live authority today is allowlist-scoped operation authority ([`route_authority_gate.py`](../../backend/app/routing/route_authority_gate.py), e.g. `cov.q046` only when flags permit).

## Target row schema (105+, extensible to q106+)

Author via [`tools/coverage_authoring/coverage_drafter.py`](../../tools/coverage_authoring/coverage_drafter.py) and builders — **do not hand-edit** the 105 JSON maps.

```text
question_ref                 # e.g. q0.q046
question_text
taxonomy_pattern             # pattern_type from taxonomy
primary_operation            # runtime operation (10 seed catalog today; open ops in P2)
operation_provenance         # registry | llm_proposed | promoted_from_audit (P2+)
design_dependency_bucket     # rename target for provisional_status (S6.2)
likely_routable              # bool derived: design_dependency_bucket == likely_routable
pattern_id / coverage_id     # when Q4A promoted (manifest)
preconditions[]              # S7 contract (shadow today; live gate target)
mitre_permitted[]            # P5 — SOC-approved technique IDs (report-first in P5-6)
mcp_evidence_needs[]         # P3 — splunk_run_query, metadata, lookup, … (report-first)
rag_collections[]
legacy_intent_hint           # TEMP mirror of 4 intents; non-authoritative on live after P2-9
```

### P0-7 extension columns (author-time, report-first)

| Column | Source today | P0/P5 deliverable |
|--------|--------------|-------------------|
| `mitre_permitted[]` | Taxonomy `suggested_MITRE_candidates` (docs) + use-case `mitre_candidates` — **not joined live** | P5-6 builder populates report; P5-7 synthesis gate |
| `mcp_evidence_needs[]` | Full matrix on **10** manifest rows in [`pattern_coverage_v1.json`](../../backend/app/coverage/pattern_coverage_v1.json); deterministic record via [`evidence_mcp_mapping.py`](../../backend/app/orchestration/evidence_mcp_mapping.py) | P3-7/P3-9 operation→needs matrix in registry export |

## Current artifacts mapped to target columns

| Target column | Committed artifact | Live on `/chat`? |
|---------------|-------------------|------------------|
| `question_ref`, `question_text`, `taxonomy_pattern` | Taxonomy + S6.1 map | Hint only |
| `primary_operation` | S6.1 `proposed_primary_skill` | Shadow in `route_plan_shadow` only |
| `design_dependency_bucket` | S6.2 `provisional_status` in [`stage3l_s6_105_question_operation_map.json`](../stage3l_s6_105_question_operation_map.json) | **No** — planning only |
| `likely_routable` | Derived: `provisional_status == likely_routable` (48 rows) | **No** |
| `coverage_id` | Manifest overlay on map row | Authority only if allowlisted |
| `legacy_intent_hint` | S6.1 `legacy_router_intent_hint` | **Yes** — still drives `selected_skill` |
| `mitre_permitted[]` | Not on map row | Partial via use-case keyword bridge (~2 techniques in runtime subset) |
| `mcp_evidence_needs[]` | Manifest rows (10) | Deterministic tool **record** only; execution gated |

## Regenerate maps (drift check)

```bash
export PYTHONPATH=backend
python tools/coverage_authoring/coverage_drafter.py --emit-maps
python tools/coverage_authoring/check_question_operation_map.py
```

## Related docs

- S6.2 provisional report: [`../stage3l_s6_105_question_operation_map.md`](../stage3l_s6_105_question_operation_map.md)
- Layered registry design (intent vs operation vs stage): [`../stage3l_s4_layered_registry_design.md`](../stage3l_s4_layered_registry_design.md)
- Stakeholder narrative for 48 / MITRE: [p0_stakeholder_48_routable_and_mitre.md](p0_stakeholder_48_routable_and_mitre.md)

## Unchanged in P0 (explicit)

- `/chat` **4-intent** routing authority
- MCP real execution
- Final LLM synthesis
- Experience Center rebase (P2-EC)
