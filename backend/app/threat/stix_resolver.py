"""Offline ATT&CK / ATLAS technique-detail resolver (plan §15 WS-G G2).

Deterministic, air-gapped, no LLM, no network. Implements the
``TechniqueResolver`` Protocol from ``app.chat.grounding_assembler`` so it drops
into ``assemble_grounding(resolver=...)`` and the coverage-card builders with zero
caller changes.

Fail-closed by construction: ``mitreattack-python`` is an OPTIONAL import and the
STIX bundles are operator-vendored artifacts. If the library is absent, a bundle
path is unset, the file is missing, or a lookup misses, ``detail()`` returns
``None`` — the resolver never fabricates and never raises into the caller.

Routing: IDs prefixed ``AML.`` resolve against the ATLAS bundle; everything else
against the enterprise ATT&CK bundle. Bundles are parsed lazily and cached per
process (STIX parsing is heavy).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_soc.threat.stix_resolver")

# Optional dependency. Air-gapped deployments onboard the wheel via the transfer
# SOP; until then the resolver degrades to None (same as NullTechniqueResolver).
try:  # pragma: no cover - import availability is environment-dependent
    from mitreattack.stix20 import MitreAttackData  # type: ignore
    _MITREATTACK_AVAILABLE = True
except Exception:  # noqa: BLE001 - any import failure means "not onboarded"
    MitreAttackData = None  # type: ignore[assignment]
    _MITREATTACK_AVAILABLE = False


def library_available() -> bool:
    """True when mitreattack-python is importable in this environment."""
    return _MITREATTACK_AVAILABLE


class StixTechniqueResolver:
    """Resolve ATT&CK/ATLAS technique IDs to name/description via local STIX bundles.

    Parameters are explicit paths (caller resolves them from config) so the resolver
    has no implicit config dependency and is trivially testable with a fixture bundle.
    """

    def __init__(
        self,
        attack_stix_path: str | Path | None = None,
        atlas_stix_path: str | Path | None = None,
    ) -> None:
        self._attack_path = Path(attack_stix_path) if attack_stix_path else None
        self._atlas_path = Path(atlas_stix_path) if atlas_stix_path else None
        # Lazy-loaded MitreAttackData handles, keyed by domain. None until first use;
        # False marks a load that was attempted and failed (don't retry every call).
        self._attack_data: Any = None
        self._atlas_data: Any = None

    @property
    def operational(self) -> bool:
        """True only when the library is present AND at least one bundle is configured."""
        return _MITREATTACK_AVAILABLE and bool(self._attack_path or self._atlas_path)

    def _load(self, path: Path | None) -> Any:
        """Return a MitreAttackData handle for a bundle path, or None (fail-closed)."""
        if not _MITREATTACK_AVAILABLE or path is None:
            return None
        if not path.exists():
            logger.warning("STIX bundle not found, resolver degrades to None: %s", path)
            return None
        try:
            return MitreAttackData(str(path))  # type: ignore[misc]
        except Exception:  # noqa: BLE001 - parse failure must not break callers
            logger.warning("STIX bundle failed to parse, resolver degrades: %s", path, exc_info=True)
            return None

    def _data_for(self, technique_id: str) -> Any:
        """Pick + lazily load the bundle for a technique ID by prefix."""
        if technique_id.startswith("AML."):
            if self._atlas_data is None:
                self._atlas_data = self._load(self._atlas_path) or False
            return self._atlas_data or None
        if self._attack_data is None:
            self._attack_data = self._load(self._attack_path) or False
        return self._attack_data or None

    def detail(self, technique_id: str) -> dict[str, Any] | None:
        """Return technique detail, or None if unresolvable (fail-closed).

        Shape: ``{name, description, deprecated, revoked, domain, url}``. Never
        raises into the caller; any internal failure yields None.
        """
        tid = (technique_id or "").strip()
        if not tid:
            return None
        data = self._data_for(tid)
        if data is None:
            return None
        try:
            obj = data.get_object_by_attack_id(tid, "attack-pattern")
        except Exception:  # noqa: BLE001 - lookup failure -> None, not a crash
            logger.debug("STIX lookup failed for %s", tid, exc_info=True)
            return None
        if obj is None:
            return None
        return _normalize(obj, tid)


def _normalize(obj: Any, technique_id: str) -> dict[str, Any]:
    """Map a STIX attack-pattern object to our flat detail dict, defensively."""
    refs = _get(obj, "external_references") or []
    url = ""
    for ref in refs:
        ref_url = _get(ref, "url")
        if ref_url:
            url = ref_url
            break
    return {
        "technique_id": technique_id,
        "name": _get(obj, "name") or "",
        "description": _get(obj, "description") or "",
        "deprecated": bool(_get(obj, "x_mitre_deprecated") or False),
        "revoked": bool(_get(obj, "revoked") or False),
        "domain": "atlas" if technique_id.startswith("AML.") else "enterprise-attack",
        "url": url,
    }


def _get(obj: Any, key: str) -> Any:
    """Read a field whether the STIX object is dict-like or attribute-like."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
