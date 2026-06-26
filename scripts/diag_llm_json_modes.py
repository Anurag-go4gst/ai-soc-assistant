#!/usr/bin/env python3
"""Diagnose how the on-host llama-server returns JSON for the SPL producer prompt.

Captures the RAW model output (to see the exact malformation) and tests which
constraint the server actually honors:
  1. plain            (no constraint)
  2. response_format json_object
  3. response_format json_schema   (llama.cpp strong mode)
  4. grammar (GBNF)                (llama.cpp native)

Prints, per mode: finish_reason, predicted tokens, whether content is valid JSON,
and a raw excerpt. One call per mode (single-slot 8B is slow).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "backend", REPO_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.spl.llm_fallback import _system_prompt, _user_prompt  # noqa: E402

BASE = "http://127.0.0.1:8081/v1/chat/completions"
MODEL = "foundation-sec-1.1-8b-instruct-q8_0.gguf"
QUERY = "Detect Modbus/TCP write commands sent to boiler-control PLCs from hosts other than the approved engineering workstation."

# Minimal GBNF that constrains output to a JSON object.
JSON_GBNF = r"""
root   ::= object
value  ::= object | array | string | number | ("true" | "false" | "null")
object ::= "{" ws (string ":" ws value ("," ws string ":" ws value)*)? "}" ws
array  ::= "[" ws (value ("," ws value)*)? "]" ws
string ::= "\"" ([^"\\] | "\\" .)* "\""
number ::= "-"? [0-9]+ ("." [0-9]+)? ([eE] [-+]? [0-9]+)?
ws     ::= [ \t\n]*
"""

SPL_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "confidence_score": {"type": "number"},
        "confidence_label": {"type": "string"},
        "detection_family": {"type": "string"},
        "candidate_spl": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "required_fields": {"type": "array", "items": {"type": "string"}},
        "missing_details": {"type": "array", "items": {"type": "string"}},
        "clarifying_questions": {"type": "array", "items": {"type": "string"}},
        "validation_notes": {"type": "array", "items": {"type": "string"}},
        "soc_std_rules_applied": {"type": "array", "items": {"type": "string"}},
        "risk_notes": {"type": "array", "items": {"type": "string"}},
        "execution_eligible": {"type": "boolean"},
        "governed": {"type": "boolean"},
        "catalog_approved": {"type": "boolean"},
    },
    "required": ["status", "candidate_spl", "execution_eligible", "governed", "catalog_approved"],
}


def _call(extra: dict, timeout: int = 200) -> dict:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(QUERY)},
        ],
        "max_tokens": 512,
        "temperature": 0.0,
        "stream": False,
        **extra,
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read())
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}", "wall_s": round(time.monotonic() - started, 1)}
    wall = round(time.monotonic() - started, 1)
    choice = (payload.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    timings = payload.get("timings") or {}
    valid = True
    err = None
    try:
        json.loads(content)
    except Exception as exc:  # noqa: BLE001
        valid = False
        err = str(exc)
    return {
        "finish_reason": choice.get("finish_reason"),
        "predicted_n": timings.get("predicted_n"),
        "tok_per_s": round(timings.get("predicted_per_second", 0) or 0, 2),
        "content_valid_json": valid,
        "json_error": err,
        "content_excerpt": content[:400],
        "wall_s": wall,
    }


def main() -> int:
    modes = {
        "plain": {},
        "json_object": {"response_format": {"type": "json_object"}},
        "json_schema": {"response_format": {"type": "json_schema", "json_schema": {"name": "spl", "schema": SPL_JSON_SCHEMA}}},
        "grammar": {"grammar": JSON_GBNF},
    }
    out: dict = {}
    for name, extra in modes.items():
        out[name] = _call(extra)
        print(f"== {name} ==")
        print(json.dumps(out[name], indent=2))
    (REPO_ROOT / "docs" / "evals" / "diag_llm_json_modes.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
