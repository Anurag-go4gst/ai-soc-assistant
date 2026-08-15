#!/usr/bin/env bash
# Fetch a redacted /debug trace bundle using the same session login as ask_chat.sh.
# Usage: scripts/fetch_debug_bundle.sh <trace_id>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/dotenv.sh
source "${ROOT}/scripts/lib/dotenv.sh"
BASE="${BASE:-http://127.0.0.1:8010}"
TRACE_ID="${1:-}"
[[ -z "${TRACE_ID}" ]] && { echo "usage: $0 <trace_id>" >&2; exit 1; }

if [[ -z "${APP_USER:-}" || -z "${APP_PASS:-}" ]]; then
  APP_USER="${APP_USER:-$(dotenv_get "${ROOT}/.env" APP_AUTH_USER)}"
  APP_PASS="${APP_PASS:-$(dotenv_get "${ROOT}/.env" APP_AUTH_PASSWORD)}"
fi
[[ -z "${APP_USER}" || -z "${APP_PASS}" ]] && { echo "missing creds" >&2; exit 1; }

CJ="$(mktemp)"
trap 'rm -f "$CJ"' EXIT
login_code=$(curl -s -o /dev/null -w '%{http_code}' -c "$CJ" -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$APP_USER" --arg p "$APP_PASS" '{username:$u,password:$p}')")
[[ "$login_code" != "200" ]] && { echo "login failed: HTTP $login_code" >&2; exit 1; }

curl -s -b "$CJ" "$BASE/debug/traces/${TRACE_ID}/bundle"
echo
