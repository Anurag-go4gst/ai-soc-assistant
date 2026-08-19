# EC agent workflow template

Copy this folder when adding a **new** Experience Center scenario that should follow the S4 agent pattern:

- editable investigation plan → run → optional HIL gate → normalized findings
- remediation plan → validation animation → orchestration → verification
- `ec_agent_workflow` payload drives `EcAgentWorkflow` (no scenario-specific frontend code)

**Reference implementation:** `fixtures/s4/` + `ec_agent/profiles/s4.py`

**Adoption guide:** [`docs/ec/agent_workflow_template.md`](../../../../docs/ec/agent_workflow_template.md)

## Files to implement per scenario

| File | Purpose |
|------|---------|
| `agent_config.py` | Step defs, brief copy, HIL template, conversational follow-up ids |
| `investigation_findings.py` | `finding_for_investigation_step(step_id, status, …)` |
| `investigation_state.py` | `build_*_normalized_investigation_state()` spine |
| `remediation_plan.py` | `finding_for_remediation_step()`, email/ticket artifact metadata |
| `pack.py` (existing) | Wire `_apply()`, call `build_*_agent_workflow`, set `use_agent_ui=True` |

## Register the profile

Create `backend/app/demo/ec_agent/profiles/sN.py`:

```python
from app.demo.ec_agent.registry import register_agent_profile
from app.demo.ec_agent.types import AgentProfile

register_agent_profile(
    AgentProfile(
        scenario_id="your_scenario_id",
        default_agent_state=...,
        init_session=...,
        handle_follow_up=...,
        build_workflow=...,
        followups_for_agent_mode=...,
        plan_preread_follow_ups=("show_advisory",),  # optional
        finalize_remediation_after_apply=...,       # optional
        conversational_follow_ups=frozenset({"generate_executive_summary"}),
    )
)
```

Import the module from `ec_agent/profiles/__init__.py`.

No changes to `ec_turn.py` or frontend are required once the profile is registered and the pack emits `ec_agent_workflow`.
