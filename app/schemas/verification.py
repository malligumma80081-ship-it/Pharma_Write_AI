"""Claim verification API schemas."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidenceCitation as SourceCitation


class ClaimToVerify(BaseModel):
    claim_id: str = Field(min_length=1, max_length=100)
    statement: str = Field(min_length=5, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class ClaimVerificationRequest(BaseModel):
    claims: list[ClaimToVerify] = Field(min_length=1, max_length=50)
    citations: list[SourceCitation] = Field(min_length=1, max_length=100)

class ClaimAssessment(BaseModel):
    claim_id: str
    statement: str
    verdict: Literal[
        "supported",
        "partially_supported",
        "contradicted",
        "insufficient_evidence",
    ]
    explanation: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)


class ClaimVerificationResponse(BaseModel):
    project_id: str
    status: str
    assessments: list[ClaimAssessment]
    warnings: list[str]