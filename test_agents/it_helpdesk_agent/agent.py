#!/usr/bin/env python3
"""
LangChain-based IT helpdesk agent.

Uses GPT-4o with tool calling to handle IT support requests including
password resets, ticket management, system status, access requests,
software installs, and escalation routing.

Integrates with Resend (email) and PagerDuty via MCP servers.

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
SYSTEM_PROMPT = """You are a professional and efficient IT helpdesk support agent.

Your primary responsibilities are:
1. Help employees with password resets
2. Manage IT support tickets (create, look up, escalate)
3. Check system status and report issues
4. Process access requests for systems
5. Handle software installation requests
6. Escalate critical issues when needed

Guidelines for your responses:
- Employee ID will be provided in the message in format: [Employee ID: EMP-XXX]
- Extract the employee ID and use it to look up employee information
- Always verify the employee exists before performing any action
- Be professional and concise in your responses
- Clearly explain what actions you're taking and why

Password reset workflow:
1. Look up the target employee using lookup_employee
2. Use reset_password with the target employee_id and the requester's employee_id
3. If the reset is successful, send an email notification via the send_email tool with the temporary password and instructions
4. If MFA re-enrollment is required, include MFA re-enrollment instructions in the email
5. Inform the employee of the result

Access request workflow:
1. Look up the employee using lookup_employee
2. Use request_access with the employee_id, system name, and permission level
3. If the result requires approval, create a ticket using create_ticket with category "access_request"
4. If approved, confirm the access grant to the employee

Software install workflow:
1. Look up the employee using lookup_employee
2. Use request_software_install with the employee_id and software name
3. If the result requires approval, create a ticket using create_ticket with category "software_install"
4. Inform the employee of the result

Ticket escalation workflow:
1. Look up the ticket using lookup_ticket
2. Use escalate_ticket with the ticket_id and reason
3. If email_required is true, send an email notification via the send_email tool about the escalation
4. If pagerduty_required is true, create a PagerDuty incident using the pagerduty_create_incident tool with relevant details
5. Inform the employee that the ticket has been escalated

Important security policies:
- Admins (role: admin) can reset any employee's password
- Regular users (role: user) can only reset their own password
- Disabled accounts cannot have passwords reset — direct them to contact an administrator
- Locked accounts will be automatically unlocked during password reset
- Admin-level access requests from non-admin employees always require manager approval

External tool usage:
- Send emails via the send_email tool for: password reset notifications, escalation alerts, access confirmations
- Create PagerDuty incidents only when escalation result shows pagerduty_required is true
- Always include relevant context in emails and PagerDuty incidents (ticket ID, employee name, description)

Be thorough but efficient. Help resolve IT issues while maintaining security policies.
"""


def _get_resend_server_params():
    """
    Build MCP server params for Resend email if configured.

    Returns:
        StdioServerParameters or None if Resend is not configured.
    """
    resend_api_key = os.getenv("RESEND_API_KEY")

    if not resend_api_key:
        raise RuntimeError("Resend email integration is not configured")

    env = {**os.environ, "RESEND_API_KEY": resend_api_key}

    sender_email = os.getenv("SENDER_EMAIL_ADDRESS")
    if sender_email:
        env["SENDER_EMAIL_ADDRESS"] = sender_email

    return StdioServerParameters(
        command="npx",
        args=["-y", "resend-mcp"],
        env=env,
    )


def _get_pagerduty_server_params():
    """
    Build MCP server params for PagerDuty if configured.

    Returns:
        StdioServerParameters or None if PagerDuty is not configured.
    """
    pd_api_key = os.getenv("PAGERDUTY_USER_API_KEY")

    if not pd_api_key:
        raise RuntimeError("PagerDuty integration is not configured")

    return StdioServerParameters(
        command="uvx",
        args=["pagerduty-mcp", "--enable-write-tools"],
        env={
            **os.environ,
            "PAGERDUTY_USER_API_KEY": pd_api_key,
            "PAGERDUTY_API_HOST": "https://api.pagerduty.com",
        },
    )


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


async def _run_agent_loop(
    tools: list, message: str, context: dict
) -> tuple[str, list[str]]:
    """
    Run the core agentic loop with the given tools.

    Args:
        tools: List of LangChain tools (local + any MCP tools)
        message: The employee's message
        context: Context dict with employee_id etc.

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

    logger.info("tools: %s", len(tool_map))

    # Enhance message with employee context if provided
    enhanced_message = message
    if context and "employee_id" in context:
        employee_id = context["employee_id"]
        enhanced_message = f"[Employee ID: {employee_id}] {message}"

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=enhanced_message),
    ]

    max_iterations = 10
    for iteration in range(max_iterations):
        logger.info("--- Iteration %d/%d ---", iteration + 1, max_iterations)
        logger.info("Messages: %s", messages)
        response = await llm_with_tools.ainvoke(messages)
        logger.info("Response: %s", response)
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


async def _load_mcp_tools_from_server(stack, server_params, tool_interceptors=None):
    """Load MCP tools from a single server."""
    read, write = await stack.enter_async_context(
        stdio_client(server_params, errlog=subprocess.DEVNULL)
    )
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return await load_mcp_tools(session, tool_interceptors=tool_interceptors)


async def load_all_tools(tool_interceptors=None) -> tuple[list, AsyncExitStack]:
    """Load all tools including MCP tools. Opens new MCP sessions.

    Args:
        tool_interceptors: Optional list of interceptors for MCP tool calls.

    Returns a tuple of (tools, stack) where stack should be closed when done.
    """
    tools = get_tools()
    stack = AsyncExitStack()

    # Load Resend email tools
    resend_params = _get_resend_server_params()
    resend_tools = await _load_mcp_tools_from_server(
        stack, resend_params, tool_interceptors
    )
    print(len(resend_tools))
    for tool in resend_tools:
        if tool.name == "send-email":
            tools.append(tool)

    # Load PagerDuty tools
    pd_params = _get_pagerduty_server_params()
    pd_tools = await _load_mcp_tools_from_server(stack, pd_params, tool_interceptors)
    for tool in pd_tools:
        if tool.name == "create-incident":
            tools.append(tool)

    return tools, stack


async def handle_message(
    message: str, context: dict = None, tools: list = None
) -> tuple[str, list[str]]:
    """
    Process an employee message and return the agent's response.

    Args:
        message: The employee's message
        context: Optional context dict containing employee_id (e.g., {"employee_id": "EMP-001"})
        tools: Optional pre-loaded tools list (skips MCP session setup if provided)

    Returns:
        Tuple of (response text, list of tool names called)
    """
    if context is None:
        context = {}

    if tools is not None:
        return await _run_agent_loop(tools, message, context)

    all_tools, stack = await load_all_tools()
    print("Num tools: %d", len(all_tools))
    try:
        return await _run_agent_loop(all_tools, message, context)
    finally:
        await stack.aclose()


async def async_main():
    """
    Async main entry point - reads JSON from stdin, processes with agent, outputs text.

    Expected stdin format:
    {
        "message": "employee message",
        "context": {"employee_id": "EMP-001"},  # optional, but recommended
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
