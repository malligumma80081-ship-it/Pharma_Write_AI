import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Document, Project
from app.db.session import get_db
from app.schemas.verification import (
    ClaimVerificationRequest,
    ClaimVerificationResponse,
)
from app.services.claim_verifier import (
    VerificationCitationError,
    verify_claim,
)
from app.services.ollama_client import OllamaError


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Claim Verification"],
)


@router.post(
    "/{project_id}/claims/verify",
    response_model=ClaimVerificationResponse,
)
def verify_claims(
    project_id: int,
    request: ClaimVerificationRequest,
    db: Session = Depends(get_db),
) -> ClaimVerificationResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        )

    evidence_ids = [citation.evidence_id for citation in request.citations]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise HTTPException(
            status_code=422,
            detail="Duplicate evidence IDs are not allowed",
        )

    document_ids: set[uuid.UUID] = set()
    for citation in request.citations:
        try:
            document_ids.add(uuid.UUID(citation.document_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Invalid document ID in citation",
            ) from exc

    documents = (
        db.query(Document.id)
        .filter(
            Document.project_id == project_id,
            Document.id.in_(document_ids),
        )
        .all()
    )
    if len(documents) != len(document_ids):
        raise HTTPException(
            status_code=422,
            detail="A cited document does not belong to this project",
        )

    citation_lookup = {
        citation.evidence_id: {
            **citation.model_dump(),
            "project_id": str(project_id),
        }
        for citation in request.citations
    }

    warnings = [
        "LLM verdicts are preliminary assessments, not proof of scientific accuracy.",
        "A qualified medical writer must review claims against the original source.",
    ]
    assessments = []

    try:
        for claim in request.claims:
            if not set(claim.evidence_ids).issubset(citation_lookup):
                raise VerificationCitationError(
                    f"Claim {claim.claim_id} contains an unknown evidence ID"
                )
            assessments.append(verify_claim(claim, citation_lookup))
    except VerificationCitationError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Citation validation failed; review the supplied source "
                "references"
            ),
        ) from exc
    except OllamaError as exc:
        raise HTTPException(
            status_code=503,
            detail="The local LLM service is unavailable",
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="The verifier returned an invalid result",
        ) from exc

    return ClaimVerificationResponse(
        project_id=str(project_id),
        status="human_review_required",
        assessments=assessments,
        warnings=warnings,
    )
