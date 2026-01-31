from pydantic import BaseModel, Field


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
    triggering_conditions: list[str]

class Intent(BaseModel):
    name: str
    description: str
    trigger_examples: list[str]
    required_slots: list[IntentRequiredSlot] = Field(default_factory=list)
    workflow: list[str] = Field(default_factory=list)
    rules: list[IntentRule] = Field(default_factory=list)
    requires_confirmation: bool = False
    outcomes: list[IntentOutcome] = Field(default_factory=list)

class GlobalRule(BaseModel):
    name: str
    description: str
    applies_to: list[str]
    behavior: str

class Refusal(BaseModel):
    reason: str
    trigger_patterns: list[str]
    response: str

class SystemPromptExtraction(BaseModel):
    agent_name: str
    agent_role: str
    intents: list[Intent]
    global_rules: list[GlobalRule] = Field(default_factory=list)
    refusals: list[Refusal] = Field(default_factory=list)
