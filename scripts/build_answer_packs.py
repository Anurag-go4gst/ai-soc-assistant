#!/usr/bin/env python3
"""Build reviewed answer-pack runtime projections.

This builder is intentionally conservative: it emits reviewed metadata only,
never raw LLM prose, and writes the same read-only projection shape consumed by
``app.use_cases.answer_packs``.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "backend" / "app" / "use_cases" / "answer_packs.json"

PACKS = {
    "q0.q046": {
        "case_id": "q0.q046",
        "use_case_id": "auth_failed_login_spike",
        "review_status": "reviewed",
        "provenance": "coe_reviewed_answer_pack_seed",
        "required_evidence": ["failed_login_count", "user", "time_window"],
        "optional_evidence": ["source_ip", "host"],
        "source_needs": ["authentication_logs"],
        "dependency_gaps": ["coe_enrichment_required"],
        "mitre_candidates": ["T1110"],
        "must_not_claim": [
            "account_compromise_without_successful_login_evidence",
            "confirmed_brute_force_without_threshold_context",
        ],
        "caveats": [
            "Reviewed answer pack enriches EvidencePlan only; it does not authorize live result claims or SPL execution."
        ],
        "spl_family_suggestion": "auth_failed_login_spike",
        "spl_template_id": "auth_failed_login_spike",
    },
    "auth_failed_login_spike": {
        "use_case_id": "auth_failed_login_spike",
        "review_status": "reviewed",
        "provenance": "coe_reviewed_answer_pack_seed",
        "required_evidence": ["failed_login_count", "user", "time_window"],
        "optional_evidence": ["source_ip", "host"],
        "source_needs": ["authentication_logs"],
        "mitre_candidates": ["T1110"],
        "must_not_claim": [
            "account_compromise_without_successful_login_evidence",
            "confirmed_brute_force_without_threshold_context",
        ],
        "caveats": [
            "Reviewed answer pack enriches EvidencePlan only; it does not authorize live result claims or SPL execution."
        ],
        "spl_family_suggestion": "auth_failed_login_spike",
        "spl_template_id": "auth_failed_login_spike",
    },
}


def main() -> int:
    payload = {
        "version": 1,
        "provenance": "reviewed_runtime_projection",
        "packs": PACKS,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(str(OUTPUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
