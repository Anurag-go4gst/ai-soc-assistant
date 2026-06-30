#!/usr/bin/env bash
# After writing a plan file, remind agent to apply checklist discipline.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
input="$(cat)"
path="$(echo "$input" | jq -r '.tool_input.path // .tool_input.file_path // empty')"

if [[ -z "$path" ]]; then
  exit 0
fi

case "$path" in
  plans/*.md|plans/*/*.md|*/plans/*.md)
    ;;
  *)
    exit 0
    ;;
esac

basename="${path##*/}"
if [[ "$basename" == "README.md" ]]; then
  exit 0
fi

jq -n --arg p "$path" --arg msg "$(cat <<CTX
Plan file edited ($path). Before any implementation:

1. Decompose into atomic checklist items (- [ ]) with **Do**, **Verify**, **Depends on**, **Evidence** per .cursor/rules/plan-discipline.mdc
2. Sequence by dependency; document stop conditions and drift log
3. Run: .cursor/hooks/audit-plan-discipline.sh $path — fix all GAPs before coding

Template: .cursor/templates/plan-checklist-template.md
CTX
)" '{additional_context: $msg}'
