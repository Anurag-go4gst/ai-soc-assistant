# Stage 3M-S4: Foundation-Sec Shadow Demo Provider

**Status:** Implemented.

**Module:** `backend/app/demo/llm_shadow_provider.py`

---

## Purpose

Optional **demo-only** shadow path for Foundation-Sec / Hugging Face style:

- raw model route proposal
- raw model summary narration

Output appears **only** in investigation lineage (collapsed technical trace). It does **not** change analyst-facing golden answers, `selected_skill`, or `route_plan_shadow` on Experience Center demos (`route_plan_shadow` stays `null`).

Story: **raw model proposal → deterministic governance → governed demo answer unchanged.**

---

## Configuration (default safe)

| Env var | Default |
|---------|---------|
| `DEMO_LLM_SHADOW_ENABLED` | `false` |
| `DEMO_LLM_SHADOW_PROVIDER` | `disabled` (`disabled` \| `fake` \| `huggingface`) |
| `DEMO_LLM_SHADOW_MODEL` | optional |
| `DEMO_LLM_SHADOW_ENDPOINT` | optional |
| `DEMO_LLM_SHADOW_TIMEOUT_SECONDS` | `5` |

- **Disabled (default):** no provider call, no lineage shadow stage content beyond disabled metadata when enabled flag is false → no stage.
- **Fake:** static fixtures for demos/tests; **no network**.
- **Huggingface:** reserved; fails closed without endpoint; **not used in automated tests**.

Production / air-gapped deployments should use **`disabled`** or a **local Foundation-Sec** endpoint only when explicitly approved — never for authoritative answers.

---

## Governance (deterministic wins)

Recorded fields include:

- `raw_model_route_proposal`
- `raw_model_summary_narration`
- `governed_route_proposal` / `governed_summary_narration` (after drops)
- `governed_acceptance_status`
- `dropped_reasons`
- `deterministic_wins=true`

Dropped when detected in model text:

- execution claims (`executed`, `we ran`, `results show`, …)
- remediation/write actions (`block IP`, `disable user`, `isolate host`, …)
- raw SPL fragments (`search index=`, `| stats`, …)
- unsupported MITRE IDs vs governed demo context

---

## Non-goals

- No final LLM synthesis
- No executable SPL generation authority
- No MCP / SPL execution
- No `/chat` production path changes
- No `selected_skill` override

---

## Verification

```bash
cd backend && python3 -m pytest app/tests/test_demo_llm_shadow_stage3m_s4.py -q
```
