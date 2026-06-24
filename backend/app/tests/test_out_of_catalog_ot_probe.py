from __future__ import annotations

from app.evals.out_of_catalog_ot_probe import evaluate_all, load_bank


def test_ot_probe_bank_loads() -> None:
    bank = load_bank()
    assert len(bank.get("probes") or []) >= 6


def test_ot_probe_bank_all_pass_offline() -> None:
    report = evaluate_all()
    assert report["critical_count"] == 0, report
