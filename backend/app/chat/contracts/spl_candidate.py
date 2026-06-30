from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class SplCandidateStageResult:
    """Single return contract for the LLM SPL candidate stage (Phase 4).

    Replaces the bare ``(candidate_payload, validation_payload)`` tuple so the LLM
    detection plan and compiler telemetry survive to the workflow node, which is
    solely responsible for persisting them (the compiler/fallback never write
    state). It stays **tuple-unpackable** (``__iter__`` / ``__getitem__`` /
    ``__len__``) so the many existing ``candidate, validation = ...`` call sites
    keep working unchanged while new consumers read ``.detection_plan`` /
    ``.compiler_telemetry`` explicitly.
    """

    candidate_payload: Any | None = None
    validation_payload: Any | None = None
    detection_plan: dict[str, Any] | None = None
    compiler_telemetry: dict[str, Any] = field(default_factory=dict)

    def __iter__(self) -> Iterator[Any]:
        yield self.candidate_payload
        yield self.validation_payload

    def __getitem__(self, index: int) -> Any:
        return (self.candidate_payload, self.validation_payload)[index]

    def __len__(self) -> int:
        return 2

    def as_legacy_tuple(self) -> tuple[Any | None, Any | None]:
        return self.candidate_payload, self.validation_payload

    @classmethod
    def from_value(
        cls,
        value: "SplCandidateStageResult | tuple[Any, Any] | None",
        *,
        detection_plan: dict[str, Any] | None = None,
        compiler_telemetry: dict[str, Any] | None = None,
    ) -> "SplCandidateStageResult | None":
        """Coerce a tuple / existing result / None into SplCandidateStageResult.

        ``detection_plan`` defaults to the value found on the candidate payload so
        the typed field mirrors what the workflow node persists.
        """
        if value is None:
            return None
        if isinstance(value, SplCandidateStageResult):
            return value
        candidate, validation = value
        if detection_plan is None and isinstance(candidate, dict):
            detection_plan = candidate.get("detection_plan")
        if compiler_telemetry is None and isinstance(candidate, dict):
            compiler_telemetry = candidate.get("spl_plan_compiler_telemetry") or {}
        return cls(
            candidate_payload=candidate,
            validation_payload=validation,
            detection_plan=detection_plan,
            compiler_telemetry=compiler_telemetry or {},
        )
