"""Enrich intent rules with structured conditions."""

import json
from ..schemas.prompt_schema import Intent, StructuredIntent, StructuredIntentRule, StructuredCondition
from ..schemas.entity_schema import EntitySchemaList
from ..schemas.tool_schema import EnrichedToolSchemaList


class RuleEnricher:
    """Converts natural language rules to structured rules with explicit conditions."""

    def __init__(self, llm_client=None):
        self.client = llm_client

    def enrich_intent_rules(
        self,
        intent: Intent,
        entities: EntitySchemaList,
        tools: EnrichedToolSchemaList,
    ) -> StructuredIntent:
        """Convert natural language rules to structured rules."""
        if not self.client:
            return self._intent_to_structured(intent, [])

        structured_rules = self._enrich_rules(intent, entities, tools)

        return StructuredIntent(
            name=intent.name,
            description=intent.description,
            required_slots=intent.required_slots,
            workflow=intent.workflow,
            rules=structured_rules,
            requires_confirmation=intent.requires_confirmation,
            outcomes=intent.outcomes,
        )

    def _enrich_rules(
        self,
        intent: Intent,
        entities: EntitySchemaList,
        tools: EnrichedToolSchemaList,
    ) -> list[StructuredIntentRule]:
        """Use LLM to convert natural language rules to structured rules."""
        entities_text = self._format_entities(entities)
        tools_text = self._format_tools(tools)
        rules_text = self._format_rules(intent)
        outcomes_text = self._format_outcomes(intent)
        slots_text = self._format_slots(intent)

        llm_prompt = f"""Convert natural language rules to structured JSON rules.

## CONSTRAINTS
1. Only generate rules for THIS intent ({intent.name}) — ignore other intents
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
    {{"id": "gold_outside_window", "conditions": [{{"field": "customer.tier", "operator": "eq", "value": "gold"}}, {{"field": "order.delivered_date_days_ago", "operator": "gt", "value": 60}}, {{"field": "is_damaged", "operator": "eq", "value": false}}], "outcome": "DENIED", "expected_behavior": "Agent expresses empathy. Agent explains refund cannot be processed. Agent cites the 60-day refund window for Gold tier customers. Agent mentions how many days it has been since delivery. Agent offers alternatives if applicable. Agent maintains professional tone."}},
    {{"id": "platinum_outside_window", "conditions": [{{"field": "customer.tier", "operator": "eq", "value": "platinum"}}, {{"field": "order.delivered_date_days_ago", "operator": "gt", "value": 90}}, {{"field": "is_damaged", "operator": "eq", "value": false}}], "outcome": "DENIED", "expected_behavior": "Agent expresses empathy. Agent explains refund cannot be processed. Agent cites the 90-day refund window for Platinum tier customers. Agent mentions how many days it has been since delivery. Agent offers alternatives if applicable. Agent maintains professional tone."}},
    {{"id": "auto_approve_under_200", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": false}}, {{"field": "order.price", "operator": "lt", "value": 200}}], "outcome": "APPROVED", "expected_behavior": "Agent confirms the refund is approved. Agent states the exact refund amount. Agent provides timeline for processing (3-5 business days). Agent thanks customer. Agent does NOT mention needing approval since amount is under $200."}},
    {{"id": "pending_200_to_1000", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": false}}, {{"field": "order.price", "operator": "gte", "value": 200}}, {{"field": "order.price", "operator": "lte", "value": 1000}}], "outcome": "PENDING_REVIEW", "expected_behavior": "Agent explains the refund request has been submitted. Agent states it requires manager approval due to the amount. Agent provides expected timeline for review (1-2 business days). Agent assures customer they will be notified of the decision. Agent does NOT promise approval."}},
    {{"id": "pending_over_1000", "conditions": [{{"field": "is_damaged", "operator": "eq", "value": false}}, {{"field": "order.price", "operator": "gt", "value": 1000}}], "outcome": "PENDING_REVIEW", "expected_behavior": "Agent explains the refund request has been submitted. Agent states it requires executive approval due to the amount exceeding $1000. Agent provides expected timeline for review (2-3 business days). Agent assures customer they will be notified of the decision. Agent does NOT promise approval."}}
  ]
}}
```

Key patterns demonstrated:
- Each rule has a specific expected_behavior describing what action the agent should take
- Override rule (damaged) listed first
- Tier-dependent threshold → 3 separate DENIED rules with concrete values (30/60/90)
- Price thresholds → 3 rules covering all ranges
- All 3 outcomes have paths to them
- `is_damaged: false` included in non-damaged rules to prevent overlap

## YOUR TASK

Intent: {intent.name}
Description: {intent.description}

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

Convert ONLY these rules into structured format. Output valid JSON:
{{
  "rules": [
    {{
      "id": "rule_id",
      "description": "when this rule applies",
      "conditions": [
        {{"field": "entity.field", "operator": "op", "value": "val"}}
      ],
      "outcome": "outcome_name",
      "expected_behavior": "how the agent should respond to the user when this rule matches"
    }}
  ]
}}"""

        response = self._call_llm(llm_prompt)
        return self._parse_rules_response(response)

    def _format_entities(self, entities: EntitySchemaList) -> str:
        """Format entities with their fields and thresholds."""
        lines = []
        for entity in entities.entities:
            lines.append(f"\n{entity.name}:")
            lines.append(f"  Description: {entity.description}")
            if entity.fields:
                lines.append(f"  Fields:")
                for field in entity.fields:
                    lines.append(f"    - {field.name} ({field.type}): {field.description} {f', Enum: {field.enum}' if field.enum else ''}")
            if entity.thresholds:
                lines.append(f"  Thresholds:")
                for threshold in entity.thresholds:
                    unit_str = f" {threshold.unit}" if threshold.unit else ""
                    lines.append(f"    - {threshold.name}: {threshold.value}{unit_str}")
        return "\n".join(lines)

    def _format_tools(self, tools: EnrichedToolSchemaList) -> str:
        """Format available tools."""
        lines = []
        for tool in tools.tools:
            lines.append(f"\n{tool.name}:")
            lines.append(f"  Description: {tool.description}")
            if tool.parameters:
                lines.append(f"  Parameters:")
                for param in tool.parameters:
                    lines.append(f"    - {param.name} ({param.type}): {param.description}")
        return "\n".join(lines)

    def _format_rules(self, intent: Intent) -> str:
        """Format natural language rules."""
        lines = []
        for rule in intent.rules:
            lines.append(f"\n- Description: {rule.description}")
            if rule.conditions:
                lines.append(f"  Conditions: {', '.join(rule.conditions)}")
            if rule.actions:
                lines.append(f"  Actions: {', '.join(rule.actions)}")
        return "\n".join(lines)

    def _format_outcomes(self, intent: Intent) -> str:
        """Format available outcomes."""
        lines = []
        for outcome in intent.outcomes:
            lines.append(f"- {outcome.outcome_name}: {outcome.description}")
        return "\n".join(lines)

    def _format_slots(self, intent: Intent) -> str:
        """Format required slots with their sources."""
        lines = []
        for slot in intent.required_slots:
            lines.append(f"- {slot.slot_name} (source: {slot.source})")
        return "\n".join(lines) if lines else "None"


    def _call_llm(self, prompt: str) -> str:
        """Call LLM and extract JSON."""
        if not self.client:
            raise RuntimeError("LLM client not initialized")

        response = self.client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content

        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        return content

    def _parse_rules_response(self, response: str) -> list[StructuredIntentRule]:
        """Parse LLM response into StructuredIntentRule objects."""
        data = json.loads(response)
        rules = []

        for rule_def in data.get("rules", []):
            conditions = []
            for cond_def in rule_def.get("conditions", []):
                condition = StructuredCondition(
                    field=cond_def.get("field", ""),
                    operator=cond_def.get("operator", ""),
                    value=cond_def.get("value"),
                )
                conditions.append(condition)

            rule = StructuredIntentRule(
                id=rule_def.get("id", ""),
                description=rule_def.get("description", ""),
                conditions=conditions,
                outcome=rule_def.get("outcome", ""),
                expected_behavior=rule_def.get("expected_behavior", ""),
            )
            rules.append(rule)

        return rules

    def _intent_to_structured(
        self,
        intent: Intent,
        structured_rules: list[StructuredIntentRule],
    ) -> StructuredIntent:
        """Convert Intent to StructuredIntent."""
        return StructuredIntent(
            name=intent.name,
            description=intent.description,
            required_slots=intent.required_slots,
            workflow=intent.workflow,
            rules=structured_rules,
            requires_confirmation=intent.requires_confirmation,
            outcomes=intent.outcomes,
        )
