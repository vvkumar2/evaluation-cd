"""Completeness evaluator."""

import re

from agenteval.config import LLMConfig
from agenteval.evaluator.base import Evaluator, EvaluationResult
from agenteval.models.test_case import ExpectedResponse


class CompletenessEvaluator(Evaluator):
    """Evaluate completeness of agent responses.

    Checks if the response:
    1. Addresses all parts of the question
    2. Includes all expected facts
    3. Provides sufficient detail
    """

    def __init__(self, llm_config: LLMConfig):
        """Initialize evaluator."""
        self.llm_config = llm_config

    @property
    def name(self) -> str:
        return "completeness"

    def evaluate(
        self,
        question: str,
        response: str,
        expected: ExpectedResponse,
    ) -> EvaluationResult:
        """Evaluate completeness of a response."""
        details = {
            "length_check": None,
            "fact_coverage": None,
            "question_parts_addressed": None,
        }

        scores = []

        # Check 1: Response length (not too short)
        word_count = len(response.split())
        if word_count < 10:
            length_score = 0.2
            length_feedback = "Response is too short"
        elif word_count < 20:
            length_score = 0.5
            length_feedback = "Response could be more detailed"
        elif word_count < 50:
            length_score = 0.8
            length_feedback = "Response has adequate length"
        else:
            length_score = 1.0
            length_feedback = "Response is sufficiently detailed"

        details["length_check"] = {
            "word_count": word_count,
            "score": length_score,
            "feedback": length_feedback,
        }
        scores.append(length_score)

        # Check 2: Expected facts coverage
        if expected.contains_facts:
            facts_found = 0
            for fact in expected.contains_facts:
                if self._fact_present(fact, response):
                    facts_found += 1

            fact_coverage = facts_found / len(expected.contains_facts)
            details["fact_coverage"] = {
                "expected": len(expected.contains_facts),
                "found": facts_found,
                "score": fact_coverage,
            }
            scores.append(fact_coverage)

        # Check 3: Question parts addressed
        question_parts = self._extract_question_parts(question)
        if question_parts:
            addressed = 0
            for part in question_parts:
                if self._part_addressed(part, response):
                    addressed += 1

            parts_score = addressed / len(question_parts)
            details["question_parts_addressed"] = {
                "parts": question_parts,
                "addressed": addressed,
                "score": parts_score,
            }
            scores.append(parts_score)

        # Calculate final score
        final_score = sum(scores) / len(scores) if scores else 0.5

        # Generate feedback
        feedback = self._generate_feedback(details, final_score)

        return EvaluationResult(
            criterion=self.name,
            score=final_score,
            passed=final_score >= 0.6,
            details=details,
            feedback=feedback,
        )

    def _fact_present(self, fact: str, response: str) -> bool:
        """Check if a fact is present in the response."""
        fact_lower = fact.lower()
        response_lower = response.lower()

        # Direct match
        if fact_lower in response_lower:
            return True

        # Key terms match
        key_terms = re.findall(r"\b\w{4,}\b", fact_lower)
        if key_terms:
            matching = sum(1 for term in key_terms if term in response_lower)
            return matching / len(key_terms) >= 0.6

        return False

    def _extract_question_parts(self, question: str) -> list[str]:
        """Extract individual parts/aspects of a question."""
        parts = []

        # Check for compound questions (and, also, as well as)
        if " and " in question.lower():
            # Split by "and" but be careful with common phrases
            parts = re.split(r"\s+and\s+", question, flags=re.IGNORECASE)

        # Check for multiple question marks
        elif question.count("?") > 1:
            parts = [p.strip() + "?" for p in question.split("?") if p.strip()]

        # Check for numbered/bulleted items
        elif re.search(r"(?:\d+\.|[-*])\s+", question):
            parts = re.split(r"(?:\d+\.|[-*])\s+", question)
            parts = [p.strip() for p in parts if p.strip()]

        # Single question
        else:
            parts = [question]

        return parts

    def _part_addressed(self, part: str, response: str) -> bool:
        """Check if a question part is addressed in the response."""
        # Extract key terms from the question part
        key_terms = re.findall(r"\b\w{4,}\b", part.lower())

        if not key_terms:
            return True  # No meaningful terms to check

        response_lower = response.lower()
        matching = sum(1 for term in key_terms if term in response_lower)

        return matching / len(key_terms) >= 0.5

    def _generate_feedback(self, details: dict, score: float) -> str:
        """Generate human-readable feedback."""
        issues = []

        length_check = details.get("length_check", {})
        if length_check.get("score", 1) < 0.7:
            issues.append(length_check.get("feedback", "Response too short"))

        fact_coverage = details.get("fact_coverage", {})
        if fact_coverage and fact_coverage.get("score", 1) < 0.7:
            missing = fact_coverage["expected"] - fact_coverage["found"]
            issues.append(f"Missing {missing} expected fact(s)")

        parts_check = details.get("question_parts_addressed", {})
        if parts_check and parts_check.get("score", 1) < 0.7:
            total = len(parts_check.get("parts", []))
            addressed = parts_check.get("addressed", 0)
            issues.append(f"Only addressed {addressed}/{total} parts of the question")

        if not issues:
            return "Response is complete and addresses all aspects"

        return "; ".join(issues)

