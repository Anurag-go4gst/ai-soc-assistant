# Rejected GitHub Skills (and rejected sections)

Reference repo: `mukul975/Anthropic-Cybersecurity-Skills`  
Register: [`github_skill_intake_register.json`](github_skill_intake_register.json)

Skills listed here should not be re-reviewed without cause. **Partial accepts** log rejected *sections* of an otherwise accepted skill.

## Rejection reason codes

| Code | Meaning |
|------|---------|
| `offensive_only` | Primary purpose is attack/offense, not defensive investigation |
| `unsafe_execution_steps` | Requires steps unsafe for governed assistant |
| `arbitrary_shell_or_curl` | Depends on arbitrary shell/curl/API execution at runtime |
| `not_relevant_to_soc_assistant` | Outside SOC analyst assistant scope |
| `duplicate_of_existing_skill` | Redundant with accepted skill or internal use case |
| `too_tool_specific` | Tied to unavailable vendor/tool we do not support |
| `too_token_heavy` | Body too large to curate into bounded enrichment |
| `requires_unavailable_data_source` | Needs telemetry we do not model |
| `no_clear_evidence_model` | Cannot map to evidence fields / preconditions |
| `not_suitable_for_client_demo` | Unsafe or inappropriate for experience center |
| `future_phase` | Valid later; not current pilot scope |

## Rejected skills

| GitHub Skill | Path | Decision | Rejection Reason | Safety Concern | Future Revisit? | Notes |
| ------------ | ---- | -------- | ---------------- | -------------- | --------------- | ----- |
| *(none — full skill rejections in batch 1)* | | | | | | |

## Rejected sections (parent skill partially accepted)

| GitHub Skill | Path | Decision | Rejection Reason | Safety Concern | Future Revisit? | Notes |
| ------------ | ---- | -------- | ---------------- | -------------- | --------------- | ----- |
| `analyzing-ransomware-encryption-mechanisms` | `skills/analyzing-ransomware-encryption-mechanisms/SKILL.md` | `partial_reject` | `offensive_only`, `unsafe_execution_steps` | Malware RE / decryptor tooling | No | Parent skill **accepted** for defensive impact evidence (P7). Do not import Ghidra, reverse-engineering, or decryptor workflow steps. |

## Policy (summary)

Rejected:

- Any skill whose primary purpose is exploit execution, credential theft, persistence creation, malware deployment, C2 setup, or evasion.
- Any skill that requires arbitrary shell execution in runtime.
- Any skill that cannot be converted into defensive investigation guidance.
