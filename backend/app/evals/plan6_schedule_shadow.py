"""Plan 6 A3 — production vs Plan-5 merged schedules as pure functions.

Wraps `scripts/eval_phase_merge_probe.py` so this module never constructs
`ResourcePlan` (that is classified production-module construction). Computes
both schedules; never executes MCP, SPL, or chat. No new env flag.
"""

from __future__ import annotations

from typing import Any

from scripts.eval_phase_merge_probe import run_probes


def compare_schedules_offline() -> dict[str, Any]:
    """Production (v2 projection) vs merged Plan-5 schedule. No connector I/O."""
    payload = run_probes()
    rows: list[dict[str, Any]] = []
    for row in payload["rows"]:
        production = list(row["v2_hooks"])
        merged_hooks = list(row["merged_hooks"])
        rows.append(
            {
                "probe_id": row["probe_id"],
                "production_hooks": production,
                "merged_hooks": merged_hooks,
                "compiler_hooks": list(row["compiler_hooks"]),
                "compiler_downgrade": row["compiler_downgrade"],
                "merge_downgrade": row["merge_downgrade"],
                "inserted_vs_production": sorted(set(merged_hooks) - set(production)),
                "dropped_vs_production": sorted(set(production) - set(merged_hooks)),
                "capability_satisfied": row["capability_satisfied"],
            }
        )
    return {
        "schema_version": "plan6_schedule_shadow_v1",
        "execute_mcp": False,
        "rows": rows,
    }
