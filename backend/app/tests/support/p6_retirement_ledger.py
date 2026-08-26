"""P6 conservative test rationalization — retirement ledger.

Every retirement or keep-as-orphan decision is a record. Removing a test without
a four-part record is a P6 stop condition. This module is the machine-checkable
ledger; it is not a license to delete coverage later without a new record.
"""

from __future__ import annotations

from typing import Literal, TypedDict

Disposition = Literal["KEEP", "TIER", "ARCHIVE", "REMOVE"]


class RetirementRecord(TypedDict):
    record_id: str
    old_test_id: str
    old_invariant: str
    replacement_owner_test: str
    green_proof: str
    risk_statement: str
    disposition: Disposition
    finding: str


# BEFORE collection measured at P5 SHA f1b741f8 on ws/l2-eval-bank:
# `pytest --collect-only -q -p no:cacheprovider` → 7111 tests collected.
# P6 added 7 contract tests → 7118. P8 L3-1 added 7 bank/threshold self-tests → 7125.
# P8-A added 8 candidate-prompt contract tests → 7133.
# P8 binding-proof added 2 request-provenance tests → 7135.
# P8 thread-safe provenance added 1 worker-thread test → 7136.
# P8 eval-arm thread visibility added 1 test → 7137.
COLLECTION_BEFORE = 7111
COLLECTION_AFTER = 7137

LEDGER: tuple[RetirementRecord, ...] = (
    {
        "record_id": "P6.R1.01",
        "old_test_id": "app/tests/test_retired_resource_planning_surfaces.py",
        "old_invariant": "Retired llm_plan_bridge / resource_plan_shadow stay unreachable as planning authority",
        "replacement_owner_test": "app/tests/test_retired_resource_planning_surfaces.py (KEEP)",
        "green_proof": "H-TESTUX-10 KEEP: file is the retirement pin, not a dead duplicate",
        "risk_statement": "Deleting it would un-pin Plan 2 B1 RETIRE and allow a silent revival",
        "disposition": "KEEP",
        "finding": "H-TESTUX-10",
    },
    {
        "record_id": "P6.R1.02",
        "old_test_id": "docs/evals/langgraph_dual_parity_report.json",
        "old_invariant": "Dual-runtime parity baseline remains a named committed report",
        "replacement_owner_test": "scripts/run_langgraph_dual_parity_eval.py --check (KEEP committed report)",
        "green_proof": "H-TESTUX-11 KEEP: Plan 6 E3 already recorded CONTINUE PRESERVING",
        "risk_statement": "Archiving without a harness path change would make governance --check ungrounded",
        "disposition": "KEEP",
        "finding": "H-TESTUX-11",
    },
    {
        "record_id": "P6.R1.03",
        "old_test_id": "frontend/src/components/ec/*.test.tsx",
        "old_invariant": "Experience Center stays isolated; EC tests must not become production /chat authority",
        "replacement_owner_test": "P7 production journeys (H-TESTUX-05); EC tests KEEP as isolation coverage",
        "green_proof": "H-TESTUX-04 KEEP: EC tests exercise EC components, not a literal copy of production ChatPanel",
        "risk_statement": "Deleting EC tests would drop isolation coverage; they are not a substitute for P7",
        "disposition": "KEEP",
        "finding": "H-TESTUX-04",
    },
    {
        "record_id": "P6.R2.01",
        "old_test_id": "(no exact duplicate family proven)",
        "old_invariant": "Do not combine tests with materially different failure meaning",
        "replacement_owner_test": "n/a — zero consolidations this wave",
        "green_proof": "Inspected sidecar timeout vs failover vs hard-timeout; assertions differ",
        "risk_statement": "Forced parameterization would hide distinct timeout vs failover failures",
        "disposition": "KEEP",
        "finding": "H-TESTUX-03",
    },
    {
        "record_id": "P6.R4.01",
        "old_test_id": "app/tests/test_sidecar_timeout_hard.py",
        "old_invariant": "Sidecar timeout budget is enforced without hanging the suite",
        "replacement_owner_test": "same file, marked l2_slow",
        "green_proof": "Module-level pytest.mark.l2_slow; assertions unchanged",
        "risk_statement": "Marker-only; omitting the file from default L1 still leaves it in full suite",
        "disposition": "TIER",
        "finding": "H-TESTUX-02",
    },
    {
        "record_id": "P6.R4.02",
        "old_test_id": "app/tests/test_sidecar_timeout_failover.py",
        "old_invariant": "Primary timeout falls over without occupying a second live slot as authority",
        "replacement_owner_test": "same file, marked l2_slow",
        "green_proof": "Module-level pytest.mark.l2_slow; assertions unchanged",
        "risk_statement": "Marker-only; failover coverage remains in full suite and -m l2_slow",
        "disposition": "TIER",
        "finding": "H-TESTUX-02",
    },
    {
        "record_id": "P6.R4.03",
        "old_test_id": "app/tests/test_synthesis_narration_deadline.py",
        "old_invariant": "Narration deadline is monotonic and fails closed to deterministic draft",
        "replacement_owner_test": "same file, marked l2_slow",
        "green_proof": "Module-level pytest.mark.l2_slow; assertions unchanged",
        "risk_statement": "Marker-only; deadline tests remain required for promotion full suite",
        "disposition": "TIER",
        "finding": "H-TESTUX-02",
    },
)


def removed_records() -> tuple[RetirementRecord, ...]:
    return tuple(row for row in LEDGER if row["disposition"] == "REMOVE")


def archive_records() -> tuple[RetirementRecord, ...]:
    return tuple(row for row in LEDGER if row["disposition"] == "ARCHIVE")
