from typing import Optional
from pydantic import BaseModel, Field


# Base tool schema models
class ToolParameter(BaseModel):
    name: str
    type: str
    description: str
    required: bool = False
    enum: Optional[list[str]] = None

class ToolReturn(BaseModel):
    type: str
    entity_name: Optional[str] = None
    description: str

class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)

class ToolSchemaList(BaseModel):
    tools: list[ToolSchema]

# LLM output schemas
class EnrichedToolReturnItem(BaseModel):
    name: str
    returns: ToolReturn

class EnrichedToolReturnList(BaseModel):
    tools: list[EnrichedToolReturnItem]

# Final enriched tool schema after parsing LLM responses
class EnrichedToolSchema(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)
    returns: ToolReturn

class EnrichedToolSchemaList(BaseModel):
    tools: list[EnrichedToolSchema]
