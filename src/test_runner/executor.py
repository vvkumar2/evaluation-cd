"""Execute agent with test cases."""

import sys
from importlib import import_module
from pathlib import Path
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
        """Import agent module and backend service."""
        agent_dir_str = str(self.agent_dir)
        agent_parent_str = str(self.agent_dir.parent)

        # Add paths for imports
        if agent_dir_str not in sys.path:
            sys.path.insert(0, agent_dir_str)
        if agent_parent_str not in sys.path:
            sys.path.insert(0, agent_parent_str)

        # Import agent and backend service
        try:
            # Import tools FIRST using the same module name agent.py will use
            # This ensures we get the same BackendService instance
            tools_module = import_module("tools")
            self.backend_service = tools_module.backend_service

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
        # Setup backend with test data
        self._setup_backend(test_case.backend_state)

        try:
            # Call agent
            response = self.agent_module.handle_message(
                test_case.input.message,
                test_case.input.context,
            )
            return str(response)
        except Exception as e:
            raise RuntimeError(f"Agent execution failed: {e}") from e
        finally:
            # Cleanup
            self._cleanup_backend()

    def _setup_backend(self, backend_state: dict[str, list[dict]]):
        """Setup backend service with test data."""
        # Populate orders
        if "orders" in backend_state:
            self.backend_service.orders.clear()
            for order in backend_state["orders"]:
                self.backend_service.orders[order["id"]] = order

        # Populate customers
        if "customers" in backend_state:
            self.backend_service.customers.clear()
            for customer in backend_state["customers"]:
                self.backend_service.customers[customer["id"]] = customer

    def _cleanup_backend(self):
        """Clean up backend service after test."""
        self.backend_service.orders.clear()
        self.backend_service.customers.clear()
