"""P4 PP2 — the versioned role prompt contract type.

One record per role, every field required. ``NOT_APPLICABLE`` is a legal value but
only with a reason, because "we did not think about it" and "this genuinely does not
apply" must not look the same in the registry.

Hashes are derived, never stored
--------------------------------
``PROMPT_HASH`` and ``STABLE_PREFIX_HASH`` are computed from content by
``app.llm.policy.templates``. Storing them would let a contract's declared hash drift
from the contract's actual content, which is precisely the failure the hash exists to
detect.

Authority
---------
Every contract declares what it may and may not do. The prohibited set is not
free-form: ``UNIVERSAL_PROHIBITED_AUTHORITY`` below is forced onto every role, so a
new role cannot be added with a quietly shorter prohibition list. A role may add more
prohibitions; it can never subtract one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CONTRACT_SCHEMA_VERSION = "prompt_role_contract_v1"

RuntimePosture = Literal[
    "PRODUCTION_REACHABLE",
    "BLOCKED_BY_ALLOWLIST",
    "DORMANT",
    "TEST_ONLY",
    "LEGACY_DEAD",
]

#: Provider-agnostic capability classes. Deliberately not provider or model names:
#: P4 must not change anyone's deployed model selection.
ModelClass = Literal[
    "small_structured_classifier",
    "general_structured_reasoner",
    "investigation_reasoner",
    "composer",
    "NOT_APPLICABLE",
]

DecodingPosture = Literal["deterministic", "low_variance", "NOT_APPLICABLE"]

CacheEligibility = Literal["ELIGIBLE", "INELIGIBLE_DYNAMIC_ONLY", "INELIGIBLE_NO_STABLE_PREFIX"]

#: Authority no prompt may ever grant. Forced onto every role contract.
#: These mirror the deterministic boundaries architecture.md already fixes; a prompt
#: cannot widen them, so listing them here is a restatement, not a new policy.
UNIVERSAL_PROHIBITED_AUTHORITY: tuple[str, ...] = (
    "routing_authority",
    "tool_execution_authority",
    "mcp_invocation_authority",
    "rbac_decision",
    "hil_bypass",
    "write_or_remediation_authority",
    "candidate_spl_execution",
    "final_rqc_overwrite",
    "fabricating_evidence",
    "fabricating_source_evidence",
    "unbounded_investigation_loop",
    "self_authorizing_additional_tool_calls",
)


class RoleContractError(ValueError):
    """Raised when a contract is structurally invalid. Never caught at runtime."""


def _requires_reason(value: str) -> bool:
    """NOT_APPLICABLE must be justified: 'NOT_APPLICABLE: <reason>'."""
    stripped = value.strip()
    if stripped == "NOT_APPLICABLE":
        return True
    return stripped.startswith("NOT_APPLICABLE") and len(stripped) <= len("NOT_APPLICABLE:")


@dataclass(frozen=True)
class RoleContract:
    """The complete governed contract for one LLM role."""

    role_id: str
    runtime_posture: RuntimePosture
    why_llm: str
    #: Inputs the role may treat as ground truth. Deterministic in origin.
    authoritative_inputs: tuple[str, ...]
    #: Context the role may read but must not treat as fact.
    non_authoritative_context: tuple[str, ...]
    #: Goes in the STABLE PREFIX. Must carry no request data.
    system_instruction: str
    #: Goes in the DYNAMIC SUFFIX. Names of per-turn inputs, not their values.
    dynamic_context: tuple[str, ...]
    output_schema: str
    few_shot_set: str
    negative_example_set: str
    model_class: ModelClass
    decoding: DecodingPosture
    timeout_seconds: float | None
    retry_repair_policy: str
    allowed_authority: tuple[str, ...]
    #: Role-specific prohibitions. UNIVERSAL_PROHIBITED_AUTHORITY is added on top.
    extra_prohibited_authority: tuple[str, ...] = field(default_factory=tuple)
    validator: str = ""
    fallback: str = ""
    trace_fields: tuple[str, ...] = field(default_factory=tuple)
    prompt_template_id: str = ""
    prompt_version: str = ""
    #: Owning workstream, when the live seam is not D's to edit.
    owning_workstream: str = "D_POLICY"

    def __post_init__(self) -> None:
        self._validate()

    # -- derived ----------------------------------------------------------

    @property
    def prohibited_authority(self) -> tuple[str, ...]:
        """Universal prohibitions plus this role's own. A role can only add."""
        merged = list(UNIVERSAL_PROHIBITED_AUTHORITY)
        for item in self.extra_prohibited_authority:
            if item not in merged:
                merged.append(item)
        return tuple(merged)

    @property
    def cache_eligible(self) -> CacheEligibility:
        """A role with no stable instruction has no prefix worth caching."""
        if not self.system_instruction.strip():
            return "INELIGIBLE_NO_STABLE_PREFIX"
        if _requires_reason(self.few_shot_set) and _requires_reason(self.negative_example_set):
            # Still cacheable: the instruction and schema alone form a stable prefix.
            return "ELIGIBLE"
        return "ELIGIBLE"

    # -- validation -------------------------------------------------------

    def _validate(self) -> None:
        required_text = {
            "role_id": self.role_id,
            "why_llm": self.why_llm,
            "system_instruction": self.system_instruction,
            "output_schema": self.output_schema,
            "few_shot_set": self.few_shot_set,
            "negative_example_set": self.negative_example_set,
            "retry_repair_policy": self.retry_repair_policy,
            "validator": self.validator,
            "fallback": self.fallback,
            "prompt_template_id": self.prompt_template_id,
            "prompt_version": self.prompt_version,
        }
        for name, value in required_text.items():
            if not str(value).strip():
                raise RoleContractError(f"{self.role_id or '<unnamed>'}: {name} must not be blank")
            if _requires_reason(str(value)):
                raise RoleContractError(
                    f"{self.role_id}: {name} is NOT_APPLICABLE without a reason"
                )

        if not self.authoritative_inputs:
            raise RoleContractError(f"{self.role_id}: authoritative_inputs must not be empty")
        if not self.allowed_authority:
            raise RoleContractError(f"{self.role_id}: allowed_authority must not be empty")
        if not self.trace_fields:
            raise RoleContractError(f"{self.role_id}: trace_fields must not be empty")

        overlap = set(self.allowed_authority) & set(self.prohibited_authority)
        if overlap:
            raise RoleContractError(
                f"{self.role_id}: authority both allowed and prohibited: {sorted(overlap)}"
            )

        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise RoleContractError(f"{self.role_id}: timeout_seconds must be positive or None")


def merge_prohibited(*extra: str) -> tuple[str, ...]:
    """Helper for callers that want the effective prohibition set for a role."""
    merged = list(UNIVERSAL_PROHIBITED_AUTHORITY)
    for item in extra:
        if item not in merged:
            merged.append(item)
    return tuple(merged)
