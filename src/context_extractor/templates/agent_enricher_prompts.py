"""LLM prompt templates for agent enricher."""

TOOL_RETURN_SCHEMA_PROMPT = """Given this tool, entities, and agent intents, infer the return schema for the tool.

Tool:
{tool_text}{code_section}

Entities:
{entities_text}

Determine:
1. Return type: "entity" (if returns entity data), "boolean" (if yes/no), "string" (if text/decision), "number" (if numeric), "array" (if list), or "object"
2. If type is "entity", specify which entity name
3. Brief description of what the tool returns

Respond with valid JSON matching this structure:
{{
  "name": "{tool_name}",
  "returns": {{
    "type": "entity|boolean|string|number|array|object",
    "entity_name": "entity_name or null",
    "description": "what this returns"
  }}
}}"""

CODE_RULES_EXTRACTION_PROMPT = """Analyze the code below and extract ONLY meaningful business rules that define actual business logic and decision-making.

IGNORE implementation details such as type conversions, error handling, and variable assignments that are just data transformations.

ONLY extract rules that represent actual business logic and decision-making (e.g., "orders over $50 get free shipping"). Be sure to replace constants with their actual values.

Tool:
{tool_text}

Code:
```python
{all_code}
```

Entities:
{entities_text}

For each meaningful business rule, provide:
- description: A clear description of the business rule (focus on WHAT the rule is, not HOW it's implemented)
- conditions: List of business conditions that trigger this rule (e.g., ["order_total >= 50", "customer_tier == 'platinum'", "order_status == 'pending'"])
- actions: List of outcomes of the rule (e.g., ["free shipping", "refund approved", "order can be cancelled"])

Respond with valid JSON matching this structure:
{{
  "rules": [
    {{
      "description": "what this rule is",
      "conditions": ["condition1", "condition2"],
      "actions": ["outcome1", "outcome2"]
    }}
  ]
}}

If no meaningful business rules are found (only implementation details), return an empty rules array: {{"rules": []}}"""

ENTITY_THRESHOLDS_EXTRACTION_PROMPT = """Extract ALL thresholds and decision boundaries for each entity from the system prompt and business rules below.
Use detailed threshold names formatted in snake_case and use the exact values as they appear in the system prompt and rules. Include the unit if mentioned.

Entities:
{entities_text}

System Prompt:
{system_prompt}

Respond with valid JSON matching the following example structure for each entity:
{{
  "entities": [
    {{
      "name": "customer",
      "thresholds": [
        {{
          "name": "standard_refund_window_days",
          "value": 30,
          "description": "Number of days in the refund window",
          "unit": "days"
        }}
      ]
    }}
  ]
}}"""
