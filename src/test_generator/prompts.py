"""LLM prompts for test case generation."""

TEST_CASE_GENERATION_PROMPT = """You are generating realistic test cases for validating agent behavior.

## Context

Agent Intent: {intent_name}
Intent Description: {intent_description}

## Rule to Test

Rule Description: {rule_description}

Rule Conditions (structured):
{conditions}

Expected Behavior: {expected_behavior}

## Entity Schema (available entities and fields)

{entities_schema}

## Task

Generate a realistic test case that would trigger this rule. The test case must:
1. Have backend_state with entity instances that satisfy ALL conditions
2. Have an agent input that would naturally trigger this intent
3. Be realistic - use believable IDs, names, and values
4. Fill in all required fields in entity instances

Return a JSON object matching this exact schema:
```json
{{
  "test_id": "intent_name_rule_description_keywords",
  "description": "Human readable description of what this test validates",
  "backend_state": {{
    "entity_name": [
      {{
        "field1": "value1",
        "field2": "value2"
      }}
    ]
  }},
  "input": {{
    "message": "Customer message to agent",
    "context": {{"customer_id": "CUST-XXX"}}
  }},
  "category": "happy_path|edge_case|boundary|invalid_input|error_handling"
}}
```

Rules for backend_state:
- Use entity names as keys (e.g., "orders", "customers")
- Value is a list of entity instances
- Each instance is a dict with field names as keys
- Satisfy ALL conditions in the rule conditions list
- Fill unused fields with sensible defaults
- Use realistic IDs (e.g., "ORD-001", "CUST-100")

Rules for input:
- message should be a natural customer request
- context should include IDs that reference backend_state entities
- Keep message concise but clear
"""
