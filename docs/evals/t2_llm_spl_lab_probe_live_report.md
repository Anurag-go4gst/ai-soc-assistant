# T2 LLM SPL Producer — Lab Probe

Mode: **live** | Questions: **2** | Producer fired: **2/2** | Governance invariants held: **2/2**

Invariant on every fired row: `normalized_spl` is null, `execution_eligible` is false, `validation.approved` is false — candidate SPL is review-only, never executable.

### pj.001
> Hunt for a flood of DNP3 unsolicited responses from an RTU to the SCADA master outside its normal class-poll schedule.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`failed` latency_ms=`97172` wall_ms=`97174`
- SPL: ``

### pj.002
> Detect Modbus/TCP write-single-register or write-multiple-coils commands sent to boiler-control PLCs from hosts other than the approved engineering workstation.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`57057` wall_ms=`57059`
- SPL: ``
