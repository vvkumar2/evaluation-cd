"""Agent Test Input Space Extractor.

This module extracts all possible test input variations for an AI agent by analyzing:
1. Tool schemas (what the agent can do)
2. Entity schemas (what data the agent works with)
3. System prompt (how the agent makes decisions)

The extraction process is 4 steps:
1. Parse tool schemas programmatically
2a. Parse entity schemas programmatically
2b. Enrich entities with business logic (LLM-based)
3. Parse system prompt (LLM-based)
4. Validate outputs (programmatic)
"""

from .main import AgentTestSpaceExtractor
from .parsers import (
    parse_tools,
    parse_entity_schema,
    EntityEnricher,
    SystemPromptParser,
)
from .validation import AgentTestValidator, ValidationResult, ValidationError
from .schemas import (
    ToolSchema,
    ToolSchemaOutput,
    EntitySchema,
    EntitySchemaOutput,
    SystemPromptExtraction,
)

__all__ = [
    "AgentTestSpaceExtractor",
    "parse_tools",
    "parse_entity_schema",
    "EntityEnricher",
    "SystemPromptParser",
    "AgentTestValidator",
    "ValidationResult",
    "ValidationError",
    "ToolSchema",
    "ToolSchemaOutput",
    "EntitySchema",
    "EntitySchemaOutput",
    "SystemPromptExtraction",
]
