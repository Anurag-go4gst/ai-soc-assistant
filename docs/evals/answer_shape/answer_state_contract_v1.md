# Answer states A–E (plan item 2.1)

| State | Meaning |
|---|---|
| **A** | Awaiting investigation approval — plan + Approve/Edit/Cancel; no terminal finished claim; no MCP |
| **B** | Approved / investigating — envelope present; progress telemetry ≠ SourceEvidence |
| **C** | Terminal inconclusive — findings + inconclusive conclusion + missing evidence; remediation plan ABSENT unless plan-eligible |
| **D** | Terminal suspicious / evidence-backed — remediation plan MAY PRESENT; user-conditional email only if predicate satisfied |
| **E** | Terminal knowledge / non-investigation / structural |

Bank rows name exactly one `primary_answer_state` in `convergence_expectation_bank_v1.json`.


## Findings / conclusion / limitations (item 2.4)

| Channel | Authority |
|---|---|
| **Findings** | Accepted SourceEvidence-backed statements only (`InvestigationOutcome.findings`) |
| **Conclusion** | `disposition` (`inconclusive` / `suspicious` / `benign`) — distinct from `investigation_status` |
| **Missing evidence / limitations** | Named on inconclusive / incomplete paths; not diagnostics |
| **Progress telemetry** | Operational only — never findings or EvidenceState authority |

Fixtures: `docs/evals/answer_shape/fixtures/cv_multi_01a_outcome.json` (C), `cv_multi_01b_outcome.json` (D).
`suspicious` ≠ `compromise_confirmed`.
