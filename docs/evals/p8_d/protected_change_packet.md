# P8 protected-change packet

Operator approval required. **No file in this packet has been applied.**

P8 evaluated production journeys and browser UX. Two remaining major defects require operator-gated files. Model comparison is a separate gate and does not hide these defects.

---

## P8-J7-KNOWLEDGE-REMEDIATION-OFFER

**REQUEST_ID:** `P8-J7-KNOWLEDGE-REMEDIATION-OFFER`

**PROTECTED_FILE:** `backend/app/chat/pipeline.py`

**CURRENT_BEHAVIOR:** Journey J7 / UI-J4 query `What is the SOP for investigating a failed login spike?` routes `selected_skill=knowledge_recall` / SOP citation, then `_apply_remediation_lifecycle` still calls `maybe_attach_remediation_offer`. The live response carries `remediation_approval.status=offered` with `safe_message` `Investigation complete. Create a remediation plan?`.

Root cause: InvestigationOutcome V2 sets `remediation_offer_required=True` whenever packaging applies and the Final RQC did not already request remediation (`investigation_outcome.py`). SOP / `procedural_steps` can still be investigation-shaped for packaging. Pipeline then attaches the CTA. Knowledge guidance is treated as if an investigation completed.

**DESIRED_BEHAVIOR:** `KNOWLEDGE GUIDANCE != EVIDENCE OF MALICIOUS ACTIVITY`. A pure SOP / `knowledge_recall` / `knowledge_only_answer` turn must not display a CTA implying confirmed remediation need. Remediation may still be offered when the governed outcome has confirmed malicious or credible evidence-backed containment need.

**WHY_PIPELINE_IS_THE_CORRECT_AUTHORITY_SEAM:** Pipeline is the production last-mile caller that attaches `remediation_approval` onto live `/chat` state (`_apply_remediation_lifecycle` → `maybe_attach_remediation_offer`). The flag on `InvestigationOutcome` is packaging; the CTA is created only when pipeline attaches the offer. A last-mile veto here:

- does not rewrite InvestigationOutcome V2 packaging for genuine investigations
- does not change H-REM-01 (`blocked → remediation_offer_required True` on the outcome object)
- does not authorize writes, MCP, or execution
- keeps API and UI aligned (frontend cannot honestly hide an offered envelope)

`maybe_attach_remediation_offer` remains a consumer of the outcome flag. It is not the skill-router.

**WHY_NO_UNPROTECTED_FIX_IS_CORRECT:** Hiding `RemediationPlanApprovalCard` in ChatBubble / InvestigationOutcomeCard would leave `remediation_approval.status=offered` on the `/chat` contract. That is a false analyst affordance at the API layer. Eval score patches are also incorrect.

**EVIDENCE_STATE_IMPACT:** None. Obtained/missing evidence keys are not rewritten.

**INVESTIGATION_OUTCOME_IMPACT:** Outcome object unchanged. `investigation_status` / `disposition` / `remediation_offer_required` stay as derived. Only attachment of `remediation_approval` is suppressed for knowledge-only turns.

**REMEDIATION_AUTHORITY_IMPACT:** Knowledge/SOP turns no longer receive an offered remediation envelope. Investigation-shaped turns with a justified offer still attach. No plan is built until the analyst asks. `execution_authorized` stays false.

**WRITE_AUTHORITY_IMPACT:** None. No connector write path is opened or closed.

**MCP_IMPACT:** None. MCP execution flags stay off. No tool call is added or removed.

**HIL_IMPACT:** Removes an unjustified HIL CTA on SOP/knowledge. Existing investigation-plan and justified-remediation HIL cards are unchanged. Approve/Edit/Cancel vocabulary is unchanged.

**NEGATIVE TESTS:**

- SOP / `knowledge_recall` query (`What is the SOP for investigating a failed login spike?`) → `remediation_approval` absent
- `context_sufficiency.answer_mode=knowledge_only_answer` → offer not attached
- empty obtained evidence + knowledge skill → offer not attached
- existing `test_cancelled_outcome_has_no_remediation_offer` remains green

**POSITIVE TESTS:**

- J1-class investigation (`attack_discovery` / live investigation with outcome `remediation_offer_required=True`) still attaches `status=offered`
- `test_p10_remediation_planning.py` offer/approve/edit/cancel path unchanged for investigation-shaped outcomes
- `test_blocked_investigation_is_not_a_security_disposition` still pins `remediation_offer_required is True` on the outcome object (packaging), independent of CTA attachment

**ROLLBACK:** Revert the `_knowledge_guidance_must_not_offer_remediation` helper and the two-line call-site gate in `_apply_remediation_lifecycle`. No other module is touched.

### EXACT_DIFF (not applied)

```diff
--- a/backend/app/chat/pipeline.py
+++ b/backend/app/chat/pipeline.py
@@ -3715,6 +3715,26 @@
     }
 
 
+def _knowledge_guidance_must_not_offer_remediation(state: ChatPipelineState) -> bool:
+    """SOP / knowledge_recall is not confirmed malicious activity.
+
+    Last-mile CTA gate only. Does not rewrite InvestigationOutcome packaging,
+    authorize execution, or call MCP.
+    """
+    skill = _context_selected_skill(state)
+    if skill == "knowledge_recall":
+        return True
+    context = state.get("context_sufficiency")
+    if isinstance(context, dict) and str(context.get("answer_mode") or "") == "knowledge_only_answer":
+        return True
+    return False
+
+
 def _apply_remediation_lifecycle(state: ChatPipelineState) -> ChatPipelineState:
     """P10 seam: attach the remediation offer, or advance an explicit analyst decision.
 
@@ -3759,7 +3779,9 @@
                         "remediation_execution": result,
                     }
             return reviewed
-        return maybe_attach_remediation_offer(dict(state))
+        if _knowledge_guidance_must_not_offer_remediation(state):
+            return state
+        return maybe_attach_remediation_offer(dict(state))
     except Exception as exc:  # noqa: BLE001 - remediation planning is additive to the answer
         logger.warning("remediation_lifecycle_skipped kind=%s", type(exc).__name__)
         return {
```

**NOT DONE IN P8:** `pipeline.py` was not edited.

---

## P8-D-CHATPANEL-SCENARIO-PICKER

**REQUEST_ID:** `P8-D-CHATPANEL-SCENARIO-PICKER`

**PROTECTED_FILE:** `frontend/src/components/ChatPanel.tsx`

**CURRENT_BEHAVIOR:** Production `/chat` empty state renders `StarterPrompts` (demo chips sourced from demo scenarios) and `DemoScenarioPicker` with a **Run** control that calls `runDemoScenario` / `demoMode: true`. Experience Center remains a legitimate `/scenarios` destination; this leakage is the production chat empty state.

**DESIRED_BEHAVIOR:**

- `/chat` → clean analyst production entry; composer (`ChatInput`) remains; no demo scenario picker; no demo chips; no simulated Run
- `/scenarios` Experience Center unchanged
- normal conversation after the first user message unchanged
- no routing / backend / HIL / MCP contract changes

**PROOF THE DIFF IS NARROW:**

- only empty-state picker/chips/Run handler removed
- `ChatInput` at the card footer is untouched
- `handleSend` / streaming / HIL review handlers untouched
- `App.tsx` `/scenarios` route untouched
- `SideNav` Experience Center item untouched
- Lab draft switch left in place (polish, not this packet)

**FRONTEND TESTS (proposed, not added while ChatPanel is frozen):**

- New unprotected `frontend/src/components/ChatPanel.emptyState.test.tsx`:
  - empty `/chat` mount → no `DemoScenarioPicker`, no `Run`, no starter demo chips
  - `ChatInput` / composer present and enabled
  - sending a user message still calls the existing send path (mock stream)
- Existing frontend suite (`npm test`) plus `npm run build` after apply
- Experience Center `ecWorkspace.test.tsx` remains green (route isolation)

**ROLLBACK:** Revert the `ChatPanel.tsx` hunk. Restore `DemoScenarioPicker` / `StarterPrompts` / `handleRunDemo`. No backend rollback.

### EXACT_DIFF (not applied)

```diff
--- a/frontend/src/components/ChatPanel.tsx
+++ b/frontend/src/components/ChatPanel.tsx
@@ -1,12 +1,10 @@
 import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
 import { toast } from 'sonner';
-import { runDemoScenario } from '@/api/client';
 import { FlaskConical } from 'lucide-react';
 import { Card, CardContent, CardHeader } from '@/components/ui/card';
 import { ScrollArea } from '@/components/ui/scroll-area';
 import { ChatBubble, type SocChatMessage } from './ChatBubble';
 import { ChatInput } from './ChatInput';
-import { DemoScenarioPicker } from './DemoScenarioPicker';
-import { StarterPrompts } from './StarterPrompts';
 import { cn } from '@/lib/utils';
 import { newClientId } from '@/lib/id';
 import { isClearChatCommand } from '@/lib/chatCommands';
@@ -34,7 +32,7 @@
 } from '@/lib/legacyDemoCoordination';
 import { playLegacyDemoInvestigationWithCoordination } from '@/lib/legacyDemoCoordinationPlayer';
 import { executeLegacyDemoCoordination } from '@/lib/legacyDemoEmail';
-import type { ChatExecutionReviewOptions, ChatInvestigationReviewOptions, ChatRemediationReviewOptions, ChatReviewOptions, DemoScenarioSummary, PlaceholderResponse } from '@/types/api';
+import type { ChatExecutionReviewOptions, ChatInvestigationReviewOptions, ChatRemediationReviewOptions, ChatReviewOptions, PlaceholderResponse } from '@/types/api';
 
 interface ChatPanelProps {
@@ -88,7 +86,6 @@
   const [llmSplDraftMode, setLlmSplDraftMode] = useState(false);
-  const conversationStarted = messages.some((message) => message.role === 'user');
 
   const handleSend = ...
@@ -617,22 +614,6 @@
     resolve('skip');
   };
 
-  const handleRunDemo = async (scenario: DemoScenarioSummary) => {
-    const userMessage: SocChatMessage = {
-      id: newClientId(),
-      role: 'user',
-      content: scenario.query,
-    };
-    setMessages((current) => [...current, userMessage]);
-    await runStagedInvestigation({
-      fetcher: () => runDemoScenario(scenario.scenario_id),
-      expectedSkill: scenario.expected_skill,
-      expectedSources: scenario.expected_sources,
-      demoMode: true,
-      demoScenarioId: scenario.scenario_id,
-    });
-  };
-
   return (
@@ -670,12 +651,6 @@
             />
           </button>
         </div>
-        {!conversationStarted ? (
-          <>
-            <StarterPrompts disabled={loading} onPick={handleSend} />
-            <DemoScenarioPicker disabled={loading} onRun={handleRunDemo} />
-          </>
-        ) : null}
       </CardHeader>
       <CardContent className="min-h-0 min-w-0 flex-1 overflow-hidden p-0">
```

`ChatInput` remains:

```tsx
      <ChatInput disabled={loading} onClear={handleClear} onSend={handleSend} />
```

**NOT DONE IN P8:** `ChatPanel.tsx` was not edited.

---

## Diagnostic dump UX

**DIAGNOSTIC_DUMP_COMPONENT:** Default-visible “too loud” content on production `/chat` is:

1. `frontend/src/components/ChatBubble.tsx` — `UnderstandingProvenancePanel` (“Understanding authority path”) and `Stage3DTracePanel` (technical evidence path / Trace authority tiers). Both are already inside collapsed `<details>` (`How this answer was produced`, `Technical evidence path`). Developer JSON is a nested collapsed details.
2. `frontend/src/components/AnalystResponseCard.tsx` — always-expanded investigation-steps / evidence-required phases. This is analyst workflow, not a hidden debug dump; collapsing it would hide material evidence.
3. `frontend/src/components/AnalystSummaryCard.tsx` — 6-stat diagnostic grid (SPL template / MITRE / HIL / Session / Node Trace / LLM) when no `analyst_response` is present.
4. `frontend/src/components/InvestigationOutcomeCard.tsx` — investigation conclusion card (product, keep visible).

**DIAGNOSTIC_FIX_PROTECTED:** NO for (1)(3). ChatBubble / AnalystSummaryCard / AnalystResponseCard are not the RACES-protected ChatPanel. A small follow-up may collapse the AnalystSummaryCard 6-stat grid into a details element without removing provenance. Do not collapse AnalystResponseCard evidence/steps. Do not hide InvestigationOutcomeCard.

**POLISH:** “Lab draft” switch remains on production chrome (`ChatPanel.tsx` header). Not a P8 blocker unless it is read as execution authority; the title already says lab-only / never executed. Left in the ChatPanel packet as out-of-scope.

---

## Operator

**OPERATOR_APPROVAL_REQUIRED:** YES

Do not apply either protected diff until explicit operator approval of the exact hunks above.
