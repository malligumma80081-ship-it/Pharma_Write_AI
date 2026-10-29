from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes.auth import router as auth_router
from app.api.routes.admin import router as admin_router
from app.api.routes.projects import router as projects_router
from app.core.config import APP_NAME, APP_VERSION
from app.db.session import get_db
from app.services.ollama_client import (
    generate_scientific_summary,
    get_ollama_status,
)

from app.api.routes.documents import router as documents_router
from app.api.routes.retrieval import router as retrieval_router
from app.api.routes.drafts import router as writing_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.verification import router as verification_router
from app.api.routes.workflow import router as workflow_router
from app.api.routes.assignments import router as assignments_router
from app.api.routes.review import (
    review_queue_router,
    router as review_router,
)
from app.api.routes.exports import router as exports_router

app = FastAPI(
    title="PharmaWrite AI",
    version="0.3.0",
    description="Scientific literature review and evidence-summary prototype.",
)

app.include_router(projects_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(writing_router)
app.include_router(evidence_router)
app.include_router(verification_router)
app.include_router(workflow_router)
app.include_router(assignments_router)
app.include_router(review_router)
app.include_router(review_queue_router)
app.include_router(exports_router)
class SummaryRequest(BaseModel):
    source_text: str = Field(min_length=1, max_length=12000)


class SummaryResponse(BaseModel):
    status: str
    summary: str
    review_required: bool = True


@app.get("/")
def root():
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "message": "PharmaWrite AI backend is running",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/database")
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        ) from exc


@app.get("/health/ollama")
def ollama_health():
    return get_ollama_status()


@app.post("/api/v1/summary", response_model=SummaryResponse)
def create_summary(request: SummaryRequest):
    try:
        summary = generate_scientific_summary(request.source_text)
        return SummaryResponse(
            status="success",
            summary=summary,
            review_required=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
