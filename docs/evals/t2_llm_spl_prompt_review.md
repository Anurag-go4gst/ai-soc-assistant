# T2 LLM SPL producer — prompt review (2026-06-19)

The on-host model is an 8B instruct (Foundation-Sec q8). Small instruct models are
**prompt-sensitive**: long, multi-section instructions dilute format adherence and
slow prompt eval. Review of `app/spl/llm_fallback.py` `_system_prompt` / `_user_prompt`.

## Findings

1. **System prompt is very long.** The default (non-correctness) path concatenates
   `universal_engineering_prompt()` + the full SOC-STD-SPL-001 C–I rules +
   `full_engineering_prompt()` (the whole detection-family catalog). On an 8B this
   (a) adds prompt-eval latency and (b) buries the output contract → format drift
   (the malformed-JSON failure seen in the live probe).
2. **JSON contract stated once, late.** "Return only JSON with keys …" sits at the
   end of the user prompt. Small models honor a contract better when it is short,
   first, and machine-enforced.
3. **Server-side JSON enforcement does not work on this build.** The producer now
   passes `response_format={"type":"json_object"}`, but a direct diagnostic showed
   the on-host llama-server **ignores it** — it returned ` ```json ` markdown
   fences and (on the large schema) dropped a JSON delimiter. So json_object is a
   harmless no-op here; on a build that honors it, it would help. The real levers
   on this hardware are the tolerant parser + a smaller schema/prompt.
4. **Example is good but buried.** One concrete example is worth more than the C–I
   prose to an 8B; it should sit immediately after the contract.

## Recommendations (priority order)

1. **Keep `response_format=json_object`** (shipped) — no-op on the current server
   build (it ignores the hint) but correct for any build that honors it; zero risk.
2. **Prefer the compact `correctness_mode` block for T2.** It already exists
   (`_correctness_engineering_block`) and is far shorter than the full SOC-STD +
   family catalog, while keeping the shift-left + native-time discipline.
3. **Lead with the contract + one example; trim prose rules.**
4. **Keep the tolerant parser** (`_extract_first_json_object` + trailing-comma
   repair) as the secondary net; truncated output still fails closed.

## Example — a tightened system prompt for an 8B

```
You are the AI SOC SPL advisory fallback. Output exactly ONE JSON object, nothing
else. Keys (all required):
  status, confidence_score, confidence_label, detection_family, candidate_spl,
  assumptions, required_fields, missing_details, clarifying_questions,
  validation_notes, soc_std_rules_applied, risk_notes,
  execution_eligible, governed, catalog_approved

candidate_spl rules:
- begin: search index=<index> sourcetype=<sourcetype>   (angle-bracket placeholders only)
- include: earliest=-<N>[mhd] latest=now
- normalize fields with coalesce() before stats; strftime timestamps AFTER stats
- end: head 100
- allowed commands only: search stats where table fields sort dedup rename eval timechart bin head streamstats
- forbidden: from tstats datamodel subsearch macro delete collect outputlookup sendemail rest, any write
- execution_eligible, governed, catalog_approved MUST be false; never claim results/execution/approval

Example:
{"status":"candidate_generated","confidence_score":0.72,"confidence_label":"medium",
"detection_family":"windows_account_lockout",
"candidate_spl":"search index=<auth_index> sourcetype=<auth_sourcetype> earliest=-60m latest=now action=failure | eval src_ip_norm=coalesce(src_ip, src, \"unknown\") | stats count as failed_logins by src_ip_norm | sort - failed_logins | head 100",
"assumptions":["<auth_index>/<auth_sourcetype> are the auth source"],
"required_fields":["src_ip","action","index","sourcetype"],
"missing_details":[],"clarifying_questions":[],
"validation_notes":["Lab candidate only"],"soc_std_rules_applied":["coalesce_normalization"],
"risk_notes":["Not governed"],"execution_eligible":false,"governed":false,"catalog_approved":false}
```

User prompt: put `User request: <query>` first, then any routing/grounding context,
then a one-line "Return only the JSON object." — no trailing prose.

## Status

- Shipped this slice: `response_format=json_object` + tolerant parser helper.
- Deferred (separate slice, needs eval): switching the default T2 path to the
  compact `correctness_mode` block and trimming the prose rules — measure SPL
  relevance before/after on the catalogue so quality does not regress.
