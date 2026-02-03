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
    {{"id": "damaged_approved", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": true}}], "outcome": "APPROVED", "expected_behavior": "Agent apologizes for the damaged item. Agent confirms the refund is approved. Agent states the refund amount. Agent provides timeline (3-5 business days). Agent does NOT mention refund window since damaged items are always eligible."}},
    {{"id": "standard_outside_window", "conditions": [{{"field": "customer.tier", "operator": "eq", "value": "standard"}}, {{"field": "order.delivered_date_days_ago", "operator": "gt", "value": 30}}, {{"field": "is_damaged", "operator": "eq", "value": false}}], "outcome": "DENIED", "expected_behavior": "Agent expresses empathy. Agent explains refund cannot be processed. Agent cites the 30-day refund window for Standard tier customers. Agent mentions how many days it has been since delivery. Agent offers alternatives if applicable (e.g., store credit, exchange). Agent maintains professional tone."}},
    {{"id": "auto_approve_under_200", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": false}}, {{"field": "order.price", "operator": "lt", "value": 200}}], "outcome": "APPROVED", "expected_behavior": "Agent confirms the refund is approved. Agent states the exact refund amount. Agent provides timeline for processing (3-5 business days). Agent thanks customer. Agent does NOT mention needing approval since amount is under $200."}},
    {{"id": "pending_200_to_1000", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": false}}, {{"field": "order.price", "operator": "gte", "value": 200}}, {{"field": "order.price", "operator": "lte", "value": 1000}}], "outcome": "PENDING_REVIEW", "expected_behavior": "Agent explains the refund request has been submitted. Agent states it requires manager approval due to the amount. Agent provides expected timeline for review (1-2 business days). Agent assures customer they will be notified of the decision. Agent does NOT promise approval."}}
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

Natural language rules to convert:
{rules_text}

Convert ONLY these rules into structured format. For each rule, include:
- **id**: Unique rule identifier
- **description**: When this rule applies
- **conditions**: List of conditions that must be true
- **outcome**: The outcome this rule leads to
- **expected_behavior**: What the agent should do/say when this rule matches (this is used to evaluate if the agent behaves correctly)

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
      "expected_behavior": "what the agent should do when this rule matches"
    }}
  ]
}}"""
