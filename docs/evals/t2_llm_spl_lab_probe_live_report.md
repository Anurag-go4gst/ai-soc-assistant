# T2 LLM SPL Producer — Lab Probe

Mode: **live** | Questions: **2** | Producer fired: **2/2** | Governance invariants held: **2/2**

Invariant on every fired row: `normalized_spl` is null, `execution_eligible` is false, `validation.approved` is false — candidate SPL is review-only, never executable.

### pj.001
> Hunt for a flood of DNP3 unsolicited responses from an RTU to the SCADA master outside its normal class-poll schedule.

- fired=`True` status=`needs_clarification` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`None` latency_ms=`None` wall_ms=`200120`
- SPL: ``

### pj.002
> Detect Modbus/TCP write-single-register or write-multiple-coils commands sent to boiler-control PLCs from hosts other than the approved engineering workstation.

- fired=`True` status=`needs_clarification` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`None` latency_ms=`76706` wall_ms=`76707`
- adapter_errors: ["strict_json_parse_failed:Expecting ',' delimiter"]
- SPL: ``
