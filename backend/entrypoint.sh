#!/bin/sh
set -eu

if [ -f scripts/migrate_ai_soc_db.py ]; then
  python scripts/migrate_ai_soc_db.py || {
    echo "database migration failed; refusing to start backend" >&2
    exit 1
  }
fi

exec "$@"
