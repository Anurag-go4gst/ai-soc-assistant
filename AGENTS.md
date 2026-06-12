# AGENTS.md

Guidance for coding agents working in this repository.

## Operating Rules

- Read the local code before changing behavior. Preserve the existing FastAPI + React/Vite structure.
- Keep changes stage-scoped. Do not mix workflow planning, connector readiness, execution, UI polish, and deployment edits in one commit unless explicitly requested.
- Do not commit secrets or `.env`.
- Do not expose Docker service ports publicly. Production-style access is via Nginx at `https://cisco-vai.vnudge.com`.
- Treat `.claude/` as local tool state unless the user explicitly asks to version it.

## Safety Boundaries

Current implementation is governed candidate generation and gated execution control:

- `/chat` returns routing results and a `workflow_plan`.
- Workflow steps stay `not_started`.
- Workflow `execution_enabled` stays `false`.
- Candidate SPL generation is allowed only through the Stage 3C stub generator.
- SPL validation is deterministic; rejected SPL must have `normalized_spl=null`.
- `candidate_spl` must never be executed.
- Only `spl_validation.approved=true` and non-null `normalized_spl` may reach the MCP execution gate.
- MCP tool discovery, deterministic tool selection, human review, and mock gated execution are Stage 3D control-layer behavior.
- MCP execution defaults disabled globally and per server.
- Mock MCP execution is allowed only when explicitly enabled through `MCP_GLOBAL_EXECUTION_ENABLED=true` and `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`.
- Real MCP execution adapter shape exists, but real execution remains blocked/not implemented until COE MCP URL, transport, auth, tool names, argument schema, and approval workflow are supplied.
- Governed RAG retrieval is wired: SOC KB results flow only through `SourceEvidence` and `StructuredContext`. There is no direct RAG-to-LLM path.
- The Context Sufficiency Gate (Stage 3J) classifies the evidence package into one answer mode and computes `synthesis_readiness`. `synthesis_allowed` stays `false`.
- No final LLM synthesis runs. `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` and `AI_SOC_LLM_ANSWER_GUARD_ENABLED` are inert config flags (Stage 3J-B), default false. Answer Guard execution stays disabled.
- The governed LLM layer (Stage 3J-B) is configuration/status/UI only and never calls a real LLM. `/settings/llm/check` validates drafts without persisting; secrets are never echoed.
- Intent hygiene (Stage 3J-C): SOP/playbook and MITRE prompts route to `knowledge_recall` (no SPL). A MITRE ask without alert context returns an `intent_clarification` human-review rather than generating SPL. The chat UI is analyst-first with the technical trace collapsed by default.
- Guarded LLM adapter (Stage 3J-I): `app/llm/adapter/` extracts the first balanced JSON object, validates role schemas, and applies active authority overrides — it always forces SPL `execution_eligible=false` and forces deterministic clarification, severity, MITRE status, SOP citation, and allowed actions on conflict, recording `warnings`/`disagreements`. Dormant semantic guards in `app/answer_guard/rules.py` (13 `guard.*` ids) are unit-tested only. Neither the adapter nor the guard rules are imported by `/chat` or the demo path; they never run on a live answer.
- Experience Center calibration (Stage 3J-J): demo golden answers in `app/demo/scenarios.py` mirror governed Foundation-sec behavior (valid template SPL, per-source distinct-user labels, explicit MITRE `Status`, P1–P4 priorities, no execution eligibility) and carry a collapsed investigation-lineage reveal. Answers stay deterministic `coe_synthetic_fixture`, not live-model output.
- LLM-assisted routing governance (Stage 3J-K0): routing modes `deterministic_only`, `llm_shadow_only`, `llm_assisted_semantic`, `llm_primary_lab`. LLM route suggestions are advisory, normalized through deterministic registries and clarification policy; final route selection stays deterministic. Evidence-need→MCP-tool mapping is a deterministic record only. The SPL optimizer field `execution_eligible` is renamed `revalidation_approved`; candidate SPL stays non-executable.
- The live `SKILL_ENUM` has five routes: `alert_summary`, `spl_generation`, `attack_discovery`, `knowledge_recall`, and `guided_investigation`. The guided route applies only to out-of-registry SOC-investigation-shaped questions; it returns review-only hypotheses and evidence guidance, requires analyst validation, and never authorizes SPL or MCP execution.
- Splunk telemetry writes are disabled.
- LLMs must never call MCP directly.

Any change that violates these boundaries needs explicit user approval and a later-stage requirement.

## MCP / LLM Architecture

- MCP is a generic multi-server registry.
- Splunk MCP is one server type and the first target, not the entire MCP framework.
- Each MCP server has independent configured/available/implemented/error status.
- Global and per-server MCP execution flags must default false.
- MCP tool discovery must expose only redacted/safe tool metadata.
- Tool selection is deterministic. User-requested MCP server/tool values are preferences only, not authority.
- Search tools may be selectable only for `spl_search` after policy checks.
- SAIA/generative/assistant/write/admin tools must be discoverable in status but blocked.

- LLM is a provider/model registry.
- Cisco/Foundation-Sec is one model family, not the only option.
- Foundation-Sec instruct and reasoning roles should be separate configurable providers/models.
- Open-weight/local models should remain configurable through provider types such as `openai_compatible`, `ollama`, `vllm`, `sglang`, `tgi`, `llamacpp`, and `custom_http`.
- Provider fallback must be explicit, not silent.
- `supports_tool_calling` must remain false in this stage.
- `LLM_TOOL_RECOMMENDATION_ENABLED` defaults false. If enabled later, recommendations are advisory only and cannot override deterministic policy, validation, or execution flags.

## Verification

Canonical governance regression:

```bash
./scripts/run_stage3_governance_regression.sh
```

Baseline: [`docs/evals/regression_baseline.md`](docs/evals/regression_baseline.md).

For backend work only:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest
```

For frontend or shared type changes:

```bash
cd frontend
npm run build
```

For harness independence:

```bash
PYTHONPATH=backend:. python3 -m test_harness.harness.runner --json
```

Expected baseline:

- Governance regression script PASS (0 failed pytest, harness 6/6).
- Frontend build passes.

## Commit Hygiene

Preferred grouping:

1. Workflow planning changes.
2. MCP/LLM readiness changes.
3. Documentation-only changes.

Recent stage commits:

- `7a35038 Add MCP discovery, HIL, and gated SPL execution`
- `a47785d Add Stage 3D trace pipeline UI`
- `80d8e35 Wire governed RAG into chat context and trace UI`
- `a0ba56f Stage 3J: Add context sufficiency gate`
- `c3d13cc Stage 3J-B: Add LLM registry settings and status UI`
- `Stage 3J-C Improve analyst chat UX and starter intent handling`
- `db37003 / 5cf271e / 9ba7ab7 Stage 3J-I.1/.2/.3: Guarded LLM adapter, dormant semantic guards, prompt contracts`
- `2fefd10 Calibrate Experience Center responses to governed LLM behavior`
- `05c95bc Stage 3J-K0: Govern LLM-assisted routing and tool selection`
- `91f7b0e Stage 3J-J.2: Surface investigation lineage reveal in chat UI`
