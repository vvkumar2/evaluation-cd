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
from typing import Any

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tools import get_tools


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


def create_agent():
    """
    Create and configure the LangChain agent.

    Returns:
        AgentExecutor: Configured agent ready to process messages
    """
    # Initialize the LLM
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    # Get available tools
    tools = get_tools()

    # Create the prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    # Create the agent
    agent = create_tool_calling_agent(llm, tools, prompt)

    # Create the executor
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=10,
        handle_parsing_errors=True,
    )

    return executor


def handle_message(message: str, context: dict = None, history: list = None) -> str:
    """
    Process a customer message and return the agent's response.

    Args:
        message: The customer's message
        context: Optional context dict containing customer_id (e.g., {"customer_id": "CUST-001"})
        history: Optional conversation history (not used in single-turn)

    Returns:
        The agent's response as a string
    """
    agent = create_agent()

    try:
        # Enhance message with customer context if provided
        enhanced_message = message
        if context and "customer_id" in context:
            customer_id = context["customer_id"]
            enhanced_message = f"[Customer ID: {customer_id}] {message}"

        # Run the agent
        result = agent.invoke({"input": enhanced_message})
        return result.get("output", "I apologize, but I'm unable to process your request at this time.")
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
        history = input_data.get("history", [])

        if not message:
            print("I need a message to help you. Could you please provide more details?")
            return

        # Process message with agent
        response = handle_message(message, context, history)

        # Output response (plain text)
        print(response)

    except json.JSONDecodeError:
        print("I apologize, but I couldn't understand the input format. Please provide valid JSON.")
        sys.exit(1)
    except Exception as e:
        print(
            "I apologize, but I'm experiencing technical difficulties. "
            "Please try again or contact our support team directly."
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
