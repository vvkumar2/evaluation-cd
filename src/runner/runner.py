"""
Test runner for executing agents against test cases.

Handles:
- Loading test cases from YAML
- Executing agents (subprocess, Python callable, HTTP)
- Managing multi-turn conversations
- Capturing outputs and timing
- Error handling and timeouts
"""

import yaml
import json
import time
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from enum import Enum


class AgentType(Enum):
    """Type of agent interface."""
    SUBPROCESS = "subprocess"  # Execute via command line
    PYTHON_CALLABLE = "python_callable"  # Python function
    HTTP = "http"  # HTTP API


@dataclass
class TurnExecution:
    """Results from executing a single conversation turn."""
    turn_number: int
    customer_message: str
    agent_response: str
    duration_ms: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestExecution:
    """Results from executing a complete test case."""
    test_id: str
    test_name: str
    turns: List[TurnExecution]
    total_duration_ms: float
    success: bool
    error: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


class AgentExecutor:
    """Execute an agent and get responses."""

    def __init__(
        self,
        agent_type: AgentType,
        agent_config: Dict[str, Any],
        timeout_seconds: int = 30
    ):
        """
        Initialize agent executor.

        Args:
            agent_type: Type of agent interface
            agent_config: Configuration for the agent
                For SUBPROCESS: {'command': 'python agent.py'}
                For PYTHON_CALLABLE: {'function': callable}
                For HTTP: {'url': 'http://...', 'method': 'POST'}
            timeout_seconds: Timeout for each agent call
        """
        self.agent_type = agent_type
        self.agent_config = agent_config
        self.timeout_seconds = timeout_seconds
        self.conversation_history: List[Dict[str, str]] = []

    def execute_turn(
        self,
        customer_message: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Execute a single conversation turn.

        Args:
            customer_message: The customer's message
            context: Context information (customer tier, order details, etc.)

        Returns:
            Agent's response

        Raises:
            TimeoutError: If agent takes too long
            Exception: If agent execution fails
        """
        # Add to conversation history
        self.conversation_history.append({
            'role': 'customer',
            'content': customer_message
        })

        # Execute based on agent type
        if self.agent_type == AgentType.SUBPROCESS:
            response = self._execute_subprocess(customer_message, context)
        elif self.agent_type == AgentType.PYTHON_CALLABLE:
            response = self._execute_callable(customer_message, context)
        elif self.agent_type == AgentType.HTTP:
            response = self._execute_http(customer_message, context)
        else:
            raise ValueError(f"Unsupported agent type: {self.agent_type}")

        # Add response to history
        self.conversation_history.append({
            'role': 'agent',
            'content': response
        })

        return response

    def reset(self):
        """Reset conversation history."""
        self.conversation_history = []

    def _execute_subprocess(
        self,
        customer_message: str,
        context: Dict[str, Any]
    ) -> str:
        """Execute agent via subprocess."""
        command = self.agent_config['command']

        # Prepare input as JSON
        agent_input = {
            'message': customer_message,
            'context': context,
            'history': self.conversation_history
        }
        input_json = json.dumps(agent_input)

        # Execute command
        try:
            result = subprocess.run(
                command.split(),
                input=input_json,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )

            if result.returncode != 0:
                raise Exception(f"Agent failed: {result.stderr}")

            # Parse response
            response = result.stdout.strip()

            # Try to parse as JSON if it looks like JSON
            if response.startswith('{'):
                try:
                    parsed = json.loads(response)
                    response = parsed.get('response', response)
                except json.JSONDecodeError:
                    pass

            return response

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Agent timed out after {self.timeout_seconds}s")

    def _execute_callable(
        self,
        customer_message: str,
        context: Dict[str, Any]
    ) -> str:
        """Execute agent via Python callable."""
        func = self.agent_config['function']

        agent_input = {
            'message': customer_message,
            'context': context,
            'history': self.conversation_history
        }

        try:
            response = func(agent_input)

            if isinstance(response, dict):
                response = response.get('response', str(response))

            return str(response)

        except Exception as e:
            raise Exception(f"Agent callable failed: {e}")

    def _execute_http(
        self,
        customer_message: str,
        context: Dict[str, Any]
    ) -> str:
        """Execute agent via HTTP API."""
        import requests

        url = self.agent_config['url']
        method = self.agent_config.get('method', 'POST')

        payload = {
            'message': customer_message,
            'context': context,
            'history': self.conversation_history
        }

        try:
            if method == 'POST':
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.timeout_seconds
                )
            else:
                response = requests.get(
                    url,
                    params=payload,
                    timeout=self.timeout_seconds
                )

            response.raise_for_status()

            data = response.json()
            return data.get('response', str(data))

        except requests.Timeout:
            raise TimeoutError(f"HTTP request timed out after {self.timeout_seconds}s")
        except Exception as e:
            raise Exception(f"HTTP request failed: {e}")


class TestRunner:
    """Run test cases against an agent."""

    def __init__(self, agent_executor: AgentExecutor):
        """
        Initialize test runner.

        Args:
            agent_executor: Configured agent executor
        """
        self.agent_executor = agent_executor

    def load_tests(self, test_file: Path) -> List[Dict[str, Any]]:
        """
        Load test cases from YAML file.

        Args:
            test_file: Path to YAML file with test cases

        Returns:
            List of test case dictionaries
        """
        with open(test_file, 'r') as f:
            data = yaml.safe_load(f)

        return data.get('test_cases', [])

    def run_test(self, test_case: Dict[str, Any]) -> TestExecution:
        """
        Run a single test case.

        Args:
            test_case: Test case definition

        Returns:
            TestExecution with results
        """
        test_id = test_case['id']
        test_name = test_case['name']
        conversation = test_case['conversation']
        context = conversation.get('context', {})

        # Reset agent state
        self.agent_executor.reset()

        turn_executions = []
        total_duration = 0
        success = True
        error = None

        try:
            # Execute each turn
            for i, turn in enumerate(conversation['turns'], 1):
                customer_message = turn['customer_message']

                # Execute turn
                start_time = time.time()

                try:
                    agent_response = self.agent_executor.execute_turn(
                        customer_message,
                        context
                    )
                    duration_ms = (time.time() - start_time) * 1000
                    turn_error = None

                except Exception as e:
                    agent_response = ""
                    duration_ms = (time.time() - start_time) * 1000
                    turn_error = str(e)
                    success = False

                # Record turn execution
                turn_exec = TurnExecution(
                    turn_number=i,
                    customer_message=customer_message,
                    agent_response=agent_response,
                    duration_ms=duration_ms,
                    error=turn_error,
                    metadata={
                        'checkpoints': turn.get('checkpoints', []),
                        'expected_actions': turn.get('agent_actions', [])
                    }
                )
                turn_executions.append(turn_exec)
                total_duration += duration_ms

                # Stop if turn failed
                if turn_error:
                    error = turn_error
                    break

        except Exception as e:
            success = False
            error = str(e)

        return TestExecution(
            test_id=test_id,
            test_name=test_name,
            turns=turn_executions,
            total_duration_ms=total_duration,
            success=success,
            error=error,
            context={
                'conversation_name': conversation.get('name'),
                'scenario_type': conversation.get('scenario_type'),
                'evaluation_dimensions': conversation.get('evaluation_dimensions', {}),
                'pass_threshold': test_case.get('pass_threshold', 0.7)
            }
        )

    def run_all(
        self,
        test_file: Path,
        max_tests: Optional[int] = None
    ) -> List[TestExecution]:
        """
        Run all test cases from a file.

        Args:
            test_file: Path to test file
            max_tests: Optional limit on number of tests to run

        Returns:
            List of test execution results
        """
        test_cases = self.load_tests(test_file)

        if max_tests:
            test_cases = test_cases[:max_tests]

        results = []

        print(f"Running {len(test_cases)} test cases...")
        print("=" * 70)

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] {test_case['name']}")

            result = self.run_test(test_case)

            # Print quick summary
            if result.success:
                print(f"  ✓ Completed in {result.total_duration_ms:.0f}ms")
            else:
                print(f"  ✗ Failed: {result.error}")

            results.append(result)

        print("\n" + "=" * 70)
        print(f"Completed: {sum(1 for r in results if r.success)}/{len(results)} successful")

        return results

    def save_results(
        self,
        results: List[TestExecution],
        output_file: Path
    ):
        """
        Save test execution results to JSON file.

        Args:
            results: Test execution results
            output_file: Output file path
        """
        output_data = {
            'metadata': {
                'timestamp': time.time(),
                'total_tests': len(results),
                'successful': sum(1 for r in results if r.success),
                'failed': sum(1 for r in results if not r.success)
            },
            'results': [
                {
                    'test_id': r.test_id,
                    'test_name': r.test_name,
                    'success': r.success,
                    'error': r.error,
                    'total_duration_ms': r.total_duration_ms,
                    'turns': [
                        {
                            'turn_number': t.turn_number,
                            'customer_message': t.customer_message,
                            'agent_response': t.agent_response,
                            'duration_ms': t.duration_ms,
                            'error': t.error,
                            'metadata': t.metadata
                        }
                        for t in r.turns
                    ],
                    'context': r.context
                }
                for r in results
            ]
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\nResults saved to: {output_file}")


if __name__ == '__main__':
    # Example usage
    from pathlib import Path

    # Simple echo agent for testing
    def echo_agent(input_data):
        message = input_data['message']
        return f"Echo: {message}"

    # Create executor
    executor = AgentExecutor(
        agent_type=AgentType.PYTHON_CALLABLE,
        agent_config={'function': echo_agent}
    )

    # Create runner
    runner = TestRunner(executor)

    # Run tests
    results = runner.run_all(Path('tests/generated_tests.yaml'))

    # Save results
    runner.save_results(results, Path('results/execution_results.json'))
