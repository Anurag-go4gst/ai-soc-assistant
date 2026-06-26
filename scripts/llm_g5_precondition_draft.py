#!/usr/bin/env python3
"""LLM-assisted G5 evidence-precondition DRAFTER (plan §15 G5, advisory).

For each G5-promoted technique, ask the local Foundation-Sec Instruct model to
propose a positive-evidence key (from a fixed allowed vocabulary) plus candidate /
confirmed detection rules, grounded in the ATT&CK xlsx name + description. The
LLM is ADVISORY ONLY:

  - it never picks authority — a deterministic validator checks the proposed key
    against the allowed vocabulary and flags off-vocab proposals;
  - output is a COE-review artifact (docs/evals/g5_precondition_drafts.{json,md});
  - this script NEVER writes mitre_attack_subset.json or the preconditions module.

Live LLM is required and gated: pass --live (or AI_SOC_TESTS_ALLOW_LIVE_LLM=1).
Offline/CI runs are a no-op so the suite never hits the slow single-slot model.

Usage:
  AI_SOC_TESTS_ALLOW_LIVE_LLM=1 PYTHONPATH=backend:. \
    python3 scripts/llm_g5_precondition_draft.py --live [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

SUBSET = ROOT / "backend" / "app" / "threat" / "mitre_attack_subset.json"
OUT_DIR = ROOT / "docs" / "evals"
_G5_PROVENANCE = "mitre_audit_v19.1_promote_g5"
LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"
LLM_MODEL = "foundation-sec-1.1-8b-instruct-q8_0.gguf"

# Allowed positive-evidence vocabulary (tactic-level keys + curated specifics).
# Mirror app.threat.mitre_evidence_preconditions.TACTIC_EVIDENCE + explicit keys.
ALLOWED_KEYS = {
    "recon_evidence", "resource_development_evidence", "initial_access_evidence",
    "process_execution_evidence", "persistence_evidence", "privilege_escalation_evidence",
    "defense_evasion_evidence", "credential_access_evidence", "discovery_evidence",
    "lateral_movement_evidence", "collection_evidence", "network_telemetry",
    "outbound_transfer", "impact_evidence",
    # curated specifics already in PRECONDITIONS:
    "successful_login", "credential_dumping_evidence", "endpoint_telemetry",
}


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _promoted_techniques() -> list[dict]:
    """The G5-promoted techniques, read from the subset by provenance stamp (they are
    already in-bundle, so the expansion artifact no longer lists them as candidates)."""
    payload = json.loads(SUBSET.read_text(encoding="utf-8"))
    out = []
    for t in payload.get("techniques", []):
        if not isinstance(t, dict) or t.get("candidate_provenance") != _G5_PROVENANCE:
            continue
        out.append({
            "technique_id": t.get("technique_id", ""),
            "name": t.get("name", ""),
            "tactic": t.get("tactic", ""),
            "description": (t.get("description") or "")[:600],
        })
    return out


_KEY_GLOSSARY = (
    "recon_evidence=reconnaissance/scanning; resource_development_evidence=adversary infra/tooling prep; "
    "initial_access_evidence=entry vector (phishing/exploit/valid-account entry); "
    "process_execution_evidence=process/command/script execution; persistence_evidence=persistence mechanism "
    "(autorun/service/task/account); privilege_escalation_evidence=privilege gain; "
    "defense_evasion_evidence=evasion/obfuscation/log-tamper/tool-disable; credential_access_evidence=credential "
    "theft/dumping/access; discovery_evidence=enumeration of hosts/accounts/services; "
    "lateral_movement_evidence=movement between hosts; collection_evidence=data staging/collection; "
    "network_telemetry=command-and-control/network comms; outbound_transfer=data leaving the network "
    "(exfiltration); impact_evidence=destruction/encryption/disruption; successful_login=confirmed successful auth; "
    "credential_dumping_evidence=OS credential dump (LSASS/SAM/NTDS); endpoint_telemetry=EDR/host telemetry present"
)
# Few-shot anchors (techniques NOT in the promotion set, so no answer leakage).
_FEWSHOT = (
    'Examples:\n'
    'Input: T1041 Exfiltration Over C2 Channel [Exfiltration] — data sent over the existing C2 channel.\n'
    'Output: {"evidence_key":"outbound_transfer","candidate_rule":"Outbound data volume to a C2 destination '
    'exceeds baseline.","confirmed_rule":"Outbound transfer correlated to an established C2 channel and staged data."}\n'
    'Input: T1110 Brute Force [Credential Access] — repeated authentication attempts to guess credentials.\n'
    'Output: {"evidence_key":"credential_access_evidence","candidate_rule":"High volume of authentication failures '
    'from a source.","confirmed_rule":"Failure burst followed by a successful login from the same source."}\n'
)


def _draft_one(tech: dict, timeout: float) -> dict:
    prompt = (
        "You are a SOC detection engineer mapping a MITRE ATT&CK technique to ONE positive-evidence key — the "
        "signal a SOC finding must carry before the technique can be claimed (candidate-tier; conservative).\n\n"
        f"Allowed keys (pick exactly one, verbatim):\n{_KEY_GLOSSARY}\n\n"
        f"{_FEWSHOT}\n"
        f"Now classify:\nInput: {tech['technique_id']} {tech['name']} [{tech['tactic']}] — {tech['description']}\n"
        'Output ONLY a JSON object, no prose, no markdown fences: '
        '{"evidence_key":"<one key from the list>","candidate_rule":"<one sentence, the minimal suspicious '
        'signal>","confirmed_rule":"<one sentence, what raises it to confirmed>"}'
    )
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 320, "temperature": 0.0,
    }).encode()
    t0 = time.time()
    req = urllib.request.Request(LLM_URL, data=body, headers={"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=timeout).read())["choices"][0]["message"]["content"]
    dt = time.time() - t0
    parsed, parse_status = _parse(raw)
    key = str(parsed.get("evidence_key") or "").strip()
    validation = "valid" if key in ALLOWED_KEYS else ("off_vocab" if key else "no_key")
    return {
        "technique_id": tech["technique_id"], "name": tech["name"], "tactic": tech["tactic"],
        "proposed_evidence_key": key, "validation": validation,
        "candidate_rule": str(parsed.get("candidate_rule") or "").strip(),
        "confirmed_rule": str(parsed.get("confirmed_rule") or "").strip(),
        "parse_status": parse_status, "latency_s": round(dt, 1),
    }


def _parse(raw: str) -> tuple[dict, str]:
    text = _strip_fences(raw)
    try:
        return json.loads(text), "valid"
    except json.JSONDecodeError:
        # tolerant: pull the first {...} block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0)), "repaired"
            except json.JSONDecodeError:
                pass
    return {}, "unparseable"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="actually call the local Instruct model")
    ap.add_argument("--limit", type=int, default=0, help="only draft the first N techniques (smoke)")
    ap.add_argument("--timeout", type=float, default=150.0)
    args = ap.parse_args()

    if not (args.live or os.environ.get("AI_SOC_TESTS_ALLOW_LIVE_LLM") == "1"):
        print("SKIP: live LLM not enabled (pass --live or AI_SOC_TESTS_ALLOW_LIVE_LLM=1). No artifact written.")
        return 0

    techs = _promoted_techniques()
    if args.limit:
        techs = techs[: args.limit]
    rows: list[dict] = []
    for i, tech in enumerate(techs, 1):
        try:
            row = _draft_one(tech, args.timeout)
        except Exception as exc:  # noqa: BLE001 - one bad call must not lose the batch
            row = {"technique_id": tech["technique_id"], "name": tech["name"], "tactic": tech["tactic"],
                   "proposed_evidence_key": "", "validation": "llm_error", "candidate_rule": "",
                   "confirmed_rule": "", "parse_status": f"error:{exc}", "latency_s": None}
        rows.append(row)
        print(f"[{i}/{len(techs)}] {row['technique_id']:12} {row['validation']:9} key={row['proposed_evidence_key']}")

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["validation"]] = counts.get(r["validation"], 0) + 1
    report = {
        "schema_role": "g5_precondition_drafts_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "advisory_only": True,
        "authority": "deterministic — these are LLM proposals for COE review; NOT applied to "
                     "mitre_attack_subset.json or mitre_evidence_preconditions.py by this script",
        "model": LLM_MODEL,
        "technique_count": len(rows),
        "validation_counts": counts,
        "drafts": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "g5_precondition_drafts.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _write_md(report)
    print(f"\nWrote {len(rows)} drafts; validation={counts} -> docs/evals/g5_precondition_drafts.{{json,md}}")
    return 0


def _write_md(report: dict) -> None:
    lines = [
        "# G5 evidence-precondition drafts (LLM-assisted, COE review)",
        "",
        f"- Generated: `{report['generated_at_utc']}`  Model: `{report['model']}`",
        f"- Techniques: **{report['technique_count']}**  Validation: "
        + ", ".join(f"`{k}`={v}" for k, v in sorted(report["validation_counts"].items())),
        "",
        f"> {report['authority']}",
        "",
        "| techniqueID | tactic | proposed_key | validation | candidate_rule |",
        "|---|---|---|---|---|",
    ]
    for r in report["drafts"]:
        cand = (r["candidate_rule"] or "").replace("|", "\\|")[:90]
        lines.append(f"| `{r['technique_id']}` | {r['tactic']} | `{r['proposed_evidence_key']}` "
                     f"| {r['validation']} | {cand} |")
    lines.append("")
    (OUT_DIR / "g5_precondition_drafts.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
