# Safeguards

The initial scaffold includes a minimal SPL validator. Production phases should add allowlisted indexes, command policies, time range limits, row count limits, evidence provenance checks, and human approval gates for sensitive actions.

## Stage 3K-Q1B — SPL template schema / registry readiness

Stage 3K-Q1B extends the SPL template schema and registry only. It does not add
production SOC template coverage, does not execute SPL, does not call MCP, and
does not change MCP/SPL execution gates, live LLM routing, final synthesis,
Answer Guard, or Experience Center behavior.

- Templates declare a `query_shape`: `raw_search`, `tstats_datamodel`, or
  `from_datamodel`. Existing raw-search templates continue to load unchanged.
- CIM/tstats/datamodel templates declare `datamodel`, optional `dataset`,
  `cim_fields`, `group_by_fields`, `metric_fields`, `aggregation_shape`,
  `time_bound_required`, `result_limit_required`, `summariesonly_required`,
  `validator_profile`, and an `evidence_output_contract` aligned with
  Stage 3K.1A aggregate-safety rules (no implicit summed per-source counts;
  model-consumed packages receive precomputed safe aggregates only).
- The registry rejects CIM templates that are missing required safety flags,
  reference unknown datamodels, or use unknown CIM fields.
- Sample CIM templates ship `enabled=false`, `production_ready=false`,
  `sample_only=true`, and are never returned by `enabled_templates()`.
- The Q1A SPL validator remains the safety boundary; actual SOC pattern
  implementation is deferred to Q1C or later.

## SPL Quality Checklist

Use when reviewing governed templates, lab drafts, or LLM SPL advisory output before promotion or execution. Full rules: `docs/architecture/spl_mcp_execution_controls.md` §1, §6–§8.

* [ ] Are all dynamic slot variables type-validated before rendering?
* [ ] Are slot values escaped or normalized before template insertion?
* [ ] Are index and sourcetype values allowlisted?
* [ ] Does the SPL avoid raw user-string interpolation?
* [ ] Does the template prevent SPL injection through host/user/IP/time/window fields?
* [ ] Does any `tstats` query use `summariesonly=true` where applicable?
* [ ] Are subsearches avoided or replaced by orchestrated multi-step searches?
* [ ] Does the query have earliest/latest time bounds?
* [ ] Does the query avoid broad unfielded wildcard base searches?
* [ ] Do all final table fields survive aggregation?
