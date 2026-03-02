from ..schemas.prompt_schema import (
    SystemPromptExtraction,
    Intent,
    IntentListResponse,
    AgentIdentityResponse,
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
        response = self.client.responses.parse(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": prompt}],
            text_format=IntentListResponse,
            temperature=0,
        )
        return response.output_parsed.intents

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

        try:
            response = self.client.responses.parse(
                model="gpt-4o-mini",
                input=[{"role": "user", "content": prompt}],
                text_format=AgentIdentityResponse,
                temperature=0,
            )
            result = response.output_parsed
            return result.name, result.role
        except Exception:
            return "Agent", "AI Assistant"

    def _format_tools_context(self, tools: EnrichedToolSchemaList) -> str:
        return "\n".join(
            (
                f"- {tool.name}: {tool.description}" + f"-> {tool.returns.type}"
                if tool.returns
                else ""
            )
            for tool in tools.tools
        )

    def _format_entities_context(self, entities: EnrichedEntitySchemaList) -> str:
        """Format entities with fields, enums, and thresholds."""
        lines = []
        for entity in entities.entities:
            line = f"- {entity.name}: {entity.description}"
            if entity.fields:
                for field in entity.fields:
                    line += f"{field.name}: {field.type}"
                    if field.enum:
                        line += f"(enum: {field.enum})"
            if entity.thresholds:
                for threshold in entity.thresholds:
                    line += (
                        f"{threshold.name}: {threshold.value} {threshold.unit or ''}"
                    )
            lines.append(line)
        return "\n".join(lines)
