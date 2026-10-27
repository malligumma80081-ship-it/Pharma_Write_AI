import uuid

from pydantic import BaseModel, Field


class AssignmentCreateRequest(BaseModel):
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class AssignmentCompleteRequest(BaseModel):
    comment: str = Field(default="", max_length=5000)


class AssignmentDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approved|changes_requested)$")
    comment: str = Field(default="", max_length=5000)


class AssignmentDraftUpdateRequest(BaseModel):
    content: dict
    comment: str = Field(
        default="Writer update submitted for review.",
        max_length=5000,
    )
