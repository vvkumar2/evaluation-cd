"""Execute agent with test cases."""

import os
import sys
from importlib import import_module
from pathlib import Path
from sqlalchemy import text
from ..test_generator.schemas import GeneratedTestCase


class AgentExecutor:
    """Execute agent with test cases."""

    def __init__(self, agent_dir: Path | str):
        """
        Initialize executor.

        Args:
            agent_dir: Path to agent directory
        """
        self.agent_dir = Path(agent_dir)
        self._import_agent()

    def _import_agent(self):
        """Import agent module and set up database connection."""
        agent_dir_str = str(self.agent_dir)
        agent_parent_str = str(self.agent_dir.parent)

        # Set test mode env vars BEFORE importing tools (read at module load time)
        os.environ["AGENT_TEST_MODE"] = "true"
        test_db_path = self.agent_dir / "test_agent.db"
        os.environ["TEST_DB_URL"] = f"sqlite:///{test_db_path.absolute()}"

        # Add paths for imports
        if agent_dir_str not in sys.path:
            sys.path.insert(0, agent_dir_str)
        if agent_parent_str not in sys.path:
            sys.path.insert(0, agent_parent_str)

        # Import tools FIRST using the same module name agent.py will use
        # This ensures we get the same db_engine instance
        try:
            tools_module = import_module("tools")
            self._db_engine = tools_module.db_engine

            # Now import agent.py which will use the same tools module
            self.agent_module = import_module("agent")
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import agent from {self.agent_dir}: {e}"
            ) from e

    def execute_test(self, test_case: GeneratedTestCase) -> str:
        """
        Execute a test case against the agent.

        Args:
            test_case: The test case to execute

        Returns:
            Agent's response as a string
        """
        self._setup_backend(test_case.backend_state)

        try:
            response = self.agent_module.handle_message(
                test_case.input.message,
                test_case.input.context,
            )
            return str(response)
        except Exception as e:
            raise RuntimeError(f"Agent execution failed: {e}") from e
        finally:
            self._cleanup_backend()

    def _setup_backend(self, backend_state: dict[str, list[dict]]):
        """Seed the test SQLite database with test-specific data."""
        customers = backend_state.get("customers", [])
        orders = backend_state.get("orders", [])

        with self._db_engine.connect() as conn:
            conn.execute(text("DELETE FROM orders"))
            conn.execute(text("DELETE FROM customers"))

            if customers:
                conn.execute(
                    text(
                        "INSERT INTO customers (id, name, tier, email) "
                        "VALUES (:id, :name, :tier, :email)"
                    ),
                    customers,
                )

            if orders:
                conn.execute(
                    text(
                        "INSERT INTO orders "
                        "(id, customer_id, price, status, delivered_date_days_ago) "
                        "VALUES (:id, :customer_id, :price, :status, :delivered_date_days_ago)"
                    ),
                    orders,
                )

            conn.commit()

    def _cleanup_backend(self):
        """Clear all test data from the database."""
        with self._db_engine.connect() as conn:
            conn.execute(text("DELETE FROM orders"))
            conn.execute(text("DELETE FROM customers"))
            conn.commit()
