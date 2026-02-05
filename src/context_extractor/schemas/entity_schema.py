from typing import Optional
from pydantic import BaseModel, Field


# Base entity schema models
class EntityField(BaseModel):
    name: str
    type: str
    description: str
    required: bool = False
    enum: Optional[list[str]] = None


class EntityThreshold(BaseModel):
    name: str
    value: float | str
    description: str
    unit: Optional[str] = None


class EntitySchema(BaseModel):
    name: str
    description: str
    fields: list[EntityField]


class EntitySchemaList(BaseModel):
    entities: list[EntitySchema]


# Final enriched entity schema after parsing LLM responses
class EnrichedEntitySchema(BaseModel):
    name: str
    description: str
    fields: list[EntityField]
    thresholds: list[EntityThreshold] = Field(default_factory=list)


class EnrichedEntitySchemaList(BaseModel):
    entities: list[EnrichedEntitySchema]


# LLM output schemas
class EnrichedEntityThresholdItem(BaseModel):
    name: str
    thresholds: list[EntityThreshold] = Field(default_factory=list)


class EnrichedEntityThresholdList(BaseModel):
    entities: list[EnrichedEntityThresholdItem]
