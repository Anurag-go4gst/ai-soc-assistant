#!/usr/bin/env bash
# Read keys from a .env file without shell evaluation.
#
# Why: `set -a; source .env` executes the file. Values that are legal for Docker's
# env_file parser but not for bash — unquoted JSON such as
# AI_SOC_SOURCE_PROFILE_MAP={"auth_index": "pgcil_soc", ...} — abort the calling
# script with "command not found". Docker never had that problem, so the breakage
# only shows up in helper scripts. These readers parse literally instead.

# dotenv_get <file> <key> [default]
# Echoes the last assignment of <key>, with one layer of surrounding quotes stripped.
dotenv_get() {
  local file="$1" key="$2" default="${3:-}" line value
  if [[ ! -f "${file}" ]]; then
    printf '%s' "${default}"
    return 0
  fi
  line="$(grep -E "^[[:space:]]*(export[[:space:]]+)?${key}=" "${file}" | tail -n1 || true)"
  if [[ -z "${line}" ]]; then
    printf '%s' "${default}"
    return 0
  fi
  value="${line#*=}"
  # Strip a single matched pair of surrounding quotes; leave inner quotes intact.
  if [[ "${value}" == \"*\" && ${#value} -ge 2 ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "${value}" == \'*\' && ${#value} -ge 2 ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "${value}"
}

# dotenv_require <file> <key>
# Exits non-zero with a message when the key is missing or empty.
dotenv_require() {
  local file="$1" key="$2" value
  value="$(dotenv_get "${file}" "${key}")"
  if [[ -z "${value}" ]]; then
    echo "ERROR: ${key} is missing or empty in ${file}" >&2
    return 1
  fi
  printf '%s' "${value}"
}
