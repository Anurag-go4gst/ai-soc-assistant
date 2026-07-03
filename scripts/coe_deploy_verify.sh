#!/usr/bin/env bash
# Build, start, and smoke-test AI-SOC Docker deployment using repo-root .env.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: repo-root .env is missing." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

HOST_BIND="${AI_SOC_HOST_BIND:-127.0.0.1}"
BACKEND_PORT="${AI_SOC_BACKEND_HOST_PORT:-8010}"
FRONTEND_PORT="${AI_SOC_FRONTEND_HOST_PORT:-3010}"
PUBLIC_API="${AI_SOC_PUBLIC_API_BASE_URL:-http://127.0.0.1:8010/api}"
VLLM_BASE="${AI_SOC_LLM_LOCAL_BASE_URL:-}"
BACKEND_HEALTH="http://${HOST_BIND}:${BACKEND_PORT}/health"
FRONTEND_URL="http://${HOST_BIND}:${FRONTEND_PORT}/"

echo "== AI-SOC deploy verify =="
echo "rendering docker compose config..."
docker compose config >/tmp/ai_soc_compose_rendered.yml

echo "starting stack (docker compose up -d --build)..."
docker compose up -d --build

echo "waiting for backend health (${BACKEND_HEALTH})..."
ready=false
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 "${BACKEND_HEALTH}" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "${ready}" != true ]]; then
  echo "ERROR: backend health check failed at ${BACKEND_HEALTH}" >&2
  docker compose ps
  exit 1
fi
echo "backend health: OK"

echo "checking frontend reachability (${FRONTEND_URL})..."
if curl -fsS --max-time 10 "${FRONTEND_URL}" >/dev/null 2>&1; then
  echo "frontend reachability: OK"
else
  echo "ERROR: frontend not reachable at ${FRONTEND_URL}" >&2
  docker compose ps
  exit 1
fi

if [[ -n "${VLLM_BASE}" ]]; then
  echo "checking vLLM reachability from backend container..."
  if docker compose exec -T backend python3 - <<'PY'
import os
import sys
import urllib.error
import urllib.request

base = os.environ.get("AI_SOC_LLM_LOCAL_BASE_URL", "").rstrip("/")
if not base:
    sys.exit(0)
root = base[:-3] if base.endswith("/v1") else base
checks = [f"{root}/health", f"{base}/models"]
for url in checks:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            if resp.status >= 400:
                print(f"FAIL {url} status={resp.status}")
                sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"FAIL {url}: {exc}")
        sys.exit(1)
    print(f"OK {url}")
PY
  then
    echo "backend -> vLLM: OK"
  else
    echo "ERROR: backend container cannot reach configured vLLM (${VLLM_BASE})" >&2
    exit 1
  fi
else
  echo "backend -> vLLM: skipped (AI_SOC_LLM_LOCAL_BASE_URL unset)"
fi

echo ""
echo "DEPLOY VERIFY: OK"
echo "frontend URL: ${FRONTEND_URL}"
echo "backend API:  ${PUBLIC_API}"
echo "backend health: ${BACKEND_HEALTH}"
