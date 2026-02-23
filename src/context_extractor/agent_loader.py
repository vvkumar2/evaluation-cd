import re
import sys
from importlib import import_module
from pathlib import Path
import yaml

from ..config import (
    AGENT_TOOLS_FILE,
    AGENT_ENTRY_FILE,
    AGENT_ENTITY_SCHEMA_FILE,
    AGENT_SYSTEM_PROMPT_VAR,
    AGENT_GET_TOOLS_FUNC,
)


class AgentLoader:
    def __init__(self, agent_dir: Path | str):
        self.agent_dir = Path(agent_dir)
        if not self.agent_dir.exists():
            raise ValueError(f"Agent directory not found: {agent_dir}")

    def load_tools_schema(self) -> dict:
        """Load tools from the agent's tools file and external tools from entity schema."""
        tools_file = self.agent_dir / AGENT_TOOLS_FILE
        if not tools_file.exists():
            raise FileNotFoundError(f"{AGENT_TOOLS_FILE} not found in {self.agent_dir}")

        tools_module_name = AGENT_TOOLS_FILE.removesuffix(".py")

        sys.path.insert(0, str(self.agent_dir))
        sys.path.insert(0, str(self.agent_dir.parent))

        try:
            module = import_module(f"{self.agent_dir.name}.{tools_module_name}")
            get_tools_fn = getattr(module, AGENT_GET_TOOLS_FUNC)
            tools = get_tools_fn()

            tools_schema = {"tools": []}
            for tool in tools:
                args_json_schema = tool.args_schema.model_json_schema()

                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": args_json_schema.get("properties", {}),
                            "required": args_json_schema.get("required", []),
                        },
                    },
                }

                tools_schema["tools"].append(tool_def)

            # Merge external tools from entity schema (e.g., MCP tools)
            entity_data = self.load_entity_schema()
            for ext_tool in entity_data.get("external_tools", []):
                properties = {}
                required = []
                for param_name, param_def in ext_tool.get("parameters", {}).items():
                    properties[param_name] = {
                        "type": param_def.get("type", "string"),
                        "description": param_def.get("description", ""),
                    }
                    if param_def.get("required", False):
                        required.append(param_name)

                tool_def = {
                    "type": "function",
                    "function": {
                        "name": ext_tool["name"],
                        "description": ext_tool.get("description", ""),
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
                tools_schema["tools"].append(tool_def)

            return tools_schema

        except Exception as e:
            raise RuntimeError(f"Failed to load tools from {tools_file}: {e}") from e
        finally:
            if str(self.agent_dir) in sys.path:
                sys.path.remove(str(self.agent_dir))
            if str(self.agent_dir.parent) in sys.path:
                sys.path.remove(str(self.agent_dir.parent))

    def load_entity_schema(self) -> dict:
        """Load entities from entity schema file."""
        schema_file = self.agent_dir / AGENT_ENTITY_SCHEMA_FILE
        if not schema_file.exists():
            raise FileNotFoundError(
                f"{AGENT_ENTITY_SCHEMA_FILE} not found in {self.agent_dir}"
            )

        with open(schema_file) as f:
            return yaml.safe_load(f)

    def load_system_prompt(self) -> str:
        """Load system prompt from agent entry file."""
        agent_file = self.agent_dir / AGENT_ENTRY_FILE
        if not agent_file.exists():
            raise FileNotFoundError(f"{AGENT_ENTRY_FILE} not found in {self.agent_dir}")

        content = agent_file.read_text()
        var = AGENT_SYSTEM_PROMPT_VAR
        patterns = [
            rf'{var}\s*=\s*"""(.*?)"""',
            rf"{var}\s*=\s*'''(.*?)'''",
            rf'{var}\s*=\s*"(.*?)"',
            rf"{var}\s*=\s*'(.*?)'",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()

        raise ValueError(
            f"{AGENT_SYSTEM_PROMPT_VAR} constant not found in {AGENT_ENTRY_FILE}"
        )

    def load_all(self) -> tuple[dict, dict, str]:
        return (
            self.load_tools_schema(),
            self.load_entity_schema(),
            self.load_system_prompt(),
        )


def load_agent(agent_dir: Path | str) -> tuple[dict, dict, str]:
    loader = AgentLoader(agent_dir)
    return loader.load_all()
