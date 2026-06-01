# P0-11 — Deck / Demo Zero-Ambiguity Pack (COE)

Use this pack alongside [p0_live_flow_check_profile.md](p0_live_flow_check_profile.md) and [p0_trace_demo_labels.md](p0_trace_demo_labels.md).

## 1. Headline (exact positioning)

```text
We are enabling the full governed control flow for inspection:
query understanding → registry/operation routing → LLM advisory → validation →
MITRE candidate mapping → MCP/RAG evidence envelope → sufficiency → guarded answer path.

Production execution remains gated by allowlists, COE MCP contract, SOC-approved RAG,
MITRE approvals, SPL validation, and human review.
```

## 2. Plan-complete one-liner

```text
No component treats selected_skill as routing authority; the legacy field may still
appear in trace as compatibility/debug until Experience Center rebase.
```

## 3. Red-line statements (never say in deck/demo)

```text
NEVER say:
  "LLM routes the query"           → "LLM proposes; registry/authority decides"
  "105 questions work today"       → "105 mapped; N allowlisted for live authority"
  "MCP is integrated"              → "mock/stub" OR "COE live" — which one?
  "MITRE is mapped"                → supported / candidate / not_mapped — which status?
  "Final answer is production-ready" → system_check / lab / production — which mode?

ALWAYS show on demo responses:
  flow_mode, route_authority, legacy_intent_authority=false,
  llm_semantic_intent_authority=false, evidence_origin, answer_mode
```

## 4. Red-line slide (architecture)

```text
This demo enables the full control-plane visibility aggressively.
It does not bypass governance. Anything not backed by live MCP, approved RAG,
SOC-approved MITRE, allowlisted coverage, and guard validation is labeled as
system-check, candidate, stub, shadow, or HIL.
```

## 5. Truth table

| Question | Deck answer |
|----------|-------------|
| Is the old 4-intent router still the live brain? | **No (target).** Compatibility mirror until EC/client migrate. |
| Does LLM decide intent? | **Proposes** candidates; deterministic registry/coverage authority decides. |
| Are all 105 questions live-routable? | **No.** Live authority = allowlist + promotions + COE inputs. |
| Can we see all 105 flow behavior? | **Classification/trace in system-check** for all rows; **execute** only allowlisted + promoted patterns. |
| Does MITRE work without SOC approval? | **Candidate** mapping in lab; production citation requires `supported` / `mitre_permitted[]`. |
| Does RAG work without SOC corpus? | **Stub/fixture only** for system check. |
| Does MCP execute? | **Mock/stub only** when **both** `MCP_GLOBAL_EXECUTION_ENABLED` and `MCP_SERVER_MOCK_EXECUTION_ENABLED` are true; not COE live. |
| Does final answer work? | **Deterministic/lab** can be shown; production requires evidence + sufficiency + guard sign-off. |

## 6. Confusable pairs (memorize)

| Pair | Correct distinction |
|------|---------------------|
| Flow visible vs production evidence | System-check = full trace + stubs; production = live MCP + approved RAG + `mitre_permitted[]` |
| 105 registry mapped vs 105 live-routable | All rows classifiable in trace; only allowlisted coverage executes |
| LLM proposed vs LLM decided | All `*_authority` false unless signed lab exception |
| 10 operations vs 10 MCP tools | Operations = analytic work types; MCP = Splunk execution channel |
| 48 routable vs precondition pass | 48 = design bucket; S7 = runtime gate |
| Operations vs 10 promoted patterns | Same count by coincidence; 104/105 map to 9 ops + 1 blocked |

## 7. Required demo scenarios

| Scenario | Expected path |
|----------|---------------|
| Known allowlisted query | Registry hit → `primary_operation` → preconditions → mock/stub evidence → sufficiency → status |
| Known registry, not allowlisted | Shadow/clarify/HIL; no execution |
| New wording, known-compatible | Semantic hint + nearest registry → validator → authority ladder |
| Known operation, no coverage row | Audit/candidate row; no silent execute |
| Novel OOD | Audit/HIL only |
| Knowledge-only SOP/MITRE | Stub RAG → sufficiency; no MCP |
| MITRE candidate mapping | LLM candidate + ID validation → candidate/review |
| Bad LLM JSON | Parse repair or failure recorded; deterministic path kept |

## 8. Success criteria (aggressive visibility demo)

```text
Known allowlisted query shows registry/operation authority (when flags on).
selected_skill visible only as compatibility/debug.
LLM semantic intent and route-plan visible but non-authoritative.
Novel OOD cannot execute.
MCP real execution remains disabled (or mock-only with both flags).
RAG direct-to-LLM remains disabled.
MITRE candidates not promoted without SOC approval.
Answer labels system_check/lab evidence origin.
Trace explains every gate decision.
```

## 9. Honest one-liner (today)

```text
Evidence-complete, answer-incomplete; 105 planned in shadow; live brain = 4 intents;
Experience Center = curated demos with 4-intent labels + golden answers.
```

## 10. Index

| Topic | Doc |
|-------|-----|
| Unified registry | [p0_unified_105_registry.md](p0_unified_105_registry.md) |
| 48 + MITRE | [p0_stakeholder_48_routable_and_mitre.md](p0_stakeholder_48_routable_and_mitre.md) |
| Flow-check env | [p0_live_flow_check_profile.md](p0_live_flow_check_profile.md) |
| Labels | [p0_trace_demo_labels.md](p0_trace_demo_labels.md) |
