"""Plan 6 D3/D4 — T4 KEEP 2.0s / DEFAULT-OFF; omit from persistent profile.

D3 recorded KEEP 2.0s / DEFAULT-OFF and
D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT.
D4 pins the repo default and does not persist T4 on VPS.
"""

from __future__ import annotations

from pathlib import Path

from app.chat.semantic_t4_understanding import SEMANTIC_T4_TIMEOUT_SECONDS
from app.config import Settings

_REPO = Path(__file__).resolve().parents[3]
_CONFIG_PY = Path(__file__).resolve().parents[1] / "config.py"
_PROFILE = _REPO / "docs" / "evals" / "plan6" / "production_flag_profile.md"
_STOP = _REPO / "docs" / "evals" / "plan6" / "c0_d3_stop_decisions.md"


def test_d3_keep_off_is_recorded() -> None:
    stop = _STOP.read_text(encoding="utf-8")
    assert "P6_T4_SERVING_POSTURE" in stop
    assert "KEEP 2.0s / DEFAULT-OFF" in stop
    assert "D1_PARAPHRASE_RESIDUE = DEFERRED_T4_SEMANTIC_SERVING_LIMIT" in stop
    assert "Do not add keyword heuristics" in stop
    profile = _PROFILE.read_text(encoding="utf-8")
    assert "OFF — omit from persistent profile" in profile
    assert "KEEP 2.0s / DEFAULT-OFF" in profile
    assert "DEFERRED_T4_SEMANTIC_SERVING_LIMIT" in profile


def test_t4_config_default_and_timeout_unchanged() -> None:
    text = _CONFIG_PY.read_text(encoding="utf-8")
    assert "ai_soc_t4_semantic_understanding_enabled: bool = False" in text
    assert "ai_soc_t4_semantic_understanding_timeout_seconds: float = 2.0" in text
    assert Settings().ai_soc_t4_semantic_understanding_enabled is False
    assert Settings().ai_soc_t4_semantic_understanding_timeout_seconds == 2.0
    assert SEMANTIC_T4_TIMEOUT_SECONDS == 2.0


def test_t4_not_enabled_in_coe_profile() -> None:
    text = (_REPO / "env" / "profiles" / "coe.env.example").read_text(encoding="utf-8")
    assert "AI_SOC_T4_SEMANTIC_UNDERSTANDING_ENABLED=true" not in text
