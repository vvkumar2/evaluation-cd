"""CLI/subprocess agent executor."""

import json
import shlex
import subprocess
from typing import Optional

from agenteval.executor.interface import AgentInterface, AgentResponse, AgentError


class CLIAgent(AgentInterface):
    """Execute agent as a CLI subprocess.

    The agent is expected to:
    - Accept a message via stdin or as a command-line argument
    - Output its response to stdout
    - Exit with code 0 on success

    Supported invocation patterns:
    1. Pipe mode: echo "message" | python agent.py
    2. Arg mode: python agent.py "message"
    3. JSON mode: python agent.py --json '{"message": "..."}'
    """

    def __init__(
        self,
        command: str,
        mode: str = "pipe",
        timeout: int = 60,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ):
        """Initialize CLI agent.

        Args:
            command: The command to execute (e.g., "python agent.py").
            mode: How to pass the message ("pipe", "arg", or "json").
            timeout: Maximum time to wait for response in seconds.
            cwd: Working directory for the subprocess.
            env: Additional environment variables.
        """
        self.command = command
        self.mode = mode
        self.timeout = timeout
        self.cwd = cwd
        self.env = env

    def send(self, message: str) -> str:
        """Send a message to the agent via subprocess."""
        try:
            if self.mode == "pipe":
                return self._send_pipe(message)
            elif self.mode == "arg":
                return self._send_arg(message)
            elif self.mode == "json":
                return self._send_json(message)
            else:
                raise AgentError(f"Unknown mode: {self.mode}")

        except subprocess.TimeoutExpired:
            raise AgentError(f"Agent timed out after {self.timeout} seconds")
        except subprocess.CalledProcessError as e:
            raise AgentError(f"Agent exited with code {e.returncode}: {e.stderr}", cause=e)
        except FileNotFoundError as e:
            raise AgentError(f"Command not found: {self.command}", cause=e)
        except Exception as e:
            raise AgentError(f"Error executing agent: {e}", cause=e)

    def _send_pipe(self, message: str) -> str:
        """Send message via stdin pipe."""
        args = shlex.split(self.command)

        result = subprocess.run(
            args,
            input=message,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=self.cwd,
            env=self._get_env(),
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                args,
                result.stdout,
                result.stderr,
            )

        return result.stdout.strip()

    def _send_arg(self, message: str) -> str:
        """Send message as command-line argument."""
        args = shlex.split(self.command) + [message]

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=self.cwd,
            env=self._get_env(),
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                args,
                result.stdout,
                result.stderr,
            )

        return result.stdout.strip()

    def _send_json(self, message: str) -> str:
        """Send message as JSON argument."""
        payload = json.dumps({"message": message})
        args = shlex.split(self.command) + ["--json", payload]

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=self.cwd,
            env=self._get_env(),
        )

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                args,
                result.stdout,
                result.stderr,
            )

        # Try to parse JSON response
        output = result.stdout.strip()
        try:
            data = json.loads(output)
            return data.get("response", data.get("text", output))
        except json.JSONDecodeError:
            return output

    def send_with_metadata(self, message: str) -> AgentResponse:
        """Send message and parse structured response if available."""
        try:
            # Try JSON mode for structured response
            payload = json.dumps({"message": message})
            args = shlex.split(self.command) + ["--json", payload]

            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.cwd,
                env=self._get_env(),
            )

            if result.returncode != 0:
                # Fall back to regular send
                text = self.send(message)
                return AgentResponse(text=text)

            output = result.stdout.strip()
            try:
                data = json.loads(output)
                return AgentResponse(
                    text=data.get("response", data.get("text", output)),
                    citations=data.get("citations", []),
                    confidence=data.get("confidence"),
                    metadata=data.get("metadata", {}),
                )
            except json.JSONDecodeError:
                return AgentResponse(text=output)

        except Exception:
            # Fall back to regular send
            text = self.send(message)
            return AgentResponse(text=text)

    def reset(self) -> None:
        """Reset agent state (no-op for stateless CLI agents)."""
        pass

    def _get_env(self) -> Optional[dict]:
        """Get environment variables for subprocess."""
        if not self.env:
            return None

        import os

        env = os.environ.copy()
        env.update(self.env)
        return env

