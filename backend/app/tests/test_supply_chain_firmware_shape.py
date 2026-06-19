"""pk.009 slice — supply-chain firmware integrity shape (judgment + substance)."""

from __future__ import annotations

from app.chat.answer_shape_router import (
    build_supply_chain_firmware_guidance,
    classify_answer_shape,
    is_supply_chain_firmware_query,
)

_PK009 = (
    "A vendor pushed a firmware update signed with an unexpected code-signing certificate "
    "to 40 RTUs overnight. How do we determine whether this is a legitimate vendor key "
    "rotation or a supply-chain compromise?"
)


def test_detects_supply_chain_firmware_query() -> None:
    assert is_supply_chain_firmware_query(_PK009)
    assert not is_supply_chain_firmware_query("hunt for modbus writes to the boiler plc")


def test_shape_router_resolves_supply_chain() -> None:
    assert classify_answer_shape(_PK009).primary_shape == "supply_chain_firmware_integrity"


def test_guidance_pairs_judgment_with_substance() -> None:
    text = build_supply_chain_firmware_guidance(_PK009).lower()
    # judgment present
    assert "not enough to confirm" in text or "does not confirm" in text
    # substance present
    assert "code-signing certificate" in text
    assert "release manifest" in text
    assert "rollback" in text
    assert "candidate" in text  # MITRE stays candidate
