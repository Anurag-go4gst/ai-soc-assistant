# LangGraph dual-run parity summary (Phase 13)

Evaluation only — imperative `/chat` remains live runtime; `LANGGRAPH_ORCHESTRATION_ENABLED=false`.

- Generated: `2026-07-25T10:08:01.735323+00:00`
- Schema: `2026-06-08-phase13-v1`
- Total evaluated: **120** (expected minimum **120**)
- Exact matches: **0**
- Acceptable differences: **85**
- Mismatches: **35**

## Safety signals

- Graph enabled execution: **0**
- Graph MITRE evidence upgrade vs imperative: **0**
- Graph SPL generation when imperative blocked: **31**
- Graph runtime_active upgrade: **0**

## Mismatch categories

- `path_type_runtime_active`: 12
- `spl_generation_mismatch`: 31
- `unsafe_hil_mismatch`: 1

## Top failing scenarios

- `q0.q001` — ['spl_generation_mismatch']
- `q0.q005` — ['spl_generation_mismatch']
- `q0.q008` — ['spl_generation_mismatch']
- `q0.q023` — ['spl_generation_mismatch']
- `q0.q031` — ['path_type_runtime_active']
- `q0.q043` — ['path_type_runtime_active']
- `q0.q046` — ['spl_generation_mismatch']
- `q0.q049` — ['spl_generation_mismatch']
- `q0.q055` — ['spl_generation_mismatch']
- `q0.q058` — ['spl_generation_mismatch']
- `q0.q059` — ['spl_generation_mismatch']
- `q0.q060` — ['spl_generation_mismatch', 'path_type_runtime_active']
- `q0.q062` — ['spl_generation_mismatch', 'path_type_runtime_active']
- `q0.q069` — ['spl_generation_mismatch']
- `q0.q071` — ['spl_generation_mismatch']

Cutover requires zero critical mismatches on runtime-active and safety scenarios.
