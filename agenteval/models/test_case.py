"""Test case data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TestType(str, Enum):
    """Type of test case."""

    QA = "qa"  # Simple question-answer
    EDGE_CASE = "edge_case"  # Edge cases (out-of-scope, ambiguous, etc.)
    CONSISTENCY = "consistency"  # Consistency check (same question, different phrasing)


@dataclass
class ExpectedResponse:
    """Expected response criteria for a test case."""

    # Facts that should be present in the response
    contains_facts: list[str] = field(default_factory=list)

    # Source documents that should be cited
    sources: list[str] = field(default_factory=list)

    # Expected tone (helpful, professional, etc.)
    tone: Optional[str] = None

    # For edge cases: should the agent decline?
    should_decline: bool = False

    # For edge cases: what should it suggest instead?
    should_suggest: Optional[str] = None

    # For consistency tests: the original question ID to compare against
    consistency_with: Optional[str] = None


@dataclass
class TestCase:
    """A single test case for agent evaluation."""

    id: str
    type: TestType
    message: str
    expected: ExpectedResponse
    category: Optional[str] = None
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        result = {
            "id": self.id,
            "type": self.type.value,
            "input": {"message": self.message},
            "expected": {},
        }

        if self.category:
            result["category"] = self.category

        if self.weight != 1.0:
            result["weight"] = self.weight

        # Add expected fields
        if self.expected.contains_facts:
            result["expected"]["contains_facts"] = self.expected.contains_facts
        if self.expected.sources:
            result["expected"]["sources"] = self.expected.sources
        if self.expected.tone:
            result["expected"]["tone"] = self.expected.tone
        if self.expected.should_decline:
            result["expected"]["should_decline"] = True
        if self.expected.should_suggest:
            result["expected"]["should_suggest"] = self.expected.should_suggest
        if self.expected.consistency_with:
            result["expected"]["consistency_with"] = self.expected.consistency_with

        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "TestCase":
        """Create from dictionary (YAML deserialization)."""
        expected_data = data.get("expected", {})
        expected = ExpectedResponse(
            contains_facts=expected_data.get("contains_facts", []),
            sources=expected_data.get("sources", []),
            tone=expected_data.get("tone"),
            should_decline=expected_data.get("should_decline", False),
            should_suggest=expected_data.get("should_suggest"),
            consistency_with=expected_data.get("consistency_with"),
        )

        return cls(
            id=data["id"],
            type=TestType(data["type"]),
            message=data.get("input", {}).get("message", ""),
            expected=expected,
            category=data.get("category"),
            weight=data.get("weight", 1.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TestSuite:
    """A collection of test cases."""

    name: str
    knowledge_base_path: str
    tests: list[TestCase] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return {
            "test_suite": {
                "name": self.name,
                "knowledge_base": self.knowledge_base_path,
                **({"metadata": self.metadata} if self.metadata else {}),
            },
            "tests": [test.to_dict() for test in self.tests],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TestSuite":
        """Create from dictionary (YAML deserialization)."""
        suite_data = data.get("test_suite", {})
        tests_data = data.get("tests", [])

        return cls(
            name=suite_data.get("name", "Unnamed Suite"),
            knowledge_base_path=suite_data.get("knowledge_base", ""),
            tests=[TestCase.from_dict(t) for t in tests_data],
            metadata=suite_data.get("metadata", {}),
        )

    @property
    def qa_tests(self) -> list[TestCase]:
        """Get all Q&A tests."""
        return [t for t in self.tests if t.type == TestType.QA]

    @property
    def edge_case_tests(self) -> list[TestCase]:
        """Get all edge case tests."""
        return [t for t in self.tests if t.type == TestType.EDGE_CASE]

    @property
    def consistency_tests(self) -> list[TestCase]:
        """Get all consistency tests."""
        return [t for t in self.tests if t.type == TestType.CONSISTENCY]

