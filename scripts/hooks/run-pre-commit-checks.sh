#!/usr/bin/env bash
# Shared pre-commit checks (optional git hook — see hooks.md).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

STAGED="$(git diff --cached --name-only)"

if [[ -z "$STAGED" ]]; then
  exit 0
fi

echo "==> pre-commit: secret path guard"
while IFS= read -r f; do
  case "$f" in
    .env|.env.*|*/.env|*/.env.*)
      echo "ERROR: refusing to commit secret file: $f"
      exit 1
      ;;
  esac
done <<<"$STAGED"

echo "==> pre-commit: staged secret pattern scan"
if git diff --cached | grep -Ei '-----BEGIN (RSA |OPENSSH )?PRIVATE KEY|bearer [a-z0-9._-]{20,}|session_secret\s*=\s*[^"\s][^"\s]{8,}'; then
  echo "ERROR: possible secret material in staged diff"
  exit 1
fi

echo "==> pre-commit: stage boundary scan (advisory)"
if git diff --cached | grep -Ei 'MCP_GLOBAL_EXECUTION_ENABLED\s*=\s*true|supports_tool_calling\s*:\s*true|execute_validated_spl|record_mcp_execution'; then
  echo "WARN: staged diff may touch execution boundaries — manual COE review required"
fi

BACKEND_TOUCHED=false
FRONTEND_TOUCHED=false
while IFS= read -r f; do
  [[ "$f" == backend/* ]] && BACKEND_TOUCHED=true
  [[ "$f" == frontend/* ]] && FRONTEND_TOUCHED=true
done <<<"$STAGED"

if $BACKEND_TOUCHED; then
  echo "==> pre-commit: backend pytest (staged backend changes)"
  (cd backend && PYTHONPATH=../backend:.. python3 -m pytest -q --tb=no -x \
    app/tests/test_advisory_promotion.py \
    app/tests/test_query_to_intent.py 2>/dev/null) || {
    echo "WARN: fast backend smoke failed — run full pytest before push"
  }
fi

if $FRONTEND_TOUCHED; then
  echo "==> pre-commit: frontend build (staged frontend changes)"
  (cd frontend && npm run build --silent) || {
    echo "ERROR: frontend build failed"
    exit 1
  }
fi

echo "==> pre-commit: OK"
exit 0
