class MockSplunkMcpClient:
    def execute(self, tool_name: str, payload: dict[str, object]) -> dict[str, object]:
        return {
            "tool_name": tool_name,
            "payload": payload,
            "mock": True,
            "note": "No Splunk MCP call was made.",
        }
