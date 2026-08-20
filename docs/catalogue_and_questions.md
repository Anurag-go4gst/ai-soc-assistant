# Catalogue and questions — reference index

**Generated** by `scripts/build_catalogue_question_index.py`. Do not hand-edit;
regenerate instead. Machine-readable copy: `docs/evals/catalogue_question_index.json`.

- Use cases: **42** (35 bindable, 34 with an SPL template)
- Questions: **105** (10 bind a use case)

A use case with no `intent_patterns` is **unbindable by design** — the `sample_*`
entries exist as SPL template-registry bindings, not as things user text can match.

## Use cases

| use case | skill | SPL template | bindable | serves a 105 question | patterns |
|---|---|---|---|---|---|
| `auth_failed_login_spike` | attack_discovery | `auth_failed_login_spike` | yes | yes | `failed login`, `failed logins`, `failure`, `failures` (+2) |
| `auth_success_after_failure` | attack_discovery | `auth_success_after_failure` | yes | yes | `successful login after`, `successful vpn login after`, `successful vpn logins after`, `success after` (+8) |
| `auth_new_source_ip_login` | attack_discovery | `auth_new_source_ip` | yes | no | `new source ip`, `new source`, `unusual source`, `unusual source ips` |
| `auth_privileged_login_anomaly` | attack_discovery | `privileged_account_failure` | yes | no | `privileged account`, `admin login`, `privileged login` |
| `auth_account_lockout_trend` | alert_summary | `auth_account_lockout_trend` | yes | no | `lockout`, `lockouts`, `account_locked` |
| `auth_mfa_failure_spike` | attack_discovery | `auth_mfa_failure_spike` | yes | yes | `mfa failure`, `mfa failures` |
| `auth_after_hours_critical_asset` | attack_discovery | `after_hours_login_critical_asset` | yes | no | `after-hours login`, `after hours login`, `critical asset after hours` |
| `net_firewall_deny_spike` | attack_discovery | `firewall_deny_spike` | yes | no | `firewall deny`, `deny spike` |
| `net_vpn_login_anomaly` | attack_discovery | `vpn_failure_spike` | yes | no | `vpn login`, `vpn anomaly` |
| `dns_beaconing_candidate` | attack_discovery | `dns_beaconing_candidate` | yes | yes | `beaconing`, `beacon pattern`, `dns beaconing`, `beaconing candidate` |
| `critical_notable_mitre_review` | attack_discovery | `notable_critical_review_mitre` | yes | no | `critical alerts`, `critical alert`, `unpatched cve`, `unpatched cves` (+3) |
| `edr_suspicious_process` | attack_discovery | `edr_suspicious_process` | yes | yes | `suspicious process` |
| `edr_powershell_suspicious_command` | attack_discovery | `edr_powershell_suspicious_command` | yes | yes | `powershell suspicious`, `suspicious powershell` |
| `soc_show_sop` | knowledge_recall | — | yes | no | `sop`, `playbook`, `runbook`, `standard operating procedure` (+10) |
| `soc_show_catalogue_index` | knowledge_recall | — | yes | no | `what questions do you support`, `what's in the catalogue`, `whats in the catalogue`, `what is in the catalogue` (+7) |
| `aws_security_group_modifications` | spl_generation | `aws_security_group_modifications` | yes | no | `aws security group`, `security group modifications`, `security groups`, `cloudtrail security group` (+2) |
| `aws_console_success_logins_by_user` | spl_generation | `aws_console_success_logins_by_user` | yes | no | `aws console logins`, `aws console login`, `successful aws console`, `console logins by user` (+2) |
| `aws_iam_policy_modifications` | spl_generation | `aws_iam_policy_modifications` | yes | no | `aws iam policies`, `iam policies`, `iam policy modifications`, `attached policies` (+3) |
| `auth_failed_login_top_users_exclude_service_accounts` | attack_discovery | `auth_failed_login_top_users_exclude_service_accounts` | yes | no | `top users with failed login count`, `failed login count`, `exclude service accounts`, `excluding service accounts` (+1) |
| `soc_generate_spl` | spl_generation | — | yes | no | `generate spl for`, `write spl for`, `create spl for`, `produce spl for` (+7) |
| `soc_explain_spl` | knowledge_recall | — | yes | no | `explain spl` |
| `soc_optimize_spl` | spl_generation | — | yes | no | `optimize spl` |
| `soc_map_alert_mitre` | mitre_mapping | — | yes | no | `mitre`, `att&ck`, `mitre technique`, `attack technique` (+6) |
| `soc_compare_past_incidents` | knowledge_recall | — | yes | no | `past incidents`, `compare current alert` |
| `cisco_cleartext_to_rtu` | attack_discovery | `cisco_cleartext_to_rtu` | yes | no | `cleartext http`, `cleartext vnc`, `cleartext telnet`, `cleartext ftp` (+4) |
| `cisco_stealthwatch_scan_with_asset` | attack_discovery | `cisco_stealthwatch_scan_with_asset` | yes | no | `stealthwatch`, `horizontal scan`, `substation automation` |
| `cisco_duo_mfa_fatigue` | attack_discovery | `cisco_duo_mfa_fatigue` | yes | no | `duo`, `mfa fatigue`, `push denied` |
| `ot_firmware_drift` | attack_discovery | `ot_firmware_drift` | yes | no | `firmware drift`, `asset lookup`, `network banner` |
| `ot_master_spoof` | attack_discovery | `ot_master_spoof` | yes | no | `master station`, `broadcast polling`, `transformer` |
| `ot_tftp_hmi` | attack_discovery | `ot_tftp_hmi` | yes | no | `tftp`, `hmi tftp`, `tftp backup`, `configuration backup` |
| `physical_access_impossible` | attack_discovery | `physical_access_impossible` | yes | no | `physical badge`, `impossible travel`, `substation login` |
| `cii_scan_detection` | attack_discovery | `cii_scan_detection` | yes | no | `cii`, `critical infrastructure scan` |
| `loto_breaker_correlation` | attack_discovery | `loto_breaker_correlation` | yes | no | `loto`, `breaker command`, `manual repair` |
| `cert_in_hash_match` | attack_discovery | `cert_in_hash_match` | yes | no | `cert-in`, `file hash`, `advisory` |
| `soc_environment_hygiene` | knowledge_recall | — | yes | no | `environment hygiene`, `log generation formats`, `ingest latency indicators`, `storage pool` (+4) |
| `sample_network_top_outbound_src` | spl_generation | `sample_network_top_outbound_src_tstats` | no | no | — |
| `sample_dns_top_query_hosts` | spl_generation | `sample_dns_top_query_hosts_from_datamodel` | no | no | — |
| `sample_auth_failed_login_top_users` | spl_generation | `sample_auth_failed_login_top_users_tstats` | no | no | — |
| `sample_ioc_correlation_indicator_match` | spl_generation | `sample_ioc_correlation_indicator_match` | no | no | — |
| `sample_threshold_anomaly_volume_spike` | spl_generation | `sample_threshold_anomaly_volume_spike` | no | no | — |
| `sample_powershell_suspicious_execution` | spl_generation | `sample_powershell_suspicious_execution` | no | no | — |
| `sample_dlp_exfiltration_volume` | spl_generation | `sample_dlp_exfiltration_volume` | no | no | — |

## Questions

| ref | question | binds | coverage |
|---|---|---|---|
| `q0.q001` | What incident or alert network events are high or critical right now? | — | — |
| `q0.q002` | Which source IPs generated the most outbound connections? | — | — |
| `q0.q003` | Which destination IPs received the most connections? | — | — |
| `q0.q004` | Which hosts contacted known malicious IPs today? | — | — |
| `q0.q005` | Which hosts contacted suspicious external domains? | — | — |
| `q0.q006` | Which DNS queries have unusually long names? | — | — |
| `q0.q007` | Which DNS queries look like DGA activity? | — | — |
| `q0.q008` | Which hosts show possible beaconing behavior? | `dns_beaconing_candidate` | 0.5152 |
| `q0.q009` | Which hosts communicated with many unique external IPs? | — | — |
| `q0.q010` | Which hosts are generating the most SMB traffic? | — | — |
| `q0.q011` | Which hosts made SMB connections to many peers? | — | — |
| `q0.q012` | Which systems used unusual destination ports? | — | — |
| `q0.q013` | Which systems generated large outbound data transfers? | — | — |
| `q0.q014` | Which hosts showed potential data exfiltration to cloud apps? | — | — |
| `q0.q015` | Which hosts have repeated connections to rare destinations? | — | — |
| `q0.q016` | Which hosts contacted the same external IP many times? | — | — |
| `q0.q017` | Which hosts generated the most DNS queries? | — | — |
| `q0.q018` | Which domains were queried by multiple hosts? | — | — |
| `q0.q019` | Which hosts queried domains with suspicious subdomains? | — | — |
| `q0.q020` | Which networks saw traffic to high-risk ports? | — | — |
| `q0.q021` | Which hosts communicated with foreign IP ranges? | — | — |
| `q0.q022` | Which hosts contacted IPs in an IOC lookup? | — | — |
| `q0.q023` | Which hosts showed possible command-and-control beaconing? | `dns_beaconing_candidate` | 0.5152 |
| `q0.q024` | Which internal hosts generated outbound traffic after DNS lookups? | — | — |
| `q0.q025` | Which hosts used unusual protocols? | — | — |
| `q0.q026` | Which hosts have unusually high connection counts to one destination? | — | — |
| `q0.q027` | Which DNS queries resolved to suspicious top-level domains? | — | — |
| `q0.q028` | Which hosts showed peer-to-peer style communication? | — | — |
| `q0.q029` | Which systems accessed the internet through rare ports? | — | — |
| `q0.q030` | Which hosts contacted external IPs after hours? | — | — |
| `q0.q031` | Which hosts repeatedly contacted the same destination at regular intervals? | — | — |
| `q0.q032` | Which hosts had both DNS and network anomalies? | — | — |
| `q0.q033` | Which hosts communicated with suspicious destination domains and IPs? | — | — |
| `q0.q034` | Which destination IPs were contacted by many hosts? | — | — |
| `q0.q035` | Which hosts generated the largest DNS response volumes? | — | — |
| `q0.q036` | Which hosts reached known malicious domains from lookup data? | — | — |
| `q0.q037` | Which hosts showed likely proxy or tunneling behavior? | — | — |
| `q0.q038` | Which hosts had large inbound traffic from a single source? | — | — |
| `q0.q039` | Which hosts downloaded large volumes from the internet? | — | — |
| `q0.q040` | Which hosts initiated traffic to rare countries? | — | — |
| `q0.q041` | Which systems have repeated hits to the same suspicious URL path? | — | — |
| `q0.q042` | Which hosts contacted both malicious IPs and domains? | — | — |
| `q0.q043` | Which hosts show consistent low-volume outbound connections? | — | — |
| `q0.q044` | Which rules are generating the most alerts? | — | — |
| `q0.q045` | What happened for this specific notable event? | — | — |
| `q0.q046` | Which users have excessive failed logins? | `auth_failed_login_spike` | 1.5103 |
| `q0.q047` | Is one IP attacking many accounts? | — | — |
| `q0.q048` | Did a user log in from impossible locations? | — | — |
| `q0.q049` | Which hosts ran suspicious PowerShell? | `edr_powershell_suspicious_command` | 1.1598 |
| `q0.q050` | Did Office apps spawn cmd or PowerShell? | — | — |
| `q0.q051` | What unusual processes ran on critical servers? | — | — |
| `q0.q052` | Did any host contact known malicious IPs? | — | — |
| `q0.q053` | Are there suspicious DNS queries indicating C2 or DGA behavior? | — | — |
| `q0.q054` | Who is sending large amounts of data outbound? | — | — |
| `q0.q055` | Did anyone get added to Administrators? | — | — |
| `q0.q056` | Which users are logging in outside normal hours? | — | — |
| `q0.q057` | Did any endpoint run this suspicious hash? | — | — |
| `q0.q058` | Which users or hosts have the highest risk scores? | — | — |
| `q0.q059` | Which source IPs generated the most authentication failures today? | `auth_failed_login_spike` | 0.5427 |
| `q0.q060` | Which accounts had a successful login after repeated failures? | `auth_success_after_failure` | 2.626 |
| `q0.q061` | Which users logged in from new countries today? | — | — |
| `q0.q062` | Which hosts show a spike in failed logins? | `auth_failed_login_spike` | 1.1327 |
| `q0.q063` | Which endpoints spawned script interpreters recently? | — | — |
| `q0.q064` | Which hosts executed encoded PowerShell commands? | — | — |
| `q0.q065` | Which endpoints created new scheduled tasks? | — | — |
| `q0.q066` | Which systems contacted rare external destinations? | — | — |
| `q0.q067` | Which hosts are generating unusual DNS query volumes? | — | — |
| `q0.q068` | Which internal hosts contacted known command-and-control domains? | — | — |
| `q0.q069` | Which users accessed privileged applications unusually? | — | — |
| `q0.q070` | Which users changed their password multiple times in a short window? | — | — |
| `q0.q071` | Which accounts were disabled or re-enabled today? | — | — |
| `q0.q072` | Which hosts show signs of lateral movement? | — | — |
| `q0.q073` | Which systems had multiple remote service creations? | — | — |
| `q0.q074` | Which hosts show SMB connections to many peers? | — | — |
| `q0.q075` | Which endpoints created suspicious archive files? | — | — |
| `q0.q076` | Which hosts uploaded large amounts of data to cloud services? | — | — |
| `q0.q077` | Which endpoints accessed USB storage recently? | — | — |
| `q0.q078` | Which systems had repeated malware detections? | — | — |
| `q0.q079` | Which files were modified by suspicious processes? | `edr_suspicious_process` | 0.8284 |
| `q0.q080` | Which hosts spawned shells from email clients? | — | — |
| `q0.q081` | Which users received and opened phishing attachments? | — | — |
| `q0.q082` | Which domains were queried by multiple hosts in a short period? | — | — |
| `q0.q083` | Which hosts have suspicious parent-child process chains? | — | — |
| `q0.q084` | Which accounts have the most risk events? | — | — |
| `q0.q085` | Which assets have accumulated risk from multiple detections? | — | — |
| `q0.q086` | Which users were involved in both failed logins and privilege changes? | `auth_failed_login_spike` | 0.8238 |
| `q0.q087` | Which hosts are communicating with unusual ports externally? | — | — |
| `q0.q088` | Which endpoints have multiple persistence indicators? | — | — |
| `q0.q089` | Which users authenticated to VPN after repeated MFA failures? | `auth_mfa_failure_spike` | 1.1445 |
| `q0.q090` | Which assets are generating the most notable events? | — | — |
| `q0.q091` | Which alerts are still open and unresolved? | — | — |
| `q0.q092` | Which users had access to sensitive systems and then large outbound transfers? | — | — |
| `q0.q093` | Which hosts showed both process execution and suspicious DNS within 24 hours? | — | — |
| `q0.q094` | Which logs are missing from key security sources? | — | — |
| `q0.q095` | Which sources stopped sending events recently? | — | — |
| `q0.q096` | Which users performed privileged actions from non-admin workstations? | — | — |
| `q0.q097` | Which systems show signs of webshell activity? | — | — |
| `q0.q098` | Which hosts downloaded executables from the internet? | — | — |
| `q0.q099` | Which detections involved the same user and host repeatedly? | — | — |
| `q0.q100` | Which users triggered multiple different detections? | — | — |
| `q0.q101` | Which devices are generating the most endpoint alerts? | — | — |
| `q0.q102` | Which users are accessing resources from unusual hosts? | — | — |
| `q0.q103` | For any flagged host or user, what is its asset criticality, business owner, and identity/privilege status? | — | — |
| `q0.q104` | What is the full activity timeline for a given entity in the N hours before and after a detection? | — | — |
| `q0.q105` | Has this entity, IP, domain, or notable been seen or investigated before, and what was the prior disposition? | — | — |
