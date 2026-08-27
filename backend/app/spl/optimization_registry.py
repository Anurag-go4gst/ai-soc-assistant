"""Live SPL preprocessor + optimization logic catalog for Knowledge UI.

Entries are anchored to real code symbols via inspect when deployed in this tree.
Optional OPTIONAL_PHASE_S modules are catalogued with runtime_active=false when absent.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from app.spl import draft_quality, llm_plan_compiler, spl_simplifier

rewrite_guard = importlib.import_module("app.spl.rewrite_guard") if importlib.util.find_spec("app.spl.rewrite_guard") else None
spl_auto_fix_safe = (
    importlib.import_module("app.spl.spl_auto_fix_safe")
    if importlib.util.find_spec("app.spl.spl_auto_fix_safe")
    else None
)

_Q04_OR_CHAIN_THRESHOLD = int(getattr(draft_quality, "_Q04_OR_CHAIN_THRESHOLD", 10))
classify_optimization = getattr(draft_quality, "classify_optimization", None)
_HAS_EFFICIENCY_ADVISORIES = hasattr(draft_quality, "_check_efficiency_advisories")
_HAS_EARLY_PROJECTION = "_early_projection" in inspect.getsource(llm_plan_compiler.compile_plan_to_spl)

Layer = Literal[
    "draft_quality",
    "classification",
    "compiler",
    "deterministic_rewrite",
    "rewrite_guard",
    "simplifier",
    "pending_llm",
]

Severity = Literal["hard_fail", "warning", "advisory", "gate", "transform", "pending"]

_OVERRIDES_PATH = Path(__file__).resolve().parent / "optimization_ui_overrides.json"
_REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CodeAnchor:
    module: str
    symbol: str
    line: int
    path: str

    @property
    def display(self) -> str:
        return f"{self.path}:{self.line}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "symbol": self.symbol,
            "line": self.line,
            "path": self.path,
            "display": self.display,
        }


@dataclass
class SplLogicEntry:
    logic_id: str
    layer: Layer
    phase: str
    rule_id: str | None
    title: str
    description: str
    severity: Severity
    runtime_active: bool
    ui_toggle_allowed: bool
    code: CodeAnchor
    triggers_classification: str | None = None
    rewrite_step: str | None = None
    guard_invariants: list[str] = field(default_factory=list)
    ui_enabled: bool = True
    ui_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "logic_id": self.logic_id,
            "layer": self.layer,
            "phase": self.phase,
            "rule_id": self.rule_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "runtime_active": self.runtime_active,
            "ui_toggle_allowed": self.ui_toggle_allowed,
            "code": self.code.to_dict(),
            "triggers_classification": self.triggers_classification,
            "rewrite_step": self.rewrite_step,
            "guard_invariants": self.guard_invariants,
            "ui_enabled": self.ui_enabled,
            "ui_note": self.ui_note,
        }


def _anchor(obj: Any, symbol: str) -> CodeAnchor:
    module = inspect.getmodule(obj)
    module_name = module.__name__ if module else "unknown"
    try:
        line = int(inspect.getsourcelines(obj)[1])
    except (OSError, TypeError):
        line = 0
    rel = Path(inspect.getfile(obj)).resolve()
    try:
        path = rel.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        path = rel.as_posix()
    return CodeAnchor(module=module_name, symbol=symbol, line=line, path=path)


def _static_anchor(path: str, symbol: str, line: int) -> CodeAnchor:
    module = path.replace("/", ".").replace("backend.", "").removesuffix(".py")
    return CodeAnchor(module=module, symbol=symbol, line=line, path=path)


def _load_ui_overrides() -> dict[str, dict[str, Any]]:
    if not _OVERRIDES_PATH.is_file():
        return {}
    try:
        raw = json.loads(_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    overrides = raw.get("overrides") if isinstance(raw, dict) else None
    return overrides if isinstance(overrides, dict) else {}


def save_ui_overrides(overrides: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cleaned: dict[str, dict[str, Any]] = {}
    for key, value in overrides.items():
        if not isinstance(value, dict):
            continue
        entry: dict[str, Any] = {"ui_enabled": bool(value.get("ui_enabled", True))}
        note = str(value.get("ui_note") or "").strip()
        if note:
            entry["ui_note"] = note[:500]
        cleaned[str(key)] = entry
    payload = {
        "schema_version": "spl_optimization_ui_overrides_v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "overrides": cleaned,
    }
    _OVERRIDES_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _apply_overrides(entries: list[SplLogicEntry]) -> None:
    overrides = _load_ui_overrides()
    for entry in entries:
        pref = overrides.get(entry.logic_id)
        if not isinstance(pref, dict):
            continue
        entry.ui_enabled = bool(pref.get("ui_enabled", True))
        entry.ui_note = str(pref.get("ui_note") or "")


def _draft_quality_entries() -> list[SplLogicEntry]:
    anchor_eval = _anchor(draft_quality.evaluate_draft_quality, "evaluate_draft_quality")
    anchor_eff = (
        _anchor(draft_quality._check_efficiency_advisories, "_check_efficiency_advisories")
        if _HAS_EFFICIENCY_ADVISORIES
        else _static_anchor("backend/app/spl/draft_quality.py", "_check_efficiency_advisories", 399)
    )
    anchor_shift = _anchor(draft_quality._check_shift_left, "_check_shift_left")
    anchor_time = _anchor(draft_quality._check_native_time, "_check_native_time")
    anchor_u03 = _anchor(draft_quality._check_stats_inclusion, "_check_stats_inclusion")

    specs: list[tuple[str, str, Severity, str, CodeAnchor, str | None, bool, bool]] = [
        ("Q01", "Quoted string newline / broken regex", "hard_fail", "Reject multiline or broken regex in quoted SPL.", anchor_eval, "SOC-STD-SPL-001-Q01", False, True),
        ("Q02", "Unescaped Windows path", "hard_fail", "Reject unescaped backslashes in quoted Windows paths.", anchor_eval, "SOC-STD-SPL-001-Q02", False, True),
        ("U02", "Native time without strftime", "hard_fail", "earliest(_time)/latest(_time) requires readable strftime after stats.", anchor_time, "SOC-STD-SPL-001-U02", False, True),
        ("U02-native", "strftime before aggregation advisory", "warning", "Event-level strftime without prior sort/aggregation warns.", anchor_time, "SOC-STD-SPL-001-U02", False, True),
        ("shift-left", "Family shift-left preprocessor", "warning", "Move static EventCode/action filters earlier when family map applies.", anchor_shift, None, False, True),
        ("U03", "Stats/table field inclusion", "hard_fail", "Final table columns must survive stats/streamstats (U03).", anchor_u03, "SOC-STD-SPL-001-U03", False, True),
        ("Q05", "Prohibited execution claims", "hard_fail", "Draft must not imply executed or governed SPL.", anchor_eval, "SOC-STD-SPL-001-Q05", False, True),
        ("Q06", "coalesce() normalization", "advisory", "Prefer coalesce() for multi-vendor field aliases when eval is used.", anchor_eval, "SOC-STD-SPL-001-Q06", True, True),
        ("Q07", "CIDR via IN()", "warning", "CIDR membership should use cidrmatch(), not IN().", anchor_eval, "SOC-STD-SPL-001-Q07", False, True),
        ("Q08", "Index/sourcetype placeholders", "advisory", "Base search should include index= and sourcetype=.", anchor_eval, "SOC-STD-SPL-001-Q08", True, True),
        ("Q09", "Static base filters", "advisory", "Base search should include EventCode/action/protocol filters when known.", anchor_eval, "SOC-STD-SPL-001-Q09", True, True),
        ("Q10", "Event 4740 caller host", "hard_fail", "4740 drafts must use caller_host_norm with governed coalesce.", anchor_eval, "SOC-STD-SPL-001-Q10", False, True),
        ("Q11", "sort 0 + _time before streamstats", "hard_fail", "Rolling streamstats requires explicit sort 0 + _time (correctness).", anchor_eval, "SOC-STD-SPL-001-Q11", False, True),
        ("Q12", "ESP fuzzy zone match", "warning", "ESP IT→OT zones should use exact IN() or cidrmatch().", anchor_eval, "SOC-STD-SPL-001-Q12", False, True),
        ("Q13", "ESP noisy wildcards / blank session", "hard_fail", "Family-scoped ESP hard fails — do not generalize.", anchor_eval, "SOC-STD-SPL-001-Q13", False, True),
        ("Q14", "Firewall session_state fuzzy", "hard_fail", "Firewall session_state_norm must use strict IN() only.", anchor_eval, "SOC-STD-SPL-001-Q14", False, True),
        ("Q03", "Broad NOT / !=", "advisory", "Prefer positive matches over broad NOT/!= in early search.", anchor_eff, "SOC-STD-SPL-001-Q03", True, _HAS_EFFICIENCY_ADVISORIES),
        ("Q04", "Same-field OR chain", "advisory", f"Same-field OR ≥{_Q04_OR_CHAIN_THRESHOLD} → prefer IN(); routes AUTO_FIX_SAFE.", anchor_eff, "SOC-STD-SPL-001-Q04", True, _HAS_EFFICIENCY_ADVISORIES),
        ("Q15", "TERM() minor-breaker candidate", "advisory", "Minor-breaker tokens may benefit from TERM() wrapping.", anchor_eff, "SOC-STD-SPL-001-Q15", True, _HAS_EFFICIENCY_ADVISORIES),
        ("Q16", "Leading wildcard term", "advisory", "Leading wildcards in search terms are expensive.", anchor_eff, "SOC-STD-SPL-001-Q16", True, _HAS_EFFICIENCY_ADVISORIES),
        ("Q17", "Non-streaming stage placement", "advisory", "Keep sort/stats late when equivalence holds; Q11 carve-out preserved.", anchor_eff, "SOC-STD-SPL-001-Q17", True, _HAS_EFFICIENCY_ADVISORIES),
        ("Q18", "Early projection opportunity", "advisory", "Project unused columns before first aggregation (U03 compatible).", anchor_eff, "SOC-STD-SPL-001-Q18", True, _HAS_EFFICIENCY_ADVISORIES),
    ]
    entries: list[SplLogicEntry] = []
    for suffix, title, severity, desc, code, rule_id, toggle, runtime in specs:
        entries.append(
            SplLogicEntry(
                logic_id=f"draft_quality.{suffix}",
                layer="draft_quality",
                phase="S1+legacy" if runtime else "S1 (ws/spl-optimization)",
                rule_id=rule_id,
                title=title,
                description=desc if runtime else f"{desc} Not deployed in this tree — see ws/spl-optimization.",
                severity=severity,
                runtime_active=runtime,
                ui_toggle_allowed=toggle,
                code=code,
                triggers_classification=(
                    "OPTIMIZATION_LLM_REQUIRED"
                    if suffix in {"Q03", "Q15", "Q16", "Q17", "Q18"}
                    else ("AUTO_FIX_SAFE" if suffix == "Q04" else None)
                ),
            )
        )
    return entries


def _classification_entries() -> list[SplLogicEntry]:
    if classify_optimization is not None:
        anchor = _anchor(classify_optimization, "classify_optimization")
        runtime = True
        phase = "S1"
    else:
        anchor = _anchor(draft_quality.evaluate_draft_quality, "evaluate_draft_quality")
        runtime = False
        phase = "S1 (ws/spl-optimization)"
    classes = [
        ("PASS", "No efficiency advisories — retain candidate."),
        ("AUTO_FIX_SAFE", "Q04-only or Q04-mixed — deterministic OR→IN rewrite eligible."),
        ("OPTIMIZATION_LLM_REQUIRED", "Efficiency gap needs bounded optimization LLM (S6 pending)."),
        ("NO_SAFE_OPTIMIZATION", "Advisories present but no safe deterministic or LLM path."),
    ]
    return [
        SplLogicEntry(
            logic_id=f"classification.{name.lower()}",
            layer="classification",
            phase=phase,
            rule_id=None,
            title=f"Route: {name}",
            description=desc,
            severity="gate",
            runtime_active=runtime,
            ui_toggle_allowed=False,
            code=anchor,
            triggers_classification=name,
        )
        for name, desc in classes
    ]


def _compiler_entries() -> list[SplLogicEntry]:
    anchor = _anchor(llm_plan_compiler.compile_plan_to_spl, "compile_plan_to_spl")
    return [
        SplLogicEntry(
            logic_id="compiler.selective_base_filters",
            layer="compiler",
            phase="S3",
            rule_id=None,
            title="Selective filters in base search",
            description="Emit index, sourcetype, time scope, and plan filters before the first pipe.",
            severity="transform",
            runtime_active=True,
            ui_toggle_allowed=False,
            code=anchor,
        ),
        SplLogicEntry(
            logic_id="compiler.early_field_projection",
            layer="compiler",
            phase="S3" if _HAS_EARLY_PROJECTION else "S3 (ws/spl-optimization)",
            rule_id=None,
            title="Early | fields projection",
            description=(
                "Project proven-safe columns before aggregation/timechart/streamstats."
                if _HAS_EARLY_PROJECTION
                else "Project proven-safe columns before aggregation — not deployed in this tree."
            ),
            severity="transform",
            runtime_active=_HAS_EARLY_PROJECTION,
            ui_toggle_allowed=False,
            code=anchor,
            rewrite_step="early_projection",
        ),
        SplLogicEntry(
            logic_id="compiler.q11_sort_before_streamstats",
            layer="compiler",
            phase="S3",
            rule_id="SOC-STD-SPL-001-Q11",
            title="Preserve sort 0 + _time before streamstats",
            description="Correctness invariant — never optimized away.",
            severity="hard_fail",
            runtime_active=True,
            ui_toggle_allowed=False,
            code=anchor,
        ),
    ]


def _rewrite_entries() -> list[SplLogicEntry]:
    if spl_auto_fix_safe is not None:
        anchor_apply = _anchor(spl_auto_fix_safe.apply_auto_fix_safe, "apply_auto_fix_safe")
        anchor_or = _anchor(spl_auto_fix_safe.rewrite_same_field_or_to_in, "rewrite_same_field_or_to_in")
        runtime = True
        phase = "S4"
    else:
        anchor_apply = _static_anchor("backend/app/spl/spl_auto_fix_safe.py", "apply_auto_fix_safe", 83)
        anchor_or = _static_anchor("backend/app/spl/spl_auto_fix_safe.py", "rewrite_same_field_or_to_in", 67)
        runtime = False
        phase = "S4 (ws/spl-optimization)"
    return [
        SplLogicEntry(
            logic_id="rewrite.auto_fix_safe_gate",
            layer="deterministic_rewrite",
            phase=phase,
            rule_id=None,
            title="AUTO_FIX_SAFE apply gate",
            description="Runs only when classification is AUTO_FIX_SAFE; retains v1 on rewrite_guard FAIL.",
            severity="gate",
            runtime_active=runtime,
            ui_toggle_allowed=False,
            code=anchor_apply,
        ),
        SplLogicEntry(
            logic_id="rewrite.or_chain_to_in",
            layer="deterministic_rewrite",
            phase=phase,
            rule_id="SOC-STD-SPL-001-Q04",
            title="Same-field OR → IN()",
            description=f"Exact values only (threshold {_Q04_OR_CHAIN_THRESHOLD}); never invent IN members.",
            severity="transform",
            runtime_active=runtime,
            ui_toggle_allowed=True,
            code=anchor_or,
            rewrite_step="or_chain_to_in",
        ),
    ]


def _guard_entries() -> list[SplLogicEntry]:
    invariants = [
        "index",
        "sourcetype",
        "time_scope_earliest",
        "time_scope_latest",
        "result_limit",
        "aggregation_meaning",
        "governed_filters",
        "semantic_fidelity",
    ]
    if rewrite_guard is not None:
        anchor = _anchor(rewrite_guard.assert_rewrite_preserves, "assert_rewrite_preserves")
        runtime = True
        phase = "S2"
    else:
        anchor = _static_anchor("backend/app/spl/rewrite_guard.py", "assert_rewrite_preserves", 41)
        runtime = False
        phase = "S2 (ws/spl-optimization)"
    return [
        SplLogicEntry(
            logic_id="rewrite_guard.assert_rewrite_preserves",
            layer="rewrite_guard",
            phase=phase,
            rule_id=None,
            title="V1→V2 rewrite guard",
            description="Composes structural invariants, RQC preservation, and optional semantic fidelity.",
            severity="gate",
            runtime_active=runtime,
            ui_toggle_allowed=False,
            code=anchor,
            guard_invariants=invariants,
        )
    ]


def _simplifier_entries() -> list[SplLogicEntry]:
    anchor = _anchor(spl_simplifier.simplify_spl, "simplify_spl")
    steps = [
        ("normalize_whitespace", "Collapse redundant whitespace."),
        ("drop_table_before_stats", "Remove table stages that precede stats."),
        ("drop_redundant_smb_where", "Drop redundant SMB where clause when base search already scopes SMB."),
        ("convert_post_stats_search_to_where", "Rewrite post-stats search to where when safe."),
        ("append_default_time_bounds", "Append default earliest/latest when absent."),
        ("append_head_after_sort", "Append head 100 after sort when missing."),
        ("append_head_after_stats", "Append head 100 after stats when missing."),
    ]
    return [
        SplLogicEntry(
            logic_id=f"simplifier.{step}",
            layer="simplifier",
            phase="legacy",
            rule_id=None,
            title=step.replace("_", " "),
            description=desc,
            severity="transform",
            runtime_active=True,
            ui_toggle_allowed=True,
            code=anchor,
            rewrite_step=step,
        )
        for step, desc in steps
    ]


def _pending_llm_entries() -> list[SplLogicEntry]:
    return [
        SplLogicEntry(
            logic_id="pending.generation_prompt",
            layer="pending_llm",
            phase="S5",
            rule_id=None,
            title="Free-text generation prompt guidance",
            description="llm_fallback.py efficiency guidance — pending live /llm-live-probe.",
            severity="pending",
            runtime_active=False,
            ui_toggle_allowed=False,
            code=CodeAnchor("app.spl.llm_fallback", "llm_fallback", 697, "backend/app/spl/llm_fallback.py"),
        ),
        SplLogicEntry(
            logic_id="pending.optimization_llm",
            layer="pending_llm",
            phase="S6",
            rule_id=None,
            title="Bounded optimization LLM (one call)",
            description="OPTIMIZED or NO_SAFE_OPTIMIZATION — not wired; probe before wiring.",
            severity="pending",
            runtime_active=False,
            ui_toggle_allowed=False,
            code=CodeAnchor("app.spl", "optimization_llm", 0, "backend/app/spl/"),
        ),
        SplLogicEntry(
            logic_id="pending.sticky_lineage_pipeline",
            layer="pending_llm",
            phase="S7",
            rule_id=None,
            title="Sticky LLM lineage + classify_llm_spl_risk",
            description="Protected pipeline.py packet deferred until S6 live gate passes.",
            severity="pending",
            runtime_active=False,
            ui_toggle_allowed=False,
            code=CodeAnchor("app.chat.pipeline", "pipeline", 3555, "backend/app/chat/pipeline.py"),
        ),
    ]


def _deployment_flags() -> dict[str, bool]:
    return {
        "efficiency_advisories_s1": _HAS_EFFICIENCY_ADVISORIES,
        "classify_optimization_s1": classify_optimization is not None,
        "rewrite_guard_s2": rewrite_guard is not None,
        "auto_fix_safe_s4": spl_auto_fix_safe is not None,
        "compiler_early_projection_s3": _HAS_EARLY_PROJECTION,
    }


def build_spl_optimization_registry() -> dict[str, Any]:
    entries: list[SplLogicEntry] = []
    entries.extend(_draft_quality_entries())
    entries.extend(_classification_entries())
    entries.extend(_compiler_entries())
    entries.extend(_rewrite_entries())
    entries.extend(_guard_entries())
    entries.extend(_simplifier_entries())
    entries.extend(_pending_llm_entries())
    _apply_overrides(entries)

    by_layer: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_layer.setdefault(entry.layer, []).append(entry.to_dict())

    deployed = _deployment_flags()
    runtime_count = sum(1 for e in entries if e.runtime_active)

    return {
        "schema_version": "spl_optimization_registry_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deployment": deployed,
        "phase_status": {
            "deterministic_spine": "ACCEPTED" if all(deployed[k] for k in ("rewrite_guard_s2", "auto_fix_safe_s4", "efficiency_advisories_s1")) else "PARTIAL_IN_THIS_TREE",
            "llm_spine": "PENDING_LIVE_VALIDATION",
            "s9a_head": "dd71393f2fe2d89b7d25258b3da3bb4e0d4ceecb",
            "full_implementation_branch": "ws/spl-optimization",
        },
        "ui_toggle_policy": (
            "UI enable/disable is preference-only. runtime_active reflects code deployed in this tree; "
            "disabling in UI does not yet skip runtime execution."
        ),
        "q04_or_chain_threshold": _Q04_OR_CHAIN_THRESHOLD,
        "entry_count": len(entries),
        "runtime_active_count": runtime_count,
        "layers": by_layer,
        "entries": [entry.to_dict() for entry in entries],
    }
