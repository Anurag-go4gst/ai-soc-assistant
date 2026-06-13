"""B11 — the LLM correctness prompt may emit tstats/from against approved CIM
datamodels; the deterministic validator must accept them via its CIM branch
(separate from raw_search). These tests pin that contract so lifting the prompt
ban does not produce SPL the validator then rejects.
"""
from __future__ import annotations

from app.safeguards.spl_validator import (
    APPROVED_DATAMODELS,
    QUERY_SHAPE_TSTATS_DATAMODEL,
    _detect_query_shape,
    validate_spl,
)
from app.spl.llm_fallback import APPROVED_CIM_DATAMODELS

VALID_TSTATS = (
    "tstats summariesonly=true count from datamodel=Authentication "
    "where earliest=-24h latest=now by Authentication.user | sort - count | head 100"
)


def test_prompt_allowlist_is_subset_of_validator_allowlist():
    # The correctness prompt must only advertise datamodels the validator accepts.
    assert set(APPROVED_CIM_DATAMODELS) <= APPROVED_DATAMODELS


def test_tstats_query_routes_to_cim_branch():
    assert _detect_query_shape(VALID_TSTATS) == QUERY_SHAPE_TSTATS_DATAMODEL


def test_valid_tstats_authentication_passes_validation():
    result = validate_spl(VALID_TSTATS)
    assert result["approved"] is True
    assert result["validation_profile"] == "cim_tstats_datamodel_v1"
    assert result["reject_reasons"] == []


def test_tstats_unapproved_datamodel_is_rejected():
    spl = (
        "tstats summariesonly=true count from datamodel=SecretModel "
        "where earliest=-24h latest=now by SecretModel.user | head 100"
    )
    result = validate_spl(spl)
    assert result["approved"] is False
