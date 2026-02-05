import re
import sys
from importlib import import_module
from pathlib import Path
import yaml


class AgentLoader:
    def __init__(self, agent_dir: Path | str):
        self.agent_dir = Path(agent_dir)
        if not self.agent_dir.exists():
            raise ValueError(f"Agent directory not found: {agent_dir}")

    def load_tools_schema(self) -> dict:
        """Load tools from tools.py."""
        tools_file = self.agent_dir / "tools.py"
        if not tools_file.exists():
            raise FileNotFoundError(f"tools.py not found in {self.agent_dir}")

        sys.path.insert(0, str(self.agent_dir))
        sys.path.insert(0, str(self.agent_dir.parent))

        try:
            module = import_module(f"{self.agent_dir.name}.tools")
            get_tools = getattr(module, "get_tools")
            tools = get_tools()

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

            return tools_schema

        except Exception as e:
            raise RuntimeError(f"Failed to load tools from {tools_file}: {e}") from e
        finally:
            if str(self.agent_dir) in sys.path:
                sys.path.remove(str(self.agent_dir))
            if str(self.agent_dir.parent) in sys.path:
                sys.path.remove(str(self.agent_dir.parent))

    def load_entity_schema(self) -> dict:
        """Load entities from entity_schema.yml file."""
        for filename in [
            "entity_schema.yml",
            "entity_schema.yaml",
            "entities.yml",
            "entities.yaml",
        ]:
            schema_file = self.agent_dir / filename
            if schema_file.exists():
                try:
                    with open(schema_file) as f:
                        return yaml.safe_load(f)

                except Exception as e:
                    raise RuntimeError(
                        f"Failed to load entity schema from {schema_file}: {e}"
                    ) from e

        raise FileNotFoundError(
            f"No entity schema file found in {self.agent_dir} "
            "(looked for: entity_schema.yml, entity_schema.yaml, entities.yml, entities.yaml)"
        )

    def load_system_prompt(self) -> str:
        """Load system prompt from agent.py."""
        agent_file = self.agent_dir / "agent.py"
        if not agent_file.exists():
            raise FileNotFoundError(f"agent.py not found in {self.agent_dir}")

        try:
            content = agent_file.read_text()
            patterns = [
                r'SYSTEM_PROMPT\s*=\s*"""(.*?)"""',
                r"SYSTEM_PROMPT\s*=\s*'''(.*?)'''",
                r'SYSTEM_PROMPT\s*=\s*"(.*?)"',
                r"SYSTEM_PROMPT\s*=\s*'(.*?)'",
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    return match.group(1).strip()

            raise ValueError("SYSTEM_PROMPT constant not found in agent.py")

        except Exception as e:
            raise RuntimeError(
                f"Failed to extract system prompt from {agent_file}: {e}"
            ) from e

    def load_all(self) -> tuple[dict, dict, str]:
        return (
            self.load_tools_schema(),
            self.load_entity_schema(),
            self.load_system_prompt(),
        )


def load_agent(agent_dir: Path | str) -> tuple[dict, dict, str]:
    loader = AgentLoader(agent_dir)
    return loader.load_all()
