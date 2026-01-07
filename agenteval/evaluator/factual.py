"""Factual accuracy evaluator using LLM and knowledge base."""

import re
from typing import Optional

from agenteval.config import LLMConfig
from agenteval.evaluator.base import Evaluator, EvaluationResult
from agenteval.knowledge.indexer import KnowledgeIndexer
from agenteval.models.knowledge import KnowledgeBase
from agenteval.models.test_case import ExpectedResponse


class FactualAccuracyEvaluator(Evaluator):
    """Evaluate factual accuracy of agent responses.

    Uses a combination of:
    1. Exact matching for expected facts
    2. LLM-as-judge for semantic evaluation
    3. Knowledge base retrieval for grounding
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        kb: Optional[KnowledgeBase] = None,
        indexer: Optional[KnowledgeIndexer] = None,
    ):
        """Initialize evaluator.

        Args:
            llm_config: LLM configuration for semantic evaluation.
            kb: Optional knowledge base for grounding.
            indexer: Optional knowledge indexer for retrieval.
        """
        self.llm_config = llm_config
        self.kb = kb
        self.indexer = indexer

    @property
    def name(self) -> str:
        return "factual_accuracy"

    def evaluate(
        self,
        question: str,
        response: str,
        expected: ExpectedResponse,
    ) -> EvaluationResult:
        """Evaluate factual accuracy of a response.

        Args:
            question: The original question.
            response: The agent's response.
            expected: Expected response criteria.

        Returns:
            EvaluationResult with factual accuracy score.
        """
        details = {
            "fact_checks": [],
            "llm_evaluation": None,
            "retrieved_context": None,
        }

        # Step 1: Check expected facts (exact/fuzzy matching)
        fact_scores = []
        for fact in expected.contains_facts:
            found, match_type = self._check_fact(fact, response)
            fact_scores.append({
                "fact": fact,
                "found": found,
                "match_type": match_type,
            })

        details["fact_checks"] = fact_scores

        # Calculate fact-based score
        if fact_scores:
            fact_score = sum(1 for f in fact_scores if f["found"]) / len(fact_scores)
        else:
            fact_score = 1.0  # No facts to check

        # Step 2: Retrieve relevant context from KB
        kb_context = ""
        if self.indexer:
            results = self.indexer.search(question, k=3)
            if results:
                kb_context = "\n".join(r["content"] for r in results)
                details["retrieved_context"] = [
                    {"content": r["content"][:200], "score": r["score"]}
                    for r in results
                ]

        # Step 3: LLM evaluation for semantic accuracy
        llm_score = 1.0
        llm_feedback = None

        if kb_context or expected.contains_facts:
            llm_result = self._llm_evaluate(question, response, kb_context, expected)
            llm_score = llm_result["score"]
            llm_feedback = llm_result["feedback"]
            details["llm_evaluation"] = llm_result

        # Combine scores (weighted average)
        if fact_scores:
            final_score = 0.6 * fact_score + 0.4 * llm_score
        else:
            final_score = llm_score

        return EvaluationResult(
            criterion=self.name,
            score=final_score,
            passed=final_score >= 0.7,
            details=details,
            feedback=llm_feedback,
        )

    def _check_fact(self, fact: str, response: str) -> tuple[bool, str]:
        """Check if a fact is present in the response.

        Returns:
            Tuple of (found, match_type).
        """
        # Normalize for comparison
        fact_lower = fact.lower()
        response_lower = response.lower()

        # Exact match
        if fact_lower in response_lower:
            return True, "exact"

        # Fuzzy match - check if key terms are present
        key_terms = self._extract_key_terms(fact)
        if key_terms:
            matching_terms = sum(1 for term in key_terms if term in response_lower)
            if matching_terms / len(key_terms) >= 0.7:
                return True, "fuzzy"

        # Number matching - extract and compare numbers
        fact_numbers = re.findall(r"\d+", fact)
        response_numbers = re.findall(r"\d+", response)
        if fact_numbers:
            if any(n in response_numbers for n in fact_numbers):
                # Check surrounding context
                for num in fact_numbers:
                    if num in response:
                        return True, "number_match"

        return False, "not_found"

    def _extract_key_terms(self, text: str) -> list[str]:
        """Extract key terms from text for fuzzy matching."""
        # Remove common words
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during", "before",
            "after", "above", "below", "up", "down", "out", "off", "over",
            "under", "again", "further", "then", "once", "and", "but",
            "or", "nor", "so", "yet", "both", "either", "neither", "not",
            "only", "own", "same", "than", "too", "very",
        }

        words = re.findall(r"\b\w+\b", text.lower())
        key_terms = [w for w in words if w not in stopwords and len(w) > 2]

        return key_terms

    def _llm_evaluate(
        self,
        question: str,
        response: str,
        context: str,
        expected: ExpectedResponse,
    ) -> dict:
        """Use LLM to evaluate semantic accuracy."""
        expected_facts = "\n".join(f"- {f}" for f in expected.contains_facts)

        prompt = f"""Evaluate if this customer service response is factually accurate.

QUESTION: {question}

RESPONSE: {response}

KNOWLEDGE BASE CONTEXT:
{context[:1500] if context else "Not available"}

EXPECTED FACTS (should be included):
{expected_facts if expected_facts else "Not specified"}

Evaluate the response on a scale of 0.0 to 1.0:
- 1.0: Completely accurate, all facts correct, no hallucinations
- 0.8: Mostly accurate with minor omissions
- 0.6: Partially accurate, some facts missing or slightly wrong
- 0.4: Significant inaccuracies or missing critical information
- 0.2: Mostly inaccurate or hallucinated
- 0.0: Completely wrong or harmful misinformation

Return your evaluation in this exact format:
SCORE: [0.0-1.0]
FEEDBACK: [One sentence explanation]"""

        try:
            import litellm

            result = litellm.completion(
                model=self.llm_config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
                api_key=self.llm_config.api_key,
                base_url=self.llm_config.base_url,
            )

            output = result.choices[0].message.content or ""

            # Parse response
            score_match = re.search(r"SCORE:\s*([\d.]+)", output)
            feedback_match = re.search(r"FEEDBACK:\s*(.+)", output, re.DOTALL)

            score = float(score_match.group(1)) if score_match else 0.5
            score = max(0.0, min(1.0, score))  # Clamp to [0, 1]

            feedback = feedback_match.group(1).strip() if feedback_match else None

            return {"score": score, "feedback": feedback, "raw": output}

        except Exception as e:
            # Fallback to simple heuristic
            return {
                "score": 0.5,
                "feedback": f"LLM evaluation failed: {e}",
                "raw": None,
            }

