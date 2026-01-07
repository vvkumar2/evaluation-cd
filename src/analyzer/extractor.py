"""
Business logic extractor for identifying test-worthy patterns in code.

This module analyzes parsed code to extract:
- Business policies (refund windows, limits, rules)
- Validation rules (input constraints, type checks)
- Error handling patterns (what can go wrong)
- Decision logic (branching based on business rules)
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from .parser import CodeAnalysis, FunctionInfo, ClassInfo


@dataclass
class BusinessPolicy:
    """A business rule or policy extracted from code."""
    name: str
    description: str
    source_file: str
    source_line: int
    policy_type: str  # 'limit', 'window', 'validation', 'workflow'
    parameters: Dict[str, Any] = field(default_factory=dict)
    code_snippet: Optional[str] = None


@dataclass
class TestableScenario:
    """A scenario that should be tested."""
    name: str
    description: str
    source: str  # Where it came from in the code
    scenario_type: str  # 'happy_path', 'edge_case', 'error_path'
    related_policies: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    expected_behavior: str = ""


@dataclass
class ExtractedLogic:
    """Business logic extracted from a codebase."""
    policies: List[BusinessPolicy]
    scenarios: List[TestableScenario]
    validation_rules: List[Dict[str, Any]]
    error_conditions: List[Dict[str, Any]]


class BusinessLogicExtractor:
    """Extract business logic patterns from parsed code."""

    def __init__(self):
        # Patterns that indicate business policies
        self.policy_patterns = {
            'time_window': [
                r'(\d+)[\s-]*day',
                r'window',
                r'expires?',
                r'valid[\s_]for',
            ],
            'limit': [
                r'max(?:imum)?[\s_](\d+)',
                r'limit[\s_](\d+)',
                r'up[\s_]to[\s_](\d+)',
                r'threshold',
            ],
            'tier': [
                r'(gold|silver|bronze|premium|basic)',
                r'tier',
                r'membership',
            ],
            'status': [
                r'(pending|approved|denied|cancelled)',
                r'state',
                r'status',
            ]
        }

    def extract(self, analyses: List[CodeAnalysis]) -> ExtractedLogic:
        """
        Extract testable business logic from parsed code.

        Args:
            analyses: List of parsed code analyses

        Returns:
            ExtractedLogic containing policies, scenarios, etc.
        """
        all_policies = []
        all_scenarios = []
        all_validations = []
        all_errors = []

        for analysis in analyses:
            # Extract from functions
            for func in analysis.functions:
                policies, scenarios = self._extract_from_function(func, analysis)
                all_policies.extend(policies)
                all_scenarios.extend(scenarios)

                validations = self._extract_validations(func, analysis)
                all_validations.extend(validations)

                errors = self._extract_error_conditions(func, analysis)
                all_errors.extend(errors)

            # Extract from classes
            for cls in analysis.classes:
                for method in cls.methods:
                    policies, scenarios = self._extract_from_function(
                        method, analysis, class_name=cls.name
                    )
                    all_policies.extend(policies)
                    all_scenarios.extend(scenarios)

            # Extract from constants
            policies = self._extract_from_constants(analysis)
            all_policies.extend(policies)

        return ExtractedLogic(
            policies=all_policies,
            scenarios=all_scenarios,
            validation_rules=all_validations,
            error_conditions=all_errors
        )

    def _extract_from_function(
        self,
        func: FunctionInfo,
        analysis: CodeAnalysis,
        class_name: Optional[str] = None
    ) -> tuple[List[BusinessPolicy], List[TestableScenario]]:
        """Extract business logic from a function."""
        policies = []
        scenarios = []

        full_name = f"{class_name}.{func.name}" if class_name else func.name

        # Extract from docstring
        if func.docstring:
            doc_policies = self._extract_policies_from_text(
                func.docstring,
                source_file=analysis.file_path,
                source_line=func.line_number,
                context=full_name
            )
            policies.extend(doc_policies)

        # Generate scenarios from error handling
        if func.raises:
            for exc in func.raises:
                scenario = TestableScenario(
                    name=f"{full_name}_raises_{exc}",
                    description=f"Function should raise {exc} under certain conditions",
                    source=f"{analysis.file_path}:{func.line_number}",
                    scenario_type='error_path'
                )
                scenarios.append(scenario)

        # Generate happy path scenario if no special logic detected
        if not func.has_validation and not func.has_error_handling:
            scenario = TestableScenario(
                name=f"{full_name}_happy_path",
                description=f"Test normal execution of {full_name}",
                source=f"{analysis.file_path}:{func.line_number}",
                scenario_type='happy_path'
            )
            scenarios.append(scenario)

        return policies, scenarios

    def _extract_from_constants(self, analysis: CodeAnalysis) -> List[BusinessPolicy]:
        """Extract business policies from module-level constants."""
        policies = []

        for const_name, const_value in analysis.constants.items():
            # Check if constant name suggests a policy
            name_lower = const_name.lower()

            if 'limit' in name_lower or 'max' in name_lower:
                policy = BusinessPolicy(
                    name=const_name,
                    description=f"System limit: {const_name} = {const_value}",
                    source_file=analysis.file_path,
                    source_line=0,
                    policy_type='limit',
                    parameters={'value': const_value}
                )
                policies.append(policy)

            elif 'window' in name_lower or 'days' in name_lower:
                policy = BusinessPolicy(
                    name=const_name,
                    description=f"Time window: {const_name} = {const_value}",
                    source_file=analysis.file_path,
                    source_line=0,
                    policy_type='window',
                    parameters={'value': const_value}
                )
                policies.append(policy)

        return policies

    def _extract_policies_from_text(
        self,
        text: str,
        source_file: str,
        source_line: int,
        context: str
    ) -> List[BusinessPolicy]:
        """Extract policies from text (docstrings, comments)."""
        policies = []

        for policy_type, patterns in self.policy_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)

                for match in matches:
                    # Extract surrounding context
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    snippet = text[start:end].strip()

                    policy = BusinessPolicy(
                        name=f"{context}_{policy_type}_{match.group(0)}",
                        description=snippet,
                        source_file=source_file,
                        source_line=source_line,
                        policy_type=policy_type,
                        parameters={'matched_text': match.group(0)},
                        code_snippet=snippet
                    )
                    policies.append(policy)

        return policies

    def _extract_validations(
        self,
        func: FunctionInfo,
        analysis: CodeAnalysis
    ) -> List[Dict[str, Any]]:
        """Extract input validation rules from a function."""
        validations = []

        if not func.has_validation:
            return validations

        # Common validation patterns from docstring
        if func.docstring:
            # Look for parameter descriptions with constraints
            param_pattern = r'(\w+)\s*\((\w+)\):\s*(.+?)(?:\n|$)'
            matches = re.finditer(param_pattern, func.docstring)

            for match in matches:
                param_name, param_type, description = match.groups()

                validation = {
                    'function': func.name,
                    'parameter': param_name,
                    'type': param_type,
                    'constraint': description.strip(),
                    'source': f"{analysis.file_path}:{func.line_number}"
                }
                validations.append(validation)

        return validations

    def _extract_error_conditions(
        self,
        func: FunctionInfo,
        analysis: CodeAnalysis
    ) -> List[Dict[str, Any]]:
        """Extract error conditions from a function."""
        errors = []

        for exc in func.raises:
            error = {
                'function': func.name,
                'exception': exc,
                'source': f"{analysis.file_path}:{func.line_number}",
                'has_handling': func.has_error_handling
            }
            errors.append(error)

        return errors


if __name__ == '__main__':
    # Example usage
    from .parser import CodeParser
    from pathlib import Path

    parser = CodeParser()
    extractor = BusinessLogicExtractor()

    # Parse a directory
    analyses = parser.parse_directory(Path('./example_codebase'))

    # Extract business logic
    logic = extractor.extract(analyses)

    print(f"\nExtracted {len(logic.policies)} policies:")
    for policy in logic.policies[:5]:  # Show first 5
        print(f"  - {policy.name}: {policy.description[:60]}...")

    print(f"\nExtracted {len(logic.scenarios)} scenarios:")
    for scenario in logic.scenarios[:5]:  # Show first 5
        print(f"  - {scenario.name} ({scenario.scenario_type})")
