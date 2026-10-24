from pydantic import BaseModel, Field


class WorkflowCreateRequest(BaseModel):
    research_question: str = Field(
        min_length=5,
        max_length=2000,
    )
    document_ids: list[str] = Field(
        min_length=1,
        max_length=50,
    )
    top_k: int = Field(default=8, ge=1, le=12)


class WorkflowCreateResponse(BaseModel):
    workflow_id: str
    project_id: int
    status: str
    current_stage: str
    message: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    project_id: int
    status: str
    current_stage: str
    result: dict | None = None
    error_message: str | None = None