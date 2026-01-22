#!/usr/bin/env python3
"""
Test runner for evaluating customer service agents.

Loads generated test cases, runs them against an agent, and scores the output.
"""

import json
import sys
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any
import yaml
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')


class TestRunner:
    """Run test cases against an agent and score results."""

    def __init__(self, agent_script_path: Path, scoring_model: str = "gpt-4o-mini"):
        """
        Initialize test runner.

        Args:
            agent_script_path: Path to the agent script (e.g., agent.py)
            scoring_model: LLM model to use for scoring output (default: gpt-4o-mini)
        """
        self.agent_script_path = agent_script_path
        self.agent_dir = agent_script_path.parent
        self.scoring_model = scoring_model
        self.client = OpenAI(api_key=api_key)
        self.results = []
        self.test_data_file = self.agent_dir / "test_data.json"

    def run_tests(self, test_yaml_path: Path) -> List[Dict[str, Any]]:
        """
        Load test cases and run them against the agent.

        Args:
            test_yaml_path: Path to the YAML file with generated tests

        Returns:
            List of test results with scores
        """
        # Load tests from YAML
        with open(test_yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        tests = data.get('tests', [])

        print(f"Running {len(tests)} tests...")
        print("=" * 80)

        for i, test in enumerate(tests):
            result = self._run_single_test(test, i + 1)
            if result:
                self.results.append(result)

        return self.results

    def _run_single_test(self, test: Dict[str, Any], test_num: int) -> Dict[str, Any]:
        """
        Run a single test case against the agent.

        Args:
            test: Test case dict
            test_num: Test number for display

        Returns:
            Result dict with score and outputs
        """
        path_id = test.get('path_id', 'unknown')
        customer_message = test.get('customer_message', '')
        expected_outcome = test.get('expected_outcome', '')
        context = test.get('context', {})

        # Extract context
        customer = context.get('customer', {})
        orders = context.get('orders', [])
        customer_id = customer.get('customer_id', '')

        print(f"\n[Test {test_num}] {path_id}")
        print(f"Customer: {customer_id} ({customer.get('tier', 'unknown')})")
        if orders:
            print(f"Order: {orders[0].get('order_id')} - ${orders[0].get('price', 0):.2f}")

        # Write test data to file so agent can load it
        self._write_test_data(context)

        # Run agent
        agent_input = {
            "message": customer_message,
            "context": {"customer_id": customer_id},
            "history": []
        }

        try:
            actual_response = self._run_agent(agent_input)
        except Exception as e:
            print(f"ERROR running agent: {e}")
            return None
        finally:
            # Clean up test data file
            self._cleanup_test_data()

        # Score the output
        score = self._score_output(
            customer_message=customer_message,
            expected_outcome=expected_outcome,
            actual_response=actual_response
        )

        result = {
            'path_id': path_id,
            'capability': test.get('capability', 'unknown'),
            'customer_message': customer_message,
            'expected_outcome': expected_outcome,
            'actual_response': actual_response,
            'score': score,
            'context': context
        }

        print(f"Score: {score}/10")

        return result

    def _write_test_data(self, context: Dict[str, Any]):
        """
        Write test context to a JSON file that the agent will load.

        Args:
            context: Dict with customer and orders data
        """
        with open(self.test_data_file, 'w') as f:
            json.dump(context, f, indent=2)

    def _cleanup_test_data(self):
        """Remove the test data file after test completes."""
        if self.test_data_file.exists():
            self.test_data_file.unlink()

    def _run_agent(self, agent_input: Dict[str, Any]) -> str:
        """
        Run the agent with given input.

        Args:
            agent_input: Dict with message, context, history

        Returns:
            Agent's response as string
        """
        # Prepare input JSON
        input_json = json.dumps(agent_input)

        # Run agent script via subprocess from agent's directory
        # This ensures test_data.json is found in the agent's working directory
        result = subprocess.run(
            [sys.executable, self.agent_script_path.name],
            input=input_json,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(self.agent_dir)  # Run from agent's directory
        )

        if result.returncode != 0:
            raise Exception(f"Agent error: {result.stderr}")

        return result.stdout.strip()

    def _score_output(
        self,
        customer_message: str,
        expected_outcome: str,
        actual_response: str
    ) -> int:
        """
        Score the agent's response using an LLM.

        Args:
            customer_message: The customer's message
            expected_outcome: What the agent should do (business language)
            actual_response: What the agent actually responded with

        Returns:
            Score out of 10
        """
        prompt = f"""You are evaluating a customer service AI agent's response.

CUSTOMER MESSAGE:
{customer_message}

EXPECTED OUTCOME (what the agent should do):
{expected_outcome}

ACTUAL RESPONSE (what the agent said):
{actual_response}

TASK:
Rate the agent's response from 0-10 based on:
1. Does it match the expected outcome?
2. Is it helpful and professional?
3. Is the tone appropriate?
4. Does it address the customer's issue?

Return ONLY a single integer from 0-10 with no explanation.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.scoring_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert evaluator of customer service interactions. Rate responses on a scale of 0-10."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0
            )

            score_text = response.choices[0].message.content.strip()
            score = int(score_text)
            return min(max(score, 0), 10)  # Clamp to 0-10

        except Exception as e:
            print(f"Scoring error: {e}")
            return 5  # Default score on error

    def save_results(self, output_path: Path):
        """
        Save test results to a file.

        Args:
            output_path: Path to save results (JSON or YAML)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if str(output_path).endswith('.json'):
            with open(output_path, 'w') as f:
                json.dump(self.results, f, indent=2)
        else:
            with open(output_path, 'w') as f:
                yaml.dump(self.results, f, default_flow_style=False, sort_keys=False)

        print(f"\nResults saved to {output_path}")

    def print_summary(self):
        """Print summary statistics of test results."""
        if not self.results:
            print("No results to summarize.")
            return

        scores = [r.get('score', 0) for r in self.results]
        avg_score = sum(scores) / len(scores) if scores else 0
        passing = sum(1 for s in scores if s >= 7)
        failing = sum(1 for s in scores if s < 7)

        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Passing:  {passing}")
        print(f"Failing:  {failing}")
        print(f"Average score: {avg_score:.1f}/10")