# T2 LLM SPL Producer — Lab Probe

Mode: **mock** | Questions: **6** | Producer fired: **6/6** | Governance invariants held: **6/6**

Invariant on every fired row: `normalized_spl` is null, `execution_eligible` is false, `validation.approved` is false — candidate SPL is review-only, never executable.

### pj.001
> Hunt for a flood of DNP3 unsolicited responses from an RTU to the SCADA master outside its normal class-poll schedule.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`1`
- SPL: ``

### pj.002
> Detect Modbus/TCP write-single-register or write-multiple-coils commands sent to boiler-control PLCs from hosts other than the approved engineering workstation.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`0`
- SPL: ``

### pj.004
> Hunt for NTP or IRIG-B time-source manipulation across substation IEDs and the PDC.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`0`
- SPL: ``

### pj.007
> Hunt for any outbound session from an OT asset that reached the corporate network or internet, bypassing the data diode.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`0`
- SPL: ``

### pj.008
> Find configuration or firmware pushes to SEL or ABB numerical relays made through a vendor engineering tool outside any approved maintenance window.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`0`
- SPL: ``

### pj.010
> Hunt for an internal host sweeping Modbus/TCP port 502 across the solar farm inverter SCADA range.

- fired=`True` status=`blocked` lab_tier=`False` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`0`
- SPL: ``
