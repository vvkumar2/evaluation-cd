"""
LLM-as-Judge evaluator for subjective quality assessment.

Uses an LLM (OpenAI or Anthropic) to evaluate conversation quality
across multiple dimensions using detailed rubrics.
"""

import json
import os
from typing import List, Dict, Any, Optional
from .metrics import DimensionScore


class LLMJudge:
    """Use an LLM to judge conversation quality."""

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize LLM judge.

        Args:
            provider: "openai" or "anthropic"
            model: Model name (defaults to gpt-4o-mini or claude-3-5-sonnet)
            api_key: API key (or use environment variable)
        """
        self.provider = provider.lower()

        if self.provider == "openai":
            import openai
            self.client = openai.OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
            self.model = model or "gpt-4o-mini"

        elif self.provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key or os.getenv('ANTHROPIC_API_KEY'))
            self.model = model or "claude-3-5-sonnet-20241022"

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def evaluate_conversation(
        self,
        customer_messages: List[str],
        agent_responses: List[str],
        context: Dict[str, Any],
        dimensions: Dict[str, float]
    ) -> List[DimensionScore]:
        """
        Evaluate a complete conversation across multiple dimensions.

        Args:
            customer_messages: List of customer messages
            agent_responses: List of agent responses
            context: Conversation context (customer tier, complaint type, etc.)
            dimensions: Dimensions to evaluate (name -> weight)

        Returns:
            List of DimensionScores
        """
        # Format conversation for LLM
        conversation_text = self._format_conversation(
            customer_messages,
            agent_responses
        )

        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            conversation_text,
            context,
            dimensions
        )

        # Call LLM
        try:
            response = self._call_llm(prompt)
            scores = self._parse_llm_response(response, dimensions)
            return scores

        except Exception as e:
            print(f"Warning: LLM evaluation failed: {e}")
            # Return default scores
            return [
                DimensionScore(
                    dimension=dim,
                    score=3.0,  # Neutral score
                    weight=weight,
                    reasoning=f"LLM evaluation failed: {e}"
                )
                for dim, weight in dimensions.items()
            ]

    def _format_conversation(
        self,
        customer_messages: List[str],
        agent_responses: List[str]
    ) -> str:
        """Format conversation as readable text."""
        lines = []

        for i, (customer, agent) in enumerate(zip(customer_messages, agent_responses), 1):
            lines.append(f"Turn {i}:")
            lines.append(f"CUSTOMER: {customer}")
            lines.append(f"AGENT: {agent}")
            lines.append("")

        return "\n".join(lines)

    def _build_evaluation_prompt(
        self,
        conversation_text: str,
        context: Dict[str, Any],
        dimensions: Dict[str, float]
    ) -> str:
        """Build the evaluation prompt for the LLM."""

        # Standard rubrics for each dimension
        rubrics = {
            'empathy': """
EMPATHY (1-5):
5 = Explicitly acknowledges customer emotions, validates feelings, shows genuine understanding
3 = Polite and acknowledges the issue, but generic/formulaic
1 = Ignores emotions, dismissive, or tone-deaf
            """,
            'resolution': """
RESOLUTION (1-5):
5 = Problem fully resolved with clear confirmation and next steps
3 = Problem partially addressed or unclear if fully resolved
1 = Problem not addressed or made worse
            """,
            'policy_compliance': """
POLICY COMPLIANCE (1-5):
5 = All policies followed correctly, no violations
3 = Minor policy misses or unclear adherence
1 = Clear policy violations or incorrect application
            """,
            'efficiency': """
EFFICIENCY (1-5):
5 = Resolved quickly without rushing, no unnecessary steps
3 = Some redundant questions or could be more streamlined
1 = Very inefficient, excessive back-and-forth
            """,
            'de_escalation': """
DE-ESCALATION (1-5):
5 = Successfully calmed angry customer, tension decreased noticeably
3 = Maintained professional tone but didn't reduce tension
1 = Customer remained angry or situation escalated
            """,
            'professionalism': """
PROFESSIONALISM (1-5):
5 = Consistently professional, appropriate tone, no errors
3 = Generally professional with minor lapses
1 = Unprofessional language, tone, or behavior
            """,
            'helpfulness': """
HELPFULNESS (1-5):
5 = Went above and beyond, anticipated needs, proactive
3 = Answered questions adequately but no extra effort
1 = Unhelpful, vague, or failed to provide needed information
            """
        }

        # Build rubric section for requested dimensions
        rubric_text = "\n".join([
            rubrics.get(dim, f"{dim.upper()} (1-5): Score this dimension appropriately")
            for dim in dimensions.keys()
        ])

        # Context summary
        context_text = f"""
CONTEXT:
- Customer Tier: {context.get('customer_tier', 'standard')}
- Scenario: {context.get('scenario_type', 'general')}
- Emotional State: {context.get('emotional_state', 'neutral')}
        """.strip()

        prompt = f"""You are evaluating a customer service conversation.

{context_text}

CONVERSATION:
{conversation_text}

EVALUATE THE AGENT ON THE FOLLOWING DIMENSIONS:

{rubric_text}

For each dimension, provide:
1. A score from 1-5
2. Brief reasoning (1-2 sentences)

IMPORTANT: Be honest and critical. A score of 3 means "acceptable but could improve."
Reserve 5 for truly excellent performance. Don't inflate scores.

Respond in JSON format:
{{
  "dimensions": [
    {{
      "dimension": "empathy",
      "score": 4.0,
      "reasoning": "Clear acknowledgment of frustration with specific validation"
    }},
    ...
  ],
  "overall_assessment": "Brief 1-2 sentence summary"
}}
"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API."""

        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert customer service evaluator. Provide honest, critical assessments."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for more consistent scoring
            )
            return response.choices[0].message.content

        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.content[0].text

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _parse_llm_response(
        self,
        response: str,
        dimensions: Dict[str, float]
    ) -> List[DimensionScore]:
        """Parse LLM JSON response into DimensionScore objects."""

        try:
            # Parse JSON
            data = json.loads(response)

            dimension_scores = []

            for dim_data in data.get('dimensions', []):
                dim_name = dim_data['dimension']
                score = float(dim_data['score'])
                reasoning = dim_data['reasoning']

                # Get weight from requested dimensions
                weight = dimensions.get(dim_name, 0.0)

                dimension_scores.append(DimensionScore(
                    dimension=dim_name,
                    score=score,
                    weight=weight,
                    reasoning=reasoning
                ))

            return dimension_scores

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise Exception(f"Failed to parse LLM response: {e}\nResponse: {response[:200]}")


if __name__ == '__main__':
    # Example usage
    import os

    judge = LLMJudge(provider="openai")

    customer_messages = [
        "This is ridiculous! My headphones are broken!",
        "Fine. What can you do about it?",
        "Okay, send me a replacement."
    ]

    agent_responses = [
        "I completely understand how frustrating this must be. Let me help you get this resolved right away.",
        "I can offer you either a full refund or a replacement. As a Gold member, we can ship the replacement with free expedited delivery arriving in 2 business days. Which would you prefer?",
        "Perfect! I've initiated your replacement order with expedited shipping. You'll receive a confirmation email shortly with tracking information. Is there anything else I can help you with today?"
    ]

    context = {
        'customer_tier': 'gold',
        'scenario_type': 'refund_request',
        'emotional_state': 'angry'
    }

    dimensions = {
        'empathy': 0.25,
        'resolution': 0.35,
        'policy_compliance': 0.25,
        'efficiency': 0.15
    }

    scores = judge.evaluate_conversation(
        customer_messages,
        agent_responses,
        context,
        dimensions
    )

    print("LLM Judge Evaluation:")
    print("=" * 60)
    for score in scores:
        print(f"\n{score.dimension.upper()}: {score.score}/5.0")
        print(f"  {score.reasoning}")
