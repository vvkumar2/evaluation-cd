"""
SQLite database setup and management for the IT helpdesk agent.

Provides schema creation, sample data seeding, and test data management.
In test mode (AGENT_TEST_MODE=true), uses a separate test database.
"""

import os
from sqlalchemy import text


def get_db_url() -> str:
    """Get database URL based on test mode environment variable."""
    if os.getenv("AGENT_TEST_MODE") == "true":
        return os.getenv("TEST_DB_URL", "sqlite:///test_agent.db")
    return "sqlite:///helpdesk.db"


def create_schema(engine) -> None:
    """Create database tables if they don't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS employees (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                department TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                mfa_enabled BOOLEAN NOT NULL DEFAULT 0,
                account_status TEXT NOT NULL DEFAULT 'active'
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'low',
                status TEXT NOT NULL DEFAULT 'open',
                description TEXT NOT NULL DEFAULT '',
                assigned_to TEXT,
                created_at TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS systems (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'operational',
                last_checked TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS access_permissions (
                id TEXT PRIMARY KEY,
                employee_id TEXT NOT NULL,
                system_id TEXT NOT NULL,
                permission_level TEXT NOT NULL DEFAULT 'read',
                granted_by TEXT NOT NULL,
                expires_at TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS software_catalog (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                requires_approval BOOLEAN NOT NULL DEFAULT 0,
                approved_roles TEXT NOT NULL DEFAULT ''
            )
        """))
        conn.commit()


def seed_sample_data(engine) -> None:
    """Seed database with sample data if tables are empty."""
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM employees")).scalar()
        if count > 0:
            return

        conn.execute(
            text(
                "INSERT INTO employees (id, name, email, department, role, mfa_enabled, account_status) "
                "VALUES (:id, :name, :email, :department, :role, :mfa_enabled, :account_status)"
            ),
            [
                {
                    "id": "EMP-001",
                    "name": "Alice Chen",
                    "email": "alice@company.com",
                    "department": "engineering",
                    "role": "admin",
                    "mfa_enabled": True,
                    "account_status": "active",
                },
                {
                    "id": "EMP-002",
                    "name": "Bob Martinez",
                    "email": "vvkumar5623@gmail.com",
                    "department": "sales",
                    "role": "user",
                    "mfa_enabled": True,
                    "account_status": "active",
                },
                {
                    "id": "EMP-003",
                    "name": "Carol Davis",
                    "email": "carol@company.com",
                    "department": "hr",
                    "role": "user",
                    "mfa_enabled": False,
                    "account_status": "locked",
                },
                {
                    "id": "EMP-004",
                    "name": "David Lee",
                    "email": "david@company.com",
                    "department": "engineering",
                    "role": "user",
                    "mfa_enabled": False,
                    "account_status": "disabled",
                },
                {
                    "id": "EMP-005",
                    "name": "Eve Wilson",
                    "email": "eve@company.com",
                    "department": "engineering",
                    "role": "admin",
                    "mfa_enabled": True,
                    "account_status": "active",
                },
            ],
        )

        conn.execute(
            text(
                "INSERT INTO tickets (id, employee_id, category, priority, status, description, assigned_to, created_at) "
                "VALUES (:id, :employee_id, :category, :priority, :status, :description, :assigned_to, :created_at)"
            ),
            [
                {
                    "id": "TKT-001",
                    "employee_id": "EMP-002",
                    "category": "password_reset",
                    "priority": "medium",
                    "status": "open",
                    "description": "Cannot log in to email",
                    "assigned_to": None,
                    "created_at": "2026-03-28",
                },
                {
                    "id": "TKT-002",
                    "employee_id": "EMP-003",
                    "category": "system_issue",
                    "priority": "critical",
                    "status": "in_progress",
                    "description": "VPN Gateway completely down",
                    "assigned_to": "EMP-001",
                    "created_at": "2026-03-30",
                },
                {
                    "id": "TKT-003",
                    "employee_id": "EMP-002",
                    "category": "software_install",
                    "priority": "low",
                    "status": "resolved",
                    "description": "Install Tableau on workstation",
                    "assigned_to": "EMP-005",
                    "created_at": "2026-03-25",
                },
            ],
        )

        conn.execute(
            text(
                "INSERT INTO systems (id, name, status, last_checked) "
                "VALUES (:id, :name, :status, :last_checked)"
            ),
            [
                {
                    "id": "SYS-001",
                    "name": "Email Server",
                    "status": "operational",
                    "last_checked": "2026-04-01T08:00:00",
                },
                {
                    "id": "SYS-002",
                    "name": "VPN Gateway",
                    "status": "outage",
                    "last_checked": "2026-04-01T07:30:00",
                },
                {
                    "id": "SYS-003",
                    "name": "HR Portal",
                    "status": "degraded",
                    "last_checked": "2026-04-01T07:45:00",
                },
                {
                    "id": "SYS-004",
                    "name": "Code Repository",
                    "status": "operational",
                    "last_checked": "2026-04-01T08:00:00",
                },
                {
                    "id": "SYS-005",
                    "name": "CI/CD Pipeline",
                    "status": "operational",
                    "last_checked": "2026-04-01T08:00:00",
                },
            ],
        )

        conn.execute(
            text(
                "INSERT INTO access_permissions (id, employee_id, system_id, permission_level, granted_by, expires_at) "
                "VALUES (:id, :employee_id, :system_id, :permission_level, :granted_by, :expires_at)"
            ),
            [
                {
                    "id": "PERM-001",
                    "employee_id": "EMP-001",
                    "system_id": "SYS-004",
                    "permission_level": "admin",
                    "granted_by": "EMP-001",
                    "expires_at": None,
                },
                {
                    "id": "PERM-002",
                    "employee_id": "EMP-002",
                    "system_id": "SYS-001",
                    "permission_level": "read",
                    "granted_by": "EMP-001",
                    "expires_at": "2026-06-01",
                },
                {
                    "id": "PERM-003",
                    "employee_id": "EMP-003",
                    "system_id": "SYS-003",
                    "permission_level": "write",
                    "granted_by": "EMP-005",
                    "expires_at": "2025-12-31",
                },
            ],
        )

        conn.execute(
            text(
                "INSERT INTO software_catalog (id, name, requires_approval, approved_roles) "
                "VALUES (:id, :name, :requires_approval, :approved_roles)"
            ),
            [
                {
                    "id": "SW-001",
                    "name": "VS Code",
                    "requires_approval": False,
                    "approved_roles": "",
                },
                {
                    "id": "SW-002",
                    "name": "Tableau",
                    "requires_approval": True,
                    "approved_roles": "admin,engineering",
                },
                {
                    "id": "SW-003",
                    "name": "Photoshop",
                    "requires_approval": True,
                    "approved_roles": "admin",
                },
                {
                    "id": "SW-004",
                    "name": "Slack",
                    "requires_approval": False,
                    "approved_roles": "",
                },
                {
                    "id": "SW-005",
                    "name": "Terraform",
                    "requires_approval": True,
                    "approved_roles": "admin,engineering",
                },
            ],
        )

        conn.commit()
