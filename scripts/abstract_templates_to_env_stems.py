#!/usr/bin/env python3
"""WS2: abstract governed-template index/sourcetype to Environment-Knowledge stems.

For each target template, replace the concrete `index=<val>` / `sourcetype=<val>`
in spl_text with the matching `<stem>`, BUT only when
apply_template_env_bindings(abstracted) resolves byte-identically back to the
original SPL. Anything that does not round-trip exactly is left hardcoded.
Idempotent: already-abstracted templates are skipped.

Usage:
  PYTHONPATH=backend:. python3 scripts/abstract_templates_to_env_stems.py --check   # dry run
  PYTHONPATH=backend:. python3 scripts/abstract_templates_to_env_stems.py --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from app.spl.source_profile_resolver import apply_template_env_bindings

TEMPLATES = Path(__file__).resolve().parents[1] / "backend" / "app" / "spl" / "templates.json"

# sourcetype -> (index_stem, sourcetype_stem). Only deployments whose stems exist
# in the Environment Knowledge map (.env AI_SOC_SOURCE_PROFILE_MAP / policy).
SOURCETYPE_STEMS: dict[str, tuple[str, str]] = {
    "pgcil:auth": ("auth_index", "auth_sourcetype"),
    "pgcil:vpn": ("vpn_index", "vpn_sourcetype"),
    "pgcil:firewall": ("firewall_index", "firewall_sourcetype"),
    "pgcil:dns": ("dns_index", "dns_sourcetype"),
    "pgcil:edr": ("endpoint_index", "endpoint_process_sourcetype"),
}


def _abstract_spl(spl: str) -> str | None:
    """Return abstracted SPL, or None if not a clean single-index/sourcetype target."""
    indexes = re.findall(r"index=([A-Za-z0-9_*]+)", spl)
    sourcetypes = re.findall(r"sourcetype=([A-Za-z0-9_:./*-]+)", spl)
    if len(set(indexes)) != 1 or len(set(sourcetypes)) != 1:
        return None
    st = sourcetypes[0]
    if st not in SOURCETYPE_STEMS:
        return None
    index_stem, st_stem = SOURCETYPE_STEMS[st]
    out = re.sub(r"index=" + re.escape(indexes[0]) + r"\b", f"index=<{index_stem}>", spl)
    out = re.sub(r"sourcetype=" + re.escape(st) + r"\b", f"sourcetype=<{st_stem}>", out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    data = json.loads(TEMPLATES.read_text(encoding="utf-8"))
    templates = data if isinstance(data, list) else data.get("templates", [])

    abstracted, skipped, already = [], [], []
    for t in templates:
        if not isinstance(t, dict):
            continue
        spl = str(t.get("spl_text") or "")
        tid = t.get("template_id")
        if re.search(r"<[A-Za-z0-9_]+>", spl):  # real <stem> placeholder, not a `<` comparator
            already.append(tid)
            continue
        new_spl = _abstract_spl(spl)
        if new_spl is None:
            skipped.append(tid)
            continue
        resolved, _trace = apply_template_env_bindings(new_spl)
        if resolved != spl:
            # Does not round-trip byte-identically -> leave hardcoded.
            skipped.append(f"{tid}(no_roundtrip)")
            continue
        t["spl_text"] = new_spl
        abstracted.append(tid)

    print(f"abstracted={len(abstracted)} already={len(already)} skipped={len(skipped)}")
    print("  abstracted:", abstracted)
    print("  skipped:", skipped)
    if args.write and abstracted:
        # Preserve the original envelope ({"templates": [...]}) — the registry
        # loader reads payload.get("templates").
        out = data if isinstance(data, dict) else {"templates": templates}
        if isinstance(data, dict):
            out["templates"] = templates
        TEMPLATES.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print("WROTE", TEMPLATES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
