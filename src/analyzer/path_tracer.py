"""
Code path tracer for extracting all possible execution paths through functions.

Traces through if/elif/else branches to find all possible paths
from function entry to exit, tracking conditions along the way.
"""

import ast
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple


@dataclass
class ExecutionPath:
    """A complete execution path through a function."""
    function_name: str
    path_number: int
    conditions: List[str]  # Conditions that must be true for this path
    negated_conditions: List[str]  # Conditions that must be false
    actions: List[str]  # Operations performed in this path
    return_value: Optional[str] = None
    raises_exception: Optional[str] = None
    calls_functions: List[str] = field(default_factory=list)
    is_error_path: bool = False
    line_numbers: List[int] = field(default_factory=list)


class PathTracer:
    """Trace all execution paths through Python functions."""

    def __init__(self):
        self.paths = []

    def trace_function(self, func_node: ast.FunctionDef) -> List[ExecutionPath]:
        """
        Trace all execution paths through a function.

        Args:
            func_node: AST node for the function

        Returns:
            List of all possible execution paths
        """
        self.paths = []
        self.path_counter = 0

        # Start tracing from function body
        self._trace_block(
            func_node.body,
            func_name=func_node.name,
            conditions=[],
            negated_conditions=[],
            actions=[],
            calls=[],
            lines=[]
        )

        return self.paths

    def _trace_block(
        self,
        statements: List[ast.stmt],
        func_name: str,
        conditions: List[str],
        negated_conditions: List[str],
        actions: List[str],
        calls: List[str],
        lines: List[int]
    ):
        """Recursively trace through a block of statements."""

        for i, stmt in enumerate(statements):
            lines_copy = lines.copy()
            if hasattr(stmt, 'lineno'):
                lines_copy.append(stmt.lineno)

            # Handle if/elif/else branches
            if isinstance(stmt, ast.If):
                self._trace_if_statement(
                    stmt, func_name, conditions.copy(), negated_conditions.copy(),
                    actions.copy(), calls.copy(), lines_copy,
                    remaining_statements=statements[i+1:]
                )
                # Don't continue after if statement at this level
                # (paths are handled in branches)
                return

            # Handle return statements
            elif isinstance(stmt, ast.Return):
                return_val = None
                if stmt.value:
                    return_val = ast.unparse(stmt.value)

                self.path_counter += 1
                self.paths.append(ExecutionPath(
                    function_name=func_name,
                    path_number=self.path_counter,
                    conditions=conditions.copy(),
                    negated_conditions=negated_conditions.copy(),
                    actions=actions.copy(),
                    return_value=return_val,
                    calls_functions=calls.copy(),
                    line_numbers=lines_copy
                ))
                return  # Path ends here

            # Handle raise statements
            elif isinstance(stmt, ast.Raise):
                exception = None
                if stmt.exc:
                    if isinstance(stmt.exc, ast.Call):
                        exception = ast.unparse(stmt.exc.func)
                    else:
                        exception = ast.unparse(stmt.exc)

                self.path_counter += 1
                self.paths.append(ExecutionPath(
                    function_name=func_name,
                    path_number=self.path_counter,
                    conditions=conditions.copy(),
                    negated_conditions=negated_conditions.copy(),
                    actions=actions.copy(),
                    raises_exception=exception,
                    calls_functions=calls.copy(),
                    is_error_path=True,
                    line_numbers=lines_copy
                ))
                return  # Path ends here

            # Track function calls
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                call_name = self._extract_call_name(stmt.value)
                if call_name:
                    calls.append(call_name)
                    actions.append(f"call:{call_name}")

            # Track assignments as actions
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        actions.append(f"assign:{target.id}")

        # If we get here without return/raise, it's an implicit return None
        self.path_counter += 1
        self.paths.append(ExecutionPath(
            function_name=func_name,
            path_number=self.path_counter,
            conditions=conditions,
            negated_conditions=negated_conditions,
            actions=actions,
            return_value="None",
            calls_functions=calls,
            line_numbers=lines_copy
        ))

    def _trace_if_statement(
        self,
        if_node: ast.If,
        func_name: str,
        conditions: List[str],
        negated_conditions: List[str],
        actions: List[str],
        calls: List[str],
        lines: List[int],
        remaining_statements: List[ast.stmt]
    ):
        """Trace through if/elif/else branches."""

        # Extract condition
        condition = ast.unparse(if_node.test)

        # Trace true branch (if body)
        true_conditions = conditions.copy()
        true_conditions.append(condition)
        self._trace_block(
            if_node.body + remaining_statements,
            func_name,
            true_conditions,
            negated_conditions.copy(),
            actions.copy(),
            calls.copy(),
            lines.copy()
        )

        # Trace false branch (else/elif)
        if if_node.orelse:
            false_negated = negated_conditions.copy()
            false_negated.append(condition)

            # Check if it's elif
            if len(if_node.orelse) == 1 and isinstance(if_node.orelse[0], ast.If):
                # This is elif - trace it
                self._trace_if_statement(
                    if_node.orelse[0],
                    func_name,
                    conditions.copy(),
                    false_negated,
                    actions.copy(),
                    calls.copy(),
                    lines.copy(),
                    remaining_statements=remaining_statements
                )
            else:
                # This is else - trace the else block
                self._trace_block(
                    if_node.orelse + remaining_statements,
                    func_name,
                    conditions.copy(),
                    false_negated,
                    actions.copy(),
                    calls.copy(),
                    lines.copy()
                )
        else:
            # No else branch - continue with remaining statements
            # but with the condition negated
            false_negated = negated_conditions.copy()
            false_negated.append(condition)
            self._trace_block(
                remaining_statements,
                func_name,
                conditions.copy(),
                false_negated,
                actions.copy(),
                calls.copy(),
                lines.copy()
            )

    def _extract_call_name(self, call_node: ast.Call) -> Optional[str]:
        """Extract the name of a function being called."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return ast.unparse(call_node.func)
        return None


def extract_all_paths(func_node: ast.FunctionDef) -> List[ExecutionPath]:
    """
    Extract all execution paths from a function.

    Args:
        func_node: AST node for the function

    Returns:
        List of all execution paths
    """
    tracer = PathTracer()
    return tracer.trace_function(func_node)


if __name__ == '__main__':
    # Test with a sample function
    source = """
def process_refund(order_total, days_since_delivery, is_damaged):
    if order_total < 0:
        raise ValueError("Negative amount")

    if is_damaged:
        return "approved"

    if days_since_delivery <= 30:
        if order_total <= 200:
            return "auto_approved"
        else:
            return "needs_manager_approval"
    else:
        return "denied"
"""

    tree = ast.parse(source)
    func = tree.body[0]

    paths = extract_all_paths(func)

    print(f"Found {len(paths)} execution paths:\n")
    for path in paths:
        print(f"Path {path.path_number}:")
        if path.conditions:
            print(f"  Conditions: {', '.join(path.conditions)}")
        if path.negated_conditions:
            print(f"  NOT: {', '.join(path.negated_conditions)}")
        if path.return_value:
            print(f"  Returns: {path.return_value}")
        if path.raises_exception:
            print(f"  Raises: {path.raises_exception}")
        print()
