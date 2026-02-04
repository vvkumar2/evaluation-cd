"""
LangChain tools for the customer service agent.

Exposes business logic and backend service as callable tools for the LLM.
"""

from langchain.tools import tool

from backend_service import BackendService
from business_logic.refund_processor import RefundProcessor, CustomerTier, RefundStatus
from business_logic.order_manager import OrderManager, OrderStatus, ShippingSpeed

# Initialize services
backend_service = BackendService()
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
    order = backend_service.get_order(order_id)
    if not order:
        return f"Order {order_id} not found in system."

    customer = backend_service.get_customer(order["customer_id"])
    customer_name = customer["name"] if customer else "Unknown"

    return (
        f"Order Details:\n"
        f"ID: {order['id']}\n"
        f"Customer: {customer_name} ({order['customer_id']})\n"
        f"Amount: ${order['price']:.2f}\n"
        f"Status: {order['status']}\n"
        f"Days since delivery: {order['delivered_date_days_ago']}"
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
    orders = [
        order
        for order in backend_service.orders.values()
        if order["customer_id"] == customer_id
    ]

    if not orders:
        return f"No orders found for customer {customer_id}."

    orders_text = f"Orders for customer {customer_id}:\n"
    for order in orders:
        orders_text += (
            f"- {order['id']}: ${order['price']:.2f}, Status: {order['status']}, "
            f"Delivered {order['delivered_date_days_ago']} days ago\n"
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
    customer = backend_service.get_customer(customer_id)
    if not customer:
        return f"Customer {customer_id} not found in system."

    return (
        f"Customer Details:\n"
        f"ID: {customer['id']}\n"
        f"Name: {customer['name']}\n"
        f"Tier: {customer['tier'].upper()}\n"
        f"Email: {customer['email']}"
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
        # Convert tier string to enum
        tier_enum = {
            "standard": CustomerTier.STANDARD,
            "gold": CustomerTier.GOLD,
            "platinum": CustomerTier.PLATINUM,
        }.get(customer_tier.lower(), CustomerTier.STANDARD)

        # Call business logic
        status = refund_processor.process_refund_request(
            order_id=order_id,
            customer_tier=tier_enum,
            order_total=order_total,
            days_since_delivery=days_since_delivery,
            is_damaged=is_damaged,
        )

        # Format response
        status_text = {
            RefundStatus.APPROVED: "APPROVED",
            RefundStatus.DENIED: "DENIED",
            RefundStatus.PENDING_REVIEW: "PENDING_REVIEW",
        }.get(status, "UNKNOWN")

        return f"Refund Request Result:\n  Status: {status_text}\n  Order: {order_id}\n  Amount: ${order_total:.2f}"

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
        # Convert shipping speed to enum
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
        else:
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
        # Convert status to enum
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
        # Convert status to enum
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
        # Convert shipping speed to enum
        speed_enum = {
            "standard": ShippingSpeed.STANDARD,
            "expedited": ShippingSpeed.EXPEDITED,
            "express": ShippingSpeed.EXPRESS,
        }.get(shipping_speed.lower(), ShippingSpeed.STANDARD)

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
