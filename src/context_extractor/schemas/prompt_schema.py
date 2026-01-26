"""Pydantic models for system prompt extraction."""

from typing import Optional
from pydantic import BaseModel, Field


class IntentRule(BaseModel):
    """A rule for how an intent should behave."""

    description: str = Field(..., description="Description of the rule")
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions when this rule applies",
    )
    actions: list[str] = Field(
        ..., description="What to do when rule applies"
    )
    additionalProperties: bool = False


class IntentOutcome(BaseModel):
    """Possible outcome of an intent."""

    outcome_name: str = Field(..., description="Name of the outcome")
    description: str = Field(..., description="Description of this outcome")
    triggering_conditions: list[str] = Field(
        ..., description="Conditions that trigger this outcome"
    )
    additionalProperties: bool = False


class Intent(BaseModel):
    """An intent the agent can handle."""

    name: str = Field(..., description="Intent name (e.g., 'process_refund')")
    description: str = Field(..., description="What this intent does")
    trigger_examples: list[str] = Field(
        ..., description="Example customer messages that trigger this intent"
    )
    required_slots: list[str] = Field(
        default_factory=list,
        description="Required information to fulfill intent",
    )
    workflow: list[str] = Field(
        default_factory=list,
        description="Steps in the workflow for this intent",
    )
    rules: list[IntentRule] = Field(
        default_factory=list,
        description="Rules for how this intent is handled",
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether intent requires user confirmation",
    )
    outcomes: list[IntentOutcome] = Field(
        default_factory=list,
        description="Possible outcomes of this intent",
    )
    additionalProperties: bool = False


class GlobalRule(BaseModel):
    """Global rule that applies across intents."""

    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="What the rule enforces")
    applies_to: list[str] = Field(
        ..., description="Intent names this rule applies to"
    )
    behavior: str = Field(..., description="How to enforce this rule")
    additionalProperties: bool = False


class Refusal(BaseModel):
    """Something the agent should refuse to do."""

    reason: str = Field(..., description="Why the agent refuses")
    trigger_patterns: list[str] = Field(
        ..., description="Patterns that trigger refusal (e.g., requests that imply this)"
    )
    response: str = Field(..., description="How the agent should respond")
    additionalProperties: bool = False


class SystemPromptExtraction(BaseModel):
    """Extracted business logic from system prompt."""

    agent_name: str = Field(..., description="Name of the agent")
    agent_role: str = Field(..., description="Role/purpose of the agent")
    intents: list[Intent] = Field(
        ..., description="Intents the agent can handle"
    )
    global_rules: list[GlobalRule] = Field(
        default_factory=list,
        description="Rules that apply globally",
    )
    refusals: list[Refusal] = Field(
        default_factory=list,
        description="Things the agent should refuse",
    )
    personality_traits: list[str] = Field(
        default_factory=list,
        description="Personality characteristics (e.g., 'professional', 'empathetic')",
    )
    additionalProperties: bool = False
