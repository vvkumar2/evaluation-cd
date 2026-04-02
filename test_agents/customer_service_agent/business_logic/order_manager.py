"""
Order management module for TechGear platform.

Handles order tracking, updates, and customer inquiries.
"""

from enum import Enum


class OrderStatus(Enum):
    """Order status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ShippingSpeed(Enum):
    """Shipping speed options."""

    STANDARD = "standard"  # 5-7 business days
    EXPEDITED = "expedited"  # 2-3 business days
    EXPRESS = "express"  # 1 business day


# Shipping costs by tier
STANDARD_SHIPPING_COST = 5.99
EXPEDITED_SHIPPING_COST = 12.99
EXPRESS_SHIPPING_COST = 24.99

# Free shipping threshold
FREE_SHIPPING_THRESHOLD = 50.00


class OrderManager:
    """
    Manages customer orders and shipping.

    Business Rules:
    - Orders over $50 get free standard shipping
    - Gold members get free expedited shipping
    - Platinum members get free express shipping
    - Orders cannot be cancelled once shipped
    - Order modifications allowed only in PENDING status
    """

    def __init__(self):
        self.orders = {}

    def get_shipping_cost(
        self,
        order_total: float,
        shipping_speed: ShippingSpeed,
        customer_tier: str = "standard",
    ) -> float:
        """
        Calculate shipping cost based on order and customer tier.

        Args:
            order_total: Total order amount before shipping
            shipping_speed: Requested shipping speed
            customer_tier: Customer membership tier

        Returns:
            Shipping cost in dollars

        Raises:
            ValueError: If order_total is negative
        """
        if order_total < 0:
            raise ValueError("Order total cannot be negative")

        # Free shipping for orders over threshold (standard shipping only)
        if (
            order_total >= FREE_SHIPPING_THRESHOLD
            and shipping_speed == ShippingSpeed.STANDARD
        ):
            return 0.00

        # Premium member benefits
        if customer_tier.lower() == "platinum":
            # Platinum gets free express shipping
            return 0.00
        elif (
            customer_tier.lower() == "gold" and shipping_speed != ShippingSpeed.EXPRESS
        ):
            # Gold gets free standard and expedited shipping
            return 0.00

        # Standard pricing
        if shipping_speed == ShippingSpeed.EXPRESS:
            return EXPRESS_SHIPPING_COST
        elif shipping_speed == ShippingSpeed.EXPEDITED:
            return EXPEDITED_SHIPPING_COST
        else:
            return STANDARD_SHIPPING_COST

    def can_cancel_order(self, order_status: OrderStatus) -> bool:
        """
        Check if an order can be cancelled.

        Orders can only be cancelled if they haven't shipped yet.

        Args:
            order_status: Current status of the order

        Returns:
            True if order can be cancelled, False otherwise
        """
        if order_status in [OrderStatus.PENDING, OrderStatus.PROCESSING]:
            return True
        return False

    def can_modify_order(self, order_status: OrderStatus) -> bool:
        """
        Check if an order can be modified.

        Orders can only be modified while still pending.

        Args:
            order_status: Current status of the order

        Returns:
            True if order can be modified, False otherwise
        """
        return order_status == OrderStatus.PENDING

    def get_delivery_estimate(self, shipping_speed: ShippingSpeed) -> str:
        """
        Get estimated delivery timeframe.

        Args:
            shipping_speed: Shipping method selected

        Returns:
            Human-readable delivery estimate
        """
        if shipping_speed == ShippingSpeed.EXPRESS:
            return "1 business day"
        elif shipping_speed == ShippingSpeed.EXPEDITED:
            return "2-3 business days"
        else:
            return "5-7 business days"
