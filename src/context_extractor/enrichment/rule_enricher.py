"""Enrich intent rules with structured conditions."""

import json
from ..schemas.prompt_schema import Intent, StructuredIntent, StructuredIntentRule, StructuredCondition
from ..schemas.entity_schema import EntitySchemaList
from ..schemas.tool_schema import EnrichedToolSchemaList
from ..templates import RULES_STRUCTURING_PROMPT


class RuleEnricher:
    """Converts natural language rules to structured rules with explicit conditions."""

    def __init__(self, llm_client=None):
        self.client = llm_client

    def enrich_intent_rules(
        self,
        tools: EnrichedToolSchemaList,
        entities: EntitySchemaList,
        intent: Intent,
    ) -> StructuredIntent:
        """Convert natural language rules to structured rules."""
        if not self.client:
            return self._intent_to_structured(intent, [])

        structured_rules = self._enrich_rules(tools, entities, intent)

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
        tools: EnrichedToolSchemaList,
        entities: EntitySchemaList,
        intent: Intent,
    ) -> list[StructuredIntentRule]:
        """Use LLM to convert natural language rules to structured rules."""
        entities_text = self._format_entities(entities)
        tools_text = self._format_tools(tools)
        rules_text = self._format_rules(intent)
        outcomes_text = self._format_outcomes(intent)
        slots_text = self._format_slots(intent)

        llm_prompt = RULES_STRUCTURING_PROMPT.format(
            intent_name=intent.name,
            intent_description=intent.description,
            slots_text=slots_text,
            outcomes_text=outcomes_text,
            entities_text=entities_text,
            tools_text=tools_text,
            rules_text=rules_text,
        )

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
