#!/usr/bin/env python3
"""
LangChain-based customer service agent for TechGear e-commerce.

Uses GPT-4o with tool calling to handle customer inquiries about refunds,
orders, shipping, and order management.

Reads JSON from stdin, processes with LangChain agent, outputs text response.
"""

import json
import sys
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from tools import get_tools

load_dotenv()


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
- Always verify the customer tier before making tier-dependent decisions
- If information cannot be found, apologize and explain what information you need

Important business policies:
- Standard tier: 30-day refund window
- Gold tier: 60-day refund window
- Platinum tier: 90-day refund window
- Damaged items receive full refunds regardless of window
- Refunds under $200 are auto-approved
- Refunds $200-$1000 require manager approval
- Refunds over $1000 require executive approval

Be concise but thorough in your responses. Help resolve customer issues while protecting the business.
"""


def _execute_tool(tool_call: dict, tool_map: dict) -> str:
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
        return tool.func(**tool_args)
    except Exception as e:
        return f"Error calling tool: {str(e)}"


def handle_message(message: str, context: dict = None) -> str:
    """
    Process a customer message and return the agent's response.

    Args:
        message: The customer's message
        context: Optional context dict containing customer_id (e.g., {"customer_id": "CUST-001"})

    Returns:
        The agent's response as a string
    """
    if context is None:
        context = {}

    # Initialize the LLM
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )

    # Get available tools and create mapping
    tools = get_tools()
    tool_map = {tool.name: tool for tool in tools}

    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)

    try:
        # Enhance message with customer context if provided
        enhanced_message = message
        if context and "customer_id" in context:
            customer_id = context["customer_id"]
            enhanced_message = f"[Customer ID: {customer_id}] {message}"

        # Prepare the messages for the agent
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=enhanced_message),
        ]

        # Agentic loop - keep calling until we get a final response
        max_iterations = 10
        for _ in range(max_iterations):
            # Call the LLM
            response = llm_with_tools.invoke(messages)

            # If the LLM didn't call any tools, return the response
            if not response.tool_calls:
                # Extract text content
                if hasattr(response, "content"):
                    return response.content
                return str(response)

            # Process tool calls
            messages.append(response)

            for tool_call in response.tool_calls:
                tool_result = _execute_tool(tool_call, tool_map)
                messages.append(
                    ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                )

        # If we hit max iterations, return what we have
        return "I apologize, but I took too long to process your request. Please try again."

    except Exception as e:
        return f"I apologize, but I'm experiencing technical difficulties: {str(e)}"


def main():
    """
    Main entry point - reads JSON from stdin, processes with agent, outputs text.

    Expected stdin format:
    {
        "message": "customer message",
        "context": {"customer_id": "CUST-001"},  # optional, but recommended
        "history": []   # optional
    }
    """
    try:
        # Read input from stdin
        input_data = json.loads(sys.stdin.read())

        message = input_data.get("message", "")
        context = input_data.get("context", {})

        if not message:
            print(
                "I need a message to help you. Could you please provide more details?"
            )
            return

        # Process message with agent
        response = handle_message(message, context)

        # Output response (plain text)
        print(response)

    except json.JSONDecodeError:
        print(
            "I apologize, but I couldn't understand the input format. Please provide valid JSON."
        )
        sys.exit(1)
    except Exception as e:
        print(f"I apologize, but I'm experiencing technical difficulties: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
