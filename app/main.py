# from fastapi import FastAPI, HTTPException
# from pydantic import BaseModel, Field

# from app.config import APP_NAME, APP_VERSION
# from app.llm import generate_scientific_summary

# app = FastAPI(
#     title=APP_NAME,
#     version=APP_VERSION,
#     description=(
#         "AI-assisted scientific literature writing "
#         "prototype for human-reviewed evidence summaries."
#     ),
# )


# class SummaryRequest(BaseModel):
#     source_text: str = Field(
#         min_length=1,
#         max_length=12000,
#         description="Text from an authorized scientific source.",
#     )


# class SummaryResponse(BaseModel):
#     status: str
#     summary: str
#     review_required: bool = True


# @app.get("/")
# def root():
#     return {
#         "app": APP_NAME,
#         "version": APP_VERSION,
#         "message": "PharmaWrite AI backend is running.",
#     }


# @app.get("/health")
# def health():
#     return {"status": "ok"}


# @app.post("/api/v1/summary", response_model=SummaryResponse)
# def create_summary(request: SummaryRequest):
#     try:
#         summary = generate_scientific_summary(request.source_text)

#         return SummaryResponse(
#             status="success",
#             summary=summary,
#             review_required=True,
#         )

#     except ValueError as exc:
#         raise HTTPException(
#             status_code=422,
#             detail=str(exc),
#         ) from exc

#     except RuntimeError as exc:
#         raise HTTPException(
#             status_code=503,
#             detail=str(exc),
#         ) from exc

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.config import APP_NAME, APP_VERSION
from db import models  # Registers SQLAlchemy models
from db.session import get_db
from api.routes.projects import router as projects_router
from app.llm import generate_scientific_summary

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Medical writing and scientific evidence summary prototype",
)

app.include_router(projects_router)


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
def health():
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