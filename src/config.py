"""Agent configuration loaded lazily from schema.yml inside the agent directory.

Call ``init(agent_dir)`` before accessing ``cfg.*`` attributes.
The only hard-coded convention is the schema filename itself.
"""

from pathlib import Path
import yaml

SCHEMA_FILE = "schema.yml"

# LLM model names per pipeline stage
EXTRACTION_MODEL = "gpt-4o-mini"
ENRICHER_MODEL = "gpt-5-mini"
GENERATION_MODEL = "gpt-4o-mini"
EVALUATION_MODEL = "gpt-4o-mini"

# Pipeline thresholds
PASS_SCORE_THRESHOLD = 7
MIN_PASS_RATE = 1.0
LLM_TIMEOUT = 200

_REQUIRED_AGENT_KEYS = [
    "tools_file",
    "entry_file",
    "system_prompt_var",
    "get_tools_func",
    "handle_message_func",
]


class AgentConfig:
    """Agent-specific configuration from the ``agent:`` section."""

    def __init__(
        self,
        tools_file: str,
        entry_file: str,
        system_prompt_var: str,
        get_tools_func: str,
        handle_message_func: str,
    ):
        self.tools_file = tools_file
        self.entry_file = entry_file
        self.system_prompt_var = system_prompt_var
        self.get_tools_func = get_tools_func
        self.handle_message_func = handle_message_func


class BackendConfig:
    """Base backend configuration."""

    def __init__(self, backend_type: str):
        self.type = backend_type


class SqliteBackendConfig(BackendConfig):
    """SQLite-specific backend configuration."""

    def __init__(self, db_engine_attr: str):
        super().__init__(backend_type="sqlite")
        self.db_engine_attr = db_engine_attr


class Config:
    """Namespace populated by ``init()``."""

    SCHEMA_FILE: str = SCHEMA_FILE
    agent: AgentConfig | None = None
    backend: BackendConfig | None = None


cfg = Config()


def _parse_sqlite_backend(section: dict) -> SqliteBackendConfig:
    """Parse sqlite backend config, requiring db_engine_attr."""
    db_engine_attr = section.get("db_engine_attr")
    if not db_engine_attr:
        raise RuntimeError(
            "Missing required key 'db_engine_attr' in backend section for sqlite backend"
        )
    return SqliteBackendConfig(db_engine_attr=db_engine_attr)


def init(agent_dir: str | Path) -> None:
    """Read ``schema.yml`` from *agent_dir* and populate ``cfg``."""
    schema_path = Path(agent_dir) / SCHEMA_FILE
    if not schema_path.exists():
        raise FileNotFoundError(f"{SCHEMA_FILE} not found in {agent_dir}")

    with open(schema_path) as f:
        data = yaml.safe_load(f)

    # Parse agent section
    agent_section = data.get("agent")
    if not agent_section:
        raise RuntimeError(f"Missing 'agent' section in {schema_path}")

    missing = [k for k in _REQUIRED_AGENT_KEYS if k not in agent_section]
    if missing:
        raise RuntimeError(
            f"Missing required keys in agent section of {schema_path}: {missing}"
        )

    cfg.agent = AgentConfig(
        tools_file=agent_section["tools_file"],
        entry_file=agent_section["entry_file"],
        system_prompt_var=agent_section["system_prompt_var"],
        get_tools_func=agent_section["get_tools_func"],
        handle_message_func=agent_section["handle_message_func"],
    )

    # Parse backend section
    backend_section = data.get("backend")
    if not backend_section:
        raise RuntimeError(f"Missing 'backend' section in {schema_path}")

    backend_type = backend_section.get("type")
    if not backend_type:
        raise RuntimeError(f"Missing 'type' in backend section of {schema_path}")

    if backend_type == "sqlite":
        cfg.backend = _parse_sqlite_backend(backend_section)
    else:
        raise RuntimeError(
            f"Unsupported backend type: '{backend_type}'. Currently only 'sqlite' is supported."
        )
