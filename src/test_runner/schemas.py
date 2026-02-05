"""Schemas for test execution and reporting."""

from pydantic import BaseModel, Field


class TestResult(BaseModel):
    """Result from a single test execution."""

    test_id: str = Field(description="Unique test ID")
    intent_name: str = Field(description="Intent being tested")
    passed: bool = Field(description="True if score >= 7")
    score: int = Field(description="Score from 1-10 from LLM")
    reasoning: str = Field(description="LLM reasoning for the score")
    output: str = Field(description="Agent's actual response")


class TestResultList(BaseModel):
    """List of test results."""

    results: list[TestResult]

    def count_passed(self) -> int:
        """Count number of passed tests."""
        return sum(1 for r in self.results if r.passed)

    def count_failed(self) -> int:
        """Count number of failed tests."""
        return sum(1 for r in self.results if not r.passed)


class TestRunReport(BaseModel):
    """Summary report of test run."""

    agent_name: str = Field(description="Name of agent tested")
    total_tests: int = Field(description="Total number of tests run")
    passed_tests: int = Field(description="Number of tests passed")
    failed_tests: int = Field(description="Number of tests failed")
    pass_rate: float = Field(description="Pass rate as decimal (e.g., 0.93)")
    results: TestResultList = Field(description="All individual test results")

    def summary(self) -> str:
        """Return summary string."""
        return (
            f"Agent: {self.agent_name}, "
            f"Pass Rate: {self.pass_rate*100:.1f}% "
            f"({self.passed_tests}/{self.total_tests})"
        )
