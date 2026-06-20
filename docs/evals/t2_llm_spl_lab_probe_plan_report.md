# T2 LLM SPL Producer — Lab Probe

Mode: **plan** | Questions: **10** | Producer fired: **10/10** | Governance invariants held: **10/10**

Invariant on every fired row: `normalized_spl` is null, `execution_eligible` is false, `validation.approved` is false — candidate SPL is review-only, never executable.

### pj.001
> Hunt for a flood of DNP3 unsolicited responses from an RTU to the SCADA master outside its normal class-poll schedule.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`42149`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")), host_norm=lower(coalesce(host, "unknown")) | stats count as…`

### pj.002
> Detect Modbus/TCP write-single-register or write-multiple-coils commands sent to boiler-control PLCs from hosts other than the approved engineering workstation.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`40123`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")) | stats count as event_count earliest(_time) as first_seen_e…`

### pj.004
> Hunt for NTP or IRIG-B time-source manipulation across substation IEDs and the PDC.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`40044`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")), host_norm=lower(coalesce(host, "unknown")) | stats dc(funct…`

### pj.007
> Hunt for any outbound session from an OT asset that reached the corporate network or internet, bypassing the data diode.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`35161`
- SPL: `search index=<ot_network_index> sourcetype=<ot_network_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")), host_norm=lower(coalesce(host, "unknown")) …`

### pj.008
> Find configuration or firmware pushes to SEL or ABB numerical relays made through a vendor engineering tool outside any approved maintenance window.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`39363`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")), host_norm=lower(coalesce(host, "unknown")) | stats dc(funct…`

### pj.010
> Hunt for an internal host sweeping Modbus/TCP port 502 across the solar farm inverter SCADA range.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`37331`
- SPL: `search index=<ot_network_index> sourcetype=<ot_network_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")) | stats count as event_count earliest(_time) as first_seen_epoch latest(_time) as last_seen_ep…`

### pn.001
> Hunt for OPC tag subscription spikes on the SCADA OPC server in the last 24 hours by source host.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`31325`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_host_norm=lower(coalesce(src_host, "unknown")) | stats count as event_count earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by src_h…`

### pn.002
> Detect off-hours interactive logons to substation HMI workstations grouped by user and host.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`38034`
- SPL: `search index=<endpoint_index> sourcetype=<endpoint_sourcetype> earliest=-24h latest=now | eval user_norm=lower(coalesce(user, "unknown")), host_norm=lower(coalesce(host, "unknown")) | stats count as event_count earliest(_time) as first_seen…`

### pn.003
> Hunt for a GOOSE message storm on the substation process LAN by source IED.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`36022`
- SPL: `search index=<ot_index> sourcetype=<ot_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")) | stats count as event_count earliest(_time) as first_seen_epoch latest(_time) as last_seen_epoch by src_ip_no…`

### pn.004
> Find bulk data exports from the SCADA historian to external destinations by source host and bytes transferred.

- fired=`True` status=`candidate_generated` lab_tier=`True` approved=`False` normalized_spl_null=`True` execution_eligible=`None`
- quality_status=`passed` latency_ms=`None` wall_ms=`37889`
- SPL: `search index=<ot_network_index> sourcetype=<ot_network_sourcetype> earliest=-24h latest=now | eval src_ip_norm=lower(coalesce(src_ip, "unknown")), dest_ip_norm=lower(coalesce(dest_ip, "unknown")), host_norm=lower(coalesce(host, "unknown")) …`
