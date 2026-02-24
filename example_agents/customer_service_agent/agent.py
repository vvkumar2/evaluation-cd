#!/usr/bin/env python3
"""
LangChain-based customer service agent for TechGear e-commerce.

Uses GPT-4o with tool calling to handle customer inquiries about refunds,
orders, shipping, and order management.

Integrates with Slack via MCP server for refund escalation notifications.

Reads JSON from stdin, processes with LangChain agent, outputs text response.
"""

import asyncio
import json
import subprocess
import sys
import os
import logging
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from tools import get_tools

load_dotenv()

# Configure logging for agent visibility (only when AGENT_DEBUG=true)
logger = logging.getLogger(__name__)
if os.getenv("AGENT_DEBUG", "false").lower() == "true":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s [agent] %(message)s",
    )
else:
    logging.disable(logging.CRITICAL)


# System prompt that guides the agent's behavior
SYSTEM_PROMPT = """You are a helpful and professional customer service agent for TechGear e-commerce.

Your primary responsibilities are:
1. Help customers with refund requests
2. Provide order status and tracking information
3. Answer questions about shipping and delivery
4. Handle order cancellations and modifications

Guidelines for your responses:
- Customer ID will be provided in the message in format: [Customer ID: CUST-XXX]
- Extract the customer ID and use it to look up customer and order information
- Always look up customer and order information first before making decisions
- Be empathetic and professional in your tone
- Clearly explain business policies and decisions
- When processing refunds, use the process_refund_request tool
- For order status, use the lookup_order tool
- For delivery estimates, ALWAYS use the get_delivery_estimate tool — never guess delivery times
- For shipping costs, ALWAYS use the calculate_shipping_cost tool — never guess costs
- Always verify the customer tier before making tier-dependent decisions
- If information cannot be found, apologize and explain what information you need

Order cancellation workflow:
1. Look up the order using lookup_order
2. Use check_can_cancel_order with the order status to verify it can be cancelled
3. If cancellable, use process_refund_request to cancel and refund the order
4. Confirm the cancellation and refund to the customer
5. If not cancellable (e.g., already shipped/delivered), explain why and suggest alternatives

Order modification workflow:
1. Look up the order using lookup_order
2. Use check_can_modify_order with the order status to verify it can be modified
3. If not modifiable, explain why to the customer

Important business policies:
- Standard tier: 30-day refund window
- Gold tier: 60-day refund window
- Platinum tier: 90-day refund window
- Damaged items receive full refunds regardless of window
- Refunds under $200 are auto-approved
- Refunds $200-$1000 require manager approval
- Refunds over $1000 require executive approval

Slack escalation policy:
- When a refund result is PENDING_REVIEW, you MUST post an escalation message to Slack using the slack_post_message tool
- Use the channel ID from the environment variable SLACK_ESCALATION_CHANNEL_ID (provided in system context below)
- The message should include: order ID, refund amount, customer name/ID, and approval level needed (manager for $200-$1000, executive for >$1000)
- Format the Slack message clearly, e.g.: ":rotating_light: Refund Escalation - Order {order_id} - ${amount} - Requires {level} approval - Customer: {customer_id}"
- After posting to Slack, inform the customer that their refund is under review and the appropriate team has been notified

Be concise but thorough in your responses. Help resolve customer issues while protecting the business.
"""


def _get_slack_system_context() -> str:
    """Build additional system context with Slack configuration."""
    channel_id = os.getenv("SLACK_ESCALATION_CHANNEL_ID", "")
    if channel_id:
        return f"\n\nSlack escalation channel ID: {channel_id}"
    raise RuntimeError("Slack integration is not configured")


async def _execute_tool(tool_call: dict, tool_map: dict) -> str:
    """
    Execute a single tool call and return the result.

    Args:
        tool_call: The tool call dict with name, args, and id
        tool_map: Mapping of tool names to tool functions

    Returns:
        Tool result as a string
    """
    tool_name = tool_call["name"]
    tool_args = tool_call["args"]

    if tool_name not in tool_map:
        return f"Tool {tool_name} not found"

    tool = tool_map[tool_name]
    try:
        result = await tool.ainvoke(tool_args)
        return str(result)
    except Exception as e:
        return f"Error calling tool: {str(e)}"


def _get_slack_server_params():
    """
    Build MCP server params for Slack if configured.

    Returns:
        StdioServerParameters or None if Slack is not configured.
    """
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_team_id = os.getenv("SLACK_TEAM_ID")

    if not slack_token or not slack_team_id:
        raise RuntimeError("Slack integration is not configured")

    return StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-slack"],
        env={
            **os.environ,
            "SLACK_BOT_TOKEN": slack_token,
            "SLACK_TEAM_ID": slack_team_id,
        },
    )


async def _run_agent_loop(
    tools: list, message: str, context: dict
) -> tuple[str, list[str]]:
    """
    Run the core agentic loop with the given tools.

    Args:
        tools: List of LangChain tools (local + any MCP tools)
        message: The customer's message
        context: Context dict with customer_id etc.

    Returns:
        Tuple of (response text, list of tool names called)
    """
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )

    tool_map = {tool.name: tool for tool in tools}
    llm_with_tools = llm.bind_tools(tools)
    called_tools = []

    # Enhance message with customer context if provided
    enhanced_message = message
    if context and "customer_id" in context:
        customer_id = context["customer_id"]
        enhanced_message = f"[Customer ID: {customer_id}] {message}"

    # Build system prompt with Slack context
    full_system_prompt = SYSTEM_PROMPT + _get_slack_system_context()

    messages = [
        SystemMessage(content=full_system_prompt),
        HumanMessage(content=enhanced_message),
    ]

    max_iterations = 10
    for iteration in range(max_iterations):
        logger.info("--- Iteration %d/%d ---", iteration + 1, max_iterations)
        response = await llm_with_tools.ainvoke(messages)

        if not response.tool_calls:
            text = response.content if hasattr(response, "content") else str(response)
            logger.info("Agent finished. Response: %s", text[:200])
            return text, called_tools

        logger.info("Agent chose %d tool(s)", len(response.tool_calls))
        messages.append(response)

        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            called_tools.append(tool_name)

            logger.info("  Calling %s(%s)", tool_name, json.dumps(tool_args))

            try:
                tool_result = await _execute_tool(tool_call, tool_map)
                logger.info("  Result: %s", tool_result[:200])
                messages.append(
                    ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                )
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                logger.error("  %s", error_msg)
                messages.append(
                    ToolMessage(content=error_msg, tool_call_id=tool_call["id"])
                )

    logger.warning("Max iterations reached - returning timeout response")
    return (
        "I apologize, but I took too long to process your request. Please try again.",
        called_tools,
    )


async def load_all_tools(tool_interceptors=None) -> tuple[list, AsyncExitStack]:
    """Load all tools including MCP tools. Opens a new MCP session.

    Args:
        tool_interceptors: Optional list of interceptors for MCP tool calls.

    Returns a tuple of (tools, stack) where stack should be closed when done.
    """
    tools = get_tools()
    server_params = _get_slack_server_params()

    stack = AsyncExitStack()
    read, write = await stack.enter_async_context(
        stdio_client(server_params, errlog=subprocess.DEVNULL)
    )
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    slack_tools = await load_mcp_tools(session, tool_interceptors=tool_interceptors)

    return tools + slack_tools, stack


async def handle_message(
    message: str, context: dict = None, tools: list = None
) -> tuple[str, list[str]]:
    """
    Process a customer message and return the agent's response.

    Args:
        message: The customer's message
        context: Optional context dict containing customer_id (e.g., {"customer_id": "CUST-001"})
        tools: Optional pre-loaded tools list (skips MCP session setup if provided)

    Returns:
        Tuple of (response text, list of tool names called)
    """
    if context is None:
        context = {}

    if tools is not None:
        return await _run_agent_loop(tools, message, context)

    all_tools, stack = await load_all_tools()
    try:
        return await _run_agent_loop(all_tools, message, context)
    finally:
        await stack.aclose()


async def async_main():
    """
    Async main entry point - reads JSON from stdin, processes with agent, outputs text.

    Expected stdin format:
    {
        "message": "customer message",
        "context": {"customer_id": "CUST-001"},  # optional, but recommended
        "history": []   # optional
    }
    """
    try:
        input_data = json.loads(sys.stdin.read())
        message = input_data.get("message", "")
        context = input_data.get("context", {})
        if not message:
            print(
                "I need a message to help you. Could you please provide more details?"
            )
            return
        response, tool_calls = await handle_message(message, context)
        print(response, tool_calls)

    except Exception as e:
        print(f"I apologize, but I'm experiencing technical difficulties: {str(e)}")
        sys.exit(1)


def main():
    """Sync entry point that runs the async main."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
