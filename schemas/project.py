import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    research_question: str = Field(min_length=10, max_length=3000)
    description: str | None = Field(default=None, max_length=5000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    research_question: str | None = Field(
        default=None,
        min_length=10,
        max_length=3000,
    )
    description: str | None = Field(default=None, max_length=5000)
    status: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    research_question: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime