# G5 evidence-precondition drafts (LLM-assisted, COE review)

- Generated: `2026-06-17T10:52:50.843528+00:00`  Model: `foundation-sec-1.1-8b-instruct-q8_0.gguf`
- Techniques: **83**  Validation: `off_vocab`=1, `valid`=82

> deterministic — these are LLM proposals for COE review; NOT applied to mitre_attack_subset.json or mitre_evidence_preconditions.py by this script

| techniqueID | tactic | proposed_key | validation | candidate_rule |
|---|---|---|---|---|
| `T1001` | Command and Control | `defense_evasion_evidence` | valid | Unusual network traffic patterns indicative of obfuscation techniques. |
| `T1003` | Credential Access | `credential_dumping_evidence` | valid | Anomalous process accessing LSASS memory. |
| `T1003.001` | Credential Access | `credential_dumping_evidence` | valid | Unusual process accessing LSASS memory. |
| `T1003.002` | Credential Access | `credential_dumping_evidence` | valid | Unusual access to the SAM database or Registry keys associated with credential storage. |
| `T1003.003` | Credential Access | `credential_dumping_evidence` | valid | Unusual access to the NTDS.dit file on a domain controller. |
| `T1016` | Discovery | `discovery_evidence` | valid | Unusual network configuration discovery tool execution. |
| `T1020` | Exfiltration | `outbound_transfer` | valid | Automated data transfer patterns detected outside the network. |
| `T1021` | Lateral Movement | `lateral_movement_evidence` | valid | Unusual remote service login from an unexpected source. |
| `T1021.001` | Lateral Movement | `lateral_movement_evidence` | valid | RDP login from an unusual location or device. |
| `T1021.002` | Lateral Movement | `lateral_movement_evidence` | valid | SMB connection from an unusual source to a sensitive share. |
| `T1021.003` | Lateral Movement | `lateral_movement_evidence` | valid | Unusual process execution on a remote host from a source not typically used for RDP or sim |
| `T1021.004` | Lateral Movement | `lateral_movement_evidence` | valid | SSH login from an unusual location or account. |
| `T1027` | Stealth | `defense_evasion_evidence` | valid | File with unusual characteristics detected during scanning. |
| `T1036` | Stealth | `defense_evasion_evidence` | valid | Executable with mismatching file metadata detected. |
| `T1036.004` | Stealth | `persistence_evidence` | valid | New service created with a name resembling benign Windows services. |
| `T1036.005` | Stealth | `defense_evasion_evidence` | valid | File placed in a trusted directory with unusual attributes or permissions. |
| `T1037` | Persistence | `persistence_evidence` | valid | Execution of a script during system boot or user logon that is not recognized as standard  |
| `T1040` | Credential Access | `network_telemetry` | valid | Unusual network traffic patterns indicative of data capture from network interfaces. |
| `T1041` | Exfiltration | `network_telemetry` | valid | Unusual data transfer patterns to a known C2 IP address. |
| `T1046` | Discovery | `discovery_evidence` | valid | Unusual network service scan activity detected. |
| `T1047` | Execution | `process_execution_evidence` | valid | Execution of WMI commands or scripts not associated with known administrative tasks. |
| `T1049` | Discovery | `discovery_evidence` | valid | Unusual network connection enumeration activity detected. |
| `T1053.003` | Execution | `persistence_evidence` | valid | New cron job added to crontab file with suspicious command execution. |
| `T1053.005` | Execution | `process_execution_evidence` | valid | Execution of schtasks.exe or creation of new scheduled tasks not associated with known ben |
| `T1055` | Privilege Escalation | `process_execution_evidence` | valid | Unusual process execution with parent-child relationship not seen before. |
| `T1055.002` | Privilege Escalation | `process_execution_evidence` | valid | Execution of a suspicious portable executable within a process. |
| `T1055.003` | Privilege Escalation | `process_execution_evidence` | valid | Process with unusual behavior detected, potentially indicating code injection. |
| `T1056` | Collection | `collection_evidence` | valid | Unusual process capturing keyboard input or monitoring system dialogs. |
| `T1057` | Discovery | `discovery_evidence` | valid | Unusual process enumeration activity detected. |
| `T1059.003` | Execution | `process_execution_evidence` | valid | Execution of cmd.exe or similar command-line interpreters not associated with typical user |
| `T1059.007` | Execution | `process_execution_evidence` | valid | Execution of JavaScript or JScript from an unusual location or with suspicious arguments. |
| `T1070.003` | Stealth | `defense_evasion_evidence` | valid | Unusual command history deletion activity detected. |
| `T1070.004` | Stealth | `defense_evasion_evidence` | valid | Unusual file deletion activity detected. |
| `T1071.001` | Command and Control | `network_telemetry` | valid | Unusual outbound network traffic matching web protocol patterns. |
| `T1071.002` | Command and Control | `network_telemetry` | valid | Unusual SMB traffic to an external server. |
| `T1074` | Collection | `collection_evidence` | valid | Unusual data file activity in a central staging directory. |
| `T1078.002` | Initial Access | `initial_access_evidence` | valid | Login from an unusual location or device for a domain account. |
| `T1078.004` | Initial Access | `initial_access_evidence` | valid | Unusual login activity from a cloud account not associated with typical user behavior. |
| `T1082` | Discovery | `discovery_evidence` | valid | Unusual system information queries from an uncommon source. |
| `T1083` | Discovery | `discovery_evidence` | valid | Enumeration of file and directory structure from an unusual user or process. |
| `T1090` | Command and Control | `network_telemmetry` | off_vocab | Unusual network traffic patterns to an external server not associated with known business  |
| `T1090.002` | Command and Control | `network_telemetry` | valid | Unusual network traffic patterns to an external proxy IP address. |
| `T1090.003` | Command and Control | `network_telemetry` | valid | Unusual network traffic patterns indicative of multi-hop proxy usage. |
| `T1095` | Command and Control | `network_telemetry` | valid | Unusual network traffic using a non-standard protocol for the given environment. |
| `T1098` | Persistence | `persistence_evidence` | valid | Unusual account permission changes detected. |
| `T1098.001` | Persistence | `persistence_evidence` | valid | New service principal or application credentials added to a cloud account without prior au |
| `T1098.002` | Persistence | `persistence_evidence` | valid | Unusual PowerShell cmdlet usage adding mailbox permissions. |
| `T1105` | Command and Control | `network_telemetry` | valid | Unusual network traffic to an external IP matching known C2 patterns. |
| `T1110.002` | Credential Access | `credential_dumping_evidence` | valid | Unusual process accessing LSASS memory or suspicious access to credential stores. |
| `T1110.004` | Credential Access | `credential_access_evidence` | valid | Multiple failed login attempts using common credential pairs from a single source. |
| `T1112` | Defense Impairment | `defense_evasion_evidence` | valid | Registry modification by an unusual process or user. |
| `T1132` | Command and Control | `network_telemetry` | valid | Unusual Base64 encoded data in network traffic. |
| `T1133` | Initial Access | `initial_access_evidence` | valid | Unusual login activity from an external IP address to a remote service gateway. |
| `T1190` | Initial Access | `initial_access_evidence` | valid | Unusual traffic pattern to a public-facing application indicating potential exploitation a |
| `T1204.002` | Execution | `process_execution_evidence` | valid | Execution of an unusual file type by a user in a non-standard location. |
| `T1210` | Lateral Movement | `lateral_movement_evidence` | valid | Unusual network traffic to a remote service not typically accessed by this user or host. |
| `T1222` | Defense Impairment | `defense_evasion_evidence` | valid | Unusual modification of file or directory permissions outside of normal business hours. |
| `T1498` | Impact | `impact_evidence` | valid | Unusual network traffic patterns indicative of a potential DoS attack. |
| `T1498.001` | Impact | `impact_evidence` | valid | Unusually high network traffic volume to a specific target. |
| `T1499` | Impact | `impact_evidence` | valid | Unusual spike in system resource usage or repeated crashes of critical services. |
| `T1505.003` | Persistence | `persistence_evidence` | valid | Web server file modification outside of normal maintenance window. |
| `T1539` | Credential Access | `credential_access_evidence` | valid | Unusual access to session cookies in user directories. |
| `T1543` | Persistence | `persistence_evidence` | valid | New or modified system process not associated with known software. |
| `T1543.001` | Persistence | `persistence_evidence` | valid | New or modified .plist files in LaunchAgents directories. |
| `T1543.002` | Persistence | `persistence_evidence` | valid | New systemd service unit created or modified outside of normal maintenance window. |
| `T1543.003` | Persistence | `persistence_evidence` | valid | New or modified Windows service detected with an unusual executable path. |
| `T1547.001` | Persistence | `persistence_evidence` | valid | New or modified entry in the Registry run keys or startup folder. |
| `T1556` | Credential Access | `credential_access_evidence` | valid | Unusual access to LSASS or SAM process. |
| `T1560.001` | Collection | `collection_evidence` | valid | Execution of data compression utility followed by unusual network activity. |
| `T1564.001` | Stealth | `defense_evasion_evidence` | valid | File or directory attributes changed to hide from normal view. |
| `T1565.001` | Impact | `impact_evidence` | valid | Unusual modification of critical database files. |
| `T1567` | Exfiltration | `outbound_transfer` | valid | Unusual outbound traffic to a web service not typically used for business operations. |
| `T1567.002` | Exfiltration | `outbound_transfer` | valid | Data transfer to an unusual cloud storage service destination. |
| `T1568` | Command and Control | `network_telemetry` | valid | Unusual network traffic patterns to dynamic IP addresses or domains. |
| `T1568.002` | Command and Control | `network_telemetry` | valid | Unusual DNS queries to multiple domains with rapid succession from a single host. |
| `T1569.002` | Execution | `process_execution_evidence` | valid | Execution of an unexpected service via services.exe or sc.exe. |
| `T1570` | Lateral Movement | `lateral_movement_evidence` | valid | File transfer between hosts not associated with normal operations. |
| `T1571` | Command and Control | `network_telemetry` | valid | Unusual network traffic on non-standard port for a given protocol. |
| `T1572` | Command and Control | `network_telemetry` | valid | Unusual network traffic patterns indicative of protocol tunneling. |
| `T1573` | Command and Control | `network_telemetry` | valid | Unusual encrypted network traffic patterns to an uncommon destination. |
| `T1583.001` | Resource Development | `resource_development_evidence` | valid | New domain registration without a clear business purpose. |
| `T1583.003` | Resource Development | `resource_development_evidence` | valid | New virtual private server (VPS) provisioned in an unusual location or with suspicious con |
| `T1595` | Reconnaissance | `recon_evidence` | valid | Unusual network scanning activity detected from an external IP address. |
