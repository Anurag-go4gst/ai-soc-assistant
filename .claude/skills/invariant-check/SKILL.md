---
name: invariant-check
description: Self-review a diff against the AI-SOC governance invariants before committing — LLM/MCP mediation, SPL executability, EC purity, redaction, HIL gates, state channels. Use before any commit or PR in this repo, after finishing a plan item that touched pipeline/planner/SPL/MCP/LLM code, or when the user says "invariant check", "governance check", or /invariant-check.
---

# invariant-check — the diff review the COE would do

Run against the working diff (`git diff` + `git diff --staged` + untracked files you created). For every item: PASS with evidence (grep/test output), or FAIL with location. One FAIL blocks commit — fix or escalate; never rationalize.

## 1. LLM ↔ MCP mediation

- [ ] No code path where LLM output reaches an MCP connector without deterministic validation between (`grep -n "call_tool\|splunk_run_query"` in the diff — every call site must be inside the gated execution node/lifecycle).
- [ ] No prompts, reasoning text, RAG chunks, credentials, or raw workflow internals in any MCP call payload.
- [ ] `supports_tool_calling` remains false on all LLM providers.

## 2. SPL executability

- [ ] `candidate_spl` never enters an execution path; only validator-approved `normalized_spl` reaches the MCP gate.
- [ ] Nothing new sets `execution_eligible=true` on LLM-produced artifacts.
- [ ] Per-call analyst confirmation (`ai_soc_require_spl_execution_confirmation`) not bypassed, defaulted off, or cached across calls.
- [ ] `freeform_spl_execution_allowed` still False everywhere.
- [ ] New SPL templates/lints respect the validator's `|`-split tokenization (regex alternation in `match()` reads as pipe-commands).

## 3. EC / demo purity

- [ ] Nothing in `backend/app/demo/` gained live LLM, live MCP, or trace emission.
- [ ] `live_llm_called` stays false on EC surfaces; EC SPL still sourced from the template registry.

## 4. Secrets + redaction

- [ ] No secrets/tokens/passwords in code, tests, fixtures, or docs (`grep -riE "password|token|secret|api_key" <changed files>` — env-var NAMES fine, values never).
- [ ] New status/settings/trace output exposes booleans (`url_configured`, `auth_configured`), never values.
- [ ] New telemetry/trace payloads go through existing redaction before persistence.

## 5. State + dual path

- [ ] Every new `state["key"]` declared in the pipeline-state TypedDict (LangGraph silently drops undeclared channels).
- [ ] Behavior change works on BOTH dispatch paths — imperative `chat/pipeline.py` and `graph/chat_workflow.py` (name the test that covers the graph path).

## 6. Flags + posture

- [ ] No new env flag introduced (ride existing flags/booleans; if genuinely unavoidable, stop and ask — user policy).
- [ ] No safety check made flag-disableable.
- [ ] Docker ports still bound to `127.0.0.1`; no new public exposure.

## 7. Test honesty

- [ ] No test weakened/deleted to make the diff pass (diff on `app/tests/` reviewed line by line).
- [ ] Pytest live-LLM conftest guard untouched.
- [ ] Fixtures from captured runs, not hand-rolled, where the plan requires it.

## Output format

```
INVARIANT CHECK — <branch> — <n> files
1 LLM↔MCP: PASS (no new call_tool sites)
2 SPL: PASS (gate tests green: test_mcp_execution_gate 12 passed)
3 EC: PASS (demo/ untouched)
4 Secrets: PASS (grep clean)
5 State: FAIL — pipeline.py:4102 writes state["mcp_calls"], not in ChatPipelineState TypedDict
6 Flags: PASS
7 Tests: PASS
VERDICT: BLOCKED (fix #5, rerun)
```

Then, if all PASS and the change touched runtime behavior: run the relevant pytest slice; at phase boundaries run `./scripts/run_stage3_governance_regression.sh`.
