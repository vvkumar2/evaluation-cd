from pathlib import Path
from .parsers import (
    parse_tools,
    parse_entity_schema,
    SystemPromptParser,
)
from .validation import AgentTestValidator
from .enrichment import AgentEnricher, RuleEnricher
from .schemas import ToolSchemaList, EntitySchemaList, EnrichedToolSchemaList, EnrichedEntitySchemaList, SystemPromptExtraction, StructuredSystemPromptExtraction


class AgentTestSpaceExtractor:
    """Extracts agent test input space from tools, entities, and system prompt."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.validator = AgentTestValidator()
        self.enricher = AgentEnricher(llm_client)
        self.prompt_parser = SystemPromptParser(llm_client)
        self.rule_enricher = RuleEnricher(llm_client)

    def extract_all(
        self,
        tools_schema: str | dict | Path,
        entity_schema: str | dict | Path,
        system_prompt: str,
    ) -> dict:
        tools = self.step1_parse_tools(tools_schema)
        entities = self.step2_parse_entities(entity_schema)
        prompt_extraction = self.step3_parse_prompt(system_prompt, tools)
        tools, entities = self.step4_enrich(tools, entities, prompt_extraction, system_prompt)
        structured_prompt_extraction = self.step5_enrich_rules(prompt_extraction, entities, tools)
        validation_result = self.step6_validate(tools, entities, structured_prompt_extraction)

        return {
            "tools": tools,
            "entities": entities,
            "prompt": structured_prompt_extraction,
            "validation": validation_result,
        }

    def step1_parse_tools(self, tools_schema: str | dict | Path) -> ToolSchemaList:
        return parse_tools(tools_schema)

    def step2_parse_entities(
        self, entity_schema: str | dict | Path
    ) -> EntitySchemaList:
        return parse_entity_schema(entity_schema)

    def step3_parse_prompt(
        self,
        system_prompt: str,
        tools: ToolSchemaList = None,
    ) -> SystemPromptExtraction:
        return self.prompt_parser.parse_system_prompt(system_prompt=system_prompt, tools=tools)

    def step4_enrich(
        self,
        tools: ToolSchemaList,
        entities: EntitySchemaList,
        prompt: SystemPromptExtraction,
        system_prompt: str,
    ) -> tuple[EnrichedToolSchemaList, EnrichedEntitySchemaList]:
        return self.enricher.enrich_all(tools, entities, prompt, system_prompt)

    def step5_enrich_rules(
        self,
        prompt_extraction: SystemPromptExtraction,
        entities: EnrichedEntitySchemaList,
        tools: EnrichedToolSchemaList,
    ) -> StructuredSystemPromptExtraction:
        """Convert natural language rules to structured rules with explicit conditions."""
        structured_intents = []
        for intent in prompt_extraction.intents:
            structured_intent = self.rule_enricher.enrich_intent_rules(intent, entities, tools)
            structured_intents.append(structured_intent)

        structured_system_prompt_extraction = StructuredSystemPromptExtraction(
            agent_name=prompt_extraction.agent_name,
            agent_role=prompt_extraction.agent_role,
            intents=structured_intents,
        )
        return structured_system_prompt_extraction

    def step6_validate(
        self,
        tools: EnrichedToolSchemaList,
        entities: EnrichedEntitySchemaList,
        prompt_extraction: StructuredSystemPromptExtraction,
    ):
        return self.validator.validate_parsed_output(tools, entities, prompt_extraction)
