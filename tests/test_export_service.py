
from io import BytesIO

from docx import Document
from pypdf import PdfReader

from app.services.export_service import export_pdf, export_docx


def sample_content():
    return {
        "title": "Scientific Literature Review",
        "executive_summary": "The study enrolled 120 participants.",
        "key_findings": [
            {
                "statement": "The study enrolled 120 participants.",
                "evidence_ids": ["E1"],
            }
        ],
        "limitations": ["Single-center study."],
        "evidence_gaps": ["Long-term outcomes were not reported."],
        "conclusion": "Further review is required.",
    }


def sample_citations():
    return [{
        "evidence_id": "E1",
        "filename": "study.pdf",
        "page_start": 3,
        "page_end": 3,
    }]


def test_pdf_export():
    result = export_pdf(
        sample_content(),
        sample_citations(),
        project_id="project-test",
        workflow_id="workflow-test",
        version_number=2,
        review_status="pending_review",
    )

    assert result.startswith(b"%PDF")
    assert len(result) > 100

    reader = PdfReader(BytesIO(result))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Scientific Literature Review" in text
    assert "120 participants" in text
    assert "study.pdf" in text
    assert "pending_review" in text


def test_docx_export():
    result = export_docx(
        sample_content(),
        sample_citations(),
        project_id="project-test",
        workflow_id="workflow-test",
        version_number=2,
        review_status="pending_review",
    )

    document = Document(BytesIO(result))
    text = "\n".join(p.text for p in document.paragraphs)

    assert "Scientific Literature Review" in text
    assert "120 participants" in text
    assert "study.pdf" in text
    assert "pending_review" in text
