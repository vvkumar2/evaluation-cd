"""Schemas for generated test cases."""

from typing import Optional
from pydantic import BaseModel, Field


class TestInput(BaseModel):
    """Input to provide to agent."""

    message: str = Field(description="Message to send to agent")
    context: Optional[dict] = Field(
        default=None, description="Context dict (e.g., customer_id)"
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
    expected_tool_calls: list[str] = Field(
        description="Tool names the agent must call for this test case"
    )

    # Test data
    backend_state: dict[str, list[dict]] = Field(
        description="Entity instances for backend. Keys are entity names, values are lists of instances."
    )

    # Agent input
    input: TestInput = Field(description="Message and context for agent")

    # Mock tool overrides (optional, for simulating tool failures)
    mock_tool_responses: Optional[dict[str, dict]] = Field(
        default=None,
        description="Per-test tool response overrides. Keys are tool names, values are "
        '{"response": str, "is_error": bool}. Overrides default mock_response from entity_schema.',
    )

    # Test classification
    category: str = Field(
        description="Test category: happy_path, edge_case, boundary, invalid_input, error_handling"
    )


class ContextEntry(BaseModel):
    """A single key-value pair for context."""

    key: str
    value: str


class TestInputLLM(BaseModel):
    """LLM-compatible input model (no bare dicts)."""

    message: str = Field(description="Message to send to agent")
    context: Optional[list[ContextEntry]] = Field(
        default=None, description="Context entries (e.g., customer_id=C123)"
    )

    def to_test_input(self) -> "TestInput":
        """Convert to TestInput with dict context."""
        context_dict = (
            {entry.key: entry.value for entry in self.context} if self.context else None
        )
        return TestInput(message=self.message, context=context_dict)


class BackendEntityField(BaseModel):
    """A single field in a backend entity instance."""

    key: str
    value: str | int | float | bool | None


class BackendEntityInstance(BaseModel):
    """A single entity instance as a list of fields."""

    fields: list[BackendEntityField]

    def to_dict(self) -> dict:
        """Convert to plain dict."""
        return {f.key: f.value for f in self.fields}


class BackendEntityGroup(BaseModel):
    """A group of entity instances under one entity name."""

    entity_name: str
    instances: list[BackendEntityInstance]


class TestCaseLLMResponse(BaseModel):
    """LLM response fields for a generated test case."""

    test_id: str
    description: str = ""
    backend_state: list[BackendEntityGroup]
    input: TestInputLLM
    category: str = "happy_path"

    def get_backend_state_dict(self) -> dict[str, list[dict]]:
        """Convert structured backend state to dict form."""
        return {
            group.entity_name: [inst.to_dict() for inst in group.instances]
            for group in self.backend_state
        }


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
