#!/usr/bin/env bash
# Preflight checks for Mac staging / COE Docker deployment.
# Reads repo-root .env only — does not start containers.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

AUTO_PORT=false
if [[ "${1:-}" == "--auto-port" ]]; then
  AUTO_PORT=true
fi

if [[ "${AUTO_PORT}" == true ]]; then
  # Resolves host-port conflicts and the derived API/CORS keys before we validate them.
  ./scripts/coe_port_autoselect.sh
  echo ""
fi

if [[ ! -f .env ]]; then
  echo "ERROR: repo-root .env is missing. Copy env/profiles/<profile>.env.example to .env and add operator secrets." >&2
  echo "HINT: ./scripts/coe_preflight.sh --auto-port seeds .env and picks free host ports automatically." >&2
  exit 1
fi

# Read .env literally — it may hold unquoted JSON values that bash cannot source.
# shellcheck source=lib/dotenv.sh
source "${REPO_ROOT}/scripts/lib/dotenv.sh"
ENV_FILE="${REPO_ROOT}/.env"

PROFILE="$(dotenv_get "${ENV_FILE}" AI_SOC_ENV_PROFILE coe)"
HOST_BIND="$(dotenv_get "${ENV_FILE}" AI_SOC_HOST_BIND 127.0.0.1)"
BACKEND_PORT="$(dotenv_get "${ENV_FILE}" AI_SOC_BACKEND_HOST_PORT 8010)"
FRONTEND_PORT="$(dotenv_get "${ENV_FILE}" AI_SOC_FRONTEND_HOST_PORT 3010)"
POSTGRES_PORT="$(dotenv_get "${ENV_FILE}" AI_SOC_POSTGRES_HOST_PORT 5434)"
PUBLIC_API="$(dotenv_get "${ENV_FILE}" AI_SOC_PUBLIC_API_BASE_URL "http://127.0.0.1:8010/api")"
CORS_ORIGINS="$(dotenv_get "${ENV_FILE}" AI_SOC_CORS_ALLOWED_ORIGINS "http://localhost:3010,http://127.0.0.1:3010")"
VLLM_BASE="$(dotenv_get "${ENV_FILE}" AI_SOC_LLM_LOCAL_BASE_URL)"

PROFILE_FILE="${REPO_ROOT}/env/profiles/${PROFILE}.env.example"
merged_dotenv_get() {
  local key="$1" default="${2:-}" from_env
  from_env="$(dotenv_get "${ENV_FILE}" "${key}")"
  if [[ -n "${from_env}" ]]; then
    printf '%s' "${from_env}"
    return 0
  fi
  dotenv_get "${PROFILE_FILE}" "${key}" "${default}"
}

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

# Ports our own compose project already publishes are not conflicts — otherwise a
# preflight run against a live stack always reports WARN.
own_published_port() {
  local mapped
  mapped="$(docker compose port "$1" "$2" 2>/dev/null || true)"
  # Must return 0 even when the service is down: a non-zero return here would abort
  # the enclosing command substitution under `set -e` and truncate OWN_PORTS.
  [[ -n "${mapped}" ]] && printf '%s\n' "${mapped##*:}"
  return 0
}
OWN_PORTS="$(
  own_published_port backend 8010
  own_published_port frontend 3010
  own_published_port postgres 5432
)"

PORTS_OK=true
for label_port in "backend:${BACKEND_PORT}" "frontend:${FRONTEND_PORT}" "postgres:${POSTGRES_PORT}"; do
  label="${label_port%%:*}"
  port="${label_port##*:}"
  if [[ -n "${OWN_PORTS}" ]] && grep -qx "${port}" <<<"${OWN_PORTS}"; then
    echo "port held by this stack: ${label} ${port}"
  elif port_in_use "${port}"; then
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

if [[ "${PROFILE}" == "coe" ]]; then
  T4_ENABLED="$(merged_dotenv_get AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED false)"
  T4_TIMEOUT="$(merged_dotenv_get AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS)"
  T4_ENABLED_LC="$(printf '%s' "${T4_ENABLED}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${T4_ENABLED_LC}" == "true" || "${T4_ENABLED_LC}" == "1" || "${T4_ENABLED_LC}" == "yes" || "${T4_ENABLED_LC}" == "on" ]]; then
    if [[ -z "${T4_TIMEOUT}" || "${T4_TIMEOUT}" == "2" || "${T4_TIMEOUT}" == "2.0" ]]; then
      echo "ERROR: COE T4 is enabled but AI_SOC_T4_SEMANTIC_UNDERSTANDING_TIMEOUT_SECONDS is unset or the 2.0s code default." >&2
      echo "HINT: set an explicit timeout in repo-root .env before live T4 qualification. Do not copy the VPS 120s bound as a COE SLO." >&2
      exit 1
    fi
    echo "T4 timeout override:  ${T4_TIMEOUT}s (operator-supplied; not a documented SLO)"
  fi

  MCP_MODE_VAL="$(merged_dotenv_get MCP_MODE mock)"
  MCP_GLOBAL_VAL="$(merged_dotenv_get MCP_GLOBAL_EXECUTION_ENABLED false)"
  SPLUNK_URL="$(merged_dotenv_get SPLUNK_MCP_BASE_URL)"
  if [[ -z "${SPLUNK_URL}" ]]; then
    SPLUNK_URL="$(merged_dotenv_get MCP_SERVER_SPLUNK_SOC_URL)"
  fi
  SPLUNK_TOKEN="$(merged_dotenv_get SPLUNK_MCP_TOKEN)"
  if [[ -z "${SPLUNK_TOKEN}" ]]; then
    SPLUNK_TOKEN="$(merged_dotenv_get MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN)"
  fi
  SPLUNK_TOKEN_FILE="$(merged_dotenv_get SPLUNK_MCP_TOKEN_FILE)"
  if [[ -z "${SPLUNK_TOKEN_FILE}" ]]; then
    SPLUNK_TOKEN_FILE="$(merged_dotenv_get MCP_SERVER_SPLUNK_SOC_BEARER_TOKEN_FILE)"
  fi
  LIVE_MCP_CONFIGURED=false
  if [[ -n "${SPLUNK_URL}" && -n "${SPLUNK_TOKEN}${SPLUNK_TOKEN_FILE}" ]]; then
    LIVE_MCP_CONFIGURED=true
  fi
  MCP_GLOBAL_LC="$(printf '%s' "${MCP_GLOBAL_VAL}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${MCP_GLOBAL_LC}" == "true" || "${MCP_GLOBAL_LC}" == "1" || "${MCP_GLOBAL_LC}" == "yes" || "${MCP_GLOBAL_LC}" == "on" ]]; then
    LIVE_MCP_EXECUTION="gated (AUTH0 + RBAC + HIL + policy + read-only allowlist)"
  else
    LIVE_MCP_EXECUTION="disabled"
  fi
  echo ""
  echo "== MCP live activation (one switch) =="
  echo "MCP_MODE:                       ${MCP_MODE_VAL}"
  echo "BEFORE LIVE ACTIVATION:"
  echo "LIVE_MCP_CONFIGURED = ${LIVE_MCP_CONFIGURED}"
  echo "MCP_GLOBAL_EXECUTION_ENABLED = ${MCP_GLOBAL_VAL}"
  echo "LIVE_MCP_EXECUTION = ${LIVE_MCP_EXECUTION}"
  echo "ACTIVATION:"
  echo "MCP_GLOBAL_EXECUTION_ENABLED=true"
  echo "AFTER ACTIVATION:"
  echo "AUTH0 + RBAC + HIL + policy + read-only tool allowlist still determine whether"
  echo "any individual call may execute."
  echo "Operator-supplied (never git): Cisco endpoint/model, explicit COE T4 timeout,"
  echo "Splunk MCP endpoint, token or token-file, TLS verify/CA path, Splunk service identity."
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
