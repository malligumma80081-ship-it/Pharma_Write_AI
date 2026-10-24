"""PDF text extraction service."""

class PDFExtractionError(Exception):
    """Raised when a PDF cannot be safely extracted."""


# MAX_PAGES = 300
# MAX_EXTRACTED_CHARACTERS = 2_000_000

MAX_PDF_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_PAGES = 300
MAX_EXTRACTED_CHARACTERS = 2_000_000

def extract_pdf_text(file_bytes: bytes) -> dict:
    if not file_bytes:
        raise PDFExtractionError("The uploaded file is empty.")

    import pymupdf

    try:
        with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
            if pdf.is_encrypted:
                raise PDFExtractionError(
                    "Password-protected PDFs are not supported."
                )

            page_count = pdf.page_count

            if page_count == 0:
                raise PDFExtractionError("The PDF contains no pages.")

            if page_count > MAX_PAGES:
                raise PDFExtractionError(
                    f"The PDF exceeds the {MAX_PAGES}-page limit."
                )

            pages = []
            total_characters = 0

            for page_number, page_index in enumerate(range(page_count), start=1):
                page = pdf.load_page(page_index)
                text = page.get_text("text").strip()

                if text:
                    pages.append(
                        f"\n--- Page {page_number} ---\n{text}"
                    )
                    total_characters += len(text)

                if total_characters > MAX_EXTRACTED_CHARACTERS:
                    raise PDFExtractionError(
                        "The extracted text exceeds the allowed size."
                    )

            extracted_text = "\n".join(pages).strip()

            if len(extracted_text) < 100:
                raise PDFExtractionError(
                    "Very little text was extracted. "
                    "The PDF may be scanned or image-based."
                )

            return {
                "page_count": page_count,
                "extracted_text": extracted_text,
                "character_count": len(extracted_text),
            }

    except PDFExtractionError:
        raise
    except Exception as exc:
        raise PDFExtractionError(
            "Unable to read this PDF. Check that it is a valid PDF file."
        ) from exc

import fitz


def validate_and_extract_pdf(file_bytes: bytes) -> dict:
    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    if len(file_bytes) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the 15 MB limit.")

    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("File does not have a valid PDF signature.")

    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
            if pdf.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")

            if len(pdf) == 0 or len(pdf) > MAX_PAGES:
                raise ValueError(
                    f"PDF must contain between 1 and {MAX_PAGES} pages."
                )

            pages = []
            total_chars = 0

            for page_number, page_index in enumerate(range(len(pdf)), start=1):
                page = pdf.load_page(page_index)
                page_text = page.get_text("text")
                total_chars += len(page_text)

                if total_chars > MAX_EXTRACTED_CHARACTERS:
                    raise ValueError(
                        "Extracted PDF text exceeds the allowed limit."
                    )

                pages.append(
                    f"--- Page {page_number} ---\n{page_text}"
                )

            text = "\n\n".join(pages)

            if len(text.strip()) < 50:
                raise ValueError(
                    "Insufficient selectable text. OCR may be required."
                )

            return {
                "page_count": len(pdf),
                "extracted_text": text,
            }

    except fitz.FileDataError as exc:
        raise ValueError("The PDF could not be parsed.") from exc