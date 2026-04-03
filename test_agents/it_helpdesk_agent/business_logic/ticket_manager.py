"""
Ticket management module for IT helpdesk.

Handles ticket creation, escalation, and auto-triage logic.
"""

from datetime import date

# Auto-priority mapping by category
CATEGORY_PRIORITY = {
    "system_issue": "high",
    "password_reset": "medium",
    "access_request": "medium",
    "software_install": "low",
    "general": "low",
}


class TicketManager:
    """
    Manages IT support tickets.

    Business Rules:
    - Auto-assigns priority based on category if not specified
    - Escalation sets status to "escalated"
    - Cannot escalate resolved tickets
    - Critical priority + system outage -> PagerDuty required
    - All escalations require email notification
    """

    def get_default_priority(self, category: str) -> str:
        return CATEGORY_PRIORITY.get(category, "low")

    def escalate_ticket(self, ticket: dict, system_status: str = None) -> dict:
        """
        Escalate a ticket.

        Args:
            ticket: Ticket record
            system_status: Optional status of the associated system

        Returns:
            Dict with escalation result and required follow-up actions
        """
        current_status = ticket.get("status", "")

        if current_status == "resolved":
            return {
                "status": "error",
                "message": f"Ticket {ticket['id']} is already resolved and cannot be escalated.",
                "pagerduty_required": False,
                "email_required": False,
            }

        if current_status == "escalated":
            return {
                "status": "error",
                "message": f"Ticket {ticket['id']} is already escalated.",
                "pagerduty_required": False,
                "email_required": False,
            }

        priority = ticket.get("priority", "low")
        pagerduty_required = priority == "critical" and system_status == "outage"

        return {
            "status": "escalated",
            "message": f"Ticket {ticket['id']} has been escalated.",
            "pagerduty_required": pagerduty_required,
            "email_required": True,
            "ticket_id": ticket["id"],
            "priority": priority,
        }
