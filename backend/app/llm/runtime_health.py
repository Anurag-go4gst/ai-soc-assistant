"""Live LLM runtime health — real generation-throughput probe for the UI/API.

Unlike ``/settings/llm/health`` (reachability-only ``/v1/models`` ping), this streams
a tiny completion and measures the actual generation rate from inter-token timing, so
a slow-but-alive model on a contended host reports its TRUE low tok/s instead of a
false 0.0. A timeout returns ``tok_per_s: None`` (UNKNOWN), never confused with 0.0.

Mirrors the classification in ``scripts/llm_health_guard.py`` so the UI button and the
host health-guard agree on what "degraded" means.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from app.config import settings

# Stream-measure from the first few tokens so a ~1 tok/s model reports fast.
_STREAM_SAMPLE_TOKENS = 12
_PROBE_MAX_TOKENS = 16
_DEFAULT_THRESHOLD = 2.0  # tok/s
_DEFAULT_MAX_PROMPT_EVAL_S = 20.0


def _base_url() -> str:
    raw = (settings.ai_soc_llm_local_base_url or "").strip().rstrip("/")
    return raw[:-3] if raw.endswith("/v1") else raw  # health lives at the root


def _completions_url() -> str:
    raw = (settings.ai_soc_llm_local_base_url or "").strip().rstrip("/")
    base = raw if raw.endswith("/v1") else f"{raw}/v1"
    return f"{base}/chat/completions"


def _health_ok(timeout: float = 5.0) -> bool:
    root = _base_url()
    if not root:
        return False
    try:
        with urllib.request.urlopen(f"{root}/health", timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def measure_runtime(*, timeout: float = 30.0) -> dict:
    """Stream a small completion and return measured throughput + classification."""
    if settings.ai_soc_llm_mode.strip().lower() in {"mock", "disabled", ""} or not settings.ai_soc_llm_enabled:
        return {"reachable": False, "tok_per_s": None, "status": "llm_disabled", "healthy": False, "reason": "llm_disabled"}
    if not _completions_url() or not _health_ok():
        return {"reachable": False, "tok_per_s": None, "status": "unreachable", "healthy": False, "reason": "unreachable"}

    body = json.dumps(
        {
            "model": settings.ai_soc_llm_local_model or "local",
            "messages": [{"role": "user", "content": "List three SOC triage steps, one short line each."}],
            "max_tokens": _PROBE_MAX_TOKENS,
            "temperature": 0.0,
            "stream": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _completions_url(), data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    started = time.monotonic()
    first_token_at: float | None = None
    token_times: list[float] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    delta = json.loads(data)["choices"][0].get("delta") or {}
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta.get("content"):
                    now = time.monotonic()
                    if first_token_at is None:
                        first_token_at = now
                    token_times.append(now)
                    if len(token_times) >= _STREAM_SAMPLE_TOKENS:
                        break
    except (urllib.error.URLError, OSError) as exc:
        if len(token_times) < 2:
            return {"reachable": True, "tok_per_s": None, "status": "probe_timeout",
                    "healthy": False, "reason": "probe_timeout", "error": f"{type(exc).__name__}"}

    wall_s = round(time.monotonic() - started, 2)
    if len(token_times) < 2:
        return {"reachable": True, "tok_per_s": None, "status": "no_tokens", "healthy": False, "reason": "no_tokens", "wall_s": wall_s}
    gen_span = token_times[-1] - token_times[0]
    tok_per_s = round((len(token_times) - 1) / gen_span, 2) if gen_span > 0 else None
    prompt_eval_s = round(first_token_at - started, 2) if first_token_at else None

    healthy, reason = _classify(tok_per_s, prompt_eval_s)
    return {
        "reachable": True,
        "tok_per_s": tok_per_s,
        "status": "measured",
        "healthy": healthy,
        "reason": reason,
        "sampled_tokens": len(token_times),
        "prompt_eval_s": prompt_eval_s,
        "wall_s": wall_s,
        "model": settings.ai_soc_llm_local_model or None,
        "threshold_tok_per_s": _DEFAULT_THRESHOLD,
    }


def _classify(tok_per_s: float | None, prompt_eval_s: float | None) -> tuple[bool, str]:
    if tok_per_s is None:
        return False, "rate_unknown"
    if prompt_eval_s is not None and prompt_eval_s > _DEFAULT_MAX_PROMPT_EVAL_S:
        return False, "prompt_stall"
    if tok_per_s < _DEFAULT_THRESHOLD:
        return False, "slow"
    return True, "ok"
