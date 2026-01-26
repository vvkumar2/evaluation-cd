"""Integration tests for AgentTestSpaceExtractor."""

import json
from .main import AgentTestSpaceExtractor
from .schemas.prompt_schema import SystemPromptExtraction, Intent


def test_tool_parsing():
    """Test Step 1: Tool schema parsing."""
    print("\n=== Test 1: Tool Schema Parsing ===")

    tools_schema = {
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
                            "order_id": {"type": "string"},
                            "reason": {
                                "type": "string",
                                "enum": ["defective", "wrong_item", "changed_mind"],
                            },
                            "amount": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 10000,
                            },
                        },
                        "required": ["order_id", "reason", "amount"],
                    },
                },
            },
        ]
    }

    extractor = AgentTestSpaceExtractor()
    tools = extractor.step1_parse_tools(tools_schema)

    assert len(tools.tools) == 2
    assert tools.tools[0].name == "lookup_order"
    assert tools.tools[1].name == "process_refund"
    assert len(tools.tools[1].parameters) == 3

    # Check constraints extraction
    amount_param = tools.tools[1].parameters[2]
    assert amount_param.name == "amount"
    assert len(amount_param.constraints) >= 2  # minimum and maximum

    print("✓ Tool schema parsing works correctly")
    print(f"  - Parsed {len(tools.tools)} tools")
    print(f"  - Tools: {[t.name for t in tools.tools]}")
    print(f"  - Constraints extracted: {len(amount_param.constraints)} for 'amount'")

    return tools


def test_entity_parsing():
    """Test Step 2a: Entity schema parsing."""
    print("\n=== Test 2: Entity Schema Parsing ===")

    entity_schema = {
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
                        "description": "Customer ID",
                    },
                    {
                        "name": "price",
                        "type": "number",
                        "description": "Order price",
                        "constraints": [{"operator": "gte", "value": 0}],
                    },
                    {
                        "name": "status",
                        "type": "string",
                        "enum": ["pending", "processing", "shipped", "delivered"],
                    },
                ],
                "thresholds": [
                    {
                        "name": "refund_window_days",
                        "value": 30,
                        "description": "Days to request refund",
                        "unit": "days",
                    }
                ],
            },
            {
                "name": "Customer",
                "description": "Customer information",
                "fields": [
                    {
                        "name": "customer_id",
                        "type": "string",
                        "required": True,
                    },
                    {
                        "name": "tier",
                        "type": "string",
                        "enum": ["standard", "gold", "platinum"],
                    },
                ],
            },
        ]
    }

    extractor = AgentTestSpaceExtractor()
    entities = extractor.step2a_parse_entities(entity_schema)

    assert len(entities.entities) == 2
    assert entities.entities[0].name == "Order"
    assert entities.entities[1].name == "Customer"

    # Check threshold parsing
    order = entities.entities[0]
    assert len(order.thresholds) == 1
    assert order.thresholds[0].name == "refund_window_days"
    assert order.thresholds[0].value == 30

    # Check constraint parsing
    price_field = order.fields[2]
    assert price_field.name == "price"
    assert len(price_field.constraints) == 1

    print("✓ Entity schema parsing works correctly")
    print(f"  - Parsed {len(entities.entities)} entities")
    print(f"  - Entities: {[e.name for e in entities.entities]}")
    print(f"  - Order thresholds: {[(t.name, t.value) for t in order.thresholds]}")

    return entities


def test_validation():
    """Test Step 4: Validation."""
    print("\n=== Test 3: Validation ===")

    # Get tools and entities from previous tests
    tools = test_tool_parsing()
    entities = test_entity_parsing()

    # Create a minimal prompt extraction
    prompt_extraction = SystemPromptExtraction(
        agent_name="TechGear Customer Service Agent",
        agent_role="Customer support for e-commerce",
        intents=[
            Intent(
                name="process_refund",
                description="Process customer refund",
                trigger_examples=["I want a refund", "This is broken"],
            ),
            Intent(
                name="check_order_status",
                description="Check order status",
                trigger_examples=["Where is my order?"],
            ),
        ],
    )

    extractor = AgentTestSpaceExtractor()
    validation_result = extractor.step4_validate(tools, entities, prompt_extraction)

    is_valid = validation_result["is_valid"]
    errors = validation_result["errors"]

    print("✓ Validation completed")
    print(f"  - Valid: {is_valid}")
    print(f"  - Errors: {len(errors)}")
    if errors:
        for error in errors:
            print(f"    - {error.error_type}: {error.message}")

    return validation_result


def test_schema_json_serialization():
    """Test that schemas can be serialized to JSON."""
    print("\n=== Test 4: Schema Serialization ===")

    tools = test_tool_parsing()
    entities = test_entity_parsing()

    # Serialize tools to JSON
    tools_json = json.dumps(
        [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                    }
                    for p in tool.parameters
                ],
            }
            for tool in tools.tools
        ]
    )

    # Serialize entities to JSON
    entities_json = json.dumps(
        [
            {
                "name": entity.name,
                "description": entity.description,
                "fields": [
                    {
                        "name": f.name,
                        "type": f.type,
                    }
                    for f in entity.fields
                ],
            }
            for entity in entities.entities
        ]
    )

    # Verify we got valid JSON
    tools_data = json.loads(tools_json)
    entities_data = json.loads(entities_json)

    assert len(tools_data) == 2
    assert len(entities_data) == 2

    print("✓ Schema serialization works correctly")
    print(f"  - Tools JSON: {len(tools_json)} bytes")
    print(f"  - Entities JSON: {len(entities_json)} bytes")


def test_end_to_end():
    """Test end-to-end extraction (without LLM steps)."""
    print("\n=== Test 5: End-to-End Extraction (Steps 1, 2a, 4) ===")

    tools_schema = {
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "lookup_order",
                    "description": "Get order details",
                    "parameters": {
                        "type": "object",
                        "properties": {"order_id": {"type": "string"}},
                        "required": ["order_id"],
                    },
                },
            }
        ]
    }

    entity_schema = {
        "entities": [
            {
                "name": "Order",
                "description": "Order data",
                "fields": [
                    {"name": "order_id", "type": "string", "required": True},
                    {"name": "price", "type": "number"},
                ],
            }
        ]
    }

    system_prompt = "You are a helpful customer service agent for an e-commerce company."

    extractor = AgentTestSpaceExtractor()

    # Extract all components
    result = extractor.extract_all(
        tools_schema,
        entity_schema,
        system_prompt,
        validate=False,  # Skip validation since we don't have full prompt extraction
    )

    assert "tools" in result
    assert "entities" in result
    assert len(result["tools"].tools) == 1
    assert len(result["entities"].entities) == 1

    print("✓ End-to-end extraction works correctly")
    print(f"  - Tools: {len(result['tools'].tools)}")
    print(f"  - Entities: {len(result['entities'].entities)}")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AgentTestSpaceExtractor Integration Tests")
    print("=" * 60)

    try:
        test_tool_parsing()
        test_entity_parsing()
        test_validation()
        test_schema_json_serialization()
        test_end_to_end()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
