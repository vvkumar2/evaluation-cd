"""Python function agent executor."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Union

from agenteval.executor.interface import AgentInterface, AgentResponse, AgentError


class PythonAgent(AgentInterface):
    """Execute agent as a Python function.

    The agent can be:
    1. A callable function
    2. A path to a Python file with a main() or respond() function
    3. A module path with function name (e.g., "my_agent:respond")
    """

    def __init__(
        self,
        agent: Union[Callable, str, Path],
        function_name: str = "respond",
    ):
        """Initialize Python agent.

        Args:
            agent: Either a callable, a path to a Python file, or a module:function string.
            function_name: Name of the function to call if agent is a file path.
        """
        self._agent_func: Optional[Callable] = None
        self._agent_instance: Any = None

        if callable(agent):
            self._agent_func = agent
        elif isinstance(agent, (str, Path)):
            self._load_agent(str(agent), function_name)
        else:
            raise AgentError(f"Invalid agent type: {type(agent)}")

    def _load_agent(self, agent_path: str, function_name: str) -> None:
        """Load agent from file path or module string."""
        # Check if it's a module:function format
        if ":" in agent_path:
            module_path, func_name = agent_path.rsplit(":", 1)
            self._load_from_module(module_path, func_name)
            return

        path = Path(agent_path)

        if not path.exists():
            raise AgentError(f"Agent file not found: {path}")

        if not path.suffix == ".py":
            raise AgentError(f"Expected .py file, got: {path}")

        self._load_from_file(path, function_name)

    def _load_from_file(self, path: Path, function_name: str) -> None:
        """Load agent from a Python file."""
        try:
            # Add parent directory to path for imports
            parent_dir = str(path.parent.absolute())
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            spec = importlib.util.spec_from_file_location("agent_module", path)
            if spec is None or spec.loader is None:
                raise AgentError(f"Could not load module from {path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules["agent_module"] = module
            spec.loader.exec_module(module)

            # Try to find the function
            if hasattr(module, function_name):
                self._agent_func = getattr(module, function_name)
            elif hasattr(module, "main"):
                self._agent_func = getattr(module, "main")
            elif hasattr(module, "Agent"):
                # If there's an Agent class, instantiate it
                agent_class = getattr(module, "Agent")
                self._agent_instance = agent_class()
                if hasattr(self._agent_instance, function_name):
                    self._agent_func = getattr(self._agent_instance, function_name)
                elif hasattr(self._agent_instance, "respond"):
                    self._agent_func = getattr(self._agent_instance, "respond")
                elif hasattr(self._agent_instance, "__call__"):
                    self._agent_func = self._agent_instance
                else:
                    raise AgentError(
                        f"Agent class has no {function_name}, respond, or __call__ method"
                    )
            else:
                raise AgentError(
                    f"No {function_name} or main function found in {path}"
                )

        except AgentError:
            raise
        except Exception as e:
            raise AgentError(f"Error loading agent from {path}: {e}", cause=e)

    def _load_from_module(self, module_path: str, function_name: str) -> None:
        """Load agent from a module path."""
        try:
            module = importlib.import_module(module_path)

            if hasattr(module, function_name):
                self._agent_func = getattr(module, function_name)
            else:
                raise AgentError(
                    f"Function {function_name} not found in module {module_path}"
                )

        except ImportError as e:
            raise AgentError(f"Could not import module {module_path}: {e}", cause=e)
        except Exception as e:
            raise AgentError(f"Error loading agent from {module_path}: {e}", cause=e)

    def send(self, message: str) -> str:
        """Send a message to the agent function."""
        if self._agent_func is None:
            raise AgentError("Agent function not loaded")

        try:
            result = self._agent_func(message)

            if result is None:
                return ""
            elif isinstance(result, str):
                return result
            elif isinstance(result, dict):
                return result.get("response", result.get("text", str(result)))
            else:
                return str(result)

        except Exception as e:
            raise AgentError(f"Agent raised an exception: {e}", cause=e)

    def send_with_metadata(self, message: str) -> AgentResponse:
        """Send message and capture structured response."""
        if self._agent_func is None:
            raise AgentError("Agent function not loaded")

        try:
            result = self._agent_func(message)

            if result is None:
                return AgentResponse(text="")
            elif isinstance(result, str):
                return AgentResponse(text=result)
            elif isinstance(result, dict):
                return AgentResponse(
                    text=result.get("response", result.get("text", str(result))),
                    citations=result.get("citations", []),
                    confidence=result.get("confidence"),
                    metadata={
                        k: v
                        for k, v in result.items()
                        if k not in ("response", "text", "citations", "confidence")
                    },
                )
            elif isinstance(result, AgentResponse):
                return result
            else:
                return AgentResponse(text=str(result))

        except Exception as e:
            raise AgentError(f"Agent raised an exception: {e}", cause=e)

    def reset(self) -> None:
        """Reset agent state."""
        if self._agent_instance and hasattr(self._agent_instance, "reset"):
            self._agent_instance.reset()

