"""Evaluate agent behavior against expected outcomes using LLM."""

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    score: int = Field(ge=1, le=10, description="Score from 1-10")
    reasoning: str = Field(description="Explanation for the score")


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

        result = self._call_llm(prompt)
        return result.score, result.reasoning

    def _call_llm(self, prompt: str) -> EvaluationResult:
        """Call LLM with structured output parsing."""
        response = self.client.responses.parse(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": prompt}],
            text_format=EvaluationResult,
            temperature=0,
        )
        return response.output_parsed
