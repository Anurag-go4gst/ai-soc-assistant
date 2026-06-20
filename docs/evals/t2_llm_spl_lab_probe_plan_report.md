# T2 LLM SPL Producer — Lab Probe

Mode: **plan** | Questions: **2** | Producer fired: **2/2** | Governance invariants held: **2/2**

Invariant on every fired row: `normalized_spl` is null, `execution_eligible` is false, `validation.approved` is false — candidate SPL is review-only, never executable.

### pj.001
> Hunt for a flood of DNP3 unsolicited responses from an RTU to the SCADA master outside its normal class-poll schedule.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`46422`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")), host_norm=lower(coalesce(host, "unknown")) | stats count as…`

### pj.002
> Detect Modbus/TCP write-single-register or write-multiple-coils commands sent to boiler-control PLCs from hosts other than the approved engineering workstation.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`39677`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")) | stats count as event_count earliest(_time) as first_seen_e…`
