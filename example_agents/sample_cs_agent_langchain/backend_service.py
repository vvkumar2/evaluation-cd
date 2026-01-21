"""
Fake order/customer backend service for LangChain agent testing.

Provides in-memory storage of orders and customers for tool use.
This can be easily swapped for a real database without changing agent code.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class BackendService:
    """In-memory order and customer database."""

    def __init__(self):
        """Initialize with sample data for testing."""
        # Sample orders with diverse scenarios
        self.orders = {
            "ORD-001": {
                "id": "ORD-001",
                "customer_id": "CUST-001",
                "price": 75.00,
                "status": "delivered",
                "delivered_date_days_ago": 5,
            },
            "ORD-002": {
                "id": "ORD-002",
                "customer_id": "CUST-002",
                "price": 250.00,
                "status": "delivered",
                "delivered_date_days_ago": 35,  # Outside 30-day window for standard
            },
            "ORD-003": {
                "id": "ORD-003",
                "customer_id": "CUST-003",
                "price": 1500.00,
                "status": "delivered",
                "delivered_date_days_ago": 10,  # High value refund
            },
            "ORD-004": {
                "id": "ORD-004",
                "customer_id": "CUST-001",
                "price": 49.99,
                "status": "shipped",
                "delivered_date_days_ago": 0,  # Not yet delivered
            },
            "ORD-005": {
                "id": "ORD-005",
                "customer_id": "CUST-004",
                "price": 120.00,
                "status": "processing",
                "delivered_date_days_ago": 0,
            },
            "ORD-006": {
                "id": "ORD-006",
                "customer_id": "CUST-002",
                "price": 199.99,
                "status": "delivered",
                "delivered_date_days_ago": 3,
            },
            "ORD-007": {
                "id": "ORD-007",
                "customer_id": "CUST-005",
                "price": 55.00,
                "status": "delivered",
                "delivered_date_days_ago": 2,
            },
            "ORD-008": {
                "id": "ORD-008",
                "customer_id": "CUST-003",
                "price": 89.99,
                "status": "pending",
                "delivered_date_days_ago": 0,
            },
        }

        # Sample customers with different tiers
        self.customers = {
            "CUST-001": {
                "id": "CUST-001",
                "tier": "standard",
                "name": "John Doe",
                "email": "john@example.com",
            },
            "CUST-002": {
                "id": "CUST-002",
                "tier": "gold",
                "name": "Jane Smith",
                "email": "jane@example.com",
            },
            "CUST-003": {
                "id": "CUST-003",
                "tier": "platinum",
                "name": "Bob Johnson",
                "email": "bob@example.com",
            },
            "CUST-004": {
                "id": "CUST-004",
                "tier": "standard",
                "name": "Alice Williams",
                "email": "alice@example.com",
            },
            "CUST-005": {
                "id": "CUST-005",
                "tier": "gold",
                "name": "Charlie Brown",
                "email": "charlie@example.com",
            },
        }

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up an order by ID.

        Args:
            order_id: The order ID to look up

        Returns:
            Order details dict or None if not found
        """
        return self.orders.get(order_id)

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up a customer by ID.

        Args:
            customer_id: The customer ID to look up

        Returns:
            Customer details dict or None if not found
        """
        return self.customers.get(customer_id)

    def get_customer_tier_for_order(self, order_id: str) -> Optional[str]:
        """
        Get the customer tier for a given order.

        Args:
            order_id: The order ID

        Returns:
            Customer tier (standard, gold, platinum) or None
        """
        order = self.get_order(order_id)
        if not order:
            return None
        customer = self.get_customer(order["customer_id"])
        return customer["tier"] if customer else None
