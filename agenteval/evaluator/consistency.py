"""Consistency evaluator."""

import re
from typing import Optional

from agenteval.config import LLMConfig
from agenteval.evaluator.base import Evaluator, EvaluationResult


class ConsistencyEvaluator(Evaluator):
    """Evaluate consistency between two responses to similar questions.

    Checks if:
    1. Key facts are the same
    2. No contradictions exist
    3. Overall meaning is consistent
    """

    def __init__(self, llm_config: LLMConfig):
        """Initialize evaluator."""
        self.llm_config = llm_config

    @property
    def name(self) -> str:
        return "consistency"

    def evaluate(
        self,
        response1: str,
        response2: str,
        context: Optional[str] = None,
    ) -> EvaluationResult:
        """Evaluate consistency between two responses.

        Args:
            response1: First response (original).
            response2: Second response (should be consistent with first).
            context: Optional context about what the responses are about.

        Returns:
            EvaluationResult with consistency score.
        """
        details = {
            "key_facts_comparison": None,
            "contradiction_check": None,
            "semantic_similarity": None,
        }

        scores = []

        # Check 1: Key facts match
        facts1 = self._extract_key_facts(response1)
        facts2 = self._extract_key_facts(response2)

        common_facts = set(facts1) & set(facts2)
        total_facts = set(facts1) | set(facts2)

        if total_facts:
            fact_overlap = len(common_facts) / len(total_facts)
        else:
            fact_overlap = 1.0  # No facts to compare

        details["key_facts_comparison"] = {
            "response1_facts": list(facts1),
            "response2_facts": list(facts2),
            "common_facts": list(common_facts),
            "overlap_score": fact_overlap,
        }
        scores.append(min(1.0, fact_overlap * 1.5))  # Boost score, cap at 1.0

        # Check 2: Number consistency
        numbers1 = self._extract_numbers_with_context(response1)
        numbers2 = self._extract_numbers_with_context(response2)

        number_score = self._compare_numbers(numbers1, numbers2)
        if number_score is not None:
            details["number_consistency"] = {
                "response1_numbers": numbers1,
                "response2_numbers": numbers2,
                "score": number_score,
            }
            scores.append(number_score)

        # Check 3: Semantic similarity (LLM-based)
        llm_result = self._llm_consistency_check(response1, response2, context)
        details["semantic_similarity"] = llm_result
        scores.append(llm_result["score"])

        # Calculate final score
        final_score = sum(scores) / len(scores) if scores else 0.5

        # Check for contradictions (they override other scores)
        if llm_result.get("has_contradictions"):
            final_score = min(final_score, 0.3)

        return EvaluationResult(
            criterion=self.name,
            score=final_score,
            passed=final_score >= 0.7,
            details=details,
            feedback=llm_result.get("feedback"),
        )

    def _extract_key_facts(self, text: str) -> set[str]:
        """Extract key facts/statements from text."""
        facts = set()

        # Extract sentences with specific information
        sentences = re.split(r"[.!?]+", text)

        for sentence in sentences:
            sentence = sentence.strip().lower()
            if len(sentence) < 10:
                continue

            # Look for factual patterns
            # Numbers, percentages, dates
            if re.search(r"\d", sentence):
                # Normalize and extract the core fact
                normalized = re.sub(r"\s+", " ", sentence)
                facts.add(normalized)

            # Definitive statements
            if any(word in sentence for word in ["is ", "are ", "will ", "must ", "requires "]):
                normalized = re.sub(r"\s+", " ", sentence)
                facts.add(normalized)

        return facts

    def _extract_numbers_with_context(self, text: str) -> list[dict]:
        """Extract numbers with surrounding context."""
        results = []

        # Find numbers with context
        pattern = r"(\w+\s+)?(\d+(?:\.\d+)?)\s*(%|days?|hours?|minutes?|dollars?|\$|weeks?|months?|years?)?(?:\s+(\w+))?"
        matches = re.finditer(pattern, text, re.IGNORECASE)

        for match in matches:
            before = match.group(1) or ""
            number = match.group(2)
            unit = match.group(3) or ""
            after = match.group(4) or ""

            results.append({
                "number": number,
                "unit": unit.lower(),
                "context": f"{before}{number}{unit} {after}".strip().lower(),
            })

        return results

    def _compare_numbers(self, nums1: list[dict], nums2: list[dict]) -> Optional[float]:
        """Compare numbers between two responses."""
        if not nums1 and not nums2:
            return None  # No numbers to compare

        if not nums1 or not nums2:
            return 0.5  # One has numbers, one doesn't

        matching = 0
        total = max(len(nums1), len(nums2))

        for n1 in nums1:
            for n2 in nums2:
                # Same number with similar context
                if n1["number"] == n2["number"]:
                    if n1["unit"] == n2["unit"]:
                        matching += 1
                        break
                    elif not n1["unit"] and not n2["unit"]:
                        matching += 0.5
                        break

        return matching / total if total > 0 else 1.0

    def _llm_consistency_check(
        self,
        response1: str,
        response2: str,
        context: Optional[str],
    ) -> dict:
        """Use LLM to check semantic consistency."""
        prompt = f"""Compare these two responses for consistency. They should convey the same information.

RESPONSE 1:
{response1[:500]}

RESPONSE 2:
{response2[:500]}

{f"CONTEXT: Both responses are about {context}" if context else ""}

Check for:
1. Are the key facts the same?
2. Are there any contradictions?
3. Is the overall meaning consistent?

Return your evaluation in this exact format:
SCORE: [0.0-1.0] (1.0 = perfectly consistent, 0.0 = completely contradictory)
HAS_CONTRADICTIONS: [yes/no]
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
            contradiction_match = re.search(r"HAS_CONTRADICTIONS:\s*(yes|no)", output, re.IGNORECASE)
            feedback_match = re.search(r"FEEDBACK:\s*(.+)", output, re.DOTALL)

            score = float(score_match.group(1)) if score_match else 0.5
            score = max(0.0, min(1.0, score))

            has_contradictions = (
                contradiction_match.group(1).lower() == "yes"
                if contradiction_match
                else False
            )

            feedback = feedback_match.group(1).strip() if feedback_match else None

            return {
                "score": score,
                "has_contradictions": has_contradictions,
                "feedback": feedback,
                "raw": output,
            }

        except Exception as e:
            # Fallback to simple word overlap
            words1 = set(response1.lower().split())
            words2 = set(response2.lower().split())
            overlap = len(words1 & words2) / len(words1 | words2) if words1 | words2 else 0

            return {
                "score": overlap,
                "has_contradictions": False,
                "feedback": f"LLM evaluation failed, using word overlap: {e}",
                "raw": None,
            }

