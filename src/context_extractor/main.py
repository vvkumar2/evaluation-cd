from pathlib import Path
from .parsers import (
    parse_tools,
    parse_entity_schema,
    SystemPromptParser,
)
from .validation import AgentTestValidator
from .enricher import AgentEnricher
from .schemas import ToolSchemaList, EntitySchemaList, EnrichedToolSchemaList, EnrichedEntitySchemaList, SystemPromptExtraction


class AgentTestSpaceExtractor:
    """Extracts agent test input space from tools, entities, and system prompt."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.validator = AgentTestValidator()
        self.enricher = AgentEnricher(llm_client)
        self.prompt_parser = SystemPromptParser(llm_client)

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
        validation_result = self.step5_validate(tools, entities, prompt_extraction)

        return {
            "tools": tools,
            "entities": entities,
            "prompt": prompt_extraction,
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

    def step5_validate(
        self,
        tools: EnrichedToolSchemaList,
        entities: EnrichedEntitySchemaList,
        prompt_extraction: SystemPromptExtraction,
    ) -> dict:
        validation_result = self.validator.validate_parsed_output(
            tools, entities, prompt_extraction
        )

        if not validation_result.is_valid:
            tools, entities, prompt_extraction = self.validator.fix_validation_errors(
                tools, entities, prompt_extraction
            )

        return {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
        }
