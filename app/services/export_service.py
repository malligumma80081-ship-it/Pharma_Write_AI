
from io import BytesIO
from html import escape
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    KeepTogether,
)


def _text(value: Any) -> str:
    """Convert a simple field to safe display text."""
    if value is None:
        return "Not reported in the available draft."

    if isinstance(value, (str, int, float, bool)):
        return str(value)

    return str(value)


def _list_items(value: Any) -> list:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _citation_label(citation: dict) -> str:
    """Format source metadata without inventing bibliographic details."""
    evidence_id = _text(citation.get("evidence_id", "Unknown evidence ID"))
    filename = _text(citation.get("filename", "Unknown source"))
    page_start = citation.get("page_start")
    page_end = citation.get("page_end")

    if page_start is not None and page_end is not None:
        page_text = (
            f"page {page_start}"
            if page_start == page_end
            else f"pages {page_start}-{page_end}"
        )
    elif page_start is not None:
        page_text = f"page {page_start}"
    else:
        page_text = "page not available"

    return f"{evidence_id} — {filename}, {page_text}"


def _render_item(item: Any) -> str:
    """Render common structured findings without dropping their fields."""
    if isinstance(item, str):
        return item

    if isinstance(item, dict):
        parts = []

        for key, value in item.items():
            if value is None:
                continue

            if isinstance(value, list):
                value = ", ".join(_text(entry) for entry in value)

            parts.append(f"{key.replace('_', ' ').title()}: {_text(value)}")

        return " | ".join(parts) or "No content supplied."

    return _text(item)


def _sections(content: dict) -> list[tuple[str, Any]]:
    return [
        ("Executive Summary", content.get("executive_summary")),
        ("Key Findings", content.get("key_findings", [])),
        ("Limitations", content.get("limitations", [])),
        ("Evidence Gaps", content.get("evidence_gaps", [])),
        ("Conclusion", content.get("conclusion")),
    ]


def export_pdf(
    content: dict,
    citations: list[dict],
    *,
    project_id: str,
    workflow_id: str,
    version_number: int,
    review_status: str,
) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=_text(content.get("title", "Literature Review Draft")),
        author="PharmaWrite AI",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="ReportBody",
        parent=styles["BodyText"],
        leading=15,
        spaceAfter=8,
    ))

    story = [
        Spacer(1, 25 * mm),
        Paragraph(
            escape(_text(content.get("title", "Literature Review Draft"))),
            styles["ReportTitle"],
        ),
        Paragraph(
            "<b>PharmaWrite AI — Scientific Literature Summary</b>",
            styles["BodyText"],
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            f"<b>Review status:</b> {escape(review_status)}",
            styles["BodyText"],
        ),
        Paragraph(
            f"<b>Revision:</b> {version_number}",
            styles["BodyText"],
        ),
        Paragraph(
            "<b>Project ID:</b> " + escape(project_id),
            styles["BodyText"],
        ),
        Paragraph(
            "<b>Workflow ID:</b> " + escape(workflow_id),
            styles["BodyText"],
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            "<b>Review notice:</b> AI-generated content. "
            "Verify findings and source citations against the original "
            "documents. This export does not independently establish "
            "scientific validity or regulatory compliance.",
            styles["ReportBody"],
        ),
        PageBreak(),
    ]

    for heading, value in _sections(content):
        story.append(Paragraph(escape(heading), styles["Heading2"]))

        if isinstance(value, list):
            if not value:
                story.append(Paragraph("No items supplied.", styles["ReportBody"]))
            else:
                for item in value:
                    story.append(Paragraph(
                        "• " + escape(_render_item(item)),
                        styles["ReportBody"],
                    ))
        else:
            story.append(Paragraph(
                escape(_text(value)),
                styles["ReportBody"],
            ))

        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Source References", styles["Heading1"]))

    if citations:
        for citation in citations:
            story.append(Paragraph(
                escape(_citation_label(citation)),
                styles["ReportBody"],
            ))
    else:
        story.append(Paragraph(
            "No citation metadata supplied. Verify sources before use.",
            styles["ReportBody"],
        ))

    doc.build(story)
    return buffer.getvalue()


def export_docx(
    content: dict,
    citations: list[dict],
    *,
    project_id: str,
    workflow_id: str,
    version_number: int,
    review_status: str,
) -> bytes:
    document = Document()

    section = document.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)

    title = document.add_heading(
        _text(content.get("title", "Literature Review Draft")),
        level=0,
    )
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_paragraph("PharmaWrite AI — Scientific Literature Summary")
    document.add_paragraph(f"Review status: {review_status}")
    document.add_paragraph(f"Revision: {version_number}")
    document.add_paragraph(f"Project ID: {project_id}")
    document.add_paragraph(f"Workflow ID: {workflow_id}")

    notice = document.add_paragraph()
    notice.add_run("Review notice: ").bold = True
    notice.add_run(
        "AI-generated content. Verify findings and citations against "
        "the original documents. Export does not independently establish "
        "scientific validity or regulatory compliance."
    )

    for heading, value in _sections(content):
        document.add_heading(heading, level=1)

        if isinstance(value, list):
            if not value:
                document.add_paragraph("No items supplied.")
            else:
                for item in value:
                    document.add_paragraph(
                        _render_item(item),
                        style="List Bullet",
                    )
        else:
            document.add_paragraph(_text(value))

    document.add_heading("Source References", level=1)

    if citations:
        for citation in citations:
            document.add_paragraph(
                _citation_label(citation),
                style="List Number",
            )
    else:
        document.add_paragraph(
            "No citation metadata supplied. Verify sources before use."
        )

    # Set a readable default font.
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Arial"
            run.font.size = Pt(10)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
