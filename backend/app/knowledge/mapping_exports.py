"""Read-only Knowledge mapping export builders (no runtime routing changes)."""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.analysis.soc_aggregates import rules_coverage_map
from app.threat.mitre_kb import load_mitre_techniques
from app.use_cases.content_enrichment import content_enrichment_records
from contracts.skill_enum import SKILL_ENUM

MITRE_METADATA_ROLE = "metadata_not_evidence"


def build_detection_coverage() -> dict[str, Any]:
    """Deterministic MITRE detection-coverage / gap map (Wazuh A3 shape).

    Each governed MITRE technique in the subset is a framework entry; the use
    cases that reference it (``related_use_cases``) are its covering detection
    rules. Techniques with no covering use case are detection gaps. Read-only —
    no runtime routing or evidence change.
    """
    techniques = load_mitre_techniques()
    rules = [
        {"framework_id": technique.technique_id, "rule_id": use_case}
        for technique in techniques
        for use_case in technique.related_use_cases
        if use_case
    ]
    coverage = rules_coverage_map(rules)
    technique_rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for technique in techniques:
        covering = coverage.get(technique.technique_id, [])
        row = {
            "technique_id": technique.technique_id,
            "name": technique.name,
            "tactic": technique.tactic,
            "covering_use_cases": covering,
            "covered": bool(covering),
        }
        technique_rows.append(row)
        if not covering:
            gaps.append(
                {
                    "technique_id": technique.technique_id,
                    "name": technique.name,
                    "tactic": technique.tactic,
                }
            )
    return {
        "schema_role": "detection_coverage_v1",
        "mitre_metadata_role": MITRE_METADATA_ROLE,
        "technique_count": len(techniques),
        "covered_count": len(techniques) - len(gaps),
        "gap_count": len(gaps),
        "coverage": coverage,
        "techniques": technique_rows,
        "gaps": gaps,
    }

_REPO_ROOT_CANDIDATES = (
    Path(__file__).resolve().parents[3],
    Path("/workspace"),
)

# MITRE ATLAS (AI/ML threat taxonomy) raw Navigator layers — operator-supplied,
# preserved unmodified. These layers carry techniqueID + tactic (+ case-study
# score) only; they have NO technique names/descriptions, so this builder reports
# structure/frequency/coverage gap, not human-readable technique detail.
_ATLAS_MATRIX_PATH = "docs/threat-intel/atlas/raw/ATLAS_Matrix.json"
_ATLAS_FREQ_PATH = "docs/threat-intel/atlas/raw/ATLAS_Case_Study_Frequency.json"
# WS-E E3: collapsed canonical layer (one row per techniqueID with tactics[] +
# per-tactic scores + source_sha256 provenance). Preferred over raw when present.
_ATLAS_NORMALIZED_PATH = "docs/threat-intel/atlas/normalized/atlas_matrix_normalized.json"
_ATLAS_CASESTUDIES_PATH = "docs/threat-intel/atlas/normalized/atlas_casestudies_normalized.json"
_ATLAS_MITIGATIONS_PATH = "docs/threat-intel/atlas/normalized/atlas_mitigations_normalized.json"
# ATLAS tactics with no enterprise-ATT&CK analogue → zero SOC coverage by design.
_ATLAS_AI_ONLY_TACTICS = ("ai-attack-staging", "ai-model-access")


def _load_atlas_normalized() -> dict[str, Any] | None:
    """Return the E3 normalized ATLAS artifact, or None if absent/unreadable."""
    path = repo_root() / _ATLAS_NORMALIZED_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    techniques = payload.get("techniques") if isinstance(payload, dict) else None
    return payload if isinstance(techniques, list) else None


def _load_atlas_casestudies() -> dict[str, Any] | None:
    """Return normalized ATLAS case-study rows, or None if absent/unreadable."""
    path = repo_root() / _ATLAS_CASESTUDIES_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    rows = payload.get("case_studies") if isinstance(payload, dict) else None
    return payload if isinstance(rows, list) else None


def _load_atlas_mitigations() -> dict[str, Any] | None:
    """Return normalized ATLAS mitigation rows, or None if absent/unreadable."""
    path = repo_root() / _ATLAS_MITIGATIONS_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    rows = payload.get("mitigations") if isinstance(payload, dict) else None
    return payload if isinstance(rows, list) else None


def atlas_technique_enrichment(technique_id: str) -> dict[str, Any]:
    """Mitigations and case studies linked to one AML technique id (fail-closed)."""
    tid = str(technique_id or "").strip()
    empty: dict[str, Any] = {"mitigations": [], "case_studies": []}
    if not tid:
        return empty

    case_payload = _load_atlas_casestudies()
    mitigation_payload = _load_atlas_mitigations()
    if case_payload is None or mitigation_payload is None:
        return empty

    mitigations: list[dict[str, str]] = []
    for row in mitigation_payload.get("mitigations") or []:
        if not isinstance(row, dict):
            continue
        technique_ids = {str(item) for item in row.get("technique_ids") or []}
        if tid not in technique_ids:
            continue
        mitigations.append(
            {
                "id": str(row.get("mitigation_id") or ""),
                "name": str(row.get("name") or ""),
                "url": str(row.get("url") or ""),
            }
        )

    case_studies: list[dict[str, str]] = []
    for row in case_payload.get("case_studies") or []:
        if not isinstance(row, dict):
            continue
        technique_ids = {str(item) for item in row.get("technique_ids") or []}
        if tid not in technique_ids:
            continue
        case_studies.append(
            {
                "id": str(row.get("case_study_id") or ""),
                "name": str(row.get("name") or ""),
                "url": str(row.get("url") or ""),
            }
        )

    mitigations.sort(key=lambda item: item["id"])
    case_studies.sort(key=lambda item: item["id"])
    return {"mitigations": mitigations, "case_studies": case_studies}


@lru_cache(maxsize=1)
def atlas_tactic_label_map() -> dict[str, str]:
    """Map AML.TA#### tactic ids to display names from the vendored ATLAS YAML."""
    from app.config import settings

    yaml_rel = getattr(settings, "ai_soc_atlas_yaml_path", "") or "docs/threat-intel/atlas/raw/ATLAS.yaml"
    path = Path(yaml_rel) if Path(yaml_rel).is_absolute() else repo_root() / yaml_rel
    if not path.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    labels: dict[str, str] = {}
    for matrix in (data or {}).get("matrices", []) if isinstance(data, dict) else []:
        for tactic in matrix.get("tactics", []) if isinstance(matrix, dict) else []:
            if not isinstance(tactic, dict):
                continue
            tid = str(tactic.get("id") or "").strip()
            name = str(tactic.get("name") or "").strip()
            if tid and name:
                labels[tid] = name
    return labels


def _atlas_technique_names(technique_ids: list[str]) -> dict[str, str]:
    """Resolve AML technique IDs → names via the offline ATLAS YAML resolver.

    Returns {} when the resolver is not onboarded (graceful ID-only fallback). Names
    are metadata only — never authority over status/coverage.
    """
    try:
        from app.config import settings
        from app.threat.attack_data_resolver import AttackDataResolver

        yaml_path = getattr(settings, "ai_soc_atlas_yaml_path", "") or ""
        if not yaml_path:
            return {}
        path = yaml_path if Path(yaml_path).is_absolute() else str(repo_root() / yaml_path)
        resolver = AttackDataResolver(atlas_yaml_path=path)
        if not resolver.operational:
            return {}
        names: dict[str, str] = {}
        for tid in technique_ids:
            detail = resolver.detail(tid)
            if detail and detail.get("name"):
                names[tid] = detail["name"]
        return names
    except Exception:  # noqa: BLE001 - enrichment is best-effort; never break the card
        return {}


def _load_atlas_layer(path_suffix: str) -> list[dict[str, Any]] | None:
    """Return the ``techniques`` rows of an ATLAS Navigator layer, or None if the
    file is absent/unreadable (air-gapped deployments may not have onboarded it)."""
    path = repo_root() / path_suffix
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    techniques = payload.get("techniques") if isinstance(payload, dict) else None
    return [row for row in techniques if isinstance(row, dict)] if isinstance(techniques, list) else None


def build_atlas_coverage_gap() -> dict[str, Any]:
    """Deterministic MITRE ATLAS (AI/ML threat) coverage-gap lane for the Knowledge page.

    ATLAS is a separate taxonomy (``AML.Txxxx``) from our enterprise ATT&CK subset,
    so enterprise coverage of ATLAS is structurally zero — every AML technique is an
    AI/LLM/MCP-threat detection gap today. Reports the gap honestly, weights it by
    real-world case-study frequency, and fails closed when ATLAS is not onboarded.
    Read-only; no runtime routing or evidence change.
    """
    limitation_ids_only = (
        "ATLAS Navigator layers carry technique IDs + tactics + case-study scores only "
        "(no names/descriptions); load the full ATLAS data bundle for analyst-readable detail."
    )
    id_tactics: dict[str, set[str]] = {}
    per_tactic: Counter[str] = Counter()
    freq: dict[str, Any] = {}
    normalization_provenance: dict[str, Any] | None = None

    # WS-E: prefer the E3 normalized canonical layer (collapsed, provenance-stamped);
    # fall back to the raw Navigator layers; fail closed if neither is onboarded.
    normalized = _load_atlas_normalized()
    if normalized is not None:
        atlas_source_status = "onboarded_normalized"
        normalization_provenance = {
            "source_sha256": (normalized.get("provenance") or {}).get("source_sha256"),
            "normalization_rules_version": normalized.get("normalization_rules_version"),
            "source_file": (normalized.get("provenance") or {}).get("source_file"),
        }
        for row in normalized["techniques"]:
            tid = str(row.get("technique_id") or "")
            if not tid:
                continue
            tactics = row.get("tactics") or []
            id_tactics.setdefault(tid, set()).update(str(t) for t in tactics)
            for t in tactics:
                per_tactic[str(t)] += 1
            freq[tid] = row.get("case_study_score", 0)
    else:
        matrix = _load_atlas_layer(_ATLAS_MATRIX_PATH)
        if matrix is None:
            return {
                "schema_role": "atlas_coverage_gap_v1",
                "atlas_source_status": "not_onboarded",
                "technique_count": 0,
                "covered_count": 0,
                "gap_count": 0,
                "tactics": {},
                "ai_only_tactics": {},
                "top_techniques_by_case_study_frequency": [],
                "limitation": "ATLAS raw layer is not onboarded in this deployment; AI-threat coverage is unknown.",
            }
        atlas_source_status = "onboarded_raw_layer"
        freq_rows = _load_atlas_layer(_ATLAS_FREQ_PATH) or []
        freq = {row.get("techniqueID"): row.get("score", 0) for row in freq_rows}
        for row in matrix:
            tid = str(row.get("techniqueID") or "")
            tactic = str(row.get("tactic") or "")
            if not tid:
                continue
            id_tactics.setdefault(tid, set()).add(tactic)
            per_tactic[tactic] += 1

    distinct = sorted(id_tactics)
    multi_tactic = {tid: sorted(tacs) for tid, tacs in id_tactics.items() if len(tacs) > 1}
    ai_only = {tac: per_tactic[tac] for tac in _ATLAS_AI_ONLY_TACTICS if tac in per_tactic}
    top_by_freq = sorted(distinct, key=lambda i: freq.get(i, 0), reverse=True)[:10]
    # WS-G G4: enrich with technique names when the offline ATLAS resolver is
    # onboarded (graceful: ID-only when absent). Resolver supplies metadata only.
    _names = _atlas_technique_names(top_by_freq)
    limitation = (
        "Top techniques include resolved AML names from the vendored ATLAS YAML; "
        "Navigator raw layers remain ID+tactics+scores for full-matrix views."
        if _names
        else limitation_ids_only
    )

    return {
        "schema_role": "atlas_coverage_gap_v1",
        "atlas_source_status": atlas_source_status,
        "normalization_provenance": normalization_provenance,
        "mitre_metadata_role": MITRE_METADATA_ROLE,
        # Enterprise ATT&CK and ATLAS share no IDs, so our SOC catalogue covers none
        # of the AML taxonomy today — this is the AI/LLM/MCP-threat gap, stated plainly.
        "technique_count": len(distinct),
        "covered_count": 0,
        "gap_count": len(distinct),
        "tactics": dict(sorted(per_tactic.items())),
        "ai_only_tactics": ai_only,
        "multi_tactic_technique_count": len(multi_tactic),
        "top_techniques_by_case_study_frequency": [
            {
                "technique_id": tid,
                "name": _names.get(tid, ""),
                "score": freq.get(tid, 0),
                "tactics": sorted(id_tactics[tid]),
            }
            for tid in top_by_freq
        ],
        "technique_names_resolved": bool(_names),
        "limitation": limitation,
    }

_SKILL_COVERAGE_PATH = "docs/evals/skill_coverage_matrix.json"
_SOC_CAPABILITY_CROSSWALK_PATH = "docs/evals/soc_capability_crosswalk.json"
_GITHUB_INTAKE_PATH = "docs/skills/github_skill_intake_register.json"
_DISCOVERY_INDEX_PATH = "docs/skills/github_skill_discovery_index.json"
_TRIAGE_SCORES_PATH = "docs/skills/github_skill_triage_scores.json"
_PROPOSED_USE_CASES_PATH = "docs/skills/proposed_use_cases_from_github.json"
_ENRICHMENT_STATUS_JSON = "docs/skills/skill_enrichment_status_matrix.json"
_PENDING_BACKLOG_JSON = "docs/skills/pending_skill_enrichment_backlog.json"
_ENRICHMENT_STATUS_MD = "docs/skills/skill_enrichment_status_matrix.md"
_REJECTED_SKILLS_MD = "docs/skills/rejected_github_skills.md"
_PENDING_BACKLOG_MD = "docs/skills/pending_skill_enrichment_backlog.md"
_CATALOG_PATH = "backend/app/use_cases/catalog.json"

GITHUB_ACCEPTANCE_NOTE = (
    "GitHub decision=accept means accepted_for_enrichment only — not runtime_active "
    "and not a live execution skill."
)


def repo_root() -> Path:
    for base in _REPO_ROOT_CANDIDATES:
        if (base / _SKILL_COVERAGE_PATH).is_file():
            return base
    return _REPO_ROOT_CANDIDATES[0]


def load_skill_coverage_matrix_rows() -> list[dict[str, Any]]:
    path = repo_root() / _SKILL_COVERAGE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def build_skill_coverage_export_payload() -> dict[str, Any]:
    rows = load_skill_coverage_matrix_rows()
    return {
        "artifact": "skill_coverage_matrix",
        "source_file": _SKILL_COVERAGE_PATH,
        "mitre_metadata_role": MITRE_METADATA_ROLE,
        "row_count": len(rows),
        "rows": rows,
    }


def load_soc_capability_crosswalk() -> dict[str, Any]:
    path = repo_root() / _SOC_CAPABILITY_CROSSWALK_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_mapping_summary() -> dict[str, Any]:
    """Compact read-only snapshot for the Knowledge page mapping spine panel."""
    crosswalk = load_soc_capability_crosswalk()
    coverage = load_skill_coverage_matrix_rows()
    row_counts = crosswalk.get("row_counts") if isinstance(crosswalk.get("row_counts"), dict) else {}

    skill_dist = Counter(row.get("live_execution_skill") for row in coverage)
    mapping_dist = Counter(row.get("mapping_status") for row in coverage)
    runtime_status = Counter(
        row.get("runtime_support_status")
        for row in (crosswalk.get("question_rows") or [])
        if isinstance(row, dict)
    )

    return {
        "generated_at": crosswalk.get("generated_at"),
        "schema_version": crosswalk.get("schema_version"),
        "mitre_metadata_role": crosswalk.get("mitre_metadata_role", MITRE_METADATA_ROLE),
        "live_route_skills": list(SKILL_ENUM),
        "allowed_live_execution_skills": crosswalk.get("allowed_live_execution_skills") or [],
        "row_counts": row_counts,
        "question_skill_distribution": {str(k): v for k, v in sorted(skill_dist.items())},
        "question_mapping_status": {str(k): v for k, v in sorted(mapping_dist.items())},
        "question_runtime_support_status": {str(k): v for k, v in sorted(runtime_status.items())},
        "questions_with_use_case_id": sum(1 for row in coverage if row.get("use_case_id")),
        "recommended_export": "soc_capability_crosswalk",
        "sources": {
            "runtime_map": "backend/app/coverage/question_runtime_map_v1.json",
            "coverage_matrix": _SKILL_COVERAGE_PATH,
            "crosswalk": _SOC_CAPABILITY_CROSSWALK_PATH,
            "catalog": _CATALOG_PATH,
        },
    }


def build_soc_capability_crosswalk_export_payload() -> dict[str, Any]:
    crosswalk = load_soc_capability_crosswalk()
    row_counts = crosswalk.get("row_counts") if isinstance(crosswalk.get("row_counts"), dict) else {}
    return {
        "artifact": "soc_capability_crosswalk",
        "source_file": _SOC_CAPABILITY_CROSSWALK_PATH,
        "schema_version": crosswalk.get("schema_version"),
        "generated_at": crosswalk.get("generated_at"),
        "mitre_metadata_role": crosswalk.get("mitre_metadata_role", MITRE_METADATA_ROLE),
        "allowed_live_execution_skills": crosswalk.get("allowed_live_execution_skills") or [],
        "row_counts": row_counts,
        "factory_visibility": crosswalk.get("factory_visibility") or {},
        "question_rows": crosswalk.get("question_rows") or [],
        "use_case_rows": crosswalk.get("use_case_rows") or [],
        "github_skill_rows": crosswalk.get("github_skill_rows") or [],
        "proposed_use_case_rows": crosswalk.get("proposed_use_case_rows") or [],
        "warnings": crosswalk.get("warnings") or [],
    }


def soc_capability_crosswalk_csv_rows() -> list[dict[str, Any]]:
    crosswalk = load_soc_capability_crosswalk()
    rows: list[dict[str, Any]] = []
    for kind, items in (
        ("question", crosswalk.get("question_rows") or []),
        ("use_case", crosswalk.get("use_case_rows") or []),
        ("github_skill", crosswalk.get("github_skill_rows") or []),
    ):
        for item in items:
            if isinstance(item, dict):
                rows.append({"row_kind": kind, **_soc_capability_crosswalk_csv_row(item)})
    return rows


def _soc_capability_crosswalk_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": row.get("question_id"),
        "question": row.get("question"),
        "question_match_status": row.get("question_match_status"),
        "use_case_id": row.get("use_case_id"),
        "catalog_present": row.get("catalog_present"),
        "enrichment_present": row.get("enrichment_present"),
        "mapping_status": row.get("mapping_status"),
        "mapping_confidence": row.get("mapping_confidence"),
        "live_execution_skill": row.get("live_execution_skill"),
        "planning_or_analytic_skill": row.get("planning_or_analytic_skill"),
        "github_reference_skills": _join(row.get("github_reference_skills")),
        "github_reuse_type": _join(row.get("github_reuse_type")),
        "spl_template_id": row.get("spl_template_id"),
        "spl_template_status": row.get("spl_template_status"),
        "mitre_metadata_role": row.get("mitre_metadata_role") or MITRE_METADATA_ROLE,
        "mitre_candidates": _join(row.get("mitre_candidates")),
        "mitre_blocked": _join(row.get("mitre_blocked")),
        "evidence_requirements": _json_cell(row.get("evidence_requirements")),
        "investigation_workflow_status": row.get("investigation_workflow_status"),
        "answer_rules_status": row.get("answer_rules_status"),
        "rag_status": row.get("rag_status"),
        "runtime_support_status": row.get("runtime_support_status"),
        "validation_status": row.get("validation_status"),
        "tests_added": row.get("tests_added"),
        "github_skill_id": row.get("github_skill_id"),
        "decision": row.get("decision"),
        "mapping_state": row.get("mapping_state"),
        "runtime_skill": row.get("runtime_skill"),
    }


def skill_coverage_csv_rows() -> list[dict[str, Any]]:
    return [_skill_coverage_export_row(row) for row in load_skill_coverage_matrix_rows()]


def _skill_coverage_export_row(row: dict[str, Any]) -> dict[str, Any]:
    github_refs = row.get("github_reference_skills") or row.get("github_reference_skill")
    intake = row.get("github_intake_decision")
    evidence = row.get("evidence_requirements") or row.get("enrichment_evidence_requirements")
    return {
        "question_id": row.get("question_id"),
        "query": row.get("query"),
        "live_execution_skill": row.get("live_execution_skill"),
        "planning_or_analytic_skill": row.get("planning_or_analytic_skill"),
        "use_case_id": row.get("use_case_id"),
        "mapping_status": row.get("mapping_status"),
        "mapping_confidence": row.get("mapping_confidence"),
        "spl_template_status": row.get("spl_template_status"),
        "github_reference_skills": _join(github_refs),
        "github_intake_decision": _join(intake),
        "enrichment_status": row.get("enrichment_status"),
        "evidence_requirements": _join(evidence),
        "implementation_status": row.get("implementation_status"),
        "test_status": row.get("test_status"),
        "mitre_permitted": _join(row.get("mitre_permitted")),
        "mitre_metadata_role": MITRE_METADATA_ROLE,
    }


def load_github_intake_register() -> dict[str, Any]:
    path = repo_root() / _GITHUB_INTAKE_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"records": []}


def _load_json_artifact(path_suffix: str) -> dict[str, Any]:
    path = repo_root() / path_suffix
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_github_skill_discovery_index() -> dict[str, Any]:
    return _load_json_artifact(_DISCOVERY_INDEX_PATH)


def build_github_skill_discovery_export_payload() -> dict[str, Any]:
    payload = load_github_skill_discovery_index()
    row_counts = payload.get("row_counts") if isinstance(payload.get("row_counts"), dict) else {}
    return {
        "artifact": "github_skill_discovery_index",
        "source_file": _DISCOVERY_INDEX_PATH,
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "clone_root_used": payload.get("clone_root_used"),
        "source_repo_name": payload.get("source_repo_name"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": row_counts,
        "skills": payload.get("skills") or [],
        "warnings": payload.get("warnings") or [],
    }


def github_skill_discovery_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for skill in load_github_skill_discovery_index().get("skills") or []:
        if not isinstance(skill, dict):
            continue
        rows.append(
            {
                "github_skill_id": skill.get("github_skill_id"),
                "path": skill.get("path"),
                "title": skill.get("title"),
                "domain": skill.get("domain"),
                "subdomain": skill.get("subdomain"),
                "tags": _join(skill.get("tags")),
                "mitre_attack": _join(skill.get("mitre_attack")),
                "likely_soc_relevance": skill.get("likely_soc_relevance"),
                "likely_internal_domain": skill.get("likely_internal_domain"),
                "review_status": skill.get("review_status"),
                "decision": skill.get("decision"),
                "priority": skill.get("priority"),
                "duplicate_of_existing": skill.get("duplicate_of_existing"),
            }
        )
    return rows


def load_github_skill_triage_scores() -> dict[str, Any]:
    return _load_json_artifact(_TRIAGE_SCORES_PATH)


def build_github_skill_triage_export_payload() -> dict[str, Any]:
    payload = load_github_skill_triage_scores()
    return {
        "artifact": "github_skill_triage_scores",
        "source_file": _TRIAGE_SCORES_PATH,
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "scoring_model_version": payload.get("scoring_model_version"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": payload.get("row_counts") or {},
        "scores": payload.get("scores") or [],
        "warnings": payload.get("warnings") or [],
    }


def github_skill_triage_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for score in load_github_skill_triage_scores().get("scores") or []:
        if not isinstance(score, dict):
            continue
        rows.append(
            {
                "github_skill_id": score.get("github_skill_id"),
                "path": score.get("path"),
                "soc_relevance": score.get("soc_relevance"),
                "defensive_usefulness": score.get("defensive_usefulness"),
                "mapped_mitre_value": score.get("mapped_mitre_value"),
                "splunk_log_detection_relevance": score.get("splunk_log_detection_relevance"),
                "enterprise_demo_value": score.get("enterprise_demo_value"),
                "evidence_model_availability": score.get("evidence_model_availability"),
                "safety_risk": score.get("safety_risk"),
                "overlap_with_existing_skill": score.get("overlap_with_existing_skill"),
                "implementation_complexity": score.get("implementation_complexity"),
                "data_source_availability": score.get("data_source_availability"),
                "recommended_decision": score.get("recommended_decision"),
                "priority": score.get("priority"),
                "reason": score.get("reason"),
            }
        )
    return rows


def load_proposed_use_cases_from_github() -> dict[str, Any]:
    return _load_json_artifact(_PROPOSED_USE_CASES_PATH)


def build_proposed_use_cases_export_payload() -> dict[str, Any]:
    payload = load_proposed_use_cases_from_github()
    return {
        "artifact": "proposed_use_cases_from_github",
        "source_file": _PROPOSED_USE_CASES_PATH,
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": payload.get("row_counts") or {},
        "proposed_use_cases": payload.get("proposed_use_cases") or [],
        "warnings": payload.get("warnings") or [],
    }


def proposed_use_cases_csv_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in load_proposed_use_cases_from_github().get("proposed_use_cases") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "proposed_use_case_id": item.get("proposed_use_case_id"),
                "source_github_skill_id": item.get("source_github_skill_id"),
                "proposed_display_name": item.get("proposed_display_name"),
                "proposed_domain": item.get("proposed_domain"),
                "proposed_subdomain": item.get("proposed_subdomain"),
                "proposed_live_execution_skill": item.get("proposed_live_execution_skill"),
                "proposed_planning_skill": item.get("proposed_planning_skill"),
                "spl_template_need": item.get("spl_template_need"),
                "soc_approval_status": item.get("soc_approval_status"),
                "implementation_status": item.get("implementation_status"),
                "runtime_support_status": item.get("runtime_support_status"),
            }
        )
    return rows


def load_skill_enrichment_status_matrix() -> dict[str, Any]:
    json_path = repo_root() / _ENRICHMENT_STATUS_JSON
    if json_path.is_file():
        return _load_json_artifact(_ENRICHMENT_STATUS_JSON)
    return load_markdown_export(_ENRICHMENT_STATUS_MD)


def build_skill_enrichment_status_export_payload() -> dict[str, Any]:
    payload = load_skill_enrichment_status_matrix()
    if payload.get("format") == "markdown":
        return {
            **payload,
            "export_kind": "markdown_backed",
            "usage_note": "Markdown-backed export; regenerate skill_enrichment_status_matrix.json for JSON-backed view.",
        }
    return {
        "artifact": "skill_enrichment_status_matrix",
        "source_file": _ENRICHMENT_STATUS_JSON,
        "export_kind": "json_backed",
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "usage_note": payload.get("usage_note") or GITHUB_ACCEPTANCE_NOTE,
        "row_counts": payload.get("row_counts") or {},
        "rows": payload.get("rows") or [],
        "warnings": payload.get("warnings") or [],
    }


def skill_enrichment_status_csv_rows() -> list[dict[str, Any]]:
    payload = load_skill_enrichment_status_matrix()
    if payload.get("format") == "markdown":
        return []
    rows: list[dict[str, Any]] = []
    for item in payload.get("rows") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "internal_use_case": item.get("internal_use_case"),
                "github_reference_skills": _join(item.get("github_reference_skills")),
                "live_skill": item.get("live_skill"),
                "planning_skill": item.get("planning_skill"),
                "spl_template": item.get("spl_template"),
                "tests_added": item.get("tests_added"),
                "status": item.get("status"),
                "runtime_support_status": item.get("runtime_support_status"),
            }
        )
    return rows


def load_pending_skill_enrichment_backlog() -> dict[str, Any]:
    json_path = repo_root() / _PENDING_BACKLOG_JSON
    if json_path.is_file():
        return _load_json_artifact(_PENDING_BACKLOG_JSON)
    return load_markdown_export(_PENDING_BACKLOG_MD)


def build_pending_backlog_export_payload() -> dict[str, Any]:
    payload = load_pending_skill_enrichment_backlog()
    if payload.get("format") == "markdown":
        return {
            **payload,
            "export_kind": "markdown_backed",
            "usage_note": "Markdown-backed export; regenerate pending_skill_enrichment_backlog.json for JSON-backed view.",
        }
    return {
        "artifact": "pending_skill_enrichment_backlog",
        "source_file": _PENDING_BACKLOG_JSON,
        "export_kind": "json_backed",
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "usage_note": payload.get("usage_note") or "Advisory backlog only; not runtime activation.",
        "row_counts": payload.get("row_counts") or {},
        "backlog": payload.get("backlog") or [],
        "warnings": payload.get("warnings") or [],
    }


def pending_backlog_csv_rows() -> list[dict[str, Any]]:
    payload = load_pending_skill_enrichment_backlog()
    if payload.get("format") == "markdown":
        return []
    rows: list[dict[str, Any]] = []
    for item in payload.get("backlog") or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "backlog_id": item.get("backlog_id"),
                "github_skill_id": item.get("github_skill_id"),
                "title": item.get("title"),
                "soc_domain": item.get("soc_domain"),
                "priority": item.get("priority"),
                "status": item.get("status"),
                "recommended_decision": item.get("recommended_decision"),
                "reason": item.get("reason"),
            }
        )
    return rows


def github_intake_csv_rows() -> list[dict[str, Any]]:
    register = load_github_intake_register()
    rows: list[dict[str, Any]] = []
    for record in register.get("records") or []:
        if not isinstance(record, dict):
            continue
        impl = record.get("implementation_status") if isinstance(record.get("implementation_status"), dict) else {}
        safety = record.get("safety_review") if isinstance(record.get("safety_review"), dict) else {}
        rows.append(
            {
                "github_skill_id": record.get("github_skill_id"),
                "path": record.get("path"),
                "decision": record.get("decision"),
                "review_status": record.get("review_status"),
                "domain": record.get("domain"),
                "subdomain": record.get("subdomain"),
                "internal_use_cases": _join(record.get("internal_use_cases")),
                "mapped_live_execution_skill": record.get("mapped_live_execution_skill"),
                "mapped_planning_or_analytic_skill": record.get("mapped_planning_or_analytic_skill"),
                "reuse_type": record.get("reuse_type"),
                "mitre_from_github": _join(record.get("mitre_from_github")),
                "content_enrichment_added": impl.get("content_enrichment_added"),
                "tests_added": impl.get("tests_added"),
                "defensive_only": safety.get("defensive_only"),
                "no_runtime_markdown_loading": safety.get("no_runtime_markdown_loading"),
                "priority": record.get("priority"),
                "reviewed_date": record.get("reviewed_date"),
            }
        )
    return rows


def load_markdown_export(path_suffix: str) -> dict[str, Any]:
    path = repo_root() / path_suffix
    content = path.read_text(encoding="utf-8")
    artifact = Path(path_suffix).stem
    return {
        "artifact": artifact,
        "source_file": path_suffix,
        "format": "markdown",
        "content": content,
    }


def load_use_case_catalog_export_rows() -> list[dict[str, Any]]:
    catalog_path = repo_root() / _CATALOG_PATH
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_by_id: dict[str, dict[str, Any]] = {}
    for item in payload.get("use_cases") or []:
        if isinstance(item, dict) and item.get("use_case_id"):
            catalog_by_id[str(item["use_case_id"])] = dict(item)

    enrichment = content_enrichment_records()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for use_case_id, catalog_row in sorted(catalog_by_id.items()):
        row = dict(catalog_row)
        _merge_enrichment_export_fields(row, enrichment.get(use_case_id))
        row["catalog_present"] = True
        rows.append(row)
        seen.add(use_case_id)

    for use_case_id, enrich in sorted(enrichment.items()):
        if use_case_id in seen:
            continue
        row: dict[str, Any] = {
            "use_case_id": use_case_id,
            "display_name": enrich.get("use_case_id"),
            "category": enrich.get("domain"),
            "primary_skill": enrich.get("live_execution_skill"),
            "catalog_present": False,
        }
        _merge_enrichment_export_fields(row, enrich)
        rows.append(row)

    return rows


def _merge_enrichment_export_fields(row: dict[str, Any], enrich: dict[str, Any] | None) -> None:
    if enrich is None:
        row.setdefault("enrichment_present", False)
        return
    row["enrichment_present"] = True
    row["domain"] = enrich.get("domain")
    row["subdomain"] = enrich.get("subdomain")
    row["use_case_status"] = enrich.get("use_case_status")
    row["github_reference_skills"] = enrich.get("github_reference_skills") or []
    row["evidence_requirements"] = enrich.get("evidence_requirements") or []
    row["investigation_workflow"] = enrich.get("investigation_workflow") or []
    row["analyst_checklist"] = enrich.get("analyst_checklist") or []
    row["answer_rules"] = enrich.get("answer_rules") or []
    row["limitations"] = enrich.get("limitations") or []
    row["allowed_spl_templates"] = enrich.get("allowed_spl_templates") or []
    row["spl_template_status"] = enrich.get("spl_template_status")
    row["enrichment_status"] = enrich.get("enrichment_status")
    row["enrichment_implementation_status"] = _enrichment_implementation_status(enrich)


def _enrichment_implementation_status(enrich: dict[str, Any]) -> str:
    github_refs = enrich.get("github_reference_skills") or []
    if not github_refs:
        return "not_started"
    first = github_refs[0] if isinstance(github_refs[0], dict) else {}
    return str(first.get("implementation_status") or enrich.get("enrichment_status") or "content_added")


def use_case_catalog_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    registry = row.get("mitre_registry") if isinstance(row.get("mitre_registry"), dict) else {}
    github_refs = row.get("github_reference_skills") or []
    github_paths = [
        ref.get("path") if isinstance(ref, dict) else str(ref)
        for ref in github_refs
    ]
    return {
        "use_case_id": row.get("use_case_id"),
        "display_name": row.get("display_name"),
        "category": row.get("category"),
        "catalog_present": row.get("catalog_present"),
        "primary_skill": row.get("primary_skill"),
        "secondary_skills": _join(row.get("secondary_skills")),
        "default_spl_template": row.get("default_spl_template"),
        "domain": row.get("domain"),
        "subdomain": row.get("subdomain"),
        "use_case_status": row.get("use_case_status"),
        "github_reference_skills": _join(github_paths),
        "evidence_requirements": _join(row.get("evidence_requirements")),
        "investigation_workflow": _join(row.get("investigation_workflow")),
        "analyst_checklist": _join(row.get("analyst_checklist")),
        "answer_rules": _join(row.get("answer_rules")),
        "limitations": _join(row.get("limitations")),
        "allowed_spl_templates": _join(row.get("allowed_spl_templates")),
        "spl_template_status": row.get("spl_template_status"),
        "enrichment_status": row.get("enrichment_status"),
        "enrichment_implementation_status": row.get("enrichment_implementation_status"),
        "enrichment_present": row.get("enrichment_present"),
        "mitre_candidates": _join(row.get("mitre_candidates")),
        "mitre_registry_permitted": _join(registry.get("permitted")),
        "mitre_registry_candidate": _join(registry.get("candidate")),
        "mitre_registry_blocked": _join(registry.get("blocked")),
        "mitre_requires_evidence": row.get("mitre_requires_evidence"),
        "mitre_requires_alert_context": row.get("mitre_requires_alert_context"),
        "mitre_visibility_policy": row.get("mitre_visibility_policy"),
        "mitre_metadata_role": MITRE_METADATA_ROLE,
        "mitre_blocked_rationale": _json_cell(registry.get("blocked_rationale")),
        "severity_policy": _json_cell(row.get("severity_policy")),
        "action_capability_tier": row.get("action_capability_tier"),
        "output_template": row.get("output_template"),
    }


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return "" if value is None else str(value)


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True)


# --------------------------------------------------------------------------- #
# SOC validation package (Phase 10) — read-only, artifact-backed exports.
# Source artifacts are generated offline by
# ``scripts/build_soc_validation_sheets.py`` from the governed crosswalk.
# --------------------------------------------------------------------------- #
_VALIDATION_DIR = "docs/validation"

# Knowledge export key -> generated artifact filename. CSV is offered only for
# the flat row sheets; nested sheets stay JSON-only.
SOC_VALIDATION_ARTIFACTS: dict[str, dict[str, Any]] = {
    "soc_validation_use_cases": {"file": "use_case_validation_sheet.json", "csv": True},
    "soc_validation_spl_templates": {"file": "spl_template_review_sheet.json", "csv": True},
    "soc_validation_mitre": {"file": "mitre_validation_sheet.json", "csv": True},
    "soc_validation_questions": {"file": "question_validation_sheet.json", "csv": True},
    "soc_validation_github_enrichment": {"file": "github_enrichment_review_sheet.json", "csv": True},
    "soc_validation_github_batch_intake": {"file": "github_batch_intake_sheet.json", "csv": False},
    "soc_validation_rag_sop": {"file": "rag_sop_validation_sheet.json", "csv": True},
    "soc_validation_pending_backlog": {"file": "pending_skill_enrichment_backlog_sheet.json", "csv": False},
    "soc_validation_combination_matrix": {"file": "combination_matrix_sheet.json", "csv": False},
    "soc_validation_demo_scenarios": {"file": "demo_scenario_sheet.json", "csv": False},
}


def load_soc_validation_sheet(artifact: str) -> dict[str, Any]:
    spec = SOC_VALIDATION_ARTIFACTS.get(artifact)
    if spec is None:
        return {}
    path = repo_root() / _VALIDATION_DIR / spec["file"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def build_soc_validation_export_payload(artifact: str) -> dict[str, Any]:
    sheet = load_soc_validation_sheet(artifact)
    rows = sheet.get("rows") if isinstance(sheet.get("rows"), list) else []
    return {
        "artifact": artifact,
        "export_kind": "json_backed",
        "source_file": f"{_VALIDATION_DIR}/{SOC_VALIDATION_ARTIFACTS[artifact]['file']}",
        "schema_version": sheet.get("schema_version"),
        "generated_at": sheet.get("generated_at"),
        "usage_note": sheet.get("usage_note"),
        "mitre_metadata_role": sheet.get("mitre_metadata_role", MITRE_METADATA_ROLE),
        "row_counts": sheet.get("row_counts") or {"rows": len(rows)},
        "rows": rows,
        "warnings": sheet.get("warnings") or [],
    }


def _flatten_validation_cell(value: Any) -> Any:
    if isinstance(value, list):
        return _json_cell(value) if value and isinstance(value[0], (dict, list)) else _join(value)
    if isinstance(value, dict):
        return _json_cell(value)
    return value


def soc_validation_csv_rows(artifact: str) -> list[dict[str, Any]] | None:
    spec = SOC_VALIDATION_ARTIFACTS.get(artifact)
    if spec is None or not spec.get("csv"):
        return None
    sheet = load_soc_validation_sheet(artifact)
    rows = sheet.get("rows") if isinstance(sheet.get("rows"), list) else []
    flattened: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            flattened.append({k: _flatten_validation_cell(v) for k, v in row.items()})
    return flattened


def build_catalogue_question_index() -> dict[str, Any]:
    """Linked catalogue/question index for analyst reference and the /knowledge page.

    Same shape as scripts/build_catalogue_question_index.py writes to
    docs/evals/catalogue_question_index.json — one builder, so the committed
    reference doc and the live page cannot drift apart.

    The per-entry flags exist because two defects came from exactly these gaps:
    an unbindable entry looks like dead weight but is a template-registry
    binding, and a bindable entry with no SPL template can win a bind and leave
    the answer without a governed query.
    """
    from app.coverage.question_runtime_map import list_question_runtime_entries
    from app.use_cases.registry import load_use_case_catalog, match_use_cases

    catalogue = load_use_case_catalog()
    questions: list[dict[str, Any]] = []
    for entry in list_question_runtime_entries():
        text = entry.get("question") or entry.get("query")
        if not text:
            continue
        matches = match_use_cases(text)
        top = matches[0] if matches else None
        questions.append(
            {
                "question_ref": entry.get("question_ref"),
                "question": text,
                "proposed_primary_skill": entry.get("proposed_primary_skill"),
                "binds_use_case_id": top.use_case_id if top else None,
                "bind_matched_patterns": list(top.matched_patterns) if top else [],
                "bind_coverage_score": top.coverage_score if top else None,
            }
        )

    bound = {q["binds_use_case_id"] for q in questions if q["binds_use_case_id"]}
    use_cases = [
        {
            "use_case_id": uc.use_case_id,
            "display_name": uc.display_name,
            "category": uc.category,
            "primary_skill": uc.primary_skill,
            "default_spl_template": uc.default_spl_template,
            "intent_patterns": list(uc.intent_patterns or []),
            "example_queries": list(uc.example_queries or []),
            "bindable": bool(uc.intent_patterns),
            "has_spl_template": bool(uc.default_spl_template),
            "binds_a_105_question": uc.use_case_id in bound,
        }
        for uc in catalogue
    ]

    return {
        "artifact": "catalogue_question_index",
        "schema_version": "catalogue_question_index_v1",
        "counts": {
            "use_cases": len(use_cases),
            "questions": len(questions),
            "use_cases_bindable": sum(1 for u in use_cases if u["bindable"]),
            "use_cases_with_template": sum(1 for u in use_cases if u["has_spl_template"]),
            "questions_binding_a_use_case": sum(1 for q in questions if q["binds_use_case_id"]),
        },
        "use_cases": use_cases,
        "questions": questions,
    }


def catalogue_question_index_csv_rows(payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = payload or build_catalogue_question_index()
    rows: list[dict[str, Any]] = []
    for u in data["use_cases"]:
        rows.append(
            {
                "row_kind": "use_case",
                "id": u["use_case_id"],
                "text": u["display_name"],
                "skill": u["primary_skill"],
                "spl_template": u["default_spl_template"] or "",
                "bindable": u["bindable"],
                "has_spl_template": u["has_spl_template"],
                "serves_105_question": u["binds_a_105_question"],
                "patterns": "; ".join(u["intent_patterns"]),
            }
        )
    for q in data["questions"]:
        rows.append(
            {
                "row_kind": "question",
                "id": q["question_ref"] or "",
                "text": q["question"],
                "skill": q["proposed_primary_skill"] or "",
                "spl_template": "",
                "bindable": "",
                "has_spl_template": "",
                "serves_105_question": "",
                "patterns": q["binds_use_case_id"] or "",
            }
        )
    return rows
