"""Evidence API schemas."""
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceField(BaseModel):
    value: str = Field(
        description=(
            "Value explicitly reported in the supplied evidence. "
            "If not reported, say 'Not reported in retrieved evidence'."
        )
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting this field, such as E1 or E2.",
    )
    status: Literal[
        "reported",
        "not_reported",
        "conflicting",
        "uncertain",
    ]


class StudyEvidenceExtraction(BaseModel):
    study_design: EvidenceField
    study_population: EvidenceField
    sample_size: EvidenceField
    intervention: EvidenceField
    comparator: EvidenceField
    endpoints: EvidenceField
    outcomes: EvidenceField
    adverse_events: EvidenceField
    study_limitations: EvidenceField


class EvidenceExtractionRequest(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    top_k: int = Field(default=12, ge=1, le=20)
    document_ids: list[str] | None = Field(
        default=None,
        max_length=50,
    )


class EvidenceCitation(BaseModel):
    evidence_id: str
    chunk_id: str
    document_id: str
    filename: str
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)


class EvidenceExtractionResponse(BaseModel):
    project_id: str
    extraction_id: str
    status: str
    evidence: StudyEvidenceExtraction
    citations: list[EvidenceCitation]
    warnings: list[str]