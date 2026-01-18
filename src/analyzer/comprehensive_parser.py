"""
Comprehensive parser for understanding agent capabilities from a codebase and business logic.
""" 
import ast
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from .path_tracer import extract_all_paths

@dataclass
class ExecutionPath:
    """A single execution path."""
    path_id: str
    conditions: List[str]
    return_value: Optional[str] = None
    raises_exception: Optional[str] = None
    is_error_path: bool = False


@dataclass
class CapabilityWorkflow:
    """All execution paths for a specific capability."""
    capability_name: str
    domain: str
    entry_function: str
    description: str
    paths: List[ExecutionPath] = field(default_factory=list)


@dataclass
class AgentCapabilities:
    """All capabilities of the agent."""
    description: str
    workflows: List[CapabilityWorkflow]
    constants: Dict[str, Any]


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
            agent_description, capabilities_list = self._parse_business_logic_yaml(business_logic_path)

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

        # Build workflows for each capability
        workflows = []
        for cap_data in capabilities_list:
            execution_paths = self._trace_execution_paths(cap_data, all_functions)

            workflow = CapabilityWorkflow(
                capability_name=cap_data['name'],
                domain=cap_data['domain'],
                entry_function=cap_data['entry_function'],
                description=cap_data['description'],
                paths=execution_paths
            )
            workflows.append(workflow)

        self.capabilities = AgentCapabilities(
            description=agent_description,
            workflows=workflows,
            constants=constants
        )

        return self.capabilities

    def _parse_business_logic_yaml(
        self,
        file_path: Path
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Parse business_logic.yaml to extract agent description and capabilities.

        Returns:
            (description, list of capability dicts)
        """
        import yaml

        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        agent_data = data.get('agent', {})
        description = agent_data.get('description', '')

        capabilities = []
        for cap_data in agent_data.get('capabilities', []):
            capabilities.append({
                'name': cap_data['name'],
                'domain': cap_data['domain'],
                'entry_function': cap_data['entry_function'],
                'description': cap_data['description']
            })

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

                                # Filter out enum-like constants where value is just lowercase of key
                                if isinstance(value, str):
                                    # Skip if value is just the key in lowercase or with underscores replaced
                                    if value == target.id.lower() or value == target.id.lower().replace('_', ''):
                                        continue
                                    # Skip if key is just uppercase of value
                                    if target.id == value.upper() or target.id == value.upper().replace(' ', '_'):
                                        continue

                                constants[target.id] = value
                            except (ValueError, TypeError):
                                pass

        # Extract functions and methods
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions[node.name] = node

        return functions, constants

    def _trace_execution_paths(
        self,
        capability_data: Dict[str, str],
        all_functions: Dict[str, ast.FunctionDef]
    ) -> List[ExecutionPath]:
        """
        Trace all execution paths for a capability starting from its entry function.

        Args:
            capability_data: Dict with capability info (name, domain, entry_function, description)
            all_functions: Dict of function_name -> AST node

        Returns:
            List of execution paths
        """
        entry_func_name = capability_data['entry_function']
        domain = capability_data['domain']
        capability_name = capability_data['name']
        capability_description = capability_data['description']

        if entry_func_name not in all_functions:
            return []

        entry_func_node = all_functions[entry_func_name]

        # Extract all code paths through the entry function
        exec_paths = extract_all_paths(entry_func_node)

        execution_paths = []
        for i, exec_path in enumerate(exec_paths):
            # Combine conditions
            all_conditions = []
            for cond in exec_path.conditions:
                all_conditions.append(f"WHEN: {cond}")
            for cond in exec_path.negated_conditions:
                all_conditions.append(f"NOT: {cond}")

            execution_paths.append(ExecutionPath(
                path_id=f"{domain}_{entry_func_name}_path_{i+1}",
                conditions=all_conditions,
                return_value=exec_path.return_value,
                raises_exception=exec_path.raises_exception,
                is_error_path=exec_path.is_error_path
            ))

        return execution_paths

    def export_to_dict(self) -> Dict[str, Any]:
        """Export capabilities to dictionary format."""
        if not self.capabilities:
            return {}

        return {
            'description': self.capabilities.description,
            'workflows': [
                {
                    'capability_name': workflow.capability_name,
                    'domain': workflow.domain,
                    'entry_function': workflow.entry_function,
                    'description': workflow.description,
                    'paths': [
                        {
                            'path_id': path.path_id,
                            'conditions': path.conditions,
                            'return_value': path.return_value,
                            'raises': path.raises_exception,
                            'is_error_path': path.is_error_path
                        }
                        for path in workflow.paths
                    ]
                }
                for workflow in self.capabilities.workflows
            ],
            'constants': self.capabilities.constants
        }
