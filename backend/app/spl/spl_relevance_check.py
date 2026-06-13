"""Structural SPL relevance gate (Stage 3K / SPL audit Phase C, R5).

Answers one question the deterministic safety validator does NOT: *does this SPL
answer what was asked?* `spl_validator.validate_spl` checks safety (index, time
bounds, aggregation presence, head limit); it never checks that the SPL's data
source, metric, and entity match the user's question. A safe-but-wrong SPL
(e.g. a DNS question answered with network-bytes SPL) passes safety but fails
relevance.

This module is the **structural** half of the gate — deterministic, no LLM. The
LLM self-critique half lives on the failover path (`llm_fallback`) and calls in
here for the structural verdict first. Inputs are read from existing models, not
a new slot schema:

  - entities     ← QueryUnderstandingResult.entities (QueryEntities)
  - data source  ← question keywords + UseCaseDefinition.required_sources
  - metric       ← question keywords (top/most/count/...) vs SPL aggregation

The constants here are the single source of truth; `scripts/eval_spl_relevance.py`
imports them so the gate and the baseline eval score identically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid import cycle at runtime
    from app.query_understanding.models import QueryUnderstandingResult


# --- Data-source signatures -------------------------------------------------
# Logical data source -> (question keywords that name it, SPL body tokens that
# prove the SPL queries it). Relevance requires every source the question names
# to appear in the SPL body.
DATA_SOURCES: dict[str, dict[str, list[str]]] = {
    "auth": {
        "q": ["login", "logon", "authentication", "auth", "failed login", "sign-in",
              "account lockout", "lockout", "brute force", "password", "credential",
              "privileged", "4625", "4624", "4740"],
        "spl": ["authentication", "wineventlog", "win:auth", "eventcode=46", "eventcode=4740",
                "failed_login", "login", "user=", "user_norm", "src_user", "account"],
    },
    "network": {
        "q": ["traffic", "top talker", "talkers", "bytes", "bandwidth", "connection",
              "smb", "port", "outbound", "egress", "lateral", "exfil", "data transfer",
              "vpn", "firewall", "denied", "blocked", "rdp"],
        "spl": ["network_traffic", "traffic", "dest_ip", "src_ip", "dest_port", "bytes",
                "conn", "all_traffic", "session", "app=", "src_ip_norm", "dest_ip_norm"],
    },
    "dns": {
        "q": ["dns", "domain", "beacon", "beaconing", "dga", "query", "resolution",
              "nxdomain", "c2", "command and control"],
        "spl": ["dns", "query", "network_resolution", "named", "answer", "domain", "query_norm"],
    },
    "endpoint": {
        # Endpoint-specific signals only — generic words like host/service/server are
        # entities, not a data-source signal, and over-trigger this source.
        "q": ["process", "powershell", "endpoint detection", "edr", "sysmon",
              "scheduled task", "persistence", "command line", "command-line",
              "encoded command", "parent process", "child process", "process creation"],
        "spl": ["edr", "endpoint", "process", "sysmon", "powershell", "cmdline", "command_line",
                "image", "parent_process", "schtask"],
    },
    "firewall": {
        "q": ["firewall", "denied", "deny", "blocked", "drop", "egress", "perimeter"],
        "spl": ["firewall", "action=blocked", "action=denied", "deny", "pan:", "fortinet",
                "action_norm"],
    },
}

# Aggregation/metric is expected when the question asks for a ranked / counted answer.
METRIC_Q = ["top", "most", "which", "how many", "count", "number of", "spike",
            "rare", "rarely", "anomaly", "unusual", "highest", "ranking", "rank",
            "distinct", "per ", "by ", "summary", "trend", "volume"]
AGG_SPL = ["stats", "tstats", "timechart", "chart", "top ", "rare ", "eventstats", "streamstats"]

# Entity tokens — asked entity should appear in the SPL (filter or by-clause).
ENTITY_TOKENS: dict[str, list[str]] = {
    "user": ["user", "account", "username"],
    "src_ip": ["ip", "source ip", "src", "address", "host"],
    "host": ["host", "machine", "endpoint", "asset", "device", "workstation", "server"],
    "dest": ["destination", "dest", "target", "domain"],
    "port": ["port"],
}

# Map QueryEntities fields to the entity classes above (for precise entity checks).
_QE_FIELD_TO_ENTITY = {
    "user": "user",
    "host": "host",
    "asset": "host",
    "source_ip": "src_ip",
    "destination_ip": "dest",
}


@dataclass
class RelevanceResult:
    """Structural relevance verdict for one (question, SPL) pair."""

    relevant: bool
    mismatches: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    trace: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "relevant": self.relevant,
            "mismatches": list(self.mismatches),
            "checks": dict(self.checks),
            "trace": self.trace,
        }


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _expected_sources(qtext: str) -> set[str]:
    q = _norm(qtext)
    return {src for src, sig in DATA_SOURCES.items() if any(kw in q for kw in sig["q"])}


def _spl_has_source(spl: str, source: str) -> bool:
    body = spl.lower()
    return any(tok in body for tok in DATA_SOURCES[source]["spl"])


def _asked_entities(qtext: str, understanding: "QueryUnderstandingResult | None") -> set[str]:
    q = _norm(qtext)
    asked = {e for e, toks in ENTITY_TOKENS.items() if any(t in q for t in toks)}
    # Concrete entities extracted by query understanding are higher-signal.
    if understanding is not None and getattr(understanding, "entities", None) is not None:
        ents = understanding.entities
        for qe_field, entity_class in _QE_FIELD_TO_ENTITY.items():
            if getattr(ents, qe_field, None):
                asked.add(entity_class)
    return asked


def check_spl_relevance(
    query: str,
    spl: str | None,
    *,
    understanding: "QueryUnderstandingResult | None" = None,
    required_sources: list[str] | None = None,
    pattern_type: str | None = None,
) -> RelevanceResult:
    """Deterministic structural relevance check.

    `relevant=False` with `mismatches` when the SPL's data source, aggregation,
    or entity does not match the question. A missing SPL is never relevant — the
    caller decides whether the question legitimately needs none.
    """
    if not spl:
        return RelevanceResult(
            relevant=False,
            mismatches=["no_spl_generated"],
            checks={},
            trace="no SPL provided to relevance check",
        )

    q = _norm(query)
    checks: dict[str, Any] = {}
    mismatches: list[str] = []

    # 1. Data source — every source the question names must appear in the SPL.
    expected = _expected_sources(query)
    checks["expected_sources"] = sorted(expected)
    src_ok = True
    if expected:
        missing = {s for s in expected if not _spl_has_source(spl, s)}
        if missing:
            src_ok = False
            mismatches.append(f"data_source_missing:{','.join(sorted(missing))}")
    checks["data_source_ok"] = src_ok

    # 2. Metric / aggregation — ranked/counted questions must aggregate.
    wants_metric = any(kw in q for kw in METRIC_Q)
    has_agg = any(tok in spl.lower() for tok in AGG_SPL)
    checks["wants_metric"] = wants_metric
    checks["has_aggregation"] = has_agg
    metric_ok = (not wants_metric) or has_agg
    if not metric_ok:
        mismatches.append("aggregation_missing")

    # 3. Entity — at least one asked entity must surface in the SPL.
    asked_entities = _asked_entities(query, understanding)
    checks["asked_entities"] = sorted(asked_entities)
    entity_ok = True
    if asked_entities:
        entity_ok = any(
            any(t in spl.lower() for t in ([e] + ENTITY_TOKENS[e])) for e in asked_entities
        )
        if not entity_ok:
            mismatches.append("entity_missing")
    checks["entity_ok"] = entity_ok

    relevant = src_ok and metric_ok and entity_ok
    trace = (
        "relevant" if relevant
        else "irrelevant: " + ", ".join(mismatches)
    )
    return RelevanceResult(relevant=relevant, mismatches=mismatches, checks=checks, trace=trace)
