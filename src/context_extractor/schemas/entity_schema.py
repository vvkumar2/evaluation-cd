"""Pydantic models for entity schema extraction."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class EntityFieldConstraint(BaseModel):
    """Constraint on an entity field."""

    operator: str = Field(
        ..., description="Comparison operator: eq, neq, gt, lt, gte, lte, in, not_in"
    )
    value: Any = Field(..., description="The constraint value")


class EntityField(BaseModel):
    """Schema for an entity field."""

    name: str = Field(..., description="Field name")
    type: str = Field(..., description="Field type (string, number, integer, boolean, array, object)")
    description: str = Field(..., description="Field description")
    required: bool = Field(default=False, description="Whether field is required")
    enum: Optional[list[str]] = Field(default=None, description="Allowed enum values")
    constraints: list[EntityFieldConstraint] = Field(
        default_factory=list,
        description="Constraints on field values",
    )
    additionalProperties: bool = False


class EntityAlias(BaseModel):
    """Alias information for an entity."""

    alias_name: str = Field(..., description="The alias name")
    refers_to: str = Field(..., description="Field or method this alias refers to")
    description: str = Field(..., description="What the alias represents")
    additionalProperties: bool = False


class EntityThreshold(BaseModel):
    """Threshold for rule application."""

    name: str = Field(..., description="Threshold name (e.g., 'refund_window_days')")
    value: float = Field(..., description="The threshold value")
    description: str = Field(..., description="What this threshold represents")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    additionalProperties: bool = False


class ComputedField(BaseModel):
    """A field computed from other fields."""

    name: str = Field(..., description="Computed field name")
    description: str = Field(..., description="What this field computes")
    source_fields: list[str] = Field(..., description="Fields used to compute this")
    computation: str = Field(..., description="How it's computed (plain language)")
    additionalProperties: bool = False


class EntityRelationship(BaseModel):
    """Relationship to another entity."""

    entity_name: str = Field(..., description="Name of related entity")
    relationship_type: str = Field(..., description="Type: 'one_to_one', 'one_to_many', 'many_to_one'")
    description: str = Field(..., description="Description of the relationship")
    additionalProperties: bool = False


class EntityConstraint(BaseModel):
    """Cross-field constraint on an entity."""

    description: str = Field(..., description="Description of the constraint")
    affected_fields: list[str] = Field(..., description="Fields involved in constraint")
    additionalProperties: bool = False


class EntitySchema(BaseModel):
    """Complete schema for an entity."""

    name: str = Field(..., description="Entity name")
    description: str = Field(..., description="Entity description")
    fields: list[EntityField] = Field(..., description="List of entity fields")
    thresholds: list[EntityThreshold] = Field(
        default_factory=list,
        description="Business logic thresholds",
    )
    aliases: list[EntityAlias] = Field(
        default_factory=list,
        description="Aliases for fields/methods",
    )
    computed_fields: list[ComputedField] = Field(
        default_factory=list,
        description="Fields computed from other fields",
    )
    relationships: list[EntityRelationship] = Field(
        default_factory=list,
        description="Relationships to other entities",
    )
    constraints: list[EntityConstraint] = Field(
        default_factory=list,
        description="Cross-field constraints",
    )
    additionalProperties: bool = False


class EntitySchemaOutput(BaseModel):
    """Output of entity schema extraction."""

    entities: list[EntitySchema] = Field(..., description="List of extracted entity schemas")
    additionalProperties: bool = False
