"""Execute agent with test cases."""

import inspect
import os
from pathlib import Path
import yaml
from sqlalchemy import text
from ..test_generator.schemas import GeneratedTestCase
from ..config import cfg, SCHEMA_FILE
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
        self._entity_map = None  # {table_name: [field_names]} built from schema
        self._import_agent()
        self._load_entity_map()

    def _import_agent(self):
        """Import agent module and set up database connection."""
        tools_module_name = cfg.agent.tools_file.removesuffix(".py")
        agent_module_name = cfg.agent.entry_file.removesuffix(".py")

        # Set test mode env vars BEFORE importing tools (read at module load time)
        os.environ["AGENT_TEST_MODE"] = "true"
        test_db_path = self.agent_dir / "test_agent.db"
        os.environ["TEST_DB_URL"] = f"sqlite:///{test_db_path.absolute()}"

        tools_file = self.agent_dir / cfg.agent.tools_file
        agent_file = self.agent_dir / cfg.agent.entry_file

        # Import tools FIRST so the agent module reuses the same instance
        try:
            tools_module = _load_module_from_file(tools_file, tools_module_name)
            self._db_engine = getattr(tools_module, cfg.backend.db_engine_attr)

            self.agent_module = _load_module_from_file(agent_file, agent_module_name)
            self._handle_message = getattr(
                self.agent_module, cfg.agent.handle_message_func
            )
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                f"Failed to import agent from {self.agent_dir}: {e}"
            ) from e

    def _load_entity_map(self):
        """Build entity map from schema.yml: {table_name: [field_names]}."""
        schema_path = self.agent_dir / SCHEMA_FILE
        with open(schema_path) as f:
            data = yaml.safe_load(f)

        entities = data.get("entities", [])
        # Preserve order for insert/delete sequencing
        self._entity_map = {}
        for entity in entities:
            table = entity.get("table", entity["name"] + "s")
            fields = list(entity.get("fields", {}).keys())
            self._entity_map[table] = fields

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
        """Seed the test database with test-specific data."""
        if cfg.backend.type == "sqlite":
            self._setup_sqlite_backend(backend_state)
        else:
            raise RuntimeError(f"Unsupported backend type: '{cfg.backend.type}'")

    def _cleanup_backend(self):
        """Clear all test data from the database."""
        if cfg.backend.type == "sqlite":
            self._cleanup_sqlite_backend()
        else:
            raise RuntimeError(f"Unsupported backend type: '{cfg.backend.type}'")

    def _setup_sqlite_backend(self, backend_state: dict[str, list[dict]]):
        """Seed the test SQLite database with test-specific data using entity schema."""
        tables = list(self._entity_map.keys())

        with self._db_engine.connect() as conn:
            # Delete in reverse order (handles foreign key constraints)
            for table in reversed(tables):
                conn.execute(text(f"DELETE FROM {table}"))

            # Insert in forward order
            for table in tables:
                rows = backend_state.get(table, [])
                if rows:
                    fields = self._entity_map[table]
                    cols = ", ".join(fields)
                    placeholders = ", ".join(f":{f}" for f in fields)
                    conn.execute(
                        text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"),
                        rows,
                    )

            conn.commit()

    def _cleanup_sqlite_backend(self):
        """Clear all test data from the SQLite database."""
        tables = list(self._entity_map.keys())

        with self._db_engine.connect() as conn:
            for table in reversed(tables):
                conn.execute(text(f"DELETE FROM {table}"))
            conn.commit()
