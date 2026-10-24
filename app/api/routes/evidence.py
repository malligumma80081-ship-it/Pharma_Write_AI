import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Project, Document, StudyEvidence
from app.db.session import get_db
from app.schemas.evidence import (
    EvidenceCitation,
    EvidenceExtractionRequest,
    EvidenceExtractionResponse,
)
from app.services.evidence_extractor import (
    EvidenceCitationError,
    extract_study_evidence,
)
from app.services.ollama_client import OllamaError


router = APIRouter(prefix="/api/v1/projects", tags=["Evidence"])


@router.post(
    "/{project_id}/evidence/extract",
    response_model=EvidenceExtractionResponse,
)
def extract_evidence(
    project_id: int,
    request: EvidenceExtractionRequest,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.document_ids:
        try:
            document_ids = [
                uuid.UUID(document_id)
                for document_id in request.document_ids
            ]
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="One or more document IDs are invalid",
            )

        documents = db.query(Document).filter(
            Document.project_id == project_id,
            Document.id.in_(document_ids),
        ).all()

        if len(documents) != len(set(document_ids)):
            raise HTTPException(
                status_code=422,
                detail="A document does not belong to this project",
            )

    try:
        extraction, citations, warnings = extract_study_evidence(
            project_id=str(project_id),
            query=request.query,
            top_k=request.top_k,
            document_ids=(
                [str(value) for value in document_ids]
                if request.document_ids
                else None
            ),
        )

        status = "draft_requires_human_review"
        validated_citations = [
            EvidenceCitation.model_validate(citation)
            for citation in citations
        ]
        record = StudyEvidence(
            project_id=project_id,
            query=request.query,
            extraction_json=extraction.model_dump(mode="json"),
            citations_json=[
                citation.model_dump(mode="json")
                for citation in validated_citations
            ],
            status=status,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

    except EvidenceCitationError:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Generated evidence references failed validation",
        )
    except OllamaError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The local LLM service is unavailable",
        )
    except ValidationError:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="The generated extraction did not match the required schema",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        db.rollback()
        # Log the exception securely in production; don't expose internals.
        raise HTTPException(
            status_code=500,
            detail="Evidence extraction failed",
        )

    return EvidenceExtractionResponse(
        project_id=str(project_id),
        extraction_id=str(record.id),
        status=status,
        evidence=extraction,
        citations=validated_citations,
        warnings=warnings,
    )