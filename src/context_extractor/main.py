from pathlib import Path
from .parsers import (
    parse_tools,
    parse_entity_schema,
    SystemPromptParser,
)
from .validation import AgentTestValidator, ValidationResult
from .enrichment import AgentEnricher, RuleEnricher
from .schemas import (
    ToolSchemaList,
    EntitySchemaList,
    EnrichedToolSchemaList,
    EnrichedEntitySchemaList,
    SystemPromptExtraction,
    StructuredSystemPromptExtraction,
    ToolCodeRuleList,
)


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
        tools_schema: dict,
        entity_schema: dict,
        system_prompt: str,
        agent_dir: Path | str,
    ) -> dict:
        tools = self.step1_parse_tools(tools_schema)
        entities = self.step2_parse_entities(entity_schema)
        tools, code_rules, entities = self.step3_enrich_tools_and_entities(
            tools, entities, system_prompt, Path(agent_dir) / "tools.py"
        )
        prompt_extraction = self.step4_parse_system_prompt(
            tools, code_rules, system_prompt
        )
        structured_prompt_extraction = self.step5_structure_rules(
            tools, entities, prompt_extraction
        )
        validation_result = self.step6_validate(
            tools, entities, structured_prompt_extraction
        )

        return (
            tools,
            code_rules,
            entities,
            structured_prompt_extraction,
            validation_result,
        )

    def step1_parse_tools(self, tools_schema: dict) -> ToolSchemaList:
        return parse_tools(tools_schema)

    def step2_parse_entities(self, entity_schema: dict) -> EntitySchemaList:
        return parse_entity_schema(entity_schema)

    def step3_enrich_tools_and_entities(
        self,
        tools: ToolSchemaList,
        entities: EntitySchemaList,
        system_prompt: str,
        tools_py_path: Path,
    ) -> tuple[EnrichedToolSchemaList, ToolCodeRuleList, EnrichedEntitySchemaList]:
        return self.enricher.enrich_all(tools, entities, system_prompt, tools_py_path)

    def step4_parse_system_prompt(
        self,
        tools: EnrichedToolSchemaList,
        code_rules: ToolCodeRuleList,
        system_prompt: str,
    ) -> SystemPromptExtraction:
        return self.prompt_parser.parse_system_prompt(tools, code_rules, system_prompt)

    def step5_structure_rules(
        self,
        tools: EnrichedToolSchemaList,
        entities: EnrichedEntitySchemaList,
        prompt_extraction: SystemPromptExtraction,
    ) -> StructuredSystemPromptExtraction:
        """Convert natural language rules to structured rules with explicit conditions."""
        structured_intents = []
        for intent in prompt_extraction.intents:
            structured_intent = self.rule_enricher.enrich_intent_rules(
                tools, entities, intent
            )
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
    ) -> ValidationResult:
        return self.validator.validate_parsed_output(tools, entities, prompt_extraction)
