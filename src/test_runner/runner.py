"""Main test runner that orchestrates test execution and evaluation."""

import asyncio
import time
from pathlib import Path

import yaml
from openai import OpenAI
from ..test_generator.schemas import GeneratedTestSuite
from ..config import cfg, PASS_SCORE_THRESHOLD
from .evaluator import BehaviorEvaluator
from .executor import AgentExecutor
from .schemas import TestResult, TestResultList, TestRunReport


class TestRunner:
    """Run tests against an agent and generate a report."""

    def __init__(self, llm_client: OpenAI):
        self.llm_client = llm_client
        self.evaluator = BehaviorEvaluator(llm_client)
        self._external_tool_names = set()

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
        return asyncio.run(self._run_tests_async(test_suite_file, agent_dir))

    async def _run_tests_async(
        self, test_suite_file: Path | str, agent_dir: Path | str
    ) -> TestRunReport:
        """Async implementation of run_tests — single event loop for all tests."""
        # Load test suite
        test_suite = self._load_test_suite(test_suite_file)

        # Load external tool names for filtering
        agent_path = Path(agent_dir)
        entity_schema_path = agent_path / cfg.SCHEMA_FILE
        with open(entity_schema_path) as f:
            entity_data = yaml.safe_load(f)
        self._external_tool_names = {
            t["name"] for t in entity_data.get("external_tools", [])
        }

        # Initialize agent executor and load tools once
        external_tools = entity_data.get("external_tools", [])
        executor = AgentExecutor(agent_dir)
        await executor.setup_tools(external_tools=external_tools)

        start = time.monotonic()
        try:
            # Run each test
            results = []
            for test_case in test_suite.test_cases:
                result = await self._run_single_test(executor, test_case)
                results.append(result)
        finally:
            await executor.cleanup_tools()
        duration_seconds = time.monotonic() - start

        # Generate report
        return self._generate_report(test_suite.agent_name, results, duration_seconds)

    def _load_test_suite(self, test_suite_file: Path | str) -> GeneratedTestSuite:
        """Load test suite from YAML file."""
        test_suite_path = Path(test_suite_file)

        with open(test_suite_path) as f:
            data = yaml.safe_load(f)

        return GeneratedTestSuite.model_validate(data)

    async def _run_single_test(self, executor: AgentExecutor, test_case) -> TestResult:
        """Run a single test case and evaluate result."""
        expected_tool_calls = [
            t
            for t in (getattr(test_case, "expected_tool_calls", []) or [])
            if t in self._external_tool_names
        ]
        input_message = test_case.input.message
        input_context = test_case.input.context or {}
        backend_state = test_case.backend_state

        try:
            # Execute test and filter to external tools only
            output, raw_tool_calls = await executor.execute_test(test_case)
            actual_tool_calls = [
                t for t in raw_tool_calls if t in self._external_tool_names
            ]

            # Evaluate output
            score, reasoning = self.evaluator.evaluate(
                actual_output=output,
                expected_behavior=test_case.expected_behavior,
                expected_tool_calls=expected_tool_calls,
                actual_tool_calls=actual_tool_calls,
            )

            passed = score >= PASS_SCORE_THRESHOLD

            return TestResult(
                test_id=test_case.test_id,
                intent_name=test_case.intent_name,
                passed=passed,
                score=score,
                reasoning=reasoning,
                input_message=input_message,
                input_context=input_context,
                backend_state=backend_state,
                output=output,
                expected_tool_calls=expected_tool_calls,
                actual_tool_calls=actual_tool_calls,
            )

        except Exception as e:
            # Return failed result on error
            return TestResult(
                test_id=test_case.test_id,
                intent_name=test_case.intent_name,
                passed=False,
                score=1,
                reasoning=f"Error executing test: {str(e)}",
                input_message=input_message,
                input_context=input_context,
                backend_state=backend_state,
                output="",
                expected_tool_calls=expected_tool_calls,
                actual_tool_calls=[],
                error=True,
            )

    def _generate_report(
        self, agent_name: str, results: list[TestResult], duration_seconds: float
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
            duration_seconds=round(duration_seconds, 1),
            results=TestResultList(results=results),
        )
