#!/usr/bin/env bash
# Ask /chat through the REAL prod HTTP path (nginx -> 127.0.0.1:8010 backend),
# authenticated, same request body the UI sends. NOT a direct-import eval harness.
#
# Why this exists: validating a fix by importing graph nodes / mock-LLM / EC
# early-return is a different code path than production. Analysis on that is
# meaningless. This drives the exact path cisco-vai.vnudge.com uses.
#
# Backend runs with uvicorn --reload bind-mounted, so local code edits are already
# live in the running container == live on cisco-vai.vnudge.com. No deploy step.
#
# Usage:
#   scripts/ask_chat.sh "question one" "question two" ...
#   BASE=https://cisco-vai.vnudge.com/api scripts/ask_chat.sh "question"   # hit via nginx
#
# Creds: read from .env (APP_AUTH_USER / APP_AUTH_PASSWORD) unless APP_USER/APP_PASS set.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:8010}"
CJ="$(mktemp)"
trap 'rm -f "$CJ"' EXIT

# Pull creds from .env if not in environment.
if [[ -z "${APP_USER:-}" || -z "${APP_PASS:-}" ]]; then
  APP_USER="${APP_USER:-$(grep -E '^APP_AUTH_USER=' "$ROOT/.env" | cut -d= -f2-)}"
  APP_PASS="${APP_PASS:-$(grep -E '^APP_AUTH_PASSWORD=' "$ROOT/.env" | cut -d= -f2-)}"
fi
[[ -z "$APP_USER" || -z "$APP_PASS" ]] && { echo "missing creds (APP_USER/APP_PASS or .env)"; exit 1; }

# 1. Login -> session cookie.
login_code=$(curl -s -o /dev/null -w '%{http_code}' -c "$CJ" -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$APP_USER" --arg p "$APP_PASS" '{username:$u,password:$p}')")
[[ "$login_code" != "200" ]] && { echo "login failed: HTTP $login_code"; exit 1; }

# 2. Ask each question, dump deterministic-fact slice + full body.
i=0
for q in "$@"; do
  i=$((i+1))
  echo "======================================================================"
  echo "Q$i: $q"
  echo "----------------------------------------------------------------------"
  resp=$(curl -s -b "$CJ" -X POST "$BASE/chat" \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg m "$q" '{message:$m}')")
  # Deterministic authority fields (stable across runs); prose may vary by LLM.
  echo "$resp" | jq '{
    route: (.workflow_plan.skill // .route // .routing.skill),
    answer_mode: (.context_sufficiency.answer_mode // .answer_mode),
    severity: (.severity // .analyst_summary.severity),
    mitre: (.mitre // .control_plane_trace.mitre_decision),
    execution_eligible: (.workflow_plan.execution_enabled // .execution_eligible),
    spl: (.candidate_spl // .normalized_spl // .workflow_plan.candidate_spl),
    human_review: (.human_review.reason // .human_review)
  }' 2>/dev/null || echo "$resp"
  echo "--- full ---"
  echo "$resp" | jq -c '.' 2>/dev/null || echo "$resp"
done
