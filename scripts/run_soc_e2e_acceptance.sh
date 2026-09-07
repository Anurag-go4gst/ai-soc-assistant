#!/usr/bin/env bash
# Bounded SOC E2E acceptance runner — recording transports only; no live email.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv/bin/python"
export PYTHONPATH="${ROOT}/backend:${ROOT}:${PYTHONPATH:-}"
exec "$PY" -m pytest \
  backend/app/tests/test_soc_e2e_acceptance.py \
  backend/app/tests/test_p11_remediation_connectors.py \
  backend/app/tests/test_p10_remediation_planning.py \
  backend/app/tests/test_p13_investigation_e2e.py \
  backend/app/tests/test_p7_bounded_plan_delta.py \
  backend/app/tests/test_p0_l2_production_chat_harness.py \
  backend/app/tests/test_negative_result_sufficiency.py \
  backend/app/tests/test_live_path_untouched_by_ec.py \
  backend/app/tests/test_email_send_hil_3_7.py \
  backend/app/tests/test_execution_idempotency.py \
  "$@"
