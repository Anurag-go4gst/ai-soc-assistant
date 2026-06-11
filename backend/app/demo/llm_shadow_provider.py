"""Experience Center Foundation-Sec advisory model signal (lineage only)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import settings

MODEL_FAMILY = "foundation_sec_instruct_shadow"
DROP_DISABLED = "shadow_disabled"
DROP_PROVIDER_DISABLED = "provider_disabled"
DROP_EXECUTION_CLAIM = "forbidden_execution_claim"
DROP_REMEDIATION_ACTION = "forbidden_remediation_action"
DROP_RAW_SPL = "forbidden_raw_spl"
DROP_UNSUPPORTED_MITRE = "forbidden_unsupported_mitre"
DROP_EMPTY_AFTER_GOVERNANCE = "empty_after_governance"

EXECUTION_CLAIM_PATTERNS = (
    re.compile(r"\bexecuted\b", re.I),
    re.compile(r"\bwe ran\b", re.I),
    re.compile(r"\bquery ran\b", re.I),
    re.compile(r"\bresults show\b", re.I),
    re.compile(r"\blive splunk\b", re.I),
    re.compile(r"\bmcp execution completed\b", re.I),
    re.compile(r"\bthis ran in production\b", re.I),
)

REMEDIATION_PATTERNS = (
    re.compile(r"\bblock\s+ip\b", re.I),
    re.compile(r"\bisolate\s+(host|endpoint)\b", re.I),
    re.compile(r"\bdisable\s+user\b", re.I),
    re.compile(r"\bcontainment\b", re.I),
)

SPL_PATTERNS = (
    re.compile(r"\bsearch\s+index=", re.I),
    re.compile(r"\|\s*stats\b", re.I),
    re.compile(r"\|\s*timechart\b", re.I),
    re.compile(r"\bindex\s*=\s*\w+", re.I),
)

MITRE_PATTERN = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")


@dataclass(frozen=True)
class DemoLlmShadowContext:
    scenario_id: str
    query: str
    selected_skill: str
    governed_mitre_ids: tuple[str, ...] = ()
    trace_id: str | None = None


@dataclass
class DemoLlmShadowResult:
    enabled: bool = False
    called: bool = False
    provider: str = "disabled"
    model_family: str = MODEL_FAMILY
    raw_model_route_proposal: dict[str, Any] | None = None
    raw_model_summary_narration: str | None = None
    governed_route_proposal: dict[str, Any] | None = None
    governed_summary_narration: str | None = None
    governed_acceptance_status: str = "disabled"
    dropped_reasons: list[str] = field(default_factory=list)
    deterministic_wins: bool = True

    def to_lineage_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "called": self.called,
            "provider": self.provider,
            "model_family": self.model_family,
            "raw_model_route_proposal": self.raw_model_route_proposal,
            "raw_model_summary_narration": self.raw_model_summary_narration,
            "governed_route_proposal": self.governed_route_proposal,
            "governed_summary_narration": self.governed_summary_narration,
            "governed_acceptance_status": self.governed_acceptance_status,
            "dropped_reasons": list(self.dropped_reasons),
            "deterministic_wins": self.deterministic_wins,
            "coe_synthetic_fixture": True,
            "production_execution": False,
        }


@dataclass(frozen=True)
class DemoLlmShadowRaw:
    route_proposal: dict[str, Any]
    summary_narration: str


class DemoLlmShadowProvider(Protocol):
    def generate(self, context: DemoLlmShadowContext) -> DemoLlmShadowRaw:
        ...


class DisabledDemoLlmShadowProvider:
    def generate(self, context: DemoLlmShadowContext) -> DemoLlmShadowRaw:
        raise RuntimeError("disabled provider must not generate")


class FakeDemoLlmShadowProvider:
    """Static shadow payloads for tests and optional demo enablement."""

    def __init__(self, *, fixture_key: str = "default") -> None:
        self._fixture_key = fixture_key

    def generate(self, context: DemoLlmShadowContext) -> DemoLlmShadowRaw:
        fixtures = _fake_fixtures()
        payload = fixtures.get(self._fixture_key) or fixtures["default"]
        route = dict(payload["route_proposal"])
        route["scenario_id"] = context.scenario_id
        narration = str(payload["summary_narration"]).format(
            skill=context.selected_skill,
            query=context.query[:120],
        )
        return DemoLlmShadowRaw(route_proposal=route, summary_narration=narration)


class HuggingFaceDemoLlmShadowProvider:
    """Optional HF-compatible HTTP provider; never used in tests or default demo path."""

    def generate(self, context: DemoLlmShadowContext) -> DemoLlmShadowRaw:
        endpoint = (settings.demo_llm_shadow_endpoint or "").strip()
        if not endpoint:
            raise RuntimeError("DEMO_LLM_SHADOW_ENDPOINT is required for huggingface provider")
        raise NotImplementedError(
            "HuggingFace demo shadow HTTP client is not enabled in this stage; use fake provider for demos."
        )


def get_demo_llm_shadow_provider(provider_name: str | None = None) -> DemoLlmShadowProvider:
    name = (provider_name or settings.demo_llm_shadow_provider or "disabled").strip().lower()
    if name == "fake":
        return FakeDemoLlmShadowProvider()
    if name == "huggingface":
        return HuggingFaceDemoLlmShadowProvider()
    return DisabledDemoLlmShadowProvider()


def govern_demo_llm_shadow(
    raw: DemoLlmShadowRaw,
    context: DemoLlmShadowContext,
) -> tuple[dict[str, Any] | None, str | None, list[str]]:
    dropped: list[str] = []
    route = dict(raw.route_proposal)
    narration = raw.summary_narration

    route_reasons = _govern_route_proposal(route, context)
    dropped.extend(route_reasons)
    if route_reasons:
        route = None

    narration_reasons = _govern_narration(narration, context)
    dropped.extend(narration_reasons)
    if narration_reasons:
        narration = None

    return route, narration, sorted(set(dropped))


def _govern_route_proposal(route: dict[str, Any], context: DemoLlmShadowContext) -> list[str]:
    dropped: list[str] = []
    serialized = str(route)
    dropped.extend(_scan_text_violations(serialized))
    proposed_skill = str(route.get("primary_skill") or route.get("suggested_skill") or "")
    if proposed_skill and proposed_skill != context.selected_skill:
        route["deterministic_skill_authority"] = context.selected_skill
    mitre = route.get("mitre_technique_ids") or route.get("mitre_ids") or []
    if isinstance(mitre, list):
        dropped.extend(_govern_mitre_list(mitre, context))
    return dropped


def _govern_narration(text: str, context: DemoLlmShadowContext) -> list[str]:
    return _scan_text_violations(text)


def _scan_text_violations(text: str) -> list[str]:
    dropped: list[str] = []
    if any(pattern.search(text) for pattern in EXECUTION_CLAIM_PATTERNS):
        dropped.append(DROP_EXECUTION_CLAIM)
    if any(pattern.search(text) for pattern in REMEDIATION_PATTERNS):
        dropped.append(DROP_REMEDIATION_ACTION)
    if any(pattern.search(text) for pattern in SPL_PATTERNS):
        dropped.append(DROP_RAW_SPL)
    return dropped


def _govern_mitre_list(mitre: list[Any], context: DemoLlmShadowContext) -> list[str]:
    if not context.governed_mitre_ids:
        return []
    allowed = set(context.governed_mitre_ids)
    extras = [str(item) for item in mitre if str(item) not in allowed]
    if extras:
        return [DROP_UNSUPPORTED_MITRE]
    return []


def run_demo_llm_shadow(
    context: DemoLlmShadowContext,
    *,
    provider_override: DemoLlmShadowProvider | None = None,
    fake_fixture_key: str | None = None,
) -> DemoLlmShadowResult | None:
    if not settings.demo_llm_shadow_enabled:
        return None

    provider_name = settings.demo_llm_shadow_provider.strip().lower()
    if provider_name == "disabled":
        return DemoLlmShadowResult(
            enabled=True,
            called=False,
            provider="disabled",
            governed_acceptance_status="disabled",
            dropped_reasons=[DROP_PROVIDER_DISABLED],
        )

    if provider_override is not None:
        provider = provider_override
        provider_name = "fake"
    elif fake_fixture_key:
        provider = FakeDemoLlmShadowProvider(fixture_key=fake_fixture_key)
        provider_name = "fake"
    else:
        provider = get_demo_llm_shadow_provider(provider_name)

    if isinstance(provider, DisabledDemoLlmShadowProvider):
        return DemoLlmShadowResult(
            enabled=True,
            called=False,
            provider=provider_name,
            governed_acceptance_status="disabled",
            dropped_reasons=[DROP_PROVIDER_DISABLED],
        )

    if provider_name == "huggingface":
        return DemoLlmShadowResult(
            enabled=True,
            called=False,
            provider="huggingface",
            governed_acceptance_status="disabled",
            dropped_reasons=["huggingface_demo_http_not_enabled"],
        )

    raw = provider.generate(context)
    governed_route, governed_narration, dropped = govern_demo_llm_shadow(raw, context)

    status = "accepted_shadow"
    if dropped and (governed_route or governed_narration):
        status = "partially_accepted"
    elif dropped:
        status = "dropped"

    return DemoLlmShadowResult(
        enabled=True,
        called=True,
        provider=provider_name,
        model_family=MODEL_FAMILY,
        raw_model_route_proposal=raw.route_proposal,
        raw_model_summary_narration=raw.summary_narration,
        governed_route_proposal=governed_route,
        governed_summary_narration=governed_narration,
        governed_acceptance_status=status,
        dropped_reasons=dropped,
        deterministic_wins=True,
    )


def _fake_fixtures() -> dict[str, dict[str, Any]]:
    return {
        "default": {
            "route_proposal": {
                "primary_skill": "attack_discovery",
                "pattern_id": "shadow_demo_pattern",
                "candidate_reason": "model_shadow_suggestion_only",
                "mitre_technique_ids": ["T1110.001"],
            },
            "summary_narration": (
                "Shadow model proposes reviewing {skill} context for '{query}'. "
                "Deterministic demo fixture remains authoritative; no execution occurred."
            ),
        },
        "bad_spl": {
            "route_proposal": {"primary_skill": "spl_generation", "spl_hint": "search index=secret | delete"},
            "summary_narration": "Try search index=pgcil_soc | stats count by user in Splunk now.",
        },
        "bad_execution": {
            "route_proposal": {"primary_skill": "attack_discovery"},
            "summary_narration": "We ran the query and results show compromise in production.",
        },
        "bad_remediation": {
            "route_proposal": {"primary_skill": "attack_discovery"},
            "summary_narration": "Next step: block IP and disable user on the host immediately.",
        },
        "bad_mitre": {
            "route_proposal": {
                "primary_skill": "attack_discovery",
                "mitre_technique_ids": ["T9999"],
            },
            "summary_narration": "Shadow MITRE hint only; governed mapping unchanged.",
        },
    }
