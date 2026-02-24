"""Evaluate agent behavior against expected outcomes using LLM."""

import json

BEHAVIOR_EVALUATION_PROMPT = """You are evaluating whether an agent's response matches the expected behavior.

## Expected Behavior
{expected_behavior}

## Actual Output from Agent
{actual_output}

## Expected Tool Calls
{expected_tool_calls}

## Actual Tool Calls
{actual_tool_calls}

## Scoring Guide
- 10: Perfect - exactly matches expected behavior and called correct tools
- 8-9: Very Good - meets core requirements with minor deviations acceptable
- 7: Good - addresses the main need, reasonable approach
- 4-6: Needs Work - missing key aspects or wrong approach
- 1-3: Poor - fundamentally doesn't address the expected behavior

## Task
Score this response on how well it addresses the expected behavior.

Return a JSON object:
{{
  "score": <integer 1-10>,
  "reasoning": "Explanation of why you gave this score"
}}
"""


class BehaviorEvaluator:
    """Evaluate if agent output matches expected behavior using LLM."""

    def __init__(self, llm_client=None):
        """
        Initialize evaluator.

        Args:
            llm_client: OpenAI client for LLM calls
        """
        self.client = llm_client

    def evaluate(
        self,
        actual_output: str,
        expected_behavior: str,
        expected_tool_calls: list[str] = None,
        actual_tool_calls: list[str] = None,
    ) -> tuple[int, str]:
        """
        Score agent output based on expected behavior and tool calls.

        Args:
            actual_output: The agent's actual response
            expected_behavior: What the agent should have done
            expected_tool_calls: Tool names the agent should have called
            actual_tool_calls: Tool names the agent actually called

        Returns:
            Tuple of (score, reasoning) where score is 1-10
        """
        if not self.client:
            raise RuntimeError("LLM client not initialized")

        prompt = BEHAVIOR_EVALUATION_PROMPT.format(
            expected_behavior=expected_behavior,
            actual_output=actual_output,
            expected_tool_calls=(
                ", ".join(expected_tool_calls)
                if expected_tool_calls
                else "none specified"
            ),
            actual_tool_calls=(
                ", ".join(actual_tool_calls) if actual_tool_calls else "none"
            ),
        )

        response = self._call_llm(prompt)
        score, reasoning = self._parse_evaluation_response(response)

        return score, reasoning

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

    def _parse_evaluation_response(self, response: str) -> tuple[int, str]:
        """Parse LLM evaluation response."""
        try:
            data = json.loads(response)
            score = int(data.get("score", 5))
            reasoning = data.get("reasoning", "No reasoning provided")
            # Clamp score to 1-10
            score = max(1, min(10, score))
            return score, reasoning
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(
                f"Failed to parse evaluation response: {e}\n{response}"
            ) from e
