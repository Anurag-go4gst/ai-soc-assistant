#!/usr/bin/env bash
# Audit a plan markdown file for plan-discipline checklist requirements.
# Usage: audit-plan-discipline.sh <path-to-plan.md>
set -euo pipefail

plan="${1:-}"
if [[ -z "$plan" || ! -f "$plan" ]]; then
  echo "ERROR: plan file not found: ${plan:-<missing>}" >&2
  exit 1
fi

issues=0
warn() { echo "GAP: $*"; issues=$((issues + 1)); }
ok() { echo "OK: $*"; }

if ! grep -qE '^[[:space:]]*-[[:space:]]+\[[ xX]\]' "$plan"; then
  warn "No markdown checklist items (- [ ] / - [x]) found — decompose into atomic items"
else
  ok "Checklist items present"
fi

verify_count="$(grep -cE '\*\*Verify:\*\*' "$plan" 2>/dev/null || true)"
if [[ "${verify_count:-0}" -lt 1 ]]; then
  warn "No **Verify:** fields — attach a verification method to every item"
else
  ok "Found ${verify_count} Verify field(s)"
fi

if ! grep -qiE 'depend|sequence|order|blocking|→' "$plan"; then
  warn "No dependency/sequence section — order items by what blocks what"
else
  ok "Dependency/sequence language present"
fi

if ! grep -qiE 'stop condition|decision needed|fails twice|blocked' "$plan"; then
  warn "No explicit stop conditions — document when the loop ends"
else
  ok "Stop conditions present"
fi

if ! grep -qiE 'drift|re-audit|evidence' "$plan"; then
  warn "No drift or evidence discipline — add Drift log and Evidence on check-off"
else
  ok "Drift/evidence discipline mentioned"
fi

unchecked="$(grep -cE '^[[:space:]]*-[[:space:]]+\[[[:space:]]\]' "$plan" 2>/dev/null || true)"
checked="$(grep -cE '^[[:space:]]*-[[:space:]]+\[[xX]\]' "$plan" 2>/dev/null || true)"
unchecked="${unchecked:-0}"
checked="${checked:-0}"

echo "---"
echo "Summary: ${checked} checked, ${unchecked} unchecked, ${issues} gap(s)"
echo "Plan: $plan"

if [[ "$issues" -gt 0 ]]; then
  exit 2
fi
exit 0
