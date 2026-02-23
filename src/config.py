"""Agent configuration loaded from agent_config.env.

All values are required — missing values raise immediately on import.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load agent_config.env from project root
_config_path = Path(__file__).resolve().parent.parent / "agent_config.env"
load_dotenv(_config_path)


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(
            f"Missing required config: {key} (expected in {_config_path})"
        )
    return val


AGENT_TOOLS_FILE = _require("AGENT_TOOLS_FILE")
AGENT_ENTRY_FILE = _require("AGENT_ENTRY_FILE")
AGENT_ENTITY_SCHEMA_FILE = _require("AGENT_ENTITY_SCHEMA_FILE")
AGENT_SYSTEM_PROMPT_VAR = _require("AGENT_SYSTEM_PROMPT_VAR")
AGENT_GET_TOOLS_FUNC = _require("AGENT_GET_TOOLS_FUNC")
AGENT_HANDLE_MESSAGE_FUNC = _require("AGENT_HANDLE_MESSAGE_FUNC")
AGENT_DB_ENGINE_ATTR = _require("AGENT_DB_ENGINE_ATTR")
