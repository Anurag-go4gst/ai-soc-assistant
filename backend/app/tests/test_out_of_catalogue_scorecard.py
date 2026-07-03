"""Plan 0.1 — out-of-catalogue scorecard runner contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evals.run_out_of_catalogue_scorecard import (
    load_probes,
    run_probe,
    run_scorecard,
    scorecard_row_contract_keys,
    write_jsonl,
)

PINNED_PROBE_IDS = (
    "harvest.ot.ot_oc_01",
    "harvest.oos.oos.mitre.01",
    "harvest.pk.pk.003",
)


def test_probe_bank_loads_and_has_harvested_probes() -> None:
    bank = load_probes()
    assert bank["version"] == "2026-07-02"
    assert bank["probe_count"] >= 40
    probes = bank["probes"]
    sources = {probe["source"] for probe in probes}
    assert "out_of_catalog_ot_probe_bank.json" in sources
    assert "out_of_set_soc_corpus.jsonl" in sources
    assert "power_industry_probe_v3_bank.json" in sources
    assert "live_efficacy_100_bank.json" in sources
    assert len(bank.get("hand_score_sample_probe_ids") or []) == 15


@pytest.mark.parametrize("probe_id", PINNED_PROBE_IDS)
def test_pinned_probe_offline_scorecard_row_contract(probe_id: str) -> None:
    bank = load_probes()
    probe = next(item for item in bank["probes"] if item["probe_id"] == probe_id)
    row = run_probe(probe, offline=True)
    assert row["status"] == "ok", row.get("error")
    assert scorecard_row_contract_keys() <= set(row.keys())
    assert isinstance(row["probe_id"], str)
    assert row["match_path"] is None or isinstance(row["match_path"], str)
    assert isinstance(row["resource_plan"], dict)
    assert isinstance(row["resource_plan"].get("steps"), list)
    assert isinstance(row["llm_calls"], list)
    assert isinstance(row["evidence_classes"], list)
    assert row["evidence_classes"]
    assert isinstance(row["answer_text"], str)
    assert row["answer_text"].strip()
    for call in row["llm_calls"]:
        assert "role" in call
        assert "llm_output_utilization" in call


def test_scorecard_jsonl_one_row_per_probe(tmp_path: Path) -> None:
    bank = load_probes()
    pinned = [p for p in bank["probes"] if p["probe_id"] in PINNED_PROBE_IDS]
    report = run_scorecard(probes=pinned, offline=True)
    out = tmp_path / "scorecard.jsonl"
    with out.open("w", encoding="utf-8") as handle:
        write_jsonl(report, handle)
    lines = [line for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == len(PINNED_PROBE_IDS)
    for line in lines:
        row = json.loads(line)
        assert scorecard_row_contract_keys() <= set(row.keys())
