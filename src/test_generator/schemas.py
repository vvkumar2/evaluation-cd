"""Schemas for generated test cases."""

from pydantic import BaseModel, Field
from typing import Optional


class TestInput(BaseModel):
    """Input to provide to agent."""
    message: str = Field(description="Message to send to agent")
    context: Optional[dict] = Field(
        default=None,
        description="Context dict (e.g., customer_id)"
    )


class GeneratedTestCase(BaseModel):
    """Runnable test case generated from rule."""

    # Identification & parsing
    test_id: str = Field(
        description="Unique test ID in snake_case, parseable to get test name"
    )
    intent_name: str = Field(description="Intent being tested")

    # Documentation
    description: str = Field(description="Human-readable test description")

    # From extraction
    rule_conditions: list[dict] = Field(
        description="Structured conditions from extracted rule"
    )
    expected_behavior: str = Field(
        description="Expected behavior copied from extraction"
    )

    # Test data
    backend_state: dict[str, list[dict]] = Field(
        description="Entity instances for backend. Keys are entity names, values are lists of instances."
    )

    # Agent input
    input: TestInput = Field(description="Message and context for agent")

    # Test classification
    category: str = Field(
        description="Test category: happy_path, edge_case, boundary, invalid_input, error_handling"
    )


class GeneratedTestSuite(BaseModel):
    """Complete test suite for an agent."""
    agent_name: str
    test_cases: list[GeneratedTestCase]

    def count_by_category(self) -> dict[str, int]:
        """Count tests by category."""
        counts = {}
        for test in self.test_cases:
            counts[test.category] = counts.get(test.category, 0) + 1
        return counts

    def summary(self) -> str:
        """Return summary of test suite."""
        return (
            f"Agent: {self.agent_name}, "
            f"Total Tests: {len(self.test_cases)}, "
            f"Categories: {self.count_by_category()}"
        )
