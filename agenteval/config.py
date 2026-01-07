"""Configuration handling for AgentEval."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000

    def __post_init__(self):
        # Resolve environment variables in api_key
        if self.api_key and self.api_key.startswith("${") and self.api_key.endswith("}"):
            env_var = self.api_key[2:-1]
            self.api_key = os.environ.get(env_var)


@dataclass
class GenerationConfig:
    """Test generation configuration."""

    count: int = 30
    types: dict = field(default_factory=lambda: {"qa": 0.7, "edge": 0.2, "consistency": 0.1})


@dataclass
class EvaluationConfig:
    """Evaluation settings."""

    weights: dict = field(
        default_factory=lambda: {
            "factual_accuracy": 0.4,
            "completeness": 0.3,
            "citation": 0.15,
            "consistency": 0.1,
            "tone": 0.05,
        }
    )
    pass_threshold: float = 0.7


@dataclass
class Config:
    """Main configuration for AgentEval."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file."""
        if path is None:
            # Look for config in current directory
            path = Path("agenteval.yaml")

        if not path.exists():
            # Return default config if file doesn't exist
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create configuration from dictionary."""
        llm_data = data.get("llm", {})
        gen_data = data.get("generation", {})
        eval_data = data.get("evaluation", {})

        return cls(
            llm=LLMConfig(
                provider=llm_data.get("provider", "openai"),
                model=llm_data.get("model", "gpt-4o-mini"),
                api_key=llm_data.get("api_key"),
                base_url=llm_data.get("base_url"),
                temperature=llm_data.get("temperature", 0.7),
                max_tokens=llm_data.get("max_tokens", 2000),
            ),
            generation=GenerationConfig(
                count=gen_data.get("count", 30),
                types=gen_data.get(
                    "types", {"qa": 0.7, "edge": 0.2, "consistency": 0.1}
                ),
            ),
            evaluation=EvaluationConfig(
                weights=eval_data.get(
                    "weights",
                    {
                        "factual_accuracy": 0.4,
                        "completeness": 0.3,
                        "citation": 0.15,
                        "consistency": 0.1,
                        "tone": 0.05,
                    },
                ),
                pass_threshold=eval_data.get("pass_threshold", 0.7),
            ),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization."""
        return {
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "api_key": "${OPENAI_API_KEY}"
                if self.llm.provider == "openai"
                else "${ANTHROPIC_API_KEY}",
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
            },
            "generation": {
                "count": self.generation.count,
                "types": self.generation.types,
            },
            "evaluation": {
                "weights": self.evaluation.weights,
                "pass_threshold": self.evaluation.pass_threshold,
            },
        }

    def save(self, path: Path) -> None:
        """Save configuration to YAML file."""
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)


def get_default_config_yaml() -> str:
    """Get default configuration as YAML string."""
    return """# AgentEval Configuration

# LLM settings for test generation and evaluation
llm:
  provider: openai  # openai, anthropic, ollama, etc.
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}  # Uses environment variable
  temperature: 0.7
  max_tokens: 2000

# Test generation settings
generation:
  count: 30  # Number of tests to generate
  types:
    qa: 0.7           # 70% simple Q&A
    edge: 0.2         # 20% edge cases
    consistency: 0.1  # 10% consistency tests

# Evaluation settings
evaluation:
  weights:
    factual_accuracy: 0.4
    completeness: 0.3
    citation: 0.15
    consistency: 0.1
    tone: 0.05
  pass_threshold: 0.7
"""

