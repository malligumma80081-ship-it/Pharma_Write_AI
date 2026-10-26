"""Index extracted documents for persistent knowledge-base search."""

from app.services.chunking import chunk_document
from app.services.vector_store import index_chunks


def index_document_text(
    extracted_text: str,
    document_id: str,
    project_id: str,
    filename: str,
) -> int:
    chunks = chunk_document(extracted_text)
    if not chunks:
        raise ValueError("No searchable text chunks were generated.")

    return index_chunks(
        chunks=chunks,
        document_id=document_id,
        project_id=project_id,
        filename=filename,
    )
