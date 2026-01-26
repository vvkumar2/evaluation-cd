"""Pydantic models for tool schema extraction."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ParameterConstraint(BaseModel):
    """Constraint on a tool parameter."""

    operator: str = Field(
        ..., description="Comparison operator: eq, neq, gt, lt, gte, lte, in, not_in"
    )
    value: Any = Field(..., description="The constraint value")


class ToolParameter(BaseModel):
    """Schema for a tool parameter."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, integer, boolean, array, object)")
    description: str = Field(..., description="Human-readable parameter description")
    required: bool = Field(default=False, description="Whether parameter is required")
    enum: Optional[list[str]] = Field(default=None, description="Allowed values if enum type")
    constraints: list[ParameterConstraint] = Field(
        default_factory=list,
        description="Constraints extracted from tool implementation",
    )
    additionalProperties: bool = False


class ToolReturn(BaseModel):
    """Schema for tool return value."""

    type: str = Field(..., description="Return type")
    description: str = Field(..., description="What the return value represents")
    additionalProperties: bool = False


class ToolError(BaseModel):
    """Schema for tool error scenarios."""

    error_type: str = Field(..., description="Type of error (e.g., 'not_found', 'invalid_input')")
    description: str = Field(..., description="When this error occurs")
    additionalProperties: bool = False


class ToolSchema(BaseModel):
    """Complete schema for a tool."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: list[ToolParameter] = Field(
        default_factory=list, description="List of tool parameters"
    )
    returns: ToolReturn = Field(..., description="Return value schema")
    errors: list[ToolError] = Field(
        default_factory=list, description="Possible error scenarios"
    )
    additionalProperties: bool = False


class ToolSchemaOutput(BaseModel):
    """Output of tool schema parsing - list of all tools."""

    tools: list[ToolSchema] = Field(..., description="List of extracted tool schemas")
    additionalProperties: bool = False
