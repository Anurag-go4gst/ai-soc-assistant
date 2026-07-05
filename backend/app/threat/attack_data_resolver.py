"""Offline ATT&CK (Excel) + ATLAS (YAML) technique-detail resolver (plan §15 WS-G).

Deterministic, air-gapped, no LLM, no network at call time. Uses the data the
operator vendored into the repo — the MITRE ATT&CK Enterprise Excel export and the
MITRE ATLAS YAML — instead of STIX + mitreattack-python, so it needs ZERO extra
runtime dependencies (xlsx is parsed with stdlib zipfile + xml; YAML via PyYAML,
already a dep).

Implements the ``TechniqueResolver`` Protocol from ``app.chat.grounding_assembler``
so it drops into ``assemble_grounding`` and ``validate_mitre_expansion_candidates``
with no caller changes.

Routing by ID prefix: ``AML.`` → ATLAS YAML; everything else → enterprise xlsx.

Important semantics (per attack.mitre.org/resources): the ATT&CK Excel export
EXCLUDES revoked/deprecated objects. So for an enterprise ``Txxxx``:
  present  → current/valid  (``detail`` returns the row)
  absent   → deprecated, revoked, renumbered, or non-enterprise → ``detail`` = None
Fail-closed everywhere: missing file / parse error / unknown id → None.
"""
from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger("ai_soc.threat.attack_data_resolver")

_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_ICS_TECHNIQUE_ID = re.compile(r"^T0[89]")
_ENTERPRISE_TECHNIQUE_ID = re.compile(r"^T\d")


def _repo_root() -> Path:
    """Base directory for resolving relative threat-resolver paths.

    Two run modes put this file at a different depth from anything worth
    calling "root", so a single fixed ``parents[N]`` cannot serve both:

    - Bare-run/pytest: ``<repo>/backend/app/threat/this_file.py`` — the real
      repo root is 3 parents up, and it has a ``docs/`` sibling of ``backend/``
      (where the vendored xlsx/yaml resolver data lives, e.g.
      ``AI_SOC_ATTACK_XLSX_PATH=docs/evals/...``, repo-root relative).
    - Docker (compose mounts ``./backend:/app``, ``working_dir: /app``): this
      file lives at ``/app/app/threat/this_file.py``. There is no repo root at
      all inside the container filesystem — ``parents[3]`` lands on ``/``,
      which silently broke every threat-resolver path config under Docker
      (the project's primary run mode) until a live probe surfaced honest
      "not found" facts for techniques known to be in the bundle (2026-07-05).
      Backend-relative paths (e.g. ``data/threat_intel/attack/...``) must
      resolve against ``/app`` — the backend-equivalent root — instead.

    Prefer the repo root only when it's real (has both ``docs/`` and
    ``backend/`` — the monorepo marker); otherwise fall back to the
    backend-equivalent root, which always exists in both modes.
    """
    backend_root = Path(__file__).resolve().parents[2]
    candidate_repo_root = Path(__file__).resolve().parents[3]
    if (candidate_repo_root / "docs").is_dir() and (candidate_repo_root / "backend").is_dir():
        return candidate_repo_root
    return backend_root


def _resolve_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    raw = str(path).strip()
    if not raw:
        return None
    resolved = Path(raw)
    return resolved if resolved.is_absolute() else _repo_root() / resolved


def absent_technique_disposition(technique_id: str) -> str:
    """Classify a None ``detail()`` for AttackDataResolver (COE G3 reporting).

    Enterprise xlsx excludes revoked/deprecated/renumbered techniques, so absent
    enterprise ``T*`` IDs are ``deprecated``. ICS ``T08xx``/``T09xx`` queried
    against the enterprise export are ``not_found`` (wrong matrix).
    """
    tid = (technique_id or "").strip()
    if tid.startswith("AML."):
        return "not_found"
    if _ICS_TECHNIQUE_ID.match(tid):
        return "not_found"
    if _ENTERPRISE_TECHNIQUE_ID.match(tid):
        return "deprecated"
    return "not_found"


def technique_resolver_from_settings() -> Any:
    """Build the best available offline resolver from ``settings`` (xlsx/yaml first)."""
    from app.config import settings
    from app.threat.resolver_types import NullTechniqueResolver
    from app.threat.stix_resolver import StixTechniqueResolver

    xlsx = _resolve_path(getattr(settings, "ai_soc_attack_xlsx_path", "") or None)
    yaml_path = _resolve_path(getattr(settings, "ai_soc_atlas_yaml_path", "") or None)
    if xlsx or yaml_path:
        resolver = AttackDataResolver(attack_xlsx_path=xlsx, atlas_yaml_path=yaml_path)
        if resolver.operational:
            return resolver
    attack = _resolve_path(getattr(settings, "ai_soc_attack_stix_path", "") or None)
    atlas = _resolve_path(getattr(settings, "ai_soc_atlas_stix_path", "") or None)
    if attack or atlas:
        return StixTechniqueResolver(
            attack_stix_path=str(attack) if attack else None,
            atlas_stix_path=str(atlas) if atlas else None,
        )
    return NullTechniqueResolver()


def _col_index(cell_ref: str) -> int:
    """'C12' -> 2 (zero-based column index)."""
    match = re.match(r"[A-Z]+", cell_ref or "")
    if match is None:
        return 0
    letters = match.group()
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _parse_xlsx_techniques(path: Path) -> dict[str, dict[str, Any]]:
    """Parse the ATT&CK Excel ``techniques`` sheet into {id: {name, description,
    version, tactics, url}}. Stdlib only. Returns {} on any failure (fail-closed)."""
    try:
        with zipfile.ZipFile(path) as z:
            shared = _shared_strings(z)
            sheet_part = _techniques_sheet_part(z)
            if sheet_part is None:
                return {}
            rows = ET.fromstring(z.read(sheet_part)).findall(f".//{_XLSX_NS}row")
            if not rows:
                return {}
            header = _row_values(rows[0], shared)
            col = {str(v).strip().lower(): i for i, v in header.items() if v}
            idc = col.get("id")
            if idc is None:
                return {}
            namec, descc = col.get("name"), col.get("description")
            verc, tacc, urlc = col.get("version"), col.get("tactics"), col.get("url")
            out: dict[str, dict[str, Any]] = {}
            for r in rows[1:]:
                vals = _row_values(r, shared)
                tid = str(vals.get(idc) or "").strip()
                if not tid:
                    continue
                out[tid] = {
                    "technique_id": tid,
                    "name": str(vals.get(namec) or "") if namec is not None else "",
                    "description": str(vals.get(descc) or "") if descc is not None else "",
                    "version": str(vals.get(verc) or "") if verc is not None else "",
                    "tactics": str(vals.get(tacc) or "") if tacc is not None else "",
                    "url": str(vals.get(urlc) or "") if urlc is not None else "",
                }
            return out
    except (OSError, zipfile.BadZipFile, ET.ParseError):
        logger.warning("ATT&CK xlsx parse failed, resolver degrades: %s", path, exc_info=True)
        return {}


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(f"{_XLSX_NS}t")) for si in root.findall(f"{_XLSX_NS}si")]


def _techniques_sheet_part(z: zipfile.ZipFile) -> str | None:
    """Map the 'techniques' sheet name → its worksheet part via workbook rels."""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {
        r.get("Id"): r.get("Target")
        for r in rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    }
    rns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    for sheet in wb.findall(f"{_XLSX_NS}sheets/{_XLSX_NS}sheet"):
        if str(sheet.get("name") or "").strip().lower() == "techniques":
            target = rid_to_target.get(sheet.get(rns))
            if target:
                return f"xl/{target.lstrip('/')}" if not target.startswith("xl/") else target
    return None


def _row_values(row: ET.Element, shared: list[str]) -> dict[int, Any]:
    out: dict[int, Any] = {}
    for c in row.findall(f"{_XLSX_NS}c"):
        idx = _col_index(c.get("r"))
        t = c.get("t")
        v = c.find(f"{_XLSX_NS}v")
        if v is None:
            inline = c.find(f"{_XLSX_NS}is")
            out[idx] = "".join(x.text or "" for x in inline.iter(f"{_XLSX_NS}t")) if inline is not None else ""
        elif t == "s":
            out[idx] = shared[int(v.text)] if v.text and int(v.text) < len(shared) else ""
        else:
            out[idx] = v.text
    return out


def _parse_atlas_yaml(path: Path) -> dict[str, dict[str, Any]]:
    """Parse ATLAS YAML matrices → {AML.Txxxx: {name, description}}. {} on failure."""
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - missing file / bad yaml / no pyyaml → fail-closed
        logger.warning("ATLAS yaml parse failed, resolver degrades: %s", path, exc_info=True)
        return {}
    out: dict[str, dict[str, Any]] = {}
    for matrix in (data or {}).get("matrices", []) if isinstance(data, dict) else []:
        for tech in matrix.get("techniques", []) if isinstance(matrix, dict) else []:
            tid = str(tech.get("id") or "").strip()
            if tid:
                out[tid] = {
                    "technique_id": tid,
                    "name": str(tech.get("name") or ""),
                    "description": str(tech.get("description") or ""),
                    "tactics": ",".join(tech.get("tactics", []) or []) if isinstance(tech.get("tactics"), list) else "",
                }
    return out


class AttackDataResolver:
    """Resolve enterprise (xlsx) + ATLAS (yaml) technique IDs to detail.

    Explicit paths (caller resolves from config) so the resolver has no implicit
    config dependency and is fixture-testable. Parsed data is process-cached.
    """

    def __init__(self, attack_xlsx_path: str | Path | None = None, atlas_yaml_path: str | Path | None = None) -> None:
        self._xlsx = _resolve_path(attack_xlsx_path)
        self._yaml = _resolve_path(atlas_yaml_path)
        self._enterprise_cache: dict[str, dict[str, Any]] | None = None
        self._atlas_cache: dict[str, dict[str, Any]] | None = None

    @property
    def operational(self) -> bool:
        return bool(
            (self._xlsx and self._xlsx.exists())
            or (self._yaml and self._yaml.exists())
        )

    @property
    def enterprise_operational(self) -> bool:
        return bool(self._xlsx and self._xlsx.exists())

    @property
    def atlas_operational(self) -> bool:
        return bool(self._yaml and self._yaml.exists())

    def _enterprise(self) -> dict[str, dict[str, Any]]:
        if self._enterprise_cache is None:
            self._enterprise_cache = (
                _parse_xlsx_techniques(self._xlsx) if self._xlsx and self._xlsx.exists() else {}
            )
        return self._enterprise_cache

    def _atlas(self) -> dict[str, dict[str, Any]]:
        if self._atlas_cache is None:
            self._atlas_cache = _parse_atlas_yaml(self._yaml) if self._yaml and self._yaml.exists() else {}
        return self._atlas_cache

    def detail(self, technique_id: str) -> dict[str, Any] | None:
        tid = (technique_id or "").strip()
        if not tid:
            return None
        if tid.startswith("AML."):
            row = self._atlas().get(tid)
            if row is None:
                return None
            return {**row, "deprecated": False, "revoked": False, "domain": "atlas"}
        row = self._enterprise().get(tid)
        if row is None:
            return None  # absent from current export = deprecated/revoked/renumbered
        return {**row, "deprecated": False, "revoked": False, "domain": "enterprise-attack"}
