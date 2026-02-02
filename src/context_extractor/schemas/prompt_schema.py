from typing import Any
from pydantic import BaseModel, Field


class StructuredCondition(BaseModel):
    """A structured condition for a rule."""

    field: str
    operator: str
    value: Any


class StructuredIntentRule(BaseModel):
    """A structured rule with explicit conditions and outcomes."""

    id: str
    description: str
    conditions: list[StructuredCondition]
    outcome: str
    expected_behavior: str


class IntentRequiredSlot(BaseModel):
    """A required slot for an intent with its information source."""

    slot_name: str
    source: str


class IntentRule(BaseModel):
    description: str
    conditions: list[str] = Field(default_factory=list)
    actions: list[str]

class IntentOutcome(BaseModel):
    outcome_name: str
    description: str

class Intent(BaseModel):
    name: str
    description: str
    required_slots: list[IntentRequiredSlot] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    rules: list[IntentRule] = Field(default_factory=list)
    requires_confirmation: bool = False
    outcomes: list[IntentOutcome] = Field(default_factory=list)

class StructuredIntent(BaseModel):
    name: str
    description: str
    required_slots: list[IntentRequiredSlot] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    rules: list[StructuredIntentRule] = Field(default_factory=list)
    requires_confirmation: bool = False
    outcomes: list[IntentOutcome] = Field(default_factory=list)

class SystemPromptExtraction(BaseModel):
    agent_name: str
    agent_role: str
    intents: list[Intent]

class StructuredSystemPromptExtraction(BaseModel):
    agent_name: str
    agent_role: str
    intents: list[StructuredIntent]
