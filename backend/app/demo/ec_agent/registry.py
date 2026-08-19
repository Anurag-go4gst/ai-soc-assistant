"""Registry of EC scenarios that expose ec_agent_workflow."""

from __future__ import annotations

from app.demo.ec_agent.types import AgentProfile

_PROFILES: dict[str, AgentProfile] = {}
_LOADED = False


def _ensure_profiles_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    import app.demo.ec_agent.profiles  # noqa: F401

    _LOADED = True


def register_agent_profile(profile: AgentProfile) -> None:
    if profile.scenario_id in _PROFILES:
        raise ValueError(f"agent profile already registered: {profile.scenario_id}")
    _PROFILES[profile.scenario_id] = profile


def get_agent_profile(scenario_id: str) -> AgentProfile | None:
    _ensure_profiles_loaded()
    return _PROFILES.get(scenario_id)


def has_agent_profile(scenario_id: str) -> bool:
    _ensure_profiles_loaded()
    return scenario_id in _PROFILES


def registered_agent_scenario_ids() -> frozenset[str]:
    _ensure_profiles_loaded()
    return frozenset(_PROFILES)
