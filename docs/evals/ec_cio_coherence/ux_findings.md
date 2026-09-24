# EC visual walkthrough — findings (2026-09-24, branch `feat/ec-cio-coherence`)

Walked in the in-app browser at the pane's native width (≈800 px): S1 end-to-end (plan → run → remediation plan → email dialog → approve → complete), S2 (plan → run), R1 (plan → run → RAG panel), Q1 (answer → chip). S4/S7 use the same agent workflow page as S1/S2; their content was verified in the backend walk harness.

| # | Where | Finding | Severity | Fix |
|---|-------|---------|----------|-----|
| F1 | Agent scenarios, first turn | The initial animation says "Executing governed Splunk searches" and shows results ("No alert — IP not in the IOC list") **before** the plan is shown — contradicts "Nothing runs until you approve" | High | Plan-only animation for agent scenarios at PLAN_READY |
| F2 | S1/S2 plan stage | Answer title and S1 story badge give the verdict ("malicious use not confirmed", "So far: MEDIUM") before the investigation runs | High | Neutral plan titles; badge says "not investigated yet" at plan stage |
| F3 | All agent, after run | Opening paragraph still says "Nothing runs until you approve" | Medium | Show the opening only on the plan turn |
| F4 | S1 outcome | Executive brief and the older executive-summary bullets repeat each other | Medium | Hide the bullet list when a brief exists |
| F5 | All agent outcome | Order is results table → conclusion → brief: the verdict sits below a long table | Medium | Brief + decision button directly after the summary strip |
| F6 | Run investigation / Approve remediation | The page jumps: to the top, then to the brief (run); to the very bottom, then to the brief (approve). Cause: the plan rows collapse while progress plays and the browser clamps the scroll | High (the original complaint) | Scroll to the progress panel as soon as a run starts |
| F7 | R1 outcome | The cited answer appears twice (conclusion list + RAG panel) | Low | Conclusion keeps the headline; sentences live in the RAG panel |
| F8 | Result rows | Provenance labels "EXPERIENCE CENTER FIXTURE", "SIMULATED MCP" | Medium | Plain labels ("Demo data", "Demo connector") |
| F9 | Various | Leftover internal wording: "expected MCP business traffic", "MCP has no deploy tool", "Splunk MCP execution (simulated)", "inventory fixture", "execution_eligible=false", metric "false · New Spl Generated", progress footer "Experience Center uses COE fixtures…" | Medium | Reword at source |
| F10 | S2 outcome | "Still unresolved" lists "Successful unauthorized tool execution" while the brief says none ran | Medium | Replace with the real open questions |
| F11 | Email dialog | No blank line between sections ("…IP" / "PLEASE TELL US") | Low | Blank line before each section |
| F12 | Composer | (a) `/clear` + Enter with the suggestion list open runs a suggested scenario instead of clearing; (b) after sending a typed question for another scenario, the box refills with that scenario's prompt | High | Never suggest for `/clear`; don't re-seed after a typed submit |
| F13 | Q1 (legacy card) | Chip findings (identity check, blast radius) are added to a field the legacy card never renders, so the answer looks unchanged; the title still says "account breach" | High | Render "Findings so far" on the legacy card; neutral title |
| F14 | Agent plan | The connected-tools strip sits below the Run button | Low | Move it above the buttons |
| F15 | Email dialog | "From: AI SOC Assistant · Experience Center" | Low | "SOC Operations · AI SOC Assistant" |

Not changed: the email dialog shows a fixed demo recipient address from `frontend/src/lib/ecDemoEmail.ts`. The backend has no mail settings here, so nothing is actually sent.
