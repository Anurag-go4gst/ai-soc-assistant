#!/usr/bin/env bash
# Shared helpers for plan-discipline hooks (loop-asap, plan-create arming).
set -euo pipefail

loop_asap_flag() {
  echo "$1/.cursor/hooks/.loop-asap-requested"
}

plan_create_flag() {
  echo "$1/.cursor/hooks/.plan-create-requested"
}

arm_loop_asap() {
  local root="$1"
  local flag
  flag="$(loop_asap_flag "$root")"
  mkdir -p "$(dirname "$flag")"
  date -u +"%Y-%m-%dT%H:%M:%SZ" >"$flag"
}

disarm_loop_asap() {
  local root="$1"
  rm -f "$(loop_asap_flag "$root")"
}

is_loop_asap_requested() {
  local root="$1"
  [[ -f "$(loop_asap_flag "$root")" ]]
}

arm_plan_create() {
  local root="$1"
  local flag
  flag="$(plan_create_flag "$root")"
  mkdir -p "$(dirname "$flag")"
  date -u +"%Y-%m-%dT%H:%M:%SZ" >"$flag"
}

disarm_plan_create() {
  local root="$1"
  rm -f "$(plan_create_flag "$root")"
}

is_plan_create_requested() {
  local root="$1"
  [[ -f "$(plan_create_flag "$root")" ]]
}

should_loop_asap_followup() {
  local root="$1"
  local disable="$root/.cursor/hooks/DISABLE_LOOP_ASAP_ON_STOP"
  [[ -f "$disable" ]] && return 1
  is_loop_asap_requested "$root"
}

plan_path_from_prompt() {
  local root="$1" prompt="$2"
  local candidate

  candidate="$(echo "$prompt" | grep -Eo 'plans/[[:alnum:]_.-]+\.md' | head -n1 || true)"
  if [[ -n "$candidate" && -f "$root/$candidate" ]]; then
    echo "$root/$candidate"
    return 0
  fi

  candidate="$(echo "$prompt" | grep -Eo '[[:alnum:]_.-]+\.md' | head -n1 || true)"
  if [[ -n "$candidate" && -f "$root/plans/$candidate" ]]; then
    echo "$root/plans/$candidate"
    return 0
  fi

  return 1
}

latest_plan_file() {
  local root="$1"
  find "$root/plans" -maxdepth 1 -name '*.md' -type f \
    ! -name 'README.md' \
    ! -name 'LOOP_RUNNER*.md' \
    ! -name '*_TEMPLATE.md' \
    -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -n1 | cut -d' ' -f2-
}
