# Stage 3L-S2B: Renderer and output-artifact COE sign-off

**Status:** Design for COE review — **not signed**. No renderer or analyst-card implementation until all boxes below are checked.

**Related:** [stage3l_s2_output_artifacts_design.md](stage3l_s2_output_artifacts_design.md) (shadow tokens landed), [stage3l_s2_intent_bridge_design.md](stage3l_s2_intent_bridge_design.md) (S2A signed).

---

## Problem

`candidate_spl_visible` is an **output-shape** decision. Shadow resolution exists on `route_plan_shadow.output_artifacts`; analysts do not yet see governed candidate SPL in the main card. Surfacing it touches renderer, lineage, sufficiency modes, and chat/demo assembly — separate from S2A bridge work.

---

## Visible ≠ executable (COE-critical)

| Concept | Meaning |
|---------|---------|
| `candidate_spl_visible` | Display the **governed candidate SPL string** (post deterministic validation metadata) in trace/UI |
| **Not** | `execution_eligible`, MCP gate input, or `normalized_spl` used for execution |
| **Not** | A “Run in Splunk”, “Execute”, or implied execution affordance |

Execution path remains unchanged: only `spl_validation.approved=true` with non-null `normalized_spl` and explicit MCP flags reach [`mcp_execution_gate.py`](../backend/app/orchestration/mcp_execution_gate.py). `route_plan_shadow.output_artifacts.renderer_applied` stays **`false`** until a later signed stage explicitly enables renderer wiring.

---

## Artifact tokens (frozen for sign-off)

| Token | Meaning |
|-------|---------|
| `candidate_spl_visible` | Show candidate SPL in trace/UI |
| `analyst_summary_only` | Narration without new SPL surface |
| `knowledge_only` | KB/SOP — no SPL |

No new tokens without updating this doc and COE re-sign.

---

## Consumer map

| Consumer | Reads token? | S2B action |
|----------|--------------|------------|
| [`app/routing/output_artifacts.py`](../backend/app/routing/output_artifacts.py) | Resolves tokens | Freeze `LEGACY_INTENT_DEFAULT_TOKENS` |
| [`app/routing/output_artifacts_shadow.py`](../backend/app/routing/output_artifacts_shadow.py) | Attaches shadow block | Keep `renderer_applied=false` |
| [`app/spl/template_renderer.py`](../backend/app/spl/template_renderer.py) | If `candidate_spl_visible` | **Contract:** read-only render; no execution side effects |
| [`app/lineage/builder.py`](../backend/app/lineage/builder.py) `_output_artifacts_stage` | Lineage stage | Document visible labels in “How this answer was produced” |
| [`app/evidence/`](../backend/app/evidence/) + Q1E contract | Evidence refs | SPL string is evidence metadata only |
| [`app/evidence/context_sufficiency.py`](../backend/app/evidence/context_sufficiency.py) | Answer modes | When `spl_review_only` vs full answer applies if SPL visible but execution blocked |
| [`app/api/routes_chat.py`](../backend/app/api/routes_chat.py) | Response assembly | Map to analyst card field — **impl deferred** |
| [`app/demo/scenarios.py`](../backend/app/demo/scenarios.py) | EC fixtures | Show SPL in technical trace; golden answer unchanged |
| [`frontend/.../Stage3DTracePanel.tsx`](../frontend/src/components/Stage3DTracePanel.tsx) | Technical trace | Read-only SPL block; copy allowed |
| [`frontend/.../ChatBubble.tsx`](../frontend/src/components/ChatBubble.tsx) | Collapsed trace | Same read-only rules |

---

## UI prohibitions (sign-off required)

- No execute / run / search buttons tied to `candidate_spl`
- No promotion of `candidate_spl` to `normalized_spl` in UI
- Demo and live paths must label SPL as **candidate / non-executable** where shown
- EC must not imply live model or MCP execution when showing SPL

---

## COE sign-off

| Reviewer | Artifact vocabulary | Consumer map accepted | Visible≠executable | Date |
|----------|---------------------|----------------------|--------------------|------|
| | ☐ | ☐ | ☐ | |

**After sign-off:** implementation stage may wire renderer + analyst card only within this map. Execution enablement remains a **separate** COE track (live MCP + readiness).
