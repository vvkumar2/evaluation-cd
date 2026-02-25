"""Agent configuration loaded lazily from schema.yml inside the agent directory.

Call ``init(agent_dir)`` before accessing ``cfg.*`` attributes.
The only hard-coded convention is the schema filename itself.
"""

from pathlib import Path
import yaml

SCHEMA_FILE = "schema.yml"

_REQUIRED_KEYS = [
    "tools_file",
    "entry_file",
    "system_prompt_var",
    "get_tools_func",
    "handle_message_func",
    "db_engine_attr",
]


class _Config:
    """Namespace populated by ``init()``."""

    SCHEMA_FILE: str = SCHEMA_FILE
    AGENT_TOOLS_FILE: str | None = None
    AGENT_ENTRY_FILE: str | None = None
    AGENT_SYSTEM_PROMPT_VAR: str | None = None
    AGENT_GET_TOOLS_FUNC: str | None = None
    AGENT_HANDLE_MESSAGE_FUNC: str | None = None
    AGENT_DB_ENGINE_ATTR: str | None = None


cfg = _Config()


def init(agent_dir: str | Path) -> None:
    """Read ``schema.yml`` from *agent_dir* and populate ``cfg``."""
    schema_path = Path(agent_dir) / SCHEMA_FILE
    if not schema_path.exists():
        raise FileNotFoundError(f"{SCHEMA_FILE} not found in {agent_dir}")

    with open(schema_path) as f:
        data = yaml.safe_load(f)

    agent_section = data.get("agent")
    if not agent_section:
        raise RuntimeError(f"Missing 'agent' section in {schema_path}")

    missing = [k for k in _REQUIRED_KEYS if k not in agent_section]
    if missing:
        raise RuntimeError(
            f"Missing required keys in agent section of {schema_path}: {missing}"
        )

    cfg.AGENT_TOOLS_FILE = agent_section["tools_file"]
    cfg.AGENT_ENTRY_FILE = agent_section["entry_file"]
    cfg.AGENT_SYSTEM_PROMPT_VAR = agent_section["system_prompt_var"]
    cfg.AGENT_GET_TOOLS_FUNC = agent_section["get_tools_func"]
    cfg.AGENT_HANDLE_MESSAGE_FUNC = agent_section["handle_message_func"]
    cfg.AGENT_DB_ENGINE_ATTR = agent_section["db_engine_attr"]
