"""LLM-based test generation."""

import json
import re
from typing import Optional

from agenteval.config import LLMConfig
from agenteval.models.knowledge import KnowledgeBase
from agenteval.models.test_case import TestCase, TestType, ExpectedResponse


class LLMGenerator:
    """Generate test cases using LLM."""

    def __init__(self, llm_config: LLMConfig):
        """Initialize with LLM configuration."""
        self.config = llm_config

    def generate(
        self,
        kb: KnowledgeBase,
        count: int,
        type_distribution: dict,
    ) -> list[TestCase]:
        """Generate test cases using LLM.

        Args:
            kb: Knowledge base to generate tests from.
            count: Number of tests to generate.
            type_distribution: Distribution of test types (qa, edge, consistency).

        Returns:
            List of generated test cases.
        """
        tests: list[TestCase] = []

        # Calculate counts for each type
        qa_count = int(count * type_distribution.get("qa", 0.7))
        edge_count = int(count * type_distribution.get("edge", 0.2))
        consistency_count = count - qa_count - edge_count

        # Generate Q&A tests
        if qa_count > 0:
            qa_tests = self._generate_qa_tests(kb, qa_count)
            tests.extend(qa_tests)

        # Generate edge case tests
        if edge_count > 0:
            edge_tests = self._generate_edge_tests(kb, edge_count)
            tests.extend(edge_tests)

        # Generate consistency tests from Q&A tests
        if consistency_count > 0 and tests:
            consistency_tests = self._generate_consistency_tests(tests[:5], consistency_count)
            tests.extend(consistency_tests)

        return tests

    def _generate_qa_tests(self, kb: KnowledgeBase, count: int) -> list[TestCase]:
        """Generate Q&A test cases."""
        # Prepare context from knowledge base
        context = self._prepare_kb_context(kb, max_tokens=3000)

        prompt = f"""You are a test case generator for conversational AI agents. 
Based on the following knowledge base content, generate {count} question-answer test cases.

KNOWLEDGE BASE:
{context}

Generate test cases in the following JSON format:
{{
    "tests": [
        {{
            "question": "The question a user might ask",
            "key_facts": ["fact1 that should be in the answer", "fact2 that should be in the answer"],
            "source_doc": "the document path this relates to"
        }}
    ]
}}

Requirements:
- Questions should be natural and varied (don't start all with "What is")
- Key facts should be specific, verifiable statements from the knowledge base
- Include 2-5 key facts per question
- Cover different topics from the knowledge base
- Make questions realistic for a customer service scenario

Return ONLY the JSON, no other text."""

        response = self._call_llm(prompt)
        tests = self._parse_qa_response(response, start_id=len([]))

        return tests

    def _generate_edge_tests(self, kb: KnowledgeBase, count: int) -> list[TestCase]:
        """Generate edge case test cases."""
        # Get topics from KB to generate relevant out-of-scope questions
        topics = self._extract_topics(kb)

        prompt = f"""Generate {count} edge case test questions for a customer service AI agent.

The agent's knowledge base covers these topics: {', '.join(topics[:10])}

Generate edge cases in these categories:
1. Out-of-scope questions (topics the agent shouldn't handle)
2. Ambiguous questions (need clarification)
3. Questions about things that don't exist

Return JSON format:
{{
    "tests": [
        {{
            "question": "The edge case question",
            "category": "out_of_scope|ambiguous|non_existent",
            "should_decline": true or false,
            "expected_behavior": "what the agent should do"
        }}
    ]
}}

Return ONLY the JSON, no other text."""

        response = self._call_llm(prompt)
        tests = self._parse_edge_response(response)

        return tests

    def _generate_consistency_tests(
        self,
        base_tests: list[TestCase],
        count: int,
    ) -> list[TestCase]:
        """Generate consistency test pairs."""
        tests: list[TestCase] = []

        for i, base_test in enumerate(base_tests[:count]):
            if base_test.type != TestType.QA:
                continue

            prompt = f"""Rephrase this question in a different way while keeping the same meaning:

Original: "{base_test.message}"

Requirements:
- Use different words and structure
- Keep the same intent/meaning
- Make it sound natural
- Don't just add "please" or change punctuation

Return ONLY the rephrased question, nothing else."""

            response = self._call_llm(prompt)
            rephrased = response.strip().strip('"')

            if rephrased and rephrased != base_test.message:
                tests.append(TestCase(
                    id=f"llm_cons_{i:03d}",
                    type=TestType.CONSISTENCY,
                    message=rephrased,
                    expected=ExpectedResponse(
                        consistency_with=base_test.id,
                        contains_facts=base_test.expected.contains_facts,
                    ),
                    category="consistency",
                    metadata={
                        "original_id": base_test.id,
                        "original_message": base_test.message,
                        "generator": "llm_consistency",
                    },
                ))

        return tests

    def _prepare_kb_context(self, kb: KnowledgeBase, max_tokens: int = 3000) -> str:
        """Prepare knowledge base content for LLM context."""
        context_parts = []
        current_length = 0
        approx_chars_per_token = 4

        for doc in kb.documents:
            doc_text = f"\n--- {doc.path} ---\n"
            if doc.title:
                doc_text += f"# {doc.title}\n"
            doc_text += doc.content[:2000]  # Limit per document

            if current_length + len(doc_text) / approx_chars_per_token > max_tokens:
                break

            context_parts.append(doc_text)
            current_length += len(doc_text) / approx_chars_per_token

        return "\n".join(context_parts)

    def _extract_topics(self, kb: KnowledgeBase) -> list[str]:
        """Extract main topics from knowledge base."""
        topics = []

        for doc in kb.documents:
            # Use document title or filename
            if doc.title:
                topics.append(doc.title)
            else:
                topics.append(doc.filename.replace("-", " ").replace("_", " "))

            # Extract section headers
            headers = re.findall(r"^##\s+(.+)$", doc.content, re.MULTILINE)
            topics.extend(headers[:3])  # First 3 headers per doc

        return list(set(topics))

    def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt."""
        try:
            import litellm

            response = litellm.completion(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )

            return response.choices[0].message.content or ""

        except ImportError:
            # Fallback if litellm not available
            return self._mock_llm_response(prompt)
        except Exception as e:
            print(f"Warning: LLM call failed: {e}")
            return self._mock_llm_response(prompt)

    def _mock_llm_response(self, prompt: str) -> str:
        """Provide mock response when LLM is not available."""
        # Return empty JSON for testing without LLM
        if "edge case" in prompt.lower():
            return '{"tests": []}'
        elif "rephrase" in prompt.lower():
            return ""
        else:
            return '{"tests": []}'

    def _parse_qa_response(self, response: str, start_id: int = 0) -> list[TestCase]:
        """Parse LLM response into Q&A test cases."""
        tests = []

        try:
            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return tests

            data = json.loads(json_match.group())
            test_data = data.get("tests", [])

            for i, item in enumerate(test_data):
                question = item.get("question", "")
                key_facts = item.get("key_facts", [])
                source = item.get("source_doc", "")

                if not question:
                    continue

                tests.append(TestCase(
                    id=f"llm_qa_{start_id + i:03d}",
                    type=TestType.QA,
                    message=question,
                    expected=ExpectedResponse(
                        contains_facts=key_facts,
                        sources=[source] if source else [],
                    ),
                    category="qa",
                    metadata={"generator": "llm"},
                ))

        except json.JSONDecodeError:
            pass

        return tests

    def _parse_edge_response(self, response: str) -> list[TestCase]:
        """Parse LLM response into edge case test cases."""
        tests = []

        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return tests

            data = json.loads(json_match.group())
            test_data = data.get("tests", [])

            for i, item in enumerate(test_data):
                question = item.get("question", "")
                category = item.get("category", "out_of_scope")
                should_decline = item.get("should_decline", True)
                expected_behavior = item.get("expected_behavior", "")

                if not question:
                    continue

                tests.append(TestCase(
                    id=f"llm_edge_{i:03d}",
                    type=TestType.EDGE_CASE,
                    message=question,
                    expected=ExpectedResponse(
                        should_decline=should_decline,
                        should_suggest=expected_behavior if not should_decline else None,
                    ),
                    category=category,
                    metadata={"generator": "llm_edge"},
                ))

        except json.JSONDecodeError:
            pass

        return tests

