import json
import ast
import re
from pathlib import Path
from typing import Optional
from ..schemas.tool_schema import (
    ToolSchemaList,
    EnrichedToolSchema,
    EnrichedToolSchemaList,
    ToolReturn,
    ToolCodeRule,
    ToolCodeRuleList,
    ToolSchema,
)
from ..schemas.entity_schema import (
    EntitySchemaList,
    EnrichedEntitySchema,
    EnrichedEntitySchemaList,
    EntityThreshold,
    EnrichedEntityThresholdList,
)
from ..schemas.prompt_schema import SystemPromptExtraction
from ..templates import (
    TOOL_RETURN_SCHEMA_PROMPT,
    CODE_RULES_EXTRACTION_PROMPT,
    ENTITY_THRESHOLDS_EXTRACTION_PROMPT,
)


class AgentEnricher:
    """Enriches tools and entities using LLM with full agent context from tools, entities, and system prompt."""

    def __init__(self, llm_client=None):
        self.client = llm_client

    def enrich_all(
        self,
        tools: ToolSchemaList,
        entities: EntitySchemaList,
        system_prompt: str,
        tools_py_path: Path | str,
    ) -> tuple[EnrichedToolSchemaList, ToolCodeRuleList, EnrichedEntitySchemaList]:
        enriched_tools, code_rules = self._enrich_tools(tools, entities, tools_py_path)
        enriched_entities = self._enrich_entities(entities, system_prompt)

        return enriched_tools, code_rules, enriched_entities

    def _enrich_tools(
        self,
        tools: ToolSchemaList,
        entities: EntitySchemaList,
        tools_py_path: Path | str,
    ) -> tuple[EnrichedToolSchemaList, ToolCodeRuleList]:
        """Enrich tools with return schemas and code rules using LLM, processing one tool at a time."""
        entities_text = self._format_entities(entities)
        enriched_list = []
        code_rules_list = []
        for tool in tools.tools:
            tool_code = self._extract_tool_code(tool.name, tools_py_path)
            enriched_tool = self._enrich_single_tool(tool, tool_code, entities_text)
            enriched_list.append(enriched_tool)
            code_rules = self._extract_tool_code_rules(
                tool, tool_code, entities_text, tools_py_path
            )
            code_rules_list.extend(code_rules)
        return EnrichedToolSchemaList(tools=enriched_list), ToolCodeRuleList(
            rules=code_rules_list
        )

    def _enrich_single_tool(
        self,
        tool: ToolSchema,
        tool_code: str,
        entities_text: str,
    ) -> EnrichedToolSchema:
        tool_text = self._format_tool(tool)
        code_section = (
            ""
            if not tool_code
            else f"\n\nTool Implementation Code:\n```python\n{tool_code}\n```"
        )
        llm_return_prompt = TOOL_RETURN_SCHEMA_PROMPT.format(
            tool_text=tool_text,
            code_section=code_section,
            entities_text=entities_text,
            tool_name=tool.name,
        )

        return_response = self._call_llm(llm_return_prompt)
        enriched_tool = self._parse_single_tool_response(return_response, tool)
        return enriched_tool

    def _extract_tool_code_rules(
        self,
        tool: ToolSchema,
        tool_code: str,
        entities_text: str,
        tools_py_path: Path | str,
    ) -> list[ToolCodeRule]:
        """Extract business rules and conditions from tool code and imported business logic modules."""
        if not tool_code:
            return []
        # Extract business logic code from imported modules
        business_logic_code = self._extract_business_logic_code(
            tool_code, tools_py_path
        )
        tool_text = self._format_tool(tool)
        all_code = (
            tool_code
            if not business_logic_code
            else f"{tool_code}\n\n{business_logic_code}"
        )
        llm_code_rules_prompt = CODE_RULES_EXTRACTION_PROMPT.format(
            tool_text=tool_text,
            all_code=all_code,
            entities_text=entities_text,
        )

        response = self._call_llm(llm_code_rules_prompt)
        return self._parse_code_rules_response(response)

    def _extract_business_logic_code(
        self,
        tool_code: str,
        tools_py_path: Path | str,
    ) -> Optional[str]:
        """Extract code from business logic modules that the tool imports and uses."""
        tools_py_path = Path(tools_py_path)
        agent_dir = tools_py_path.parent

        try:
            # Read the full tools.py file to find imports
            full_tools_code = tools_py_path.read_text()
            tools_tree = ast.parse(full_tools_code)

            # Find business logic module imports and their instance names
            business_logic_info = {}  # {module_name: instance_name}
            for node in ast.walk(tools_tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module
                        # Find the instance assignment (e.g., order_manager = OrderManager())
                        module_class = None
                        for alias in node.names:
                            module_class = alias.name
                            break

                        if module_class:
                            # Find where this class is instantiated
                            for assign_node in ast.walk(tools_tree):
                                if isinstance(assign_node, ast.Assign):
                                    for target in assign_node.targets:
                                        if isinstance(target, ast.Name):
                                            if isinstance(assign_node.value, ast.Call):
                                                if isinstance(
                                                    assign_node.value.func, ast.Name
                                                ):
                                                    if (
                                                        assign_node.value.func.id
                                                        == module_class
                                                    ):
                                                        instance_name = target.id
                                                        business_logic_info[
                                                            module_name
                                                        ] = instance_name
                                                        break

            # Parse tool code to find called methods
            tool_tree = ast.parse(tool_code)
            called_methods_by_module = {}  # {instance_name: [method_names]}

            for node in ast.walk(tool_tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            instance_name = node.func.value.id
                            method_name = node.func.attr
                            if instance_name in business_logic_info.values():
                                if instance_name not in called_methods_by_module:
                                    called_methods_by_module[instance_name] = []
                                called_methods_by_module[instance_name].append(
                                    method_name
                                )

            if not called_methods_by_module:
                return None

            # Extract code from business logic files
            business_logic_code_parts = []
            for module_name, instance_name in business_logic_info.items():
                if instance_name in called_methods_by_module:
                    # Convert module path to file path
                    module_path = module_name.replace(".", "/") + ".py"
                    business_logic_file = agent_dir / module_path

                    if business_logic_file.exists():
                        called_methods = called_methods_by_module[instance_name]
                        # Extract constants and methods
                        constants_code = self._extract_constants_from_file(
                            business_logic_file
                        )
                        methods_code = self._extract_methods_from_file(
                            business_logic_file, called_methods
                        )
                        # Combine constants and methods
                        module_code_parts = []
                        if constants_code:
                            module_code_parts.append(f"# Constants:\n{constants_code}")
                        if methods_code:
                            module_code_parts.append(f"# Methods:\n{methods_code}")
                        if module_code_parts:
                            business_logic_code_parts.append(
                                f"# From {module_name}:\n\n"
                                + "\n\n".join(module_code_parts)
                            )

            return (
                "\n\n".join(business_logic_code_parts)
                if business_logic_code_parts
                else None
            )

        except Exception:
            return None

    def _extract_constants_from_file(self, file_path: Path) -> Optional[str]:
        """Extract module-level constants (uppercase variable assignments) from a Python file."""
        try:
            source_code = file_path.read_text()
            tree = ast.parse(source_code)
            lines = source_code.split("\n")

            # Build a map of line numbers to their containing scopes (class/function)
            scope_map = {}  # {line_number: scope_type}

            def visit_node(node, parent_scope=None):
                """Recursively visit nodes to build scope map."""
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    scope_type = (
                        "class" if isinstance(node, ast.ClassDef) else "function"
                    )
                    start = node.lineno
                    end = (
                        node.end_lineno
                        if hasattr(node, "end_lineno") and node.end_lineno
                        else start
                    )
                    for line_num in range(start, end + 1):
                        scope_map[line_num] = scope_type
                    # Visit children with this scope as parent
                    for child in ast.iter_child_nodes(node):
                        visit_node(child, scope_type)
                else:
                    for child in ast.iter_child_nodes(node):
                        visit_node(child, parent_scope)

            visit_node(tree)

            extracted_constants = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    # Check if this assignment is at module level (not in a class or function)
                    node_line = node.lineno
                    if node_line not in scope_map:
                        # This is at module level
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                # Check if variable name is uppercase (convention for constants)
                                var_name = target.id
                                if var_name.isupper() or (
                                    var_name.startswith("_")
                                    and len(var_name) > 1
                                    and var_name[1:].isupper()
                                ):
                                    start_line = node.lineno - 1
                                    # Find the end of the assignment
                                    end_line = (
                                        node.end_lineno
                                        if hasattr(node, "end_lineno")
                                        and node.end_lineno
                                        else node.lineno
                                    )

                                    # Include comments before the constant if they're on adjacent lines
                                    comment_start = start_line
                                    for i in range(
                                        start_line - 1, max(0, start_line - 3), -1
                                    ):
                                        line = lines[i].strip()
                                        if line.startswith("#"):
                                            comment_start = i
                                        elif line == "":
                                            continue
                                        else:
                                            break

                                    constant_code = "\n".join(
                                        lines[comment_start:end_line]
                                    )
                                    extracted_constants.append(constant_code)
                                    break

            return "\n".join(extracted_constants) if extracted_constants else None
        except Exception:
            return None

    def _extract_methods_from_file(
        self, file_path: Path, method_names: list[str]
    ) -> Optional[str]:
        """Extract specific method definitions from a Python file."""
        try:
            source_code = file_path.read_text()
            tree = ast.parse(source_code)
            lines = source_code.split("\n")

            extracted_methods = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in method_names:
                    start_line = node.lineno - 1
                    end_line = (
                        node.end_lineno
                        if hasattr(node, "end_lineno") and node.end_lineno
                        else None
                    )

                    if end_line is None:
                        # Find next function or class
                        for i in range(start_line + 1, len(lines)):
                            line = lines[i]
                            if line.strip() and not line[0].isspace():
                                stripped = line.strip()
                                if (
                                    stripped.startswith("def ")
                                    or stripped.startswith("class ")
                                    or stripped.startswith("@")
                                ):
                                    end_line = i
                                    break
                        if end_line is None:
                            end_line = len(lines)

                    method_code = "\n".join(lines[start_line:end_line])
                    extracted_methods.append(method_code)

            return "\n\n".join(extracted_methods) if extracted_methods else None
        except Exception:
            return None

    def _parse_code_rules_response(self, response: str) -> list[ToolCodeRule]:
        """Parse LLM response for code rules."""
        data = json.loads(response)
        rules_data = ToolCodeRuleList(**data)
        return rules_data.rules

    def _enrich_entities(
        self,
        entities: EntitySchemaList,
        system_prompt: str,
    ) -> EnrichedEntitySchemaList:
        """Enrich entities with thresholds using LLM."""
        entities_text = self._format_entities(entities)

        llm_prompt = ENTITY_THRESHOLDS_EXTRACTION_PROMPT.format(
            entities_text=entities_text,
            system_prompt=system_prompt,
        )
        response = self._call_llm(llm_prompt)
        enriched = self._parse_entities_response(response, entities)
        return enriched

    def _format_tool(self, tool: ToolSchema) -> str:
        tool_text = f"- {tool.name}: {tool.description}"
        if tool.parameters:
            params_text = "\n".join(
                f"  - {p.name} ({p.type}): {p.description}" for p in tool.parameters
            )
            tool_text += f"\n  Parameters:\n{params_text}"
        return tool_text

    def _format_entities(self, entities: EntitySchemaList) -> str:
        """Format entities for LLM input."""
        return "\n".join(
            f"- {entity.name}: {entity.description}" for entity in entities.entities
        )

    def _format_intents(self, prompt: SystemPromptExtraction) -> str:
        """Format intents for LLM input."""
        return "\n".join(
            f"- {intent.name}: {intent.description}, workflow: {' -> '.join(intent.workflow)}"
            for intent in prompt.intents
        )

    def _call_llm(self, prompt: str) -> str:
        """Call LLM and extract JSON from response."""
        if not self.client:
            raise RuntimeError("LLM client not initialized")

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content

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

    def _parse_single_tool_response(
        self, response: str, original_tool
    ) -> EnrichedToolSchema:
        """Parse LLM response for a single tool and convert to EnrichedToolSchema."""
        data = json.loads(response)

        returns_data = data["returns"]
        returns = ToolReturn(**returns_data)
        updated = {
            **original_tool.model_dump(),
            "returns": returns.model_dump(),
        }

        return EnrichedToolSchema(**updated)

    def _extract_tool_code(
        self, tool_name: str, tools_py_path: Path | str
    ) -> Optional[str]:
        """Extract the code for a specific tool function from tools.py file, including decorators."""
        tools_py_path = Path(tools_py_path)
        if not tools_py_path.exists():
            return None
        try:
            source_code = tools_py_path.read_text()
            lines = source_code.split("\n")
            tree = ast.parse(source_code)
            # Find the function definition for this tool
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == tool_name:
                    # Get the line numbers for this function
                    start_line = node.lineno - 1  # 0-indexed (convert to 0-based)
                    end_line = (
                        node.end_lineno
                        if hasattr(node, "end_lineno") and node.end_lineno
                        else None
                    )
                    # Find the end of the function
                    if end_line is None:
                        for i in range(start_line + 1, len(lines)):
                            line = lines[i]
                            if line.strip() and not line[0].isspace():
                                stripped = line.strip()
                                if (
                                    stripped.startswith("@")
                                    or stripped.startswith("def ")
                                    or stripped.startswith("class ")
                                ):
                                    end_line = i
                                    break
                        if end_line is None:
                            end_line = len(lines)
                    # Extract the function code
                    function_lines = lines[start_line:end_line]
                    return "\n".join(function_lines)
            return None
        except Exception:
            return self._extract_tool_code_regex(tool_name, tools_py_path)

    def _extract_tool_code_regex(
        self, tool_name: str, tools_py_path: Path
    ) -> Optional[str]:
        source_code = tools_py_path.read_text()
        # Pattern to match function definition with decorators
        pattern = rf"(@\w+.*?\n)*def\s+{re.escape(tool_name)}\s*\([^)]*\)\s*->[^:]*:.*?(?=\n(?:@\w+|def\s+\w+|class\s+\w+|\Z))"
        match = re.search(pattern, source_code, re.DOTALL)
        if match:
            return match.group(0).strip()
        return None

    def _parse_entities_response(
        self, response: str, original_entities: EntitySchemaList
    ) -> EnrichedEntitySchemaList:
        """Parse LLM response and convert to EnrichedEntitySchemaList."""
        try:
            data = json.loads(response)
            enriched_data = EnrichedEntityThresholdList(**data)
            entities_dict = {e.name: e for e in original_entities.entities}
            enriched_list = []
            for enriched_entity in enriched_data.entities:
                original = entities_dict.get(enriched_entity.name)
                if original:
                    thresholds = [
                        EntityThreshold(
                            name=t.name,
                            value=t.value,
                            description=t.description,
                            unit=t.unit,
                        )
                        for t in enriched_entity.thresholds
                    ]

                    updated = {
                        **original.model_dump(),
                        "thresholds": [t.model_dump() for t in thresholds],
                    }
                    enriched_list.append(EnrichedEntitySchema(**updated))

            return EnrichedEntitySchemaList(entities=enriched_list)
        except Exception as e:
            raise e
