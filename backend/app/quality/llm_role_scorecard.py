"""Phase 5 — LLM role scorecard (WS3 T3.1). Read-model over control_plane_trace.

Aggregates per-role sidecar/narration telemetry already present on each turn's
``control_plane_trace`` (no new write path):

- invocation count (n)
- fallback rate (answered by Foundation-Sec Instruct instead of local primary)
- agreement rate vs the deterministic decision (guard passed / advisory accepted)
- guard / disagreement reasons

Verdict per role drives the COE promotion gate. Nothing here changes routing,
severity, MITRE, SPL, HIL, or execution — it only measures.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

# Endpoint labels (endpoint_resolver). A fallback answer means local primary was
# down/slow and Foundation-Sec Instruct served instead.
PRIMARY_LABEL = "local_primary"
FALLBACK_LABEL = "foundation_sec_instruct_fallback"

# Verdict thresholds (plan §Phase 5).
MIN_SAMPLE = 20
MAX_FALLBACK_RATE = 0.10
MIN_AGREEMENT_RATE = 0.70

VERDICT_HEALTHY = "HEALTHY"
VERDICT_DEGRADED = "DEGRADED"
VERDICT_INSUFFICIENT = "INSUFFICIENT_DATA"


@dataclass
class RoleMetrics:
    role: str
    invocations: int = 0
    fallbacks: int = 0
    timeouts: int = 0
    disagreements: int = 0
    disagreement_reasons: list[str] = field(default_factory=list)

    @property
    def fallback_rate(self) -> float:
        return round(self.fallbacks / self.invocations, 3) if self.invocations else 0.0

    @property
    def agreement_rate(self) -> float:
        if not self.invocations:
            return 0.0
        return round(1.0 - (self.disagreements / self.invocations), 3)

    def verdict(self) -> str:
        if self.invocations < MIN_SAMPLE:
            return VERDICT_INSUFFICIENT
        if self.fallback_rate >= MAX_FALLBACK_RATE or self.agreement_rate < MIN_AGREEMENT_RATE:
            return VERDICT_DEGRADED
        return VERDICT_HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "invocations": self.invocations,
            "fallbacks": self.fallbacks,
            "timeouts": self.timeouts,
            "disagreements": self.disagreements,
            "fallback_rate": self.fallback_rate,
            "agreement_rate": self.agreement_rate,
            "disagreement_reasons": sorted(set(self.disagreement_reasons))[:20],
            "verdict": self.verdict(),
        }


def _is_fallback(label: str | None) -> bool:
    return bool(label) and FALLBACK_LABEL in str(label)


def _record(metrics: dict[str, RoleMetrics], role: str) -> RoleMetrics:
    if role not in metrics:
        metrics[role] = RoleMetrics(role=role)
    return metrics[role]


def aggregate_role_metrics(traces: list[dict[str, Any]]) -> dict[str, RoleMetrics]:
    """Aggregate per-role metrics from a list of ``control_plane_trace`` dicts."""
    metrics: dict[str, RoleMetrics] = {}
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        _aggregate_budget(metrics, trace.get("llm_turn_budget"))
        _aggregate_intent(metrics, trace.get("llm_intent_advisory") or _nested_intent(trace))
        _aggregate_missing_evidence(metrics, trace.get("missing_evidence_reasoning"))
        _aggregate_rationale(metrics, trace.get("mitre_risk_rationale"))
        _aggregate_composer(metrics, trace)
        _aggregate_resource_shadow(metrics, trace.get("resource_plan_shadow"))
    return metrics


def _nested_intent(trace: dict[str, Any]) -> dict[str, Any] | None:
    qti = trace.get("query_to_intent")
    if isinstance(qti, dict) and isinstance(qti.get("llm_intent_advisory"), dict):
        return qti["llm_intent_advisory"]
    return None


def _aggregate_budget(metrics: dict[str, RoleMetrics], budget: Any) -> None:
    # Budget records carry the authoritative per-call provider_label + outcome for
    # sidecar roles. Narration is attributed to the composer block instead.
    if not isinstance(budget, dict):
        return
    for record in budget.get("records") or []:
        if not isinstance(record, dict) or record.get("kind") != "sidecar":
            continue
        role = str(record.get("role") or "").strip()
        if not role:
            continue
        m = _record(metrics, role)
        m.invocations += 1
        if _is_fallback(record.get("provider_label")):
            m.fallbacks += 1
        if record.get("outcome") == "timed_out":
            m.timeouts += 1
            m.disagreements += 1
            m.disagreement_reasons.append("timed_out")


def _aggregate_intent(metrics: dict[str, RoleMetrics], advisory: Any) -> None:
    # Invocation count comes from the budget; here we only add agreement signal.
    if not isinstance(advisory, dict) or not advisory.get("llm_called"):
        return
    status = str(advisory.get("adjudication_status") or "")
    if status in {"corrected", "rejected"}:
        m = _record(metrics, "intent_shadow_classifier")
        m.disagreements += 1
        m.disagreement_reasons.append(str(advisory.get("adjudication_reason") or status))


def _aggregate_missing_evidence(metrics: dict[str, RoleMetrics], trace: Any) -> None:
    if not isinstance(trace, dict) or not trace.get("llm_called"):
        return
    # Invocation already counted via budget; add timeout disagreement if any.
    if trace.get("timed_out"):
        m = _record(metrics, "missing_evidence_reasoner")
        m.disagreement_reasons.append("timed_out")


def _aggregate_rationale(metrics: dict[str, RoleMetrics], trace: Any) -> None:
    if not isinstance(trace, dict) or not trace.get("llm_called"):
        return
    if trace.get("guard_status") == "blocked" or trace.get("fallback_used"):
        # Attribute to both reasoning roles' shared signal under mitre_reasoner.
        m = _record(metrics, "mitre_reasoner")
        m.disagreements += 1
        m.disagreement_reasons.append("rationale_guard_fallback")


def _aggregate_composer(metrics: dict[str, RoleMetrics], trace: dict[str, Any]) -> None:
    # The composer trace is nested under control_plane_trace["llm_composer"]; fall
    # back to the trace itself so bare-composer dicts also aggregate.
    composer = trace.get("llm_composer") if isinstance(trace.get("llm_composer"), dict) else trace
    used = composer.get("llm_composer_used")
    guard = composer.get("llm_guard_status")
    blocked_reason = composer.get("llm_blocked_reason")
    # Count a narration invocation only when the composer actually called the model
    # (used) or was blocked after a call (guard blocked with a reason).
    attempted = bool(used) or (guard == "blocked" and bool(blocked_reason))
    if not attempted:
        return
    m = _record(metrics, "narration_composer")
    m.invocations += 1
    if _is_fallback(composer.get("llm_provider_label") or composer.get("llm_answered_label")):
        m.fallbacks += 1
    if guard == "blocked":
        m.disagreements += 1
        m.disagreement_reasons.append(str(blocked_reason or "composer_guard_blocked"))


def _aggregate_resource_shadow(metrics: dict[str, RoleMetrics], trace: Any) -> None:
    if not isinstance(trace, dict) or not trace.get("llm_called"):
        return
    # Invocation already counted via budget record (route_plan_candidate_generator).
    if trace.get("promotion_blocked") is False:
        return


def build_llm_role_scorecard(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the full scorecard payload: per-role metrics + an overall verdict."""
    metrics = aggregate_role_metrics(traces)
    roles = {role: m.to_dict() for role, m in sorted(metrics.items())}
    verdicts = [m.verdict() for m in metrics.values()]
    if not verdicts:
        overall = VERDICT_INSUFFICIENT
    elif VERDICT_DEGRADED in verdicts:
        overall = VERDICT_DEGRADED
    elif all(v == VERDICT_HEALTHY for v in verdicts):
        overall = VERDICT_HEALTHY
    else:
        overall = VERDICT_INSUFFICIENT
    return {
        "sample_turns": len(traces),
        "roles": roles,
        "overall_verdict": overall,
        "thresholds": {
            "min_sample": MIN_SAMPLE,
            "max_fallback_rate": MAX_FALLBACK_RATE,
            "min_agreement_rate": MIN_AGREEMENT_RATE,
        },
    }
