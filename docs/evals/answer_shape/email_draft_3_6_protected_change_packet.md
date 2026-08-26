# 3.6 — governed email-draft protected change packet

**STATUS: APPLIED UNDER THE USER'S REQUEST TO EXECUTE THE EXISTING CANONICAL PLAN.**

## CURRENT CONTRACT

Final RQC preserves a conditional `email_draft`, Phase 10 deterministically advances it to `ELIGIBLE`, and recipient roles persist without addresses. There is no governed email-drafting LLM role and the configured live providers are currently unreachable. The production `/chat` wire contract has no dedicated draft field, so analyst-visible draft content cannot be represented without either a protected additive field or semantically incorrect metadata smuggling.

## PROPOSED CONTRACT

Add one typed additive `email_draft` field to `PlaceholderResponse` and `ChatPipelineState`, backed by `GovernedEmailDraft`. When and only when the Final-RQC email action is `ELIGIBLE` and the governed InvestigationOutcome is completed, suspicious, evidence-backed, and has accepted findings, Phase 10 produces a deterministic draft. Inputs are only accepted findings, evidence refs, severity, and governed recipient-role ids. The envelope has no address field and pins `recipient_resolution_required=true`, `llm_attempted=false`, `send_authorized=false`, and `sent=false`. The frontend renders a draft-only card with no action buttons.

No new LLM role, provider binding, model configuration, prompt, connector, action proposal, or send path is introduced. `ec_email.py` and all demo email modules remain untouched.

## EXACT PROTECTED FILES

- `backend/app/chat/pipeline.py`: declares and forwards the additive `email_draft` state field after the existing Phase-10 seam.
- `backend/app/schemas/responses.py`: declares the optional typed `/chat` wire field.

The RACES freeze baseline is advanced by exact SHA-256 content pins for these two protected files. This is stricter than a path allowlist: any future byte change fails until separately reviewed. No graph, route, ChatPanel, MCP gate, SPL validator, or demo file changes.

## WHY J7 REMAINS TRUE

Draft production is downstream of the existing closed predicate evaluator and separately rechecks completed+suspicious outcome, evidence refs, and non-empty accepted findings. It does not create or widen remediation eligibility. An `ELIGIBLE` label without governed outcome support produces no draft.

## POSITIVE TEST

CV.MULTI.01B with exact accepted predicate evidence produces a role-only, evidence-bound deterministic draft. The wire schema accepts it and the UI displays subject/body plus the explicit unresolved/not-sent posture. The trace records no live model attempt.

## NEGATIVE TEST

CV.MULTI.01A/unmet predicate produces no draft. Missing governed findings/evidence produces no draft even if an action label is present. No send/approve button, address, approval envelope, execution result, action proposal, or connector call is created.

## ROLLBACK

Remove `GovernedEmailDraft`, the Phase-10 builder/attachment, the optional state and response fields, the UI card/type/tests, and the two exact protected-blob pins. Restore no prior data because the field is additive and no draft is persisted or sent.
