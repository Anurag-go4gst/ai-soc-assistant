"""R1 answer content, derived only from the captured governed SOC-KB retrieval.

The capture (``captures/r1_privileged_success_after_failure_rag.json``) is produced by
``scripts/capture_ec_r1_rag.py`` running the real ``retrieve_soc_kb``. Every answer sentence here
names the passage it rests on; ``test_r1_rag_answer.py`` fails if a sentence cites a passage that
is not in the capture. Anything the retrieved passages do not say is listed as a gap instead of
being filled in.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CAPTURE_PATH = Path(__file__).resolve().parents[2] / "captures" / "r1_privileged_success_after_failure_rag.json"

# Short labels the answer uses to cite a passage (entry_id → label shown in the UI).
CITATION_LABELS: dict[str, str] = {
    "coe-auth-success-after-failures": "AUTH-003",
    "coe-auth-bruteforce": "AUTH-001",
    "coe-escalation-hil-auth": "ESC-AUTH-001",
    "skill-enrich-auth_failed_login_spike-rules": "AUTH-GUARD-RULES",
    "skill-enrich-auth_failed_login_spike-limits": "AUTH-GUARD-LIMITS",
}

# Why each passage was used (or kept only as a guardrail) in the answer.
PASSAGE_USE: dict[str, str] = {
    "coe-auth-success-after-failures": "Answer: what to review before escalating",
    "coe-auth-bruteforce": "Answer: privileged accounts must be escalated",
    "coe-escalation-hil-auth": "Answer: who to escalate to",
    "skill-enrich-auth_failed_login_spike-rules": "Guardrail: what the answer must not claim",
    "skill-enrich-auth_failed_login_spike-limits": "Guardrail: limits of failed-login evidence",
}

ANSWER_HEADLINE = (
    "Treat it as an escalation case: review the account, the source and the session, then escalate "
    "to a Tier 2 SOC analyst. Do not call it a compromise yet."
)

ANSWER_SENTENCES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Review how critical the account is, whether the source is new for this user, and what the "
        "session did after the successful login.",
        ("coe-auth-success-after-failures",),
    ),
    (
        "Correlate the failed attempts and the success for the same user and source.",
        ("coe-auth-success-after-failures",),
    ),
    (
        "Because the account is privileged, the SOP requires escalation.",
        ("coe-auth-bruteforce",),
    ),
    (
        "Escalate to a Tier 2 SOC analyst — a privileged account and a success after failures are both "
        "escalation triggers in our matrix.",
        ("coe-escalation-hil-auth",),
    ),
    (
        "Report it as 'successful login after failures observed'; do not state 'compromised account' or "
        "'confirmed brute force' without further evidence.",
        ("coe-auth-bruteforce", "skill-enrich-auth_failed_login_spike-rules"),
    ),
    (
        "Failed-login telemetry alone does not prove the credential was valid for an attacker — shared "
        "or NAT'd sources can look the same.",
        ("skill-enrich-auth_failed_login_spike-limits",),
    ),
)

KNOWLEDGE_GAPS: tuple[str, ...] = (
    "A deadline for escalation — the retrieved SOP and matrix do not set one.",
    "Whether to disable the account — the retrieved passages do not authorize account actions; that stays a human decision.",
)


@lru_cache(maxsize=1)
def load_capture() -> dict[str, Any]:
    return json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))


def captured_entry_ids() -> set[str]:
    return {str(entry["entry_id"]) for entry in load_capture()["retrieved_entries"]}


def build_rag_trace() -> dict[str, Any]:
    """The "How RAG answered this" payload: query, governance filters, passages, citations, gaps."""
    capture = load_capture()
    used_ids = {entry_id for _, cites in ANSWER_SENTENCES for entry_id in cites}
    excluded = [
        {"reason": reason, "count": count}
        for reason, count in capture["excluded_counts"].items()
        if count
    ]
    passages = [
        {
            "entry_id": entry["entry_id"],
            "label": CITATION_LABELS.get(entry["entry_id"], entry["entry_id"]),
            "citation": entry["citation"],
            "doc_title": entry["doc_title"],
            "doc_version": entry["doc_version"],
            "approval_status": entry["approval_status"],
            "confidence": entry["confidence"],
            "excerpt": entry["source_excerpt"],
            "used": entry["entry_id"] in used_ids,
            "used_for": PASSAGE_USE.get(entry["entry_id"], ""),
        }
        for entry in capture["retrieved_entries"]
    ]
    return {
        "question": capture["query"],
        "collections": ["SOC SOPs", "Escalation matrix"],
        "retrieval_mode": capture["retrieval_mode"],
        "top_confidence": capture["confidence"],
        "direct_to_llm": capture["direct_to_llm"],
        "excluded": excluded,
        "excluded_total": sum(item["count"] for item in excluded),
        "passages": passages,
        "answer": {
            "headline": ANSWER_HEADLINE,
            "sentences": [
                {
                    "text": text,
                    "citations": [CITATION_LABELS[entry_id] for entry_id in cites],
                }
                for text, cites in ANSWER_SENTENCES
            ],
            "gaps": list(KNOWLEDGE_GAPS),
        },
        "governance": [
            "Only published, reviewed passages are eligible; draft, rejected, superseded and expired versions are excluded before ranking.",
            "Every answer sentence cites the passage it rests on.",
            "Retrieved text is evidence for the answer, not instructions to the system.",
        ],
    }
