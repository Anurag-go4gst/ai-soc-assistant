#!/usr/bin/env bash
# Preflight checks for Mac staging / COE Docker deployment.
# Reads repo-root .env only — does not start containers.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: repo-root .env is missing. Copy env/profiles/<profile>.env.example to .env and add operator secrets." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

PROFILE="${AI_SOC_ENV_PROFILE:-coe}"
HOST_BIND="${AI_SOC_HOST_BIND:-127.0.0.1}"
BACKEND_PORT="${AI_SOC_BACKEND_HOST_PORT:-8010}"
FRONTEND_PORT="${AI_SOC_FRONTEND_HOST_PORT:-3010}"
POSTGRES_PORT="${AI_SOC_POSTGRES_HOST_PORT:-5434}"
PUBLIC_API="${AI_SOC_PUBLIC_API_BASE_URL:-http://127.0.0.1:8010/api}"
CORS_ORIGINS="${AI_SOC_CORS_ALLOWED_ORIGINS:-http://localhost:3010,http://127.0.0.1:3010}"
VLLM_BASE="${AI_SOC_LLM_LOCAL_BASE_URL:-}"

echo "== AI-SOC deployment preflight =="
echo "profile:              ${PROFILE}"
echo "host bind:            ${HOST_BIND}"
echo "backend host port:    ${BACKEND_PORT} -> container 8010"
echo "frontend host port:   ${FRONTEND_PORT} -> container 3010"
echo "postgres host port:   ${POSTGRES_PORT} -> container 5432"
echo "public API base URL:  ${PUBLIC_API}"
echo "CORS allowed origins: ${CORS_ORIGINS}"

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH 2>/dev/null | awk '{print $4}' | grep -qE ":${port}$"
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  echo "WARN: cannot check port ${port} (ss/lsof unavailable)" >&2
  return 1
}

PORTS_OK=true
for label_port in "backend:${BACKEND_PORT}" "frontend:${FRONTEND_PORT}" "postgres:${POSTGRES_PORT}"; do
  label="${label_port%%:*}"
  port="${label_port##*:}"
  if port_in_use "${port}"; then
    echo "WARN: ${label} host port ${port} appears to be in use" >&2
    PORTS_OK=false
  else
    echo "port free: ${label} ${port}"
  fi
done

if [[ -z "${PUBLIC_API}" ]]; then
  echo "ERROR: AI_SOC_PUBLIC_API_BASE_URL is empty" >&2
  exit 1
fi
if [[ -z "${CORS_ORIGINS}" ]]; then
  echo "ERROR: AI_SOC_CORS_ALLOWED_ORIGINS is empty" >&2
  exit 1
fi
if [[ "${CORS_ORIGINS}" == *"*"* ]]; then
  echo "ERROR: wildcard CORS is not allowed when credentials are enabled" >&2
  exit 1
fi

echo ""
echo "== docker compose config =="
docker compose config >/tmp/ai_soc_compose_rendered.yml
echo "rendered compose written to /tmp/ai_soc_compose_rendered.yml"
grep -E 'published:|VITE_API_BASE_URL|AI_SOC_ENV_PROFILE' /tmp/ai_soc_compose_rendered.yml || true

if [[ -n "${VLLM_BASE}" ]]; then
  VLLM_ROOT="${VLLM_BASE%/v1}"
  VLLM_ROOT="${VLLM_ROOT%/}"
  echo ""
  echo "== optional vLLM reachability (from host) =="
  echo "vLLM base: ${VLLM_BASE}"
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 10 "${VLLM_ROOT}/health" >/dev/null; then
      echo "vLLM /health: OK"
    else
      echo "WARN: vLLM /health unreachable from this host (${VLLM_ROOT}/health)" >&2
    fi
    if curl -fsS --max-time 10 "${VLLM_BASE}/models" >/dev/null; then
      echo "vLLM /v1/models: OK"
    else
      echo "WARN: vLLM /v1/models unreachable from this host" >&2
    fi
  else
    echo "WARN: curl not available; skipping vLLM probe" >&2
  fi
else
  echo ""
  echo "vLLM probe skipped (AI_SOC_LLM_LOCAL_BASE_URL unset)"
fi

if [[ "${PORTS_OK}" != true ]]; then
  echo ""
  echo "PREFLIGHT: WARN — one or more host ports appear in use. Adjust .env or stop conflicting services." >&2
  exit 2
fi

echo ""
echo "PREFLIGHT: OK"
