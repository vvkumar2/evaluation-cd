"""
LangChain tools for the IT helpdesk agent.

Exposes business logic and SQLite database as callable tools for the LLM.
Database URL is determined at import time from environment variables:
- Normal mode: sqlite:///helpdesk.db
- Test mode (AGENT_TEST_MODE=true): uses TEST_DB_URL env var
"""

import os
from datetime import date
from langchain.tools import tool
from sqlalchemy import create_engine, text

from backend_service import get_db_url, create_schema, seed_sample_data
from business_logic.password_manager import PasswordManager
from business_logic.access_manager import AccessManager
from business_logic.ticket_manager import TicketManager

# Initialize SQLite database connection
_db_url = get_db_url()
db_engine = create_engine(_db_url, connect_args={"check_same_thread": False})
create_schema(db_engine)

# Only seed sample data in non-test mode
if os.getenv("AGENT_TEST_MODE") != "true":
    seed_sample_data(db_engine)

password_manager = PasswordManager()
access_manager = AccessManager()
ticket_manager = TicketManager()


@tool
def lookup_employee(employee_id: str) -> str:
    """
    Look up employee details by employee ID.

    Args:
        employee_id: The employee ID to look up (e.g., "EMP-001")

    Returns:
        Employee details as a formatted string, or error message if not found
    """
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, name, email, department, role, mfa_enabled, account_status "
                "FROM employees WHERE id = :employee_id"
            ),
            {"employee_id": employee_id},
        ).fetchone()

    if not row:
        return f"Employee {employee_id} not found in system."

    return (
        f"Employee Details:\n"
        f"ID: {row[0]}\n"
        f"Name: {row[1]}\n"
        f"Email: {row[2]}\n"
        f"Department: {row[3]}\n"
        f"Role: {row[4]}\n"
        f"MFA Enabled: {bool(row[5])}\n"
        f"Account Status: {row[6]}"
    )


@tool
def lookup_ticket(ticket_id: str) -> str:
    """
    Look up ticket details by ticket ID.

    Args:
        ticket_id: The ticket ID to look up (e.g., "TKT-001")

    Returns:
        Ticket details as a formatted string, or error message if not found
    """
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT t.id, t.employee_id, e.name, t.category, t.priority, "
                "t.status, t.description, t.assigned_to, t.created_at "
                "FROM tickets t JOIN employees e ON t.employee_id = e.id "
                "WHERE t.id = :ticket_id"
            ),
            {"ticket_id": ticket_id},
        ).fetchone()

    if not row:
        return f"Ticket {ticket_id} not found in system."

    assigned = row[7] if row[7] else "Unassigned"
    return (
        f"Ticket Details:\n"
        f"ID: {row[0]}\n"
        f"Employee: {row[2]} ({row[1]})\n"
        f"Category: {row[3]}\n"
        f"Priority: {row[4]}\n"
        f"Status: {row[5]}\n"
        f"Description: {row[6]}\n"
        f"Assigned To: {assigned}\n"
        f"Created: {row[8]}"
    )


@tool
def get_employee_tickets(employee_id: str) -> str:
    """
    Get all tickets for an employee.

    Args:
        employee_id: The employee ID (e.g., "EMP-001")

    Returns:
        List of employee's tickets as a formatted string
    """
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, category, priority, status, description, created_at "
                "FROM tickets WHERE employee_id = :employee_id"
            ),
            {"employee_id": employee_id},
        ).fetchall()

    if not rows:
        return f"No tickets found for employee {employee_id}."

    tickets_text = f"Tickets for employee {employee_id}:\n"
    for row in rows:
        tickets_text += (
            f"- {row[0]}: [{row[3].upper()}] {row[1]} (Priority: {row[2]}) - "
            f"{row[4]} (Created: {row[5]})\n"
        )

    return tickets_text.rstrip()


@tool
def create_ticket(
    employee_id: str, category: str, priority: str = "", description: str = ""
) -> str:
    """
    Create a new IT support ticket.

    Args:
        employee_id: Employee ID creating the ticket
        category: Ticket category (password_reset, access_request, software_install, system_issue, general)
        priority: Priority level (low, medium, high, critical). Auto-assigned from category if empty.
        description: Description of the issue

    Returns:
        New ticket details as a formatted string
    """
    if not priority:
        priority = ticket_manager.get_default_priority(category)

    with db_engine.connect() as conn:
        # Generate next ticket ID
        row = conn.execute(text("SELECT COUNT(*) FROM tickets")).fetchone()
        next_id = f"TKT-{(row[0] + 1):03d}"

        today = date.today().isoformat()

        conn.execute(
            text(
                "INSERT INTO tickets (id, employee_id, category, priority, status, description, created_at) "
                "VALUES (:id, :employee_id, :category, :priority, 'open', :description, :created_at)"
            ),
            {
                "id": next_id,
                "employee_id": employee_id,
                "category": category,
                "priority": priority,
                "description": description,
                "created_at": today,
            },
        )
        conn.commit()

    return (
        f"Ticket Created:\n"
        f"ID: {next_id}\n"
        f"Category: {category}\n"
        f"Priority: {priority}\n"
        f"Status: open\n"
        f"Description: {description}"
    )


@tool
def check_system_status(system_name: str) -> str:
    """
    Check the status of a system by name.

    Args:
        system_name: Name of the system to check (case-insensitive)

    Returns:
        System status as a formatted string, or error if not found
    """
    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, name, status, last_checked FROM systems "
                "WHERE LOWER(name) = LOWER(:system_name)"
            ),
            {"system_name": system_name},
        ).fetchone()

    if not row:
        return f"System '{system_name}' not found in system catalog."

    return (
        f"System Status:\n"
        f"ID: {row[0]}\n"
        f"Name: {row[1]}\n"
        f"Status: {row[2]}\n"
        f"Last Checked: {row[3]}"
    )


@tool
def list_system_issues() -> str:
    """
    List all systems that are not operational.

    Returns:
        List of systems with issues, or message if all systems are healthy
    """
    with db_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, name, status, last_checked FROM systems "
                "WHERE status != 'operational'"
            )
        ).fetchall()

    if not rows:
        return "All systems are operational. No issues detected."

    issues_text = "Systems with issues:\n"
    for row in rows:
        issues_text += (
            f"- {row[1]} ({row[0]}): {row[2].upper()} (Last checked: {row[3]})\n"
        )

    return issues_text.rstrip()


@tool
def reset_password(employee_id: str, requester_id: str) -> str:
    """
    Reset an employee's password. Admins can reset anyone's password.
    Regular users can only reset their own.

    Args:
        employee_id: ID of the employee whose password should be reset
        requester_id: ID of the employee requesting the reset

    Returns:
        Password reset result as a formatted string
    """
    with db_engine.connect() as conn:
        target = conn.execute(
            text(
                "SELECT id, name, email, department, role, mfa_enabled, account_status "
                "FROM employees WHERE id = :eid"
            ),
            {"eid": employee_id},
        ).fetchone()

        if not target:
            return f"Employee {employee_id} not found in system."

        requester = conn.execute(
            text(
                "SELECT id, name, email, department, role, mfa_enabled, account_status "
                "FROM employees WHERE id = :eid"
            ),
            {"eid": requester_id},
        ).fetchone()

        if not requester:
            return f"Requester {requester_id} not found in system."

    target_dict = dict(
        zip(
            [
                "id",
                "name",
                "email",
                "department",
                "role",
                "mfa_enabled",
                "account_status",
            ],
            target,
        )
    )
    requester_dict = dict(
        zip(
            [
                "id",
                "name",
                "email",
                "department",
                "role",
                "mfa_enabled",
                "account_status",
            ],
            requester,
        )
    )

    result = password_manager.reset_password(target_dict, requester_dict)

    # If successful, update account status in DB
    if result["status"] == "success":
        with db_engine.connect() as conn:
            conn.execute(
                text("UPDATE employees SET account_status = 'active' WHERE id = :eid"),
                {"eid": employee_id},
            )
            conn.commit()

    output = f"Password Reset Result:\n  Status: {result['status'].upper()}\n  {result['message']}"
    if result["status"] == "success":
        output += f"\n  Temporary Password: {result['temp_password']}"
        output += f"\n  Account Unlocked: {result['account_unlocked']}"
        output += (
            f"\n  MFA Re-enrollment Required: {result['mfa_reenrollment_required']}"
        )
        output += f"\n  Employee Email: {result['employee_email']}"

    return output


@tool
def request_access(employee_id: str, system_name: str, permission_level: str) -> str:
    """
    Request access to a system for an employee.

    Args:
        employee_id: Employee requesting access
        system_name: Name of the system (case-insensitive)
        permission_level: Requested permission level (read, write, admin)

    Returns:
        Access request result as a formatted string
    """
    with db_engine.connect() as conn:
        employee = conn.execute(
            text(
                "SELECT id, name, email, department, role FROM employees WHERE id = :eid"
            ),
            {"eid": employee_id},
        ).fetchone()

        if not employee:
            return f"Employee {employee_id} not found in system."

        system = conn.execute(
            text(
                "SELECT id, name, status FROM systems WHERE LOWER(name) = LOWER(:name)"
            ),
            {"name": system_name},
        ).fetchone()

        if not system:
            return f"System '{system_name}' not found in system catalog."

        existing_perms = conn.execute(
            text(
                "SELECT id, employee_id, system_id, permission_level, granted_by, expires_at "
                "FROM access_permissions WHERE employee_id = :eid AND system_id = :sid"
            ),
            {"eid": employee_id, "sid": system[0]},
        ).fetchall()

    employee_dict = dict(zip(["id", "name", "email", "department", "role"], employee))
    system_dict = dict(zip(["id", "name", "status"], system))
    perms_list = [
        dict(
            zip(
                [
                    "id",
                    "employee_id",
                    "system_id",
                    "permission_level",
                    "granted_by",
                    "expires_at",
                ],
                p,
            )
        )
        for p in existing_perms
    ]

    result = access_manager.request_access(
        employee_dict, system_dict, permission_level, perms_list
    )

    # If approved, create permission record
    if result["status"] == "approved":
        with db_engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM access_permissions")
            ).fetchone()
            perm_id = f"PERM-{(row[0] + 1):03d}"

            conn.execute(
                text(
                    "INSERT INTO access_permissions (id, employee_id, system_id, permission_level, granted_by, expires_at) "
                    "VALUES (:id, :employee_id, :system_id, :permission_level, :granted_by, NULL)"
                ),
                {
                    "id": perm_id,
                    "employee_id": employee_id,
                    "system_id": system[0],
                    "permission_level": permission_level,
                    "granted_by": "system",
                },
            )
            conn.commit()

    return (
        f"Access Request Result:\n"
        f"  Status: {result['status'].upper()}\n"
        f"  {result['message']}\n"
        f"  Requires Approval: {result['requires_approval']}"
    )


@tool
def request_software_install(employee_id: str, software_name: str) -> str:
    """
    Request installation of software for an employee.

    Args:
        employee_id: Employee requesting the software
        software_name: Name of the software (case-insensitive)

    Returns:
        Software install request result as a formatted string
    """
    with db_engine.connect() as conn:
        employee = conn.execute(
            text(
                "SELECT id, name, email, department, role FROM employees WHERE id = :eid"
            ),
            {"eid": employee_id},
        ).fetchone()

        if not employee:
            return f"Employee {employee_id} not found in system."

        software = conn.execute(
            text(
                "SELECT id, name, requires_approval, approved_roles "
                "FROM software_catalog WHERE LOWER(name) = LOWER(:name)"
            ),
            {"name": software_name},
        ).fetchone()

        if not software:
            return f"Software '{software_name}' not found in catalog."

    employee_dict = dict(zip(["id", "name", "email", "department", "role"], employee))
    software_dict = dict(
        zip(["id", "name", "requires_approval", "approved_roles"], software)
    )

    result = access_manager.request_software_install(employee_dict, software_dict)

    return (
        f"Software Install Result:\n"
        f"  Status: {result['status'].upper()}\n"
        f"  {result['message']}\n"
        f"  Requires Approval: {result['requires_approval']}"
    )


@tool
def escalate_ticket(ticket_id: str, reason: str) -> str:
    """
    Escalate an IT support ticket. Triggers PagerDuty for critical tickets
    with system outages, and always sends email notification.

    Args:
        ticket_id: The ticket ID to escalate
        reason: Reason for escalation

    Returns:
        Escalation result as a formatted string
    """
    with db_engine.connect() as conn:
        ticket_row = conn.execute(
            text(
                "SELECT id, employee_id, category, priority, status, description "
                "FROM tickets WHERE id = :tid"
            ),
            {"tid": ticket_id},
        ).fetchone()

        if not ticket_row:
            return f"Ticket {ticket_id} not found in system."

        ticket_dict = dict(
            zip(
                ["id", "employee_id", "category", "priority", "status", "description"],
                ticket_row,
            )
        )

        # Check for associated system status if it's a system_issue
        system_status = None
        if ticket_dict["category"] == "system_issue":
            # Look for systems in outage
            sys_row = conn.execute(
                text("SELECT status FROM systems WHERE status = 'outage' LIMIT 1")
            ).fetchone()
            if sys_row:
                system_status = sys_row[0]

    result = ticket_manager.escalate_ticket(ticket_dict, system_status)

    # Update ticket status in DB if escalated
    if result["status"] == "escalated":
        with db_engine.connect() as conn:
            conn.execute(
                text("UPDATE tickets SET status = 'escalated' WHERE id = :tid"),
                {"tid": ticket_id},
            )
            conn.commit()

    output = (
        f"Escalation Result:\n"
        f"  Status: {result['status'].upper()}\n"
        f"  {result['message']}\n"
        f"  PagerDuty Required: {result['pagerduty_required']}\n"
        f"  Email Required: {result['email_required']}"
    )

    if reason:
        output += f"\n  Reason: {reason}"

    return output


def get_tools():
    """Return list of all available tools."""
    return [
        lookup_employee,
        lookup_ticket,
        get_employee_tickets,
        create_ticket,
        check_system_status,
        list_system_issues,
        reset_password,
        request_access,
        request_software_install,
        escalate_ticket,
    ]
