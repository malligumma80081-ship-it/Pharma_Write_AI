"""Draft API schemas."""

from pydantic import BaseModel, Field


class EvidenceClaim(BaseModel):
    statement: str = Field(
        min_length=1,
        description="One factual statement supported by source evidence.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of the supplied evidence passages supporting the statement.",
    )


class EvidenceGap(BaseModel):
    question: str
    reason: str


class LiteratureDraft(BaseModel):
    title: str
    executive_summary: str
    key_findings: list[EvidenceClaim]
    limitations: list[str]
    evidence_gaps: list[EvidenceGap]
    conclusion: str


class LiteratureDraftRequest(BaseModel):
    research_question: str = Field(min_length=5, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=12)
    document_ids: list[str] | None = Field(default=None, max_length=50)
    page_from: int | None = Field(default=None, ge=1)
    page_to: int | None = Field(default=None, ge=1)


class CitationSource(BaseModel):
    evidence_id: str
    chunk_id: str
    document_id: str
    filename: str
    page_start: int
    page_end: int


class LiteratureDraftResponse(BaseModel):
    project_id: str
    status: str
    title: str
    executive_summary: str
    key_findings: list[EvidenceClaim]
    limitations: list[str]
    evidence_gaps: list[EvidenceGap]
    conclusion: str
    citations: list[CitationSource]
    warnings: list[str]
