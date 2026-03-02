import logging

from openai import OpenAI

from ..schemas.prompt_schema import (
    SystemPromptExtraction,
    Intent,
    IntentListResponse,
    AgentIdentityResponse,
)
from ..schemas.tool_schema import EnrichedToolSchemaList, ToolCodeRuleList
from ...config import EXTRACTION_MODEL
from ...utils import format_tools_with_returns
from ..templates import INTENT_EXTRACTION_PROMPT, AGENT_IDENTITY_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class SystemPromptParser:
    """Extracts intents from system prompts using LLM analysis."""

    def __init__(self, client: OpenAI):
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
            model=EXTRACTION_MODEL,
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
        tools_context = format_tools_with_returns(tools)
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
                model=EXTRACTION_MODEL,
                input=[{"role": "user", "content": prompt}],
                text_format=AgentIdentityResponse,
                temperature=0,
            )
            result = response.output_parsed
            return result.name, result.role
        except Exception:
            logger.warning(
                "Failed to extract agent identity, using defaults", exc_info=True
            )
            return "Agent", "AI Assistant"
