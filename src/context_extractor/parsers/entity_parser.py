"""Step 2a: Parse entity schemas from YAML/JSON format."""

import json
from typing import Any, Optional
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from ..schemas.entity_schema import (
    EntitySchema,
    EntitySchemaOutput,
    EntityField,
    EntityFieldConstraint,
    EntityThreshold,
    EntityAlias,
    ComputedField,
    EntityRelationship,
    EntityConstraint,
)
from ..schemas.tool_schema import ToolSchemaOutput


def parse_entity_schema(entity_yaml: str | dict | Path) -> EntitySchemaOutput:
    """
    Parse entity schema definitions from YAML/JSON format.

    Args:
        entity_yaml: Entity definitions as YAML/JSON string, dict, or file path

    Returns:
        EntitySchemaOutput with extracted entity schemas
    """
    # Load the input
    if isinstance(entity_yaml, Path):
        if entity_yaml.suffix in (".yaml", ".yml"):
            content = entity_yaml.read_text()
            entity_data = yaml.safe_load(content) if yaml else json.loads(content)
        else:
            entity_data = json.loads(entity_yaml.read_text())
    elif isinstance(entity_yaml, str):
        try:
            # Try JSON first
            entity_data = json.loads(entity_yaml)
        except json.JSONDecodeError:
            # Try YAML
            if yaml:
                entity_data = yaml.safe_load(entity_yaml)
            else:
                try:
                    entity_data = json.loads(Path(entity_yaml).read_text())
                except (FileNotFoundError, json.JSONDecodeError):
                    raise ValueError(f"Could not parse entity data: {entity_yaml}")
    else:
        entity_data = entity_yaml

    # Handle different input formats
    if isinstance(entity_data, dict):
        if "entities" in entity_data:
            entities_list = entity_data["entities"]
        else:
            # Assume it's a single entity
            entities_list = [entity_data]
    elif isinstance(entity_data, list):
        entities_list = entity_data
    else:
        raise ValueError(f"Unexpected entity format: {type(entity_data)}")

    # Parse each entity
    parsed_entities = []
    for entity_def in entities_list:
        parsed_entity = _parse_single_entity(entity_def)
        parsed_entities.append(parsed_entity)

    return EntitySchemaOutput(entities=parsed_entities)


def _parse_single_entity(entity_def: dict) -> EntitySchema:
    """Parse a single entity definition."""
    name = entity_def.get("name", "unknown")
    description = entity_def.get("description", "")

    # Parse fields
    fields = _parse_fields(entity_def.get("fields", []))

    # Parse thresholds
    thresholds = _parse_thresholds(entity_def.get("thresholds", []))

    # Parse aliases
    aliases = _parse_aliases(entity_def.get("aliases", []))

    # Parse computed fields
    computed_fields = _parse_computed_fields(entity_def.get("computed_fields", []))

    # Parse relationships
    relationships = _parse_relationships(entity_def.get("relationships", []))

    # Parse constraints
    constraints = _parse_constraints(entity_def.get("constraints", []))

    return EntitySchema(
        name=name,
        description=description,
        fields=fields,
        thresholds=thresholds,
        aliases=aliases,
        computed_fields=computed_fields,
        relationships=relationships,
        constraints=constraints,
    )


def _parse_fields(fields_data: list | dict) -> list[EntityField]:
    """Parse entity fields."""
    fields = []

    if isinstance(fields_data, dict):
        # Format: {field_name: schema}
        for field_name, field_schema in fields_data.items():
            field = _parse_field(field_name, field_schema)
            fields.append(field)
    elif isinstance(fields_data, list):
        # Format: [{name: ..., type: ..., ...}, ...]
        for field_def in fields_data:
            field = _parse_field(
                field_def.get("name", "unknown"),
                field_def,
            )
            fields.append(field)

    return fields


def _parse_field(name: str, schema: dict | str) -> EntityField:
    """Parse a single field."""
    if isinstance(schema, str):
        # Simple type specification
        field_type = schema
        field_schema = {"type": field_type}
    else:
        field_schema = schema
        field_type = field_schema.get("type", "string")

    description = field_schema.get("description", f"Field: {name}")
    required = field_schema.get("required", False)
    enum = field_schema.get("enum")

    # Extract constraints
    constraints = _extract_field_constraints(field_schema)

    return EntityField(
        name=name,
        type=field_type,
        description=description,
        required=required,
        enum=enum,
        constraints=constraints,
    )


def _extract_field_constraints(schema: dict) -> list[EntityFieldConstraint]:
    """Extract constraints from field schema."""
    constraints = []

    # Handle explicit constraints
    if "constraints" in schema:
        for constraint_def in schema["constraints"]:
            if isinstance(constraint_def, dict):
                constraint = EntityFieldConstraint(
                    operator=constraint_def.get("operator", "eq"),
                    value=constraint_def.get("value"),
                )
                constraints.append(constraint)

    # Handle minimum/maximum for numbers
    if schema.get("type") in ("number", "integer"):
        if "minimum" in schema:
            constraint = EntityFieldConstraint(
                operator="gte",
                value=schema["minimum"],
            )
            constraints.append(constraint)

        if "maximum" in schema:
            constraint = EntityFieldConstraint(
                operator="lte",
                value=schema["maximum"],
            )
            constraints.append(constraint)

    return constraints


def _parse_thresholds(thresholds_data: list) -> list[EntityThreshold]:
    """Parse business logic thresholds."""
    thresholds = []

    for threshold_def in thresholds_data:
        threshold = EntityThreshold(
            name=threshold_def.get("name", "unknown"),
            value=threshold_def.get("value", 0),
            description=threshold_def.get("description", ""),
            unit=threshold_def.get("unit"),
        )
        thresholds.append(threshold)

    return thresholds


def _parse_aliases(aliases_data: list) -> list[EntityAlias]:
    """Parse field aliases."""
    aliases = []

    for alias_def in aliases_data:
        alias = EntityAlias(
            alias_name=alias_def.get("alias_name", "unknown"),
            refers_to=alias_def.get("refers_to", "unknown"),
            description=alias_def.get("description", ""),
        )
        aliases.append(alias)

    return aliases


def _parse_computed_fields(computed_fields_data: list) -> list[ComputedField]:
    """Parse computed fields."""
    computed_fields = []

    for field_def in computed_fields_data:
        field = ComputedField(
            name=field_def.get("name", "unknown"),
            description=field_def.get("description", ""),
            source_fields=field_def.get("source_fields", []),
            computation=field_def.get("computation", ""),
        )
        computed_fields.append(field)

    return computed_fields


def _parse_relationships(relationships_data: list) -> list[EntityRelationship]:
    """Parse entity relationships."""
    relationships = []

    for rel_def in relationships_data:
        rel = EntityRelationship(
            entity_name=rel_def.get("entity_name", "unknown"),
            relationship_type=rel_def.get("relationship_type", "one_to_one"),
            description=rel_def.get("description", ""),
        )
        relationships.append(rel)

    return relationships


def _parse_constraints(constraints_data: list) -> list[EntityConstraint]:
    """Parse cross-field constraints."""
    constraints = []

    for constraint_def in constraints_data:
        constraint = EntityConstraint(
            description=constraint_def.get("description", ""),
            affected_fields=constraint_def.get("affected_fields", []),
        )
        constraints.append(constraint)

    return constraints


def enrich_entities_from_tools(
    entities: EntitySchemaOutput, tools: ToolSchemaOutput
) -> EntitySchemaOutput:
    """
    Enrich entity schema with information extracted from tool schemas.

    Args:
        entities: Extracted entity schemas
        tools: Extracted tool schemas

    Returns:
        Enriched entity schemas
    """
    # Build a map of tool names and their parameters for reference
    tool_param_map = {}
    for tool in tools.tools:
        tool_param_map[tool.name] = {p.name: p for p in tool.parameters}

    # For each entity, look for related tool parameter constraints
    # This is a basic implementation - more sophisticated enrichment
    # could be added based on tool definitions

    return entities
