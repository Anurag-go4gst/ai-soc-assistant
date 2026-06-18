# Cisco Power-Grid Catalogue Eval Gate

Status: active review gate  
Scope: 50 Cisco/PGCIL catalogue questions plus focused paraphrase bridge rows  
Execution posture: candidate-only; MCP execution remains disabled by default

## Required Gates

1. Offline catalogue smoke:

```bash
AI_SOC_DISABLE_DOTENV=1 AI_SOC_SPL_DRAFT_PREVIEW_ENABLED=false \
python3 scripts/run_cisco_powergrid_question_eval.py --profile deterministic --min-wave wave3 --check
```

Expected: `PASS=50 REVIEW=0 FAIL=0 CRITICAL=0`.

2. Paraphrase bridge:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_cisco_paraphrase_eval.py -q
```

Expected: all paraphrase rows route to the expected Cisco question id and pattern type.

3. Live chat contract:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_cisco_live_chat_contract.py -q
```

Expected:
- Cisco SPL-review paraphrases remain review-only and non-executable.
- Metadata hygiene questions surface an `environment_hygiene` envelope.
- `candidate_spl` is absent for metadata-only rows.
- `spl_validation.approved` is never used to authorize execution for Cisco lab drafts.
- `execution.executed_spl` remains `null`.

4. Template profile validation:

```bash
cd backend
PYTHONPATH=../backend:.. python3 -m pytest \
  app/tests/test_template_renderer_stage3k_q1d.py \
  app/tests/test_spl_source_resolve.py \
  app/tests/test_spl_tiered_policy.py -q
```

Expected: template `validation_rules` are applied during render, source substitution, and Tier-2 command validation.

## Completion Criteria

- All 50 Cisco rows pass the offline gate for the requested wave.
- Focused paraphrases cover DNS window, geo egress, multi-site auth, Umbrella bypass, and metadata wording.
- Live `/chat` assertions prove governance posture: no automatic execution, no `candidate_spl` for metadata-only questions, and no live-row claims without collected metadata.
- Tier-2 `lookup`, `join`, and `transaction` capabilities are template-scoped and denied by default.
- Any COE/operator-dependent lookup files or live MCP enablement remain explicitly deferred until operator sign-off.

## Current Deferred Items

- Wave 3 lookup/join/transaction templates that require COE-populated lookup files.
- Production deployment/publish of `frontend/dist`.
- Live Splunk execution; this gate verifies metadata and candidate posture only.

## COE demo profile — guided and weak-path LLM composition

Deterministic eval (`--check`, synthesis flags off) does **not** require live LLM prose.
For COE demo / analyst UX review with composed bodies on guided and low-confidence turns:

| Flag | Demo value | Purpose |
|------|------------|---------|
| `CONTROL_PLANE_ENABLED` | `true` | Enables contract-driven finalize + composer path |
| `AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED` | `true` | Allows governed composer |
| `AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED` | `true` | Calls configured local/openai_compatible endpoint |
| `AI_SOC_LLM_ANSWER_GUARD_ENABLED` | `true` | Runs Answer Guard on composed draft |
| `AI_SOC_LLM_COMPOSE_HIL_THRESHOLD` | `0.55` (default) | Low confidence attaches compose HIL |

Weak-path qualification (`query_understanding_weak`, `out_of_registry`, router confidence < 0.35, clarification turns) routes through the same governed composer with deterministic authority preserved.
MCP execution flags remain **false** for eval and demo.

