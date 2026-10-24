
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from app.db.models import Document, Project
from app.db.session import get_db
from app.schemas.retrieval import (
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.chunking import chunk_document
from app.services.retrieval import retrieve_evidence
from app.services.vector_store import index_chunks


router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Evidence Retrieval"],
)


def _parse_document_id(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value

    if isinstance(value, str):
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1].strip()
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise ValueError("document_id must be a valid UUID.") from exc

    raise ValueError("document_id must be a valid UUID.")


DocumentId = Annotated[uuid.UUID, BeforeValidator(_parse_document_id)]


@router.post(
    "/{project_id}/documents/{document_id}/index"
)
def index_document(
    project_id: int,
    document_id: DocumentId,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    document = db.get(Document, document_id)

    if document is None or document.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Document not found in this project.",
        )

    chunks = chunk_document(document.extracted_text)

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No searchable text chunks were generated.",
        )

    try:
        indexed_count = index_chunks(
            chunks=chunks,
            document_id=str(document.id),
            project_id=str(project.id),
            filename=document.filename,
        )
    except Exception as exc:
        # Log the full exception server-side in a production app.
        raise HTTPException(
            status_code=500,
            detail="Document indexing failed.",
        ) from exc

    return {
        "project_id": project.id,
        "document_id": str(document.id),
        "filename": document.filename,
        "chunk_count": indexed_count,
        "status": "indexed",
    }


@router.post(
    "/{project_id}/search",
    response_model=SearchResponse,
)
def search_project_evidence(
    project_id: int,
    request: SearchRequest,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    parsed_document_ids = None
    if request.document_ids is not None:
        try:
            parsed_document_ids = [
                uuid.UUID(document_id)
                for document_id in request.document_ids
            ]
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="Each document_id must be a valid UUID.",
            ) from exc

        project_documents = (
            db.query(Document.id)
            .filter(
                Document.project_id == project_id,
                Document.id.in_(parsed_document_ids),
            )
            .all()
        )
        allowed_ids = {str(row[0]) for row in project_documents}
        if allowed_ids != {str(item) for item in parsed_document_ids}:
            raise HTTPException(
                status_code=404,
                detail="One or more documents were not found in this project.",
            )

    try:
        results = retrieve_evidence(
            query=request.query,
            project_id=str(project_id),
            top_k=request.top_k,
            document_ids=(
                [str(document_id) for document_id in parsed_document_ids]
                if parsed_document_ids is not None
                else None
            ),
            page_from=request.page_from,
            page_to=request.page_to,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Log diagnostic details securely in production.
        raise HTTPException(
            status_code=500,
            detail="Evidence search failed.",
        ) from exc

    return SearchResponse(
        query=request.query,
        project_id=str(project_id),
        result_count=len(results),
        results=[
            SearchResult(**result)
            for result in results
        ],
    )
