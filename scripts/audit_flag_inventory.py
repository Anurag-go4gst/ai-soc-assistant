#!/usr/bin/env python3
"""Generate flag inventory data for docs/architecture/flag_rightsizing_audit.md (plan 0.4)."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO / ".env.example"
CONFIG_PY = REPO / "backend" / "app" / "config.py"
PROFILE_DIR = REPO / "env" / "profiles"
BACKEND = REPO / "backend" / "app"
OUT_JSON = REPO / "docs" / "architecture" / "flag_rightsizing_audit_data.json"

# Keys that must never be deleted without hardcoding behavior first (safety invariants).
SAFETY_INVARIANT_KEYS = {
    "SPL_BLOCKED_COMMANDS",
    "SPL_VALIDATION_ENABLED",
    "MCP_GLOBAL_EXECUTION_ENABLED",
    "MCP_SERVER_MOCK_EXECUTION_ENABLED",
    "AI_SOC_REQUIRE_SPL_EXECUTION_CONFIRMATION",
    "AI_SOC_REQUIRE_HIL_FOR_MOCK_EXECUTION",
    "LLM_TOOL_RECOMMENDATION_ENABLED",
}

# Legacy duplicates / aliases — candidate fold-in or delete after shim.
DUPLICATE_GROUPS: list[list[str]] = [
    ["SPLUNK_MCP_ENABLED", "MCP_MODE"],
    ["LLM_ENABLED", "AI_SOC_LLM_MODE", "LLM_MODE"],
    ["FOUNDATION_SEC_INSTRUCT_URL", "LLM_PROVIDER_FOUNDATION_SEC_INSTRUCT_URL"],
    ["FOUNDATION_SEC_REASONING_URL", "LLM_PROVIDER_FOUNDATION_SEC_REASONING_URL"],
]

# Stage-scaffold flags with zero product effect when off (grep-only in config/tests).
STAGE_SCAFFOLD_PATTERNS = (
    re.compile(r"_FLOW_CHECK_"),
    re.compile(r"_SHADOW_"),
    re.compile(r"STAGE3"),
    re.compile(r"_LAB_"),
)

POSTURE_PREFIXES = (
    "AI_SOC_",
    "CONTROL_PLANE_",
    "MCP_",
    "SOC_KB_",
    "QUALITY_",
    "ROUTING_",
    "SPL_",
    "RAG_",
    "LLM_",
    "EMBEDDINGS_",
    "TELEMETRY_",
    "DEBUG_",
    "APP_AUTH_",
)

OPERATOR_SUFFIXES = (
    "_URL",
    "_TOKEN",
    "_PASSWORD",
    "_SECRET",
    "_PATH",
    "_PORT",
    "_TIMEOUT",
    "_MS",
    "_SECONDS",
    "_DIR",
    "_DSN",
    "_API_KEY",
    "_BASE_URL",
    "_ALLOWLIST",
    "_BUDGET",
    "_DEADLINE",
    "_MAX_",
    "_MIN_",
    "_INTERVAL",
)


@dataclass
class FlagRow:
    env_key: str
    config_field: str | None
    default_env: str | None
    profile_values: dict[str, str]
    read_sites: list[str]
    git_intro: str | None
    classification: str
    disposition: str
    batch: str | None
    evidence: str
    risk_note: str


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def parse_settings_fields() -> dict[str, Any]:
    tree = ast.parse(CONFIG_PY.read_text(encoding="utf-8"))
    fields: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    default = None
                    if item.value is not None:
                        if isinstance(item.value, ast.Constant):
                            default = item.value.value
                        elif isinstance(item.value, ast.Name):
                            default = item.value.id
                    fields[item.target.id] = default
    return fields


def env_to_field(env_key: str) -> str:
    return env_key.lower()


def field_to_env(field: str) -> str:
    return field.upper()


def grep_read_sites(env_key: str, field: str | None) -> list[str]:
    patterns = {env_key}
    if field:
        patterns.add(f"settings.{field}")
        patterns.add(f'"{field}"')
    hits: set[str] = set()
    for pattern in patterns:
        try:
            proc = subprocess.run(
                ["rg", "-l", "--glob", "!**/__pycache__/**", pattern, str(BACKEND), str(REPO / "frontend" / "src"), str(REPO / "scripts")],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in proc.stdout.splitlines():
            rel = str(Path(line).relative_to(REPO)) if line.startswith(str(REPO)) else line
            if rel.endswith("config.py") and pattern == env_key:
                continue
            hits.add(rel)
    return sorted(hits)[:8]


def git_intro(path: Path, needle: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%h %cs %s", "-S", needle, "--", str(path.relative_to(REPO))],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        line = proc.stdout.strip()
        return line or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def classify(
    env_key: str,
    *,
    read_sites: list[str],
    in_config: bool,
    profile_values: dict[str, str],
) -> tuple[str, str, str | None, str]:
    """Return classification, disposition, batch, risk_note."""
    if env_key in SAFETY_INVARIANT_KEYS:
        return (
            "a_safety_invariant",
            "hardcode_then_delete",
            "D",
            "Safety gate — hardcode fail-closed behavior before removing env key.",
        )

    for group in DUPLICATE_GROUPS:
        if env_key in group:
            canonical = group[0]
            if env_key != canonical:
                return (
                    "d_duplicate",
                    "delete_alias",
                    "B",
                    f"Duplicate of {canonical}; consolidate with compat shim one release.",
                )

    if not read_sites and not in_config:
        return ("d_dead", "delete", "A", "No runtime read sites outside env templates.")

    if any(p.search(env_key) for p in STAGE_SCAFFOLD_PATTERNS):
        if len(read_sites) <= 2:
            return ("d_stage_scaffold", "delete", "A", "Stage-scaffold / trace-only; limited read sites.")

    if any(env_key.endswith(s) or s in env_key for s in OPERATOR_SUFFIXES):
        return ("c_operator_infra", "keep", None, "Operator-managed URL/credential/budget — keep in profile.")

    if env_key.startswith(POSTURE_PREFIXES) or env_key in {
        "CONTROL_PLANE_ENABLED",
        "MCP_MODE",
        "RAG_MODE",
        "LLM_MODE",
        "EMBEDDINGS_MODE",
        "TELEMETRY_MODE",
    }:
        # Check if always-on across profiles
        vals = set(profile_values.values())
        if vals == {"true"} or vals == {"false"}:
            if env_key.endswith("_ENABLED") and vals == {"true"}:
                return (
                    "e_permanent_on",
                    "fold_in",
                    "C",
                    "Same value across all profile examples — fold into code default.",
                )
        return ("b_posture", "keep_group", None, "Governance posture — group under master toggles in Phase 7.")

    if not in_config:
        return ("keep_unresolved", "keep", None, "Env key not mapped in Settings — manual review required.")

    if len(read_sites) <= 1:
        return ("keep_unresolved", "keep", None, "Read sites not fully traced — doubt rule applies.")

    return ("c_operator_infra", "keep", None, "General app config — retain unless proven dead.")


def build_rows() -> list[FlagRow]:
    env_defaults = parse_env_file(ENV_EXAMPLE)
    settings_fields = parse_settings_fields()
    profiles = {
        p.stem.replace(".env", ""): parse_env_file(p)
        for p in sorted(PROFILE_DIR.glob("*.env.example"))
    }

    all_keys = sorted(set(env_defaults) | {field_to_env(f) for f in settings_fields})
    rows: list[FlagRow] = []
    for env_key in all_keys:
        field = env_to_field(env_key)
        in_config = field in settings_fields
        profile_values = {name: vals[env_key] for name, vals in profiles.items() if env_key in vals}
        read_sites = grep_read_sites(env_key, field if in_config else None)
        intro = git_intro(CONFIG_PY, env_key) or git_intro(ENV_EXAMPLE, env_key)
        classification, disposition, batch, risk = classify(
            env_key,
            read_sites=read_sites,
            in_config=in_config,
            profile_values=profile_values,
        )
        evidence_parts = []
        if read_sites:
            evidence_parts.append(f"rg: {', '.join(read_sites[:3])}")
        if intro:
            evidence_parts.append(f"git: {intro}")
        if not evidence_parts:
            evidence_parts.append("grep: config/env only")
        rows.append(
            FlagRow(
                env_key=env_key,
                config_field=field if in_config else None,
                default_env=env_defaults.get(env_key),
                profile_values=profile_values,
                read_sites=read_sites,
                git_intro=intro,
                classification=classification,
                disposition=disposition,
                batch=batch,
                evidence="; ".join(evidence_parts),
                risk_note=risk,
            )
        )
    return rows


def render_markdown(rows: list[FlagRow]) -> str:
    counts: dict[str, int] = defaultdict(int)
    batch_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row.disposition] += 1
        if row.batch:
            batch_counts[row.batch] += 1

    lines = [
        "# Flag rightsizing audit (plan 0.4)",
        "",
        "**Status:** Draft proposal for DG-4 batch approval. No flags deleted in this item — documentation only.",
        "",
        "## Scope",
        "",
        f"- `.env.example`: {len(parse_env_file(ENV_EXAMPLE))} keys",
        f"- `backend/app/config.py` Settings: {len(parse_settings_fields())} fields",
        f"- Profiles: {', '.join(p.name for p in PROFILE_DIR.glob('*.env.example'))}",
        f"- **Disposition table rows:** {len(rows)} (one row per canonical env key)",
        "",
        "## Target end-state",
        "",
        "- **Profile key budget:** <60 operator + posture keys (correctness beats count).",
        "- **Master posture groups (proposed):** `AI_SOC_GOVERNANCE_PROFILE`, `MCP_EXECUTION_PROFILE`, `LLM_SYNTHESIS_PROFILE`, `RAG_PROFILE`.",
        "- **Safety invariants:** SPL blocklist, MCP global off-default, no LLM-to-MCP, HIL confirmation — hardcoded after Batch D.",
        "",
        "## Disposition summary",
        "",
        "| Disposition | Count |",
        "|-------------|------:|",
    ]
    for disp in sorted(counts):
        lines.append(f"| `{disp}` | {counts[disp]} |")

    lines.extend(
        [
            "",
            "## DG-4 deletion batches (proposal — requires user approval before Phase 7.1)",
            "",
            "| Batch | Risk | Disposition types | Count |",
            "|-------|------|-------------------|------:|",
            f"| **A** | Lowest | `delete` dead/scaffold | {batch_counts.get('A', 0)} |",
            f"| **B** | Low | `delete_alias` duplicates | {batch_counts.get('B', 0)} |",
            f"| **C** | Medium | `fold_in` permanent-on | {batch_counts.get('C', 0)} |",
            f"| **D** | Highest | `hardcode_then_delete` safety | {batch_counts.get('D', 0)} |",
            "",
            "**Doubt rule:** Rows with `keep` / `keep_unresolved` are excluded from all batches until traced.",
            "",
            "## Per-flag disposition table",
            "",
            "| Flag | Config field | Default (.env.example) | Profile values | Read sites (sample) | Class | Disposition | Batch | Evidence | Risk |",
            "|------|--------------|------------------------|----------------|---------------------|-------|-------------|-------|----------|------|",
        ]
    )

    for row in rows:
        prof = "; ".join(f"{k}={v}" for k, v in sorted(row.profile_values.items())) or "—"
        sites = ", ".join(row.read_sites[:3]) if row.read_sites else "—"
        if len(row.read_sites) > 3:
            sites += f" (+{len(row.read_sites) - 3})"
        default = (row.default_env or "—")[:40]
        lines.append(
            f"| `{row.env_key}` | `{row.config_field or '—'}` | `{default}` | {prof} | {sites} | {row.classification} | {row.disposition} | {row.batch or '—'} | {row.evidence[:80]} | {row.risk_note[:60]} |"
        )

    lines.extend(
        [
            "",
            "## Migration notes (Phase 7.2)",
            "",
            "Compat shim: log warning (do not crash) when retired keys are present for one release.",
            "",
            "| Retired key | Replacement / behavior |",
            "|-------------|------------------------|",
        ]
    )
    for row in rows:
        if row.disposition in {"delete_alias", "fold_in", "delete"}:
            lines.append(f"| `{row.env_key}` | See disposition `{row.disposition}` — {row.risk_note} |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    rows = build_rows()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps([row.__dict__ for row in rows], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path = REPO / "docs" / "architecture" / "flag_rightsizing_audit.md"
    md_path.write_text(render_markdown(rows), encoding="utf-8")
    print(f"wrote {md_path} ({len(rows)} rows)")
    print(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
