"""Base evaluator interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class EvaluationResult:
    """Result of an evaluation."""

    criterion: str
    score: float  # 0.0 to 1.0
    passed: bool
    details: dict = None
    feedback: Optional[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class Evaluator(ABC):
    """Abstract base class for evaluators."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this evaluator."""
        pass

    @abstractmethod
    def evaluate(self, *args, **kwargs) -> EvaluationResult:
        """Perform evaluation.

        Args vary by evaluator type.

        Returns:
            EvaluationResult with score and details.
        """
        pass

