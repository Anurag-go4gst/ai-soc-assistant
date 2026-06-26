---
name: llm-doctor
description: Diagnose and fix the on-host Foundation-Sec llama-server (slow generation, timeouts, JSON malformation, CPU contention) for the AI-SOC governed LLM. Use when the user says "LLM slow", "model timing out", "chat hanging", "check the LLM", "llama-server", "why is synthesis slow", or /llm-doctor.
disable-model-invocation: true
---

# llm-doctor

Triage the on-host Foundation-Sec 8B (`llama-server`, `http://127.0.0.1:8081`, systemd `llama-server.service`, model `foundation-sec-1.1-8b-instruct-q8_0.gguf`). It is single-slot and CPU-bound on a shared VPS — degradation is usually **infra (steal/thrash), not code**.

## Known truths (do not relitigate)
- **`/health` lies.** A 200 from `/health` or `/settings/llm/health` does NOT mean usable throughput. Always measure real generation tok/s. False `0.0` readings came from waiting on a large completion that timed out — measure from the first few streamed tokens.
- **Throughput:** clean ≈ 5.7 tok/s, degraded ≈ 0.6 tok/s. Guard threshold 2.0 tok/s.
- **KV-cache thrash:** q8 8B with `-c 9000` swap-thrashes the ~15 GB box. Fix = `-c 4000` in the systemd unit, then restart. ~3–5 tok/s clean.
- **CPU steal/contention:** hypervisor steal bursts 62–83% + concurrent Codex/cert/MCP load throttle the model. A restart will NOT fix steal — confirm with `vmstat` `st` column before blaming the model or restarting.
- **JSON fences:** the 8B wraps output in ```json fences, which break the strict SPL parser. Diagnose response shaping with `diag_llm_json_modes.py`.
- Live LLM is blocked in pytest by an autouse guard; never let a probe run inside the suite.

## Procedure (escalate in order)

1. **Measure real throughput** (the only honest signal):
   ```bash
   cd /var/www/ai-soc-assistant
   python3 scripts/llm_health_guard.py            # exit 1 if < 2.0 tok/s
   ```
2. **Check for CPU steal BEFORE restarting** (restart won't fix steal):
   ```bash
   vmstat 1 5      # watch the 'st' column; sustained high st = hypervisor contention
   ```
   Also check what else is burning CPU (Codex, cert renew, MCP). If steal is the cause, the fix is reducing concurrent load / waiting, not restarting.
3. **If degraded and steal is low → restart the unit and re-measure:**
   ```bash
   python3 scripts/llm_health_guard.py --restart
   # or, hands-on:
   sudo systemctl restart llama-server.service && sleep 3 && python3 scripts/llm_health_guard.py
   ```
4. **If output is malformed (parser errors, not slowness)** — diagnose JSON shaping:
   ```bash
   python3 scripts/diag_llm_json_modes.py     # plain / json_object / json_schema / grammar, raw excerpt per mode
   ```
5. **Confirm the KV-cache size** if thrash suspected: inspect the `llama-server.service` unit for `-c`; if `> ~4000` on this box, lower to `-c 4000`, `daemon-reload`, restart.
6. **Role quality** (offline, from captured traces — not a live probe):
   ```bash
   PYTHONPATH=backend:. python3 scripts/build_llm_role_scorecard.py --input <traces.jsonl> --check
   ```

## Reporting
State the measured tok/s, the `vmstat` steal reading, and the action taken. Distinguish **infra contention** (steal/thrash — restart may not help) from a **dead/wedged server** (restart fixes) from **malformed output** (parser/prompt issue, not health). Never report "LLM healthy" off a `/health` 200 alone.
