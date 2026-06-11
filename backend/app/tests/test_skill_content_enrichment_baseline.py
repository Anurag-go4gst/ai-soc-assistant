"""Batch 2 SOC skill content-enrichment baseline validation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.routing.skills import SKILL_ENUM

REPO_ROOT = Path(__file__).resolve().parents[3]
ENRICHMENT_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "content_enrichment.json"
INTAKE_PATH = REPO_ROOT / "docs" / "skills" / "github_skill_intake_register.json"
STATUS_MATRIX_PATH = REPO_ROOT / "docs" / "skills" / "skill_enrichment_status_matrix.md"
COVERAGE_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "skill_coverage_matrix.json"
GENERATOR_PATH = REPO_ROOT / "scripts" / "build_skill_coverage_matrix.py"
REGISTRY_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "registry.py"
CATALOG_PATH = REPO_ROOT / "backend" / "app" / "use_cases" / "catalog.json"
SPL_TEMPLATES_PATH = REPO_ROOT / "backend" / "app" / "spl" / "templates.json"
QUESTION_USE_CASE_MAP_PATH = REPO_ROOT / "docs" / "evals" / "question_use_case_map.json"

REQUIRED_GITHUB_SKILLS = {
    "detecting-rdp-brute-force-attacks",
    "triaging-security-alerts-in-splunk",
    "analyzing-email-headers-for-phishing-investigation",
    "hunting-for-anomalous-powershell-execution",
    "hunting-for-command-and-control-beaconing",
    "triaging-security-incident-with-ir-playbook",
    "analyzing-ransomware-encryption-mechanisms",
}

REQUIRED_RECORD_IDS = {
    "auth_failed_login_spike",
    "auth_success_after_failure",
    "email_phishing_header_review",
    "edr_powershell_suspicious_command",
    "dns_beaconing_candidate",
    "soc_incident_triage",
    "endpoint_ransomware_impact_review",
    # Internally curated (Anurag, 2026-06-11) — checklist content staged for WS2.
    "auth_privileged_login_anomaly",
}

REQUIRED_RECORD_FIELDS = {
    "use_case_status",
    "domain",
    "subdomain",
    "tags",
    "live_execution_skill",
    "planning_or_analytic_skill",
    "github_reference_skills",
    "reuse_types",
    "mitre_candidates",
    "evidence_requirements",
    "investigation_workflow",
    "analyst_checklist",
    "allowed_spl_templates",
    "spl_template_status",
    "answer_rules",
    "limitations",
    "not_claimed_defaults",
    "rag_doc_ids",
    "safety_review",
}

REQUIRED_SAFETY_KEYS = {
    "defensive_only",
    "offensive_steps_removed",
    "no_arbitrary_commands",
    "no_runtime_markdown_loading",
    "no_direct_tool_execution",
    "no_unsupported_mitre_claims",
    "limitations_included",
    "hil_and_validation_preserved",
}

REQUIRED_CURATED_MAPPING_KEYS = {
    "question_id",
    "use_case_id",
    "mapping_status",
    "mapping_source_file",
    "mapping_confidence",
    "evidence_note",
}

LIVE_SKILL_ENUM_BASELINE = {
    "attack_discovery",
    "alert_summary",
    "knowledge_recall",
    "spl_generation",
}


def _load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_enrichment_records() -> dict[str, dict]:
    payload = _load_json(ENRICHMENT_PATH)
    assert isinstance(payload, dict)
    records = payload.get("records")
    assert isinstance(records, dict)
    return records


def test_content_enrichment_exists_and_is_valid_json() -> None:
    payload = _load_json(ENRICHMENT_PATH)

    assert isinstance(payload, dict)
    assert payload["schema_version"] == "2026-06-06-batch2-v1"
    assert set(payload["records"]) == REQUIRED_RECORD_IDS


def test_required_github_reference_skills_are_represented_in_intake_and_status_docs() -> None:
    intake = _load_json(INTAKE_PATH)
    assert isinstance(intake, dict)
    intake_skill_ids = {record["github_skill_id"] for record in intake["records"]}

    status_doc = STATUS_MATRIX_PATH.read_text(encoding="utf-8")

    assert REQUIRED_GITHUB_SKILLS <= intake_skill_ids
    for skill_id in REQUIRED_GITHUB_SKILLS:
        assert skill_id in status_doc


def test_every_enrichment_record_has_required_contract_fields() -> None:
    for record_id, record in _load_enrichment_records().items():
        assert REQUIRED_RECORD_FIELDS <= set(record), record_id
        assert record.get("use_case_id") or record.get("proposed_use_case_id")
        assert record["use_case_status"] in {"active", "planned", "unavailable"}
        assert record["live_execution_skill"]
        assert record["planning_or_analytic_skill"]
        has_github_provenance = bool(record["github_reference_skills"])
        has_internal_provenance = any(
            str(tag).startswith("curated_internal_") for tag in record.get("tags", [])
        )
        assert isinstance(record["github_reference_skills"], list)
        assert has_github_provenance or has_internal_provenance, record_id
        assert isinstance(record["mitre_candidates"], list)
        assert isinstance(record["evidence_requirements"], list) and record["evidence_requirements"]
        assert isinstance(record["answer_rules"], list) and record["answer_rules"]
        assert isinstance(record["limitations"], list) and record["limitations"]

        for reference in record["github_reference_skills"]:
            assert reference["repo"] == "mukul975/Anthropic-Cybersecurity-Skills"
            assert reference["path"].startswith("skills/")
            assert reference["path"].endswith("/SKILL.md")
            assert reference["decision"] in {"accepted", "deferred", "rejected"}
            assert reference["reuse_type"] in {
                "workflow_reference",
                "mitre_reference",
                "evidence_reference",
                "sop_reference",
                "rejected",
            }


def test_safety_review_booleans_are_present_and_true() -> None:
    for record_id, record in _load_enrichment_records().items():
        safety_review = record["safety_review"]
        assert REQUIRED_SAFETY_KEYS <= set(safety_review), record_id
        assert all(safety_review[key] is True for key in REQUIRED_SAFETY_KEYS), record_id


def test_active_records_and_spl_status_match_catalog_and_template_registry() -> None:
    catalog = _load_json(CATALOG_PATH)
    templates = _load_json(SPL_TEMPLATES_PATH)
    assert isinstance(catalog, dict)
    assert isinstance(templates, dict)

    catalog_ids = {record["use_case_id"] for record in catalog["use_cases"]}
    template_status_by_id = {record["template_id"]: record["status"] for record in templates["templates"]}

    for record_id, record in _load_enrichment_records().items():
        if record["use_case_status"] == "active":
            assert record["use_case_id"] in catalog_ids

        if record["spl_template_status"] == "active":
            assert record["allowed_spl_templates"], record_id
            for template_id in record["allowed_spl_templates"]:
                assert template_status_by_id.get(template_id) == "active", record_id


def test_github_markdown_and_intake_docs_are_not_loaded_by_runtime_python() -> None:
    runtime_root = REPO_ROOT / "backend" / "app"
    # Read-only Knowledge export builders may reference governed JSON/Markdown paths
    # for analyst download endpoints; they must not load raw SKILL.md into /chat.
    export_allowlist = {
        runtime_root / "knowledge" / "mapping_exports.py",
        runtime_root / "api" / "routes_knowledge.py",
    }
    forbidden_tokens = (
        "Anthropic-Cybersecurity-Skills",
        "github_skill_intake_register",
        "SKILL.md",
    )

    for path in runtime_root.rglob("*.py"):
        if path.parts[-2] == "tests" or path in export_allowlist:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in text, f"{token!r} unexpectedly referenced in {path}"


def test_coverage_matrix_generator_is_idempotent_with_enrichment_join() -> None:
    spec = importlib.util.spec_from_file_location("build_skill_coverage_matrix", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    warnings: list[str] = []
    rendered = generator._serialize(generator.generate_matrix(warnings))

    assert warnings
    assert COVERAGE_MATRIX_PATH.read_text(encoding="utf-8") == rendered


def test_coverage_matrix_preserves_catalog_evidence_shape_and_adds_enrichment_shape() -> None:
    matrix = _load_json(COVERAGE_MATRIX_PATH)
    assert isinstance(matrix, list)

    mapped_row = next(row for row in matrix if row["use_case_id"] == "auth_failed_login_spike")

    assert isinstance(mapped_row["evidence_requirements"], dict)
    assert {
        "required_entities",
        "optional_entities",
        "required_sources",
        "optional_sources",
    } <= set(mapped_row["evidence_requirements"])
    assert isinstance(mapped_row["enrichment_evidence_requirements"], list)
    assert "fail_count" in mapped_row["enrichment_evidence_requirements"]


def test_curated_question_use_case_mappings_have_required_evidence_fields() -> None:
    payload = _load_json(QUESTION_USE_CASE_MAP_PATH)
    assert isinstance(payload, dict)

    mappings = payload["mappings"]
    assert isinstance(mappings, dict)
    for question_id, mapping in mappings.items():
        assert REQUIRED_CURATED_MAPPING_KEYS <= set(mapping), question_id
        assert mapping["question_id"] == question_id
        assert mapping["mapping_status"] == "curated_manual"
        assert mapping["mapping_confidence"] in {"high", "medium"}
        assert mapping["mapping_source_file"] == "docs/evals/question_use_case_map.json"
        assert "semantic" not in mapping["evidence_note"].lower()
        assert "template_ref=" in mapping["evidence_note"] or "use_case_id=" in mapping["evidence_note"]

    reviewed_unmapped = payload.get("reviewed_unmapped")
    assert isinstance(reviewed_unmapped, list)
    for review in reviewed_unmapped:
        assert review.get("question_id")
        assert review.get("candidate_area")
        reason = review.get("reason", "").lower()
        assert "no " in reason or "not " in reason


def test_runtime_routing_contract_remains_unchanged() -> None:
    registry_source = REGISTRY_PATH.read_text(encoding="utf-8")

    assert set(SKILL_ENUM) == LIVE_SKILL_ENUM_BASELINE
    assert 'with_name("catalog.json")' in registry_source
    assert "content_enrichment" not in registry_source
