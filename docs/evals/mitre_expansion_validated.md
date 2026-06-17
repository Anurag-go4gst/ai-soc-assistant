# MITRE expansion-candidate validation (plan §15 G3)

- Generated: `2026-06-17T05:27:03.900703+00:00`
- Audit source: `docs/evals/out/llm_mitre_catalogue_audit.json`
- Bundle techniques (excluded): **15**
- Expansion candidates: **96**
- Resolver operational: **True**

Dispositions: `not_found`=13, `promote_candidate`=83

> Candidates = union of all `results[*].llm_invalid_ids` (out-of-subset proposals) minus the local 13-technique bundle. No `expansion` bucket exists in the audit JSON; this set is derived. Until the STIX bundle is onboarded, every row is `pending_bundle` (honest, not a fabricated promote/drop).

| techniqueID | disposition | name |
|---|---|---|
| `T0819` | not_found |  |
| `T0839` | not_found |  |
| `T0849` | not_found |  |
| `T0881` | not_found |  |
| `T1001` | promote_candidate | Data Obfuscation |
| `T1003` | promote_candidate | OS Credential Dumping |
| `T1003.001` | promote_candidate | OS Credential Dumping: LSASS Memory |
| `T1003.002` | promote_candidate | OS Credential Dumping: Security Account Manager |
| `T1003.003` | promote_candidate | OS Credential Dumping: NTDS |
| `T1016` | promote_candidate | System Network Configuration Discovery |
| `T1020` | promote_candidate | Automated Exfiltration |
| `T1021` | promote_candidate | Remote Services |
| `T1021.001` | promote_candidate | Remote Services: Remote Desktop Protocol |
| `T1021.002` | promote_candidate | Remote Services: SMB/Windows Admin Shares |
| `T1021.003` | promote_candidate | Remote Services: Distributed Component Object Model |
| `T1021.004` | promote_candidate | Remote Services: SSH |
| `T1022` | not_found |  |
| `T1027` | promote_candidate | Obfuscated Files or Information |
| `T1036` | promote_candidate | Masquerading |
| `T1036.004` | promote_candidate | Masquerading: Masquerade Task or Service |
| `T1036.005` | promote_candidate | Masquerading: Match Legitimate Resource Name or Location |
| `T1037` | promote_candidate | Boot or Logon Initialization Scripts |
| `T1040` | promote_candidate | Network Sniffing |
| `T1041` | promote_candidate | Exfiltration Over C2 Channel |
| `T1043` | not_found |  |
| `T1045` | not_found |  |
| `T1046` | promote_candidate | Network Service Discovery |
| `T1047` | promote_candidate | Windows Management Instrumentation |
| `T1049` | promote_candidate | System Network Connections Discovery |
| `T1053.003` | promote_candidate | Scheduled Task/Job: Cron |
| `T1053.004` | not_found |  |
| `T1053.005` | promote_candidate | Scheduled Task/Job: Scheduled Task |
| `T1055` | promote_candidate | Process Injection |
| `T1055.002` | promote_candidate | Process Injection: Portable Executable Injection |
| `T1055.003` | promote_candidate | Process Injection: Thread Execution Hijacking |
| `T1056` | promote_candidate | Input Capture |
| `T1057` | promote_candidate | Process Discovery |
| `T1059.003` | promote_candidate | Command and Scripting Interpreter: Windows Command Shell |
| `T1059.007` | promote_candidate | Command and Scripting Interpreter: JavaScript |
| `T1070.001` | not_found |  |
| `T1070.003` | promote_candidate | Indicator Removal: Clear Command History |
| `T1070.004` | promote_candidate | Indicator Removal: File Deletion |
| `T1071.001` | promote_candidate | Application Layer Protocol: Web Protocols |
| `T1071.002` | promote_candidate | Application Layer Protocol: File Transfer Protocols |
| `T1074` | promote_candidate | Data Staged |
| `T1078.002` | promote_candidate | Valid Accounts: Domain Accounts |
| `T1078.004` | promote_candidate | Valid Accounts: Cloud Accounts |
| `T1082` | promote_candidate | System Information Discovery |
| `T1083` | promote_candidate | File and Directory Discovery |
| `T1086` | not_found |  |
| `T1090` | promote_candidate | Proxy |
| `T1090.002` | promote_candidate | Proxy: External Proxy |
| `T1090.003` | promote_candidate | Proxy: Multi-hop Proxy |
| `T1095` | promote_candidate | Non-Application Layer Protocol |
| `T1098` | promote_candidate | Account Manipulation |
| `T1098.001` | promote_candidate | Account Manipulation: Additional Cloud Credentials |
| `T1098.002` | promote_candidate | Account Manipulation: Additional Email Delegate Permissions |
| `T1105` | promote_candidate | Ingress Tool Transfer |
| `T1110.002` | promote_candidate | Brute Force: Password Cracking |
| `T1110.004` | promote_candidate | Brute Force: Credential Stuffing |
| `T1112` | promote_candidate | Modify Registry |
| `T1132` | promote_candidate | Data Encoding |
| `T1133` | promote_candidate | External Remote Services |
| `T1190` | promote_candidate | Exploit Public-Facing Application |
| `T1193` | not_found |  |
| `T1204.002` | promote_candidate | User Execution: Malicious File |
| `T1210` | promote_candidate | Exploitation of Remote Services |
| `T1222` | promote_candidate | File and Directory Permissions Modification |
| `T1498` | promote_candidate | Network Denial of Service |
| `T1498.001` | promote_candidate | Network Denial of Service: Direct Network Flood |
| `T1499` | promote_candidate | Endpoint Denial of Service |
| `T1505.003` | promote_candidate | Server Software Component: Web Shell |
| `T1539` | promote_candidate | Steal Web Session Cookie |
| `T1543` | promote_candidate | Create or Modify System Process |
| `T1543.001` | promote_candidate | Create or Modify System Process: Launch Agent |
| `T1543.002` | promote_candidate | Create or Modify System Process: Systemd Service |
| `T1543.003` | promote_candidate | Create or Modify System Process: Windows Service |
| `T1547.001` | promote_candidate | Boot or Logon Autostart Execution: Registry Run Keys / Startup Folder |
| `T1556` | promote_candidate | Modify Authentication Process |
| `T1560.001` | promote_candidate | Archive Collected Data: Archive via Utility |
| `T1562` | not_found |  |
| `T1562.001` | not_found |  |
| `T1564.001` | promote_candidate | Hide Artifacts: Hidden Files and Directories |
| `T1565.001` | promote_candidate | Data Manipulation: Stored Data Manipulation |
| `T1567` | promote_candidate | Exfiltration Over Web Service |
| `T1567.002` | promote_candidate | Exfiltration Over Web Service: Exfiltration to Cloud Storage |
| `T1568` | promote_candidate | Dynamic Resolution |
| `T1568.002` | promote_candidate | Dynamic Resolution: Domain Generation Algorithms |
| `T1569.002` | promote_candidate | System Services: Service Execution |
| `T1570` | promote_candidate | Lateral Tool Transfer |
| `T1571` | promote_candidate | Non-Standard Port |
| `T1572` | promote_candidate | Protocol Tunneling |
| `T1573` | promote_candidate | Encrypted Channel |
| `T1583.001` | promote_candidate | Acquire Infrastructure: Domains |
| `T1583.003` | promote_candidate | Acquire Infrastructure: Virtual Private Server |
| `T1595` | promote_candidate | Active Scanning |
