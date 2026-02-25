"""Execute agent with test cases."""

import inspect
import os
from pathlib import Path
from sqlalchemy import text
from ..test_generator.schemas import GeneratedTestCase
from ..config import cfg
from ..context_extractor.agent_loader import _load_module_from_file
from .mock_interceptor import MockToolInterceptor


class AgentExecutor:
    """Execute agent with test cases."""

    def __init__(self, agent_dir: Path | str):
        """
        Initialize executor.

        Args:
            agent_dir: Path to agent directory
        """
        self.agent_dir = Path(agent_dir)
        self._tools = None
        self._mcp_stack = None
        self._interceptor = None
        self._import_agent()

    def _import_agent(self):
        """Import agent module and set up database connection."""
        tools_module_name = cfg.AGENT_TOOLS_FILE.removesuffix(".py")
        agent_module_name = cfg.AGENT_ENTRY_FILE.removesuffix(".py")

        # Set test mode env vars BEFORE importing tools (read at module load time)
        os.environ["AGENT_TEST_MODE"] = "true"
        test_db_path = self.agent_dir / "test_agent.db"
        os.environ["TEST_DB_URL"] = f"sqlite:///{test_db_path.absolute()}"

        tools_file = self.agent_dir / cfg.AGENT_TOOLS_FILE
        agent_file = self.agent_dir / cfg.AGENT_ENTRY_FILE

        # Import tools FIRST so the agent module reuses the same instance
        try:
            tools_module = _load_module_from_file(tools_file, tools_module_name)
            self._db_engine = getattr(tools_module, cfg.AGENT_DB_ENGINE_ATTR)

            self.agent_module = _load_module_from_file(agent_file, agent_module_name)
            self._handle_message = getattr(
                self.agent_module, cfg.AGENT_HANDLE_MESSAGE_FUNC
            )
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                f"Failed to import agent from {self.agent_dir}: {e}"
            ) from e

    async def setup_tools(self, external_tools: list[dict] = None):
        """Load all tools (including MCP) once. Must be called before execute_test.

        Args:
            external_tools: External tool definitions from schema.yml.
                Used to build mock responses so real APIs are not called.
        """
        load_all_tools = getattr(self.agent_module, "load_all_tools", None)
        if not load_all_tools:
            raise RuntimeError("Agent module does not export load_all_tools()")

        mock_responses = {}
        if external_tools:
            for tool_def in external_tools:
                mock_responses[tool_def["name"]] = tool_def.get("mock_response", "OK")

        self._interceptor = MockToolInterceptor(mock_responses)
        self._tools, self._mcp_stack = await load_all_tools(
            tool_interceptors=[self._interceptor]
        )

    async def cleanup_tools(self):
        """Close MCP session if one was opened."""
        if self._mcp_stack:
            await self._mcp_stack.aclose()
            self._mcp_stack = None

    async def execute_test(self, test_case: GeneratedTestCase) -> tuple[str, list[str]]:
        """
        Execute a test case against the agent.

        Args:
            test_case: The test case to execute

        Returns:
            Tuple of (agent response text, list of tool names called)
        """
        self._setup_backend(test_case.backend_state)
        if self._interceptor:
            self._interceptor.set_overrides(test_case.mock_tool_responses)

        try:
            result = self._handle_message(
                test_case.input.message,
                test_case.input.context,
                self._tools,
            )
            if inspect.isawaitable(result):
                result = await result
            response, tool_calls = result
            return str(response), tool_calls
        except Exception as e:
            raise RuntimeError(f"Agent execution failed: {e}") from e
        finally:
            if self._interceptor:
                self._interceptor.set_overrides(None)
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
