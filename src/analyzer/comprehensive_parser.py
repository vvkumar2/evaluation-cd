"""
Comprehensive parser for understanding agent capabilities.

Combines:
1. Business logic YAML (user-defined capabilities)
2. Codebase analysis (implementation and workflow paths)

Extracts:
- Agent description
- Workflow paths (end-to-end execution flows)
- Constants
"""

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import json

from .path_tracer import extract_all_paths


@dataclass
class WorkflowPath:
    """A complete end-to-end workflow path through a capability."""
    capability_name: str
    path_id: str
    entry_function: str
    conditions: List[str]  # Conditions across entire workflow
    function_calls: List[str]  # Sequence of functions called
    return_value: Optional[str] = None
    raises_exception: Optional[str] = None
    is_error_path: bool = False
    description: str = ""


@dataclass
class Capability:
    """A user-facing capability of the agent."""
    name: str
    domain: str
    entry_function: str
    description: str


@dataclass
class AgentCapabilities:
    """Complete understanding of agent capabilities."""
    description: str
    workflow_paths: List[WorkflowPath]
    constants: Dict[str, Any]
    capabilities: List[Capability] = field(default_factory=list)


class ComprehensiveParser:
    """Parse and combine business logic + codebase for complete understanding."""

    def __init__(self):
        self.capabilities = None

    def parse(
        self,
        codebase_path: Path,
        business_logic_path: Optional[Path] = None
    ) -> AgentCapabilities:
        """
        Parse codebase and business logic to extract complete capabilities.

        Args:
            codebase_path: Path to codebase directory or file
            business_logic_path: Path to business_logic.yaml defining capabilities

        Returns:
            AgentCapabilities with complete understanding
        """
        # Parse business logic YAML to get capabilities
        agent_description = ""
        capabilities = []

        if business_logic_path and business_logic_path.exists():
            agent_description, capabilities = self._parse_business_logic_yaml(business_logic_path)

        # Parse codebase to extract function implementations
        all_functions = {}  # function_name -> AST node
        constants = {}

        if codebase_path.is_file():
            funcs, consts = self._parse_python_file_for_functions(codebase_path)
            all_functions.update(funcs)
            constants.update(consts)
        else:
            # Parse all Python files in directory
            for py_file in codebase_path.rglob("*.py"):
                if "__pycache__" not in str(py_file):
                    funcs, consts = self._parse_python_file_for_functions(py_file)
                    all_functions.update(funcs)
                    constants.update(consts)

        # Trace workflow paths for each capability
        workflow_paths = []
        for capability in capabilities:
            paths = self._trace_workflow_paths(capability, all_functions)
            workflow_paths.extend(paths)

        self.capabilities = AgentCapabilities(
            description=agent_description,
            workflow_paths=workflow_paths,
            constants=constants,
            capabilities=capabilities
        )

        return self.capabilities

    def _parse_business_logic_yaml(
        self,
        file_path: Path
    ) -> Tuple[str, List[Capability]]:
        """
        Parse business_logic.yaml to extract agent description and capabilities.

        Returns:
            (description, capabilities)
        """
        import yaml

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        agent_data = data.get('agent', {})
        description = agent_data.get('description', '')

        capabilities = []
        for cap_data in agent_data.get('capabilities', []):
            capabilities.append(Capability(
                name=cap_data['name'],
                domain=cap_data['domain'],
                entry_function=cap_data['entry_function'],
                description=cap_data['description']
            ))

        return description, capabilities

    def _parse_python_file_for_functions(
        self,
        file_path: Path
    ) -> Tuple[Dict[str, ast.FunctionDef], Dict[str, Any]]:
        """
        Parse Python file to extract function AST nodes and constants.

        Returns:
            (functions_dict, constants)
        """
        with open(file_path, 'r') as f:
            source = f.read()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}, {}

        functions = {}
        constants = {}

        # Extract module-level constants
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id.isupper():  # Constant naming convention
                            try:
                                value = ast.literal_eval(node.value)
                                constants[target.id] = value
                            except (ValueError, TypeError):
                                pass

        # Extract functions and methods
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions[node.name] = node

        return functions, constants

    def _trace_workflow_paths(
        self,
        capability: Capability,
        all_functions: Dict[str, ast.FunctionDef]
    ) -> List[WorkflowPath]:
        """
        Trace all workflow paths for a capability starting from its entry function.

        Args:
            capability: The capability to trace
            all_functions: Dict of function_name -> AST node

        Returns:
            List of workflow paths
        """
        entry_func_name = capability.entry_function

        if entry_func_name not in all_functions:
            return []

        entry_func_node = all_functions[entry_func_name]

        # Extract all code paths through the entry function
        exec_paths = extract_all_paths(entry_func_node)

        workflow_paths = []
        for i, exec_path in enumerate(exec_paths):
            # Combine conditions
            all_conditions = []
            for cond in exec_path.conditions:
                all_conditions.append(f"WHEN: {cond}")
            for cond in exec_path.negated_conditions:
                all_conditions.append(f"NOT: {cond}")

            # Extract function calls made in this path
            function_calls = [entry_func_name]
            function_calls.extend(exec_path.calls_functions)

            workflow_paths.append(WorkflowPath(
                capability_name=capability.name,
                path_id=f"{capability.domain}_{entry_func_name}_path_{i+1}",
                entry_function=entry_func_name,
                conditions=all_conditions,
                function_calls=function_calls,
                return_value=exec_path.return_value,
                raises_exception=exec_path.raises_exception,
                is_error_path=exec_path.is_error_path,
                description=f"{capability.name} - {exec_path.return_value or exec_path.raises_exception or 'execution'}"
            ))

        return workflow_paths

    def export_to_dict(self) -> Dict[str, Any]:
        """Export capabilities to dictionary format."""
        if not self.capabilities:
            return {}

        return {
            'description': self.capabilities.description,
            'capabilities': [
                {
                    'name': cap.name,
                    'domain': cap.domain,
                    'entry_function': cap.entry_function,
                    'description': cap.description
                }
                for cap in self.capabilities.capabilities
            ],
            'workflow_paths': [
                {
                    'capability_name': path.capability_name,
                    'path_id': path.path_id,
                    'entry_function': path.entry_function,
                    'conditions': path.conditions,
                    'function_calls': path.function_calls,
                    'return_value': path.return_value,
                    'raises': path.raises_exception,
                    'is_error_path': path.is_error_path,
                    'description': path.description
                }
                for path in self.capabilities.workflow_paths
            ],
            'constants': self.capabilities.constants
        }


if __name__ == '__main__':
    # Test with sample CS agent
    parser = ComprehensiveParser()

    codebase = Path('example_agents/sample_cs_agent/business_logic')
    business_logic = Path('example_agents/sample_cs_agent/business_logic.yml')

    capabilities = parser.parse(codebase, business_logic)

    print(f"Extracted Capabilities:")
    print(f"  Agent: {capabilities.description}")
    print(f"  Capabilities: {len(capabilities.capabilities)}")
    print(f"  Workflow Paths: {len(capabilities.workflow_paths)}")
    print(f"  Constants: {len(capabilities.constants)}")

    # Export to JSON
    output = parser.export_to_dict()
    print(f"\n{json.dumps(output, indent=2)}")
