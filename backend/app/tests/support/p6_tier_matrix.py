"""P6 deterministic test-tier commands.

These strings are the contract for L0/L1/L2/L2-slow. L3 remains live-local-LLM
and is owned by P8; this matrix only names the command, it does not run a model.
"""

TIER_COMMANDS: dict[str, str] = {
    "L0": (
        'cd backend && PYTHONPATH=../backend:.. "$PYVENV" -m pytest -q '
        "app/tests/test_live_path_untouched_by_ec.py "
        "app/tests/test_p0_reasoning_role_reachability.py"
    ),
    "L1": (
        'cd backend && PYTHONPATH=../backend:.. "$PYVENV" -m pytest -q '
        "app/tests/test_trace_stable_oracle.py "
        "app/tests/test_minimal_evidence_state.py "
        "app/tests/test_spl_semantic_v2_contract.py "
        "app/tests/test_prompt_policy_contracts.py"
    ),
    "L2": (
        'cd backend && PYTHONPATH=../backend:.. "$PYVENV" -m pytest -q '
        "app/tests/test_l2_bank_manifest.py "
        "app/tests/test_l2_bank_journeys.py "
        "app/tests/test_p0_l2_production_chat_harness.py"
    ),
    "L2-SLOW": (
        'cd backend && PYTHONPATH=../backend:.. "$PYVENV" -m pytest -q -m l2_slow'
    ),
    "L3": (
        'PYTHONPATH=backend:. python3 scripts/eval_p8_l3_live.py ; '
        'live: AI_SOC_TESTS_ALLOW_LIVE_LLM=1 PYTHONPATH=backend:. '
        'python3 scripts/eval_p8_l3_live.py --live --write-report. '
        'LIVE_AB_EVAL_PERFORMED = NO.'
    ),
}

L2_SLOW_MODULES: tuple[str, ...] = (
    "app/tests/test_sidecar_timeout_hard.py",
    "app/tests/test_sidecar_timeout_failover.py",
    "app/tests/test_synthesis_narration_deadline.py",
)

REGISTERED_MARKERS: tuple[str, ...] = (
    "l0",
    "l1",
    "l2",
    "l2_slow",
    "l3",
    "known_parity_gap",
    "integration",
)
