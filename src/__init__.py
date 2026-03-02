"""AgentEval - AI Agent Testing Platform."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("agent-eval")
except PackageNotFoundError:
    __version__ = "0.0.0"
