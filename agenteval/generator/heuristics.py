"""Heuristic-based test generation from knowledge base patterns."""

import re
from typing import Optional

from agenteval.config import Config
from agenteval.models.knowledge import Document, KnowledgeBase
from agenteval.models.test_case import TestCase, TestType, ExpectedResponse


class HeuristicGenerator:
    """Generate test cases using heuristic pattern detection."""

    def generate(self, kb: KnowledgeBase, config: Config) -> list[TestCase]:
        """Generate test cases from knowledge base patterns.

        Detects:
        - FAQ-style content (Q: A: patterns)
        - Policy documents (headers with explanatory content)
        - Lists of facts/features
        - Procedure/how-to sections
        """
        tests: list[TestCase] = []
        test_id = 1

        for doc in kb.documents:
            # Extract FAQ patterns
            faq_tests = self._extract_faq_patterns(doc, test_id)
            tests.extend(faq_tests)
            test_id += len(faq_tests)

            # Extract from section headers
            section_tests = self._extract_section_tests(doc, test_id)
            tests.extend(section_tests)
            test_id += len(section_tests)

            # Extract from bullet points/lists
            list_tests = self._extract_list_tests(doc, test_id)
            tests.extend(list_tests)
            test_id += len(list_tests)

        # Generate edge case tests
        edge_tests = self._generate_edge_cases(kb, test_id)
        tests.extend(edge_tests)
        test_id += len(edge_tests)

        # Generate consistency test pairs
        consistency_tests = self._generate_consistency_tests(tests, test_id)
        tests.extend(consistency_tests)

        return tests

    def _extract_faq_patterns(self, doc: Document, start_id: int) -> list[TestCase]:
        """Extract FAQ-style Q&A patterns."""
        tests = []
        content = doc.content

        # Pattern 1: Q: ... A: ...
        qa_pattern = r"Q:\s*(.+?)\s*A:\s*(.+?)(?=Q:|$)"
        matches = re.findall(qa_pattern, content, re.DOTALL | re.IGNORECASE)

        for i, (question, answer) in enumerate(matches):
            question = question.strip()
            answer = answer.strip()

            if len(question) < 10 or len(answer) < 20:
                continue

            # Extract key facts from answer
            facts = self._extract_key_facts(answer)

            tests.append(TestCase(
                id=f"heur_{start_id + len(tests):03d}",
                type=TestType.QA,
                message=question,
                expected=ExpectedResponse(
                    contains_facts=facts[:5],  # Top 5 facts
                    sources=[str(doc.path)],
                ),
                category="faq",
                metadata={"source": str(doc.path), "generator": "heuristic_faq"},
            ))

        # Pattern 2: ### Question heading followed by answer
        heading_qa_pattern = r"###\s*(.+?)\n\n(.+?)(?=###|##|$)"
        matches = re.findall(heading_qa_pattern, content, re.DOTALL)

        for question, answer in matches:
            question = question.strip()
            answer = answer.strip()

            # Check if heading looks like a question
            if not any(q in question.lower() for q in ["how", "what", "when", "where", "why", "can", "do", "is", "?"]):
                continue

            if len(question) < 5 or len(answer) < 20:
                continue

            facts = self._extract_key_facts(answer)

            tests.append(TestCase(
                id=f"heur_{start_id + len(tests):03d}",
                type=TestType.QA,
                message=question if question.endswith("?") else question + "?",
                expected=ExpectedResponse(
                    contains_facts=facts[:5],
                    sources=[str(doc.path)],
                ),
                category="faq_heading",
                metadata={"source": str(doc.path), "generator": "heuristic_heading"},
            ))

        return tests

    def _extract_section_tests(self, doc: Document, start_id: int) -> list[TestCase]:
        """Generate tests from document sections."""
        tests = []
        content = doc.content

        # Find ## sections (main topic sections)
        section_pattern = r"##\s*(.+?)\n\n(.+?)(?=##|$)"
        matches = re.findall(section_pattern, content, re.DOTALL)

        for title, section_content in matches:
            title = title.strip()
            section_content = section_content.strip()

            if len(section_content) < 50:
                continue

            # Generate a natural question from the section title
            question = self._title_to_question(title)
            if not question:
                continue

            facts = self._extract_key_facts(section_content)

            tests.append(TestCase(
                id=f"heur_{start_id + len(tests):03d}",
                type=TestType.QA,
                message=question,
                expected=ExpectedResponse(
                    contains_facts=facts[:5],
                    sources=[str(doc.path)],
                ),
                category="section",
                metadata={"source": str(doc.path), "section": title, "generator": "heuristic_section"},
            ))

        return tests

    def _extract_list_tests(self, doc: Document, start_id: int) -> list[TestCase]:
        """Generate tests from bullet point lists."""
        tests = []
        content = doc.content

        # Find sections with bullet lists
        # Pattern: heading followed by bullet points
        list_pattern = r"##\s*(.+?)\n\n((?:[-*]\s+.+\n?)+)"
        matches = re.findall(list_pattern, content, re.DOTALL)

        for title, list_content in matches:
            title = title.strip()

            # Extract list items
            items = re.findall(r"[-*]\s+(.+)", list_content)
            if len(items) < 2:
                continue

            # Generate question about the list
            question = f"What are the {title.lower()}?"
            if "feature" in title.lower():
                question = f"What features do you offer?"
            elif "benefit" in title.lower():
                question = f"What are the benefits?"
            elif "step" in title.lower():
                question = f"What are the steps for {title.lower().replace('steps', '').strip()}?"

            tests.append(TestCase(
                id=f"heur_{start_id + len(tests):03d}",
                type=TestType.QA,
                message=question,
                expected=ExpectedResponse(
                    contains_facts=items[:5],  # First 5 items
                    sources=[str(doc.path)],
                ),
                category="list",
                metadata={"source": str(doc.path), "section": title, "generator": "heuristic_list"},
            ))

        return tests

    def _generate_edge_cases(self, kb: KnowledgeBase, start_id: int) -> list[TestCase]:
        """Generate edge case tests."""
        tests = []

        # Out-of-scope questions
        out_of_scope = [
            "Can you help me with my taxes?",
            "What's the weather like today?",
            "Can you book a flight for me?",
            "What's your opinion on politics?",
        ]

        for i, question in enumerate(out_of_scope):
            tests.append(TestCase(
                id=f"edge_{start_id + i:03d}",
                type=TestType.EDGE_CASE,
                message=question,
                expected=ExpectedResponse(
                    should_decline=True,
                    should_suggest="redirect to appropriate resource",
                    tone="polite",
                ),
                category="out_of_scope",
                metadata={"generator": "heuristic_edge"},
            ))

        # Non-existent info (generate based on KB content to make realistic)
        non_existent = [
            "What's your policy on teleportation?",
            "Do you offer time travel services?",
            "Can I pay with cryptocurrency from the future?",
        ]

        for i, question in enumerate(non_existent, start=len(out_of_scope)):
            tests.append(TestCase(
                id=f"edge_{start_id + i:03d}",
                type=TestType.EDGE_CASE,
                message=question,
                expected=ExpectedResponse(
                    should_decline=True,
                    tone="helpful",
                ),
                category="non_existent",
                metadata={"generator": "heuristic_edge"},
            ))

        return tests

    def _generate_consistency_tests(self, qa_tests: list[TestCase], start_id: int) -> list[TestCase]:
        """Generate consistency test pairs from existing Q&A tests."""
        tests = []
        consistency_id = 0

        # Take first few Q&A tests and create rephrased versions
        qa_only = [t for t in qa_tests if t.type == TestType.QA][:5]

        for original in qa_only:
            rephrased = self._rephrase_question(original.message)
            if rephrased and rephrased != original.message:
                tests.append(TestCase(
                    id=f"cons_{start_id + consistency_id:03d}",
                    type=TestType.CONSISTENCY,
                    message=rephrased,
                    expected=ExpectedResponse(
                        consistency_with=original.id,
                        contains_facts=original.expected.contains_facts,
                    ),
                    category="consistency",
                    metadata={
                        "original_id": original.id,
                        "original_message": original.message,
                        "generator": "heuristic_consistency",
                    },
                ))
                consistency_id += 1

        return tests

    def _extract_key_facts(self, text: str) -> list[str]:
        """Extract key facts from text."""
        facts = []

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            sentence = sentence.strip()

            # Skip very short or very long sentences
            if len(sentence) < 20 or len(sentence) > 200:
                continue

            # Skip sentences that are questions
            if sentence.endswith("?"):
                continue

            # Look for sentences with specific patterns
            # Numbers, percentages, dates, specific terms
            has_specifics = bool(re.search(
                r"\d+|%|days?|hours?|minutes?|dollars?|\$|\bfree\b|\bincluded\b|\brequired\b",
                sentence,
                re.IGNORECASE,
            ))

            if has_specifics:
                facts.append(sentence)
            elif len(facts) < 3:
                # Include some general sentences if we don't have many facts
                facts.append(sentence)

        return facts[:10]  # Return max 10 facts

    def _title_to_question(self, title: str) -> Optional[str]:
        """Convert a section title to a natural question."""
        title_lower = title.lower()

        # Already a question
        if title.endswith("?"):
            return title

        # Common patterns
        if "return" in title_lower and "policy" in title_lower:
            return "What is your return policy?"
        if "shipping" in title_lower:
            return "How does shipping work?"
        if "warranty" in title_lower:
            return "What warranty do you offer?"
        if "contact" in title_lower:
            return "How can I contact you?"
        if "payment" in title_lower:
            return "What payment methods do you accept?"
        if "hour" in title_lower or "time" in title_lower:
            return "What are your business hours?"
        if "faq" in title_lower:
            return None  # Skip FAQ headers themselves
        if "about" in title_lower:
            return f"Tell me about {title.replace('About', '').strip()}"

        # Generic fallback
        return f"What is {title}?"

    def _rephrase_question(self, question: str) -> Optional[str]:
        """Generate a rephrased version of a question."""
        question_lower = question.lower()

        # Simple rephrasing rules
        if question_lower.startswith("what is "):
            remaining = question[8:]
            return f"Can you tell me about {remaining}"

        if question_lower.startswith("how do "):
            remaining = question[7:]
            return f"What's the process for {remaining.rstrip('?')}?"

        if question_lower.startswith("what are "):
            remaining = question[9:]
            return f"Tell me about {remaining}"

        if "policy" in question_lower:
            if "return" in question_lower:
                return "How do returns work?"
            if "shipping" in question_lower:
                return "How is shipping handled?"

        # Can't rephrase
        return None

