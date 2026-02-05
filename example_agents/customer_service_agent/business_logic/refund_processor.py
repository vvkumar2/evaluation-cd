"""
Refund processing module for TechGear e-commerce platform.

This module handles refund requests and policy enforcement.
"""

from enum import Enum


class CustomerTier(Enum):
    """Customer membership tiers."""

    STANDARD = "standard"
    GOLD = "gold"
    PLATINUM = "platinum"


class RefundStatus(Enum):
    """Refund request status."""

    APPROVED = "approved"
    DENIED = "denied"
    PENDING_REVIEW = "pending_review"


# Business policy constants
STANDARD_REFUND_WINDOW_DAYS = 30
GOLD_REFUND_WINDOW_DAYS = 60
PLATINUM_REFUND_WINDOW_DAYS = 90

MAX_REFUND_WITHOUT_APPROVAL = 200.00
MAX_REFUND_WITH_MANAGER_APPROVAL = 1000.00


class RefundProcessor:
    """
    Handles refund requests for customer orders.

    Business Rules:
    - Standard customers: 30-day refund window
    - Gold customers: 60-day refund window
    - Platinum customers: 90-day refund window
    - Refunds up to $200 can be auto-approved
    - Refunds $200-$1000 require manager approval
    - Refunds over $1000 require executive approval
    - Damaged items: Full refund regardless of window
    - Original packaging required for non-damaged returns
    """

    def __init__(self):
        self.pending_approvals = []

    def process_refund_request(
        self,
        order_id: str,
        customer_tier: CustomerTier,
        order_total: float,
        days_since_delivery: int,
        is_damaged: bool = False,
    ) -> RefundStatus:
        """
        Process a refund request and return the status.

        Args:
            order_id: Unique order identifier
            customer_tier: Customer's membership tier
            order_total: Total order amount
            days_since_delivery: Number of days since order was delivered
            is_damaged: Whether the item arrived damaged

        Returns:
            RefundStatus indicating approval, denial, or pending review

        Raises:
            ValueError: If order_total is negative
            ValueError: If days_since_delivery is negative
        """
        # Validation
        if order_total < 0:
            raise ValueError("Order total must be non-negative")

        if days_since_delivery < 0:
            raise ValueError("Days since delivery must be non-negative")

        # Special case: Damaged items always get refunded
        if is_damaged:
            return RefundStatus.APPROVED

        # Check if within refund window
        if not self._is_within_refund_window(customer_tier, days_since_delivery):
            return RefundStatus.DENIED

        # Check refund amount and approval authority
        if order_total <= MAX_REFUND_WITHOUT_APPROVAL:
            return RefundStatus.APPROVED

        elif order_total <= MAX_REFUND_WITH_MANAGER_APPROVAL:
            return self._request_manager_approval(order_id, order_total)

        else:
            return self._request_executive_approval(order_id, order_total)

    def _is_within_refund_window(
        self, customer_tier: CustomerTier, days_since_delivery: int
    ) -> bool:
        """Check if refund request is within the allowed window."""
        if customer_tier == CustomerTier.PLATINUM:
            return days_since_delivery <= PLATINUM_REFUND_WINDOW_DAYS
        elif customer_tier == CustomerTier.GOLD:
            return days_since_delivery <= GOLD_REFUND_WINDOW_DAYS
        else:  # STANDARD
            return days_since_delivery <= STANDARD_REFUND_WINDOW_DAYS

    def _request_manager_approval(self, order_id: str, amount: float) -> RefundStatus:
        """Request manager approval for mid-tier refunds."""
        self.pending_approvals.append(
            {"order_id": order_id, "amount": amount, "approval_level": "manager"}
        )
        return RefundStatus.PENDING_REVIEW

    def _request_executive_approval(self, order_id: str, amount: float) -> RefundStatus:
        """Request executive approval for high-value refunds."""
        self.pending_approvals.append(
            {"order_id": order_id, "amount": amount, "approval_level": "executive"}
        )
        return RefundStatus.PENDING_REVIEW

    def get_refund_window_for_tier(self, customer_tier: CustomerTier) -> int:
        """
        Get the refund window in days for a customer tier.

        Args:
            customer_tier: Customer's membership tier

        Returns:
            Number of days in the refund window
        """
        if customer_tier == CustomerTier.PLATINUM:
            return PLATINUM_REFUND_WINDOW_DAYS
        elif customer_tier == CustomerTier.GOLD:
            return GOLD_REFUND_WINDOW_DAYS
        else:
            return STANDARD_REFUND_WINDOW_DAYS
