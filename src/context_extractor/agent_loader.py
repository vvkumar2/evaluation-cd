"""Dynamically load agent information (tools, entities, system prompt)."""

import sys
import re
from pathlib import Path
from typing import Any, Optional
from importlib import import_module


class AgentLoader:
    """Loads tools, entities, and system prompt from an agent directory."""

    def __init__(self, agent_dir: Path | str):
        """
        Initialize loader for an agent directory.
        """
        self.agent_dir = Path(agent_dir)
        if not self.agent_dir.exists():
            raise ValueError(f"Agent directory not found: {agent_dir}")

    def load_tools_schema(self) -> dict:
        """
        Load tool schemas from agent's tools.py.

        Returns:
            Tools schema dict in OpenAI function calling format
        """
        tools_file = self.agent_dir / "tools.py"
        if not tools_file.exists():
            raise FileNotFoundError(f"tools.py not found in {self.agent_dir}")

        # Add agent directory to path for imports
        sys.path.insert(0, str(self.agent_dir))
        sys.path.insert(0, str(self.agent_dir.parent))

        try:
            # Import the get_tools function
            module = import_module(f"{self.agent_dir.name}.tools")
            get_tools = getattr(module, "get_tools")

            # Get tools
            tools = get_tools()

            # Convert to schema format
            tools_schema = {"tools": []}

            for tool in tools:
                # Get JSON schema from args_schema
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
            raise RuntimeError(f"Failed to load tools from {tools_file}: {e}")
        finally:
            # Clean up sys.path
            if str(self.agent_dir) in sys.path:
                sys.path.remove(str(self.agent_dir))
            if str(self.agent_dir.parent) in sys.path:
                sys.path.remove(str(self.agent_dir.parent))

    def load_entity_schema(self) -> dict:
        """
        Load entity schema from entity_schema.yml.

        Returns:
            Entity schema dict
        """
        # Try common filenames
        for filename in ["entity_schema.yml", "entity_schema.yaml", "entities.yml", "entities.yaml"]:
            schema_file = self.agent_dir / filename
            if schema_file.exists():
                try:
                    import yaml

                    with open(schema_file) as f:
                        data = yaml.safe_load(f)

                    # Normalize to our format
                    if isinstance(data, dict):
                        if "entities" in data:
                            return data
                        # If it's flat entity definitions, wrap in "entities"
                        elif all(isinstance(v, dict) for v in data.values()):
                            return {"entities": [{"name": k, **v} for k, v in data.items()]}

                    return {"entities": data if isinstance(data, list) else [data]}

                except Exception as e:
                    raise RuntimeError(f"Failed to load entity schema from {schema_file}: {e}")

        raise FileNotFoundError(
            f"No entity schema file found in {self.agent_dir} "
            "(looked for: entity_schema.yml, entity_schema.yaml, entities.yml, entities.yaml)"
        )

    def load_system_prompt(self) -> str:
        """
        Extract system prompt from agent.py.

        Returns:
            System prompt string
        """
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
            raise RuntimeError(f"Failed to extract system prompt from {agent_file}: {e}")

    def load_all(self) -> dict:
        """
        Load tools, entities, and system prompt.

        Returns:
            Dict with 'tools', 'entities', 'system_prompt' keys
        """
        return {
            "tools_schema": self.load_tools_schema(),
            "entity_schema": self.load_entity_schema(),
            "system_prompt": self.load_system_prompt(),
        }


def load_agent(agent_dir: Path | str) -> dict:
    """
    Convenience function to load all agent data.

    Args:
        agent_dir: Path to agent directory

    Returns:
        Dict with tools_schema, entity_schema, system_prompt
    """
    loader = AgentLoader(agent_dir)
    return loader.load_all()
