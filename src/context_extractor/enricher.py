import json
from .schemas.tool_schema import ToolSchemaList, EnrichedToolSchema, EnrichedToolSchemaList, EnrichedToolReturnList
from .schemas.entity_schema import EntitySchemaList, EnrichedEntitySchema, EnrichedEntitySchemaList, EntityThreshold, EnrichedEntityThresholdList
from .schemas.prompt_schema import SystemPromptExtraction


class AgentEnricher:
    """Enriches tools and entities using LLM with full agent context from tools, entities, and system prompt."""

    def __init__(self, llm_client=None):
        self.client = llm_client

    def enrich_all(
        self,
        tools: ToolSchemaList,
        entities: EntitySchemaList,
        prompt: SystemPromptExtraction,
        system_prompt: str,
    ) -> tuple[EnrichedToolSchemaList, EnrichedEntitySchemaList]:
        enriched_tools = self._enrich_tools(tools, entities, prompt)
        enriched_entities = self._enrich_entities(entities, prompt, system_prompt)

        return enriched_tools, enriched_entities

    def _enrich_tools(
        self,
        tools: ToolSchemaList,
        entities: EntitySchemaList,
        prompt: SystemPromptExtraction,
    ) -> EnrichedToolSchemaList:
        """Enrich tools with return schemas using LLM."""
        tools_text = self._format_tools(tools)
        entities_text = self._format_entities(entities)
        intents_text = self._format_intents(prompt)

        llm_prompt = f"""Given these tools, entities, and agent intents, infer the return schema for each tool.

Tools:
{tools_text}

Entities:
{entities_text}

Intents and Rules:
{intents_text}

For each tool, determine:
1. Return type: "entity" (if returns entity data), "boolean" (if yes/no), "string" (if text/decision), "number" (if numeric), "array" (if list), or "object"
2. If type is "entity", specify which entity name
3. Brief description of what the tool returns

Respond with valid JSON matching this structure:
{{
  "tools": [
    {{
      "name": "tool_name",
      "returns": {{
        "type": "entity|boolean|string|number|array|object",
        "entity_name": "entity_name or null",
        "description": "what this returns"
      }}
    }}
  ]
}}"""

        response = self._call_llm(llm_prompt)
        enriched = self._parse_tools_response(response, tools)
        return enriched

    def _enrich_entities(
        self,
        entities: EntitySchemaList,
        prompt: SystemPromptExtraction,
        system_prompt: str,
    ) -> EnrichedEntitySchemaList:
        """Enrich entities with thresholds using LLM."""
        entities_text = self._format_entities(entities)
        rules_text = self._format_rules(prompt)

        llm_prompt = f"""Extract ALL thresholds and decision boundaries for each entity from the system prompt and business rules below. 
Use detailed threshold names formatted in snake_case and use the exact values as they appear in the system prompt and rules. Include the unit if mentioned.

Entities:
{entities_text}

System Prompt:
{system_prompt}

Business Rules:
{rules_text}

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
        response = self._call_llm(llm_prompt)
        enriched = self._parse_entities_response(response, entities)
        return enriched

    def _format_tools(self, tools: ToolSchemaList) -> str:
        """Format tools for LLM input."""
        return "\n".join(f"- {tool.name}: {tool.description}" for tool in tools.tools)

    def _format_entities(self, entities: EntitySchemaList) -> str:
        """Format entities for LLM input."""
        return "\n".join(f"- {entity.name}: {entity.description}" for entity in entities.entities)

    def _format_intents(self, prompt: SystemPromptExtraction) -> str:
        """Format intents for LLM input."""
        return "\n".join(f"- {intent.name}: {intent.description}, workflow: {' -> '.join(intent.workflow)}" for intent in prompt.intents)

    def _format_rules(self, prompt: SystemPromptExtraction) -> str:
        """Format rules for LLM input."""
        return "\n".join(f"- {rule.name}: {rule.description}, behavior: {rule.behavior}" for rule in prompt.global_rules)

    def _call_llm(self, prompt: str) -> str:
        """Call LLM and extract JSON from response."""
        if not self.client:
            return "{}"

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
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
        except Exception:
            return "{}"

    def _parse_tools_response(
        self, response: str, original_tools: ToolSchemaList
    ) -> EnrichedToolSchemaList:
        """Parse LLM response and convert to EnrichedToolSchemaList."""
        try:
            data = json.loads(response)
            enriched_data = EnrichedToolReturnList(**data)

            tools_dict = {t.name: t for t in original_tools.tools}
            enriched_list = []

            for enriched_tool in enriched_data.tools:
                original = tools_dict.get(enriched_tool.name)
                if original:
                    updated = {
                        **original.model_dump(),
                        "returns": enriched_tool.returns.model_dump(),
                    }

                    enriched_list.append(EnrichedToolSchema(**updated))

            return EnrichedToolSchemaList(tools=enriched_list)
        except Exception:
            enriched_list = [
                EnrichedToolSchema(
                    **{**t.model_dump(), "returns": {"type": "unknown", "entity_name": None, "description": ""}}
                )
                for t in original_tools.tools
            ]
            return EnrichedToolSchemaList(tools=enriched_list)

    def _parse_entities_response(
        self, response: str, original_entities: EntitySchemaList
    ) -> EnrichedEntitySchemaList:
        """Parse LLM response and convert to EnrichedEntitySchemaList."""
        try:
            data = json.loads(response)
            enriched_data = EnrichedEntityThresholdList(**data)
            entities_dict = {e.name: e for e in original_entities.entities}
            enriched_list = []
            for enriched_entity in enriched_data.entities:
                original = entities_dict.get(enriched_entity.name)
                if original:
                    thresholds = [
                        EntityThreshold(
                            name=t.name,
                            value=t.value,
                            description=t.description,
                            unit=t.unit,
                        )
                        for t in enriched_entity.thresholds
                    ]

                    updated = {
                        **original.model_dump(),
                        "thresholds": [t.model_dump() for t in thresholds],
                    }
                    enriched_list.append(EnrichedEntitySchema(**updated))

            return EnrichedEntitySchemaList(entities=enriched_list)
        except Exception as e:
            raise e
