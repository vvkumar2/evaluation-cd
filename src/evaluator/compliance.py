"""
Compliance checker for hard rules and policy violations.

Handles:
- Keyword/phrase presence checks
- Policy violation detection
- Required action verification
- Forbidden behavior detection
"""

import re
from typing import List, Dict, Any
from .metrics import CheckpointResult


class ComplianceChecker:
    """Check agent responses for compliance with hard rules."""

    def check_checkpoint(
        self,
        agent_response: str,
        checkpoint: Dict[str, Any]
    ) -> CheckpointResult:
        """
        Evaluate a single checkpoint against agent response.

        Args:
            agent_response: Agent's response text
            checkpoint: Checkpoint definition with criterion, check_type, description

        Returns:
            CheckpointResult
        """
        criterion = checkpoint['criterion']
        check_type = checkpoint['check_type']
        description = checkpoint['description']
        weight = checkpoint.get('weight', 1.0)

        # Route to appropriate check method
        if check_type == 'must':
            return self._check_must_include(
                agent_response, criterion, description, weight
            )
        elif check_type == 'must_not':
            return self._check_must_not_include(
                agent_response, criterion, description, weight
            )
        elif check_type == 'should':
            return self._check_should_include(
                agent_response, criterion, description, weight
            )
        else:
            # Unknown check type - pass with warning
            return CheckpointResult(
                criterion=criterion,
                check_type=check_type,
                passed=True,
                score=1.0,
                reason=f"Unknown check type: {check_type}",
                weight=weight
            )

    def _check_must_include(
        self,
        agent_response: str,
        criterion: str,
        description: str,
        weight: float
    ) -> CheckpointResult:
        """
        Check that response includes required content.

        Uses heuristics based on criterion name to determine what to look for.
        """
        response_lower = agent_response.lower()

        # Map criterion to keywords to look for
        keyword_map = {
            'empathy': [
                'understand', 'frustrat', 'sorry', 'apologize',
                'i know how', 'appreciate', 'hear'
            ],
            'de_escalation': [
                'understand', 'apologize', 'sorry', 'help you',
                'make this right', 'resolve'
            ],
            'ownership': [
                'i will', 'let me', 'i can help', "i'll",
                'we will', 'we can'
            ],
            'policy_check': [
                'policy', 'eligible', 'qualify', 'within',
                'allow', 'permitted'
            ],
            'offers_solution': [
                'refund', 'replacement', 'option', 'can offer',
                'would you like', 'i can'
            ],
            'timeline_provided': [
                'day', 'hour', 'week', 'business day',
                'within', 'by', 'should receive'
            ],
            'confirmation': [
                'processed', 'initiated', 'confirmed', 'submitted',
                'completed', 'done'
            ],
            'information_gathering': [
                'order number', 'can you', 'could you',
                'may i', 'need to', 'help me understand'
            ],
            'clear_next_steps': [
                'next', 'will', 'receive', 'expect',
                'happen', 'then'
            ],
            'concrete_action': [
                'will', 'can', 'going to', 'send',
                'process', 'provide'
            ],
            'explanation': [
                'because', 'reason', 'policy', 'unfortunately',
                'this is', 'why'
            ]
        }

        # Get keywords for this criterion
        keywords = keyword_map.get(criterion.lower(), [])

        if not keywords:
            # Generic check - just verify response is not empty
            if agent_response.strip():
                return CheckpointResult(
                    criterion=criterion,
                    check_type='must',
                    passed=True,
                    score=1.0,
                    reason=f"Response provided for: {description}",
                    weight=weight
                )
            else:
                return CheckpointResult(
                    criterion=criterion,
                    check_type='must',
                    passed=False,
                    score=0.0,
                    reason="Empty response",
                    weight=weight
                )

        # Check if any keywords are present
        found_keywords = [kw for kw in keywords if kw in response_lower]

        if found_keywords:
            return CheckpointResult(
                criterion=criterion,
                check_type='must',
                passed=True,
                score=1.0,
                reason=f"Found indicators: {', '.join(found_keywords[:2])}",
                weight=weight
            )
        else:
            return CheckpointResult(
                criterion=criterion,
                check_type='must',
                passed=False,
                score=0.0,
                reason=f"Missing required element: {description}",
                weight=weight
            )

    def _check_must_not_include(
        self,
        agent_response: str,
        criterion: str,
        description: str,
        weight: float
    ) -> CheckpointResult:
        """Check that response does NOT include forbidden content."""
        response_lower = agent_response.lower()

        # Map criterion to forbidden keywords
        forbidden_map = {
            'no_blame': [
                'your fault', 'you should have', 'you did',
                'you forgot', 'you should', 'did you'
            ],
            'no_defensiveness': [
                'our policy is', 'we cannot', 'impossible',
                'not our fault', 'shipping company', 'manufacturer'
            ],
            'no_immediate_refusal': [
                'no', 'cannot', 'unable', "can't", 'impossible',
                'not possible'
            ],
            'no_script': [
                'i apologize for any inconvenience this may have caused',
                'thank you for your patience',
                'is there anything else i can help you with today'
            ]
        }

        forbidden = forbidden_map.get(criterion.lower(), [])

        if not forbidden:
            # Generic check - just pass
            return CheckpointResult(
                criterion=criterion,
                check_type='must_not',
                passed=True,
                score=1.0,
                reason=f"No violations detected: {description}",
                weight=weight
            )

        # Check if any forbidden phrases are present
        found_forbidden = [phrase for phrase in forbidden if phrase in response_lower]

        if found_forbidden:
            return CheckpointResult(
                criterion=criterion,
                check_type='must_not',
                passed=False,
                score=0.0,
                reason=f"Forbidden content found: '{found_forbidden[0]}'",
                weight=weight
            )
        else:
            return CheckpointResult(
                criterion=criterion,
                check_type='must_not',
                passed=True,
                score=1.0,
                reason="No forbidden content detected",
                weight=weight
            )

    def _check_should_include(
        self,
        agent_response: str,
        criterion: str,
        description: str,
        weight: float
    ) -> CheckpointResult:
        """
        Check for recommended but not required content.

        'Should' checks don't fail hard - they just reduce the score.
        """
        response_lower = agent_response.lower()

        # Similar to 'must' but less strict
        keyword_map = {
            'professional_close': [
                'thank', 'appreciate', 'please', 'help',
                'welcome', 'glad'
            ],
            'premium_treatment': [
                'gold', 'premium', 'valued', 'special',
                'expedited', 'priority'
            ],
            'alternative_offered': [
                'alternatively', 'instead', 'another option',
                'could also', 'other'
            ],
            'clarification': [
                'could you', 'can you clarify', 'tell me more',
                'help me understand', 'what do you mean'
            ],
            'urgency': [
                'quickly', 'immediately', 'right away', 'asap',
                'priority', 'today'
            ]
        }

        keywords = keyword_map.get(criterion.lower(), [])

        if not keywords:
            # Default to partial credit for 'should' checks
            return CheckpointResult(
                criterion=criterion,
                check_type='should',
                passed=True,
                score=0.7,
                reason=f"Optional: {description}",
                weight=weight
            )

        found_keywords = [kw for kw in keywords if kw in response_lower]

        if found_keywords:
            return CheckpointResult(
                criterion=criterion,
                check_type='should',
                passed=True,
                score=1.0,
                reason=f"Recommended content included: {', '.join(found_keywords[:2])}",
                weight=weight
            )
        else:
            # Still passes but with lower score
            return CheckpointResult(
                criterion=criterion,
                check_type='should',
                passed=True,
                score=0.5,
                reason=f"Recommended but not included: {description}",
                weight=weight
            )

    def check_all_checkpoints(
        self,
        agent_response: str,
        checkpoints: List[Dict[str, Any]]
    ) -> List[CheckpointResult]:
        """
        Check all checkpoints for a turn.

        Args:
            agent_response: Agent's response
            checkpoints: List of checkpoint definitions

        Returns:
            List of CheckpointResults
        """
        results = []

        for checkpoint in checkpoints:
            result = self.check_checkpoint(agent_response, checkpoint)
            results.append(result)

        return results

    def calculate_turn_score(self, checkpoint_results: List[CheckpointResult]) -> float:
        """
        Calculate overall score for a turn based on checkpoint results.

        Args:
            checkpoint_results: Results from all checkpoints

        Returns:
            Score from 0.0 to 1.0
        """
        if not checkpoint_results:
            return 1.0

        total_weight = sum(cp.weight for cp in checkpoint_results)
        if total_weight == 0:
            return 1.0

        weighted_sum = sum(cp.score * cp.weight for cp in checkpoint_results)
        return weighted_sum / total_weight


if __name__ == '__main__':
    # Example usage
    checker = ComplianceChecker()

    agent_response = """
    I completely understand how frustrating this must be.
    Let me help you with that refund right away.
    I've processed your refund of $149.99, and you should
    receive it within 3-5 business days.
    """

    checkpoints = [
        {
            'criterion': 'empathy',
            'check_type': 'must',
            'description': 'Acknowledges customer frustration',
            'weight': 0.3
        },
        {
            'criterion': 'no_blame',
            'check_type': 'must_not',
            'description': 'Does not blame customer',
            'weight': 0.3
        },
        {
            'criterion': 'timeline_provided',
            'check_type': 'must',
            'description': 'Provides timeline for refund',
            'weight': 0.4
        }
    ]

    results = checker.check_all_checkpoints(agent_response, checkpoints)
    turn_score = checker.calculate_turn_score(results)

    print(f"Turn Score: {turn_score:.2f}\n")
    for result in results:
        status = "✓" if result.passed else "✗"
        print(f"{status} {result.criterion}: {result.reason}")
