#!/usr/bin/env python3
"""
Simple customer service agent for TechGear e-commerce platform.

Reads JSON input from stdin with customer message and context,
responds with appropriate customer service reply.
"""

import json
import sys
import os

# Add business logic to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'business_logic'))

from refund_processor import (
    RefundProcessor,
    CustomerTier,
    RefundStatus,
    GOLD_REFUND_WINDOW_DAYS,
    STANDARD_REFUND_WINDOW_DAYS
)
from order_manager import OrderManager, OrderStatus, ShippingSpeed


class CustomerServiceAgent:
    """Simple rule-based customer service agent."""

    def __init__(self):
        self.refund_processor = RefundProcessor()
        self.order_manager = OrderManager()

    def handle_message(self, message: str, context: dict, history: list) -> str:
        """
        Handle a customer message and return a response.

        Args:
            message: Customer's message
            context: Context information (customer tier, order details, etc.)
            history: Conversation history

        Returns:
            Agent's response
        """
        message_lower = message.lower()

        # Detect intent
        if any(word in message_lower for word in ['refund', 'return', 'money back']):
            return self._handle_refund_request(message, context, history)

        elif any(word in message_lower for word in ['order', 'tracking', 'shipped', 'delivery']):
            return self._handle_order_inquiry(message, context, history)

        elif any(word in message_lower for word in ['cancel', 'modify', 'change']):
            return self._handle_order_modification(message, context, history)

        elif any(word in message_lower for word in ['shipping', 'delivery time', 'how long']):
            return self._handle_shipping_inquiry(message, context)

        else:
            return self._handle_general_inquiry(message, context)

    def _handle_refund_request(self, message: str, context: dict, history: list) -> str:
        """Handle refund-related requests."""
        customer_tier = context.get('customer_tier', 'standard')
        message_lower = message.lower()

        # Check if customer is angry (multiple exclamation marks, all caps, words like "ridiculous")
        is_angry = (
            '!!' in message or
            message.isupper() or
            any(word in message_lower for word in ['ridiculous', 'unacceptable', 'terrible', 'awful'])
        )

        # Build response
        response_parts = []

        # Empathy (but not always perfect)
        if is_angry:
            # Good empathy for angry customers
            response_parts.append("I completely understand how frustrating this must be, and I sincerely apologize for the inconvenience.")
        elif any(word in message_lower for word in ['broken', 'damaged', 'defective']):
            # Decent empathy for problems
            response_parts.append("I'm sorry to hear you're having issues with your product.")
        else:
            # Minimal empathy for standard requests
            response_parts.append("I can help you with that.")

        # Offer solution based on context
        order = context.get('order', {})
        days_since = order.get('delivered_date_days_ago', 5)
        price = order.get('price', 99.99)

        # Determine refund window
        tier_enum = CustomerTier.GOLD if customer_tier == 'gold' else CustomerTier.STANDARD
        refund_window = self.refund_processor.get_refund_window_for_tier(tier_enum)

        if days_since > refund_window:
            # Outside window
            response_parts.append(
                f"I've checked your order, and it was delivered {days_since} days ago. "
                f"Unfortunately, our refund policy for {customer_tier} members is {refund_window} days. "
                f"However, I'd like to help. Can you tell me more about the issue? "
                f"If the item arrived damaged, we can make an exception."
            )
        else:
            # Within window - offer refund
            response_parts.append(
                f"I can absolutely help with a refund. Since you're within our {refund_window}-day "
                f"return window, you're eligible for a full refund of ${price:.2f}."
            )

            # Add timeline
            if price <= 200:
                response_parts.append("I've initiated the refund, and you should see it in 3-5 business days.")
            else:
                response_parts.append(
                    "Since this is over $200, I'll need to get manager approval, "
                    "which typically takes 1-2 business days. I'll follow up with you as soon as it's approved."
                )

            # Mention gold benefits if applicable
            if customer_tier == 'gold':
                response_parts.append(
                    "As a valued Gold member, you have an extended 60-day return window, "
                    "which I want to make sure you're aware of for future reference."
                )

        # Professional close
        response_parts.append("Is there anything else I can help you with?")

        return " ".join(response_parts)

    def _handle_order_inquiry(self, message: str, context: dict, history: list) -> str:
        """Handle order tracking and status inquiries."""
        order = context.get('order', {})
        order_id = order.get('id', 'ORD-12345')
        status = order.get('status', 'shipped')

        response_parts = []
        response_parts.append(f"Let me check on that for you.")
        response_parts.append(
            f"Your order {order_id} is currently {status}. "
        )

        if status == 'shipped':
            response_parts.append("It should arrive within 2-3 business days.")
        elif status == 'delivered':
            response_parts.append("According to our records, it was delivered.")

        response_parts.append("Let me know if you need anything else!")

        return " ".join(response_parts)

    def _handle_order_modification(self, message: str, context: dict, history: list) -> str:
        """Handle order cancellation or modification requests."""
        order = context.get('order', {})
        status_str = order.get('status', 'processing')

        try:
            status = OrderStatus[status_str.upper()]
        except KeyError:
            status = OrderStatus.PROCESSING

        response_parts = []

        if 'cancel' in message.lower():
            if self.order_manager.can_cancel_order(status):
                response_parts.append(
                    "I can help you cancel that order. Since it hasn't shipped yet, "
                    "I can process the cancellation right away. Your refund will be "
                    "processed within 3-5 business days."
                )
            else:
                response_parts.append(
                    "Unfortunately, your order has already shipped, so I can't cancel it at this point. "
                    "However, once you receive it, you can return it for a full refund within our "
                    "return window. Would that work for you?"
                )
        else:
            # Modification request
            if self.order_manager.can_modify_order(status):
                response_parts.append(
                    "I can help modify your order since it's still pending. "
                    "What would you like to change?"
                )
            else:
                response_parts.append(
                    "I'm sorry, but once an order is being processed, we can't make modifications. "
                    "If you need to change something, you could cancel and place a new order, "
                    "or wait for this one to arrive and return it if needed."
                )

        return " ".join(response_parts)

    def _handle_shipping_inquiry(self, message: str, context: dict) -> str:
        """Handle shipping-related questions."""
        customer_tier = context.get('customer_tier', 'standard')
        order = context.get('order', {})
        price = order.get('price', 99.99)

        response_parts = []

        # Standard shipping time
        response_parts.append("Standard shipping takes 5-7 business days.")

        # Free shipping info
        if price >= 50:
            response_parts.append("Your order qualifies for free standard shipping since it's over $50.")

        # Premium member benefits
        if customer_tier == 'gold':
            response_parts.append(
                "As a Gold member, you also have access to free expedited shipping (2-3 days)."
            )
        elif customer_tier == 'platinum':
            response_parts.append(
                "As a Platinum member, you get free express shipping (1 business day)!"
            )

        return " ".join(response_parts)

    def _handle_general_inquiry(self, message: str, context: dict) -> str:
        """Handle general questions."""
        # Basic response (not very helpful - should score poorly)
        return (
            "Thank you for contacting TechGear customer support. "
            "How can I assist you today?"
        )


def main():
    """Main entry point - reads from stdin, writes to stdout."""
    try:
        # Read input
        input_data = json.loads(sys.stdin.read())

        message = input_data.get('message', '')
        context = input_data.get('context', {})
        history = input_data.get('history', [])

        # Create agent and get response
        agent = CustomerServiceAgent()
        response = agent.handle_message(message, context, history)

        # Output response (just the text, no JSON wrapper needed)
        print(response)

    except Exception as e:
        # Error handling - return a generic error message
        print(f"I apologize, but I'm experiencing technical difficulties. Please try again or contact our support team directly.")
        sys.exit(0)  # Don't exit with error code - we still gave a response


if __name__ == '__main__':
    main()
