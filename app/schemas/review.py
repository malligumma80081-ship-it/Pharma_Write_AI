
from typing import Any, Literal

from pydantic import BaseModel, Field


class DraftEditRequest(BaseModel):
    content: dict[str, Any]
    comment: str = Field(
        default="Draft edited; review required again.",
        max_length=5000,
    )


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=5000)


class DraftRevisionResponse(BaseModel):
    id: str
    workflow_id: str
    version_number: int
    content: dict[str, Any]
    status: str
    reviewer_comment: str | None
    reviewer_id: str | None
    created_at: str


class DraftReviewResponse(BaseModel):
    current_revision: DraftRevisionResponse
    human_review_required: bool = True
