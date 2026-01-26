"""Example usage of AgentTestSpaceExtractor."""

import json
from .main import AgentTestSpaceExtractor

# Example 1: Sample tool schemas (as would come from LangChain agent)
SAMPLE_TOOLS_SCHEMA = {
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": "Look up order details by order ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The order ID (e.g., ORD-001)",
                        }
                    },
                    "required": ["order_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "process_refund",
                "description": "Process a refund for an order",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The order ID",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for refund",
                            "enum": ["defective", "wrong_item", "changed_mind", "other"],
                        },
                        "amount": {
                            "type": "number",
                            "description": "Refund amount in dollars",
                            "minimum": 0,
                        },
                    },
                    "required": ["order_id", "reason", "amount"],
                },
            },
        },
    ]
}

# Example 2: Sample entity schema (YAML-like)
SAMPLE_ENTITY_SCHEMA = {
    "entities": [
        {
            "name": "Order",
            "description": "Customer order information",
            "fields": [
                {
                    "name": "order_id",
                    "type": "string",
                    "description": "Unique order identifier",
                    "required": True,
                },
                {
                    "name": "customer_id",
                    "type": "string",
                    "description": "Customer who placed the order",
                    "required": True,
                },
                {
                    "name": "price",
                    "type": "number",
                    "description": "Order price in dollars",
                    "required": True,
                    "constraints": [{"operator": "gte", "value": 0}],
                },
                {
                    "name": "status",
                    "type": "string",
                    "description": "Order status",
                    "enum": ["pending", "processing", "shipped", "delivered", "cancelled"],
                },
                {
                    "name": "delivered_date",
                    "type": "string",
                    "description": "Date order was delivered (ISO format)",
                },
            ],
            "thresholds": [
                {
                    "name": "refund_window_days",
                    "value": 30,
                    "description": "Days after delivery customer can request refund",
                    "unit": "days",
                }
            ],
        },
        {
            "name": "Customer",
            "description": "Customer account information",
            "fields": [
                {
                    "name": "customer_id",
                    "type": "string",
                    "description": "Unique customer identifier",
                    "required": True,
                },
                {
                    "name": "tier",
                    "type": "string",
                    "description": "Customer tier",
                    "enum": ["standard", "gold", "platinum"],
                },
                {
                    "name": "lifetime_value",
                    "type": "number",
                    "description": "Total customer spending",
                    "constraints": [{"operator": "gte", "value": 0}],
                },
            ],
        },
    ]
}

# Example 3: Sample system prompt
SAMPLE_SYSTEM_PROMPT = """You are TechGear Customer Service Agent, responsible for helping customers with their orders.

Your primary responsibilities:
1. Help customers with refund requests
2. Provide order tracking information
3. Answer questions about policies

## Refund Policy

You can process refunds for:
- Defective products: Full refund always
- Wrong item: Full refund always
- Changed mind: 50% refund only for orders under $200
- Other: Requires manager approval

The refund window is 30 days from delivery for standard customers, 60 days for gold customers, and 90 days for platinum customers.

Always look up the order details before making a decision.

## Order Policies

- Orders can be cancelled only if status is "pending" or "processing"
- Customers can modify orders only within 1 hour of placement
- Shipping is free for orders over $100

## Global Rules

- Be professional and empathetic in all interactions
- Always verify customer identity before processing requests
- Escalate high-value refunds (over $500) to manager
- Do not process refunds outside the refund window

## Refusals

- Do not modify orders that have already shipped
- Do not process refunds for items intentionally damaged by customer
- Do not bypass policies under any circumstances
"""


def example_basic_extraction():
    """Example: Basic extraction without LLM (Steps 1 and 2a only)."""
    print("\n=== Example 1: Basic Extraction (No LLM) ===\n")

    extractor = AgentTestSpaceExtractor()

    # Extract tools and entities only (no LLM needed)
    tools = extractor.step1_parse_tools(SAMPLE_TOOLS_SCHEMA)
    entities = extractor.step2a_parse_entities(SAMPLE_ENTITY_SCHEMA)

    print(f"Extracted {len(tools.tools)} tools:")
    for tool in tools.tools:
        print(f"  - {tool.name}: {tool.description}")
        print(f"    Parameters: {[p.name for p in tool.parameters]}")

    print(f"\nExtracted {len(entities.entities)} entities:")
    for entity in entities.entities:
        print(f"  - {entity.name}: {entity.description}")
        print(f"    Fields: {[f.name for f in entity.fields]}")
        print(f"    Thresholds: {[(t.name, t.value) for t in entity.thresholds]}")

    return tools, entities


def example_validation():
    """Example: Validate extracted outputs."""
    print("\n=== Example 2: Validation ===\n")

    extractor = AgentTestSpaceExtractor()

    # Extract without LLM
    tools = extractor.step1_parse_tools(SAMPLE_TOOLS_SCHEMA)
    entities = extractor.step2a_parse_entities(SAMPLE_ENTITY_SCHEMA)

    # Would normally extract from prompt with LLM
    # For this example, create minimal prompt extraction
    from .schemas.prompt_schema import (
        SystemPromptExtraction,
        Intent,
    )

    prompt_extraction = SystemPromptExtraction(
        agent_name="TechGear Customer Service Agent",
        agent_role="Process customer support requests",
        intents=[
            Intent(
                name="process_refund",
                description="Process a customer refund request",
                trigger_examples=[
                    "I want a refund",
                    "Can I get my money back?",
                    "This item is defective",
                ],
            ),
        ],
    )

    # Validate
    validation_result = extractor.step4_validate(tools, entities, prompt_extraction)

    print(f"Validation Result:")
    print(f"  Valid: {validation_result['is_valid']}")
    print(f"  Errors: {len(validation_result['errors'])}")
    for error in validation_result["errors"]:
        print(f"    - {error.error_type}: {error.message}")


def example_json_output():
    """Example: Output extracted data as JSON."""
    print("\n=== Example 3: JSON Output ===\n")

    extractor = AgentTestSpaceExtractor()

    # Extract
    tools = extractor.step1_parse_tools(SAMPLE_TOOLS_SCHEMA)
    entities = extractor.step2a_parse_entities(SAMPLE_ENTITY_SCHEMA)

    # Convert to JSON-serializable format
    tools_json = json.dumps(
        [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required,
                    }
                    for p in tool.parameters
                ],
            }
            for tool in tools.tools
        ],
        indent=2,
    )

    print("Tools JSON:")
    print(tools_json)

    entities_json = json.dumps(
        [
            {
                "name": entity.name,
                "description": entity.description,
                "fields": [
                    {
                        "name": f.name,
                        "type": f.type,
                        "description": f.description,
                    }
                    for f in entity.fields
                ],
            }
            for entity in entities.entities
        ],
        indent=2,
    )

    print("\nEntities JSON:")
    print(entities_json)


if __name__ == "__main__":
    # Run examples
    example_basic_extraction()
    example_validation()
    example_json_output()

    print("\n=== All examples completed ===")
