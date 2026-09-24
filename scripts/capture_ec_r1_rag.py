#!/usr/bin/env python3
"""Capture the governed SOC-KB retrieval that the Experience Center R1 question replays.

The Experience Center never calls retrieval live. This script runs the real governed retriever
(`retrieve_soc_kb`) once, outside EC, and writes a trimmed capture that the R1 pack replays, so
every sentence R1 shows is traceable to a published, approved KB passage.

Run from the repo root (or inside the backend container with the repo mounted at /workspace):

    PYTHONPATH=backend:. python3 scripts/capture_ec_r1_rag.py [--out PATH]

In the compose backend container the repo mount is read-only; pass
``--out /app/app/demo/captures/r1_privileged_success_after_failure_rag.json``.

Re-run whenever the auth SOP or escalation matrix in the SOC-KB changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from app.knowledge.soc_kb_retriever import retrieve_soc_kb

R1_QUERY = (
    "A privileged account logged in successfully after repeated failed logins. "
    "What does our SOP require, and what does our escalation matrix say?"
)
R1_SELECTED_SKILL = "alert_summary"
R1_COLLECTIONS = ["soc_sop", "escalation_matrix"]
R1_MAX_RESULTS = 8

_KEPT_ENTRY_FIELDS = (
    "entry_id",
    "doc_id",
    "doc_title",
    "doc_version",
    "collection_id",
    "approval_status",
    "status",
    "entry_title",
    "source_excerpt",
    "citation",
    "confidence",
    "recommended_actions",
    "prohibited_conclusions",
    "answer_constraints",
)

CAPTURE_PATH = Path(__file__).resolve().parents[1] / "backend" / "app" / "demo" / "captures" / "r1_privileged_success_after_failure_rag.json"


def build_capture() -> dict[str, Any]:
    """Run the governed retriever and keep only what the EC trace panel shows."""
    result = retrieve_soc_kb(
        query=R1_QUERY,
        selected_skill=R1_SELECTED_SKILL,
        collection_ids=R1_COLLECTIONS,
        max_results=R1_MAX_RESULTS,
    )
    if result.get("retrieval_status") != "retrieved":
        raise RuntimeError(f"R1 retrieval did not succeed: {result.get('retrieval_status')} {result.get('reasons')}")
    return {
        "query": R1_QUERY,
        "selected_skill": R1_SELECTED_SKILL,
        "collection_ids": R1_COLLECTIONS,
        "retrieval_status": result["retrieval_status"],
        "confidence": result["confidence"],
        "retrieval_mode": result["retrieval_mode"],
        "direct_to_llm": result["direct_to_llm"],
        "excluded_counts": result["excluded_counts"],
        "retrieval_stages": (result.get("retrieval_stage_metadata") or {}).get("retrieval_stages") or [],
        "retrieved_entries": [
            {key: entry.get(key) for key in _KEPT_ENTRY_FIELDS} for entry in result["retrieved_entries"]
        ],
    }


def main(argv: list[str]) -> int:
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else CAPTURE_PATH
    capture = build_capture()
    out.write_text(json.dumps(capture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(capture['retrieved_entries'])} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
