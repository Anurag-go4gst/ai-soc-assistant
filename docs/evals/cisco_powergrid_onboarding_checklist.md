# Cisco PowerGrid / PGCIL Onboarding Checklist

COE control artifact listing what **PGCIL must supply** before the Cisco 50-question eval and analyst workflows can reach full PASS (not honest REVIEW/deferred). This is not runtime configuration — operators enter values through **Settings → Environment Knowledge** and deployment env vars.

## 1. Document control

| Field | PGCIL must supply |
|-------|-------------------|
| Engagement owner | SOC lead + OT engineering contact |
| Splunk App ID | `7931` (first MCP target; fixed) |
| Splunk platform | Enterprise / Cloud + staging vs prod label |
| COE reviewer sign-off | Names + approval date for frozen context doc |
| Linked static context doc | Completed [splunk_context_document_template.md](../splunk_context_document_template.md) |

## 2. Environment Knowledge — telemetry slots (Settings → Telemetry Routing)

| Slot group | Required for | PGCIL must supply |
|------------|--------------|-------------------|
| Core indexes | All SPL paths | `auth_index`, `network_index`, `dns_index`, `endpoint_index`, `firewall_index`, `vpn_index`, `sysmon_index` |
| Core sourcetypes | SPL placeholder resolution | Matching sourcetype for each index above |
| Cisco product indexes | Q1–Q20, Q41–Q43 | `cisco_firewall_index`, `cisco_ise_index`, `cisco_ios_index`, `stealthwatch_index`, `cisco_tacacs_index`, `cisco_wlc_index`, `cisco_duo_index`, `cisco_amp_index`, `cisco_secure_endpoint_index` |
| Cisco sourcetypes | Same | Matching `cisco_*_sourcetype` for each product |
| Zone labels | Perimeter / VPN / SCADA questions | `vpn_pool_zone`, `scada_core_zone`, `i_dmz_zone`, `internet_zone`, `it_corporate_zone` |
| Network constants | Geo / CIDR hunts | `internal_dns_ip`, `ot_asset_cidr`, `corporate_cidr` |
| Regional tags | Western / Northern grid filters | `western_grid_tag`, `northern_grid_tag`, `sldc_node` |
| Maintenance window | Q14 after-hours VPN | `vendor_maint_start_hour`, `vendor_maint_end_hour` |

**Note:** MCP **Discover from MCP** may fill index/sourcetype blanks only. COE-entered zone/CIDR/regional values win over discovery.

## 3. Asset Registry (Settings → Asset Registry)

| Field | Required for | PGCIL must supply |
|-------|--------------|-------------------|
| RTU / IED / HMI inventory | Tier-2 lookup templates (Wave 3), Q3/Q25–Q26/Q30/Q32–Q33/Q40 | CSV/JSON with `ip`, `asset_name`, `asset_type`, `purdue_layer`, `criticality`, `substation_id`, `region`, `is_master_station`, `expected_firmware` |
| CII designation | Q33 CII node hunts | `criticality=CII` on designated nodes |
| Master station flag | Q35 dual-master correlation | `is_master_station=true` where applicable |

Honest degrade when empty: answers show `asset_registry=not_configured` and review-only SPL placeholders.

## 4. IOC / compliance bundle (Settings → IOC Registry)

| Field | Required for | PGCIL must supply |
|-------|--------------|-------------------|
| CERT-In advisory bundle | Q40 hash block list | JSON IOC registry at `IOC_REGISTRY_PATH` with hash IOCs + `source_id` / `last_refreshed` |
| Registry activation | Live IOC lookup | `IOC_REGISTRY_ENABLED=true` in deployment env |
| Staleness policy | Routing preconditions | Refresh cadence + owner for air-gapped bundle imports |

UI shows read-only hash preview; file replace is operator-managed (AI-SOC does not pull external feeds).

## 5. SPL policy env (deployment `.env`)

| Variable | PGCIL must supply |
|----------|-------------------|
| `SPL_ALLOWED_INDEXES` | All Cisco + PGCIL indexes used in governed templates |
| `SPL_ALLOWED_SOURCETYPES` | All sourcetypes referenced in templates / lab drafts |
| `SPL_ALLOWED_LOOKUPS` | **COE sign-off required** before Wave 3 Tier-2 templates: e.g. `ot_asset_inventory.csv`, `cii_registry.csv`, `cert_in_ioc.csv`, `master_stations.csv`, `physical_access.csv` |
| Tier-1 enrichment | Confirm `iplocation`, `mvexpand`, `bucket` allowed per COE posture |

MCP execution flags remain **false** until explicit COE go-live.

## 6. Splunk MCP readiness (when live metadata / search needed)

| Field | PGCIL must supply |
|-------|-------------------|
| `SPLUNK_MCP_BASE_URL` + bearer token | Read-only Splunk MCP (App 7931) |
| Schema smoke | One approved search + metadata tool call signed off in [splunk_mcp_connection_contract.md](../../contracts/splunk_mcp_connection_contract.md) |
| Metadata hygiene (Q44–Q48) | Read-only discovery enabled for indexes / index info / metadata / knowledge objects / cluster info |

## 7. Optional — guided / weak-path LLM enrichment (COE demo, not deterministic eval)

Deterministic Cisco eval (`--profile deterministic`) does **not** require LLM synthesis. For COE demo narration on guided / low-confidence paths:

```bash
CONTROL_PLANE_ENABLED=true
AI_SOC_LLM_ENABLED=true
AI_SOC_LLM_MODE=local
AI_SOC_LLM_FINAL_SYNTHESIS_ENABLED=true
AI_SOC_LLM_LIVE_SYNTHESIS_ENABLED=true
AI_SOC_LLM_ANSWER_GUARD_ENABLED=true
ROUTING_LLM_SHADOW_ENABLED=true
# MCP execution stays false for eval
```

## 8. Explicitly out of scope for Cisco 50 gate

| Item | Status |
|------|--------|
| Google 25 OT question bank | Follow-on — placeholders only; not required for Cisco 50 PASS |
| Live Splunk lookup writes | Operator manual; AI-SOC never writes KV/lookups |
| MCP execution globally enabled | COE-gated; eval assumes disabled |
| Wazuh / second MCP server | Deferred (plan §5) |

## 9. Verification before COE sign-off

```bash
# Environment KB + routing smoke
cd backend && PYTHONPATH=../backend:.. python3 -m pytest app/tests/test_query_entity_extractors.py app/tests/test_guided_hunt_rescue.py app/tests/test_ioc_registry_settings_api.py

# Cisco catalogue gate (phased)
python3 scripts/run_cisco_powergrid_question_eval.py --profile deterministic --min-wave batch1 --check

# Full governance
./scripts/run_stage3_governance_regression.sh

# Frontend (prod serves frontend/dist)
cd frontend && npm run build
```
