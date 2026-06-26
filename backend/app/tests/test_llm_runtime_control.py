"""LLM runtime control queue + host watcher + runtime-health classification."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.llm import runtime_control as rc
from app.llm import runtime_health as rh


# --- control queue (backend side) ---

def test_control_disabled_raises(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_enabled", False)
    assert rc.control_available() is False
    with pytest.raises(rc.LlmControlError):
        rc.request_control("restart")


def test_control_dir_not_configured_raises(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_dir", "")
    with pytest.raises(rc.LlmControlError):
        rc.request_control("restart")


def test_invalid_action_rejected(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_dir", str(tmp_path))
    with pytest.raises(rc.LlmControlError):
        rc.request_control("rm -rf")


def test_request_writes_sentinel(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_dir", str(tmp_path))
    rec = rc.request_control("restart", requested_by="alice")
    assert rec["action"] == "restart" and rec["status"] == "pending"
    files = list(tmp_path.glob("request-*.json"))
    assert len(files) == 1
    written = json.loads(files[0].read_text())
    assert written["requested_by"] == "alice" and written["request_id"] == rec["request_id"]


def test_last_result_reads_watcher_output(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_enabled", True)
    monkeypatch.setattr("app.config.settings.ai_soc_llm_control_dir", str(tmp_path))
    (tmp_path / "last_result.json").write_text(json.dumps({"action": "restart", "ok": True}))
    assert rc.last_result()["ok"] is True


# --- host watcher ---

_WATCHER = Path(__file__).resolve().parents[3] / "scripts" / "llm_control_watcher.py"
_spec = importlib.util.spec_from_file_location("llm_control_watcher", _WATCHER)
assert _spec and _spec.loader
watcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher)


def test_watcher_applies_pending_and_writes_result(monkeypatch, tmp_path) -> None:
    (tmp_path / "request-abc.json").write_text(json.dumps({"request_id": "abc", "action": "restart", "requested_by": "bob"}))
    monkeypatch.setattr(watcher, "_apply", lambda action: {"ok": True, "cmd": f"systemctl {action} fake"})
    applied = watcher.process_pending(tmp_path)
    assert applied == 1
    assert not list(tmp_path.glob("request-*.json"))  # consumed
    result = json.loads((tmp_path / "last_result.json").read_text())
    assert result["action"] == "restart" and result["ok"] is True and result["requested_by"] == "bob"


def test_watcher_rejects_invalid_action() -> None:
    assert watcher._apply("destroy")["ok"] is False


# --- runtime health classification ---

def test_health_classify_slow_not_dead() -> None:
    assert rh._classify(1.0, 3.0) == (False, "slow")


def test_health_classify_rate_unknown() -> None:
    assert rh._classify(None, None) == (False, "rate_unknown")


def test_health_classify_prompt_stall() -> None:
    assert rh._classify(9.0, 45.0) == (False, "prompt_stall")


def test_health_classify_ok() -> None:
    assert rh._classify(6.0, 3.0) == (True, "ok")


def test_runtime_health_disabled_is_reported_not_raised(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.ai_soc_llm_mode", "disabled")
    out = rh.measure_runtime()
    assert out["healthy"] is False and out["reason"] == "llm_disabled"
