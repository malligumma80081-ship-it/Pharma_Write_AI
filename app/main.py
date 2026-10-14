from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import APP_NAME, APP_VERSION
from app.llm import generate_scientific_summary

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "AI-assisted scientific literature writing "
        "prototype for human-reviewed evidence summaries."
    ),
)


class SummaryRequest(BaseModel):
    source_text: str = Field(
        min_length=1,
        max_length=12000,
        description="Text from an authorized scientific source.",
    )


class SummaryResponse(BaseModel):
    status: str
    summary: str
    review_required: bool = True


@app.get("/")
def root():
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "message": "PharmaWrite AI backend is running.",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


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
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc