"""Main test runner that orchestrates test execution and evaluation."""

from pathlib import Path
import yaml
from ..test_generator.schemas import GeneratedTestSuite
from .evaluator import BehaviorEvaluator
from .executor import AgentExecutor
from .schemas import TestResult, TestResultList, TestRunReport


class TestRunner:
    """Run tests against an agent and generate a report."""

    def __init__(self, llm_client=None):
        """
        Initialize test runner.

        Args:
            llm_client: OpenAI client for LLM evaluation
        """
        self.llm_client = llm_client
        self.evaluator = BehaviorEvaluator(llm_client)

    def run_tests(
        self, test_suite_file: Path | str, agent_dir: Path | str
    ) -> TestRunReport:
        """
        Run all tests in a test suite against an agent.

        Args:
            test_suite_file: Path to generated tests YAML file
            agent_dir: Path to agent directory

        Returns:
            TestRunReport with results
        """
        # Load test suite
        test_suite = self._load_test_suite(test_suite_file)

        # Initialize agent executor
        executor = AgentExecutor(agent_dir)

        # Run each test
        results = []
        for test_case in test_suite.test_cases:
            result = self._run_single_test(executor, test_case)
            results.append(result)

        # Generate report
        return self._generate_report(test_suite.agent_name, results)

    def _load_test_suite(self, test_suite_file: Path | str) -> GeneratedTestSuite:
        """Load test suite from YAML file."""
        test_suite_path = Path(test_suite_file)

        with open(test_suite_path) as f:
            data = yaml.safe_load(f)

        return GeneratedTestSuite.model_validate(data)

    def _run_single_test(self, executor: AgentExecutor, test_case) -> TestResult:
        """Run a single test case and evaluate result."""
        try:
            # Execute test
            output = executor.execute_test(test_case)

            # Evaluate output
            score, reasoning = self.evaluator.evaluate(
                actual_output=output,
                expected_behavior=test_case.expected_behavior,
            )

            # Determine pass/fail (7 or higher is passing)
            passed = score >= 7

            return TestResult(
                test_id=test_case.test_id,
                intent_name=test_case.intent_name,
                passed=passed,
                score=score,
                reasoning=reasoning,
                output=output,
            )

        except Exception as e:
            # Return failed result on error
            return TestResult(
                test_id=test_case.test_id,
                intent_name=test_case.intent_name,
                passed=False,
                score=1,
                reasoning=f"Error executing test: {str(e)}",
                output="",
            )

    def _generate_report(
        self, agent_name: str, results: list[TestResult]
    ) -> TestRunReport:
        """Generate test run report from results."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        pass_rate = passed / total if total > 0 else 0.0

        return TestRunReport(
            agent_name=agent_name,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            pass_rate=pass_rate,
            results=TestResultList(results=results),
        )
