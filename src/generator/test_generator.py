"""
Generates realistic single-turn customer service test cases based on parsed agent capabilities.
"""

import json
import os
from typing import List, Dict, Any
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('OPENAI_API_KEY')

class TestGenerator:
    """Generate test cases from parsed agent capabilities using LLM."""

    def __init__(self, model: str = "gpt-5-mini"):
        self.model = model
        self.client = OpenAI(api_key=api_key)

    def generate_from_file(self, parsed_json_path: Path) -> List[Dict[str, Any]]:
        """
        Generate tests from a parsed capabilities JSON file.
        """
        with open(parsed_json_path, 'r') as f:
            data = json.load(f)

        return self.generate_from_dict(data)

    def generate_from_dict(self, capabilities: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate tests from parsed capabilities dictionary.
        """
        tests = []
        agent_description = capabilities.get('description', '')
        constants = capabilities.get('constants', {})
        workflows = capabilities.get('workflows', [])

        for workflow in workflows:
            capability_name = workflow['capability_name']
            capability_description = workflow['description']
            paths = workflow.get('paths', [])

            for path in paths:
                test = self._generate_test_for_path(
                    agent_description=agent_description,
                    capability_name=capability_name,
                    capability_description=capability_description,
                    path=path,
                    constants=constants
                )
                if test:
                    tests.append(test)

        return tests

    def _generate_test_for_path(
        self,
        agent_description: str,
        capability_name: str,
        capability_description: str,
        path: Dict[str, Any],
        constants: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a single test case for a specific execution path.
        """
        prompt = self._build_prompt(
            agent_description=agent_description,
            capability_name=capability_name,
            capability_description=capability_description,
            path=path,
            constants=constants
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a test case generator for customer service AI agents. Generate realistic, natural customer messages and expected agent responses. Focus on actual business scenarios a customer would experience. Do not reference technical implementation details, error codes, or impossible situations. Always create scenarios that could realistically happen."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            customer_msg = result.get('customer_message', '').strip()
            expected_outcome = result.get('expected_outcome', '').strip()
            if customer_msg == "SKIP" or expected_outcome == "SKIP":
                return None

            return {
                'path_id': path['path_id'],
                'capability': capability_name,
                'customer_message': customer_msg,
                'expected_outcome': expected_outcome,
                'is_error_case': path.get('is_error_path', False)
            }

        except Exception as e:
            print(f"Error generating test for {path['path_id']}: {e}")
            return None

    def _build_prompt(
        self,
        agent_description: str,
        capability_name: str,
        capability_description: str,
        path: Dict[str, Any],
        constants: Dict[str, Any]
    ) -> str:
        """
        Build the LLM prompt for test generation.
        """
        conditions_str = "\n".join([f"  - {c}" for c in path.get('conditions', [])])
        constants_str = "\n".join([f"  - {k}: {v}" for k, v in constants.items()])

        # Determine expected behavior
        if path.get('is_error_path'):
            expected_behavior = f"Should raise error: {path.get('raises', 'Unknown error')}"
        elif path.get('return_value'):
            expected_behavior = f"Should return: {path['return_value']}"
        else:
            expected_behavior = "Should complete successfully"

        prompt = f"""Generate a realistic test case for this agent behavior path.

                    ## AGENT
                    {agent_description}

                    ## CAPABILITY
                    **Name:** {capability_name}
                    **Description:** {capability_description}

                    ## PATH {path['path_id']}
                    **Triggers:** {conditions_str if conditions_str else 'Default behavior'}
                    **Expected behavior:** {expected_behavior}
                    {f"**Constants:** {constants_str}" if constants_str else ""}

                    ## TASK
                    * Create a single-turn test case with a realistic customer message that would naturally trigger this path.
                    * If this scenario does not make practical sense in a real-life situation return SKIP.
                    * The expected_outcome should be stated in BUSINESS LANGUAGE describing what the agent should do.

                    **Output JSON:**
                    {{
                    "customer_message": "...",
                    "expected_outcome": "..."
                    }}

                    Or if you cannot create a realistic scenario:
                    {{
                    "customer_message": "SKIP",
                    "expected_outcome": "SKIP"
                    }}
                """
        return prompt

    def save_tests(self, tests: List[Dict[str, Any]], output_path: Path):
        """
        Save generated tests to a YAML file.
        """
        import yaml

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump({'tests': tests}, f, default_flow_style=False, sort_keys=False)

        print(f"Saved {len(tests)} tests to {output_path}")
