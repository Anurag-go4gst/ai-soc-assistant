"""Phase A relevance baseline — does generated SPL answer the asked question?

Headline metric for the SPL Generation Audit (relevance-first). For every
question we resolve the SPL the analyst would see (governed template lane or
lab draft lane), then score *relevance* structurally: does the SPL's data
source, aggregation/metric, entity, and action match what the question asks?

This is the deterministic structural half of the future `spl_relevance_check`
gate (Phase C). It runs NO LLM and changes NO app behavior — it only reads the
existing generators (`build_draft_preview`, governed `templates.json`).

Two corpora, reported separately (never a double-counted /151):
  - 105 canonical questions (app/coverage/question_runtime_map_v1.json)
  - catalogue rows (app/use_cases/catalog.json); overlap with 105 is flagged.

Usage:
    PYTHONPATH=backend:. python3 scripts/eval_spl_relevance.py
    PYTHONPATH=backend:. python3 scripts/eval_spl_relevance.py --check   # gate
    PYTHONPATH=backend:. python3 scripts/eval_spl_relevance.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Force the draft-preview lane on for measurement only (no persistence, no app run).
os.environ.setdefault("AI_SOC_SPL_DRAFT_PREVIEW_ENABLED", "true")

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
MAP_PATH = BACKEND / "app" / "coverage" / "question_runtime_map_v1.json"
CATALOG_PATH = BACKEND / "app" / "use_cases" / "catalog.json"
TEMPLATES_PATH = BACKEND / "app" / "spl" / "templates.json"
REPORT_JSON = ROOT / "docs" / "evals" / "spl_relevance_report.json"
REPORT_MD = ROOT / "docs" / "evals" / "spl_relevance_summary.md"

import app.chat  # noqa: E402,F401  — warm the package to resolve the draft_preview import cycle
from app.spl.draft_preview import build_draft_preview  # noqa: E402


# --- Data-source signatures -------------------------------------------------
# Map a logical data source to (question keywords, SPL body tokens). Relevance
# requires the SPL body to carry tokens of the source the question asks about.
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


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _expected_sources(qtext: str, required_sources: list[str] | None) -> set[str]:
    q = _norm(qtext)
    found = {src for src, sig in DATA_SOURCES.items() if any(kw in q for kw in sig["q"])}
    # mcp:splunk is generic; do not infer a source from it. Keyword evidence only.
    return found


def _spl_has_source(spl: str, source: str) -> bool:
    body = spl.lower()
    return any(tok in body for tok in DATA_SOURCES[source]["spl"])


def score_relevance(
    qtext: str,
    spl: str | None,
    *,
    pattern_type: str | None = None,
    required_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Structural relevance score for one (question, SPL) pair.

    Returns relevant bool + mismatch list. A missing SPL is not relevant unless
    the question legitimately needs none (handled by caller via pattern_type).
    """
    mismatches: list[str] = []
    if not spl:
        return {"relevant": False, "mismatches": ["no_spl_generated"], "checks": {}}

    q = _norm(qtext)
    checks: dict[str, Any] = {}

    # 1. Data source: every source the question names must appear in the SPL body.
    expected = _expected_sources(qtext, required_sources)
    checks["expected_sources"] = sorted(expected)
    src_ok = True
    if expected:
        missing = {s for s in expected if not _spl_has_source(spl, s)}
        if missing:
            src_ok = False
            mismatches.append(f"data_source_missing:{','.join(sorted(missing))}")
    checks["data_source_ok"] = src_ok

    # 2. Metric/aggregation: ranked/counted questions must aggregate.
    wants_metric = any(kw in q for kw in METRIC_Q)
    has_agg = any(tok in spl.lower() for tok in AGG_SPL)
    checks["wants_metric"] = wants_metric
    checks["has_aggregation"] = has_agg
    metric_ok = (not wants_metric) or has_agg
    if not metric_ok:
        mismatches.append("aggregation_missing")

    # 3. Entity: at least one asked entity must surface in the SPL.
    asked_entities = {e for e, toks in ENTITY_TOKENS.items() if any(t in q for t in toks)}
    checks["asked_entities"] = sorted(asked_entities)
    entity_ok = True
    if asked_entities:
        entity_ok = any(
            any(t in spl.lower() for t in ([e] + ENTITY_TOKENS[e])) for e in asked_entities
        )
        if not entity_ok:
            mismatches.append("entity_missing")
    checks["entity_ok"] = entity_ok

    # Relevant = source + metric + entity all satisfied.
    relevant = src_ok and metric_ok and entity_ok
    return {"relevant": relevant, "mismatches": mismatches, "checks": checks}


# --- SPL resolution per lane ------------------------------------------------
def _load_active_templates() -> dict[str, str]:
    data = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))["templates"]
    out: dict[str, str] = {}
    for t in data:
        if t.get("status") == "active" and t.get("spl_text"):
            out[t.get("use_case_id") or t.get("template_id")] = t["spl_text"]
    return out


def resolve_spl_for_query(
    qtext: str,
    *,
    pattern_type: str | None = None,
    use_case_id: str | None = None,
    default_spl_template: str | None = None,
    active_templates: dict[str, str] | None = None,
) -> tuple[str | None, str]:
    """Return (spl_text, lane). Lane in {template, draft, none}."""
    active = active_templates or {}
    # Governed template lane (catalogue rows that bind an active template).
    for key in (default_spl_template, use_case_id):
        if key and key in active:
            return active[key], "template"
    # Lab draft lane.
    draft = build_draft_preview(qtext, pattern_type=pattern_type)
    if draft and draft.get("draft_spl"):
        return draft["draft_spl"], "draft"
    return None, "none"


def _eval_105(active: dict[str, str]) -> list[dict[str, Any]]:
    entries = json.loads(MAP_PATH.read_text(encoding="utf-8"))["entries"]
    rows: list[dict[str, Any]] = []
    for e in entries:
        q = str(e["question"])
        pt = e.get("pattern_type")
        spl, lane = resolve_spl_for_query(q, pattern_type=pt, active_templates=active)
        score = score_relevance(q, spl, pattern_type=pt)
        rows.append({
            "corpus": "105",
            "ref": e["question_ref"],
            "question": q,
            "pattern_type": pt,
            "lane": lane,
            "relevant": score["relevant"],
            "mismatches": score["mismatches"],
            "checks": score["checks"],
        })
    return rows


# Skills that answer with knowledge / workflow output, not a detection SPL.
# Rows in these classes legitimately produce no SPL — they must not count
# against catalogue coverage (otherwise the % understates reality).
NON_SPL_SKILLS = {
    "knowledge_recall", "mitre_mapping", "investigation_notes",
    "ticket_drafting", "action_planning", "alert_summary",
}


def classify_catalogue_row(r: dict[str, Any]) -> str:
    """spl_expected | justified_no_spl | deferred."""
    uid = (r.get("use_case_id") or r.get("id") or "")
    category = (r.get("category") or "").lower()
    skill = r.get("primary_skill")
    if "later" in category:  # OT rows explicitly marked "later"
        return "deferred"
    if uid.startswith("soc_") or skill in NON_SPL_SKILLS:
        return "justified_no_spl"
    return "spl_expected"


def _eval_catalogue(active: dict[str, str]) -> list[dict[str, Any]]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    cat = data if isinstance(data, list) else data.get("use_cases") or list(data.values())
    rows: list[dict[str, Any]] = []
    for r in cat:
        uid = r.get("use_case_id") or r.get("id")
        examples = r.get("example_queries") or []
        q = examples[0] if examples else (r.get("display_name") or uid)
        row_class = classify_catalogue_row(r)
        spl, lane = resolve_spl_for_query(
            q,
            use_case_id=uid,
            default_spl_template=r.get("default_spl_template"),
            active_templates=active,
        )
        score = score_relevance(q, spl, required_sources=r.get("required_sources"))
        rows.append({
            "corpus": "catalogue",
            "ref": uid,
            "question": q,
            "pattern_type": r.get("category"),
            "row_class": row_class,
            "lane": lane,
            # justified/deferred rows are "correctly handled" regardless of SPL.
            "relevant": score["relevant"] if row_class == "spl_expected" else True,
            "mismatches": score["mismatches"] if row_class == "spl_expected" else [],
            "checks": score["checks"],
        })
    return rows


def _summary(rows: list[dict[str, Any]], corpus: str) -> dict[str, Any]:
    sub = [r for r in rows if r["corpus"] == corpus]
    # For catalogue, the coverage denominator is the SPL-expected rows only;
    # justified-no-SPL and deferred rows are excluded from the %.
    if corpus == "catalogue":
        scored = [r for r in sub if r.get("row_class") == "spl_expected"]
        classes = Counter(r.get("row_class") for r in sub)
    else:
        scored = sub
        classes = {}
    n = len(scored)
    relevant = sum(1 for r in scored if r["relevant"])
    lanes = Counter(r["lane"] for r in scored)
    mism = Counter(m for r in scored for m in r["mismatches"])
    return {
        "n": n,
        "relevant": relevant,
        "relevant_pct": round(100 * relevant / n, 1) if n else 0.0,
        "lanes": dict(lanes),
        "classes": dict(classes),
        "top_mismatches": dict(mism.most_common(8)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if relevance regresses below recorded floor")
    parser.add_argument("--json", type=Path, default=REPORT_JSON,
                        help="write per-row results JSON")
    parser.add_argument("--floor-105", type=int, default=0,
                        help="minimum relevant/105 for --check")
    parser.add_argument("--floor-catalogue", type=int, default=0,
                        help="minimum relevant/catalogue for --check")
    args = parser.parse_args()

    active = _load_active_templates()
    rows = _eval_105(active) + _eval_catalogue(active)

    s105 = _summary(rows, "105")
    scat = _summary(rows, "catalogue")

    report = {
        "active_templates": sorted(active.keys()),
        "summary": {"105": s105, "catalogue": scat},
        "rows": rows,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_md(report)

    print("SPL RELEVANCE BASELINE")
    print(f"  105 canonical : {s105['relevant']}/{s105['n']} relevant "
          f"({s105['relevant_pct']}%)  lanes={s105['lanes']}")
    print(f"  catalogue     : {scat['relevant']}/{scat['n']} spl-expected relevant "
          f"({scat['relevant_pct']}%)  classes={scat['classes']}  lanes={scat['lanes']}")
    print(f"  105 top mismatches      : {s105['top_mismatches']}")
    print(f"  catalogue top mismatches: {scat['top_mismatches']}")
    print(f"  report: {args.json}")

    if args.check:
        bad = []
        if s105["relevant"] < args.floor_105:
            bad.append(f"105 {s105['relevant']} < floor {args.floor_105}")
        if scat["relevant"] < args.floor_catalogue:
            bad.append(f"catalogue {scat['relevant']} < floor {args.floor_catalogue}")
        if bad:
            print("RESULT: FAIL (" + "; ".join(bad) + ")")
            return 1
        print("RESULT: PASS")
    return 0


def _write_md(report: dict[str, Any]) -> None:
    s = report["summary"]
    lines = [
        "# SPL Relevance Baseline (Phase A)",
        "",
        "Deterministic structural relevance — does generated SPL match the asked",
        "data source, metric/aggregation, and entity? No LLM, no app behavior change.",
        "",
        "| Corpus | Relevant | Total | % | Lanes |",
        "|--------|----------|-------|---|-------|",
        f"| 105 canonical | {s['105']['relevant']} | {s['105']['n']} | {s['105']['relevant_pct']} | {s['105']['lanes']} |",
        f"| Catalogue (spl-expected) | {s['catalogue']['relevant']} | {s['catalogue']['n']} | {s['catalogue']['relevant_pct']} | {s['catalogue']['lanes']} |",
        "",
        f"Catalogue row classes: {s['catalogue']['classes']} — `justified_no_spl`",
        "(analyst-workflow / knowledge skills) and `deferred` (OT \"later\") are",
        "excluded from the coverage denominator; they are correctly handled without SPL.",
        "",
        "> Corpora reported separately by design — 105 (pattern_type keyspace) and",
        "> catalogue (use_case_id keyspace) overlap; a combined /151 would double-count.",
        "",
        "## Top mismatch reasons",
        "",
        f"- **105**: {s['105']['top_mismatches']}",
        f"- **Catalogue**: {s['catalogue']['top_mismatches']}",
        "",
        "## Method (caveat)",
        "",
        "SPL resolved via the real generators (`build_draft_preview` + active",
        "`templates.json`), not a full `/chat` boot. Lane `none` = no SPL surfaced.",
        "Relevance is structural (source/metric/entity); the Phase C gate adds LLM",
        "self-critique. Numbers are a floor to beat in Phases B–D, not a grade.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
