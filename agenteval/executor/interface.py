"""Agent interface abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentResponse:
    """Response from an agent."""

    text: str
    citations: list[str] = None
    confidence: Optional[float] = None
    metadata: dict = None

    def __post_init__(self):
        if self.citations is None:
            self.citations = []
        if self.metadata is None:
            self.metadata = {}


class AgentInterface(ABC):
    """Abstract base class for agent interfaces."""

    @abstractmethod
    def send(self, message: str) -> str:
        """Send a message to the agent and get a response.

        Args:
            message: The user message to send.

        Returns:
            The agent's response text.

        Raises:
            AgentError: If there's an error communicating with the agent.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the agent's conversation state.

        For single-turn interactions, this may be a no-op.
        """
        pass

    def send_with_metadata(self, message: str) -> AgentResponse:
        """Send a message and get response with metadata.

        Default implementation just wraps send(). Subclasses can override
        to provide richer responses with citations, confidence, etc.

        Args:
            message: The user message to send.

        Returns:
            AgentResponse with text and optional metadata.
        """
        text = self.send(message)
        return AgentResponse(text=text)

    def health_check(self) -> bool:
        """Check if the agent is ready to receive messages.

        Returns:
            True if the agent is healthy, False otherwise.
        """
        try:
            # Try a simple test message
            self.send("Hello")
            return True
        except Exception:
            return False


class AgentError(Exception):
    """Error communicating with an agent."""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        super().__init__(message)
        self.cause = cause

