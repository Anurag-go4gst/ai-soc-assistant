# Data Boundary

- MCP receives validated SPL and approved tool calls only.
- LLM receives minimized evidence and context only.
- Raw logs must not be sent to the LLM.
- Credentials, tokens, and secrets must not be sent to the LLM.
- The LLM must never execute directly against MCP or Splunk.
- Backend safeguards mediate all tool calls and analyst-facing outputs.
