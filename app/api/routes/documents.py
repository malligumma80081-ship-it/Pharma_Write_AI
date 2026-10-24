from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.models import Document, Project, User
from app.db.session import get_db
from app.services.pdf_parser import (
    PDFExtractionError,
    extract_pdf_text,
)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Documents"],
)

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
PDF_SIGNATURE = b"%PDF-"


@router.post("/{project_id}/documents", status_code=201)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("writer", "admin")),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    filename = (file.filename or "").replace("\\", "/").split("/")[-1]

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415,
            detail="Only PDF files are supported.",
        )

    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=415,
            detail="The uploaded file must be a PDF.",
        )

    try:
        # Read one extra byte to detect files larger than the limit.
        file_bytes = await file.read(MAX_FILE_SIZE + 1)

        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File size exceeds the 15 MB limit.",
            )

        if not file_bytes.startswith(PDF_SIGNATURE):
            raise HTTPException(
                status_code=415,
                detail="The file does not have a valid PDF signature.",
            )

        try:
            extracted = extract_pdf_text(file_bytes)
        except PDFExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        document = Document(
            project_id=project.id,
            filename=filename[:255],
            content_type="application/pdf",
            file_size_bytes=len(file_bytes),
            page_count=extracted["page_count"],
            extracted_text=extracted["extracted_text"],
            status="extracted",
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return {
            "id": str(document.id),
            "project_id": document.project_id,
            "filename": document.filename,
            "page_count": document.page_count,
            "character_count": extracted["character_count"],
            "status": document.status,
            "message": "PDF text extracted and saved successfully.",
        }

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save the document.",
        ) from exc
    finally:
        await file.close()

@router.get("/{project_id}/documents")
def list_documents(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("writer", "admin")),
):
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    documents = (
        db.query(Document)
        .filter(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(document.id),
            "filename": document.filename,
            "page_count": document.page_count,
            "file_size_bytes": document.file_size_bytes,
            "status": document.status,
            "created_at": document.created_at,
        }
        for document in documents
    ]        