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
- Candidate SPL is generated through governed templates, lab draft preview, Stage 3C stub (legacy), or flag-gated LLM failover (`AI_SOC_LLM_SPL_FALLBACK_ENABLED`); all paths are candidate-only.
- SPL validation is deterministic; rejected SPL and lab-tier LLM SPL must have `normalized_spl=null`. Lab-tier exposure (`validate_spl_lab_candidate`) may show placeholder SPL to analysts with `spl_validation.approved=false`.
- `candidate_spl` must never be executed.
- Only `spl_validation.approved=true` and non-null `normalized_spl` may reach the MCP execution gate. `graph_node_spl_source_resolve` substitutes placeholders from config/RAG/session before re-validation.
- Structural SPL relevance gate (`app/spl/spl_relevance_check.py`) runs on non-template candidates; LLM failover retry defaults off (`AI_SOC_LLM_SPL_FAILOVER_RETRY_ENABLED=false`).
- MCP tool discovery, deterministic tool selection, human review, and mock gated execution are Stage 3D control-layer behavior.
- MCP execution defaults disabled globally and per server.
- Mock MCP execution is allowed only when explicitly enabled through `MCP_GLOBAL_EXECUTION_ENABLED=true` and `MCP_SERVER_MOCK_EXECUTION_ENABLED=true`.
- Real Splunk MCP search adapter is implemented (`splunk_mcp.py`, async lifecycle). Live execution stays **default-off** until operator sets URL/token + execution flags per `CLAUDE.md` §Splunk MCP go-live.
- Governed RAG retrieval is wired: SOC KB results flow only through `SourceEvidence` and `StructuredContext`. There is no direct RAG-to-LLM path.
- The Context Sufficiency Gate (Stage 3J) classifies the evidence package into one answer mode and computes `synthesis_readiness`. `synthesis_allowed` stays `false`.
- No final LLM synthesis runs. `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` and `AI_SOC_LLM_ANSWER_GUARD_ENABLED` are inert config flags (Stage 3J-B), default false. Answer Guard execution stays disabled.
- The governed LLM layer (Stage 3J-B) is configuration/status/UI only and never calls a real LLM. `/settings/llm/check` validates drafts without persisting; secrets are never echoed.
- Intent hygiene (Stage 3J-C): SOP/playbook and MITRE prompts route to `knowledge_recall` (no SPL). A MITRE ask without alert context returns an `intent_clarification` human-review rather than generating SPL. The chat UI is analyst-first with the technical trace collapsed by default.
- Guarded LLM adapter (Stage 3J-I): `app/llm/adapter/` extracts the first balanced JSON object, validates role schemas, and applies active authority overrides — it always forces SPL `execution_eligible=false` and forces deterministic clarification, severity, MITRE status, SOP citation, and allowed actions on conflict, recording `warnings`/`disagreements`. Dormant semantic guards in `app/answer_guard/rules.py` (13 `guard.*` ids) are unit-tested only. Neither the adapter nor the guard rules are imported by `/chat` or the demo path; they never run on a live answer.
- Experience Center calibration (Stage 3J-J): demo golden answers in `app/demo/scenarios.py` mirror governed Foundation-sec behavior (valid template SPL, per-source distinct-user labels, explicit MITRE `Status`, P1–P4 priorities, no execution eligibility) and carry a collapsed investigation-lineage reveal. Answers stay deterministic `coe_synthetic_fixture`, not live-model output.
- Experience Center ↔ production parity (2026-06-15): EC mirrors the real `/chat` pipeline. EC SPL is sourced from the governed template registry via `_scoped_template_spl()` (no hardcoded SPL; edit `templates.json` and EC follows); success-after-failure is P2. EC surfaces the production LLM sidecars — `control_plane_trace.{mitre_risk_rationale,resource_plan_shadow}` + `llm_sidecars` + governance `llm_sidecar_panel` — built from real deterministic rationale, posture kept (`live_llm_called=false`, advisory, deterministic wins). Lineage/evidence/governance sections render from the shared builders, same as live. Scenarios: added `dns_beaconing_c2_hunt` (+`_run` mock MCP hop) and `guided_investigation_supply_chain` (out-of-catalog 5th-skill hunt); removed redundant `failed_login_playbook`. Demo progress UX (`investigationProgress.ts`, `InvestigationProgressPanel.tsx`): realistic MCP handshake (submit→poll→fetch with job sid), per-step jitter, live elapsed ticker to mask real latency. Prod frontend = Nginx serving `frontend/dist`; run `npm run build` in `frontend/` to publish UI changes (docker `frontend` is Vite dev only).
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

- `911eed6` Fix SPL routing relevance bugs (Phase B)
- `ad29958` Wire LLM-primary SPL failover and relevance gate (Phase C)
- `35b42b0` Single SPL surface and ambiguous-route disambiguation (Phase C.2)
- `1b86da2` / `22cbbc3` Close catalogue SPL coverage (Phases D / D.2)
- `8f44eee` Complete SPL audit phases G/E/F/H (lab-tier exposure, simplifier, template audit, source resolve)
