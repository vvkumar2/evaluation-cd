"""Shared formatting utilities for LLM prompts."""

from .context_extractor.schemas.entity_schema import (
    EntitySchemaList,
    EnrichedEntitySchemaList,
)
from .context_extractor.schemas.tool_schema import (
    EnrichedToolSchemaList,
    ToolSchemaList,
)


def format_entities_brief(entities: EntitySchemaList | EnrichedEntitySchemaList) -> str:
    """Format entities as name + description only."""
    return "\n".join(f"- {e.name}: {e.description}" for e in entities.entities)


def format_entities_detailed(
    entities: EntitySchemaList | EnrichedEntitySchemaList,
) -> str:
    """Format entities with fields, enums, and thresholds."""
    lines = []
    for entity in entities.entities:
        lines.append(f"\n{entity.name}:")
        lines.append(f"Description: {entity.description}")
        if entity.fields:
            lines.append("  Fields:")
            for field in entity.fields:
                enum_str = f", Enum: {field.enum}" if field.enum else ""
                lines.append(
                    f"  - {field.name} ({field.type}): {field.description}{enum_str}"
                )
        if getattr(entity, "thresholds", None):
            lines.append("  Thresholds:")
            for t in entity.thresholds:
                unit_str = t.unit or ""
                lines.append(f"  - {t.name}: {t.value}{unit_str}")
    return "\n".join(lines)


def format_tool(tool) -> str:
    """Format a single tool with its parameters."""
    parts = [f"- {tool.name}: {tool.description}"]
    if tool.parameters:
        for p in tool.parameters:
            parts.append(f"  - {p.name} ({p.type}): {p.description}")
    return "\n".join(parts)


def format_tools(tools: ToolSchemaList | EnrichedToolSchemaList) -> str:
    """Format a list of tools with descriptions and parameters."""
    return "\n\n".join(format_tool(tool) for tool in tools.tools)


def format_tools_with_returns(tools: EnrichedToolSchemaList) -> str:
    """Format tools with return type info."""
    lines = []
    for tool in tools.tools:
        line = f"- {tool.name}: {tool.description}"
        if tool.returns:
            line += f" -> {tool.returns.type}"
        lines.append(line)
    return "\n".join(lines)
