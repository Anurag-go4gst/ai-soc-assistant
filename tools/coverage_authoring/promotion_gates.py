"""Stage 3L-S5: Re-export backend promotion gates for authoring CLI."""

from __future__ import annotations

from app.coverage.manifest_promotion_gates import (  # noqa: F401
    PromotionGateCheck,
    PromotionGateResult,
    evaluate_promotion_gates,
)

__all__ = [
    "PromotionGateCheck",
    "PromotionGateResult",
    "evaluate_promotion_gates",
]
