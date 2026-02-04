import json
from ..schemas.prompt_schema import (
    SystemPromptExtraction,
    Intent,
    IntentRule,
    IntentOutcome,
    IntentRequiredSlot,
)
from ..schemas.tool_schema import EnrichedToolSchemaList, ToolCodeRuleList
from ..schemas.entity_schema import EnrichedEntitySchemaList
from ..templates import INTENT_EXTRACTION_PROMPT, AGENT_IDENTITY_EXTRACTION_PROMPT


class SystemPromptParser:
    """Extracts intents from system prompts using LLM analysis."""

    def __init__(self, client=None):
        """Initialize parser with optional LLM client."""
        self.client = client

    def parse_system_prompt(
        self,
        tools: EnrichedToolSchemaList,
        code_rules: ToolCodeRuleList,
        system_prompt: str,
    ) -> SystemPromptExtraction:
        """Extract intents and agent identity from system prompt."""
        intents = self.extract_intents(tools, code_rules, system_prompt)
        agent_name, agent_role = self._extract_agent_identity(system_prompt)

        return SystemPromptExtraction(
            agent_name=agent_name,
            agent_role=agent_role,
            intents=intents,
        )

    def extract_intents(
        self,
        tools: EnrichedToolSchemaList,
        code_rules: ToolCodeRuleList,
        system_prompt: str,
    ) -> list[Intent]:
        """Use LLM to identify goals and tasks the agent can help with."""
        prompt = self._build_intent_extraction_prompt(tools, code_rules, system_prompt)
        response = self._call_llm(prompt)
        intents = self._parse_intent_response(response)
        return intents

    def _build_intent_extraction_prompt(
        self,
        tools: EnrichedToolSchemaList,
        code_rules: ToolCodeRuleList,
        system_prompt: str,
    ) -> str:
        """Build LLM prompt for intent extraction."""
        tools_context = self._format_tools_context(tools)
        code_rules_context = "\n".join(
            f"- {rule.description}" for rule in code_rules.rules
        )
        source_options = "user_input"
        if tools.tools:
            source_options += " | " + " | ".join(tool.name for tool in tools.tools)

        return INTENT_EXTRACTION_PROMPT.format(
            system_prompt=system_prompt,
            tools_context=tools_context,
            code_rules_context=code_rules_context,
            source_options=source_options,
        )

    def _extract_agent_identity(self, system_prompt: str) -> tuple[str, str]:
        """Use LLM to extract agent's name and role."""
        prompt = AGENT_IDENTITY_EXTRACTION_PROMPT.format(system_prompt=system_prompt)

        response = self._call_llm(prompt)

        try:
            data = json.loads(response)
            name = data.get("name", "Agent")
            role = data.get("role", "AI Assistant")
            return name, role
        except (json.JSONDecodeError, TypeError):
            return "Agent", "AI Assistant"

    def _call_llm(self, prompt: str) -> str:
        """Call LLM and extract JSON from response, handling markdown code blocks."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content

        # Extract JSON from markdown code blocks if present
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

    def _parse_intent_response(self, response: str) -> list[Intent]:
        """Parse JSON response from LLM and convert to Intent objects."""
        intents = []

        try:
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    # Parse rules
                    rules = []
                    for rule_def in item.get("rules", []):
                        rule = IntentRule(
                            description=rule_def.get("description", ""),
                            conditions=rule_def.get("conditions", []),
                            actions=rule_def.get("actions", []),
                        )
                        rules.append(rule)

                    # Parse outcomes
                    outcomes = []
                    for outcome_def in item.get("outcomes", []):
                        outcome = IntentOutcome(
                            outcome_name=outcome_def.get("outcome_name", ""),
                            description=outcome_def.get("description", ""),
                        )
                        outcomes.append(outcome)

                    required_slots = []
                    for slot_def in item.get("required_slots", []):
                        if isinstance(slot_def, dict):
                            slot = IntentRequiredSlot(
                                slot_name=slot_def.get("slot_name", "unknown"),
                                source=slot_def.get("source", "user_input"),
                            )
                            required_slots.append(slot)

                    intent = Intent(
                        name=item.get("name", "unknown"),
                        description=item.get("description", ""),
                        required_slots=required_slots,
                        workflow=item.get("workflow", []),
                        rules=rules,
                        requires_confirmation=item.get("requires_confirmation", False),
                        outcomes=outcomes,
                    )
                    intents.append(intent)
        except (json.JSONDecodeError, TypeError):
            pass

        return intents

    def _format_tools_context(self, tools: EnrichedToolSchemaList) -> str:
        return "\n".join(
            (
                f"- {tool.name}: {tool.description}" + f" -> {tool.returns.type}"
                if tool.returns
                else ""
            )
            for tool in tools.tools
        )
        # """Brief tool summary - name, description, returns."""
        # lines = []
        # for tool in tools.tools:
        #     if tool.returns:
        #         returns = f" -> {tool.returns.type}"
        #         if tool.returns.entity_name:
        #             returns += f" -> {tool.returns.entity_name}"
        #     else:
        #         returns = ""
        #     lines.append(f"- {tool.name}: {tool.description}{returns}")
        # return "\n".join(lines)

    def _format_entities_context(self, entities: EnrichedEntitySchemaList) -> str:
        """Format entities with fields, enums, and thresholds."""
        lines = []
        for entity in entities.entities:
            line = f"- {entity.name}: {entity.description}"
            if entity.fields:
                for field in entity.fields:
                    line += f" {field.name}: {field.type}"
                    if field.enum:
                        line += f" (enum: {field.enum})"
            if entity.thresholds:
                for threshold in entity.thresholds:
                    line += (
                        f" {threshold.name}: {threshold.value} {threshold.unit or ''}"
                    )
            lines.append(line)
        return "\n".join(lines)
