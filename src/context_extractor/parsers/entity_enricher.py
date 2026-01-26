"""Step 2b: Enrich entity schemas with LLM-extracted business logic."""

import json
from typing import Optional

from ..schemas.entity_schema import (
    EntitySchema,
    EntitySchemaOutput,
    EntityThreshold,
    ComputedField,
)
from ..schemas.tool_schema import ToolSchemaOutput


class EntityEnricher:
    """Enriches entity schemas using LLM to extract business logic."""

    def __init__(self, client=None):
        """
        Initialize enricher.

        Args:
            client: LLM client (e.g., OpenAI client). If None, uses environment variables.
        """
        self.client = client

    def enrich_entities_with_business_logic(
        self,
        entities: EntitySchemaOutput,
        tools: ToolSchemaOutput,
        system_prompt: Optional[str] = None,
    ) -> EntitySchemaOutput:
        """
        Enrich entities with business logic extracted from tools and system prompt.

        Uses LLM to extract:
        - Thresholds (decision boundaries)
        - Computed fields (derived values)
        - Relationships between entities

        Args:
            entities: Initial entity schemas
            tools: Tool schemas that implement business logic
            system_prompt: System prompt containing business rules

        Returns:
            Enriched entity schemas
        """
        if not self.client:
            # Without client, return entities as-is
            return entities

        enriched_entities = []
        for entity in entities.entities:
            enriched_entity = self._enrich_single_entity(
                entity, tools, system_prompt
            )
            enriched_entities.append(enriched_entity)

        return EntitySchemaOutput(entities=enriched_entities)

    def _enrich_single_entity(
        self,
        entity: EntitySchema,
        tools: ToolSchemaOutput,
        system_prompt: Optional[str],
    ) -> EntitySchema:
        """Enrich a single entity."""
        # Extract thresholds from tool descriptions
        thresholds = self._extract_thresholds(entity, tools, system_prompt)

        # Extract computed fields
        computed_fields = self._extract_computed_fields(entity, tools, system_prompt)

        # Merge with existing data
        all_thresholds = list(entity.thresholds) + thresholds
        all_computed_fields = list(entity.computed_fields) + computed_fields

        return EntitySchema(
            name=entity.name,
            description=entity.description,
            fields=entity.fields,
            thresholds=all_thresholds,
            aliases=entity.aliases,
            computed_fields=all_computed_fields,
            relationships=entity.relationships,
            constraints=entity.constraints,
        )

    def _extract_thresholds(
        self,
        entity: EntitySchema,
        tools: ToolSchemaOutput,
        system_prompt: Optional[str],
    ) -> list[EntityThreshold]:
        """Extract business logic thresholds using LLM."""
        # Build prompt for LLM
        tools_description = self._format_tools_description(tools)
        entity_description = self._format_entity_description(entity)

        prompt = f"""Analyze the business logic and extract all thresholds/decision boundaries for the {entity.name} entity.

Entity Schema:
{entity_description}

Available Tools and Their Descriptions:
{tools_description}

{f"System Prompt: {system_prompt}" if system_prompt else ""}

Extract all numeric thresholds, decision boundaries, and limits that affect {entity.name}.
For each threshold, provide:
- name: The threshold name (e.g., 'refund_window_days')
- value: The numeric threshold value
- description: What this threshold represents
- unit: Unit of measurement (if applicable)

Respond with a JSON array of threshold objects."""

        # Call LLM
        response = self._call_llm(prompt)

        # Parse response
        thresholds = self._parse_threshold_response(response)
        return thresholds

    def _extract_computed_fields(
        self,
        entity: EntitySchema,
        tools: ToolSchemaOutput,
        system_prompt: Optional[str],
    ) -> list[ComputedField]:
        """Extract computed fields using LLM."""
        # Build prompt for LLM
        tools_description = self._format_tools_description(tools)
        entity_description = self._format_entity_description(entity)

        prompt = f"""Analyze the business logic and identify computed fields for the {entity.name} entity.

Entity Schema:
{entity_description}

Available Tools and Their Descriptions:
{tools_description}

{f"System Prompt: {system_prompt}" if system_prompt else ""}

Identify fields that are computed or derived from other fields.
For each computed field, provide:
- name: The computed field name
- description: What this field represents
- source_fields: List of fields used to compute this
- computation: Plain language description of how it's computed

Respond with a JSON array of computed field objects."""

        # Call LLM
        response = self._call_llm(prompt)

        # Parse response
        computed_fields = self._parse_computed_field_response(response)
        return computed_fields

    def _format_tools_description(self, tools: ToolSchemaOutput) -> str:
        """Format tools as readable description."""
        lines = []
        for tool in tools.tools:
            lines.append(f"Tool: {tool.name}")
            lines.append(f"  Description: {tool.description}")
            if tool.parameters:
                lines.append(f"  Parameters:")
                for param in tool.parameters:
                    lines.append(f"    - {param.name} ({param.type}): {param.description}")
        return "\n".join(lines)

    def _format_entity_description(self, entity: EntitySchema) -> str:
        """Format entity as readable description."""
        lines = [f"Entity: {entity.name}", f"Description: {entity.description}"]

        if entity.fields:
            lines.append("Fields:")
            for field in entity.fields:
                lines.append(
                    f"  - {field.name} ({field.type}): {field.description}"
                )

        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt."""
        if not self.client:
            return "[]"

        try:
            # Try to use OpenAI client format
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
        except Exception:
            # Fallback
            return "[]"

    def _parse_threshold_response(self, response: str) -> list[EntityThreshold]:
        """Parse LLM response for thresholds."""
        thresholds = []

        try:
            # Extract JSON from response
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    threshold = EntityThreshold(
                        name=item.get("name", "unknown"),
                        value=float(item.get("value", 0)),
                        description=item.get("description", ""),
                        unit=item.get("unit"),
                    )
                    thresholds.append(threshold)
        except (json.JSONDecodeError, ValueError):
            pass

        return thresholds

    def _parse_computed_field_response(self, response: str) -> list[ComputedField]:
        """Parse LLM response for computed fields."""
        computed_fields = []

        try:
            # Extract JSON from response
            data = json.loads(response)
            if not isinstance(data, list):
                data = [data]

            for item in data:
                if isinstance(item, dict):
                    field = ComputedField(
                        name=item.get("name", "unknown"),
                        description=item.get("description", ""),
                        source_fields=item.get("source_fields", []),
                        computation=item.get("computation", ""),
                    )
                    computed_fields.append(field)
        except (json.JSONDecodeError, ValueError):
            pass

        return computed_fields
