#!/usr/bin/env bash
# Claude Code Stop hook: keep production in sync after a work session.
# - Frontend prod = Nginx serves frontend/dist => rebuild dist when src is newer.
# - Backend prod  = Docker uvicorn --reload reflects .py saves live; only deps
#   (pyproject.toml / Dockerfile / requirements) need an image rebuild => warn only.
# Always exit 0 (never block the stop / never loop). Output shows in transcript.
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$ROOT" || exit 0

# ---- frontend: build dist if stale vs source ----
dist="frontend/dist/index.html"
newest_src="$(find frontend/src frontend/index.html frontend/package.json \
  frontend/vite.config.ts frontend/tailwind.config.ts \
  -type f -printf '%T@\n' 2>/dev/null | sort -nr | head -1)"

if [[ -n "$newest_src" ]]; then
  src_m="${newest_src%.*}"
  needs_build=0
  if [[ ! -f "$dist" ]]; then
    needs_build=1
  else
    dist_m="$(stat -c '%Y' "$dist" 2>/dev/null || echo 0)"
    (( src_m > dist_m )) && needs_build=1
  fi

  if [[ "$needs_build" == "1" ]]; then
    echo "[publish] frontend/dist stale vs frontend/src — building so Nginx reflects changes..."
    if (cd frontend && npm run build >/tmp/ai_soc_fe_build.log 2>&1); then
      echo "[publish] frontend build OK -> frontend/dist published."
    else
      echo "[publish] frontend build FAILED — production NOT updated. Tail of /tmp/ai_soc_fe_build.log:"
      tail -20 /tmp/ai_soc_fe_build.log
    fi
  fi
fi

# ---- backend: warn if dependency surfaces changed (image rebuild needed) ----
if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  if ! git -C "$ROOT" diff --quiet -- backend/pyproject.toml backend/Dockerfile 2>/dev/null \
     || ! git -C "$ROOT" diff --cached --quiet -- backend/pyproject.toml backend/Dockerfile 2>/dev/null; then
    echo "[publish] backend deps changed (pyproject.toml / Dockerfile). uvicorn --reload won't pick these up — run: docker compose build backend && docker compose up -d backend"
  fi
fi

exit 0
