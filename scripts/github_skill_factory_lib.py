"""Shared offline helpers for GitHub Skill Expansion Factory scripts.

No ``app.*`` imports. Never copies raw SKILL.md bodies into generated artifacts.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INTAKE_REGISTER_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_intake_register.json"
ENRICHMENT_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "content_enrichment.json"
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"

DEFAULT_CLONE_ROOT = Path("/tmp/ai-soc-references/Anthropic-Cybersecurity-Skills")
CLONE_ROOT_ENV = "AI_SOC_GITHUB_SKILL_CLONE_ROOT"

MITRE_METADATA_ROLE = "metadata_not_evidence"
GITHUB_ACCEPTANCE_NOTE = (
    "GitHub decision=accept means accepted_for_enrichment only — not runtime_active "
    "and not a live execution skill."
)

ALLOWED_LIVE_SKILLS = frozenset(
    {"alert_summary", "spl_generation", "attack_discovery", "knowledge_recall"}
)

_MITRE_RE = re.compile(r"\bT\d{4}(?:\.\d{3})?\b", re.IGNORECASE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def resolve_clone_root(
    *,
    fixture_root: Path | None = None,
    allow_missing: bool = False,
) -> Path:
    if fixture_root is not None:
        root = fixture_root.expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(
                f"fixture clone root does not exist: {root}\n"
                "Provide a temporary test fixture directory containing skills/**/SKILL.md"
            )
        return root
    env_value = os.environ.get(CLONE_ROOT_ENV, "").strip()
    root = Path(env_value).expanduser().resolve() if env_value else DEFAULT_CLONE_ROOT.resolve()
    if not root.is_dir():
        if allow_missing:
            return root
        raise FileNotFoundError(
            f"GitHub skill clone root not found: {root}\n"
            f"Clone the reference repo locally or set {CLONE_ROOT_ENV}.\n"
            "Example:\n"
            "  git clone https://github.com/mukul975/Anthropic-Cybersecurity-Skills "
            f"{DEFAULT_CLONE_ROOT}\n"
            "Tests must pass --fixture-root instead of requiring the real clone."
        )
    return root


def load_json(path: Path, warnings: list[str] | None = None) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        if warnings is not None:
            warnings.append(f"source file missing: {path}")
        return None
    except (json.JSONDecodeError, OSError) as exc:
        if warnings is not None:
            warnings.append(f"could not read {path}: {exc}")
        return None


def load_intake_register(warnings: list[str] | None = None) -> dict[str, Any]:
    payload = load_json(INTAKE_REGISTER_PATH, warnings)
    return payload if isinstance(payload, dict) else {"records": []}


def intake_by_skill_id(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in register.get("records") or []:
        if isinstance(record, dict) and record.get("github_skill_id"):
            index[str(record["github_skill_id"])] = record
    return index


def parse_frontmatter(text: str) -> dict[str, Any]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)
    metadata: dict[str, Any] = {}
    current_key: str | None = None
    list_mode = False
    for line in block.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key and list_mode:
            metadata.setdefault(current_key, []).append(line[4:].strip().strip("'\""))
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if not value:
            current_key = key
            list_mode = True
            metadata[key] = []
            continue
        list_mode = False
        current_key = key
        metadata[key] = value
    return metadata


def extract_title(text: str, github_skill_id: str) -> str:
    match = _FRONTMATTER_RE.match(text)
    body = text[match.end() :] if match else text
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return github_skill_id.replace("-", " ").title()


def extract_mitre_attack(metadata: dict[str, Any], text: str) -> list[str]:
    values: set[str] = set()
    raw = metadata.get("mitre_attack")
    if isinstance(raw, list):
        values.update(str(item).upper() for item in raw if item)
    elif isinstance(raw, str) and raw:
        values.add(raw.upper())
    for match in _MITRE_RE.findall(text[:4000]):
        values.add(match.upper())
    return sorted(values)


def infer_domain_subdomain(metadata: dict[str, Any], github_skill_id: str) -> tuple[str, str]:
    domain = str(metadata.get("domain") or metadata.get("subdomain") or "soc-operations")
    subdomain = str(metadata.get("subdomain") or metadata.get("domain") or github_skill_id)
    domain = domain.replace("cybersecurity", "soc-operations")
    return domain, subdomain


def infer_tags(metadata: dict[str, Any], github_skill_id: str) -> list[str]:
    tags = metadata.get("tags")
    if isinstance(tags, list):
        return sorted({str(tag) for tag in tags if tag})
    if isinstance(tags, str) and tags:
        return [tags]
    return sorted({github_skill_id.replace("-", "_"), "github-skill"})


def likely_soc_relevance(metadata: dict[str, Any], text: str) -> str:
    haystack = " ".join(
        [
            str(metadata.get("description") or ""),
            str(metadata.get("name") or ""),
            text[:2000].lower(),
        ]
    ).lower()
    positive = (
        "splunk",
        "siem",
        "soc",
        "blue-team",
        "threat-hunt",
        "incident",
        "phishing",
        "brute",
        "ransomware",
        "powershell",
        "beacon",
        "detection",
        "investigation",
        "triage",
    )
    negative = ("exploit development", "payload generation", "offensive", "red team attack")
    if any(term in haystack for term in negative):
        return "low"
    if any(term in haystack for term in positive):
        return "high"
    return "medium"


def likely_internal_domain(metadata: dict[str, Any], github_skill_id: str) -> str:
    domain, _ = infer_domain_subdomain(metadata, github_skill_id)
    mapping = {
        "identity-access-management": "identity-access-management",
        "authentication-security": "identity-access-management",
        "endpoint-security": "endpoint-security",
        "phishing-defense": "phishing-defense",
        "incident-response": "incident-response",
        "threat-hunting": "threat-hunting",
        "ransomware-defense": "ransomware-defense",
        "soc-operations": "soc-operations",
    }
    for key, value in mapping.items():
        if key in domain or key in github_skill_id:
            return value
    return "soc-operations"


def scan_skill_files(clone_root: Path) -> list[Path]:
    skills_root = clone_root / "skills"
    if skills_root.is_dir():
        return sorted(skills_root.glob("**/SKILL.md"))
    return sorted(clone_root.glob("**/SKILL.md"))


def skill_id_from_path(skill_path: Path, clone_root: Path) -> str:
    try:
        rel = skill_path.relative_to(clone_root / "skills")
        return rel.parts[0]
    except ValueError:
        return skill_path.parent.name


def relative_skill_path(skill_path: Path, clone_root: Path) -> str:
    try:
        return str(skill_path.relative_to(clone_root)).replace("\\", "/")
    except ValueError:
        return str(skill_path)


def duplicate_of_existing(skill_id: str, intake_index: dict[str, dict[str, Any]]) -> str | None:
    record = intake_index.get(skill_id)
    if record and record.get("decision") == "accept":
        return skill_id
    return None
