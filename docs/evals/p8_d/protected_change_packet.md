# P8 protected-change packet

P8 evaluated production journeys and browser UX. Two remaining major defects require operator-gated files. No silent architecture change was made.

## P8-J7 / UI-J4 — unjustified remediation offer on SOP knowledge

**REQUEST_ID:** `P8-J7-KNOWLEDGE-REMEDIATION-OFFER`

**FILE:** `backend/app/chat/pipeline.py` (likely also `derive_investigation_outcome` / `maybe_attach_remediation_offer` callers)

**WHY:** Live journey J7 and production browser UI-J4 (`What is the SOP for investigating a failed login spike?`) route `selected_skill=knowledge_recall` / `soc_show_sop`, then still attach `remediation_approval.status=offered` with safe_message `Investigation complete. Create a remediation plan?`

That is a misleading remediation CTA: knowledge-only SOP recall is not a confirmed malicious investigation conclusion, and P8 does not authorize remediation execution.

**OBSERVED:**
- Journey scorer: `REMEDIATION_APPROPRIATENESS=FAIL` (`docs/evals/p8_c/journey_scorecard.json`)
- Browser: `docs/evals/p8_d/ui_j4_remediation_cta.png`

**PROPOSED DIRECTION (not applied):**
- Do not offer remediation for knowledge_recall / SOP-only answer modes.
- Keep H-REM-01 pin for genuine investigation completions unless operator reclassifies it.
- Tests currently pin `blocked → remediation_offer_required True` in `test_p8_investigation_outcome_v2.py`; any change must be explicit policy, not an eval-score patch.

**AUTHORITY IMPACT:** When a remediation CTA may appear.

**NOT DONE IN P8:** No pipeline.py edit.

## P8-D — production `/chat` empty-state Experience Center picker

**REQUEST_ID:** `P8-D-CHATPANEL-SCENARIO-PICKER`

**FILE:** `frontend/src/components/ChatPanel.tsx`

**WHY:** Empty production `/chat` still renders `DemoScenarioPicker`, demo starter chips, and a `Run` control. That leaks Experience Center / scenario simulation into the production journey. Chrome leakage (login copy, title, TopBar badge, SideNav subtitle) was fixed in unprotected files.

**PROPOSED DIRECTION (not applied):**
- Hide `DemoScenarioPicker` and demo chips when `demoMode` is false.
- Keep Experience Center as a sidenav destination to `/scenarios`.

**NOT DONE IN P8:** ChatPanel.tsx untouched.

## Presentation copy already fixed (unprotected)

`backend/app/chat/investigation_envelope_runtime.py` analyst-visible plan helper text now says Approve / Edit / Cancel. Backend allowed action remains `run`.
