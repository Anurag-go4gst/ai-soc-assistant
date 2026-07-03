"""Governed MCP investigation recipe registry (O5a — contract only).

A *recipe* is a small, deterministic, COE-approved description of how a single
chat turn may make one or more bounded MCP calls. Multi-call behaviour must come
from this registry, never from free-form planner or LLM prose (plan A.9).

This module is a **contract**: it defines the recipe shape, ships two governed
recipes, and provides pure validation/selection helpers. It does NOT call a
connector, does NOT wire into the live pipeline, and changes no execution
behaviour. The runtime scheduler/reconcile loop that consumes these recipes is
O5b/O5c and stays behind `MCP_MULTI_CALL_ORCHESTRATION_ENABLED` (default off).

Key governance invariants enforced here:
- A search-class call never sources executable SPL from `candidate_spl`; it
  uses a governed template family, a deterministic transform, or an
  LLM-proposed candidate that must re-enter full validation.
- The LLM-proposed broadened query (`broaden_scope_on_empty`) is advisory: its
  call requires HIL approval before it can execute, and it carries the full
  validation chain (relevance → source resolve → validate_spl → allowlist →
  approval). LLM intelligence in the loop; deterministic authority around it.
- Empty results are honest negative evidence and may only activate a
  predeclared follow-up edge — never open-ended LLM replanning.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Deterministic conditions only — evaluated against normalized envelope
# metadata, never arbitrary row-content interpretation (plan A.9).
ActivationCondition = Literal[
    "always",
    "previous_ok",
    "previous_empty",
    "evidence_key_missing",
]

# Distinct MCP call classes (plan A.3). A search call sources approved
# normalized SPL; a metadata call uses bounded allowlisted selectors.
CallClass = Literal[
    "metadata_discovery",
    "evidence_search",
    "investigation_pivot",
    "job_lifecycle",
]

# Where a search-class call's executable SPL comes from. Note the deliberate
# absence of "candidate_spl": candidate SPL is never executable.
SplSource = Literal[
    "template_family",
    "deterministic_transform",
    "llm_failover_candidate",
]

# Edge target for a failover/outcome: another call_id in the recipe, or a
# terminal policy. Terminal means "stop the loop"; "hil" means "stop and ask".
EdgeTarget = Literal["terminal", "hil"]

# The deterministic validation chain a search-class candidate must clear before
# any execution. Order is significant.
_SEARCH_VALIDATION_CHAIN = [
    "r5_relevance",
    "source_resolve",
    "validate_spl",
    "allowlist",
    "approval",
]


class RecipeCall(BaseModel):
    """One bounded call within a recipe. Edges are predeclared, not ad hoc."""

    call_id: str
    purpose: str
    call_class: CallClass
    depends_on: list[str] = Field(default_factory=list)
    activation_condition: ActivationCondition = "always"
    resource_capability: str
    resource_alternatives: list[str] = Field(default_factory=list)
    spl_source: SplSource | None = None
    spl_template_family: str | None = None
    required_evidence_keys: list[str] = Field(default_factory=list)
    produces_evidence_keys: list[str] = Field(default_factory=list)
    # Outcome edges: each is a sibling call_id or a terminal policy.
    on_unavailable: str = "hil"
    on_empty: str = "terminal"
    on_error: str = "hil"
    on_timeout: str = "hil"
    on_denied: str = "hil"
    # HIL: a search call requires analyst approval before it may execute. Only
    # when HIL approves does the call run (plan A.7 default production posture).
    requires_hil: bool = True
    hil_review_type: str = "spl_execution_confirmation"
    # Full deterministic validation chain a search candidate must clear.
    validation_chain: list[str] = Field(default_factory=list)
    terminal: bool = False
    max_attempts: int = 1

    @field_validator("spl_template_family")
    @classmethod
    def _candidate_spl_is_never_a_source(cls, value: str | None) -> str | None:
        if value is not None and value.strip().lower() in {"candidate_spl", "candidate"}:
            raise ValueError("candidate_spl is never an executable SPL source")
        return value


class Recipe(BaseModel):
    """A governed multi-call plan template. Start with `single_search`; add one
    COE-approved recipe at a time (plan A.9)."""

    recipe_id: str
    eligible_skills: list[str] = Field(default_factory=list)
    eligible_path_types: list[str] = Field(default_factory=list)
    max_calls: int = 1
    calls: list[RecipeCall] = Field(default_factory=list)

    def call_by_id(self, call_id: str) -> RecipeCall | None:
        for call in self.calls:
            if call.call_id == call_id:
                return call
        return None


def _single_search_recipe() -> Recipe:
    return Recipe(
        recipe_id="single_search",
        eligible_skills=["spl_generation", "alert_summary", "attack_discovery"],
        eligible_path_types=["spl_review", "spl_review_plus_rag", "hybrid_investigation"],
        max_calls=1,
        calls=[
            RecipeCall(
                call_id="c1_primary_search",
                purpose="Run the route-bound governed search.",
                call_class="evidence_search",
                activation_condition="always",
                resource_capability="spl_search",
                spl_source="template_family",
                produces_evidence_keys=["primary_search_rows"],
                on_empty="terminal",
                requires_hil=True,
                validation_chain=list(_SEARCH_VALIDATION_CHAIN),
                terminal=True,
            ),
        ],
    )


def _broaden_scope_on_empty_recipe() -> Recipe:
    """Lantern Plan-Run-Adapt analogue, governed (plan A.17 delta 1).

    The retry is *triggered* deterministically (`previous_empty`) but the
    broadened query is *proposed by the LLM* through the existing
    `AI_SOC_LLM_SPL_FALLBACK_ENABLED` failover path. The proposal is advisory:
    it re-enters the full validation chain and requires HIL approval before it
    can execute. If HIL approves, it executes; otherwise the loop stops.
    """
    return Recipe(
        recipe_id="broaden_scope_on_empty",
        eligible_skills=["spl_generation", "guided_investigation"],
        eligible_path_types=["spl_review", "spl_review_plus_rag", "hybrid_investigation"],
        max_calls=2,
        calls=[
            RecipeCall(
                call_id="c1_primary_search",
                purpose="Run the route-bound governed search.",
                call_class="evidence_search",
                activation_condition="always",
                resource_capability="spl_search",
                spl_source="template_family",
                produces_evidence_keys=["primary_search_rows"],
                # Empty primary result is the trigger for the broadened call.
                on_empty="c2_broadened_search",
                requires_hil=True,
                validation_chain=list(_SEARCH_VALIDATION_CHAIN),
            ),
            RecipeCall(
                call_id="c2_broadened_search",
                purpose=(
                    "LLM-proposed broadened/alternative search after an empty "
                    "primary result; bounded, validated, HIL-approved."
                ),
                call_class="evidence_search",
                depends_on=["c1_primary_search"],
                activation_condition="previous_empty",
                resource_capability="spl_search",
                # LLM proposes the broadened query; it is non-executable until
                # the full chain + HIL approval clears it.
                spl_source="llm_failover_candidate",
                produces_evidence_keys=["broadened_search_rows"],
                # A still-empty broadened result is honest negative — never
                # connector failure, never "no threat", never another retry.
                on_empty="terminal",
                requires_hil=True,
                hil_review_type="spl_execution_confirmation",
                validation_chain=list(_SEARCH_VALIDATION_CHAIN),
                terminal=True,
            ),
        ],
    )


def _hunt_baseline_recipe() -> Recipe:
    """Discovery -> bounded search -> on-empty broaden edge to HIL (item 3.2).

    A hunt-shaped turn gets one read-only discovery hop for context (no HIL —
    metadata only), then one bounded governed search. Unlike the other two
    recipes, an empty search result here is NOT a silent finalize: it routes
    to analyst hand-off (`on_empty="hil"`) since a hunt-shaped ask with zero
    rows is exactly the case where an analyst should decide whether to widen
    scope, not the loop.
    """
    return Recipe(
        recipe_id="hunt_baseline",
        eligible_skills=["attack_discovery", "guided_investigation"],
        eligible_path_types=["spl_review", "spl_review_plus_rag", "hybrid_investigation"],
        max_calls=2,
        calls=[
            RecipeCall(
                call_id="c1_discovery",
                purpose="Read-only metadata discovery to scope the hunt before searching.",
                call_class="metadata_discovery",
                activation_condition="always",
                resource_capability="metadata_discovery",
                produces_evidence_keys=["discovery_context"],
                on_empty="terminal",
                requires_hil=False,
            ),
            RecipeCall(
                call_id="c2_bounded_search",
                purpose="Run the bounded governed hunt search.",
                call_class="evidence_search",
                depends_on=["c1_discovery"],
                activation_condition="always",
                resource_capability="spl_search",
                spl_source="template_family",
                produces_evidence_keys=["hunt_search_rows"],
                on_empty="hil",
                requires_hil=True,
                validation_chain=list(_SEARCH_VALIDATION_CHAIN),
                terminal=True,
            ),
        ],
    )


_RECIPES: dict[str, Recipe] = {
    recipe.recipe_id: recipe
    for recipe in (_single_search_recipe(), _broaden_scope_on_empty_recipe(), _hunt_baseline_recipe())
}


def load_recipe_registry() -> dict[str, Recipe]:
    """Return a fresh copy of the governed recipe registry."""
    return {recipe_id: recipe.model_copy(deep=True) for recipe_id, recipe in _RECIPES.items()}


def get_recipe(recipe_id: str) -> Recipe | None:
    recipe = _RECIPES.get(recipe_id)
    return recipe.model_copy(deep=True) if recipe is not None else None


def select_recipe_for_plan(
    *,
    resource_plan_purposes: set[str] | list[str] | tuple[str, ...],
    answer_shape: str | None,
    mcp_allowed: bool,
    discovery_allowed: bool = False,
) -> str | None:
    """Deterministic recipe selection (item 3.2): promoted plan purposes +
    answer shape -> at most one governed recipe. The LLM never names a
    recipe directly — this maps already-validated plan/shape data to a
    registry id; the caller loads the actual Recipe via `get_recipe`."""
    purposes = set(resource_plan_purposes)
    if not (purposes & {"mcp_execution", "mcp_discovery"}):
        return None
    if not (mcp_allowed or discovery_allowed):
        return None
    if answer_shape == "hunt":
        return "hunt_baseline"
    return None


def recipes_for_skill(skill_id: str) -> list[Recipe]:
    return [
        recipe.model_copy(deep=True)
        for recipe in _RECIPES.values()
        if skill_id in recipe.eligible_skills
    ]


def validate_recipe(recipe: Recipe) -> list[str]:
    """Return a list of governance violations; empty means the recipe is valid.

    Pure check used by contract tests and (later) registry load-time assertions.
    """
    problems: list[str] = []
    call_ids = {call.call_id for call in recipe.calls}

    if len(recipe.calls) > recipe.max_calls:
        problems.append(f"{recipe.recipe_id}: more calls than max_calls={recipe.max_calls}")

    for call in recipe.calls:
        # Dependency and edge targets must resolve to real calls or terminals.
        for dep in call.depends_on:
            if dep not in call_ids:
                problems.append(f"{call.call_id}: depends_on unknown call '{dep}'")
        for edge_name in ("on_unavailable", "on_empty", "on_error", "on_timeout", "on_denied"):
            target = getattr(call, edge_name)
            if target not in ("terminal", "hil") and target not in call_ids:
                problems.append(f"{call.call_id}: {edge_name} points at unknown call '{target}'")

        # Search-class calls must declare the full validation chain and HIL.
        if call.call_class in ("evidence_search", "investigation_pivot"):
            if call.validation_chain != _SEARCH_VALIDATION_CHAIN:
                problems.append(f"{call.call_id}: search call missing the deterministic validation chain")
            if not call.requires_hil:
                problems.append(f"{call.call_id}: search call must require HIL approval before execution")
            if call.spl_source not in ("template_family", "deterministic_transform", "llm_failover_candidate"):
                problems.append(f"{call.call_id}: search call has no governed spl_source")

        # A non-`always` call must declare a dependency it reacts to.
        if call.activation_condition != "always" and not call.depends_on:
            problems.append(f"{call.call_id}: conditional activation requires depends_on")

    return problems


def evaluate_activation(condition: ActivationCondition, *, prior_outcome: str | None, missing_keys: list[str]) -> bool:
    """Pure activation check against normalized envelope metadata (plan A.9).

    `prior_outcome` is the classified outcome of the depended-on call
    ("ok"/"empty"/etc.); `missing_keys` are currently-unresolved evidence keys.
    """
    if condition == "always":
        return True
    if condition == "previous_ok":
        return prior_outcome == "ok"
    if condition == "previous_empty":
        return prior_outcome == "empty"
    if condition == "evidence_key_missing":
        return bool(missing_keys)
    return False
