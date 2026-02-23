"""
LangChain tools for the customer service agent.

Exposes business logic and SQLite database as callable tools for the LLM.
Database URL is determined at import time from environment variables:
- Normal mode: sqlite:///techgear.db
- Test mode (AGENT_TEST_MODE=true): uses TEST_DB_URL env var
"""

import os
from langchain.tools import tool
from sqlalchemy import create_engine, text

from backend_service import get_db_url, create_schema, seed_sample_data
from business_logic.refund_processor import RefundProcessor, CustomerTier, RefundStatus
from business_logic.order_manager import OrderManager, OrderStatus, ShippingSpeed

# Initialize SQLite database connection
_db_url = get_db_url()
db_engine = create_engine(_db_url, connect_args={"check_same_thread": False})
create_schema(db_engine)

# Only seed sample data in non-test mode
if os.getenv("AGENT_TEST_MODE") != "true":
    seed_sample_data(db_engine)

refund_processor = RefundProcessor()
order_manager = OrderManager()


@tool
def lookup_order(order_id: str) -> str:
    """
    Look up order details by order ID.

    Args:
        order_id: The order ID to look up (e.g., "ORD-001")

    Returns:
        Order details as a formatted string, or error message if not found
    """
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT o.id, o.customer_id, c.name, o.price, o.status, "
                "o.delivered_date_days_ago "
                "FROM orders o JOIN customers c ON o.customer_id = c.id "
                "WHERE o.id = :order_id"
            ),
            {"order_id": order_id},
        ).fetchone()

    if not row:
        return f"Order {order_id} not found in system."

    return (
        f"Order Details:\n"
        f"ID: {row[0]}\n"
        f"Customer: {row[2]} ({row[1]})\n"
        f"Amount: ${row[3]:.2f}\n"
        f"Status: {row[4]}\n"
        f"Days since delivery: {row[5]}"
    )


@tool
def get_customer_orders(customer_id: str) -> str:
    """
    Get all orders for a customer.

    Args:
        customer_id: The customer ID (e.g., "CUST-001")

    Returns:
        List of customer's orders as a formatted string
    """
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, price, status, delivered_date_days_ago "
                "FROM orders WHERE customer_id = :customer_id"
            ),
            {"customer_id": customer_id},
        ).fetchall()

    if not rows:
        return f"No orders found for customer {customer_id}."

    orders_text = f"Orders for customer {customer_id}:\n"
    for row in rows:
        orders_text += (
            f"- {row[0]}: ${row[1]:.2f}, Status: {row[2]}, "
            f"Delivered {row[3]} days ago\n"
        )

    return orders_text.rstrip()


@tool
def lookup_customer(customer_id: str) -> str:
    """
    Look up customer details by customer ID.

    Args:
        customer_id: The customer ID to look up (e.g., "CUST-001")

    Returns:
        Customer details as a formatted string, or error message if not found
    """
    with db_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, name, tier, email FROM customers WHERE id = :customer_id"),
            {"customer_id": customer_id},
        ).fetchone()

    if not row:
        return f"Customer {customer_id} not found in system."

    return (
        f"Customer Details:\n"
        f"ID: {row[0]}\n"
        f"Name: {row[1]}\n"
        f"Tier: {row[2].upper()}\n"
        f"Email: {row[3]}"
    )


@tool
def process_refund_request(
    order_id: str,
    customer_tier: str,
    order_total: float,
    days_since_delivery: int,
    is_damaged: bool = False,
) -> str:
    """
    Process a refund request using business logic.

    Args:
        order_id: The order ID for the refund
        customer_tier: Customer tier (standard, gold, or platinum)
        order_total: Total order amount in dollars
        days_since_delivery: Days since the order was delivered
        is_damaged: Whether the item arrived damaged

    Returns:
        Refund decision (APPROVED, DENIED, or PENDING_REVIEW) as a formatted string
    """
    try:
        tier_enum = {
            "standard": CustomerTier.STANDARD,
            "gold": CustomerTier.GOLD,
            "platinum": CustomerTier.PLATINUM,
        }.get(customer_tier.lower(), CustomerTier.STANDARD)

        status = refund_processor.process_refund_request(
            order_id=order_id,
            customer_tier=tier_enum,
            order_total=order_total,
            days_since_delivery=days_since_delivery,
            is_damaged=is_damaged,
        )

        status_text = {
            RefundStatus.APPROVED: "APPROVED",
            RefundStatus.DENIED: "DENIED",
            RefundStatus.PENDING_REVIEW: "PENDING_REVIEW",
        }.get(status, "UNKNOWN")

        return (
            f"Refund Request Result:\n"
            f"  Status: {status_text}\n"
            f"  Order: {order_id}\n"
            f"  Amount: ${order_total:.2f}"
        )

    except Exception as e:
        return f"Error processing refund: {str(e)}"


@tool
def get_refund_window(customer_tier: str) -> str:
    """
    Get the refund window (in days) for a customer tier.

    Args:
        customer_tier: Customer tier (standard, gold, or platinum)

    Returns:
        Number of days in the refund window
    """
    tier_enum = {
        "standard": CustomerTier.STANDARD,
        "gold": CustomerTier.GOLD,
        "platinum": CustomerTier.PLATINUM,
    }.get(customer_tier.lower(), CustomerTier.STANDARD)

    days = refund_processor.get_refund_window_for_tier(tier_enum)
    return f"{customer_tier.upper()} tier customers have a {days}-day refund window."


@tool
def calculate_shipping_cost(
    order_total: float, shipping_speed: str, customer_tier: str = "standard"
) -> str:
    """
    Calculate shipping cost for an order.

    Args:
        order_total: Total order amount before shipping
        shipping_speed: Shipping speed (standard, expedited, or express)
        customer_tier: Customer tier (standard, gold, or platinum)

    Returns:
        Shipping cost as a formatted string
    """
    try:
        speed_enum = {
            "standard": ShippingSpeed.STANDARD,
            "expedited": ShippingSpeed.EXPEDITED,
            "express": ShippingSpeed.EXPRESS,
        }.get(shipping_speed.lower(), ShippingSpeed.STANDARD)

        cost = order_manager.get_shipping_cost(
            order_total=order_total,
            shipping_speed=speed_enum,
            customer_tier=customer_tier.lower(),
        )

        if cost == 0:
            return f"Free {shipping_speed.lower()} shipping for this order."
        return f"{shipping_speed.lower().capitalize()} shipping costs ${cost:.2f}"

    except Exception as e:
        return f"Error calculating shipping: {str(e)}"


@tool
def check_can_cancel_order(order_status: str) -> str:
    """
    Check if an order can be cancelled based on its status.

    Args:
        order_status: Current order status (pending, processing, shipped, delivered, or cancelled)

    Returns:
        Whether the order can be cancelled (yes/no) as a formatted string
    """
    try:
        status_enum = {
            "pending": OrderStatus.PENDING,
            "processing": OrderStatus.PROCESSING,
            "shipped": OrderStatus.SHIPPED,
            "delivered": OrderStatus.DELIVERED,
            "cancelled": OrderStatus.CANCELLED,
        }.get(order_status.lower(), OrderStatus.SHIPPED)

        can_cancel = order_manager.can_cancel_order(status_enum)
        return f"Order can be cancelled: {can_cancel}"

    except Exception as e:
        return f"Error checking cancellation: {str(e)}"


@tool
def check_can_modify_order(order_status: str) -> str:
    """
    Check if an order can be modified based on its status.

    Args:
        order_status: Current order status (pending, processing, shipped, delivered, or cancelled)

    Returns:
        Whether the order can be modified (yes/no) as a formatted string
    """
    try:
        status_enum = {
            "pending": OrderStatus.PENDING,
            "processing": OrderStatus.PROCESSING,
            "shipped": OrderStatus.SHIPPED,
            "delivered": OrderStatus.DELIVERED,
            "cancelled": OrderStatus.CANCELLED,
        }.get(order_status.lower(), OrderStatus.SHIPPED)

        can_modify = order_manager.can_modify_order(status_enum)
        return f"Order can be modified: {can_modify}"

    except Exception as e:
        return f"Error checking modification: {str(e)}"


@tool
def get_delivery_estimate(shipping_speed: str) -> str:
    """
    Get the estimated delivery time for a shipping speed.

    Args:
        shipping_speed: Shipping speed (standard, expedited, or express)

    Returns:
        Estimated delivery time as a formatted string
    """
    try:
        speed_map = {
            "standard": ShippingSpeed.STANDARD,
            "expedited": ShippingSpeed.EXPEDITED,
            "express": ShippingSpeed.EXPRESS,
        }
        speed_enum = speed_map.get(shipping_speed.lower())
        if speed_enum is None:
            valid = ", ".join(speed_map.keys())
            return f"Invalid shipping speed: '{shipping_speed}'. Valid options are: {valid}"

        estimate = order_manager.get_delivery_estimate(speed_enum)
        return f"Estimated delivery time for {shipping_speed.lower()}: {estimate}"

    except Exception as e:
        return f"Error getting delivery estimate: {str(e)}"


def get_tools():
    """Return list of all available tools."""
    return [
        lookup_order,
        get_customer_orders,
        lookup_customer,
        process_refund_request,
        get_refund_window,
        calculate_shipping_cost,
        check_can_cancel_order,
        check_can_modify_order,
        get_delivery_estimate,
    ]
