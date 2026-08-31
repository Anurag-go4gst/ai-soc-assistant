# Protected change packet — guided investigation HIL boundary

## CURRENT

`backend/app/chat/pipeline.py` @ master `9e1b1369` (RACES approved blob
`08bcee4e703dd56e0b17335da3ce5b93c8dff16573dad08f17042a2e1c331f49`).

On `awaiting_investigation_plan` / `investigation_approval.status=awaiting_approval`,
`graph_node_context_finalize` still:

1. retrieved SOC-KB RAG into `source_evidence`
2. derived `InvestigationOutcome` (disposition/conclusion)
3. ran live synthesis-lab narration (`provider=local_model`)
4. skipped guided composer with `synthesis_lab_already_narrated`
5. surfaced a false “planner unavailable” analyst message

Dispatch correctly skipped ResourcePlan/MCP; packaging did not stop at HIL.

## PROPOSED

Surgical gates in finalize (imperative + ResourcePlanner graph share this node):

1. If awaiting investigation approval → inject RAG skip payload (no material retrieval).
2. Force `investigation_outcome` absent.
3. When guided LLM owns the hop OR awaiting HIL → `allow_live_narration=False` on
   `run_governed_synthesis_lab` so lab cannot steal the guided hop.
4. Strip analyst_response / collected evidence / outcome from the awaiting-approval
   `PlaceholderResponse`.
5. Never overwrite investigation-approval `safe_message` with guided degrade copy.

Companion modules (not freeze-listed):

- `awaiting_investigation_plan_gate.py` — classification + skip payload
- `guided_investigation_synthesizer.py` — failure classes; no env-var leak
- `lab_runner.py` — `allow_live_narration` knob
- `parser.py` — failed SSH event_type preservation
- frontend `ChatBubble.tsx` — defence-in-depth hide of post-execution cards

## ROLLBACK

Revert this commit. Restore pipeline blob hash to
`08bcee4e703dd56e0b17335da3ce5b93c8dff16573dad08f17042a2e1c331f49`.

## SHA PIN

New pipeline.py sha256:
`9116223a99e758dedd4f4c8eee6237bab07812724bff5b17c44d323b9f4a78b0`

Base: `9e1b13694b4047560f8ddd77a77282147b46c3fb`
