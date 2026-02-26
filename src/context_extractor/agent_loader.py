import importlib.util
import re
import sys
from pathlib import Path
import yaml

from ..config import cfg


def _load_module_from_file(file_path: Path, module_name: str):
    """Load a Python module directly from a file path.

    Temporarily adds the module's parent directory to sys.path so that
    sibling imports inside the agent code work (e.g. ``from tools import …``).
    """
    parent = str(file_path.parent)
    added = parent not in sys.path
    if added:
        sys.path.insert(0, parent)
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if added and parent in sys.path:
            sys.path.remove(parent)


class AgentLoader:
    def __init__(self, agent_dir: Path | str):
        self.agent_dir = Path(agent_dir)
        if not self.agent_dir.exists():
            raise ValueError(f"Agent directory not found: {agent_dir}")

    def load_tools_schema(self) -> dict:
        """Load tools from the agent's tools file and external tools from entity schema."""
        tools_file = self.agent_dir / cfg.agent.tools_file
        if not tools_file.exists():
            raise FileNotFoundError(
                f"{cfg.agent.tools_file} not found in {self.agent_dir}"
            )

        tools_module_name = cfg.agent.tools_file.removesuffix(".py")

        try:
            module = _load_module_from_file(tools_file, tools_module_name)
            get_tools_fn = getattr(module, cfg.agent.get_tools_func)
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

    def load_entity_schema(self) -> dict:
        """Load entities from entity schema file."""
        schema_file = self.agent_dir / cfg.SCHEMA_FILE
        if not schema_file.exists():
            raise FileNotFoundError(f"{cfg.SCHEMA_FILE} not found in {self.agent_dir}")

        with open(schema_file) as f:
            return yaml.safe_load(f)

    def load_system_prompt(self) -> str:
        """Load system prompt from agent entry file."""
        agent_file = self.agent_dir / cfg.agent.entry_file
        if not agent_file.exists():
            raise FileNotFoundError(
                f"{cfg.agent.entry_file} not found in {self.agent_dir}"
            )

        content = agent_file.read_text()
        var = cfg.agent.system_prompt_var
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
            f"{cfg.agent.system_prompt_var} constant not found in {cfg.agent.entry_file}"
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
