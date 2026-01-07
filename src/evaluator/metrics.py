"""
Metrics and scoring logic for agent evaluation.

Handles:
- Combining scores from multiple evaluators
- Weighted dimension scoring
- Pass/fail determination
- Generating actionable feedback
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class EvalStatus(Enum):
    """Evaluation result status."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class CheckpointResult:
    """Result from evaluating a single checkpoint."""
    criterion: str
    check_type: str  # 'must', 'must_not', 'should'
    passed: bool
    score: float  # 0.0 to 1.0
    reason: str
    weight: float = 1.0


@dataclass
class TurnEvaluation:
    """Evaluation results for a single turn."""
    turn_number: int
    checkpoint_results: List[CheckpointResult]
    turn_score: float  # 0.0 to 1.0
    feedback: str


@dataclass
class DimensionScore:
    """Score for a quality dimension (empathy, resolution, etc.)."""
    dimension: str
    score: float  # 1.0 to 5.0
    weight: float
    reasoning: str


@dataclass
class EvaluationResult:
    """Complete evaluation result for a test case."""
    test_id: str
    test_name: str
    status: EvalStatus
    overall_score: float  # 0.0 to 1.0 (or 1.0 to 5.0 depending on context)
    dimension_scores: List[DimensionScore]
    turn_evaluations: List[TurnEvaluation]
    pass_threshold: float
    feedback: str
    improvement_suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCalculator:
    """Calculate final scores from evaluation components."""

    def calculate_overall_score(
        self,
        dimension_scores: List[DimensionScore],
        turn_evaluations: List[TurnEvaluation]
    ) -> float:
        """
        Calculate overall score from dimensions and turn results.

        Args:
            dimension_scores: Scores for each quality dimension
            turn_evaluations: Per-turn evaluation results

        Returns:
            Overall score (0.0 to 1.0)
        """
        if not dimension_scores and not turn_evaluations:
            return 0.0

        # Weighted average of dimension scores (normalized to 0-1)
        if dimension_scores:
            total_weight = sum(d.weight for d in dimension_scores)
            if total_weight > 0:
                dimension_avg = sum(
                    (d.score / 5.0) * d.weight  # Normalize 1-5 to 0-1
                    for d in dimension_scores
                ) / total_weight
            else:
                dimension_avg = 0.0
        else:
            dimension_avg = 0.0

        # Average of turn scores
        if turn_evaluations:
            turn_avg = sum(t.turn_score for t in turn_evaluations) / len(turn_evaluations)
        else:
            turn_avg = 0.0

        # Combine (70% dimension scores, 30% turn checkpoints)
        if dimension_scores and turn_evaluations:
            overall = (dimension_avg * 0.7) + (turn_avg * 0.3)
        elif dimension_scores:
            overall = dimension_avg
        else:
            overall = turn_avg

        return overall

    def determine_status(
        self,
        overall_score: float,
        pass_threshold: float,
        has_critical_failures: bool = False
    ) -> EvalStatus:
        """
        Determine pass/fail status.

        Args:
            overall_score: Overall score (0-1)
            pass_threshold: Minimum score to pass
            has_critical_failures: Whether there were critical violations

        Returns:
            EvalStatus
        """
        if has_critical_failures:
            return EvalStatus.FAIL

        if overall_score >= pass_threshold:
            return EvalStatus.PASS
        else:
            return EvalStatus.FAIL

    def generate_feedback(
        self,
        status: EvalStatus,
        overall_score: float,
        dimension_scores: List[DimensionScore],
        turn_evaluations: List[TurnEvaluation]
    ) -> str:
        """
        Generate human-readable feedback.

        Args:
            status: Pass/fail status
            overall_score: Overall score
            dimension_scores: Dimension scores
            turn_evaluations: Turn evaluations

        Returns:
            Feedback string
        """
        lines = []

        # Overall result
        status_emoji = "✓" if status == EvalStatus.PASS else "✗"
        lines.append(f"{status_emoji} Overall: {overall_score:.2f} ({status.value.upper()})")

        # Dimension breakdown
        if dimension_scores:
            lines.append("\nDimension Scores:")
            for dim in sorted(dimension_scores, key=lambda d: d.score):
                lines.append(f"  • {dim.dimension}: {dim.score:.1f}/5.0 - {dim.reasoning}")

        # Turn-by-turn issues
        failed_turns = [t for t in turn_evaluations if t.turn_score < 0.7]
        if failed_turns:
            lines.append("\nTurns with Issues:")
            for turn in failed_turns:
                lines.append(f"  • Turn {turn.turn_number}: {turn.feedback}")

        return "\n".join(lines)

    def generate_improvement_suggestions(
        self,
        dimension_scores: List[DimensionScore],
        turn_evaluations: List[TurnEvaluation]
    ) -> List[str]:
        """
        Generate actionable improvement suggestions.

        Args:
            dimension_scores: Dimension scores
            turn_evaluations: Turn evaluations

        Returns:
            List of suggestions
        """
        suggestions = []

        # Find lowest scoring dimensions
        if dimension_scores:
            sorted_dims = sorted(dimension_scores, key=lambda d: d.score)

            for dim in sorted_dims[:2]:  # Top 2 areas for improvement
                if dim.score < 4.0:
                    suggestion = self._get_dimension_tip(dim.dimension, dim.score)
                    if suggestion:
                        suggestions.append(suggestion)

        # Find common checkpoint failures
        failed_criteria = {}
        for turn in turn_evaluations:
            for cp in turn.checkpoint_results:
                if not cp.passed and cp.check_type == 'must':
                    failed_criteria[cp.criterion] = failed_criteria.get(cp.criterion, 0) + 1

        # Suggest fixes for frequently failed checkpoints
        for criterion, count in sorted(failed_criteria.items(), key=lambda x: x[1], reverse=True)[:3]:
            suggestions.append(f"Fix '{criterion}' - failed in {count} turn(s)")

        return suggestions

    def _get_dimension_tip(self, dimension: str, score: float) -> Optional[str]:
        """Get improvement tip for a dimension."""
        tips = {
            'empathy': "Add explicit acknowledgment of customer emotions before offering solutions",
            'resolution': "Ensure all customer questions are answered with clear next steps",
            'policy_compliance': "Review policy documentation and ensure all rules are followed",
            'efficiency': "Reduce unnecessary clarifying questions by using available context",
            'de_escalation': "Lead with validation of customer feelings before problem-solving",
            'professionalism': "Maintain consistent professional tone throughout conversation",
            'helpfulness': "Provide specific, actionable information rather than generic responses"
        }

        if dimension.lower() in tips and score < 4.0:
            return f"Improve {dimension} ({score:.1f}/5.0): {tips[dimension.lower()]}"

        return None

    def create_evaluation_result(
        self,
        test_id: str,
        test_name: str,
        dimension_scores: List[DimensionScore],
        turn_evaluations: List[TurnEvaluation],
        pass_threshold: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        """
        Create a complete evaluation result.

        Args:
            test_id: Test case ID
            test_name: Test case name
            dimension_scores: Dimension scores
            turn_evaluations: Turn evaluations
            pass_threshold: Pass threshold
            metadata: Optional metadata

        Returns:
            EvaluationResult
        """
        # Calculate overall score
        overall_score = self.calculate_overall_score(dimension_scores, turn_evaluations)

        # Check for critical failures
        has_critical_failures = any(
            not cp.passed and cp.check_type == 'must'
            for turn in turn_evaluations
            for cp in turn.checkpoint_results
        )

        # Determine status
        status = self.determine_status(overall_score, pass_threshold, has_critical_failures)

        # Generate feedback
        feedback = self.generate_feedback(status, overall_score, dimension_scores, turn_evaluations)

        # Generate suggestions
        suggestions = self.generate_improvement_suggestions(dimension_scores, turn_evaluations)

        return EvaluationResult(
            test_id=test_id,
            test_name=test_name,
            status=status,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            turn_evaluations=turn_evaluations,
            pass_threshold=pass_threshold,
            feedback=feedback,
            improvement_suggestions=suggestions,
            metadata=metadata or {}
        )


if __name__ == '__main__':
    # Example usage
    calculator = MetricsCalculator()

    # Sample dimension scores
    dimensions = [
        DimensionScore("empathy", 3.5, 0.25, "Adequate but could be warmer"),
        DimensionScore("resolution", 4.5, 0.35, "Problem fully resolved"),
        DimensionScore("policy_compliance", 5.0, 0.25, "All policies followed"),
        DimensionScore("efficiency", 4.0, 0.15, "Reasonably efficient")
    ]

    # Sample turn evaluations
    turns = [
        TurnEvaluation(
            turn_number=1,
            checkpoint_results=[
                CheckpointResult("empathy", "must", True, 0.8, "Good acknowledgment"),
                CheckpointResult("no_blame", "must_not", True, 1.0, "No blame detected")
            ],
            turn_score=0.9,
            feedback="Good start"
        )
    ]

    # Create result
    result = calculator.create_evaluation_result(
        test_id="test_001",
        test_name="Refund request",
        dimension_scores=dimensions,
        turn_evaluations=turns,
        pass_threshold=0.7
    )

    print(result.feedback)
    print("\nSuggestions:")
    for suggestion in result.improvement_suggestions:
        print(f"  - {suggestion}")
