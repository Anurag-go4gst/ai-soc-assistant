"""Flagship Experience Center packs S1–S7. Isolated from production /chat."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.demo.ec_response import EcFollowUpChip, ExperienceCenterResponse
from app.demo.fixtures.s1.pack import (
    S1_FOLLOWUP_IDS,
    S1_SCENARIO_ID,
    build_s1_demo_scenarios,
    build_s1_turn,
    s1_analyst_override,
)
from app.demo.fixtures.s1.pack import _followup_catalog as s1_followups
from app.demo.fixtures.s2.pack import (
    S2_FOLLOWUP_IDS,
    S2_FOLLOWUPS,
    S2_SCENARIO_ID,
    build_s2_demo_scenarios,
    build_s2_turn,
    s2_analyst_override,
)
from app.demo.fixtures.s3.pack import (
    S3_FOLLOWUP_IDS,
    S3_FOLLOWUPS,
    S3_SCENARIO_ID,
    build_s3_demo_scenarios,
    build_s3_turn,
    s3_analyst_override,
)
from app.demo.fixtures.s4.pack import (
    S4_FOLLOWUP_IDS,
    S4_FOLLOWUPS,
    S4_SCENARIO_ID,
    build_s4_demo_scenarios,
    build_s4_turn,
    s4_analyst_override,
)
from app.demo.fixtures.s5.pack import (
    S5_FOLLOWUP_IDS,
    S5_ALL_FOLLOWUPS,
    S5_SCENARIO_ID,
    build_s5_demo_scenarios,
    build_s5_turn,
    s5_analyst_override,
)
from app.demo.fixtures.s6.pack import (
    S6_FOLLOWUP_IDS,
    S6_FOLLOWUPS,
    S6_SCENARIO_ID,
    S6_SYNONYMS,
    build_s6_demo_scenarios,
    build_s6_turn,
    resolve_s6_follow_up,
    s6_analyst_override,
)
from app.demo.fixtures.s7.pack import (
    S7_FOLLOWUP_IDS,
    S7_FOLLOWUPS,
    S7_SCENARIO_ID,
    build_s7_demo_scenarios,
    build_s7_turn,
    s7_analyst_override,
)

FLAGSHIP_SCENARIO_IDS = (
    S1_SCENARIO_ID,
    S2_SCENARIO_ID,
    S3_SCENARIO_ID,
    S4_SCENARIO_ID,
    S5_SCENARIO_ID,
    S6_SCENARIO_ID,
    S7_SCENARIO_ID,
)


class _Pack:
    def __init__(
        self,
        *,
        followup_ids: frozenset[str],
        followups: Callable[[], list[EcFollowUpChip]],
        build_turn: Callable[..., ExperienceCenterResponse],
        analyst_override: Callable[[str, dict[str, Any]], dict[str, Any] | None],
        demo_scenarios: Callable[[], dict[str, Any]],
        resolve: Callable[[str], str] | None = None,
    ) -> None:
        self.followup_ids = followup_ids
        self.followups = followups
        self.build_turn = build_turn
        self.analyst_override = analyst_override
        self.demo_scenarios = demo_scenarios
        self.resolve = resolve or (lambda follow_up_id: follow_up_id)


PACKS: dict[str, _Pack] = {
    S1_SCENARIO_ID: _Pack(
        followup_ids=S1_FOLLOWUP_IDS,
        followups=lambda: list(s1_followups()),
        build_turn=build_s1_turn,
        analyst_override=s1_analyst_override,
        demo_scenarios=build_s1_demo_scenarios,
    ),
    S2_SCENARIO_ID: _Pack(
        followup_ids=S2_FOLLOWUP_IDS,
        followups=lambda: list(S2_FOLLOWUPS),
        build_turn=build_s2_turn,
        analyst_override=s2_analyst_override,
        demo_scenarios=build_s2_demo_scenarios,
    ),
    S3_SCENARIO_ID: _Pack(
        followup_ids=S3_FOLLOWUP_IDS,
        followups=lambda: list(S3_FOLLOWUPS),
        build_turn=build_s3_turn,
        analyst_override=s3_analyst_override,
        demo_scenarios=build_s3_demo_scenarios,
    ),
    S4_SCENARIO_ID: _Pack(
        followup_ids=S4_FOLLOWUP_IDS,
        followups=lambda: list(S4_FOLLOWUPS),
        build_turn=build_s4_turn,
        analyst_override=s4_analyst_override,
        demo_scenarios=build_s4_demo_scenarios,
    ),
    S5_SCENARIO_ID: _Pack(
        followup_ids=S5_FOLLOWUP_IDS,
        followups=lambda: list(S5_ALL_FOLLOWUPS),
        build_turn=build_s5_turn,
        analyst_override=s5_analyst_override,
        demo_scenarios=build_s5_demo_scenarios,
    ),
    S6_SCENARIO_ID: _Pack(
        followup_ids=S6_FOLLOWUP_IDS,
        followups=lambda: list(S6_FOLLOWUPS),
        build_turn=build_s6_turn,
        analyst_override=s6_analyst_override,
        demo_scenarios=build_s6_demo_scenarios,
        resolve=resolve_s6_follow_up,
    ),
    S7_SCENARIO_ID: _Pack(
        followup_ids=S7_FOLLOWUP_IDS,
        followups=lambda: list(S7_FOLLOWUPS),
        build_turn=build_s7_turn,
        analyst_override=s7_analyst_override,
        demo_scenarios=build_s7_demo_scenarios,
    ),
}


def resolve_follow_up(scenario_id: str, follow_up_id: str) -> str:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return follow_up_id
    return pack.resolve(follow_up_id)


def followups_for_flagship(scenario_id: str) -> list[EcFollowUpChip] | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    return pack.followups()


def known_flagship_follow_up_ids(scenario_id: str) -> set[str] | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    ids = set(pack.followup_ids)
    if scenario_id == S6_SCENARIO_ID:
        ids.update(S6_SYNONYMS)
    return ids


def build_flagship_turn(
    scenario_id: str,
    *,
    session_id: str,
    turn: int,
    applied_follow_up_ids: list[str],
    pending_action_id: str | None = None,
    awaiting_external: bool = False,
) -> ExperienceCenterResponse | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    return pack.build_turn(
        session_id=session_id,
        turn=turn,
        applied_follow_up_ids=applied_follow_up_ids,
        pending_action_id=pending_action_id,
        awaiting_external=awaiting_external,
    )


def analyst_override_for(scenario_id: str, base: dict[str, Any]) -> dict[str, Any] | None:
    pack = PACKS.get(scenario_id)
    if pack is None:
        return None
    return pack.analyst_override(scenario_id, base)


def all_flagship_demo_scenarios() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for pack in PACKS.values():
        merged.update(pack.demo_scenarios())
    return merged


