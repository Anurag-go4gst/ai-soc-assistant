"""The ten Experience Center scenarios, written as specs on the shared agent lifecycle."""

from __future__ import annotations

from app.demo.ec_agent.spec_engine import ScenarioSpec, register_spec, spec_for
from app.demo.fixtures.specs.q1_firewall_spike import Q1
from app.demo.fixtures.specs.q2_firewall_baseline import Q2
from app.demo.fixtures.specs.r1_sop_answer import R1
from app.demo.fixtures.specs.s1_new_external_ip import S1
from app.demo.fixtures.specs.s2_ai_assistant import S2
from app.demo.fixtures.specs.s3_firewall_block import S3
from app.demo.fixtures.specs.s4_vpn_zero_day import S4
from app.demo.fixtures.specs.s5_router_change import S5
from app.demo.fixtures.specs.s6_vpn_followup import S6
from app.demo.fixtures.specs.s7_retired_ot_device import S7

ALL_SPECS: tuple[ScenarioSpec, ...] = (S1, S2, S3, S4, S5, S6, S7, R1, Q1, Q2)

for _spec in ALL_SPECS:
    if spec_for(_spec.scenario_id) is None:
        register_spec(_spec)
