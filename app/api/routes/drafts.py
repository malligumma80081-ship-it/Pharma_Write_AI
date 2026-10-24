
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Document, Project
from app.db.session import get_db
from app.schemas.writing import (
    LiteratureDraftRequest,
    LiteratureDraftResponse,
)
from app.services.ollama_client import OllamaError
from app.services.rag_writer import (
    CitationValidationError,
    generate_literature_draft,
)


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Medical Writing"],
)


@router.post(
    "/{project_id}/drafts",
    response_model=LiteratureDraftResponse,
)
def create_literature_draft(
    project_id: int,
    request: LiteratureDraftRequest,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    if (
        request.page_from is not None
        and request.page_to is not None
        and request.page_from > request.page_to
    ):
        raise HTTPException(
            status_code=422,
            detail="page_from cannot exceed page_to.",
        )

    if request.document_ids is not None:
        try:
            requested_ids = [
                uuid.UUID(value)
                for value in request.document_ids
            ]
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Each document_id must be a valid UUID.",
            ) from exc

        found = (
            db.query(Document.id)
            .filter(
                Document.project_id == project_id,
                Document.id.in_(requested_ids),
            )
            .all()
        )

        found_ids = {str(row[0]) for row in found}

        if found_ids != {str(value) for value in requested_ids}:
            raise HTTPException(
                status_code=404,
                detail="One or more documents were not found in this project.",
            )

    try:
        return generate_literature_draft(
            project_id=str(project_id),
            research_question=request.research_question,
            top_k=request.top_k,
            document_ids=request.document_ids,
            page_from=request.page_from,
            page_to=request.page_to,
        )

    except ValidationError as exc:
        # The model output did not satisfy the expected schema.
        raise HTTPException(
            status_code=502,
            detail="The generated draft did not pass output validation.",
        ) from exc

    except CitationValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Generated citations failed validation. Retry or review manually.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except OllamaError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        # Log full diagnostic details securely in production.
        raise HTTPException(
            status_code=500,
            detail="Could not generate the literature draft.",
        ) from exc
