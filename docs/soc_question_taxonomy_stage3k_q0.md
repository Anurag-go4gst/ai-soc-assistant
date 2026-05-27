# Stage 3K-Q0-FIX: SOC Team Question Taxonomy

Status: documentation-only taxonomy rebuild
Input: `docs/input/soc_team_questions_stage3kq0.txt`
Scope: classify the actual SOC team questions only. No runtime code, SPL templates, SPL validator changes, LLM synthesis, Answer Guard execution, live LLM calls, MCP/SPL gate changes, or Experience Center behavior changes are included.

## Executive Summary

The actual SOC team list contains 105 analyst questions. Each non-empty input line is classified exactly once in the table below.

The list collapses into 20 reusable implementation patterns. The highest-value first-demo candidates are a small subset of common SOC triage questions: read-only alert/notable triage, top-N network/authentication aggregations, IOC correlation, DNS/beaconing behavior, success-after-failure, data source health, and one multi-signal investigation view.

Important Stage 3K-Q1 warning: this taxonomy can classify the ideal pattern and source class, but it does not mean implementation is ready. The current SPL validator is raw-search shaped and does not yet safely support CIM, `tstats`, or data-model query shapes. Do not implement CIM/tstats templates until Stage 3K-Q1 extends the SPL validator and template schema safely. Validator extension must come before template implementation.

## Pattern Taxonomy

| Pattern type | Description | Count | Representative actual questions | Likely Splunk source class | Template-generated SPL acceptable? | Vetted detection/correlation logic required? | Governance risk | Demo suitability |
|---|---|---:|---|---|---|---|---|---|
| top_n_aggregation | Rank entities by event count, connection count, alert count, or volume. | 9 | Which source IPs generated the most outbound connections?; Which hosts generated the most DNS queries? | CIM data model | yes, after validator support | no | low | P0 |
| threshold_anomaly | Find entities above an explicit or baseline-derived threshold. | 13 | Which users have excessive failed logins?; Which hosts show a spike in failed logins? | CIM data model | yes, after validator support | sometimes | medium | P0 |
| time_trend | Bucket counts over time. | 0 | No direct actual question in the input list. | CIM data model | yes, after validator support | no | low | later |
| new_or_unusual_source | Identify rare, first-seen, after-hours, unusual, or geo-unusual activity. | 14 | Which users logged in from new countries today?; Which hosts initiated traffic to rare countries? | CIM data model plus history/baseline | yes, after validator support | yes | medium | P1 |
| success_after_failure | Detect successful authentication after repeated failures. | 2 | Which accounts had a successful login after repeated failures? | CIM data model | yes, after validator support | yes | medium | P0 |
| ioc_correlation | Match observed IPs, domains, URLs, or hashes against a local IOC lookup. | 8 | Which hosts contacted known malicious IPs today?; Did any endpoint run this suspicious hash? | local IOC/threat-intel lookup | yes, after lookup/schema confirmation | no | high | P1 |
| threat_intel_enrichment | Enrich suspicious entities with local threat-intel context. | 1 | Which hosts contacted suspicious external domains? | local IOC/threat-intel lookup | no, enrichment first | no | high | P2 |
| notable_risk_lookup | Read alert/notable/risk records and rank risk or notable activity. | 5 | Which users or hosts have the highest risk scores?; Which assets are generating the most notable events? | ES notable/risk or equivalent alert/case source | yes for read-only lookup | no | medium/high | P0 |
| case_state_lookup | Read a specific notable/case state, prior disposition, or history. | 3 | What happened for this specific notable event? | ES notable/risk or equivalent alert/case source | yes for read-only lookup | no | high | P1 |
| asset_identity_context | Add asset criticality, owner, privilege, admin, or identity state. | 5 | For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status? | ES Asset & Identity or equivalent lookup | no, enrichment dependency first | no | medium | P1 |
| dns_beaconing_dga_behavior | Detect long DNS names, DGA, C2, beaconing, tunneling, suspicious subdomains, or periodicity. | 10 | Which DNS queries look like DGA activity?; Which hosts repeatedly contacted the same destination at regular intervals? | existing correlation search / ESCU-like detection | no | yes | high | P1 |
| lateral_movement | Detect SMB peer spread, remote services, or lateral movement signs. | 3 | Which hosts made SMB connections to many peers? | existing correlation search / ESCU-like detection | no | yes | high | P2 |
| suspicious_process_powershell | Detect suspicious PowerShell, process chains, shells, webshells, downloads, or endpoint execution behavior. | 12 | Which hosts executed encoded PowerShell commands?; Which hosts have suspicious parent-child process chains? | existing correlation search / ESCU-like detection | no | yes | high | P2 |
| persistence_scheduled_task_service | Detect scheduled tasks, remote service creation, or persistence indicators. | 3 | Which endpoints created new scheduled tasks? | existing correlation search / ESCU-like detection | no | yes | high | P2 |
| data_source_health | Check whether key sources are missing, stale, or stopped. | 2 | Which logs are missing from key security sources? | raw index fallback / metadata | yes | no | medium | P0 |
| cloud_activity | Analyze cloud control-plane activity. | 0 | No direct cloud-control question in the input list. | external / unknown | no | yes | high | later |
| dlp_exfiltration | Analyze large outbound transfer, cloud upload, USB, or exfiltration behavior. | 6 | Which hosts showed potential data exfiltration to cloud apps? | DLP/proxy/network source, often external / unknown | maybe, after source confirmation | yes | high | P2 |
| multi_signal_correlation | Combine multiple signal families into one investigation view. | 8 | Which hosts showed both process execution and suspicious DNS within 24 hours? | multi-source CIM plus ES/A&I/IOC as needed | yes for component lookups only | yes | high | P1 |
| safe_metadata_discovery | Discover indexes, sourcetypes, fields, or safe metadata before query generation. | 0 | No direct metadata-discovery question in the input list. | raw index fallback / metadata | yes | no | low | later |
| other_or_unclear | Actual question is not specific enough for a governed query family without SOC interpretation. | 1 | Which hosts showed peer-to-peer style communication? | external / unknown | no | yes | medium | later |

## Question-Level Classification Table

| # | original_question | normalized_intent | pattern_type | SOC domain | likely source class | likely CIM data model | required entities | clarification_required | IOC_or_threat_intel_required | behavioral_detection_required | suggested_MITRE_candidates | governance_risk | demo_priority | data_dependency_status | notes |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | What incident or alert network events are high or critical right now? | read high/critical current network alerts | notable_risk_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | time_range | false | false | false |  | medium | P0 | assumed | Read-only alert/notable lookup; define "right now" window. |
| 2 | Which source IPs generated the most outbound connections? | rank outbound connection source IPs | top_n_aggregation | network | CIM data model | Network_Traffic | src_ip, time_range | false | false | false |  | low | P0 | assumed | Good bounded aggregation. |
| 3 | Which destination IPs received the most connections? | rank destination IPs by connection count | top_n_aggregation | network | CIM data model | Network_Traffic | dest_ip, time_range | false | false | false |  | low | P1 | assumed | Directionality and internal/external classification should be explicit. |
| 4 | Which hosts contacted known malicious IPs today? | correlate host traffic with malicious IP lookup | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Network_Traffic | host, dest_ip, time_range | false | true | false | T1071, T1041 | high | P1 | blocked_external | Requires local malicious IP lookup. |
| 5 | Which hosts contacted suspicious external domains? | enrich external domains and return suspicious host contacts | threat_intel_enrichment | threat_intel | local IOC/threat-intel lookup | Network_Resolution / DNS | host, domain, time_range | false | true | false | T1071.004 | high | P2 | blocked_external | "Suspicious" needs a vetted local reputation source or rule. |
| 6 | Which DNS queries have unusually long names? | detect long DNS query names | dns_beaconing_dga_behavior | dns | existing correlation search / ESCU-like detection | Network_Resolution / DNS | domain, threshold, time_range | false | false | true | T1568 | high | P1 | unknown | Needs vetted length/entropy thresholds. |
| 7 | Which DNS queries look like DGA activity? | detect DGA-like DNS queries | dns_beaconing_dga_behavior | dns | existing correlation search / ESCU-like detection | Network_Resolution / DNS | domain, time_range | false | false | true | T1568 | high | P1 | unknown | Do not generate DGA logic ad hoc. |
| 8 | Which hosts show possible beaconing behavior? | detect host beaconing candidates | dns_beaconing_dga_behavior | dns | existing correlation search / ESCU-like detection | Network_Traffic | host, time_range | false | false | true | T1071 | high | P1 | unknown | Requires vetted periodicity logic. |
| 9 | Which hosts communicated with many unique external IPs? | find hosts exceeding unique external IP threshold | threshold_anomaly | network | CIM data model | Network_Traffic | host, dest_ip, threshold, time_range | false | false | true | T1071 | medium | P1 | assumed | Threshold or baseline must be explicit. |
| 10 | Which hosts are generating the most SMB traffic? | rank hosts by SMB traffic | top_n_aggregation | network | CIM data model | Network_Traffic | host, time_range | false | false | false | T1021.002 | low | P1 | assumed | Query is aggregation; interpretation may imply lateral movement. |
| 11 | Which hosts made SMB connections to many peers? | detect SMB peer spread | lateral_movement | lateral_movement | existing correlation search / ESCU-like detection | Network_Traffic | host, threshold, time_range | false | false | true | T1021.002 | high | P2 | unknown | Detection logic should be vetted. |
| 12 | Which systems used unusual destination ports? | find unusual destination port usage | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, threshold, time_range | false | false | true |  | medium | P1 | assumed | Needs baseline or allowed-port policy. |
| 13 | Which systems generated large outbound data transfers? | find large outbound transfers by system | dlp_exfiltration | exfiltration | raw index fallback | Network_Traffic | host, threshold, time_range | false | false | true | T1041, T1048 | high | P2 | blocked_external | Network bytes may be available, but exfil claim needs DLP/proxy context. |
| 14 | Which hosts showed potential data exfiltration to cloud apps? | detect possible cloud-app exfiltration | dlp_exfiltration | cloud | external / unknown | Web | host, url, threshold, time_range | false | false | true | T1048 | high | P2 | blocked_external | Requires cloud app/proxy/DLP classification. |
| 15 | Which hosts have repeated connections to rare destinations? | detect repeated connections to rare destinations | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, time_range | false | false | true | T1071 | medium | P1 | assumed | Needs rarity baseline. |
| 16 | Which hosts contacted the same external IP many times? | find repeated host-to-external-IP contacts | threshold_anomaly | network | CIM data model | Network_Traffic | host, dest_ip, threshold, time_range | false | false | true | T1071 | medium | P1 | assumed | Good bounded threshold pattern. |
| 17 | Which hosts generated the most DNS queries? | rank hosts by DNS query count | top_n_aggregation | dns | CIM data model | Network_Resolution / DNS | host, time_range | false | false | false | T1071.004 | low | P0 | assumed | Useful demo if DNS data exists. |
| 18 | Which domains were queried by multiple hosts? | rank domains by distinct querying hosts | top_n_aggregation | dns | CIM data model | Network_Resolution / DNS | domain, host, time_range | false | false | false | T1071.004 | low | P1 | assumed | Distinct-host count. |
| 19 | Which hosts queried domains with suspicious subdomains? | detect suspicious subdomain DNS behavior | dns_beaconing_dga_behavior | dns | existing correlation search / ESCU-like detection | Network_Resolution / DNS | host, domain, time_range | false | false | true | T1568 | high | P1 | unknown | Suspicious subdomain criteria must be vetted. |
| 20 | Which networks saw traffic to high-risk ports? | find networks with high-risk destination ports | new_or_unusual_source | network | CIM data model | Network_Traffic | src_ip, dest_ip, time_range | false | false | true |  | medium | P1 | assumed | Needs approved high-risk port list. |
| 21 | Which hosts communicated with foreign IP ranges? | find hosts communicating with foreign IP ranges | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, time_range | false | false | true |  | medium | P2 | assumed | Requires geo/IP range enrichment. |
| 22 | Which hosts contacted IPs in an IOC lookup? | correlate host traffic with IOC IP lookup | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Network_Traffic | host, dest_ip, time_range | false | true | false | T1071 | high | P1 | blocked_external | Requires local IOC lookup. |
| 23 | Which hosts showed possible command-and-control beaconing? | detect C2 beaconing hosts | dns_beaconing_dga_behavior | dns | existing correlation search / ESCU-like detection | Network_Traffic | host, time_range | false | false | true | T1071 | high | P1 | unknown | Use vetted C2/beaconing detection. |
| 24 | Which internal hosts generated outbound traffic after DNS lookups? | correlate DNS lookup followed by outbound traffic | multi_signal_correlation | multi_signal_correlation | CIM data model | Network_Resolution / DNS | host, domain, dest_ip, time_range | false | false | true | T1071.004 | high | P1 | unknown | Requires DNS plus network temporal correlation. |
| 25 | Which hosts used unusual protocols? | find unusual protocol use by host | new_or_unusual_source | network | CIM data model | Network_Traffic | host, threshold, time_range | false | false | true |  | medium | P1 | assumed | Needs approved protocol baseline. |
| 26 | Which hosts have unusually high connection counts to one destination? | find high host-to-destination connection counts | threshold_anomaly | network | CIM data model | Network_Traffic | host, dest_ip, threshold, time_range | false | false | true | T1071 | medium | P1 | assumed | Threshold/baseline required. |
| 27 | Which DNS queries resolved to suspicious top-level domains? | detect suspicious TLD DNS queries | dns_beaconing_dga_behavior | dns | existing correlation search / ESCU-like detection | Network_Resolution / DNS | domain, time_range | false | false | true | T1568 | high | P2 | unknown | Requires vetted suspicious TLD list. |
| 28 | Which hosts showed peer-to-peer style communication? | identify peer-to-peer style communication | other_or_unclear | network | external / unknown | unknown / not applicable | host, time_range | false | false | true |  | medium | later | unknown | Needs SOC definition of P2P style. |
| 29 | Which systems accessed the internet through rare ports? | find internet access through rare ports | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, threshold, time_range | false | false | true |  | medium | P1 | assumed | Needs rare-port baseline. |
| 30 | Which hosts contacted external IPs after hours? | find after-hours external IP contact | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, time_range | false | false | true | T1071 | medium | P1 | assumed | Needs business-hours policy. |
| 31 | Which hosts repeatedly contacted the same destination at regular intervals? | detect periodic host-to-destination contacts | dns_beaconing_dga_behavior | network | existing correlation search / ESCU-like detection | Network_Traffic | host, dest_ip, time_range | false | false | true | T1071 | high | P1 | unknown | Beaconing periodicity logic must be vetted. |
| 32 | Which hosts had both DNS and network anomalies? | correlate DNS and network anomaly flags | multi_signal_correlation | multi_signal_correlation | existing correlation search / ESCU-like detection | Network_Resolution / DNS | host, time_range | false | false | true | T1071.004 | high | P1 | unknown | Requires two anomaly sources and provenance. |
| 33 | Which hosts communicated with suspicious destination domains and IPs? | correlate suspicious domain and IP communication | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Network_Traffic | host, domain, dest_ip, time_range | false | true | false | T1071 | high | P1 | blocked_external | Suspicious lists must be local and vetted. |
| 34 | Which destination IPs were contacted by many hosts? | rank destination IPs by distinct hosts | top_n_aggregation | network | CIM data model | Network_Traffic | dest_ip, host, time_range | false | false | false |  | low | P1 | assumed | Distinct-source aggregation. |
| 35 | Which hosts generated the largest DNS response volumes? | rank DNS response volume by host | threshold_anomaly | dns | CIM data model | Network_Resolution / DNS | host, threshold, time_range | false | false | true | T1071.004 | medium | P2 | assumed | Requires DNS response size fields. |
| 36 | Which hosts reached known malicious domains from lookup data? | correlate host DNS/web with malicious domain lookup | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Network_Resolution / DNS | host, domain, time_range | false | true | false | T1071.004 | high | P1 | blocked_external | Requires local domain IOC lookup. |
| 37 | Which hosts showed likely proxy or tunneling behavior? | detect proxy/tunneling behavior | dns_beaconing_dga_behavior | network | existing correlation search / ESCU-like detection | Network_Traffic | host, time_range | false | false | true | T1090 | high | P2 | unknown | Requires vetted tunneling/proxy detection. |
| 38 | Which hosts had large inbound traffic from a single source? | find large inbound traffic from one source | threshold_anomaly | network | CIM data model | Network_Traffic | host, src_ip, threshold, time_range | false | false | true |  | medium | P2 | assumed | Needs byte fields and threshold. |
| 39 | Which hosts downloaded large volumes from the internet? | find large internet downloads by host | dlp_exfiltration | exfiltration | raw index fallback | Network_Traffic | host, threshold, time_range | false | false | true | T1105 | high | P2 | blocked_external | May use network/proxy bytes; exfil or malware interpretation needs context. |
| 40 | Which hosts initiated traffic to rare countries? | find host traffic to rare countries | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, time_range | false | false | true |  | medium | P2 | assumed | Needs geo enrichment and baseline. |
| 41 | Which systems have repeated hits to the same suspicious URL path? | find repeated suspicious URL path hits | threshold_anomaly | network | CIM data model | Web | host, url, threshold, time_range | false | false | true | T1071.001 | medium | P2 | assumed | Requires web/proxy URL fields and suspicious-path criteria. |
| 42 | Which hosts contacted both malicious IPs and domains? | correlate malicious IP and domain IOC hits | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Network_Traffic | host, dest_ip, domain, time_range | false | true | false | T1071 | high | P1 | blocked_external | Requires IP and domain IOC lookups. |
| 43 | Which hosts show consistent low-volume outbound connections? | detect low-volume periodic outbound behavior | dns_beaconing_dga_behavior | network | existing correlation search / ESCU-like detection | Network_Traffic | host, time_range | false | false | true | T1071 | high | P2 | unknown | Beaconing-like behavior; use vetted logic. |
| 44 | Which rules are generating the most alerts? | rank alerting rules by volume | top_n_aggregation | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | time_range | false | false | false |  | low | P0 | assumed | Read-only alert analytics. |
| 45 | What happened for this specific notable event? | retrieve notable event detail and context | case_state_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | notable_id | true | false | false |  | high | P1 | blocked_external | Needs notable id and read-only case/notable source. |
| 46 | Which users have excessive failed logins? | find users above failed-login threshold | threshold_anomaly | authentication | CIM data model | Authentication | user, threshold, time_range | false | false | true | T1110.001 | medium | P0 | assumed | Threshold must be explicit or policy default. |
| 47 | Is one IP attacking many accounts? | detect one source IP failing against many accounts | threshold_anomaly | authentication | CIM data model | Authentication | src_ip, user, threshold, time_range | false | false | true | T1110.001 | medium | P0 | assumed | Good brute-force pattern. |
| 48 | Did a user log in from impossible locations? | detect impossible travel login behavior | new_or_unusual_source | identity | existing correlation search / ESCU-like detection | Authentication | user, time_range | true | false | true | T1078 | medium | P1 | assumed | Needs geo enrichment and user context. |
| 49 | Which hosts ran suspicious PowerShell? | detect suspicious PowerShell by host | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1059.001 | high | P2 | unknown | Use vetted detection content. |
| 50 | Did Office apps spawn cmd or PowerShell? | detect Office-to-shell child process behavior | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1204, T1059 | high | P2 | unknown | Requires endpoint process telemetry. |
| 51 | What unusual processes ran on critical servers? | detect unusual processes on critical servers | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1059 | high | P2 | unknown | Also needs critical-server asset enrichment. |
| 52 | Did any host contact known malicious IPs? | correlate host traffic with malicious IPs | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Network_Traffic | host, dest_ip, time_range | false | true | false | T1071 | high | P1 | blocked_external | Requires local malicious IP lookup. |
| 53 | Are there suspicious DNS queries indicating C2 or DGA behavior? | detect DNS C2 or DGA behavior | dns_beaconing_dga_behavior | dns | existing correlation search / ESCU-like detection | Network_Resolution / DNS | domain, time_range | false | false | true | T1071.004, T1568 | high | P1 | unknown | Detection content should be pre-vetted. |
| 54 | Who is sending large amounts of data outbound? | identify users/hosts with large outbound data | dlp_exfiltration | exfiltration | raw index fallback | Network_Traffic | user, host, threshold, time_range | false | false | true | T1041, T1048 | high | P2 | blocked_external | User attribution may require proxy/DLP. |
| 55 | Did anyone get added to Administrators? | detect users added to Administrators group | asset_identity_context | identity | CIM data model | Change | user, time_range | false | false | true | T1098 | medium | P1 | blocked_external | Requires AD/change or identity source. |
| 56 | Which users are logging in outside normal hours? | find users authenticating outside normal hours | new_or_unusual_source | authentication | CIM data model | Authentication | user, time_range | false | false | true | T1078 | medium | P1 | assumed | Needs business-hours policy. |
| 57 | Did any endpoint run this suspicious hash? | search endpoint telemetry for suspicious hash | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Endpoint | hash, time_range | true | true | false | T1204 | high | P2 | blocked_external | Needs hash value and endpoint hash telemetry. |
| 58 | Which users or hosts have the highest risk scores? | rank users/hosts by risk score | notable_risk_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | user, host, time_range | false | false | false |  | high | P1 | assumed | Depends on populated risk data. |
| 59 | Which source IPs generated the most authentication failures today? | rank source IPs by authentication failures | top_n_aggregation | authentication | CIM data model | Authentication | src_ip, time_range | false | false | false | T1110.001 | low | P0 | assumed | Strong first-demo candidate. |
| 60 | Which accounts had a successful login after repeated failures? | find success after repeated auth failures | success_after_failure | authentication | CIM data model | Authentication | user, threshold, time_range | false | false | true | T1078, T1110.001 | medium | P0 | assumed | Strong first-demo candidate. |
| 61 | Which users logged in from new countries today? | detect new-country logins | new_or_unusual_source | identity | CIM data model | Authentication | user, time_range | false | false | true | T1078 | medium | P1 | assumed | Requires geo and historical baseline. |
| 62 | Which hosts show a spike in failed logins? | detect hosts with failed-login spike | threshold_anomaly | authentication | CIM data model | Authentication | host, threshold, time_range | false | false | true | T1110.001 | medium | P1 | assumed | Needs baseline or explicit spike definition. |
| 63 | Which endpoints spawned script interpreters recently? | detect script interpreter process spawns | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1059 | high | P2 | unknown | Requires endpoint process telemetry. |
| 64 | Which hosts executed encoded PowerShell commands? | detect encoded PowerShell | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1059.001 | high | P2 | unknown | Use vetted detection content. |
| 65 | Which endpoints created new scheduled tasks? | detect scheduled task creation | persistence_scheduled_task_service | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1053 | high | P2 | unknown | Requires Windows endpoint telemetry. |
| 66 | Which systems contacted rare external destinations? | find rare external destination contacts | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, time_range | false | false | true | T1071 | medium | P1 | assumed | Needs rarity baseline. |
| 67 | Which hosts are generating unusual DNS query volumes? | detect unusual DNS volume by host | threshold_anomaly | dns | CIM data model | Network_Resolution / DNS | host, threshold, time_range | false | false | true | T1071.004 | medium | P1 | assumed | Threshold or baseline required. |
| 68 | Which internal hosts contacted known command-and-control domains? | correlate internal hosts with known C2 domains | ioc_correlation | threat_intel | local IOC/threat-intel lookup | Network_Resolution / DNS | host, domain, time_range | false | true | false | T1071.004 | high | P1 | blocked_external | Requires local C2 domain lookup. |
| 69 | Which users accessed privileged applications unusually? | detect unusual privileged application access | asset_identity_context | identity | CIM data model | Web | user, url, time_range | false | false | true | T1078 | medium | P2 | blocked_external | Needs privileged-app inventory and user baseline. |
| 70 | Which users changed their password multiple times in a short window? | detect repeated password changes | threshold_anomaly | identity | CIM data model | Change | user, threshold, time_range | false | false | true | T1098 | medium | P1 | assumed | Needs AD/change events. |
| 71 | Which accounts were disabled or re-enabled today? | list account disable/re-enable changes | asset_identity_context | identity | CIM data model | Change | user, time_range | false | false | false | T1098 | medium | P1 | blocked_external | Requires identity/change source. |
| 72 | Which hosts show signs of lateral movement? | detect lateral movement signs | lateral_movement | lateral_movement | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1021 | high | P2 | unknown | Needs vetted lateral movement detection content. |
| 73 | Which systems had multiple remote service creations? | detect multiple remote service creations | persistence_scheduled_task_service | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, threshold, time_range | false | false | true | T1543.003 | high | P2 | unknown | Also lateral movement adjacent. |
| 74 | Which hosts show SMB connections to many peers? | detect SMB fan-out to many peers | lateral_movement | lateral_movement | existing correlation search / ESCU-like detection | Network_Traffic | host, threshold, time_range | false | false | true | T1021.002 | high | P2 | unknown | Duplicate pattern with row 11, actual question preserved. |
| 75 | Which endpoints created suspicious archive files? | detect suspicious archive creation | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1560 | high | P2 | unknown | Could also support exfil staging. |
| 76 | Which hosts uploaded large amounts of data to cloud services? | detect large uploads to cloud services | dlp_exfiltration | cloud | external / unknown | Web | host, url, threshold, time_range | false | false | true | T1048 | high | P2 | blocked_external | Requires proxy/CASB/DLP/cloud-service classification. |
| 77 | Which endpoints accessed USB storage recently? | detect endpoint USB storage access | dlp_exfiltration | dlp | raw index fallback | Endpoint | host, time_range | false | false | true | T1052 | high | P2 | blocked_external | Requires endpoint/device control telemetry. |
| 78 | Which systems had repeated malware detections? | find systems with repeated malware detections | threshold_anomaly | endpoint | CIM data model | Intrusion_Detection | host, threshold, time_range | false | false | true |  | medium | P2 | assumed | Depends EDR/AV source. |
| 79 | Which files were modified by suspicious processes? | correlate file modifications with suspicious processes | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1105 | high | P2 | unknown | Requires endpoint file and process telemetry. |
| 80 | Which hosts spawned shells from email clients? | detect email-client-to-shell process chains | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1204, T1059 | high | P2 | unknown | Requires parent-child process telemetry. |
| 81 | Which users received and opened phishing attachments? | detect phishing attachment open events | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | user, time_range | false | false | true | T1566.001, T1204 | high | P2 | unknown | May require email security plus endpoint telemetry. |
| 82 | Which domains were queried by multiple hosts in a short period? | find domains queried by many hosts in short window | threshold_anomaly | dns | CIM data model | Network_Resolution / DNS | domain, host, threshold, time_range | false | false | true | T1071.004 | medium | P1 | assumed | Threshold and short-window duration must be defined. |
| 83 | Which hosts have suspicious parent-child process chains? | detect suspicious parent-child process chains | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1059, T1204 | high | P2 | unknown | Use vetted process-chain rules. |
| 84 | Which accounts have the most risk events? | rank accounts by risk event count | notable_risk_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | user, time_range | false | false | false |  | high | P1 | assumed | Requires risk-event population. |
| 85 | Which assets have accumulated risk from multiple detections? | rank assets by accumulated risk | notable_risk_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | host, time_range | false | false | false |  | high | P1 | assumed | Requires risk plus asset mapping. |
| 86 | Which users were involved in both failed logins and privilege changes? | correlate failed logins with privilege changes | multi_signal_correlation | multi_signal_correlation | CIM data model | Authentication | user, time_range | false | false | true | T1110.001, T1098 | high | P1 | unknown | Requires auth plus AD/change events. |
| 87 | Which hosts are communicating with unusual ports externally? | find unusual external port communication | new_or_unusual_source | network | CIM data model | Network_Traffic | host, dest_ip, threshold, time_range | false | false | true |  | medium | P1 | assumed | Needs port baseline/allowlist. |
| 88 | Which endpoints have multiple persistence indicators? | detect endpoints with multiple persistence indicators | persistence_scheduled_task_service | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, threshold, time_range | false | false | true | T1053, T1543, T1547 | high | P2 | unknown | Requires detection inventory. |
| 89 | Which users authenticated to VPN after repeated MFA failures? | detect VPN success after repeated MFA failures | success_after_failure | authentication | CIM data model | Authentication | user, threshold, time_range | false | false | true | T1078, T1110.001 | medium | P1 | assumed | Requires VPN/MFA source mapping. |
| 90 | Which assets are generating the most notable events? | rank assets by notable event count | notable_risk_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | host, time_range | false | false | false |  | high | P1 | assumed | Requires notable source and asset mapping. |
| 91 | Which alerts are still open and unresolved? | read open unresolved alert state | case_state_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | time_range | false | false | false |  | high | P1 | blocked_external | Read-only case state only. |
| 92 | Which users had access to sensitive systems and then large outbound transfers? | correlate sensitive-system access and outbound transfer | multi_signal_correlation | multi_signal_correlation | CIM data model | Authentication | user, host, threshold, time_range | false | false | true | T1078, T1048 | high | P1 | unknown | Needs asset sensitivity plus network/proxy/DLP data. |
| 93 | Which hosts showed both process execution and suspicious DNS within 24 hours? | correlate endpoint process and suspicious DNS signals | multi_signal_correlation | multi_signal_correlation | existing correlation search / ESCU-like detection | Endpoint | host, domain, time_range | false | false | true | T1059, T1071.004 | high | P1 | unknown | Strong governed investigation demo candidate. |
| 94 | Which logs are missing from key security sources? | identify missing key security logs | data_source_health | data_health | raw index fallback | unknown / not applicable | none / derived | false | false | false |  | medium | P0 | unknown | Safe metadata/source-health pattern. |
| 95 | Which sources stopped sending events recently? | identify stale sources | data_source_health | data_health | raw index fallback | unknown / not applicable | time_range | false | false | false |  | medium | P0 | unknown | Safe metadata/source-health pattern. |
| 96 | Which users performed privileged actions from non-admin workstations? | detect privileged actions from non-admin workstations | asset_identity_context | identity | CIM data model | Change | user, host, time_range | false | false | true | T1098 | medium | P1 | blocked_external | Needs privilege action mapping plus workstation classification. |
| 97 | Which systems show signs of webshell activity? | detect webshell activity signs | suspicious_process_powershell | endpoint | existing correlation search / ESCU-like detection | Endpoint | host, time_range | false | false | true | T1505.003 | high | P2 | unknown | Requires vetted webshell detection content. |
| 98 | Which hosts downloaded executables from the internet? | find internet executable downloads by host | suspicious_process_powershell | endpoint | CIM data model | Web | host, url, time_range | false | false | true | T1105 | high | P2 | unknown | Needs proxy/web file metadata or endpoint telemetry. |
| 99 | Which detections involved the same user and host repeatedly? | correlate repeated detections for same user and host | multi_signal_correlation | multi_signal_correlation | ES notable/risk or equivalent alert/case source | Risk / Notable | user, host, threshold, time_range | false | false | true |  | high | P1 | unknown | Requires detection/notable event normalization. |
| 100 | Which users triggered multiple different detections? | correlate multiple detection types per user | multi_signal_correlation | multi_signal_correlation | ES notable/risk or equivalent alert/case source | Risk / Notable | user, threshold, time_range | false | false | true |  | high | P1 | unknown | Requires detection taxonomy. |
| 101 | Which devices are generating the most endpoint alerts? | rank devices by endpoint alert count | top_n_aggregation | endpoint | CIM data model | Intrusion_Detection | host, time_range | false | false | false |  | low | P1 | assumed | Needs endpoint alert source. |
| 102 | Which users are accessing resources from unusual hosts? | find users accessing resources from unusual hosts | new_or_unusual_source | identity | CIM data model | Authentication | user, host, time_range | false | false | true | T1078 | medium | P1 | assumed | Needs user-host baseline. |
| 103 | For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status? | enrich flagged entity with asset and identity context | asset_identity_context | identity | ES notable/risk or equivalent alert/case source | unknown / not applicable | user, host | true | false | false |  | medium | P1 | blocked_external | Requires Asset & Identity/CMDB/IAM enrichment. |
| 104 | What is the full activity timeline for a given entity in the N hours before and after a detection? | build bounded entity activity timeline around detection | multi_signal_correlation | multi_signal_correlation | CIM data model | unknown / not applicable | user, host, src_ip, dest_ip, time_range | true | false | true |  | high | P1 | unknown | Needs entity and detection anchor; read-only timeline. |
| 105 | Has this entity, IP, domain, or notable been seen or investigated before, and what was the prior disposition? | read prior sightings and investigation disposition | case_state_lookup | notable_risk | ES notable/risk or equivalent alert/case source | Risk / Notable | user, src_ip, domain, notable_id, time_range | true | false | false |  | high | P1 | blocked_external | Requires case history/prior disposition source. |

## Working Assumptions

- The input file is authoritative for Stage 3K-Q0-FIX. No representative or invented questions are added.
- "Today", "recently", "right now", "short window", and "after hours" need deterministic default windows before runtime implementation.
- IOC and threat-intel questions require a local lookup. External enrichment is not assumed.
- Behavioral detections should reuse vetted correlation searches, ESCU-like content, or SOC-approved logic. They should not be produced as one-off LLM-authored SPL.
- ES notable/risk, Asset & Identity, cloud, DLP, EDR, proxy/web, VPN/MFA, and AD/change availability must be confirmed before implementation.
- MCP remains read-only for this taxonomy stage. Candidate SPL remains non-executable unless future governed gates explicitly approve it.
- Stage 3K-Q1 must extend the SPL validator before CIM/tstats or data-model template work begins.

## Minimal SOC/Splunk Team Validation Questions

A. Which 8-10 questions from this list are highest priority for the first portal demo?

B. Which log sources are currently available: firewall, DNS, proxy/web, AD/auth, VPN/MFA, EDR/endpoint, cloud, DLP?

C. For available sources, should we assume CIM/tstats is available, or should we start with raw index/sourcetype fallback?

D. For known malicious IP/domain/hash questions, what local IOC/threat-intel lookup should be used?

E. Are existing detections/correlation searches available for beaconing, DGA, lateral movement, impossible travel, encoded PowerShell, scheduled tasks?

F. Are ES notable/risk data and Asset & Identity lookups available for read-only use?

## Recommended First Demo Coverage

| Original question | Pattern | Why it is representative | Data needed | Governance risk demonstrated | Fixture-based for Experience Center? |
|---|---|---|---|---|---|
| What incident or alert network events are high or critical right now? | notable_risk_lookup | Shows read-only alert triage without enabling actions. | ES notable/alert fixture with severity and status. | Medium: severity/status must be evidence-backed. | yes |
| Which source IPs generated the most outbound connections? | top_n_aggregation | Covers low-risk network aggregation. | Network traffic fixture with source IP and direction. | Low: bounded aggregation only. | yes |
| Which source IPs generated the most authentication failures today? | top_n_aggregation | Covers common SOC authentication triage. | Authentication fixture with source IP and failures. | Low: read-only count, no attribution overclaim. | yes |
| Which accounts had a successful login after repeated failures? | success_after_failure | Captures a high-value identity sequence pattern. | Authentication fixture with failed and successful events. | Medium: suspicious sequence, not proof of compromise. | yes |
| Which hosts contacted known malicious IPs today? | ioc_correlation | Demonstrates local IOC lookup dependency. | Network traffic plus local malicious-IP lookup fixture. | High: IOC source and match semantics must be explicit. | yes |
| Which DNS queries look like DGA activity? | dns_beaconing_dga_behavior | Demonstrates behavioral detection governance. | DNS fixture plus vetted DGA detection result/logic. | High: no ad hoc LLM-generated detection SPL. | yes |
| Which logs are missing from key security sources? | data_source_health | Shows safe metadata/source-health value before query expansion. | Source freshness fixture. | Medium: metadata-only, no event search execution. | yes |
| Which hosts showed both process execution and suspicious DNS within 24 hours? | multi_signal_correlation | Demonstrates multi-source evidence composition with provenance. | Endpoint process and DNS fixtures. | High: correlation must keep source lineage visible. | yes |

## Next Implementation Recommendation

Do not implement runtime behavior from this document. The next implementation step is Stage 3K-Q1 safety work:

1. Extend the SPL validator and template schema before CIM-first implementation.
   - The current validator expects raw-search shapes.
   - CIM/tstats/datamodel query shapes need explicit allowlists, time bounds, field allowlists, result limits, and blocked-command enforcement.
   - Template schema should distinguish raw-search, `tstats`, and data-model query shapes before any template is executable.

2. Confirm source readiness and dependencies with the SOC/Splunk team.
   - Use the six validation questions above.
   - Pick only 6-8 first-demo questions, not the full list.

3. Map behavioral questions to vetted detections.
   - Beaconing, DGA, lateral movement, PowerShell, persistence, webshell, and exfiltration patterns require approved detection logic or fixture-backed detection results.

4. Keep LLM/MCP/SPL governance unchanged.
   - LLMs must not call MCP directly.
   - Candidate SPL must not execute.
   - No LLM final synthesis or Answer Guard runtime path should be enabled by this taxonomy work.

## Counts

- Input questions read: 105.
- Questions classified: 105.
- Pattern counts:
  - top_n_aggregation: 9
  - threshold_anomaly: 13
  - time_trend: 0
  - new_or_unusual_source: 14
  - success_after_failure: 2
  - ioc_correlation: 8
  - threat_intel_enrichment: 1
  - notable_risk_lookup: 5
  - case_state_lookup: 3
  - asset_identity_context: 5
  - dns_beaconing_dga_behavior: 10
  - lateral_movement: 3
  - suspicious_process_powershell: 12
  - persistence_scheduled_task_service: 3
  - data_source_health: 2
  - cloud_activity: 0
  - dlp_exfiltration: 6
  - multi_signal_correlation: 8
  - safe_metadata_discovery: 0
  - other_or_unclear: 1
- High-governance-risk questions: 58.
- Questions needing IOC/threat intel: 9.
- Behavioral-detection questions: 71.
- Questions needing ES notable/risk: 8.
- Questions needing asset/identity enrichment: 14.
- `blocked_external` dependency questions: 23.
- `unknown` dependency questions: 39.
- `blocked_external` plus `unknown` dependency questions: 62.
