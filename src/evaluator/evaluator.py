"""
Main evaluator that combines compliance checking and LLM judging.

Orchestrates:
- Per-turn checkpoint evaluation (compliance checker)
- Overall conversation quality (LLM judge)
- Score calculation and result generation
"""

from typing import List, Dict, Any
from ..runner.runner import TestExecution
from .compliance import ComplianceChecker
from .llm_judge import LLMJudge
from .metrics import (
    MetricsCalculator,
    EvaluationResult,
    TurnEvaluation,
    CheckpointResult
)


class Evaluator:
    """Main evaluator combining all evaluation methods."""

    def __init__(
        self,
        use_llm: bool = True,
        llm_provider: str = "openai",
        llm_model: str = None
    ):
        """
        Initialize evaluator.

        Args:
            use_llm: Whether to use LLM-as-judge
            llm_provider: LLM provider ("openai" or "anthropic")
            llm_model: Optional model override
        """
        self.compliance_checker = ComplianceChecker()
        self.metrics_calculator = MetricsCalculator()

        self.use_llm = use_llm
        if use_llm:
            self.llm_judge = LLMJudge(provider=llm_provider, model=llm_model)
        else:
            self.llm_judge = None

    def evaluate(self, test_execution: TestExecution) -> EvaluationResult:
        """
        Evaluate a test execution.

        Args:
            test_execution: Results from running a test

        Returns:
            EvaluationResult with scores and feedback
        """
        # If test execution failed, return error result
        if not test_execution.success:
            return self._create_error_result(test_execution)

        # Step 1: Evaluate each turn with compliance checker
        turn_evaluations = []

        for turn_exec in test_execution.turns:
            checkpoints = turn_exec.metadata.get('checkpoints', [])

            # Check all checkpoints
            checkpoint_results = self.compliance_checker.check_all_checkpoints(
                turn_exec.agent_response,
                checkpoints
            )

            # Calculate turn score
            turn_score = self.compliance_checker.calculate_turn_score(checkpoint_results)

            # Generate feedback
            failed = [cp for cp in checkpoint_results if not cp.passed and cp.check_type == 'must']
            if failed:
                feedback = f"Failed: {', '.join(cp.criterion for cp in failed)}"
            else:
                feedback = "All checkpoints passed"

            turn_eval = TurnEvaluation(
                turn_number=turn_exec.turn_number,
                checkpoint_results=checkpoint_results,
                turn_score=turn_score,
                feedback=feedback
            )
            turn_evaluations.append(turn_eval)

        # Step 2: Use LLM judge for overall conversation quality
        dimension_scores = []

        if self.use_llm and self.llm_judge:
            customer_messages = [t.customer_message for t in test_execution.turns]
            agent_responses = [t.agent_response for t in test_execution.turns]
            context = test_execution.context
            dimensions = context.get('evaluation_dimensions', {})

            if dimensions:
                dimension_scores = self.llm_judge.evaluate_conversation(
                    customer_messages,
                    agent_responses,
                    context,
                    dimensions
                )

        # Step 3: Calculate final score and create result
        pass_threshold = test_execution.context.get('pass_threshold', 0.7)

        result = self.metrics_calculator.create_evaluation_result(
            test_id=test_execution.test_id,
            test_name=test_execution.test_name,
            dimension_scores=dimension_scores,
            turn_evaluations=turn_evaluations,
            pass_threshold=pass_threshold,
            metadata={
                'total_duration_ms': test_execution.total_duration_ms,
                'num_turns': len(test_execution.turns)
            }
        )

        return result

    def evaluate_batch(
        self,
        test_executions: List[TestExecution]
    ) -> List[EvaluationResult]:
        """
        Evaluate multiple test executions.

        Args:
            test_executions: List of test execution results

        Returns:
            List of evaluation results
        """
        results = []

        print(f"\nEvaluating {len(test_executions)} test executions...")
        print("=" * 70)

        for i, test_exec in enumerate(test_executions, 1):
            print(f"\n[{i}/{len(test_executions)}] Evaluating: {test_exec.test_name}")

            result = self.evaluate(test_exec)

            # Print quick summary
            status_symbol = "✓" if result.status.value == "pass" else "✗"
            print(f"  {status_symbol} Score: {result.overall_score:.2f} ({result.status.value.upper()})")

            if result.dimension_scores:
                lowest = min(result.dimension_scores, key=lambda d: d.score)
                print(f"  Lowest dimension: {lowest.dimension} = {lowest.score:.1f}/5.0")

            results.append(result)

        print("\n" + "=" * 70)
        passed = sum(1 for r in results if r.status.value == "pass")
        print(f"Results: {passed}/{len(results)} passed")

        return results

    def _create_error_result(self, test_execution: TestExecution) -> EvaluationResult:
        """Create an error result for failed test execution."""
        from .metrics import EvalStatus

        return EvaluationResult(
            test_id=test_execution.test_id,
            test_name=test_execution.test_name,
            status=EvalStatus.ERROR,
            overall_score=0.0,
            dimension_scores=[],
            turn_evaluations=[],
            pass_threshold=test_execution.context.get('pass_threshold', 0.7),
            feedback=f"Test execution failed: {test_execution.error}",
            improvement_suggestions=[],
            metadata={'error': test_execution.error}
        )


if __name__ == '__main__':
    # Example usage
    from ..runner.runner import TestExecution, TurnExecution
    from pathlib import Path

    # Mock test execution
    test_exec = TestExecution(
        test_id="test_001",
        test_name="Refund request - angry customer",
        turns=[
            TurnExecution(
                turn_number=1,
                customer_message="This is ridiculous! My product is broken!",
                agent_response="I completely understand how frustrating this must be. Let me help you right away.",
                duration_ms=1200,
                metadata={
                    'checkpoints': [
                        {
                            'criterion': 'empathy',
                            'check_type': 'must',
                            'description': 'Acknowledges frustration',
                            'weight': 0.5
                        },
                        {
                            'criterion': 'no_blame',
                            'check_type': 'must_not',
                            'description': 'Does not blame customer',
                            'weight': 0.5
                        }
                    ]
                }
            )
        ],
        total_duration_ms=1200,
        success=True,
        context={
            'evaluation_dimensions': {
                'empathy': 0.3,
                'resolution': 0.4,
                'efficiency': 0.3
            },
            'pass_threshold': 0.7,
            'customer_tier': 'gold',
            'scenario_type': 'angry_customer'
        }
    )

    # Evaluate
    evaluator = Evaluator(use_llm=False)  # Set to True to use LLM
    result = evaluator.evaluate(test_exec)

    print(result.feedback)
    print("\nSuggestions:")
    for suggestion in result.improvement_suggestions:
        print(f"  - {suggestion}")
