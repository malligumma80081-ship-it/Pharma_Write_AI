
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO

from app.api.dependencies.auth import require_roles
from app.db.models import User
from app.db.session import get_db
from app.services.review_service import (
    ReviewError,
    get_current_revision,
)
from app.services.export_service import export_pdf, export_docx

router = APIRouter(prefix="/api/v1/projects", tags=["Document Export"])


def safe_filename(title: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_")
    return (value or "literature_review")[:80]


@router.get("/{project_id}/workflows/{workflow_id}/export")
def download_draft(
    project_id: str,
    workflow_id: UUID,
    format: str = Query(pattern="^(pdf|docx)$"),
    db: Session = Depends(get_db),
    reviewer: User = Depends(require_roles("reviewer", "admin")),
):
    try:
        revision = get_current_revision(
            db=db,
            project_id=project_id,
            workflow_id=workflow_id,
        )
    except ReviewError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    snapshot = revision.content_json

    if not isinstance(snapshot, dict):
        raise HTTPException(
            status_code=422,
            detail="Draft snapshot is not a valid object.",
        )

    # Adapt this normalization to your actual stored data structure.
    # Some workflows store the draft under snapshot["draft"].
    content = snapshot.get("draft", snapshot)

    if not isinstance(content, dict):
        raise HTTPException(
            status_code=422,
            detail="Draft content is not a valid object.",
        )

    citations = content.get("citations", snapshot.get("citations", []))

    if not isinstance(citations, list):
        citations = []

    title = str(content.get("title", "literature_review"))

    export_args = {
        "content": content,
        "citations": citations,
        "project_id": str(project_id),
        "workflow_id": str(workflow_id),
        "version_number": revision.version_number,
        "review_status": revision.status,
    }

    try:
        if format == "pdf":
            file_bytes = export_pdf(**export_args)
            media_type = "application/pdf"
            extension = "pdf"
        else:
            file_bytes = export_docx(**export_args)
            media_type = (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
            extension = "docx"
    except Exception as exc:
        # Log a sanitized error internally; do not log source text.
        raise HTTPException(
            status_code=500,
            detail="Document export failed.",
        ) from exc

    filename = (
        f"{safe_filename(title)}_v{revision.version_number}.{extension}"
    )

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
