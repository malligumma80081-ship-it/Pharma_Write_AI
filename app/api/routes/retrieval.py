
import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BeforeValidator
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.models import Document, Project
from app.db.models import User
from app.db.session import get_db
from app.schemas.retrieval import (
    KnowledgeAnswerResponse,
    KnowledgeQuestionRequest,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.document_indexer import index_document_text
from app.services.knowledge_base import answer_knowledge_question
from app.services.ollama_client import OllamaError
from app.services.retrieval import retrieve_evidence

logger = logging.getLogger(__name__)


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
    user: User = Depends(
        require_roles("writer", "project_manager", "admin")
    ),
):
    project = db.get(Project, project_id)

    if project is None or (
        user.role == "writer" and project.owner_id != user.id
    ):
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

    try:
        indexed_count = index_document_text(
            extracted_text=document.extracted_text,
            document_id=str(document.id),
            project_id=str(project.id),
            filename=document.filename,
        )
    except Exception as exc:
        logger.exception(
            "Document indexing failed for document_id=%s",
            document.id,
        )
        document.status = "indexing_failed"
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Document indexing failed.",
        ) from exc

    document.status = "indexed"
    db.commit()

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
    user: User = Depends(
        require_roles("writer", "project_manager", "admin")
    ),
):
    project = db.get(Project, project_id)

    if project is None or (
        user.role == "writer" and project.owner_id != user.id
    ):
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


@router.post(
    "/{project_id}/knowledge-base/ask",
    response_model=KnowledgeAnswerResponse,
)
def ask_knowledge_base(
    project_id: int,
    request: KnowledgeQuestionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles("writer", "project_manager", "admin")
    ),
):
    project = db.get(Project, project_id)
    if project is None or (
        user.role == "writer" and project.owner_id != user.id
    ):
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

        documents = (
            db.query(Document)
            .filter(
                Document.project_id == project_id,
                Document.id.in_(parsed_document_ids),
            )
            .all()
        )
        if {str(document.id) for document in documents} != {
            str(document_id) for document_id in parsed_document_ids
        }:
            raise HTTPException(
                status_code=404,
                detail="One or more documents were not found in this project.",
            )
    else:
        documents = (
            db.query(Document)
            .filter(Document.project_id == project_id)
            .all()
        )

    if not documents:
        raise HTTPException(
            status_code=409,
            detail="Upload a PDF before asking the project knowledge base.",
        )

    unindexed = [
        document.filename
        for document in documents
        if document.status != "indexed"
    ]
    if unindexed:
        raise HTTPException(
            status_code=409,
            detail=(
                "These documents are not indexed yet. Re-index them from "
                "the Documents page: "
                + ", ".join(unindexed)
            ),
        )

    try:
        answer, citations = answer_knowledge_question(
            project_id=str(project_id),
            query=request.query,
            top_k=request.top_k,
            document_ids=(
                [str(document_id) for document_id in parsed_document_ids]
                if parsed_document_ids is not None
                else None
            ),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except OllamaError as exc:
        raise HTTPException(
            status_code=503,
            detail="The local AI service could not answer this question.",
        ) from exc
    except Exception as exc:
        logger.exception(
            "Knowledge-base question failed for project_id=%s",
            project_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Knowledge-base search failed.",
        ) from exc

    return KnowledgeAnswerResponse(
        query=request.query,
        project_id=str(project_id),
        answer=answer,
        citations=citations,
    )
