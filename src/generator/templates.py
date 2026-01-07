"""
Templates for generating test cases from extracted business logic.

Provides reusable templates for different types of test scenarios:
- Happy path conversations
- Error handling scenarios
- Edge case testing
- Policy compliance checks
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class CheckpointTemplate:
    """Template for a conversation checkpoint."""
    criterion: str
    check_type: str  # 'must', 'must_not', 'should'
    description: str
    weight: float = 1.0


@dataclass
class TurnTemplate:
    """Template for a conversation turn."""
    customer_message: str
    checkpoints: List[CheckpointTemplate]
    agent_actions: List[str] = field(default_factory=list)  # Expected API calls


@dataclass
class ConversationTemplate:
    """Template for a multi-turn conversation."""
    name: str
    description: str
    scenario_type: str  # 'happy_path', 'error_path', 'edge_case'
    context: Dict[str, Any]
    turns: List[TurnTemplate]
    evaluation_dimensions: Dict[str, float]  # dimension -> weight


@dataclass
class TestCaseTemplate:
    """Complete test case template."""
    id: str
    name: str
    category: str
    conversation: ConversationTemplate
    expected_outcome: str
    pass_threshold: float = 0.7


class TemplateLibrary:
    """Library of pre-built test case templates."""

    @staticmethod
    def refund_request_template(
        item_name: str = "product",
        price: float = 99.99,
        days_since_delivery: int = 5,
        customer_tier: str = "standard"
    ) -> ConversationTemplate:
        """Template for a refund request scenario."""

        return ConversationTemplate(
            name=f"refund_request_{customer_tier}",
            description=f"Customer requesting refund for {item_name} within policy window",
            scenario_type="happy_path",
            context={
                "customer_tier": customer_tier,
                "order": {
                    "item": item_name,
                    "price": price,
                    "delivered_date_days_ago": days_since_delivery
                }
            },
            turns=[
                TurnTemplate(
                    customer_message=f"I want to return my {item_name}. It doesn't work as expected.",
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="empathy",
                            check_type="must",
                            description="Acknowledges customer's issue",
                            weight=0.2
                        ),
                        CheckpointTemplate(
                            criterion="information_gathering",
                            check_type="must",
                            description="Asks about order details or offers to look it up",
                            weight=0.3
                        ),
                        CheckpointTemplate(
                            criterion="no_immediate_refusal",
                            check_type="must_not",
                            description="Does not refuse without understanding the issue",
                            weight=0.5
                        )
                    ]
                ),
                TurnTemplate(
                    customer_message="My order number is ORD-12345. I got it last week.",
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="policy_check",
                            check_type="must",
                            description="Verifies refund eligibility (within window)",
                            weight=0.4
                        ),
                        CheckpointTemplate(
                            criterion="offers_solution",
                            check_type="must",
                            description="Offers refund or replacement options",
                            weight=0.4
                        ),
                        CheckpointTemplate(
                            criterion="clear_next_steps",
                            check_type="must",
                            description="Explains what will happen next",
                            weight=0.2
                        )
                    ],
                    agent_actions=["verify_order", "check_refund_eligibility"]
                ),
                TurnTemplate(
                    customer_message="Okay, I'll take the refund. How long will it take?",
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="timeline_provided",
                            check_type="must",
                            description="Gives specific timeline for refund processing",
                            weight=0.3
                        ),
                        CheckpointTemplate(
                            criterion="confirmation",
                            check_type="must",
                            description="Confirms refund has been initiated",
                            weight=0.5
                        ),
                        CheckpointTemplate(
                            criterion="professional_close",
                            check_type="should",
                            description="Ends conversation professionally",
                            weight=0.2
                        )
                    ],
                    agent_actions=["initiate_refund"]
                )
            ],
            evaluation_dimensions={
                "empathy": 0.2,
                "resolution": 0.35,
                "policy_compliance": 0.25,
                "efficiency": 0.2
            }
        )

    @staticmethod
    def angry_customer_template(
        complaint: str = "broken product",
        customer_tier: str = "gold"
    ) -> ConversationTemplate:
        """Template for handling an angry customer."""

        return ConversationTemplate(
            name=f"angry_customer_{complaint.replace(' ', '_')}",
            description=f"De-escalate angry customer complaining about {complaint}",
            scenario_type="edge_case",
            context={
                "customer_tier": customer_tier,
                "emotional_state": "angry",
                "complaint": complaint
            },
            turns=[
                TurnTemplate(
                    customer_message=f"This is RIDICULOUS! Your {complaint}! I'm extremely disappointed!",
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="de_escalation",
                            check_type="must",
                            description="Explicitly acknowledges frustration and apologizes",
                            weight=0.4
                        ),
                        CheckpointTemplate(
                            criterion="no_defensiveness",
                            check_type="must_not",
                            description="Does not make excuses or blame customer",
                            weight=0.3
                        ),
                        CheckpointTemplate(
                            criterion="ownership",
                            check_type="must",
                            description="Takes ownership of resolving the issue",
                            weight=0.3
                        )
                    ]
                ),
                TurnTemplate(
                    customer_message="Fine. What are you going to do about it?",
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="concrete_action",
                            check_type="must",
                            description="Offers specific resolution (not vague promises)",
                            weight=0.5
                        ),
                        CheckpointTemplate(
                            criterion="premium_treatment",
                            check_type="should",
                            description=f"Mentions {customer_tier} member benefits if applicable",
                            weight=0.3
                        ),
                        CheckpointTemplate(
                            criterion="urgency",
                            check_type="must",
                            description="Conveys that issue will be resolved quickly",
                            weight=0.2
                        )
                    ]
                )
            ],
            evaluation_dimensions={
                "empathy": 0.3,
                "de_escalation": 0.3,
                "resolution": 0.25,
                "professionalism": 0.15
            }
        )

    @staticmethod
    def policy_violation_template(
        policy_name: str,
        violation_reason: str,
        customer_request: str
    ) -> ConversationTemplate:
        """Template for scenario where customer request violates policy."""

        return ConversationTemplate(
            name=f"policy_violation_{policy_name}",
            description=f"Customer requests something that violates {policy_name}",
            scenario_type="error_path",
            context={
                "policy": policy_name,
                "violation": violation_reason,
                "customer_request": customer_request
            },
            turns=[
                TurnTemplate(
                    customer_message=customer_request,
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="policy_enforcement",
                            check_type="must",
                            description=f"Does not grant request that violates {policy_name}",
                            weight=0.5
                        ),
                        CheckpointTemplate(
                            criterion="explanation",
                            check_type="must",
                            description="Explains the policy reason clearly",
                            weight=0.3
                        ),
                        CheckpointTemplate(
                            criterion="alternative_offered",
                            check_type="should",
                            description="Offers alternative solution if possible",
                            weight=0.2
                        )
                    ]
                )
            ],
            evaluation_dimensions={
                "policy_compliance": 0.5,
                "empathy": 0.2,
                "helpfulness": 0.3
            }
        )

    @staticmethod
    def edge_case_template(
        edge_case_type: str,
        description: str,
        customer_message: str
    ) -> ConversationTemplate:
        """Template for edge case scenarios."""

        return ConversationTemplate(
            name=f"edge_case_{edge_case_type}",
            description=description,
            scenario_type="edge_case",
            context={
                "edge_case_type": edge_case_type
            },
            turns=[
                TurnTemplate(
                    customer_message=customer_message,
                    checkpoints=[
                        CheckpointTemplate(
                            criterion="handles_gracefully",
                            check_type="must",
                            description="Does not crash or give nonsensical response",
                            weight=0.4
                        ),
                        CheckpointTemplate(
                            criterion="clarification",
                            check_type="should",
                            description="Asks for clarification if input is unclear",
                            weight=0.3
                        ),
                        CheckpointTemplate(
                            criterion="helpful_response",
                            check_type="must",
                            description="Provides helpful guidance even for unusual request",
                            weight=0.3
                        )
                    ]
                )
            ],
            evaluation_dimensions={
                "robustness": 0.4,
                "helpfulness": 0.4,
                "professionalism": 0.2
            }
        )


if __name__ == '__main__':
    # Example usage
    library = TemplateLibrary()

    # Generate a refund template
    refund_conv = library.refund_request_template(
        item_name="wireless headphones",
        price=149.99,
        customer_tier="gold"
    )

    print(f"Template: {refund_conv.name}")
    print(f"Turns: {len(refund_conv.turns)}")
    print(f"\nFirst turn:")
    print(f"  Customer: {refund_conv.turns[0].customer_message}")
    print(f"  Checkpoints: {len(refund_conv.turns[0].checkpoints)}")
