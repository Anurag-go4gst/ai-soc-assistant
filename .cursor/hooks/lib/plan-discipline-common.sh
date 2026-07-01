#!/usr/bin/env bash
# Shared helpers for plan-discipline hooks (loop-asap, plan-create arming).
set -euo pipefail

LOOP_ASAP_HOOK_MARKER='Plan loop-asap (plan-discipline rule):'
LOOP_ASAP_MAX_TURNS=5

loop_asap_flag() {
  echo "$1/.cursor/hooks/.loop-asap-requested"
}

active_plan_file() {
  echo "$1/plans/.active-plan"
}

plan_create_flag() {
  echo "$1/.cursor/hooks/.plan-create-requested"
}

_read_loop_flag_field() {
  local flag="$1" key="$2"
  [[ -f "$flag" ]] || return 1
  grep -E "^${key}=" "$flag" 2>/dev/null | head -n1 | cut -d= -f2- || return 1
}

_write_loop_flag() {
  local flag="$1" armed_at="$2" plan_path="${3:-}" turns="${4:-0}"
  mkdir -p "$(dirname "$flag")"
  {
    echo "armed_at=${armed_at}"
    [[ -n "$plan_path" ]] && echo "plan_path=${plan_path}"
    echo "turns=${turns}"
    echo "max_turns=${LOOP_ASAP_MAX_TURNS}"
  } >"$flag"
}

arm_loop_asap() {
  local root="$1" plan_path="${2:-}"
  local flag armed_at rel=""
  flag="$(loop_asap_flag "$root")"
  armed_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  if [[ -n "$plan_path" ]]; then
    case "$plan_path" in
      "$root"/*) rel="${plan_path#"$root"/}" ;;
      /*) rel="${plan_path}" ;;
      *) rel="$plan_path" ;;
    esac
    bind_active_plan "$root" "$rel"
  fi
  _write_loop_flag "$flag" "$armed_at" "$rel" 0
}

disarm_loop_asap() {
  local root="$1"
  rm -f "$(loop_asap_flag "$root")"
}

is_loop_asap_requested() {
  local root="$1"
  [[ -f "$(loop_asap_flag "$root")" ]]
}

loop_asap_bound_plan() {
  local root="$1" raw=""
  raw="$(_read_loop_flag_field "$(loop_asap_flag "$root")" plan_path 2>/dev/null || true)"
  if [[ -n "$raw" && -f "$root/$raw" ]]; then
    echo "$root/$raw"
    return 0
  fi
  return 1
}

loop_asap_turn_count() {
  local root="$1" turns=""
  turns="$(_read_loop_flag_field "$(loop_asap_flag "$root")" turns 2>/dev/null || echo 0)"
  echo "${turns:-0}"
}

loop_asap_turns_exhausted() {
  local root="$1" turns max
  turns="$(loop_asap_turn_count "$root")"
  max="$(_read_loop_flag_field "$(loop_asap_flag "$root")" max_turns 2>/dev/null || echo "$LOOP_ASAP_MAX_TURNS")"
  [[ "${turns:-0}" -ge "${max:-$LOOP_ASAP_MAX_TURNS}" ]]
}

increment_loop_asap_turn() {
  local root="$1" flag turns armed_at plan_path max
  flag="$(loop_asap_flag "$root")"
  [[ -f "$flag" ]] || return 1
  turns="$(loop_asap_turn_count "$root")"
  armed_at="$(_read_loop_flag_field "$flag" armed_at 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")"
  plan_path="$(_read_loop_flag_field "$flag" plan_path 2>/dev/null || true)"
  max="$(_read_loop_flag_field "$flag" max_turns 2>/dev/null || echo "$LOOP_ASAP_MAX_TURNS")"
  turns=$((turns + 1))
  {
    echo "armed_at=${armed_at}"
    [[ -n "$plan_path" ]] && echo "plan_path=${plan_path}"
    echo "turns=${turns}"
    echo "max_turns=${max}"
  } >"$flag"
}

is_loop_asap_hook_followup_prompt() {
  local prompt="$1"
  [[ -n "$prompt" ]] && echo "$prompt" | grep -Fq "$LOOP_ASAP_HOOK_MARKER"
}

is_loop_asap_stop_prompt() {
  local prompt="$1"
  [[ -n "$prompt" ]] && echo "$prompt" | grep -Eiq '\b(stop|cancel|end|quit)\b.{0,24}\bloop[\s-]?asap\b|\bloop[\s-]?asap\b.{0,24}\b(stop|cancel|end|quit)\b'
}

is_user_loop_asap_arm_prompt() {
  local prompt="$1"
  is_loop_asap_hook_followup_prompt "$prompt" && return 1
  [[ -n "$prompt" ]] && echo "$prompt" | grep -Eiq '\bloop[\s-]?asap\b' && ! is_loop_asap_stop_prompt "$prompt"
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

bind_active_plan() {
  local root="$1" plan_rel="$2"
  [[ -n "$plan_rel" ]] || return 1
  case "$plan_rel" in
    plans/*.md) ;;
    *) return 1 ;;
  esac
  mkdir -p "$(dirname "$(active_plan_file "$root")")"
  printf '%s\n' "$plan_rel" >"$(active_plan_file "$root")"
}

read_active_plan() {
  local root="$1" rel=""
  rel="$(cat "$(active_plan_file "$root")" 2>/dev/null | head -n1 | tr -d '\r' || true)"
  [[ -n "$rel" && -f "$root/$rel" ]] || return 1
  echo "$root/$rel"
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

resolve_loop_asap_plan_for_arm() {
  local root="$1" prompt="$2" candidate=""
  if plan_path="$(plan_path_from_prompt "$root" "$prompt" 2>/dev/null)"; then
    echo "$plan_path"
    return 0
  fi
  if candidate="$(read_active_plan "$root" 2>/dev/null)"; then
    echo "$candidate"
    return 0
  fi
  return 1
}

resolve_loop_asap_plan_for_followup() {
  local root="$1" prompt="$2" candidate=""
  if candidate="$(loop_asap_bound_plan "$root" 2>/dev/null)"; then
    echo "$candidate"
    return 0
  fi
  if plan_path="$(plan_path_from_prompt "$root" "$prompt" 2>/dev/null)"; then
    echo "$plan_path"
    return 0
  fi
  if candidate="$(read_active_plan "$root" 2>/dev/null)"; then
    echo "$candidate"
    return 0
  fi
  if [[ -f "$root/.cursor/hooks/ALLOW_LOOP_ASAP_LATEST_PLAN_FALLBACK" ]]; then
    if latest="$(latest_plan_file "$root")" && [[ -n "$latest" ]]; then
      echo "$latest"
      return 0
    fi
  fi
  return 1
}

plan_execution_complete() {
  local plan="$1"
  local unchecked checked
  [[ -f "$plan" ]] || return 1
  unchecked="$(grep -cE '^[[:space:]]*-[[:space:]]+\[[[:space:]]\]' "$plan" 2>/dev/null || true)"
  checked="$(grep -cE '^[[:space:]]*-[[:space:]]+\[[xX]\]' "$plan" 2>/dev/null || true)"
  unchecked="${unchecked:-0}"
  checked="${checked:-0}"
  [[ "$unchecked" -eq 0 && "$checked" -gt 0 ]]
}
