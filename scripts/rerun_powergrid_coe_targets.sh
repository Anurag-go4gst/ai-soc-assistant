#!/usr/bin/env bash
# Targeted PowerGrid rerun via production HTTP /chat path (ask_chat route).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${BASE:-http://127.0.0.1:8010}"
OUT="${OUT:-$ROOT/docs/evals/powergrid_soc_rerun_coe_repair.jsonl}"
CJ="$(mktemp)"
trap 'rm -f "$CJ"' EXIT

if [[ -z "${APP_USER:-}" || -z "${APP_PASS:-}" ]]; then
  APP_USER="${APP_USER:-$(grep -E '^APP_AUTH_USER=' "$ROOT/.env" | cut -d= -f2-)}"
  APP_PASS="${APP_PASS:-$(grep -E '^APP_AUTH_PASSWORD=' "$ROOT/.env" | cut -d= -f2-)}"
fi
[[ -z "$APP_USER" || -z "$APP_PASS" ]] && { echo "missing creds"; exit 1; }

login_code=$(curl -s -o /dev/null -w '%{http_code}' -c "$CJ" -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$APP_USER" --arg p "$APP_PASS" '{username:$u,password:$p}')")
[[ "$login_code" != "200" ]] && { echo "login failed: HTTP $login_code"; exit 1; }

IDS=(
  pg.auth.001 pg.auth.002 pg.auth.004 pg.auth.005 pg.auth.006 pg.auth.007 pg.auth.008
  pg.auth.009 pg.auth.010 pg.fw.002 pg.fw.006 pg.fw.008 pg.dns.002 pg.dns.007 pg.dns.008
  pg.dns.009 pg.ep.004 pg.ep.005 pg.ep.006 pg.ep.007 pg.ep.008 pg.sop.003 pg.unsafe.002
)

: > "$OUT"
pass=0 fail=0
for qid in "${IDS[@]}"; do
  q=$(jq -r --arg id "$qid" '.questions[] | select(.question_id==$id) | .question' "$ROOT/docs/evals/powergrid_soc_question_bank.json")
  echo "=== $qid ==="
  resp=$(curl -s -b "$CJ" -X POST "$BASE/chat" -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg m "$q" '{message:$m}')")
  msg=$(echo "$resp" | jq -r '.message // ""')
  summary=$(echo "$resp" | jq -r '.analyst_response.direct_answer_summary // ""')
  skill=$(echo "$resp" | jq -r '.selected_skill // .workflow_plan.skill // ""')
  hil=$(echo "$resp" | jq -r '.human_review.required // false')
  coe=false
  if echo "$msg$summary" | grep -qi 'COE stop-condition validation failed\|duplicate_soc_review_checklist'; then
    coe=true
    fail=$((fail+1))
    status=COE_FAIL
  else
    pass=$((pass+1))
    status=OK
  fi
  echo "$status | skill=$skill | hil=$hil | ${q:0:72}..."
  jq -nc --arg id "$qid" --arg q "$q" --arg status "$status" --arg skill "$skill" \
    --argjson hil "$hil" --argjson coe "$coe" --arg msg "$msg" --arg summary "$summary" \
    '{question_id:$id,question:$q,status:$status,selected_skill:$skill,hil_required:$hil,coe_error:$coe,message:$msg,direct_answer_summary:$summary}' >> "$OUT"
done
echo ""
echo "RERUN SUMMARY: OK=$pass COE_FAIL=$fail (total=${#IDS[@]})"
echo "Wrote $OUT"
