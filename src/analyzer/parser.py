"""
AST-based code parser for extracting structural information from Python code.

This module parses Python source files to extract:
- Function and method signatures
- Class definitions
- Docstrings and comments
- Exception handling patterns
- Validation logic
- Type hints
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any


@dataclass
class FunctionInfo:
    """Information about a function or method."""
    name: str
    params: List[str]
    return_type: Optional[str]
    docstring: Optional[str]
    decorators: List[str]
    line_number: int
    is_async: bool = False
    raises: List[str] = field(default_factory=list)  # Exceptions it can raise
    has_validation: bool = False  # Contains input validation
    has_error_handling: bool = False  # Contains try/except


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    methods: List[FunctionInfo]
    docstring: Optional[str]
    base_classes: List[str]
    line_number: int


@dataclass
class CodeAnalysis:
    """Complete analysis of a Python file."""
    file_path: str
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    imports: List[str]
    constants: Dict[str, Any]  # Module-level constants
    comments: List[str]  # Standalone comments


class CodeParser:
    """Parse Python source code to extract structural information."""

    def parse_file(self, file_path: Path) -> CodeAnalysis:
        """
        Parse a Python file and extract all structural information.

        Args:
            file_path: Path to Python source file

        Returns:
            CodeAnalysis object containing extracted information
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()

        tree = ast.parse(source)

        functions = []
        classes = []
        imports = []
        constants = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Only top-level functions (not methods)
                if self._is_top_level(node, tree):
                    functions.append(self._extract_function_info(node, source))

            elif isinstance(node, ast.ClassDef):
                classes.append(self._extract_class_info(node, source))

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.extend(self._extract_imports(node))

            elif isinstance(node, ast.Assign) and self._is_top_level(node, tree):
                # Module-level constants (UPPER_CASE names)
                constants.update(self._extract_constants(node))

        return CodeAnalysis(
            file_path=str(file_path),
            functions=functions,
            classes=classes,
            imports=imports,
            constants=constants,
            comments=self._extract_comments(source)
        )

    def parse_directory(self, dir_path: Path) -> List[CodeAnalysis]:
        """
        Parse all Python files in a directory recursively.

        Args:
            dir_path: Path to directory

        Returns:
            List of CodeAnalysis objects, one per file
        """
        analyses = []

        for py_file in dir_path.rglob('*.py'):
            # Skip test files and __pycache__
            if 'test' in py_file.name or '__pycache__' in str(py_file):
                continue

            try:
                analysis = self.parse_file(py_file)
                analyses.append(analysis)
            except Exception as e:
                print(f"Warning: Failed to parse {py_file}: {e}")

        return analyses

    def _extract_function_info(self, node: ast.FunctionDef, source: str) -> FunctionInfo:
        """Extract detailed information about a function."""
        params = [arg.arg for arg in node.args.args]

        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        docstring = ast.get_docstring(node)

        decorators = [ast.unparse(d) for d in node.decorator_list]

        # Check for exception handling
        has_error_handling = any(
            isinstance(n, ast.Try) for n in ast.walk(node)
        )

        # Check for validation (if statements checking parameters)
        has_validation = self._has_validation_logic(node)

        # Extract raised exceptions from docstring or raises statements
        raises = self._extract_raises(node, docstring)

        return FunctionInfo(
            name=node.name,
            params=params,
            return_type=return_type,
            docstring=docstring,
            decorators=decorators,
            line_number=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            raises=raises,
            has_validation=has_validation,
            has_error_handling=has_error_handling
        )

    def _extract_class_info(self, node: ast.ClassDef, source: str) -> ClassInfo:
        """Extract information about a class."""
        methods = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(self._extract_function_info(item, source))

        base_classes = [ast.unparse(base) for base in node.bases]

        return ClassInfo(
            name=node.name,
            methods=methods,
            docstring=ast.get_docstring(node),
            base_classes=base_classes,
            line_number=node.lineno
        )

    def _extract_imports(self, node: ast.Import | ast.ImportFrom) -> List[str]:
        """Extract import statements."""
        imports = []

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")

        return imports

    def _extract_constants(self, node: ast.Assign) -> Dict[str, Any]:
        """Extract module-level constants (UPPER_CASE variables)."""
        constants = {}

        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                try:
                    # Try to evaluate simple constants
                    value = ast.literal_eval(node.value)
                    constants[target.id] = value
                except (ValueError, TypeError):
                    # Can't evaluate, just store the AST representation
                    constants[target.id] = ast.unparse(node.value)

        return constants

    def _extract_comments(self, source: str) -> List[str]:
        """Extract standalone comments from source code."""
        comments = []

        for line in source.split('\n'):
            stripped = line.strip()
            if stripped.startswith('#') and not stripped.startswith('#!'):
                comments.append(stripped[1:].strip())

        return comments

    def _has_validation_logic(self, node: ast.FunctionDef) -> bool:
        """
        Check if function contains input validation logic.

        Looks for patterns like:
        - if param is None: raise ValueError
        - if param < 0: raise InvalidError
        - if not isinstance(param, type): raise TypeError
        """
        for child in ast.walk(node):
            if isinstance(child, ast.If):
                # Check if the if block raises an exception
                for stmt in child.body:
                    if isinstance(stmt, ast.Raise):
                        return True
                    # Check for early returns on validation
                    if isinstance(stmt, ast.Return):
                        return True

        return False

    def _extract_raises(self, node: ast.FunctionDef, docstring: Optional[str]) -> List[str]:
        """
        Extract exceptions that a function can raise.

        Looks in:
        1. Docstring (Raises: section)
        2. Raise statements in code
        """
        raises = []

        # From docstring
        if docstring:
            lines = docstring.split('\n')
            in_raises_section = False

            for line in lines:
                stripped = line.strip()
                if 'Raises:' in stripped or 'Raises' in stripped:
                    in_raises_section = True
                    continue

                if in_raises_section:
                    if stripped and not stripped[0].isspace():
                        # New section started
                        break

                    # Extract exception name
                    if ':' in stripped:
                        exc_name = stripped.split(':')[0].strip()
                        if exc_name:
                            raises.append(exc_name)

        # From actual raise statements
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                if isinstance(child.exc, ast.Call):
                    exc_name = ast.unparse(child.exc.func)
                    if exc_name not in raises:
                        raises.append(exc_name)
                elif isinstance(child.exc, ast.Name):
                    if child.exc.id not in raises:
                        raises.append(child.exc.id)

        return raises

    def _is_top_level(self, node: ast.AST, tree: ast.Module) -> bool:
        """Check if a node is at the top level of the module."""
        for item in tree.body:
            if item == node:
                return True
            # Check if it's inside a class
            if isinstance(item, ast.ClassDef):
                return False
        return False


if __name__ == '__main__':
    # Example usage
    parser = CodeParser()

    # Parse a single file
    analysis = parser.parse_file(Path('example.py'))

    print(f"Found {len(analysis.functions)} functions")
    print(f"Found {len(analysis.classes)} classes")

    for func in analysis.functions:
        print(f"\nFunction: {func.name}")
        print(f"  Params: {func.params}")
        print(f"  Raises: {func.raises}")
        print(f"  Has validation: {func.has_validation}")
