"""Enrich intent rules with structured conditions."""

from openai import OpenAI

from ..schemas.prompt_schema import (
    Intent,
    StructuredIntent,
    StructuredIntentRule,
    StructuredRulesResponse,
)
from ..schemas.entity_schema import EntitySchemaList
from ..schemas.tool_schema import EnrichedToolSchemaList
from ...config import EXTRACTION_MODEL
from ...utils import format_entities_detailed, format_tools
from ..templates import RULES_STRUCTURING_PROMPT


class RuleEnricher:
    """Converts natural language rules to structured rules with explicit conditions."""

    def __init__(self, llm_client: OpenAI):
        self.client = llm_client

    def enrich_intent_rules(
        self,
        tools: EnrichedToolSchemaList,
        entities: EntitySchemaList,
        intent: Intent,
        external_tool_names: list[str],
    ) -> StructuredIntent:
        """Convert natural language rules to structured rules."""
        structured_rules = self._enrich_rules(
            tools, entities, intent, external_tool_names
        )

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
        external_tool_names: list[str],
    ) -> list[StructuredIntentRule]:
        """Use LLM to convert natural language rules to structured rules."""
        entities_text = format_entities_detailed(entities)
        rules_text = self._format_rules(intent)
        outcomes_text = self._format_outcomes(intent)
        slots_text = self._format_slots(intent)

        # Separate internal vs external tools so the LLM knows which can appear in expected_tool_calls
        external_set = set(external_tool_names)
        internal_tools = EnrichedToolSchemaList(
            tools=[t for t in tools.tools if t.name not in external_set]
        )
        tools_text = format_tools(internal_tools)
        external_tools_text = (
            ", ".join(external_tool_names) if external_tool_names else "none"
        )

        llm_prompt = RULES_STRUCTURING_PROMPT.format(
            intent_name=intent.name,
            intent_description=intent.description,
            slots_text=slots_text,
            outcomes_text=outcomes_text,
            entities_text=entities_text,
            tools_text=tools_text,
            external_tools_text=external_tools_text,
            rules_text=rules_text,
        )

        response = self.client.responses.parse(
            model=EXTRACTION_MODEL,
            input=[{"role": "user", "content": llm_prompt}],
            text_format=StructuredRulesResponse,
        )
        return response.output_parsed.rules

    def _format_rules(self, intent: Intent) -> str:
        """Format natural language rules."""
        lines = []
        for rule in intent.rules:
            lines.append(f"\n- Description: {rule.description}")
            if rule.conditions:
                lines.append(f"Conditions: {', '.join(rule.conditions)}")
            if rule.actions:
                lines.append(f"Actions: {', '.join(rule.actions)}")
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
