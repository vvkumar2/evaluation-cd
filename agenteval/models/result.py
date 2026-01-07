"""Result data models for test execution and evaluation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TestStatus(str, Enum):
    """Status of a test case execution."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class EvaluationScore:
    """Scores for different evaluation criteria."""

    factual_accuracy: float = 0.0
    completeness: float = 0.0
    citation: float = 0.0
    consistency: float = 0.0
    tone: float = 0.0

    @property
    def weighted_score(self) -> float:
        """Calculate weighted overall score."""
        weights = {
            "factual_accuracy": 0.4,
            "completeness": 0.3,
            "citation": 0.15,
            "consistency": 0.1,
            "tone": 0.05,
        }
        total = sum(
            getattr(self, key) * weight
            for key, weight in weights.items()
        )
        return total

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "factual_accuracy": self.factual_accuracy,
            "completeness": self.completeness,
            "citation": self.citation,
            "consistency": self.consistency,
            "tone": self.tone,
            "weighted_score": self.weighted_score,
        }


@dataclass
class EvaluationResult:
    """Detailed evaluation result for a single criterion."""

    criterion: str
    score: float
    passed: bool
    details: dict = field(default_factory=dict)
    feedback: Optional[str] = None


@dataclass
class TestResult:
    """Result of running a single test case."""

    test_id: str
    status: TestStatus
    agent_response: Optional[str] = None
    scores: Optional[EvaluationScore] = None
    evaluations: list[EvaluationResult] = field(default_factory=list)
    error_message: Optional[str] = None
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def passed(self) -> bool:
        """Check if the test passed (score above threshold)."""
        if self.status == TestStatus.ERROR:
            return False
        if self.scores is None:
            return False
        return self.scores.weighted_score >= 0.7  # Default threshold

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "test_id": self.test_id,
            "status": self.status.value,
            "passed": self.passed,
            "agent_response": self.agent_response,
            "scores": self.scores.to_dict() if self.scores else None,
            "evaluations": [
                {
                    "criterion": e.criterion,
                    "score": e.score,
                    "passed": e.passed,
                    "details": e.details,
                    "feedback": e.feedback,
                }
                for e in self.evaluations
            ],
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RunResult:
    """Result of running a complete test suite."""

    suite_name: str
    results: list[TestResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    @property
    def total_tests(self) -> int:
        """Total number of tests."""
        return len(self.results)

    @property
    def passed_tests(self) -> int:
        """Number of passed tests."""
        return sum(1 for r in self.results if r.passed)

    @property
    def failed_tests(self) -> int:
        """Number of failed tests."""
        return sum(1 for r in self.results if not r.passed and r.status != TestStatus.ERROR)

    @property
    def error_tests(self) -> int:
        """Number of tests with errors."""
        return sum(1 for r in self.results if r.status == TestStatus.ERROR)

    @property
    def pass_rate(self) -> float:
        """Overall pass rate as a percentage."""
        if not self.results:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def average_score(self) -> float:
        """Average weighted score across all tests."""
        scored = [r for r in self.results if r.scores]
        if not scored:
            return 0.0
        return sum(r.scores.weighted_score for r in scored) / len(scored)

    @property
    def duration_ms(self) -> int:
        """Total duration in milliseconds."""
        if not self.completed_at:
            return 0
        return int((self.completed_at - self.started_at).total_seconds() * 1000)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "suite_name": self.suite_name,
            "summary": {
                "total": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
                "errors": self.error_tests,
                "pass_rate": round(self.pass_rate, 2),
                "average_score": round(self.average_score, 3),
            },
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }

