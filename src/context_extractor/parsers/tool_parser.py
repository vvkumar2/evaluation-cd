"""Step 1: Parse tool schemas from JSON/OpenAPI format."""

import json
from typing import Any, Optional
from pathlib import Path

from ..schemas.tool_schema import (
    ToolSchema,
    ToolSchemaOutput,
    ToolParameter,
    ToolReturn,
    ToolError,
    ParameterConstraint,
)


def parse_tools(tools_json: str | dict | Path) -> ToolSchemaOutput:
    """
    Parse tool definitions from JSON/OpenAPI format.

    Args:
        tools_json: Tool definitions as JSON string, dict, or path to JSON file

    Returns:
        ToolSchemaOutput with extracted tool schemas
    """
    # Load the input
    if isinstance(tools_json, Path):
        with open(tools_json) as f:
            tools_data = json.load(f)
    elif isinstance(tools_json, str):
        try:
            tools_data = json.loads(tools_json)
        except json.JSONDecodeError:
            # Try as file path
            tools_data = json.loads(Path(tools_json).read_text())
    else:
        tools_data = tools_json

    # Handle different input formats
    if isinstance(tools_data, dict):
        if "tools" in tools_data:
            tools_list = tools_data["tools"]
        elif "functions" in tools_data:
            tools_list = tools_data["functions"]
        else:
            # Assume it's a single tool
            tools_list = [tools_data]
    elif isinstance(tools_data, list):
        tools_list = tools_data
    else:
        raise ValueError(f"Unexpected tools format: {type(tools_data)}")

    # Parse each tool
    parsed_tools = []
    for tool_def in tools_list:
        parsed_tool = _parse_single_tool(tool_def)
        parsed_tools.append(parsed_tool)

    return ToolSchemaOutput(tools=parsed_tools)


def _parse_single_tool(tool_def: dict) -> ToolSchema:
    """Parse a single tool definition."""
    # Extract basic info
    name = tool_def.get("name") or tool_def.get("function", {}).get("name", "unknown")
    description = (
        tool_def.get("description")
        or tool_def.get("function", {}).get("description", "")
    )

    # Handle function-wrapped format
    if "function" in tool_def and isinstance(tool_def["function"], dict):
        func_def = tool_def["function"]
        name = name or func_def.get("name", "unknown")
        description = description or func_def.get("description", "")
        params_schema = func_def.get("parameters", {})
    else:
        params_schema = tool_def.get("parameters", {})

    # Parse parameters
    parameters = _parse_parameters(params_schema)

    # Parse return value
    returns = _parse_return_value(tool_def.get("returns") or {})

    # Parse error scenarios
    errors = _parse_errors(tool_def.get("errors") or [])

    return ToolSchema(
        name=name,
        description=description,
        parameters=parameters,
        returns=returns,
        errors=errors,
    )


def _parse_parameters(params_schema: dict) -> list[ToolParameter]:
    """Parse parameters from JSON Schema format."""
    parameters = []

    # Handle JSON Schema format
    if "properties" in params_schema:
        properties = params_schema["properties"]
        required_fields = params_schema.get("required", [])

        for prop_name, prop_schema in properties.items():
            param = _parse_parameter(prop_name, prop_schema, prop_name in required_fields)
            parameters.append(param)
    # Handle parameter array format
    elif isinstance(params_schema, list):
        for param_def in params_schema:
            param = _parse_parameter(
                param_def.get("name", "unknown"),
                param_def,
                param_def.get("required", False),
            )
            parameters.append(param)

    return parameters


def _parse_parameter(
    name: str, schema: dict, required: bool = False
) -> ToolParameter:
    """Parse a single parameter."""
    param_type = schema.get("type", "string")
    description = schema.get("description", f"Parameter: {name}")
    enum = schema.get("enum")

    # Extract constraints if present
    constraints = _extract_constraints(schema)

    return ToolParameter(
        name=name,
        type=param_type,
        description=description,
        required=required,
        enum=enum,
        constraints=constraints,
    )


def _parse_return_value(returns_schema: dict) -> ToolReturn:
    """Parse return value schema."""
    return_type = returns_schema.get("type", "object")
    description = returns_schema.get("description", "Tool return value")

    return ToolReturn(type=return_type, description=description)


def _parse_errors(errors_list: list) -> list[ToolError]:
    """Parse error scenarios."""
    errors = []

    for error_def in errors_list:
        if isinstance(error_def, dict):
            error = ToolError(
                error_type=error_def.get("type", "error"),
                description=error_def.get("description", "Error occurred"),
            )
        else:
            error = ToolError(
                error_type=str(error_def),
                description="Error occurred",
            )
        errors.append(error)

    return errors


def _extract_constraints(schema: dict) -> list[ParameterConstraint]:
    """Extract constraints from parameter schema."""
    constraints = []

    # Handle explicit constraints
    if "constraints" in schema:
        for constraint_def in schema["constraints"]:
            if isinstance(constraint_def, dict):
                constraint = ParameterConstraint(
                    operator=constraint_def.get("operator", "eq"),
                    value=constraint_def.get("value"),
                )
                constraints.append(constraint)

    # Handle minimum/maximum for numbers
    if schema.get("type") in ("number", "integer"):
        if "minimum" in schema:
            constraint = ParameterConstraint(
                operator="gte",
                value=schema["minimum"],
            )
            constraints.append(constraint)

        if "maximum" in schema:
            constraint = ParameterConstraint(
                operator="lte",
                value=schema["maximum"],
            )
            constraints.append(constraint)

    # Handle enum as constraint
    if "enum" in schema:
        constraint = ParameterConstraint(
            operator="in",
            value=schema["enum"],
        )
        constraints.append(constraint)

    return constraints
