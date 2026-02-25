"""Generate test cases from extracted agent specifications using LLM."""

import json
import logging
from ..context_extractor.schemas.prompt_schema import StructuredSystemPromptExtraction
from ..context_extractor.schemas.entity_schema import EntitySchemaList
from .schemas import GeneratedTestCase, GeneratedTestSuite, TestInput
from .prompts import TEST_CASE_GENERATION_PROMPT

logger = logging.getLogger(__name__)


class TestCaseGenerator:
    """Generate runnable test cases from extracted intents using LLM."""

    def __init__(self, llm_client=None):
        """
        Initialize generator.

        Args:
            llm_client: OpenAI client for LLM calls
        """
        self.client = llm_client

    def generate_test_suite(
        self,
        agent_name: str,
        extraction: StructuredSystemPromptExtraction,
        entities: EntitySchemaList,
        external_tools: list[dict] | None = None,
    ) -> GeneratedTestSuite:
        """Generate complete test suite from extracted specifications."""
        if not self.client:
            raise RuntimeError("LLM client not initialized")

        test_cases = []

        for intent in extraction.intents:
            for rule in intent.rules:
                test_case = self._generate_test_case_with_llm(
                    intent_name=intent.name,
                    intent_description=intent.description,
                    rule=rule,
                    entities=entities,
                )
                if test_case:
                    test_cases.append(test_case)

        # Generate tool failure variants for each external tool
        if external_tools:
            failure_tests = self._generate_tool_failure_tests(
                test_cases, external_tools
            )
            test_cases.extend(failure_tests)

        return GeneratedTestSuite(agent_name=agent_name, test_cases=test_cases)

    def _generate_test_case_with_llm(
        self,
        intent_name: str,
        intent_description: str,
        rule,
        entities: EntitySchemaList,
    ) -> GeneratedTestCase:
        """Generate a single test case using LLM."""
        # Format conditions for LLM
        conditions_text = self._format_conditions(rule.conditions)

        # Format entity schema for LLM
        entities_schema_text = self._format_entities_schema(entities)

        # Build prompt
        prompt = TEST_CASE_GENERATION_PROMPT.format(
            intent_name=intent_name,
            intent_description=intent_description,
            rule_description=rule.description,
            conditions=conditions_text,
            expected_behavior=rule.expected_behavior,
            expected_tool_calls=(
                ", ".join(rule.expected_tool_calls)
                if rule.expected_tool_calls
                else "none specified"
            ),
            entities_schema=entities_schema_text,
        )

        # Call LLM
        response = self._call_llm(prompt)

        # Parse response
        test_case_dict = self._parse_test_case_response(response)

        # Validate and fix backend state
        backend_state, valid = self._validate_and_fix_backend_state(
            test_case_dict["backend_state"], entities
        )

        if not valid:
            return None

        # Convert to GeneratedTestCase
        return GeneratedTestCase(
            test_id=test_case_dict["test_id"],
            intent_name=intent_name,
            description=test_case_dict.get("description", rule.description),
            rule_conditions=[c.model_dump() for c in rule.conditions],
            backend_state=backend_state,
            input=TestInput(**test_case_dict["input"]),
            expected_behavior=rule.expected_behavior,
            expected_tool_calls=rule.expected_tool_calls,
            category=test_case_dict.get("category", "happy_path"),
        )

    def _format_conditions(self, conditions) -> str:
        """Format structured conditions for LLM."""
        lines = []
        for condition in conditions:
            line = f"- {condition.field} {condition.operator} {condition.value}"
            lines.append(line)
        return "\n".join(lines)

    def _format_entities_schema(self, entities: EntitySchemaList) -> str:
        """Format entity schema for LLM."""
        lines = []
        for entity in entities.entities:
            lines.append(f"- {entity.name}: {entity.description}")

            if entity.fields:
                for field in entity.fields:
                    enum_str = f" (enum: {field.enum})" if field.enum else ""
                    lines.append(
                        f"    - {field.name} ({field.type}): {field.description}{enum_str}"
                    )

        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        """Call LLM and extract JSON from response."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content

        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        return content

    def _parse_test_case_response(self, response: str) -> dict:
        """Parse LLM response into test case dict."""
        try:
            data = json.loads(response)
            return data
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse test case response: {e}\n{response}"
            ) from e

    def _validate_and_fix_backend_state(
        self,
        backend_state: dict[str, list[dict]],
        entities: EntitySchemaList,
    ) -> tuple[dict[str, list[dict]], bool]:
        """Normalize keys, fill missing fields, and verify conditions are satisfied.

        Returns:
            Tuple of (fixed_backend_state, is_valid).
        """
        # Build key mapping: entity name "order" -> backend key "orders"
        # Accept both "order" and "orders" as input keys
        entity_by_key = {}
        backend_key_for = {}
        for e in entities.entities:
            plural = e.name + "s"
            entity_by_key[e.name] = e
            entity_by_key[plural] = e
            backend_key_for[e.name] = plural
            backend_key_for[plural] = plural

        # Normalize keys to plural form
        fixed_state = {}
        for key, instances in backend_state.items():
            if key not in entity_by_key:
                logger.warning(
                    "backend_state key '%s' does not match any entity",
                    key,
                )
                return fixed_state, False
            fixed_state[backend_key_for[key]] = instances

        # Fill missing fields with defaults
        for key, instances in fixed_state.items():
            entity = entity_by_key.get(key)
            if not entity or not entity.fields:
                logger.warning(
                    "no entity or fields for key '%s'",
                    key,
                )
                return fixed_state, False
            for instance in instances:
                for field in entity.fields:
                    if (
                        field.name not in instance
                        and hasattr(field, "default")
                        and field.default is not None
                    ):
                        instance[field.name] = field.default

        # TODO: We need a better way to verify rule conditions are satisfied
        # for condition in conditions:
        # ...

        return fixed_state, True

    @staticmethod
    def _check_condition(actual, operator: str, expected) -> bool:
        """Check if a single value satisfies a condition operator."""
        if actual is None:
            return operator == "missing"

        ops = {
            "eq": lambda a, e: a == e,
            "ne": lambda a, e: a != e,
            "lt": lambda a, e: a < e,
            "lte": lambda a, e: a <= e,
            "gt": lambda a, e: a > e,
            "gte": lambda a, e: a >= e,
            "in": lambda a, e: a in e if isinstance(e, list) else a == e,
            "not_in": lambda a, e: a not in e if isinstance(e, list) else a != e,
            "exists": lambda a, e: a is not None,
            "missing": lambda a, e: a is None,
        }
        check = ops.get(operator)
        if not check:
            return True
        try:
            return check(actual, expected)
        except (TypeError, ValueError):
            return False

    def _generate_tool_failure_tests(
        self,
        test_cases: list[GeneratedTestCase],
        external_tools: list[dict],
    ) -> list[GeneratedTestCase]:
        """Generate tool failure variants by duplicating existing tests.

        For each external tool, finds the first test that expects to call it,
        duplicates it with mock_tool_responses set to return an error, and
        adjusts the expected behavior.
        """
        failure_tests = []

        for tool_def in external_tools:
            tool_name = tool_def["name"]

            # Find first test that expects this tool
            source_test = None
            for tc in test_cases:
                if tool_name in (tc.expected_tool_calls or []):
                    source_test = tc
                    break

            if not source_test:
                continue

            # Duplicate with error override
            failure_test = source_test.model_copy(
                update={
                    "test_id": f"{source_test.test_id}_{tool_name}_failure",
                    "description": (
                        f"Validates agent handles {tool_name} failure gracefully. "
                        f"Based on: {source_test.description}"
                    ),
                    "category": "error_handling",
                    "expected_behavior": (
                        f"The agent should still process the primary action but handle "
                        f"the {tool_name} failure gracefully — informing the customer "
                        f"that the notification or side-effect could not be completed."
                    ),
                    "mock_tool_responses": {
                        tool_name: {
                            "response": f"{tool_name} service unavailable",
                            "is_error": True,
                        }
                    },
                }
            )
            failure_tests.append(failure_test)

        return failure_tests
