"""
SQLite database setup and management for the customer service agent.

Provides schema creation, sample data seeding, and test data management.
In test mode (AGENT_TEST_MODE=true), uses a separate test database.
"""

import os
from sqlalchemy import text


def get_db_url() -> str:
    """Get database URL based on test mode environment variable."""
    if os.getenv("AGENT_TEST_MODE") == "true":
        return os.getenv("TEST_DB_URL", "sqlite:///test_agent.db")
    return "sqlite:///techgear.db"


def create_schema(engine) -> None:
    """Create database tables if they don't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tier TEXT NOT NULL,
                email TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL,
                delivered_date_days_ago INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.commit()


def seed_sample_data(engine) -> None:
    """Seed database with sample data if tables are empty."""
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM customers")).scalar()
        if count > 0:
            return

        conn.execute(
            text(
                "INSERT INTO customers (id, name, tier, email) "
                "VALUES (:id, :name, :tier, :email)"
            ),
            [
                {
                    "id": "CUST-001",
                    "name": "John Doe",
                    "tier": "standard",
                    "email": "john@example.com",
                },
                {
                    "id": "CUST-002",
                    "name": "Jane Smith",
                    "tier": "gold",
                    "email": "jane@example.com",
                },
                {
                    "id": "CUST-003",
                    "name": "Bob Johnson",
                    "tier": "platinum",
                    "email": "bob@example.com",
                },
                {
                    "id": "CUST-004",
                    "name": "Alice Williams",
                    "tier": "standard",
                    "email": "alice@example.com",
                },
                {
                    "id": "CUST-005",
                    "name": "Charlie Brown",
                    "tier": "gold",
                    "email": "charlie@example.com",
                },
            ],
        )

        conn.execute(
            text(
                "INSERT INTO orders (id, customer_id, price, status, delivered_date_days_ago) "
                "VALUES (:id, :customer_id, :price, :status, :delivered_date_days_ago)"
            ),
            [
                {
                    "id": "ORD-001",
                    "customer_id": "CUST-001",
                    "price": 75.00,
                    "status": "delivered",
                    "delivered_date_days_ago": 5,
                },
                {
                    "id": "ORD-002",
                    "customer_id": "CUST-002",
                    "price": 250.00,
                    "status": "delivered",
                    "delivered_date_days_ago": 35,
                },
                {
                    "id": "ORD-003",
                    "customer_id": "CUST-003",
                    "price": 1500.00,
                    "status": "delivered",
                    "delivered_date_days_ago": 10,
                },
                {
                    "id": "ORD-004",
                    "customer_id": "CUST-001",
                    "price": 49.99,
                    "status": "shipped",
                    "delivered_date_days_ago": 0,
                },
                {
                    "id": "ORD-005",
                    "customer_id": "CUST-004",
                    "price": 120.00,
                    "status": "processing",
                    "delivered_date_days_ago": 0,
                },
                {
                    "id": "ORD-006",
                    "customer_id": "CUST-002",
                    "price": 199.99,
                    "status": "delivered",
                    "delivered_date_days_ago": 3,
                },
                {
                    "id": "ORD-007",
                    "customer_id": "CUST-005",
                    "price": 55.00,
                    "status": "delivered",
                    "delivered_date_days_ago": 2,
                },
                {
                    "id": "ORD-008",
                    "customer_id": "CUST-003",
                    "price": 89.99,
                    "status": "pending",
                    "delivered_date_days_ago": 0,
                },
            ],
        )
        conn.commit()
