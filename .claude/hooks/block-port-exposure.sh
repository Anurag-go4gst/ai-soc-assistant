#!/usr/bin/env bash
# Claude Code PreToolUse: block edits that expose a Docker port publicly.
# Repo rule: all service ports bind 127.0.0.1; Nginx fronts production.
# Exit 2 = deny; stderr shown to Claude.
set -euo pipefail

input="$(cat)"
path="$(echo "$input" | jq -r '.tool_input.file_path // .tool_input.path // empty')"
[[ -z "$path" ]] && exit 0

case "$(basename "$path")" in
  docker-compose.yml|docker-compose.yaml) ;;
  *.example) exit 0 ;;
  .env|.env.*) ;;
  *) exit 0 ;;
esac

# Inspect content being written (Write) or the replacement text (Edit).
content="$(echo "$input" | jq -r '.tool_input.content // .tool_input.new_string // empty')"
[[ -z "$content" ]] && exit 0

# Strong signal: explicit public bind.
if echo "$content" | grep -Eq '0\.0\.0\.0:[0-9]+'; then
  echo "Blocked: '0.0.0.0:' bind exposes a Docker port publicly. All ports must bind 127.0.0.1 (Nginx fronts prod at cisco-vai.vnudge.com). Use 127.0.0.1:HOST:CONTAINER." >&2
  exit 2
fi

# Compose host port mapping without a 127.0.0.1 prefix => public by default.
if echo "$content" | grep -Eq '^[[:space:]]*-[[:space:]]*"?[0-9]{2,5}:[0-9]{2,5}"?[[:space:]]*$'; then
  echo "Blocked: a bare 'HOST:CONTAINER' port mapping exposes the port on all interfaces. Prefix with 127.0.0.1: (e.g. 127.0.0.1:8010:8000)." >&2
  exit 2
fi

exit 0
