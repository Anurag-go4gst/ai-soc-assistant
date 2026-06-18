#!/usr/bin/env bash
# Stage 3L / 3M governance regression (no live MCP, no live LLM, no route authority).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PYTHONPATH="${REPO_ROOT}/backend:${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

section() {
  echo ""
  echo "== $1 =="
}

fail() {
  echo "REGRESSION FAILED: $1" >&2
  exit 1
}

section "github skill factory generators"
python3 scripts/build_github_skill_discovery_index.py --check || fail "github discovery index stale"
python3 scripts/score_github_skill_triage.py --check || fail "github triage scores stale"
python3 scripts/build_github_skill_factory_artifacts.py --check || fail "github factory artifacts stale"

section "soc capability crosswalk generator"
python3 scripts/build_soc_capability_crosswalk.py --check || fail "soc capability crosswalk stale"

section "soc validation package (Phase 10/11)"
python3 scripts/build_soc_validation_sheets.py --check || fail "soc validation sheets stale"
(cd backend && python3 -m pytest app/tests/test_soc_validation_package_phase10.py -q) \
  || fail "soc validation package phase10 pytest"

section "sentinel happy-path gate (T-PRE)"
python3 scripts/build_sentinel_set.py --check || fail "sentinel set drifted"
python3 scripts/eval_sentinel.py --check || fail "sentinel baseline diff"

section "Tier-D answer quality (T5.1)"
python3 scripts/eval_answer_quality.py --check || fail "answer quality gate"

section "backend pytest"
(cd backend && python3 -m pytest -q) || fail "backend pytest"

section "test harness (6/6)"
python3 -m test_harness.harness.runner --json >/tmp/stage3_harness.jsonl
if ! python3 -c "
import json, sys
lines = open('/tmp/stage3_harness.jsonl').read().splitlines()
rows = [json.loads(l) for l in lines if l.strip()]
assert len(rows) == 6, len(rows)
assert all(r.get('overall_pass') for r in rows), [r.get('case_id') for r in rows if not r.get('overall_pass')]
"; then
  fail "harness not 6/6"
fi

section "manifest promotion audit"
IOC_REGISTRY_ENABLED=false \
DETECTION_REGISTRY_ENABLED=false \
python3 tools/coverage_authoring/check_manifest_promotion.py || fail "manifest promotion audit"

section "105-question operation map audit"
python3 tools/coverage_authoring/check_question_operation_map.py || fail "operation map audit"

section "QU route bridge 105 routing comparison"
python3 scripts/eval_qu_route_bridge_105.py >/tmp/qu_route_bridge_105.json || fail "QU route bridge 105 eval"

section "cov.q046 trace capture baseline"
python3 -c "
import json
from pathlib import Path
p = Path('docs/stage3l_s3_step3_coe_pilot_verification_traces.json')
data = json.loads(p.read_text(encoding='utf-8'))
assert data.get('pilot_coverage_id') == 'cov.q046.excessive_failed_logins_sample'
scenarios = data.get('scenarios') or []
assert len(scenarios) >= 2, len(scenarios)
for name in ('default_production_safe_fallback', 'lab_pilot_happy_path'):
    assert any(s.get('scenario') == name for s in scenarios), [s.get('scenario') for s in scenarios]
print('cov_q046_baseline_ok scenarios=%d' % len(scenarios))
" || fail "cov.q046 baseline JSON"

section "cov.q046 Step 7 observation window (pytest)"
(cd backend && python3 -m pytest app/tests/test_cov_q046_observation_window_stage3l_s3_step7.py -q) || fail "cov.q046 observation window tests"

section "cov.q046 observation summary closed"
python3 -c "
import json
from pathlib import Path
summary = json.loads(Path('docs/stage3l_s3_cov_q046_observation_summary.json').read_text(encoding='utf-8'))
assert summary.get('status') == 'closed', summary
assert summary.get('unexpected_disagreement_count') == 0, summary
assert summary.get('authority_eligible') is True, summary
print('cov_q046_window_closed', summary.get('closure_reason'))
" || fail "observation summary not closed"

section "Stage 3M-S5 live MCP capture fail-closed"
if python3 scripts/capture_stage3m_s5_live_mcp_schema.py >/tmp/stage3m_s5_capture.out 2>/tmp/stage3m_s5_capture.err; then
  fail "live MCP capture should fail closed without flag"
fi
grep -q 'capture_blocked:live_capture_flag_missing' /tmp/stage3m_s5_capture.err \
  || fail "expected live_capture_flag_missing"

section "golden answer Tier 0 (control plane)"
(cd backend && PYTHONPATH=../backend:.. python3 -m app.evals.golden_answer_runner --tier 0 --json --no-write) \
  || fail "golden answer Tier 0"

section "105-question shadow route eval"
ROUTE_AUTHORITY_OPERATION_AUTHORITATIVE_ENABLED=false \
LEGACY_SELECTED_SKILL_AUTHORITY_ENABLED=true \
ROUTING_MODE=llm_assisted_semantic \
MCP_GLOBAL_EXECUTION_ENABLED=false \
DEMO_LLM_SHADOW_ENABLED=false \
python3 scripts/eval_stage3l_105_question_shadow_routes.py \
  --out-dir docs/evals/out \
  || fail "105-question shadow eval"

section "LangGraph dual-run parity (Phase 13)"
python3 scripts/run_langgraph_dual_parity_eval.py --check \
  || fail "langgraph dual-run parity --check"
(cd backend && python3 -m pytest app/tests/test_langgraph_dual_parity_phase13.py -q) \
  || fail "langgraph dual parity phase13 pytest"

section "SOC clean-answer eval"
python3 scripts/run_soc_clean_answer_eval.py --check \
  || fail "soc clean-answer eval --check"
(cd backend && python3 -m pytest app/tests/test_soc_clean_answer_eval.py -q) \
  || fail "soc clean answer eval pytest"

section "SPL template audit (Phase F)"
python3 scripts/llm_template_audit.py --write-report || fail "template audit review findings remain"

section "Cisco power-grid catalogue gate"
AI_SOC_DISABLE_DOTENV=1 AI_SOC_SPL_DRAFT_PREVIEW_ENABLED=false \
python3 scripts/run_cisco_powergrid_question_eval.py --profile deterministic --min-wave wave3 --check \
  || fail "cisco power-grid catalogue eval"

section "done"
echo "stage3_governance_regression: PASS"
