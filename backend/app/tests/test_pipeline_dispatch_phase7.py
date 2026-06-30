"""Phase 7 — retire SCADA/Cisco T2-native early return under dispatch v2.

The T2-native early return is flag-gated off when dispatch v2 is on, so SCADA /
Cisco queries flow through the governed template -> LLM plan-compiler -> lab
draft failover chain. runtime_source_profiles is RETAINED for validator profiles
(not removed). Promoting scada_perf/cisco_asa to enabled catalogue templates is
deferred until a live Splunk schema exists (Wave-3 posture).
"""

from __future__ import annotations

import inspect

from app.spl.runtime_source_profiles import resolve_runtime_profile_for_query
from app.chat import pipeline as chat_pipeline


def test_runtime_profiles_retained_for_scada_and_cisco() -> None:
    scada = resolve_runtime_profile_for_query("Show SCADA threshold anomalies")
    cisco = resolve_runtime_profile_for_query(
        "Check Cisco ASA hits against known bad IP threat feed IOCs"
    )
    assert scada is not None and "scada_perf" in scada.allowed_indexes
    assert cisco is not None and "cisco_asa" in cisco.allowed_indexes


def test_t2_native_early_return_is_flag_gated() -> None:
    """The early-return block must be guarded by the dispatch v2 flag."""
    src = inspect.getsource(chat_pipeline._candidate_spl_stage)
    assert "runtime_profile is not None and not _dispatch_v2_on" in src


def test_t2_native_helper_still_available_for_legacy_path() -> None:
    # Flag-off legacy path still relies on the helper; it must not be removed.
    assert callable(chat_pipeline._candidate_from_t2_spl_native)


def test_guided_spl_rescue_t2_native_is_flag_gated() -> None:
    src = inspect.getsource(chat_pipeline._candidate_spl_stage)
    assert "guided_spl_rescue and not _dispatch_v2_on" in src
