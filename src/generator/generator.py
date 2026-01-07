"""
Test case generator that converts extracted business logic into test cases.

Uses templates + optional LLM assistance to create realistic test scenarios.
"""

import yaml
import json
from dataclasses import asdict
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..analyzer.extractor import ExtractedLogic, BusinessPolicy, TestableScenario
from ..analyzer.scorer import ScoredScenario, TestPriorityScorer
from .templates import (
    TemplateLibrary,
    ConversationTemplate,
    TestCaseTemplate,
    TurnTemplate,
    CheckpointTemplate
)


class TestCaseGenerator:
    """Generate test cases from extracted business logic."""

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize generator.

        Args:
            llm_client: Optional LLM client for enriching test cases
        """
        self.llm_client = llm_client
        self.template_library = TemplateLibrary()
        self.scorer = TestPriorityScorer()

    def generate(
        self,
        logic: ExtractedLogic,
        max_tests: int = 20,
        use_llm: bool = False
    ) -> List[TestCaseTemplate]:
        """
        Generate test cases from extracted logic.

        Args:
            logic: Extracted business logic
            max_tests: Maximum number of test cases to generate
            use_llm: Whether to use LLM to enrich test cases

        Returns:
            List of generated test cases
        """
        # Score and prioritize scenarios
        scored_scenarios = self.scorer.score_scenarios(logic)
        top_scenarios = self.scorer.top_n(scored_scenarios, max_tests)

        test_cases = []

        for scored in top_scenarios:
            scenario = scored.scenario

            # Generate test case based on scenario type
            if scenario.scenario_type == 'error_path':
                test_case = self._generate_error_path_test(scenario, logic)
            elif scenario.scenario_type == 'edge_case':
                test_case = self._generate_edge_case_test(scenario, logic)
            else:  # happy_path
                test_case = self._generate_happy_path_test(scenario, logic)

            if use_llm and self.llm_client:
                test_case = self._enrich_with_llm(test_case, scenario, logic)

            test_cases.append(test_case)

        return test_cases

    def _generate_happy_path_test(
        self,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> TestCaseTemplate:
        """Generate a happy path test case."""

        # Try to match scenario to a template
        if 'refund' in scenario.name.lower():
            conversation = self._generate_refund_conversation(scenario, logic)
            category = 'refunds'

        elif 'order' in scenario.name.lower():
            conversation = self._generate_order_conversation(scenario, logic)
            category = 'orders'

        else:
            # Generic happy path
            conversation = self._generate_generic_conversation(scenario, logic)
            category = 'general'

        return TestCaseTemplate(
            id=f"test_{scenario.name}",
            name=scenario.name,
            category=category,
            conversation=conversation,
            expected_outcome=scenario.expected_behavior or "Successful resolution",
            pass_threshold=0.7
        )

    def _generate_error_path_test(
        self,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> TestCaseTemplate:
        """Generate an error path test case."""

        # Find related policy violations
        policy_name = "general_policy"
        violation_reason = "request violates policy"

        for policy in logic.policies:
            if any(p in scenario.name for p in scenario.related_policies):
                policy_name = policy.name
                violation_reason = policy.description
                break

        conversation = self.template_library.policy_violation_template(
            policy_name=policy_name,
            violation_reason=violation_reason,
            customer_request=f"Can you help me with {scenario.description}?"
        )

        return TestCaseTemplate(
            id=f"test_{scenario.name}",
            name=scenario.name,
            category='policy_enforcement',
            conversation=conversation,
            expected_outcome="Policy correctly enforced",
            pass_threshold=0.8  # Higher threshold for policy compliance
        )

    def _generate_edge_case_test(
        self,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> TestCaseTemplate:
        """Generate an edge case test."""

        conversation = self.template_library.edge_case_template(
            edge_case_type=scenario.name,
            description=scenario.description,
            customer_message=self._generate_edge_case_message(scenario)
        )

        return TestCaseTemplate(
            id=f"test_{scenario.name}",
            name=scenario.name,
            category='edge_cases',
            conversation=conversation,
            expected_outcome="Handled gracefully without errors",
            pass_threshold=0.6  # Lower threshold for edge cases
        )

    def _generate_refund_conversation(
        self,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> ConversationTemplate:
        """Generate a refund-specific conversation."""

        # Extract refund-related parameters from policies
        refund_window_days = 30  # default
        max_refund_amount = 200.0  # default

        for policy in logic.policies:
            if 'refund' in policy.name.lower():
                if 'day' in policy.description.lower():
                    # Try to extract number of days
                    import re
                    match = re.search(r'(\d+)\s*day', policy.description, re.IGNORECASE)
                    if match:
                        refund_window_days = int(match.group(1))

                if 'limit' in policy.name.lower() or 'max' in policy.name.lower():
                    if 'value' in policy.parameters:
                        max_refund_amount = policy.parameters['value']

        # Determine customer tier from scenario context
        customer_tier = scenario.inputs.get('customer_tier', 'standard')

        return self.template_library.refund_request_template(
            item_name="product",
            price=99.99,
            days_since_delivery=5,
            customer_tier=customer_tier
        )

    def _generate_order_conversation(
        self,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> ConversationTemplate:
        """Generate an order-related conversation."""

        # For now, use a generic template
        # In the future, this could be more sophisticated
        return ConversationTemplate(
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type,
            context=scenario.inputs,
            turns=[
                TurnTemplate(
                    customer_message="I have a question about my order.",
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="helpful_response",
                            check_type="must",
                            description="Provides helpful information about orders",
                            weight=1.0
                        )
                    ]
                )
            ],
            evaluation_dimensions={
                "helpfulness": 0.5,
                "accuracy": 0.5
            }
        )

    def _generate_generic_conversation(
        self,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> ConversationTemplate:
        """Generate a generic conversation for scenarios that don't match templates."""

        return ConversationTemplate(
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type,
            context=scenario.inputs,
            turns=[
                TurnTemplate(
                    customer_message=f"Can you help me with {scenario.description}?",
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="addresses_request",
                            check_type="must",
                            description="Addresses the customer's request",
                            weight=0.6
                        ),
                        CheckpointTemplate(
                            criterion="professional",
                            check_type="must",
                            description="Maintains professional tone",
                            weight=0.4
                        )
                    ]
                )
            ],
            evaluation_dimensions={
                "helpfulness": 0.6,
                "professionalism": 0.4
            }
        )

    def _generate_edge_case_message(self, scenario: TestableScenario) -> str:
        """Generate a realistic edge case customer message."""

        edge_case_messages = {
            'empty_input': "",
            'very_long': "I " + "really " * 50 + "need help with this issue.",
            'special_chars': "My order #@!$%^ isn't working!!!",
            'non_english': "你好，我需要帮助",
            'ambiguous': "help",
            'contradictory': "I want a refund but don't send it back",
        }

        # Try to match scenario to a known edge case type
        for case_type, message in edge_case_messages.items():
            if case_type in scenario.name.lower():
                return message

        return scenario.description

    def _enrich_with_llm(
        self,
        test_case: TestCaseTemplate,
        scenario: TestableScenario,
        logic: ExtractedLogic
    ) -> TestCaseTemplate:
        """Use LLM to make the test case more realistic and varied."""

        if not self.llm_client:
            return test_case

        prompt = f"""
You are helping create realistic customer service test scenarios.

Given this test scenario:
- Name: {scenario.name}
- Type: {scenario.scenario_type}
- Description: {scenario.description}

Current conversation template has {len(test_case.conversation.turns)} turns.

Make the customer messages more realistic and varied. Consider:
1. Different communication styles (formal, casual, frustrated)
2. Realistic details (order numbers, product names, dates)
3. Natural conversation flow

Return JSON with improved customer messages for each turn.

Format:
{{
  "turns": [
    {{"customer_message": "improved message 1"}},
    {{"customer_message": "improved message 2"}},
    ...
  ]
}}
"""

        try:
            response = self.llm_client.complete(prompt)
            improved = json.loads(response)

            # Update customer messages
            for i, turn_data in enumerate(improved.get('turns', [])):
                if i < len(test_case.conversation.turns):
                    test_case.conversation.turns[i].customer_message = turn_data.get(
                        'customer_message',
                        test_case.conversation.turns[i].customer_message
                    )

        except Exception as e:
            print(f"Warning: LLM enrichment failed: {e}")

        return test_case

    def save_to_yaml(
        self,
        test_cases: List[TestCaseTemplate],
        output_path: Path
    ):
        """
        Save generated test cases to YAML file.

        Args:
            test_cases: Test cases to save
            output_path: Output file path
        """
        # Convert test cases to dict format
        test_suite = {
            'metadata': {
                'generator': 'AgentEval',
                'version': '1.0',
                'total_tests': len(test_cases)
            },
            'test_cases': []
        }

        for test_case in test_cases:
            tc_dict = {
                'id': test_case.id,
                'name': test_case.name,
                'category': test_case.category,
                'expected_outcome': test_case.expected_outcome,
                'pass_threshold': test_case.pass_threshold,
                'conversation': self._conversation_to_dict(test_case.conversation)
            }
            test_suite['test_cases'].append(tc_dict)

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            yaml.dump(test_suite, f, default_flow_style=False, sort_keys=False)

        print(f"Generated {len(test_cases)} test cases -> {output_path}")

    def _conversation_to_dict(self, conversation: ConversationTemplate) -> Dict:
        """Convert conversation template to dictionary."""
        return {
            'name': conversation.name,
            'description': conversation.description,
            'scenario_type': conversation.scenario_type,
            'context': conversation.context,
            'turns': [
                {
                    'customer_message': turn.customer_message,
                    'checkpoints': [
                        {
                            'criterion': cp.criterion,
                            'check_type': cp.check_type,
                            'description': cp.description,
                            'weight': cp.weight
                        }
                        for cp in turn.checkpoints
                    ],
                    'agent_actions': turn.agent_actions
                }
                for turn in conversation.turns
            ],
            'evaluation_dimensions': conversation.evaluation_dimensions
        }


if __name__ == '__main__':
    # Example usage
    from ..analyzer.parser import CodeParser
    from ..analyzer.extractor import BusinessLogicExtractor
    from pathlib import Path

    # Parse codebase
    parser = CodeParser()
    extractor = BusinessLogicExtractor()
    generator = TestCaseGenerator()

    # Extract logic
    analyses = parser.parse_directory(Path('./example_codebase'))
    logic = extractor.extract(analyses)

    # Generate test cases
    test_cases = generator.generate(logic, max_tests=10)

    # Save to file
    generator.save_to_yaml(test_cases, Path('./tests/generated_tests.yaml'))

    print(f"\nGenerated {len(test_cases)} test cases")
    for tc in test_cases[:3]:
        print(f"  - {tc.name} ({tc.category})")
