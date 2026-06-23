"""P3 deterministic asset-contribution floor (plan §456)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "eval_p3_contribution.py"
_spec = importlib.util.spec_from_file_location("eval_p3_contribution", _SCRIPT)
assert _spec and _spec.loader
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def test_mitre_buckets_with_provenance_no_fabrication() -> None:
    out = ev._eval_mitre()
    assert out["failures"] == []
    assert len(out["rows"]) == 15
    # Governance: no entry is ever labelled a "confirmed" technique.
    for r in out["rows"]:
        assert not (set(r["statuses"]) & ev.FORBIDDEN_MITRE_STATUS)
        assert r["provenance"] is True


def test_cve_chain_is_honest_when_not_onboarded() -> None:
    out = ev._eval_cve()
    assert out["failures"] == []
    for r in out["rows"]:
        # not-onboarded must still be substantive (carry a limitation), never silent.
        if r["status"] == "not_onboarded":
            assert r["limitation"] is True


def test_skills_expose_governed_contract_without_authority_override() -> None:
    out = ev._eval_skills()
    assert out["failures"] == []
    for r in out["rows"]:
        assert r["contract_ok"] is True
        assert r["no_authority_override"] is True


def test_rag_retriever_never_fabricates() -> None:
    out = ev._eval_rag()
    assert out["failures"] == []
