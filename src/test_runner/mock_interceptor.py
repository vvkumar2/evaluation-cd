"""Mock interceptor for MCP tool calls during test execution."""

import json
from mcp.types import CallToolResult, TextContent


class MockToolInterceptor:
    """Intercepts MCP tool calls and returns mock responses instead of calling real APIs.

    Supports both success and error responses matching the real MCP server format.
    Per-test overrides can be applied via set_overrides() to simulate failures
    for specific test cases.
    """

    def __init__(self, default_responses: dict[str, str]):
        """Initialize with default success responses from schema.yml.

        Args:
            default_responses: Mapping of tool name to default success response text.
        """
        self.default_responses = default_responses
        self._overrides: dict[str, dict] = {}

    def set_overrides(self, overrides: dict[str, dict] | None):
        """Set per-test response overrides.

        Args:
            overrides: Mapping of tool name to {"response": str, "is_error": bool}.
                Pass None to clear overrides.
        """
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
