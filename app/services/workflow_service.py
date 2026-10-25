import logging
import uuid

from sqlalchemy.orm import Session

from app.db.models import Document, LiteratureWorkflow
from app.services.chunking import TextChunk
from app.services.vector_store import index_chunks
from app.services.evidence_extractor import (
    EvidenceCitationError,
    extract_study_evidence,
)
from app.services.ollama_client import OllamaError
from app.services.rag_writer import generate_literature_draft

logger = logging.getLogger(__name__)


def make_chunks(text: str, chunk_size: int = 500, overlap: int = 80):
    """Split extracted PDF text while preserving page boundaries."""
    chunks = []
    current_page = 1

    for page_text in text.split("--- Page ")[1:]:
        page_number, separator, content = page_text.partition(" ---")
        if not separator:
            # Support page markers without a trailing space/dash format.
            content = page_text
            page_number = str(current_page)

        try:
            current_page = int(page_number.split()[0])
        except (ValueError, IndexError):
            pass

        words = content.split()
        start = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])

            if chunk_text.strip():
                chunks.append(
                    TextChunk(
                        chunk_index=len(chunks),
                        text=chunk_text,
                        page_start=current_page,
                        page_end=current_page,
                    )
                )

            if end == len(words):
                break

            start = end - overlap

    return chunks


def update_stage(db, workflow, stage):
    workflow.current_stage = stage
    db.add(workflow)
    db.commit()
    db.refresh(workflow)


def run_literature_workflow(
    db: Session,
    workflow: LiteratureWorkflow,
    document_ids: list[uuid.UUID],
    top_k: int = 8,
):
    """Run the MVP workflow and persist the final result."""
    try:
        workflow.status = "running"
        workflow.error_message = None
        update_stage(db, workflow, "validating_documents")

        documents = db.query(Document).filter(
            Document.project_id == workflow.project_id,
            Document.id.in_(document_ids),
        ).all()

        if len(documents) != len(set(document_ids)):
            raise ValueError(
                "One or more documents do not belong to this project."
            )

        if not documents:
            raise ValueError("No documents were selected.")

        update_stage(db, workflow, "indexing_documents")

        for document in documents:
            if not document.extracted_text:
                raise ValueError(
                    f"No extracted text available for {document.filename}."
                )

            chunks = make_chunks(document.extracted_text)

            if not chunks:
                raise ValueError(
                    f"No indexable text found in {document.filename}."
                )

            index_chunks(
                chunks=chunks,
                document_id=str(document.id),
                project_id=str(workflow.project_id),
                filename=document.filename,
            )

        selected_ids = [str(value) for value in document_ids]

        update_stage(db, workflow, "extracting_evidence")

        extraction, citations, extraction_warnings = (
            extract_study_evidence(
                project_id=str(workflow.project_id),
                query=workflow.research_question,
                top_k=top_k,
                document_ids=selected_ids,
            )
        )

        update_stage(db, workflow, "generating_draft")

        draft = generate_literature_draft(
            project_id=str(workflow.project_id),
            research_question=workflow.research_question,
            top_k=top_k,
            document_ids=selected_ids,
        )

        # Pydantic models and dictionaries both occur in this project.
        draft_data = (
            draft.model_dump(mode="json")
            if hasattr(draft, "model_dump")
            else draft
        )

        update_stage(db, workflow, "preparing_review")

        workflow.result_json = {
            "evidence": (
                extraction.model_dump(mode="json")
                if hasattr(extraction, "model_dump")
                else extraction
            ),
            "evidence_citations": citations,
            "draft": draft_data,
            "warnings": extraction_warnings + [
                "Draft requires qualified human review.",
                "Citation existence does not establish claim accuracy.",
            ],
            "review_status": "pending_human_review",
        }
        workflow.status = "completed"
        workflow.current_stage = "pending_human_review"
        db.add(workflow)
        db.commit()
        db.refresh(workflow)

        return workflow

    except Exception as exc:
        db.rollback()

        # Avoid exposing internal exception details to API clients.
        logger.exception(
            "Literature workflow failed: workflow_id=%s",
            workflow.id,
        )

        workflow = db.query(LiteratureWorkflow).filter(
            LiteratureWorkflow.id == workflow.id
        ).first()

        if workflow:
            workflow.status = "failed"
            workflow.current_stage = "failed"
            workflow.error_message = (
                str(exc)
                if isinstance(
                    exc,
                    (ValueError, OllamaError, EvidenceCitationError),
                )
                else "Workflow failed. Check server logs."
            )
            db.add(workflow)
            db.commit()
            db.refresh(workflow)

        raise