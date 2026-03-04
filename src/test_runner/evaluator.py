"""Evaluate agent behavior against expected outcomes using LLM."""

import json

from openai import OpenAI
from pydantic import BaseModel, Field
from ..config import EVALUATION_MODEL


class EvaluationResult(BaseModel):
    score: int = Field(ge=1, le=10, description="Score from 1-10")
    reasoning: str = Field(description="Explanation for the score")


BEHAVIOR_EVALUATION_PROMPT = """You are evaluating whether an agent's response matches the expected behavior.

## Customer Input
{input_message}

## Backend State (ground truth data for this test)
{backend_state}

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

## Important
- Use the backend state to verify factual correctness of the agent's response
- If the expected behavior is generic (e.g., "return the calculated cost") but the agent's response is factually correct given the backend state, score it favorably

## Task
Score this response on how well it addresses the expected behavior

Return a JSON object:
{{
  "score": <integer 1-10>,
  "reasoning": "Explanation of why you gave this score"
}}
"""


class BehaviorEvaluator:
    """Evaluate if agent output matches expected behavior using LLM."""

    def __init__(self, llm_client: OpenAI):
        self.client = llm_client

    def evaluate(
        self,
        actual_output: str,
        expected_behavior: str,
        expected_tool_calls: list[str] | None = None,
        actual_tool_calls: list[str] | None = None,
        input_message: str = "",
        backend_state: dict | None = None,
    ) -> tuple[int, str]:
        """Score agent output against expected behavior. Returns (score, reasoning)."""
        prompt = BEHAVIOR_EVALUATION_PROMPT.format(
            input_message=input_message or "not provided",
            backend_state=(
                json.dumps(backend_state, indent=2, default=str)
                if backend_state
                else "not provided"
            ),
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

        response = self.client.responses.parse(
            model=EVALUATION_MODEL,
            input=[{"role": "user", "content": prompt}],
            text_format=EvaluationResult,
            temperature=0,
        )
        result = response.output_parsed
        return result.score, result.reasoning
