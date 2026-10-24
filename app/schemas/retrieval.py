
from pydantic import BaseModel, Field, model_validator


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_ids: list[str] | None = Field(
        default=None,
        max_length=50,
    )
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_page_range(self):
        if (
            self.page_from is not None
            and self.page_to is not None
            and self.page_from > self.page_to
        ):
            raise ValueError("page_from cannot exceed page_to.")
        return self


class SearchResult(BaseModel):
    chunk_id: str
    project_id: str
    document_id: str
    filename: str
    page_start: int
    page_end: int
    chunk_index: int
    text: str
    distance: float


class SearchResponse(BaseModel):
    query: str
    project_id: str
    result_count: int
    results: list[SearchResult]
