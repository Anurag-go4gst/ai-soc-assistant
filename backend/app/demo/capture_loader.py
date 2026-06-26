"""Experience Center capture-artifact loader (plan Track B2 / B2.1).

An EC capture artifact is a frozen recording of a genuine `user query -> final result`
run: the real (post-guard, post-authority-override) answer body, the per-stage latencies
measured during capture, and provenance proving "actual LLM answer from model X on date Y".

Demo time replays the frozen body with **no live LLM/MCP call**. This module is the strict
loader + fallback policy:

  load capture artifact
    -> on missing / corrupt / schema-version mismatch: fall back to the legacy in-code fixture
    -> if neither is usable: fail closed with an operator-facing error (never a blank/partial answer)

The artifact body deliberately excludes `trace_id`/`turn_id`/timestamps; the EC serving path
re-stamps those per run so each demo looks freshly executed.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

logger = logging.getLogger("ai_soc.demo.capture_loader")

# Bump on any artifact-shape change. The loader refuses to serve an artifact whose
# schema_version does not match, falling back to the legacy fixture instead.
CAPTURE_SCHEMA_VERSION = 1

CAPTURES_DIR = Path(__file__).resolve().parent / "captures"

# Each stage replay duration is capped so a worst-case captured run (VPS CPU steal can
# spike an LLM stage to 30-120s) never produces a multi-minute dead demo. See plan B4.
MAX_REPLAYED_STAGE_MS = 6000

_REQUIRED_TOP_KEYS = ("schema_version", "final_response", "stage_latencies", "provenance")
_REQUIRED_PROVENANCE_KEYS = (
    "model_id",
    "captured_at",
    "transport",
    "live_llm_called",
    "live_mcp_called",
)


class CaptureArtifactError(Exception):
    """Raised when a capture artifact exists but is unusable (corrupt / wrong schema).

    The serving path catches this and falls back to the legacy in-code fixture. It is NOT
    raised for a simply-absent artifact (that returns ``None`` so fallback is silent).
    """


def capture_path_for(scenario_id: str) -> Path:
    """Return the on-disk path an artifact for ``scenario_id`` would occupy."""
    return CAPTURES_DIR / f"{scenario_id}.json"


def capture_exists(scenario_id: str) -> bool:
    """Return True if a capture artifact file is present for ``scenario_id``."""
    return capture_path_for(scenario_id).is_file()


def load_capture_artifact(scenario_id: str) -> dict[str, Any] | None:
    """Strictly load and validate the capture artifact for ``scenario_id``.

    Returns the validated artifact dict, or ``None`` when no artifact file exists
    (silent fallback to the legacy fixture). Raises :class:`CaptureArtifactError`
    when an artifact exists but is corrupt or carries an unsupported schema_version,
    so the caller can fall back deliberately and log the reason.
    """
    path = capture_path_for(scenario_id)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:  # unreadable file on disk
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' could not be read: {exc}"
        ) from exc
    try:
        artifact = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' is not valid JSON: {exc}"
        ) from exc
    _validate_artifact(scenario_id, artifact)
    return artifact


def _validate_artifact(scenario_id: str, artifact: Any) -> None:
    """Validate artifact shape and schema_version; raise on any contract breach."""
    if not isinstance(artifact, dict):
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' must be a JSON object"
        )
    missing = [key for key in _REQUIRED_TOP_KEYS if key not in artifact]
    if missing:
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' missing keys: {sorted(missing)}"
        )
    version = artifact.get("schema_version")
    if version != CAPTURE_SCHEMA_VERSION:
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' has schema_version {version!r}; "
            f"expected {CAPTURE_SCHEMA_VERSION}"
        )
    final_response = artifact.get("final_response")
    if not isinstance(final_response, dict) or not final_response:
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' has an empty or non-object final_response"
        )
    # Never serve an artifact that pins ids/timestamps — those are re-stamped per run.
    for forbidden in ("trace_id", "turn_id", "timestamp"):
        if forbidden in final_response:
            raise CaptureArtifactError(
                f"capture artifact for '{scenario_id}' final_response must not embed "
                f"'{forbidden}' (re-stamped per run)"
            )
    provenance = artifact.get("provenance")
    if not isinstance(provenance, dict):
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' provenance must be an object"
        )
    prov_missing = [key for key in _REQUIRED_PROVENANCE_KEYS if key not in provenance]
    if prov_missing:
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' provenance missing keys: {sorted(prov_missing)}"
        )
    if provenance.get("live_mcp_called") is not False:
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' must record live_mcp_called=false"
        )
    if not isinstance(artifact.get("stage_latencies"), list):
        raise CaptureArtifactError(
            f"capture artifact for '{scenario_id}' stage_latencies must be a list"
        )


def normalize_stage_latencies(stage_latencies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return stage records with a `replayed_ms` capped to ``MAX_REPLAYED_STAGE_MS``.

    The frontend playback advances on the capped `replayed_ms`; `recorded_ms` is kept
    for honesty/audit ("representative replay, not exact"). Records without a usable
    recorded value are passed through with a best-effort cap.
    """
    normalized: list[dict[str, Any]] = []
    for record in stage_latencies:
        if not isinstance(record, dict):
            continue
        item = dict(record)
        recorded = item.get("recorded_ms")
        if isinstance(recorded, (int, float)):
            item["replayed_ms"] = min(int(recorded), MAX_REPLAYED_STAGE_MS)
        else:
            replayed = item.get("replayed_ms")
            item["replayed_ms"] = (
                min(int(replayed), MAX_REPLAYED_STAGE_MS)
                if isinstance(replayed, (int, float))
                else MAX_REPLAYED_STAGE_MS
            )
        normalized.append(item)
    return normalized


def ec_provenance_block(provenance: dict[str, Any]) -> dict[str, Any]:
    """Build the demo-time `ec_provenance` block the frontend badges (plan B6).

    `transport=fake` is surfaced as "simulated MCP lifecycle replay" so the demo never
    overclaims "real MCP called". The wording is gated off provenance, so it auto-corrects
    when a scenario is re-captured against a real Splunk MCP (`transport=live`).
    """
    transport = str(provenance.get("transport") or "fake")
    mcp_label = (
        "simulated MCP lifecycle replay"
        if transport != "live"
        else "live Splunk MCP"
    )
    return {
        "source": "captured_end_to_end_run",
        "model_id": provenance.get("model_id"),
        "captured_at": provenance.get("captured_at"),
        "git_sha": provenance.get("git_sha"),
        "prompt_hash": provenance.get("prompt_hash"),
        "transport": transport,
        "mcp_label": mcp_label,
        # Capture-time truth (the model WAS called when the artifact was recorded), kept
        # distinct from the demo-time posture below which is always no-live-call.
        "live_llm_called_at_capture": bool(provenance.get("live_llm_called")),
        # Demo-time posture — invariant regardless of any nested envelope marker.
        "live_llm_called": False,
        "live_mcp_called": False,
    }
