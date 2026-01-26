"""Main orchestrator for agent test space extraction."""

from typing import Optional
from pathlib import Path

from .parsers import (
    parse_tools,
    parse_entity_schema,
    enrich_entities_from_tools,
    EntityEnricher,
    SystemPromptParser,
)
from .validation import AgentTestValidator
from .schemas import ToolSchemaOutput, EntitySchemaOutput, SystemPromptExtraction


class AgentTestSpaceExtractor:
    """
    Extracts the complete test input space for an AI agent.

    This is a 4-step pipeline:
    1. Parse tool schemas (programmatic)
    2a. Parse entity schemas (programmatic)
    2b. Enrich entities with business logic (LLM-based)
    3. Parse system prompt (LLM-based)
    4. Validate outputs (programmatic)
    """

    def __init__(self, llm_client=None):
        """
        Initialize the extractor.

        Args:
            llm_client: LLM client for steps 2b and 3. If None, those steps are skipped.
        """
        self.llm_client = llm_client
        self.validator = AgentTestValidator()
        self.entity_enricher = EntityEnricher(llm_client)
        self.prompt_parser = SystemPromptParser(llm_client)

    def extract_all(
        self,
        tools_schema: str | dict | Path,
        entity_schema: str | dict | Path,
        system_prompt: str,
        validate: bool = True,
    ) -> dict:
        """
        Extract all agent information in one call.

        Args:
            tools_schema: Tool schema (JSON/OpenAPI format)
            entity_schema: Entity schema (YAML/JSON format)
            system_prompt: System prompt containing business logic
            validate: Whether to validate outputs

        Returns:
            Dictionary with extracted information:
            {
                'tools': ToolSchemaOutput,
                'entities': EntitySchemaOutput,
                'prompt': SystemPromptExtraction,
                'validation': ValidationResult (if validate=True)
            }
        """
        # Step 1: Parse tool schemas
        tools = self.step1_parse_tools(tools_schema)

        # Step 2a: Parse entity schemas
        entities = self.step2a_parse_entities(entity_schema)

        # Step 2b: Enrich entities
        entities = self.step2b_enrich_entities(entities, tools, system_prompt)

        # Step 3: Parse system prompt
        prompt_extraction = self.step3_parse_prompt(system_prompt, tools, entities)

        # Step 4: Validate
        validation_result = None
        if validate:
            validation_result = self.step4_validate(tools, entities, prompt_extraction)

        result = {
            "tools": tools,
            "entities": entities,
            "prompt": prompt_extraction,
        }

        if validation_result:
            result["validation"] = validation_result

        return result

    def step1_parse_tools(self, tools_schema: str | dict | Path) -> ToolSchemaOutput:
        """
        Step 1: Parse tool schemas programmatically.

        Args:
            tools_schema: Tool definitions in JSON/OpenAPI format

        Returns:
            Extracted tool schemas
        """
        return parse_tools(tools_schema)

    def step2a_parse_entities(
        self, entity_schema: str | dict | Path
    ) -> EntitySchemaOutput:
        """
        Step 2a: Parse entity schemas programmatically.

        Args:
            entity_schema: Entity definitions in YAML/JSON format

        Returns:
            Extracted entity schemas
        """
        return parse_entity_schema(entity_schema)

    def step2b_enrich_entities(
        self,
        entities: EntitySchemaOutput,
        tools: ToolSchemaOutput,
        system_prompt: Optional[str] = None,
    ) -> EntitySchemaOutput:
        """
        Step 2b: Enrich entity schemas with LLM-extracted business logic.

        Args:
            entities: Initial entity schemas
            tools: Tool schemas for context
            system_prompt: System prompt for additional context

        Returns:
            Enriched entity schemas
        """
        return self.entity_enricher.enrich_entities_with_business_logic(
            entities, tools, system_prompt
        )

    def step3_parse_prompt(
        self,
        system_prompt: str,
        tools: Optional[ToolSchemaOutput] = None,
        entities: Optional[EntitySchemaOutput] = None,
    ) -> SystemPromptExtraction:
        """
        Step 3: Parse system prompt to extract intents, rules, and refusals.

        Args:
            system_prompt: The system prompt
            tools: Tool schemas for context
            entities: Entity schemas for context

        Returns:
            Extracted system prompt structure
        """
        return self.prompt_parser.parse_system_prompt(
            system_prompt, tools, entities
        )

    def step4_validate(
        self,
        tools: ToolSchemaOutput,
        entities: EntitySchemaOutput,
        prompt_extraction: SystemPromptExtraction,
    ) -> dict:
        """
        Step 4: Validate extracted outputs.

        Args:
            tools: Extracted tool schemas
            entities: Extracted entity schemas
            prompt_extraction: Extracted prompt information

        Returns:
            Validation result with any errors found
        """
        validation_result = self.validator.validate_parsed_output(
            tools, entities, prompt_extraction
        )

        if not validation_result.is_valid:
            # Try to fix errors
            tools, entities, prompt_extraction = self.validator.fix_validation_errors(
                tools, entities, prompt_extraction, validation_result.errors
            )

        return {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
        }
