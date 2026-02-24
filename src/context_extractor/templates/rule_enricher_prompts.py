"""LLM prompt templates for rule enricher."""

RULES_STRUCTURING_PROMPT = """Convert natural language rules to structured JSON rules.

## CONSTRAINTS
1. Only generate rules for THIS intent ({intent_name}) — ignore other intents
2. Use ONLY enum values from the schema — never invent values like 'yes'/'no'
3. Use concrete threshold values — no dynamic references like `get_refund_window(tier)`
4. Cover ALL outcomes — every outcome needs at least one rule path
5. For enum fields, cover ALL possible values exhaustively

## OPERATORS
eq, ne, lt, lte, gt, gte, in, not_in, exists, missing

## FIELD NAMING
- Entity fields: `entity.field` (e.g., `order.status`)
- Slot fields: just the name (e.g., `is_damaged`)

## EXAMPLE
Intent: process_refund
Entities:
- customer.tier enum: [standard, gold, platinum]
- order.price (number)
- order.delivered_date_days_ago (integer)
Thresholds: standard_window=30, gold_window=60, platinum_window=90, auto_approve=200, manager_limit=1000
Slots: is_damaged (boolean)
Outcomes: [APPROVED, DENIED, PENDING_REVIEW]

Rules:
- "Damaged items always get refund"
- "Must be within refund window (varies by tier)"
- "Under $200 auto-approved, $200-$1000 manager review, over $1000 executive review"

Output:
```json
{{
  "rules": [
    {{"id": "damaged_approved", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": true}}], "outcome": "APPROVED", "expected_behavior": "Refund approved for damaged item.", "expected_tool_calls": []}},
    {{"id": "standard_outside_window", "conditions": [{{"field": "customer.tier", "operator": "eq", "value": "standard"}}, {{"field": "order.delivered_date_days_ago", "operator": "gt", "value": 30}}, {{"field": "is_damaged", "operator": "eq", "value": false}}], "outcome": "DENIED", "expected_behavior": "Refund denied: outside 30-day window for Standard tier.", "expected_tool_calls": []}},
    {{"id": "auto_approve_under_200", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": false}}, {{"field": "order.price", "operator": "lt", "value": 200}}], "outcome": "APPROVED", "expected_behavior": "Refund approved.", "expected_tool_calls": []}},
    {{"id": "pending_200_to_1000", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": false}}, {{"field": "order.price", "operator": "gte", "value": 200}}, {{"field": "order.price", "operator": "lte", "value": 1000}}], "outcome": "PENDING_REVIEW", "expected_behavior": "Refund requires manager approval.", "expected_tool_calls": ["slack_post_message"]}}
  ]
}}
```

Key patterns demonstrated:
- Each rule has a specific expected_behavior describing what action the agent should take
- Override rule (damaged) listed first
- Tier-dependent threshold → separate DENIED rules with concrete values
- Price thresholds → multiple rules covering all ranges
- All outcomes have paths to them
- Slot conditions included to prevent overlap

## YOUR TASK

Intent: {intent_name}
Description: {intent_description}

Required slots (user/tool inputs):
{slots_text}

Available outcomes:
{outcomes_text}

Entity definitions:
{entities_text}

Available tools:
{tools_text}

External tools (MCP):
{external_tools_text}

Natural language rules to convert:
{rules_text}

Convert ONLY these rules into structured format. For each rule, include:
- **id**: Unique rule identifier
- **description**: When this rule applies
- **conditions**: List of conditions that must be true
- **outcome**: The outcome this rule leads to
- **expected_behavior**: Only core, objective outcomes the agent must communicate, not suggestions
- **expected_tool_calls**: List of external/MCP tool names the agent must call when this rule matches. ONLY use tool names from the "External tools (MCP)" list above. Use an empty list if no external tools are needed.

Output valid JSON:
{{
  "rules": [
    {{
      "id": "rule_id",
      "description": "when this rule applies",
      "conditions": [
        {{"field": "entity.field", "operator": "op", "value": "val"}}
      ],
      "outcome": "outcome_name",
      "expected_behavior": "objective outcomes the agent must communicate",
      "expected_tool_calls": ["tool_name_1", "tool_name_2"]
    }}
  ]
}}"""
