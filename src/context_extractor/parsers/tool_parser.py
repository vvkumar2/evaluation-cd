from ..schemas.tool_schema import (
    ToolSchema,
    ToolSchemaList,
    ToolParameter,
)


def parse_tools(tools_data: dict) -> ToolSchemaList:
    return ToolSchemaList(tools=[_parse_single_tool(tool_def) for tool_def in tools_data["tools"]])


def _parse_single_tool(tool_def: dict) -> ToolSchema:
    """Parse a single tool definition."""
    name = tool_def.get("name") or tool_def.get("function", {}).get("name", "unknown")
    description = (
        tool_def.get("description")
        or tool_def.get("function", {}).get("description", "")
    )

    if "function" in tool_def and isinstance(tool_def["function"], dict):
        func_def = tool_def["function"]
        name = name or func_def.get("name", "unknown")
        description = description or func_def.get("description", "")
        params_schema = func_def.get("parameters", {})
    else:
        params_schema = tool_def.get("parameters", {})

    parameters = _parse_parameters(params_schema)

    return ToolSchema(
        name=name,
        description=description,
        parameters=parameters,
    )


def _parse_parameters(params_schema: dict) -> list[ToolParameter]:
    """Parse parameters from JSON Schema or array format."""
    parameters = []

    if "properties" in params_schema:
        properties = params_schema["properties"]
        required_fields = params_schema.get("required", [])

        for prop_name, prop_schema in properties.items():
            param = _parse_parameter(prop_name, prop_schema, prop_name in required_fields)
            parameters.append(param)
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
    param_type = schema.get("type", "string")
    description = schema.get("description", f"Parameter: {name}")
    enum = schema.get("enum")

    return ToolParameter(
        name=name,
        type=param_type,
        description=description,
        required=required,
        enum=enum,
    )
