"""Mock interceptor for MCP tool calls during test execution."""

import json
from mcp.types import CallToolResult, TextContent


class MockToolInterceptor:
    """Intercepts MCP tool calls and returns mock responses instead of calling real APIs."""

    def __init__(self, default_responses: dict[str, str]):
        self.default_responses = default_responses
        self._overrides: dict[str, dict] = {}

    def set_overrides(self, overrides: dict[str, dict] | None):
        """Set per-test response overrides. Pass None to clear."""
        self._overrides = overrides or {}

    async def __call__(self, request, handler):
        if request.name in self._overrides:
            override = self._overrides[request.name]
            text = override.get("response", "OK")
            is_error = override.get("is_error", False)
        else:
            text = self.default_responses.get(request.name, "OK")
            is_error = False

        if is_error:
            # Match real Slack MCP server error format: {"error": "message"}
            error_text = json.dumps({"error": text})
            return CallToolResult(
                content=[TextContent(type="text", text=error_text)],
                isError=True,
            )

        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            isError=False,
        )
