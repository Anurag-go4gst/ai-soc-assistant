"""T2.2 — skill-enrichment knowledge in the governed SOC-KB."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.evals.sentinel_eval import sentinel_runtime
from app.knowledge.soc_kb_retriever import retrieve_soc_kb

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS = json.loads((REPO_ROOT / "backend/app/knowledge/fixtures/soc_kb_documents.json").read_text())
ENTRIES = json.loads((REPO_ROOT / "backend/app/knowledge/fixtures/soc_kb_entries.json").read_text())
FORBIDDEN = ("skill.md", "github.com", "/skills/", "github_ref:")


def test_import_is_idempotent_check_passes() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/import_skill_knowledge_to_kb.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={"PYTHONPATH": f"{REPO_ROOT}/backend:{REPO_ROOT}", "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_every_checklist_enrichment_record_has_kb_doc_and_entries() -> None:
    enrichment = json.loads(
        (REPO_ROOT / "backend/app/use_cases/content_enrichment.json").read_text()
    )["records"]
    doc_ids = {doc["doc_id"] for doc in DOCS}
    for use_case, record in enrichment.items():
        if record.get("analyst_checklist") or record.get("investigation_workflow"):
            assert f"skill-enrich-{use_case}-v1" in doc_ids, use_case
    skill_entries = [e for e in ENTRIES if e["entry_id"].startswith("skill-enrich-")]
    assert len(skill_entries) >= 24
    for entry in skill_entries:
        assert entry["approval_status"] == "coe_reviewed"
        assert entry["allowed_use"] == ["hil_guidance", "synthesis_context"]


def test_no_provenance_markers_in_generated_kb() -> None:
    blob = json.dumps([d for d in DOCS if d["doc_id"].startswith("skill-enrich-")]).lower()
    blob += json.dumps([e for e in ENTRIES if e["entry_id"].startswith("skill-enrich-")]).lower()
    for marker in FORBIDDEN:
        assert marker not in blob, marker


def test_existing_coe_docs_untouched() -> None:
    assert any(doc["doc_id"] == "coe-auth-sop-v1" for doc in DOCS)


def test_curated_privileged_checklist_is_retrievable() -> None:
    with sentinel_runtime():
        result = retrieve_soc_kb(
            query="checklist for validating suspicious privileged admin login activity",
            selected_skill="knowledge_recall",
            workflow_stage="context",
            workflow_plan={"required_sources": []},
            required_sources=[],
            execution_block_reason=None,
        )
    assert result.get("retrieval_status") == "retrieved"
    citations = [row.get("citation") for row in result.get("retrieved_entries") or []]
    assert any("auth_privileged_login_anomaly" in str(c) for c in citations)


def test_github_derived_skill_knowledge_is_retrievable() -> None:
    with sentinel_runtime():
        result = retrieve_soc_kb(
            query="how to investigate dns beaconing candidate",
            selected_skill="knowledge_recall",
            workflow_stage="context",
            workflow_plan={"required_sources": []},
            required_sources=[],
            execution_block_reason=None,
        )
    assert result.get("retrieval_status") == "retrieved"
    citations = [row.get("citation") for row in result.get("retrieved_entries") or []]
    assert any("dns_beaconing_candidate" in str(c) for c in citations)
